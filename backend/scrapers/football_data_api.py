"""
backend/scrapers/football_data_api.py

Fetches data from the Football-Data.org REST API (free tier).
All functions return raw Python dicts/lists — no DB interaction here.
The processor module (backend/processors/cleaner.py) handles transformation.

Free tier covers: PL, CL, BL1, SA, PD and more.
Rate limit: 10 requests/minute.

Docs: https://www.football-data.org/documentation/quickstart
"""

import os
import time
import requests
from dotenv import load_dotenv

# -------------------------------------------------------------------------
# Load environment variables from .env file
# -------------------------------------------------------------------------
# load_dotenv() reads the .env file in the project root and loads each
# KEY=VALUE pair into the process environment. After this call,
# os.getenv("FOOTBALL_DATA_API_KEY") returns your actual key.
# Without this call, os.getenv() would return None.

load_dotenv()

# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------

BASE_URL = "https://api.football-data.org/v4"

# The API requires authentication via a custom HTTP header.
# X-Auth-Token is the specific header name Football-Data.org expects.
# Every request we make must include this header.
HEADERS = {
    "X-Auth-Token": os.getenv("FOOTBALL_DATA_API_KEY")
}

# Free tier competition codes we can use
COMPETITIONS = {
    "premier_league": "PL",
    "champions_league": "CL",
    "bundesliga": "BL1",
    "serie_a": "SA",
    "la_liga": "PD",
    "ligue_1": "FL1",
}


# -------------------------------------------------------------------------
# Core request handler
# -------------------------------------------------------------------------

def _get(endpoint: str, params: dict = None) -> dict:
    """
    Internal helper that makes a GET request to the API.
    All public functions in this module call this instead of calling
    requests.get() directly — this centralizes error handling and
    rate limit logic in one place.

    Args:
        endpoint: API path e.g. "/competitions/PL/matches"
        params: Optional query parameters e.g. {"matchday": 5}

    Returns:
        Parsed JSON response as a Python dict.

    Raises:
        Exception with a descriptive message on failure.
    """
    url = f"{BASE_URL}{endpoint}"

    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)

        # 429 = rate limit hit. We wait 60 seconds and retry once.
        # This is called "retry with backoff" — a standard pattern
        # when working with rate-limited APIs.
        if response.status_code == 429:
            print("Rate limit hit. Waiting 60 seconds...")
            time.sleep(60)
            response = requests.get(url, headers=HEADERS, params=params, timeout=10)

        # raise_for_status() throws an exception for any 4xx or 5xx response.
        # 4xx = client error (bad request, unauthorized, not found)
        # 5xx = server error (their problem, not ours)
        response.raise_for_status()

        return response.json()

    except requests.exceptions.Timeout:
        raise Exception(f"Request timed out: {url}")
    except requests.exceptions.ConnectionError:
        raise Exception(f"Connection error — are you online? URL: {url}")
    except requests.exceptions.HTTPError as e:
        raise Exception(f"HTTP error {response.status_code}: {e} — URL: {url}")


# -------------------------------------------------------------------------
# Public API functions
# -------------------------------------------------------------------------

def get_competitions() -> list:
    """
    Returns a list of all competitions available on your API tier.
    Useful for verifying your key works and seeing what's accessible.

    Returns:
        List of competition dicts with keys: id, name, code, area
    """
    data = _get("/competitions")
    return data.get("competitions", [])


def get_matches_by_competition(competition_code: str, matchday: int = None) -> list:
    """
    Fetches all matches for a given competition.
    Optionally filter by matchday number.

    Args:
        competition_code: e.g. "PL" for Premier League
        matchday: Optional integer e.g. 12 for matchday 12

    Returns:
        List of match dicts.

    Example:
        get_matches_by_competition("PL", matchday=5)
    """
    params = {}
    if matchday:
        params["matchday"] = matchday

    data = _get(f"/competitions/{competition_code}/matches", params=params)
    return data.get("matches", [])


def get_match_by_id(match_id: int) -> dict:
    """
    Fetches full details for a single match by its ID.
    Includes score, lineups (if available), referee, and more.

    Args:
        match_id: Football-Data.org numeric match ID

    Returns:
        Single match dict.
    """
    return _get(f"/matches/{match_id}")


def get_team_by_id(team_id: int) -> dict:
    """
    Fetches team details including current squad.
    The squad list is what we use to populate our players table.

    Args:
        team_id: Football-Data.org numeric team ID

    Returns:
        Team dict including 'squad' list of player dicts.
    """
    return _get(f"/teams/{team_id}")


def get_standings(competition_code: str) -> list:
    """
    Fetches current league standings/table for a competition.

    Args:
        competition_code: e.g. "PL"

    Returns:
        List of standing tables (home, away, total).
    """
    data = _get(f"/competitions/{competition_code}/standings")
    return data.get("standings", [])


# -------------------------------------------------------------------------
# Quick test — run this file directly to verify your API key works
# -------------------------------------------------------------------------

if __name__ == "__main__":
    print("Testing Football-Data.org API connection...\n")

    competitions = get_competitions()
    print(f"Found {len(competitions)} competitions on your tier:")
    for c in competitions:
        print(f"  - {c['name']} ({c['code']})")