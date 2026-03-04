"""
backend/scrapers/sofascore.py

Fetches match statistics and lineups from SofaScore via RapidAPI.
Uses three confirmed working endpoints:
    - match/list        — find matches by date, get SofaScore match IDs
    - match/statistics  — match-level stats (xG, possession, shots, etc.)
    - match/lineups     — confirmed lineups with formations and players

SofaScore match IDs are different from Football-Data.org IDs.
We bridge them by matching team names and date.

Rate limit: depends on RapidAPI plan — add delay between requests.
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------

RAPIDAPI_KEY = os.getenv("RAPID_API_KEY")
HOST = "sofascore6.p.rapidapi.com"
BASE_URL = f"https://{HOST}/api/sofascore/v1"

HEADERS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": HOST
}

REQUEST_DELAY = 1  # seconds between requests


# -------------------------------------------------------------------------
# Core request handler
# -------------------------------------------------------------------------

def _get(endpoint: str, params: dict = None) -> any:
    """
    Internal GET request handler with error handling.
    All public functions call this instead of requests.get() directly.

    Args:
        endpoint: API path e.g. "/match/statistics"
        params: Query parameters dict

    Returns:
        Parsed JSON response (dict or list depending on endpoint)

    Raises:
        Exception with descriptive message on failure
    """
    url = f"{BASE_URL}{endpoint}"

    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=15)

        if response.status_code == 429:
            print("Rate limit hit. Waiting 60 seconds...")
            time.sleep(60)
            response = requests.get(url, headers=HEADERS, params=params, timeout=15)

        response.raise_for_status()
        return response.json()

    except requests.exceptions.Timeout:
        raise Exception(f"Request timed out: {url}")
    except requests.exceptions.HTTPError as e:
        raise Exception(f"HTTP {response.status_code} error: {e} — {url}")
    except requests.exceptions.ConnectionError:
        raise Exception(f"Connection error: {url}")


# -------------------------------------------------------------------------
# Public functions
# -------------------------------------------------------------------------

def get_matches_by_date(date_str: str) -> list:
    """
    Fetches all football matches for a given date from SofaScore.

    Args:
        date_str: Date in YYYY-MM-DD format e.g. "2026-03-03"

    Returns:
        List of match dicts. Each dict contains:
            - id: SofaScore match ID
            - slug: URL-friendly match name
            - homeTeam/awayTeam: team info dicts
            - tournament: competition info
            - status: match status (finished, inprogress, etc.)
            - startTimestamp: Unix timestamp of kickoff
    """
    data = _get("/match/list", params={"sport_slug": "football", "date": date_str})
    time.sleep(REQUEST_DELAY)

    # Response is a list of match dicts directly
    if isinstance(data, list):
        return data
    # Some responses wrap in a dict
    return data.get("events", []) if isinstance(data, dict) else []


def get_match_statistics(sofascore_match_id: int) -> dict:
    """
    Fetches detailed match statistics for a single match.
    Returns stats grouped by category (overview, shots, passes, etc.)

    Args:
        sofascore_match_id: SofaScore numeric match ID

    Returns:
        Dict with keys:
            - overview: ball possession, xG, shots, fouls, cards, passes, tackles
            - shots: total, on target, off target, blocked, inside/outside box
            - passes: accurate, long balls, crosses, final third entries
            - duels: ground, aerial, dribbles
            - defending: tackles won, interceptions, recoveries, clearances
            - goalkeeping: saves, goals prevented

        Returns empty dict if stats unavailable.
    """
    data = _get("/match/statistics", params={"match_id": str(sofascore_match_id)})
    time.sleep(REQUEST_DELAY)

    if not isinstance(data, list):
        return {}

    # Find the ALL period (full match stats, not just first/second half)
    all_period = next((d for d in data if d.get("period") == "ALL"), None)
    if not all_period:
        return {}

    # Flatten nested groups into a clean dict
    # Structure: {stat_key: {"home": value, "away": value}}
    result = {}
    for group in all_period.get("groups", []):
        for stat in group.get("statisticsItems", []):
            key = stat.get("key", "")
            if key:
                result[key] = {
                    "home": stat.get("homeValue"),
                    "away": stat.get("awayValue"),
                    "home_display": stat.get("home"),
                    "away_display": stat.get("away"),
                    "name": stat.get("name"),
                }

    return result


def get_match_lineups(sofascore_match_id: int) -> dict:
    """
    Fetches confirmed lineups for a match including formations.

    Args:
        sofascore_match_id: SofaScore numeric match ID

    Returns:
        Dict with keys:
            - confirmed: bool — whether lineups are official
            - home_formation: str e.g. "3-5-1-1"
            - away_formation: str e.g. "4-2-3-1"
            - home_players: list of player dicts
            - away_players: list of player dicts

        Each player dict contains:
            - id, name, short_name, position, jersey_number
    """
    data = _get("/match/lineups", params={"match_id": str(sofascore_match_id)})
    time.sleep(REQUEST_DELAY)

    if not isinstance(data, dict):
        return {}

    def _extract_players(side_data: dict) -> list:
        """Extracts and normalizes player list from a lineup side."""
        players = []
        for p in side_data.get("players", []):
            players.append({
                "id": p.get("id"),
                "name": p.get("name"),
                "short_name": p.get("shortName"),
                "position": p.get("position"),
                "jersey_number": p.get("jerseyNumber"),
            })
        return players

    return {
        "confirmed": data.get("confirmed", False),
        "home_formation": data.get("home", {}).get("formation", "Unknown"),
        "away_formation": data.get("away", {}).get("formation", "Unknown"),
        "home_players": _extract_players(data.get("home", {})),
        "away_players": _extract_players(data.get("away", {})),
    }


def find_sofascore_match_id(matches: list, home_team: str,
                             away_team: str) -> int | None:
    """
    Finds a SofaScore match ID by matching team names from a match list.
    Bridges Football-Data.org team names with SofaScore team names.

    Name matching is fuzzy — removes common suffixes like "FC", "United",
    etc. and does partial matching because the two APIs use different
    naming conventions.
    e.g. "Wolverhampton Wanderers FC" vs "Wolverhampton"

    Args:
        matches: Output of get_matches_by_date()
        home_team: Home team name from Football-Data.org
        away_team: Away team name from Football-Data.org

    Returns:
        SofaScore match ID integer, or None if not found.
    """
    def _normalize(name: str) -> str:
        """Strips common suffixes and lowercases for comparison."""
        name = name.lower()
        for suffix in [" fc", " united", " city", " wanderers",
                       " rovers", " athletic", " albion", " hotspur"]:
            name = name.replace(suffix, "")
        return name.strip()

    home_norm = _normalize(home_team)
    away_norm = _normalize(away_team)

    for match in matches:
        ss_home = _normalize(match.get("homeTeam", {}).get("name", ""))
        ss_away = _normalize(match.get("awayTeam", {}).get("name", ""))

        # Check if normalized names match in either direction
        if (home_norm in ss_home or ss_home in home_norm) and \
           (away_norm in ss_away or ss_away in away_norm):
            return match.get("id")

    return None


def get_full_match_data(date_str: str, home_team: str,
                        away_team: str) -> dict | None:
    """
    Convenience function that chains all three API calls:
    1. Get match list for the date
    2. Find the specific match ID
    3. Fetch statistics and lineups

    Args:
        date_str: Match date "YYYY-MM-DD"
        home_team: Home team name (Football-Data.org format)
        away_team: Away team name (Football-Data.org format)

    Returns:
        Dict with keys: match_id, statistics, lineups
        Returns None if match not found.
    """
    print(f"Fetching match data: {home_team} vs {away_team} on {date_str}")

    matches = get_matches_by_date(date_str)
    match_id = find_sofascore_match_id(matches, home_team, away_team)

    if not match_id:
        print(f"Match not found in SofaScore for {home_team} vs {away_team}")
        return None

    print(f"Found SofaScore match ID: {match_id}")

    stats = get_match_statistics(match_id)
    lineups = get_match_lineups(match_id)

    return {
        "match_id": match_id,
        "statistics": stats,
        "lineups": lineups,
    }


# -------------------------------------------------------------------------
# Quick test
# -------------------------------------------------------------------------

if __name__ == "__main__":
    print("Testing SofaScore scraper...\n")

    result = get_full_match_data(
        date_str="2026-03-03",
        home_team="Wolverhampton Wanderers FC",
        away_team="Liverpool FC"
    )

    if result:
        print(f"\nMatch ID: {result['match_id']}")

        print("\n--- Key Statistics ---")
        stats = result["statistics"]
        key_stats = ["ballPossession", "expectedGoals", "totalShots",
                     "passes", "tackles", "yellowCards"]
        for key in key_stats:
            if key in stats:
                s = stats[key]
                print(f"  {s['name']}: Home={s['home_display']} Away={s['away_display']}")

        print("\n--- Lineups ---")
        lineups = result["lineups"]
        print(f"  Confirmed: {lineups.get('confirmed')}")
        print(f"  Home formation: {lineups.get('home_formation')}")
        print(f"  Away formation: {lineups.get('away_formation')}")
        print(f"  Home players: {len(lineups.get('home_players', []))}")
        print(f"  Away players: {len(lineups.get('away_players', []))}")