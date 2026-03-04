"""
backend/db/writer.py

Handles all database write operations using SQLAlchemy sessions.
Takes clean dicts (output of cleaner.py) and persists them to SQLite.

Uses upsert pattern via session.merge() — safe to call multiple times
without creating duplicate records.

Pipeline position: scraper → cleaner → writer → DB
"""

from sqlalchemy.orm import sessionmaker
from backend.db.schema import (
    engine,
    Competition,
    Team,
    Match,
    Player,
    PlayerStat,
    Summary,
)


# -------------------------------------------------------------------------
# Session factory
# -------------------------------------------------------------------------
# sessionmaker() creates a Session class bound to our engine.
# Every time we need to talk to the DB we call SessionLocal() to get
# a fresh session instance. We never share sessions across threads.

SessionLocal = sessionmaker(bind=engine)


# -------------------------------------------------------------------------
# Context manager for safe session handling
# -------------------------------------------------------------------------

from contextlib import contextmanager

@contextmanager
def get_session():
    """
    Provides a transactional database session.
    
    Using this as a context manager (with get_session() as session:)
    guarantees that:
    - The session is committed if everything succeeds
    - The session is rolled back if any exception occurs
    - The session is always closed when the block exits
    
    This prevents connection leaks and partial writes.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


# -------------------------------------------------------------------------
# Writers
# -------------------------------------------------------------------------

def save_competitions(competitions: list) -> int:
    """
    Saves a list of clean competition dicts to the DB.
    Uses merge() so existing competitions are updated, not duplicated.

    Args:
        competitions: List of clean dicts from clean_competitions()

    Returns:
        Count of competitions saved.
    """
    with get_session() as session:
        for comp_data in competitions:
            # merge() checks if a record with this primary key exists.
            # If yes → update it. If no → insert it.
            competition = Competition(**comp_data)
            session.merge(competition)

    return len(competitions)


def save_teams(teams: list) -> int:
    """
    Saves a list of clean team dicts to the DB.

    Args:
        teams: List of clean dicts from clean_teams_from_matches()

    Returns:
        Count of teams saved.
    """
    with get_session() as session:
        for team_data in teams:
            team = Team(**team_data)
            session.merge(team)

    return len(teams)


def save_matches(matches: list) -> int:
    """
    Saves a list of clean match dicts to the DB.
    Only saves matches that have valid home and away team IDs.

    Args:
        matches: List of clean dicts from clean_matches()

    Returns:
        Count of matches saved.
    """
    saved = 0
    with get_session() as session:
        for match_data in matches:
            # Guard: don't save a match if team IDs are missing
            if not match_data.get("home_team_id") or not match_data.get("away_team_id"):
                print(f"Skipping match {match_data.get('id')} — missing team IDs")
                continue

            match = Match(**match_data)
            session.merge(match)
            saved += 1

    return saved


def save_players(players: list) -> int:
    """
    Saves a list of clean player dicts to the DB.

    Args:
        players: List of clean dicts from clean_player()

    Returns:
        Count of players saved.
    """
    with get_session() as session:
        for player_data in players:
            if not player_data.get("id"):
                continue
            player = Player(**player_data)
            session.merge(player)

    return len(players)


def save_player_stat(stat_data: dict) -> None:
    """
    Saves a single player stat record.
    Used when we have per-match stats for a specific player.

    Args:
        stat_data: Dict with keys matching PlayerStat model fields.
                   Must include match_id and player_id.
    """
    with get_session() as session:
        stat = PlayerStat(**stat_data)
        session.merge(stat)


def save_summary(match_id: int, content: str) -> None:
    """
    Saves or updates the AI-generated summary for a match.
    If a summary already exists for this match, it gets overwritten.

    Args:
        match_id: The DB match ID this summary belongs to.
        content: The full text of the AI-generated summary.
    """
    with get_session() as session:
        summary = Summary(match_id=match_id, content=content)
        session.merge(summary)


def get_match_ids_in_db() -> list:
    """
    Returns a list of all match IDs currently stored in the DB.
    Used by the pipeline to avoid re-fetching matches we already have.
    """
    with get_session() as session:
        results = session.query(Match.id).all()
        # results is a list of tuples like [(419884,), (419885,)]
        # We unpack each tuple to get a flat list of IDs
        return [r[0] for r in results]


# -------------------------------------------------------------------------
# Quick test
# -------------------------------------------------------------------------

if __name__ == "__main__":
    from backend.db.schema import init_db
    from backend.processors.cleaner import clean_competition, clean_team, clean_match

    # Make sure tables exist
    init_db()

    # Sample data mirroring what the API + cleaner would produce
    sample_comp = clean_competition({
        "id": 2021,
        "name": "Premier League",
        "code": "PL",
        "area": {"name": "England"}
    })

    sample_teams = [
        clean_team({"id": 57, "name": "Arsenal FC", "shortName": "Arsenal", "tla": "ARS"}),
        clean_team({"id": 65, "name": "Manchester City FC", "shortName": "Man City", "tla": "MCI"}),
    ]

    sample_match = clean_match({
        "id": 419884,
        "utcDate": "2024-01-15T20:00:00Z",
        "status": "FINISHED",
        "matchday": 21,
        "homeTeam": {"id": 57, "name": "Arsenal FC", "shortName": "Arsenal", "tla": "ARS"},
        "awayTeam": {"id": 65, "name": "Manchester City FC", "shortName": "Man City", "tla": "MCI"},
        "score": {"fullTime": {"home": 1, "away": 0}}
    }, competition_id=2021)

    # Save to DB
    saved_comps = save_competitions([sample_comp])
    saved_teams = save_teams(sample_teams)
    saved_matches = save_matches([sample_match])

    print(f"Saved {saved_comps} competition(s)")
    print(f"Saved {saved_teams} team(s)")
    print(f"Saved {saved_matches} match(es)")

    # Verify
    match_ids = get_match_ids_in_db()
    print(f"Match IDs in DB: {match_ids}")