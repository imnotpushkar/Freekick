"""
backend/processors/cleaner.py

Transforms raw API responses from Football-Data.org into clean, flat
Python dicts that map directly to SQLAlchemy models in backend/db/schema.py.

No database interaction here — functions take raw dicts, return clean dicts.
The pipeline is: scraper → cleaner → db writer (next step).
"""

from datetime import datetime
from typing import Optional


# -------------------------------------------------------------------------
# Utility helpers
# -------------------------------------------------------------------------

def _safe_get(d: dict, *keys, default=None):
    """
    Safely traverses a nested dict using a chain of keys.
    Returns default if any key is missing or value is None.

    Example:
        _safe_get(match, "score", "fullTime", "home", default=0)
        # equivalent to match["score"]["fullTime"]["home"]
        # but won't crash if any level is missing
    """
    for key in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(key)
        if d is None:
            return default
    return d


def _parse_utc_date(date_str: Optional[str]) -> Optional[datetime]:
    """
    Converts Football-Data.org's UTC date string into a Python datetime.
    Their format is: "2024-01-15T20:00:00Z"

    Returns None if the string is missing or unparseable — we never
    want a date parsing failure to crash the entire pipeline.
    """
    if not date_str:
        return None
    try:
        # Strip the trailing "Z" (which means UTC) and parse
        return datetime.strptime(date_str.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


# -------------------------------------------------------------------------
# Competition cleaner
# -------------------------------------------------------------------------

def clean_competition(raw: dict) -> dict:
    """
    Extracts relevant fields from a raw competition dict.

    Args:
        raw: Single competition dict from get_competitions()

    Returns:
        Clean dict matching the Competition model fields.

    Example input:
        {"id": 2021, "name": "Premier League", "code": "PL",
         "area": {"name": "England"}}

    Example output:
        {"id": 2021, "name": "Premier League", "code": "PL",
         "country": "England"}
    """
    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "code": raw.get("code"),
        "country": _safe_get(raw, "area", "name", default="Unknown"),
    }


# -------------------------------------------------------------------------
# Team cleaner
# -------------------------------------------------------------------------

def clean_team(raw: dict) -> dict:
    """
    Extracts relevant fields from a raw team dict.

    Args:
        raw: Team dict — either from a match's homeTeam/awayTeam
             or from get_team_by_id()

    Returns:
        Clean dict matching the Team model fields.
    """
    return {
        "id": raw.get("id"),
        "name": raw.get("name", "Unknown"),
        "short_name": raw.get("shortName") or raw.get("name", "Unknown"),
        "tla": raw.get("tla", "???"),
    }


# -------------------------------------------------------------------------
# Match cleaner
# -------------------------------------------------------------------------

def clean_match(raw: dict, competition_id: int) -> dict:
    """
    Flattens a raw match dict into a clean structure.
    The nested score object gets flattened into home_score/away_score.

    Args:
        raw: Single match dict from get_matches_by_competition()
        competition_id: The DB competition ID to link this match to

    Returns:
        Clean dict matching the Match model fields.

    Note on scores: if a match is SCHEDULED (not played yet),
    score fields will be None — we store them as None, not 0.
    Storing 0 would imply a 0-0 result which is factually wrong.
    """
    status = raw.get("status", "UNKNOWN")

    # Only extract scores if the match is finished
    if status == "FINISHED":
        home_score = _safe_get(raw, "score", "fullTime", "home", default=None)
        away_score = _safe_get(raw, "score", "fullTime", "away", default=None)
    else:
        home_score = None
        away_score = None

    return {
        "id": raw.get("id"),
        "competition_id": competition_id,
        "home_team_id": _safe_get(raw, "homeTeam", "id"),
        "away_team_id": _safe_get(raw, "awayTeam", "id"),
        "matchday": raw.get("matchday"),
        "status": status,
        "utc_date": _parse_utc_date(raw.get("utcDate")),
        "home_score": home_score,
        "away_score": away_score,
    }


# -------------------------------------------------------------------------
# Player cleaner
# -------------------------------------------------------------------------

def clean_player(raw: dict, team_id: int) -> dict:
    """
    Extracts player fields from a squad member dict.
    Squad data comes from get_team_by_id() which returns a
    'squad' list inside the team response.

    Args:
        raw: Single player dict from team['squad']
        team_id: The DB team ID to link this player to

    Returns:
        Clean dict matching the Player model fields.
    """
    return {
        "id": raw.get("id"),
        "name": raw.get("name", "Unknown"),
        "position": raw.get("position", "Unknown"),
        "nationality": raw.get("nationality", "Unknown"),
        "team_id": team_id,
    }


# -------------------------------------------------------------------------
# Batch cleaners — process lists at once
# -------------------------------------------------------------------------

def clean_competitions(raw_list: list) -> list:
    """Cleans a list of raw competition dicts."""
    return [clean_competition(c) for c in raw_list if c.get("id")]


def clean_teams_from_matches(raw_matches: list) -> list:
    """
    Extracts and deduplicates both home and away teams from a match list.
    Avoids storing the same team twice if they appear in multiple matches.

    Returns:
        List of unique clean team dicts.
    """
    seen_ids = set()
    teams = []

    for match in raw_matches:
        for key in ["homeTeam", "awayTeam"]:
            raw_team = match.get(key, {})
            team_id = raw_team.get("id")
            if team_id and team_id not in seen_ids:
                seen_ids.add(team_id)
                teams.append(clean_team(raw_team))

    return teams


def clean_matches(raw_matches: list, competition_id: int) -> list:
    """Cleans a list of raw match dicts for a given competition."""
    return [clean_match(m, competition_id) for m in raw_matches if m.get("id")]


# -------------------------------------------------------------------------
# Quick test
# -------------------------------------------------------------------------

if __name__ == "__main__":
    # Simulate what a raw API response looks like and verify cleaning
    sample_match = {
        "id": 419884,
        "utcDate": "2024-01-15T20:00:00Z",
        "status": "FINISHED",
        "matchday": 21,
        "homeTeam": {"id": 57, "name": "Arsenal FC", "shortName": "Arsenal", "tla": "ARS"},
        "awayTeam": {"id": 65, "name": "Manchester City FC", "shortName": "Man City", "tla": "MCI"},
        "score": {
            "fullTime": {"home": 1, "away": 0}
        }
    }

    cleaned = clean_match(sample_match, competition_id=2021)
    print("Cleaned match:")
    for key, value in cleaned.items():
        print(f"  {key}: {value}")

    teams = clean_teams_from_matches([sample_match])
    print("\nCleaned teams:")
    for t in teams:
        print(f"  {t}")