"""
backend/main.py

Orchestrates the full V1 pipeline:
    1. Fetch competitions and matches from Football-Data.org API
    2. Clean and normalize the raw response
    3. Save competitions, teams, and matches to SQLite
    4. Generate AI summary for the most recent finished match
    5. Save the summary to the DB and print it

This is the entry point for the entire backend pipeline.
Run it with: python -m backend.main

This is also what n8n will call via a scheduled Execute Command node.
"""

import sys
from datetime import datetime

from backend.db.schema import init_db
from backend.db.writer import (
    save_competitions,
    save_teams,
    save_matches,
    save_summary,
    get_match_ids_in_db,
)
from backend.scrapers.football_data_api import (
    get_competitions,
    get_matches_by_competition,
    get_team_by_id,
)
from backend.processors.cleaner import (
    clean_competitions,
    clean_teams_from_matches,
    clean_matches,
)
from backend.summarizer.summarize import summarize_match


# -------------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------------
# Which competition to track in V1.
# PL = Premier League. Change this to any supported code to track others.
# Full list: PL, CL, BL1, SA, PD, FL1
TARGET_COMPETITION_CODE = "PL"
TARGET_COMPETITION_ID = 2021  # Football-Data.org's ID for Premier League


# -------------------------------------------------------------------------
# Pipeline steps
# -------------------------------------------------------------------------

def step_init():
    """
    Step 0: Ensure the database exists with all tables.
    Safe to run every time — won't overwrite existing data.
    """
    print("[1/5] Initializing database...")
    init_db()
    print("      Done.\n")


def step_fetch_and_store(competition_code: str, competition_id: int) -> list:
    """
    Step 1: Fetch matches from the API, clean them, and save to DB.
    Skips matches already in the DB to avoid redundant API calls.

    Args:
        competition_code: e.g. "PL"
        competition_id: e.g. 2021

    Returns:
        List of all raw match dicts fetched from the API.
    """
    print(f"[2/5] Fetching matches for competition: {competition_code}...")

    # Fetch raw matches from API
    raw_matches = get_matches_by_competition(competition_code)
    print(f"      Found {len(raw_matches)} matches from API.")

    # Clean and save competitions
    raw_competitions = get_competitions()
    clean_comps = clean_competitions(raw_competitions)
    saved_comps = save_competitions(clean_comps)
    print(f"      Saved {saved_comps} competition(s).")

    # Extract and save unique teams from match data
    clean_team_list = clean_teams_from_matches(raw_matches)
    saved_teams = save_teams(clean_team_list)
    print(f"      Saved {saved_teams} team(s).")

    # Only save matches we don't already have
    existing_ids = set(get_match_ids_in_db())
    new_raw_matches = [m for m in raw_matches if m.get("id") not in existing_ids]
    print(f"      {len(new_raw_matches)} new match(es) to save (skipping {len(existing_ids)} already in DB).")

    if new_raw_matches:
        clean_match_list = clean_matches(new_raw_matches, competition_id)
        saved_matches = save_matches(clean_match_list)
        print(f"      Saved {saved_matches} new match(es).\n")
    else:
        print("      No new matches to save.\n")

    return raw_matches


def step_get_latest_finished_match(raw_matches: list) -> dict | None:
    """
    Step 2: Find the most recently finished match from the raw match list.
    We sort by utcDate descending and return the first FINISHED match.

    Args:
        raw_matches: List of raw match dicts from the API

    Returns:
        Single raw match dict, or None if no finished matches found.
    """
    print("[3/5] Finding most recent finished match...")

    finished = [m for m in raw_matches if m.get("status") == "FINISHED"]

    if not finished:
        print("      No finished matches found.\n")
        return None

    # Sort by date descending — most recent first
    finished.sort(key=lambda m: m.get("utcDate", ""), reverse=True)
    latest = finished[0]

    home = latest.get("homeTeam", {}).get("name", "Unknown")
    away = latest.get("awayTeam", {}).get("name", "Unknown")
    score_home = latest.get("score", {}).get("fullTime", {}).get("home", "?")
    score_away = latest.get("score", {}).get("fullTime", {}).get("away", "?")
    print(f"      Latest match: {home} {score_home} - {score_away} {away}\n")

    return latest


def step_summarize(raw_match: dict, competition_name: str) -> str:
    """
    Step 3: Build match_data dict and call the summarizer.
    
    Note: In V1 we don't have per-player stats from the API's free tier
    (that requires the premium tier or Understat scraping which comes later).
    We pass an empty player_stats list for now — the summarizer handles this
    gracefully and Claude will base the summary on match-level data only.
    This is an honest limitation we will fix in a later step.

    Args:
        raw_match: Single raw match dict
        competition_name: e.g. "Premier League"

    Returns:
        Summary text string.
    """
    print("[4/5] Generating AI summary...")

    match_data = {
        "home_team": raw_match.get("homeTeam", {}).get("name", "Unknown"),
        "away_team": raw_match.get("awayTeam", {}).get("name", "Unknown"),
        "home_score": raw_match.get("score", {}).get("fullTime", {}).get("home"),
        "away_score": raw_match.get("score", {}).get("fullTime", {}).get("away"),
        "competition": competition_name,
        "matchday": raw_match.get("matchday"),
        "date": raw_match.get("utcDate", "")[:10],  # Trim to YYYY-MM-DD
    }

    # V1 limitation: no player-level stats yet
    # These will come from Understat scraper in the next development phase
    player_stats = []

    summary = summarize_match(match_data, player_stats)
    print("      Summary generated.\n")

    return summary


def step_save_summary(match_id: int, summary: str):
    """
    Step 4: Persist the generated summary to the DB.

    Args:
        match_id: DB match ID to link the summary to
        summary: The full summary text
    """
    print("[5/5] Saving summary to database...")
    save_summary(match_id, summary)
    print("      Done.\n")


# -------------------------------------------------------------------------
# Main entry point
# -------------------------------------------------------------------------

def run_pipeline(competition_code: str = TARGET_COMPETITION_CODE,
                 competition_id: int = TARGET_COMPETITION_ID):
    """
    Runs the full ETL + summarization pipeline.
    Called directly or triggered by n8n.
    """
    start = datetime.now()
    print("=" * 55)
    print("  FOOTBALL ANALYTICS PIPELINE — V1")
    print(f"  Started: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55 + "\n")

    # Step 0: Init DB
    step_init()

    # Step 1: Fetch, clean, store
    raw_matches = step_fetch_and_store(competition_code, competition_id)

    if not raw_matches:
        print("No matches returned from API. Exiting.")
        sys.exit(0)

    # Step 2: Find latest finished match
    latest_match = step_get_latest_finished_match(raw_matches)

    if not latest_match:
        print("No finished matches available for summarization. Exiting.")
        sys.exit(0)

    # Step 3: Summarize
    summary = step_summarize(latest_match, "Premier League")

    # Step 4: Save summary
    step_save_summary(latest_match["id"], summary)

    # Print final output
    elapsed = (datetime.now() - start).seconds
    print("=" * 55)
    print("  PIPELINE COMPLETE")
    print(f"  Time elapsed: {elapsed}s")
    print("=" * 55 + "\n")
    print("MATCH SUMMARY:")
    print("-" * 55)
    print(summary)


if __name__ == "__main__":
    run_pipeline()