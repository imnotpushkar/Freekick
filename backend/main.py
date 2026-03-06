"""
backend/main.py

Orchestrates the full pipeline:
    1. Initialize database
    2. Fetch matches from Football-Data.org API
    3. Clean and store competitions, teams, matches
    4. Find unanalysed matches — either from the most complete matchday
       (default) or from a specific matchday (via target_matchday param)
    5. For each unanalysed match:
       a. Fetch SofaScore stats and lineups
       b. Fetch SofaScore incidents (goals, cards, subs)
       c. Generate AI summary via Groq
       d. Save summary and events to DB
    6. Sleep 3s between matches to respect Groq rate limits

RUNNING THE PIPELINE:

    Default mode — processes most complete unfinished matchday:
        python -m backend.main

    Backfill mode — processes a specific matchday:
        python -m backend.main --matchday 28

    The --matchday flag is for backfilling historical data.
    The frontend "Run Pipeline" button always uses default mode.

WHY target_matchday IS OPTIONAL:
    The pipeline needs two modes:
    1. Live mode (no argument): auto-detects the most complete matchday.
       This is what the frontend button triggers — it should always
       process the latest available round without manual input.
    2. Backfill mode (--matchday N): targets a specific historical round.
       This is for catching up on older matchdays that have no summaries.
       You control the pace, avoiding Groq daily token limits.

    Both modes share all the same step functions — only the matchday
    selection logic differs.
"""

import sys
import time
import argparse
from datetime import datetime

from backend.db.schema import init_db, Summary
from backend.db.writer import (
    save_competitions,
    save_teams,
    save_matches,
    save_match_events,
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
# Configuration
# -------------------------------------------------------------------------

TARGET_COMPETITION_CODE = "PL"
TARGET_COMPETITION_ID = 2021
TARGET_COMPETITION_NAME = "Premier League"

# Seconds to wait between Groq API calls.
# Groq free tier: 30 requests/minute, 6000 tokens/minute on llama-3.3-70b.
# Each summary uses ~1500 tokens output + ~800 input = ~2300 tokens.
# At 6000 tokens/minute we can do ~2.6 matches/minute safely.
# 3 seconds between calls keeps us well within this limit.
GROQ_DELAY_SECONDS = 3


# -------------------------------------------------------------------------
# Pipeline steps
# -------------------------------------------------------------------------

def step_init():
    """Step 1: Ensure DB exists with all tables."""
    print("[1/5] Initializing database...")
    init_db()
    print("      Done.\n")


def step_fetch_and_store(competition_code: str,
                         competition_id: int) -> list:
    """
    Step 2: Fetch matches from Football-Data.org, clean, save to DB.
    Skips matches already in DB to avoid redundant API calls.

    Returns:
        List of all raw match dicts from the API.
    """
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
    """
    Step 3: Find finished matches that need summarizing.

    Two modes depending on target_matchday:

    AUTO MODE (target_matchday=None):
        Counts finished matches per matchday and picks the one with
        the highest count. This handles out-of-order fixtures — a lone
        MD31 match won't beat a nearly-complete MD29 with 9 finished.
        Tiebreak: higher matchday number wins (more recent round).

    BACKFILL MODE (target_matchday=N):
        Directly targets matchday N. Useful for processing historical
        rounds that were skipped. The auto-detection logic is bypassed
        entirely — we just go straight to that matchday.

    Both modes skip matches that already have a summary in the DB,
    making every pipeline run idempotent (safe to re-run).

    Args:
        raw_matches:     All matches from the API for this competition.
        target_matchday: Specific matchday to process. None = auto-detect.

    Returns:
        List of raw match dicts that need summarizing, sorted
        chronologically by kick-off time.
    """
    finished = [m for m in raw_matches if m.get("status") == "FINISHED"]

    if not finished:
        print("      No finished matches found.\n")
        return []

    if target_matchday is not None:
        # --- BACKFILL MODE ---
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
        # --- AUTO MODE ---
        print("[3/5] Finding unanalysed matches from most complete matchday...")

        # Count finished matches per matchday
        matchday_counts = {}
        for m in finished:
            md = m.get("matchday", 0)
            matchday_counts[md] = matchday_counts.get(md, 0) + 1

        # Pick matchday with most finished matches.
        # Tiebreak: higher matchday number = more recent round wins.
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

    # Check which matches already have summaries — skip those
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

    # Sort by kick-off time — process chronologically
    unanalysed.sort(key=lambda m: m.get("utcDate", ""))

    already_done = len(matchday_matches) - len(unanalysed)
    print(f"      Already analysed: {already_done}")
    print(f"      Need analysis:    {len(unanalysed)}\n")

    return unanalysed


def step_fetch_sofascore_data(raw_match: dict) -> dict:
    """
    Fetch SofaScore statistics and lineups for a single match.

    Returns:
        Dict with stats, lineups, raw_incidents keys.
        Returns empty dict on failure — pipeline continues without stats.
    """
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
    """
    Clean match incidents (goals, cards, subs) from raw SofaScore data.

    Returns:
        Cleaned incidents dict, or empty dict if unavailable.
    """
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
    """
    Build full match context and generate AI summary via Groq.

    Returns:
        Summary text string with four ## sections.
    """
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

    summary = summarize_match(context)
    return summary


def step_save(match_id: int, summary: str, incidents: dict):
    """Persist AI summary and match events to DB."""
    save_summary(match_id, summary)

    if incidents:
        saved_events = save_match_events(match_id, incidents)
        print(f"      Saved {saved_events} event(s) to DB.")


# -------------------------------------------------------------------------
# Main entry point
# -------------------------------------------------------------------------

def run_pipeline(
    competition_code: str = TARGET_COMPETITION_CODE,
    competition_id: int = TARGET_COMPETITION_ID,
    competition_name: str = TARGET_COMPETITION_NAME,
    target_matchday: int | None = None,
) -> list:
    """
    Runs the full ETL + summarization pipeline.

    In auto mode (target_matchday=None), processes all unanalysed matches
    from the most complete finished matchday — used by the frontend button.

    In backfill mode (target_matchday=N), processes a specific matchday —
    used from the CLI for catching up on historical data.

    Args:
        competition_code:  e.g. "PL"
        competition_id:    e.g. 2021
        competition_name:  e.g. "Premier League"
        target_matchday:   Specific matchday to process, or None for auto.

    Returns:
        List of result dicts — one per match attempted.
        Each has: match_id, home_team, away_team, status ("ok"/"error").
    """
    start = datetime.now()
    mode = f"BACKFILL MD{target_matchday}" if target_matchday else "AUTO"
    print("=" * 55)
    print(f"  FOOTBALL ANALYTICS PIPELINE — V2 [{mode}]")
    print(f"  Started: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55 + "\n")

    step_init()

    raw_matches = step_fetch_and_store(competition_code, competition_id)
    if not raw_matches:
        print("No matches returned from API. Exiting.")
        return []

    unanalysed = step_get_unanalysed_matches(raw_matches, target_matchday)
    if not unanalysed:
        md_label = f"MD{target_matchday}" if target_matchday else "the most complete matchday"
        print(f"All matches from {md_label} are already analysed.")
        print("Nothing to do.\n")
        return []

    total = len(unanalysed)
    print(f"[4/5] Processing {total} match(es)...\n")

    results = []

    for i, raw_match in enumerate(unanalysed, start=1):
        home = raw_match.get("homeTeam", {}).get("name", "Unknown")
        away = raw_match.get("awayTeam", {}).get("name", "Unknown")
        match_id = raw_match.get("id")

        print(f"  [{i}/{total}] {home} vs {away} (ID: {match_id})")

        try:
            sofascore_data = step_fetch_sofascore_data(raw_match)
            incidents = step_fetch_incidents(sofascore_data, home, away)

            print(f"      Generating AI summary...")
            summary = step_summarize(
                raw_match, competition_name, sofascore_data, incidents
            )

            step_save(match_id, summary, incidents)
            print(f"      ✓ Done.\n")

            results.append({
                "match_id": match_id,
                "home_team": home,
                "away_team": away,
                "status": "ok",
            })

        except Exception as e:
            print(f"      ✗ Failed: {e}\n")
            results.append({
                "match_id": match_id,
                "home_team": home,
                "away_team": away,
                "status": "error",
                "error": str(e),
            })

        # Respect Groq rate limits between calls.
        # Skip delay after the last match — no next call to protect.
        if i < total:
            print(f"      Waiting {GROQ_DELAY_SECONDS}s before next match...")
            time.sleep(GROQ_DELAY_SECONDS)

    elapsed = (datetime.now() - start).seconds
    ok_count   = sum(1 for r in results if r["status"] == "ok")
    fail_count = len(results) - ok_count

    print("=" * 55)
    print(f"  PIPELINE COMPLETE [{mode}]")
    print(f"  Analysed: {ok_count} match(es)")
    if fail_count:
        print(f"  Failed:   {fail_count} match(es)")
    print(f"  Time elapsed: {elapsed}s")
    print("=" * 55 + "\n")

    return results


# -------------------------------------------------------------------------
# CLI entry point
# -------------------------------------------------------------------------

if __name__ == "__main__":
    """
    CLI usage:
        python -m backend.main                  # auto mode
        python -m backend.main --matchday 28    # backfill MD28

    argparse is Python's standard library for parsing command-line
    arguments. add_argument() defines what flags are accepted.
    parse_args() reads sys.argv (the actual command you typed) and
    returns a Namespace object where args.matchday is the value.

    type=int tells argparse to convert the string "28" to the integer 28
    automatically — otherwise everything from the terminal is a string.
    """
    parser = argparse.ArgumentParser(
        description="Football Analytics Pipeline"
    )
    parser.add_argument(
        "--matchday",
        type=int,
        default=None,
        help="Specific matchday to process (e.g. --matchday 28). "
             "Omit for auto-detection of most complete matchday."
    )
    args = parser.parse_args()

    run_pipeline(target_matchday=args.matchday)
