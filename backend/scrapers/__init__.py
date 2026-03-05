"""
backend/scrapers/sofascore.py

Fetches match data from two SofaScore RapidAPI hosts:

    Host 1 — sofascore6.p.rapidapi.com (original)
        Endpoints: match/list, match/statistics, match/lineups
        Used for: date-based match lookup, stats, lineups

    Host 2 — sofascore.p.rapidapi.com (API Dojo)
        Endpoint: /matches/get-incidents
        Used for: goals, cards, substitutions with timestamps
        Confirmed working: returns {'incidents', 'home', 'away'}
        Confirmed NOT working on sofascore6: match/incidents → 404

    Both hosts use the same RAPID_API_KEY from .env.
    RapidAPI keys are platform-wide — they work on any subscribed API
    regardless of host. The host string is just a routing identifier.

Key findings from raw API inspection:
    - substitute: False = starter, substitute: True = bench player
    - positionsDetailed: [] — empty on free tier, no coordinate data
    - Players ordered: starters first (indices 0-10), bench after (11+)
    - position tag = natural position, NOT match role
    - Incidents list returned in reverse chronological order — sort needed
    - incidentType values: "goal", "card", "substitution", "period",
      "injuryTime" — we only parse the first three

Rate limit: depends on RapidAPI plan — REQUEST_DELAY between calls.
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

RAPIDAPI_KEY = os.getenv("RAPID_API_KEY")

# ── Host 1: stats + lineups ───────────────────────────────────────────────
HOST_STATS = "sofascore6.p.rapidapi.com"
BASE_URL_STATS = f"https://{HOST_STATS}/api/sofascore/v1"
HEADERS_STATS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": HOST_STATS,
}

# ── Host 2: incidents (API Dojo) ──────────────────────────────────────────
HOST_INCIDENTS = "sofascore.p.rapidapi.com"
BASE_URL_INCIDENTS = f"https://{HOST_INCIDENTS}"
HEADERS_INCIDENTS = {
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": HOST_INCIDENTS,
}

REQUEST_DELAY = 1


# -------------------------------------------------------------------------
# Core request handlers — one per host
# -------------------------------------------------------------------------

def _get_stats(endpoint: str, params: dict = None) -> any:
    """
    GET request to sofascore6 host (stats + lineups).

    Args:
        endpoint: API path e.g. "/match/statistics"
        params: Query parameters dict

    Returns:
        Parsed JSON response (dict or list)

    Raises:
        Exception with descriptive message on failure
    """
    url = f"{BASE_URL_STATS}{endpoint}"
    try:
        response = requests.get(
            url, headers=HEADERS_STATS, params=params, timeout=15
        )
        if response.status_code == 429:
            print("Rate limit hit (stats host). Waiting 60 seconds...")
            time.sleep(60)
            response = requests.get(
                url, headers=HEADERS_STATS, params=params, timeout=15
            )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        raise Exception(f"Request timed out: {url}")
    except requests.exceptions.HTTPError as e:
        raise Exception(f"HTTP {response.status_code} error: {e} — {url}")
    except requests.exceptions.ConnectionError:
        raise Exception(f"Connection error: {url}")


def _get_incidents(path: str, params: dict = None) -> any:
    """
    GET request to API Dojo SofaScore host (incidents).

    Args:
        path: API path e.g. "/matches/get-incidents"
        params: Query parameters dict

    Returns:
        Parsed JSON response (dict or list)

    Raises:
        Exception with descriptive message on failure
    """
    url = f"{BASE_URL_INCIDENTS}{path}"
    try:
        response = requests.get(
            url, headers=HEADERS_INCIDENTS, params=params, timeout=15
        )
        if response.status_code == 429:
            print("Rate limit hit (incidents host). Waiting 60 seconds...")
            time.sleep(60)
            response = requests.get(
                url, headers=HEADERS_INCIDENTS, params=params, timeout=15
            )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        raise Exception(f"Request timed out: {url}")
    except requests.exceptions.HTTPError as e:
        raise Exception(f"HTTP {response.status_code} error: {e} — {url}")
    except requests.exceptions.ConnectionError:
        raise Exception(f"Connection error: {url}")


# -------------------------------------------------------------------------
# Public functions — stats + lineups (sofascore6 host)
# -------------------------------------------------------------------------

def get_matches_by_date(date_str: str) -> list:
    """
    Fetches all football matches for a given date from SofaScore.

    Args:
        date_str: Date in YYYY-MM-DD format e.g. "2026-03-03"

    Returns:
        List of match dicts. Each dict contains:
            - id: SofaScore match ID
            - homeTeam/awayTeam: team info dicts
            - tournament: competition info
            - status: match status (finished, inprogress, etc.)
    """
    data = _get_stats(
        "/match/list", params={"sport_slug": "football", "date": date_str}
    )
    time.sleep(REQUEST_DELAY)

    if isinstance(data, list):
        return data
    return data.get("events", []) if isinstance(data, dict) else []


def get_match_statistics(sofascore_match_id: int) -> dict:
    """
    Fetches detailed match statistics for a single match.

    Args:
        sofascore_match_id: SofaScore numeric match ID

    Returns:
        Flattened dict of {stat_key: {home, away, home_display, away_display}}
        Returns empty dict if stats unavailable.
    """
    data = _get_stats(
        "/match/statistics", params={"match_id": str(sofascore_match_id)}
    )
    time.sleep(REQUEST_DELAY)

    if not isinstance(data, list):
        return {}

    all_period = next((d for d in data if d.get("period") == "ALL"), None)
    if not all_period:
        return {}

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

    Key behaviour:
        - Returns ALL players (starters + substitutes)
        - substitute: False = starter (indices 0-10 in returned list)
        - substitute: True  = bench player (indices 11+ in returned list)
        - positionsDetailed is empty on free tier — no coordinate data
        - position tag reflects natural position, not match role

    Args:
        sofascore_match_id: SofaScore numeric match ID

    Returns:
        Dict with keys:
            - confirmed: bool
            - home_formation, away_formation: str
            - home_players, away_players: list of player dicts
              Each player has: id, name, short_name, position,
              jersey_number, substitute (bool)
    """
    data = _get_stats(
        "/match/lineups", params={"match_id": str(sofascore_match_id)}
    )
    time.sleep(REQUEST_DELAY)

    if not isinstance(data, dict):
        return {}

    def _extract_players(side_data: dict) -> list:
        players = []
        for p in side_data.get("players", []):
            players.append({
                "id": p.get("id"),
                "name": p.get("name"),
                "short_name": p.get("shortName"),
                "position": p.get("position"),
                "jersey_number": p.get("jerseyNumber"),
                "substitute": p.get("substitute", True),
            })
        return players

    return {
        "confirmed": data.get("confirmed", False),
        "home_formation": data.get("home", {}).get("formation", "Unknown"),
        "away_formation": data.get("away", {}).get("formation", "Unknown"),
        "home_players": _extract_players(data.get("home", {})),
        "away_players": _extract_players(data.get("away", {})),
    }


# -------------------------------------------------------------------------
# Public functions — incidents (API Dojo host)
# -------------------------------------------------------------------------

def get_match_incidents(sofascore_match_id: int) -> dict:
    """
    Fetches match incidents — goals, cards, substitutions with timestamps.
    Uses the API Dojo SofaScore host (sofascore.p.rapidapi.com).

    The raw response comes in reverse chronological order (latest first).
    This function returns raw data — cleaner.py handles parsing and sorting.

    Args:
        sofascore_match_id: SofaScore numeric match ID

    Returns:
        Raw dict with keys:
            - incidents: list of all incident dicts (unsorted)
            - home: home team info dict
            - away: away team info dict
        Returns empty dict on failure.

    Incident structure by type:
        goal:
            player.name, assist1.name (optional), time, isHome,
            incidentClass ("regular", "penalty", "own-goal")
        card:
            player.name, time, isHome,
            incidentClass ("yellow", "yellow-red", "red"), reason
        substitution:
            playerIn.name, playerOut.name, time, isHome, injury (bool)
        period / injuryTime:
            ignored by cleaner — structural markers only
    """
    data = _get_incidents(
        "/matches/get-incidents", params={"matchId": str(sofascore_match_id)}
    )
    time.sleep(REQUEST_DELAY)

    if not isinstance(data, dict):
        return {}

    return data


# -------------------------------------------------------------------------
# Bridge — match ID lookup
# -------------------------------------------------------------------------

def find_sofascore_match_id(matches: list, home_team: str,
                             away_team: str) -> int | None:
    """
    Finds a SofaScore match ID by fuzzy-matching team names.
    Bridges Football-Data.org team names with SofaScore names.

    Args:
        matches: Output of get_matches_by_date()
        home_team: Home team name from Football-Data.org
        away_team: Away team name from Football-Data.org

    Returns:
        SofaScore match ID integer, or None if not found.
    """
    def _normalize(name: str) -> str:
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

        if (home_norm in ss_home or ss_home in home_norm) and \
           (away_norm in ss_away or ss_away in away_norm):
            return match.get("id")

    return None


# -------------------------------------------------------------------------
# Convenience wrapper — full match data
# -------------------------------------------------------------------------

def get_full_match_data(date_str: str, home_team: str,
                        away_team: str) -> dict | None:
    """
    Chains all API calls into one convenience function.
    Fetches statistics, lineups, and incidents for a match.

    Args:
        date_str: Match date "YYYY-MM-DD"
        home_team: Home team name (Football-Data.org format)
        away_team: Away team name (Football-Data.org format)

    Returns:
        Dict with keys: match_id, statistics, lineups, incidents
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
    incidents = get_match_incidents(match_id)

    return {
        "match_id": match_id,
        "statistics": stats,
        "lineups": lineups,
        "incidents": incidents,
    }


# -------------------------------------------------------------------------
# Quick test — verify incidents parse correctly
# -------------------------------------------------------------------------

if __name__ == "__main__":
    print("Testing incidents fetch for Wolves vs Liverpool (ID: 14023985)\n")
    try:
        data = get_match_incidents(14023985)
        incidents = data.get("incidents", [])
        print(f"Total incidents returned: {len(incidents)}\n")

        for inc in sorted(incidents, key=lambda x: x.get("time", 0)):
            inc_type = inc.get("incidentType")
            if inc_type == "goal":
                player = inc.get("player", {}).get("name", "?")
                assist = inc.get("assist1", {}).get("name")
                side = "HOME" if inc.get("isHome") else "AWAY"
                cls = inc.get("incidentClass", "regular")
                assist_str = f" (assist: {assist})" if assist else ""
                print(f"  {inc.get('time')}' GOAL [{cls}] {player}{assist_str} ({side})")
            elif inc_type == "card":
                player = inc.get("player", {}).get("name", "?")
                side = "HOME" if inc.get("isHome") else "AWAY"
                cls = inc.get("incidentClass", "yellow").upper()
                print(f"  {inc.get('time')}' {cls} CARD — {player} ({side})")
    except Exception as e:
        print(f"Failed: {e}")
