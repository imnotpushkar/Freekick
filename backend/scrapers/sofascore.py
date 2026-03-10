"""
backend/scrapers/sofascore.py

Fetches match statistics and lineups from SofaScore via RapidAPI.
Uses three confirmed working endpoints:
    - match/list        — find matches by date, get SofaScore match IDs
    - match/statistics  — match-level stats (xG, possession, shots, etc.)
    - match/lineups     — confirmed lineups with formations and players

Key findings from raw API inspection:
    - substitute: False = starter, substitute: True = bench player
    - positionsDetailed: [] — empty on free tier, no coordinate data
    - Players ordered: starters first (indices 0-10), bench after (11+)
    - position tag = natural position, NOT match role (e.g. Wolfe tagged
      as D but played Left Wingback — role comes from formation_roles.py)

Rate limit: depends on RapidAPI plan — REQUEST_DELAY between calls.
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

RAPIDAPI_KEY = os.getenv("RAPID_API_KEY")
HOST = "sofascore6.p.rapidapi.com"
BASE_URL = f"https://{HOST}/api/sofascore/v1"

HEADERS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": HOST
}

HOST_INCIDENTS = "sofascore.p.rapidapi.com"
BASE_URL_INCIDENTS = f"https://{HOST_INCIDENTS}"
HEADERS_INCIDENTS = {
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": HOST_INCIDENTS,
}

REQUEST_DELAY = 1


# -------------------------------------------------------------------------
# Core request handler
# -------------------------------------------------------------------------

def _get(endpoint: str, params: dict = None) -> any:
    """
    Internal GET request handler with error handling and rate limit retry.

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


def _get_incidents(path: str, params: dict = None) -> any:
    """
    GET request to API Dojo SofaScore host (incidents).
    sofascore.p.rapidapi.com — confirmed working for /matches/get-incidents.
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
    data = _get("/match/list", params={"sport_slug": "football", "date": date_str})
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
    data = _get("/match/statistics", params={"match_id": str(sofascore_match_id)})
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
    data = _get("/match/lineups", params={"match_id": str(sofascore_match_id)})
    time.sleep(REQUEST_DELAY)

    if not isinstance(data, dict):
        return {}

    def _extract_players(side_data: dict) -> list:
        """
        Extracts player list preserving substitute flag.
        substitute: False = starter, substitute: True = bench.
        """
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



def get_match_incidents(sofascore_match_id: int) -> dict:
    """
    Fetches match incidents (goals, cards, substitutions) using the
    API Dojo SofaScore host. Returns raw dict with 'incidents' key.
    Returns empty dict on failure.
    """
    data = _get_incidents(
        "/matches/get-incidents", params={"matchId": str(sofascore_match_id)}
    )
    time.sleep(REQUEST_DELAY)

    if not isinstance(data, dict):
        return {}

    return data


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
        for prefix in ["rc ", "rcd ", "club ", "cf "]:
            if name.startswith(prefix):
                name = name[len(prefix):]
        for token in [" fc", " united", " city", " wanderers", " rovers",
                      " athletic", " albion", " hotspur"]:
            name = name.replace(token, "")
        name = name.replace(" de ", " ")
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



def get_full_match_data(date_str: str, home_team: str,
                        away_team: str) -> dict | None:
    """
    Chains all three API calls into one convenience function.

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

    incidents = get_match_incidents(match_id)

    return {
        "match_id": match_id,
        "statistics": stats,
        "lineups": lineups,
        "incidents": incidents,
    }


# -------------------------------------------------------------------------
# Quick test — run directly to probe the incidents endpoint
# -------------------------------------------------------------------------

if __name__ == "__main__":
    print("Testing incidents endpoint...\n")
    try:
        data = _get("/match/incidents", params={"match_id": "14023985"})
        print(f"Response type: {type(data)}")
        if isinstance(data, list):
            for item in data[:5]:
                print(item)
        elif isinstance(data, dict):
            for key in list(data.keys())[:3]:
                print(f"{key}: {data[key]}")
    except Exception as e:
        print(f"Failed: {e}")
