"""
backend/main.py

Orchestrates the full pipeline for any supported competition:
    1. Initialize database
    2. Fetch matches from Football-Data.org API
    3. Clean and store competitions, teams, matches
    4. Find unanalysed matches — most complete matchday (auto)
       or a specific matchday (--matchday N)
    5. For each unanalysed match:
       a. Fetch SofaScore stats and lineups
       b. Fetch SofaScore incidents (goals, cards, subs)
       c. Generate AI summary via Groq
       d. Save summary, events, and match stats to DB
    6. Sleep 3s between matches to respect Groq rate limits

--force FLAG:
    Normally the pipeline skips matches that already have summaries.
    --force deletes existing summaries for the target matchday before
    running, so they get regenerated from scratch.

    RULES:
      - --force REQUIRES --matchday. Without it the pipeline exits with
        an error. This prevents accidentally wiping auto-detected matchdays.
      - Only the summaries table rows for the specific competition +
        matchday are deleted. match_events and match_stats are kept —
        the pipeline overwrites them anyway via delete-then-insert.
      - Normal runs (no --force) are completely unaffected.

    USE CASE:
      Regenerating summaries that contain "Unknown player" text, generated
      before the cleaner.py Unknown filter was added in Session 15.

    EXAMPLE:
      python -m backend.main --competition PD --matchday 26 --force
      python -m backend.main --competition PL --matchday 29 --force

PROGRESS CALLBACK:
    run_pipeline() accepts an optional progress_callback parameter.
    Called by routes.py to report live progress to the frontend.
    CLI runs pass no callback — all callback calls are no-ops.

CLI USAGE:
    python -m backend.main
    python -m backend.main --competition CL
    python -m backend.main --competition PD --matchday 26
    python -m backend.main --competition PD --matchday 26 --force

SUPPORTED COMPETITION CODES:
    PL, CL, PD, BL1, SA, FL1
"""

import sys
import time
import argparse
from datetime import datetime
from typing import Callable, Optional

from backend.db.schema import init_db, Summary, Match, Competition
from backend.db.writer import (
    save_competitions,
    save_teams,
    save_matches,
    save_match_events,
    save_match_stats,
    save_summary,
    get_match_ids_in_db,
)
from backend.scrapers.football_data_api import (
    get_competitions,
    get_matches_by_competition,
)
from backend.processors.cleaner import (
    clean_competitions,
    clean_teams_from_matches,
    clean_matches,
    clean_sofascore_stats,
    clean_sofascore_lineups,
    clean_match_incidents,
    build_match_context,
)
from backend.summarizer.summarize import summarize_match
from backend.db.schema import engine
from sqlalchemy.orm import sessionmaker

SessionLocal = sessionmaker(bind=engine)


# -------------------------------------------------------------------------
# Competition registry
# -------------------------------------------------------------------------

COMPETITIONS = {
    "PL":  {"id": 2021, "name": "Premier League"},
    "CL":  {"id": 2001, "name": "UEFA Champions League"},
    "PD":  {"id": 2014, "name": "La Liga"},
    "BL1": {"id": 2002, "name": "Bundesliga"},
    "SA":  {"id": 2019, "name": "Serie A"},
    "FL1": {"id": 2015, "name": "Ligue 1"},
}

DEFAULT_COMPETITION = "PL"
GROQ_DELAY_SECONDS = 3


# -------------------------------------------------------------------------
# Force regenerate helper
# -------------------------------------------------------------------------

def force_delete_summaries(competition_code: str,
                           target_matchday: int) -> int:
    """
    Deletes all summaries for a specific competition + matchday.
    Called when --force flag is used, before the pipeline runs.

    WHY DELETE ONLY SUMMARIES AND NOT EVENTS/STATS:
        The pipeline's "already analysed" check only queries the summaries
        table. Deleting the summary row is enough to make the pipeline
        treat the match as unanalysed. match_events and match_stats use
        a delete-then-insert pattern in writer.py — they get overwritten
        automatically when the pipeline runs. Deleting them here first
        would be redundant.

    Returns:
        Number of summary rows deleted.
    """
    session = SessionLocal()
    try:
        # Step 1 — find all match IDs for this competition + matchday
        match_ids = [
            row.id
            for row in session.query(Match)
            .join(Competition, Match.competition_id == Competition.id)
            .filter(
                Competition.code == competition_code,
                Match.matchday == target_matchday,
            )
            .all()
        ]

        if not match_ids:
            print(f"      No matches found for {competition_code} MD{target_matchday}.")
            return 0

        # Step 2 — delete summaries for those match IDs
        # synchronize_session=False: skip SQLAlchemy's in-memory sync —
        # faster for bulk deletes where we don't need the objects afterward
        deleted = (
            session.query(Summary)
            .filter(Summary.match_id.in_(match_ids))
            .delete(synchronize_session=False)
        )
        session.commit()
        return deleted

    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


# -------------------------------------------------------------------------
# Pipeline steps
# -------------------------------------------------------------------------

def step_init():
    print("[1/5] Initializing database...")
    init_db()
    print("      Done.\n")


def step_fetch_and_store(competition_code: str,
                         competition_id: int) -> list:
    print(f"[2/5] Fetching matches for: {competition_code}...")

    raw_matches = get_matches_by_competition(competition_code)
    print(f"      Found {len(raw_matches)} matches from API.")

    raw_competitions = get_competitions()
    clean_comps = clean_competitions(raw_competitions)
    saved_comps = save_competitions(clean_comps)
    print(f"      Saved {saved_comps} competition(s).")

    clean_team_list = clean_teams_from_matches(raw_matches)
    saved_teams = save_teams(clean_team_list)
    print(f"      Saved {saved_teams} team(s).")

    existing_ids = set(get_match_ids_in_db())
    new_raw_matches = [
        m for m in raw_matches if m.get("id") not in existing_ids
    ]
    print(f"      {len(new_raw_matches)} new match(es) to save "
          f"(skipping {len(existing_ids)} already in DB).")

    if new_raw_matches:
        clean_match_list = clean_matches(new_raw_matches, competition_id)
        saved_matches = save_matches(clean_match_list)
        print(f"      Saved {saved_matches} new match(es).\n")
    else:
        print("      No new matches to save.\n")

    return raw_matches


def step_get_unanalysed_matches(raw_matches: list,
                                target_matchday: int | None = None) -> list:
    finished = [m for m in raw_matches if m.get("status") == "FINISHED"]

    if not finished:
        print("      No finished matches found.\n")
        return []

    if target_matchday is not None:
        print(f"[3/5] Backfill mode — targeting MD{target_matchday}...")
        matchday_matches = [
            m for m in finished if m.get("matchday") == target_matchday
        ]
        if not matchday_matches:
            print(f"      No finished matches found for MD{target_matchday}.\n")
            return []
        total_in_md = sum(
            1 for m in raw_matches if m.get("matchday") == target_matchday
        )
        print(f"      MD{target_matchday}: {len(matchday_matches)}/{total_in_md} finished")

    else:
        print("[3/5] Finding unanalysed matches from most complete matchday...")
        matchday_counts = {}
        for m in finished:
            md = m.get("matchday", 0)
            matchday_counts[md] = matchday_counts.get(md, 0) + 1

        chosen_md = max(
            matchday_counts,
            key=lambda md: (matchday_counts[md], md)
        )
        finished_count = matchday_counts[chosen_md]
        total_in_md = sum(
            1 for m in raw_matches if m.get("matchday") == chosen_md
        )
        print(f"      Most complete matchday: MD{chosen_md} "
              f"({finished_count}/{total_in_md} finished)")
        matchday_matches = [
            m for m in finished if m.get("matchday") == chosen_md
        ]

    session = SessionLocal()
    try:
        existing_summary_ids = {
            row.match_id
            for row in session.query(Summary.match_id).all()
        }
    finally:
        session.close()

    unanalysed = [
        m for m in matchday_matches
        if m.get("id") not in existing_summary_ids
    ]
    unanalysed.sort(key=lambda m: m.get("utcDate", ""))

    already_done = len(matchday_matches) - len(unanalysed)
    print(f"      Already analysed: {already_done}")
    print(f"      Need analysis:    {len(unanalysed)}\n")

    return unanalysed


def step_fetch_sofascore_data(raw_match: dict) -> dict:
    from backend.scrapers.sofascore import get_full_match_data

    home_team = raw_match.get("homeTeam", {}).get("name", "")
    away_team = raw_match.get("awayTeam", {}).get("name", "")
    date_str = raw_match.get("utcDate", "")[:10]

    print(f"      Fetching SofaScore: {home_team} vs {away_team}...")

    try:
        result = get_full_match_data(date_str, home_team, away_team)
        if not result:
            print("      Not found on SofaScore — using match data only.")
            return {}

        cleaned_stats = clean_sofascore_stats(
            result["statistics"], home_team, away_team
        )
        cleaned_lineups = clean_sofascore_lineups(result["lineups"])
        hint_count = len(cleaned_stats.get("narrative_hints", []))
        confirmed = cleaned_lineups.get("confirmed", False)
        print(f"      Stats OK. Hints: {hint_count} | Lineups confirmed: {confirmed}")

        return {
            "stats": cleaned_stats,
            "lineups": cleaned_lineups,
            "raw_incidents": result.get("incidents", {}),
            "sofascore_match_id": result.get("match_id"),
        }

    except Exception as e:
        print(f"      SofaScore fetch failed: {e} — continuing without stats.")
        return {}


def step_fetch_incidents(sofascore_data: dict, home_team: str,
                         away_team: str) -> dict:
    raw_incidents = sofascore_data.get("raw_incidents", {})
    if not raw_incidents:
        return {}

    try:
        cleaned = clean_match_incidents(raw_incidents, home_team, away_team)
        goal_count = len(cleaned.get("goals", []))
        card_count = len(cleaned.get("cards", []))
        sub_count  = len(cleaned.get("substitutions", []))
        print(f"      Incidents: {goal_count} goals | {card_count} cards | {sub_count} subs")
        return cleaned
    except Exception as e:
        print(f"      Incidents processing failed: {e}")
        return {}


def step_summarize(raw_match: dict, competition_name: str,
                   sofascore_data: dict, incidents: dict) -> str:
    match_data = {
        "home_team": raw_match.get("homeTeam", {}).get("name", "Unknown"),
        "away_team": raw_match.get("awayTeam", {}).get("name", "Unknown"),
        "home_score": raw_match.get("score", {}).get("fullTime", {}).get("home"),
        "away_score": raw_match.get("score", {}).get("fullTime", {}).get("away"),
        "competition": competition_name,
        "matchday": raw_match.get("matchday"),
        "date": raw_match.get("utcDate", "")[:10],
    }

    if sofascore_data:
        context = build_match_context(
            match_data,
            sofascore_data.get("stats", {}),
            sofascore_data.get("lineups", {}),
            sofascore_incidents=incidents,
        )
    else:
        context = {
            **match_data,
            "home_stats": {}, "away_stats": {},
            "narrative_hints": [],
            "home_formation": "Unknown", "away_formation": "Unknown",
            "home_players": [], "away_players": [],
            "lineups_confirmed": False,
            "goals": [], "cards": [], "substitutions": [],
            "events_text": incidents.get("events_text", ""),
        }

    return summarize_match(context)


def step_save(match_id: int, summary: str, incidents: dict,
              raw_match: dict, sofascore_data: dict):
    save_summary(match_id, summary)

    if incidents:
        saved_events = save_match_events(match_id, incidents)
        print(f"      Saved {saved_events} event(s) to DB.")

    if sofascore_data and sofascore_data.get("stats"):
        cleaned_stats = sofascore_data["stats"]
        match_team_ids = {
            "home_team_id": raw_match.get("homeTeam", {}).get("id"),
            "away_team_id": raw_match.get("awayTeam", {}).get("id"),
        }
        saved_stats = save_match_stats(match_id, match_team_ids, cleaned_stats)
        if saved_stats:
            print(f"      Saved match stats (home + away) to DB.")


# -------------------------------------------------------------------------
# Main entry point
# -------------------------------------------------------------------------

def run_pipeline(
    competition_code: str = DEFAULT_COMPETITION,
    competition_id: int = None,
    competition_name: str = None,
    target_matchday: int | None = None,
    force: bool = False,
    progress_callback: Optional[Callable] = None,
) -> list:
    """
    Runs the full ETL + summarization pipeline for a competition.

    Args:
        competition_code:   e.g. "PL", "CL", "PD"
        competition_id:     numeric DB id — looked up if None
        competition_name:   human name for AI prompt — looked up if None
        target_matchday:    specific matchday to process, or None for auto
        force:              delete existing summaries before running
                            REQUIRES target_matchday — errors if None
        progress_callback:  optional fn(event, data) for live progress
    """
    def _cb(event: str, data: dict):
        if progress_callback:
            progress_callback(event, data)

    # Guard: --force without --matchday is dangerous — reject it
    if force and target_matchday is None:
        raise ValueError(
            "--force requires --matchday. "
            "Specify which matchday to regenerate, e.g. --matchday 26 --force"
        )

    if competition_code not in COMPETITIONS:
        raise ValueError(
            f"Unknown competition code: {competition_code}. "
            f"Supported: {', '.join(COMPETITIONS.keys())}"
        )

    comp_meta = COMPETITIONS[competition_code]
    if competition_id is None:
        competition_id = comp_meta["id"]
    if competition_name is None:
        competition_name = comp_meta["name"]

    start = datetime.now()
    mode = f"BACKFILL MD{target_matchday}" if target_matchday else "AUTO"
    if force:
        mode += " (FORCE REGENERATE)"

    print("=" * 55)
    print(f"  FOOTBALL ANALYTICS PIPELINE — V2")
    print(f"  Competition: {competition_name} ({competition_code})")
    print(f"  Mode: {mode}")
    print(f"  Started: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55 + "\n")

    step_init()

    # --force: wipe existing summaries so pipeline treats them as new
    if force:
        print(f"[FORCE] Deleting existing summaries for "
              f"{competition_code} MD{target_matchday}...")
        deleted = force_delete_summaries(competition_code, target_matchday)
        print(f"[FORCE] Deleted {deleted} summary/summaries. "
              f"Will regenerate from scratch.\n")

    raw_matches = step_fetch_and_store(competition_code, competition_id)
    if not raw_matches:
        print("No matches returned from API. Exiting.")
        _cb("up_to_date", {})
        return []

    unanalysed = step_get_unanalysed_matches(raw_matches, target_matchday)
    if not unanalysed:
        md_label = f"MD{target_matchday}" if target_matchday else "the most complete matchday"
        print(f"All matches from {md_label} are already analysed.")
        print("Nothing to do.\n")
        _cb("up_to_date", {})
        _cb("complete", {})
        return []

    total = len(unanalysed)
    print(f"[4/5] Processing {total} match(es)...\n")
    _cb("total_found", {"total": total})

    results = []

    for i, raw_match in enumerate(unanalysed, start=1):
        home = raw_match.get("homeTeam", {}).get("name", "Unknown")
        away = raw_match.get("awayTeam", {}).get("name", "Unknown")
        match_id = raw_match.get("id")

        print(f"  [{i}/{total}] {home} vs {away} (ID: {match_id})")
        _cb("match_start", {"index": i, "total": total, "home": home, "away": away})

        try:
            sofascore_data = step_fetch_sofascore_data(raw_match)
            incidents = step_fetch_incidents(sofascore_data, home, away)
            print(f"      Generating AI summary...")
            summary = step_summarize(
                raw_match, competition_name, sofascore_data, incidents
            )
            step_save(match_id, summary, incidents, raw_match, sofascore_data)
            print(f"      ✓ Done.\n")
            _cb("match_done", {"status": "ok", "home": home, "away": away})
            results.append({
                "match_id": match_id,
                "home_team": home,
                "away_team": away,
                "status": "ok",
            })

        except Exception as e:
            print(f"      ✗ Failed: {e}\n")
            _cb("match_done", {"status": "error", "home": home, "away": away})
            results.append({
                "match_id": match_id,
                "home_team": home,
                "away_team": away,
                "status": "error",
                "error": str(e),
            })

        if i < total:
            print(f"      Waiting {GROQ_DELAY_SECONDS}s before next match...")
            time.sleep(GROQ_DELAY_SECONDS)

    elapsed = (datetime.now() - start).seconds
    ok_count   = sum(1 for r in results if r["status"] == "ok")
    fail_count = len(results) - ok_count

    print("=" * 55)
    print(f"  PIPELINE COMPLETE — {competition_name}")
    print(f"  Analysed: {ok_count} match(es)")
    if fail_count:
        print(f"  Failed:   {fail_count} match(es)")
    print(f"  Time elapsed: {elapsed}s")
    print("=" * 55 + "\n")

    _cb("complete", {"ok": ok_count, "failed": fail_count})
    return results


# -------------------------------------------------------------------------
# CLI entry point
# -------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Football Analytics Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m backend.main                                        # PL, auto
  python -m backend.main --competition CL                       # CL, auto
  python -m backend.main --competition PD --matchday 26         # La Liga MD26
  python -m backend.main --competition PD --matchday 26 --force # regenerate

--force requires --matchday. Deletes existing summaries for that matchday
and regenerates from scratch. Use to fix summaries generated before a
prompt fix (e.g. Unknown player filter added in Session 15).

Supported competition codes: PL, CL, PD, BL1, SA, FL1
        """
    )
    parser.add_argument(
        "--competition",
        type=str,
        default=DEFAULT_COMPETITION,
        choices=list(COMPETITIONS.keys()),
        help="Competition code (default: PL)"
    )
    parser.add_argument(
        "--matchday",
        type=int,
        default=None,
        help="Specific matchday to process (default: auto-detect)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Delete existing summaries and regenerate. Requires --matchday."
    )
    args = parser.parse_args()

    run_pipeline(
        competition_code=args.competition,
        target_matchday=args.matchday,
        force=args.force,
    )
