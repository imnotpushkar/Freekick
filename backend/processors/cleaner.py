"""
backend/processors/cleaner.py

Transforms raw API responses from Football-Data.org and SofaScore
into clean, flat Python dicts that map to SQLAlchemy models and
AI summarizer context objects.

No database interaction here — functions take raw dicts, return clean dicts.
Pipeline: scraper → cleaner → db writer / summarizer
"""

from datetime import datetime
from typing import Optional
from backend.processors.formation_roles import map_tactical_roles


# -------------------------------------------------------------------------
# Utility helpers
# -------------------------------------------------------------------------

def _safe_get(d: dict, *keys, default=None):
    """
    Safely traverses a nested dict using a chain of keys.
    Returns default if any key is missing or value is None.

    Example:
        _safe_get(match, "score", "fullTime", "home", default=0)
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
    Converts Football-Data.org UTC date string to Python datetime.
    Format: "2024-01-15T20:00:00Z"
    Returns None if missing or unparseable.
    """
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


# -------------------------------------------------------------------------
# Football-Data.org cleaners
# -------------------------------------------------------------------------

def clean_competition(raw: dict) -> dict:
    """
    Extracts relevant fields from a raw competition dict.

    Args:
        raw: Single competition dict from get_competitions()

    Returns:
        Clean dict matching the Competition model fields.
    """
    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "code": raw.get("code"),
        "country": _safe_get(raw, "area", "name", default="Unknown"),
    }


def clean_team(raw: dict) -> dict:
    """
    Extracts relevant fields from a raw team dict.

    Args:
        raw: Team dict from a match's homeTeam/awayTeam or get_team_by_id()

    Returns:
        Clean dict matching the Team model fields.
    """
    return {
        "id": raw.get("id"),
        "name": raw.get("name", "Unknown"),
        "short_name": raw.get("shortName") or raw.get("name", "Unknown"),
        "tla": raw.get("tla", "???"),
    }


def clean_match(raw: dict, competition_id: int) -> dict:
    """
    Flattens a raw match dict into a clean structure.
    Scheduled matches store None scores to avoid implying 0-0.

    Args:
        raw: Single match dict from get_matches_by_competition()
        competition_id: DB competition ID to link this match to

    Returns:
        Clean dict matching the Match model fields.
    """
    status = raw.get("status", "UNKNOWN")

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


def clean_player(raw: dict, team_id: int) -> dict:
    """
    Extracts player fields from a squad member dict.

    Args:
        raw: Single player dict from team['squad']
        team_id: DB team ID to link this player to

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


def clean_competitions(raw_list: list) -> list:
    """Cleans a list of raw competition dicts."""
    return [clean_competition(c) for c in raw_list if c.get("id")]


def clean_teams_from_matches(raw_matches: list) -> list:
    """
    Extracts and deduplicates both home and away teams from a match list.

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
# SofaScore cleaners
# -------------------------------------------------------------------------

def clean_sofascore_stats(raw_stats: dict, home_team: str,
                           away_team: str) -> dict:
    """
    Flattens the SofaScore statistics dict into a structured context
    object ready for the AI summarizer.

    Args:
        raw_stats: Output of get_match_statistics() from sofascore.py
        home_team: Home team name string
        away_team: Away team name string

    Returns:
        Dict with "home", "away", and "narrative_hints" keys.
    """
    if not raw_stats:
        return {}

    def _extract(key: str, side: str):
        stat = raw_stats.get(key, {})
        return stat.get(side)

    home = {
        "possession": _extract("ballPossession", "home"),
        "xg": _extract("expectedGoals", "home"),
        "big_chances": _extract("bigChances", "home"),
        "total_shots": _extract("totalShots", "home"),
        "shots_on_target": _extract("shotsOnTarget", "home"),
        "shots_off_target": _extract("shotsOffTarget", "home"),
        "shots_inside_box": _extract("shotsInsideBox", "home"),
        "passes": _extract("passes", "home"),
        "accurate_passes": _extract("accuratePasses", "home"),
        "long_balls": _extract("longBalls", "home_display"),
        "crosses": _extract("crosses", "home_display"),
        "final_third_entries": _extract("finalThirdEntries", "home"),
        "tackles": _extract("totalTackles", "home"),
        "tackles_won_pct": _extract("tacklesWon", "home_display"),
        "interceptions": _extract("interceptions", "home"),
        "recoveries": _extract("recoveries", "home"),
        "clearances": _extract("clearances", "home"),
        "aerial_duels": _extract("aerialDuels", "home_display"),
        "ground_duels": _extract("groundDuels", "home_display"),
        "dribbles": _extract("dribbles", "home_display"),
        "fouls": _extract("fouls", "home"),
        "yellow_cards": _extract("yellowCards", "home"),
        "goalkeeper_saves": _extract("goalKeeperSaves", "home"),
        "goals_prevented": _extract("goalsPrevented", "home"),
    }

    away = {
        "possession": _extract("ballPossession", "away"),
        "xg": _extract("expectedGoals", "away"),
        "big_chances": _extract("bigChances", "away"),
        "total_shots": _extract("totalShots", "away"),
        "shots_on_target": _extract("shotsOnTarget", "away"),
        "shots_off_target": _extract("shotsOffTarget", "away"),
        "shots_inside_box": _extract("shotsInsideBox", "away"),
        "passes": _extract("passes", "away"),
        "accurate_passes": _extract("accuratePasses", "away"),
        "long_balls": _extract("longBalls", "away_display"),
        "crosses": _extract("crosses", "away_display"),
        "final_third_entries": _extract("finalThirdEntries", "away"),
        "tackles": _extract("totalTackles", "away"),
        "tackles_won_pct": _extract("tacklesWon", "away_display"),
        "interceptions": _extract("interceptions", "away"),
        "recoveries": _extract("recoveries", "away"),
        "clearances": _extract("clearances", "away"),
        "aerial_duels": _extract("aerialDuels", "away_display"),
        "ground_duels": _extract("groundDuels", "away_display"),
        "dribbles": _extract("dribbles", "away_display"),
        "fouls": _extract("fouls", "away"),
        "yellow_cards": _extract("yellowCards", "away"),
        "goalkeeper_saves": _extract("goalKeeperSaves", "away"),
        "goals_prevented": _extract("goalsPrevented", "away"),
    }

    hints = []

    home_xg = _extract("expectedGoals", "home") or 0
    away_xg = _extract("expectedGoals", "away") or 0
    home_shots = _extract("totalShots", "home") or 0
    away_shots = _extract("totalShots", "away") or 0
    home_poss = _extract("ballPossession", "home") or 0
    away_poss = _extract("ballPossession", "away") or 0
    home_recoveries = _extract("recoveries", "home") or 0
    away_recoveries = _extract("recoveries", "away") or 0
    home_final_third = _extract("finalThirdEntries", "home") or 0
    away_final_third = _extract("finalThirdEntries", "away") or 0

    if home_xg and away_xg:
        if home_xg < away_xg:
            hints.append(
                f"{home_team} underperformed their xG ({home_xg}) vs "
                f"{away_team}'s xG ({away_xg}) — {away_team} created "
                f"the better chances despite the result."
            )
        elif home_xg > away_xg * 1.5:
            hints.append(
                f"{home_team} dominated in expected goals ({home_xg} vs "
                f"{away_xg}) — their attacking pressure was significant."
            )

    if home_poss and away_poss:
        dominant = home_team if home_poss > away_poss else away_team
        dominant_poss = max(home_poss, away_poss)
        other = away_team if home_poss > away_poss else home_team
        other_shots = away_shots if home_poss > away_poss else home_shots
        if dominant_poss > 60 and other_shots > 10:
            hints.append(
                f"{other} was dangerous without the ball — despite {dominant} "
                f"holding {dominant_poss}% possession, {other} still generated "
                f"{other_shots} shots suggesting a counter-attacking threat."
            )

    if home_recoveries and away_recoveries:
        if home_recoveries > away_recoveries * 1.3:
            hints.append(
                f"{home_team} pressed aggressively — {home_recoveries} ball "
                f"recoveries vs {away_team}'s {away_recoveries} suggests "
                f"a high-intensity pressing game."
            )
        elif away_recoveries > home_recoveries * 1.3:
            hints.append(
                f"{away_team} were the more aggressive pressers — "
                f"{away_recoveries} recoveries vs {home_team}'s {home_recoveries}."
            )

    if home_final_third and away_final_third:
        if away_final_third > home_final_third * 1.5:
            hints.append(
                f"{away_team} consistently threatened in the final third — "
                f"{away_final_third} entries vs {home_team}'s {home_final_third}."
            )
        elif home_final_third > away_final_third * 1.5:
            hints.append(
                f"{home_team} dominated in the attacking third — "
                f"{home_final_third} final third entries vs {away_final_third}."
            )

    return {
        "home_team": home_team,
        "away_team": away_team,
        "home": home,
        "away": away,
        "narrative_hints": hints,
    }


def clean_sofascore_lineups(raw_lineups: dict) -> dict:
    """
    Cleans and structures lineup data from SofaScore.

    Key behaviour:
        - Filters starters from substitutes using substitute: False flag
        - Only the starting 11 get tactical roles assigned
        - Substitutes are included separately without tactical roles
        - Tactical roles assigned via formation_roles.map_tactical_roles()

    Why we filter by substitute flag rather than index:
        SofaScore guarantees starters come first (indices 0-10) but
        using the explicit substitute flag is more robust — if SofaScore
        ever changes ordering, the flag stays reliable.

    Args:
        raw_lineups: Output of get_match_lineups() from sofascore.py

    Returns:
        Dict with formations, tactically enriched starters, and
        a separate substitutes list per side.
    """
    if not raw_lineups:
        return {}

    position_map = {
        "G": "Goalkeeper",
        "D": "Defender",
        "M": "Midfielder",
        "F": "Forward",
    }

    def _format_player(p: dict) -> dict:
        return {
            "id": p.get("id"),
            "name": p.get("name", "Unknown"),
            "short_name": p.get("short_name", ""),
            "position": position_map.get(
                p.get("position", ""), p.get("position", "Unknown")
            ),
            "jersey_number": p.get("jersey_number", "?"),
        }

    def _split_starters_subs(players: list) -> tuple[list, list]:
        """
        Splits player list into starters and substitutes.
        Uses substitute flag: False = starter, True = bench.
        Falls back to first 11 if flag missing on all players.
        """
        starters = [p for p in players if not p.get("substitute", True)]
        subs = [p for p in players if p.get("substitute", False)]

        # Fallback: if substitute flag missing, use first 11
        if not starters:
            starters = players[:11]
            subs = players[11:]

        return starters, subs

    home_formation = raw_lineups.get("home_formation", "Unknown")
    away_formation = raw_lineups.get("away_formation", "Unknown")

    home_all = raw_lineups.get("home_players", [])
    away_all = raw_lineups.get("away_players", [])

    home_starters_raw, home_subs_raw = _split_starters_subs(home_all)
    away_starters_raw, away_subs_raw = _split_starters_subs(away_all)

    # Format players
    home_starters = [_format_player(p) for p in home_starters_raw]
    away_starters = [_format_player(p) for p in away_starters_raw]
    home_subs = [_format_player(p) for p in home_subs_raw]
    away_subs = [_format_player(p) for p in away_subs_raw]

    # Assign tactical roles to starters only
    home_starters = map_tactical_roles(home_starters, home_formation)
    away_starters = map_tactical_roles(away_starters, away_formation)

    return {
        "confirmed": raw_lineups.get("confirmed", False),
        "home_formation": home_formation,
        "away_formation": away_formation,
        "home_players": home_starters,
        "away_players": away_starters,
        "home_substitutes": home_subs,
        "away_substitutes": away_subs,
    }


def build_match_context(match_data: dict, sofascore_stats: dict,
                         sofascore_lineups: dict) -> dict:
    """
    Combines Football-Data.org match data with SofaScore stats and
    lineups into a single rich context dict for the AI summarizer.

    Args:
        match_data: Basic match info dict (teams, score, competition, date)
        sofascore_stats: Output of clean_sofascore_stats()
        sofascore_lineups: Output of clean_sofascore_lineups()

    Returns:
        Complete context dict passed directly to summarize_match()
    """
    return {
        "home_team": match_data.get("home_team", "Home Team"),
        "away_team": match_data.get("away_team", "Away Team"),
        "home_score": match_data.get("home_score"),
        "away_score": match_data.get("away_score"),
        "competition": match_data.get("competition", "Unknown"),
        "matchday": match_data.get("matchday"),
        "date": match_data.get("date", ""),
        "home_stats": sofascore_stats.get("home", {}),
        "away_stats": sofascore_stats.get("away", {}),
        "narrative_hints": sofascore_stats.get("narrative_hints", []),
        "home_formation": sofascore_lineups.get("home_formation", "Unknown"),
        "away_formation": sofascore_lineups.get("away_formation", "Unknown"),
        "home_players": sofascore_lineups.get("home_players", []),
        "away_players": sofascore_lineups.get("away_players", []),
        "home_substitutes": sofascore_lineups.get("home_substitutes", []),
        "away_substitutes": sofascore_lineups.get("away_substitutes", []),
        "lineups_confirmed": sofascore_lineups.get("confirmed", False),
    }


# -------------------------------------------------------------------------
# Quick test
# -------------------------------------------------------------------------

if __name__ == "__main__":
    sample_match = {
        "id": 419884,
        "utcDate": "2024-01-15T20:00:00Z",
        "status": "FINISHED",
        "matchday": 21,
        "homeTeam": {"id": 57, "name": "Arsenal FC",
                     "shortName": "Arsenal", "tla": "ARS"},
        "awayTeam": {"id": 65, "name": "Manchester City FC",
                     "shortName": "Man City", "tla": "MCI"},
        "score": {"fullTime": {"home": 1, "away": 0}}
    }

    cleaned = clean_match(sample_match, competition_id=2021)
    print("Cleaned match:")
    for key, value in cleaned.items():
        print(f"  {key}: {value}")