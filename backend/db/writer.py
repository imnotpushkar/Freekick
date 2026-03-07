"""
backend/db/writer.py

Handles all database write operations using SQLAlchemy sessions.
Takes clean dicts (output of cleaner.py) and persists them to SQLite.

Uses upsert pattern via session.merge() — safe to call multiple times
without creating duplicate records.

Pipeline position: scraper → cleaner → writer → DB
"""

from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker
from backend.db.schema import (
    engine,
    Competition,
    Team,
    Match,
    Player,
    PlayerStat,
    MatchStat,
    MatchEvent,
    Summary,
)

SessionLocal = sessionmaker(bind=engine)


@contextmanager
def get_session():
    """
    Provides a transactional database session as a context manager.
    Commits on success, rolls back on any exception, always closes.

    WHY A CONTEXT MANAGER:
        The 'with' statement guarantees cleanup even if an exception
        is raised mid-function. Without this pattern you'd need
        try/except/finally in every function that touches the DB.
        contextmanager lets us write that cleanup logic once here.

    Usage:
        with get_session() as session:
            session.merge(some_object)
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


def save_competitions(competitions: list) -> int:
    """
    Saves a list of clean competition dicts to the DB.
    Uses merge() so existing competitions are updated, not duplicated.
    """
    with get_session() as session:
        for comp_data in competitions:
            competition = Competition(**comp_data)
            session.merge(competition)
    return len(competitions)


def save_teams(teams: list) -> int:
    """Saves a list of clean team dicts to the DB."""
    with get_session() as session:
        for team_data in teams:
            team = Team(**team_data)
            session.merge(team)
    return len(teams)


def save_matches(matches: list) -> int:
    """
    Saves a list of clean match dicts to the DB.
    Skips matches with missing team IDs.
    """
    saved = 0
    with get_session() as session:
        for match_data in matches:
            if not match_data.get("home_team_id") or not match_data.get("away_team_id"):
                print(f"Skipping match {match_data.get('id')} — missing team IDs")
                continue
            match = Match(**match_data)
            session.merge(match)
            saved += 1
    return saved


def save_players(players: list) -> int:
    """Saves a list of clean player dicts to the DB."""
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
    Reserved for future player-level data sources.
    Currently not called by the pipeline — team-level stats
    use save_match_stats() instead.
    """
    with get_session() as session:
        stat = PlayerStat(**stat_data)
        session.merge(stat)


def save_match_stats(match_id: int, match: dict, stats: dict) -> int:
    """
    Saves team-level match statistics from SofaScore to the match_stats table.
    Stores two rows per match — one for home team, one for away team.

    WHY DELETE-THEN-INSERT:
        MatchStat rows don't have a single natural business key we can
        use with merge(). We could use (match_id, team_id) as a composite
        key, but delete-then-insert is simpler and equally idempotent —
        re-running the pipeline for the same match overwrites the stats
        cleanly. This is the same pattern used for match_events.

    Args:
        match_id:  The DB match ID these stats belong to.
        match:     Match dict with home_team_id and away_team_id.
                   Shape: { "home_team_id": int, "away_team_id": int }
        stats:     Output of clean_sofascore_stats() from cleaner.py.
                   Shape: { "home": {...}, "away": {...} }

    Returns:
        Number of rows saved (always 2 if successful, 0 if no stats).
    """
    if not stats or not stats.get("home") or not stats.get("away"):
        return 0

    home_team_id = match.get("home_team_id")
    away_team_id = match.get("away_team_id")

    if not home_team_id or not away_team_id:
        return 0

    def _build_stat_row(side_stats: dict, team_id: int, is_home: bool) -> MatchStat:
        """
        Constructs a MatchStat ORM object from a side's stats dict.
        The keys in side_stats map directly to MatchStat column names —
        this is intentional design: cleaner.py output keys match schema
        column names so no remapping is needed here.
        """
        return MatchStat(
            match_id=match_id,
            team_id=team_id,
            is_home=is_home,
            possession=side_stats.get("possession"),
            xg=side_stats.get("xg"),
            big_chances=side_stats.get("big_chances"),
            total_shots=side_stats.get("total_shots"),
            shots_on_target=side_stats.get("shots_on_target"),
            shots_off_target=side_stats.get("shots_off_target"),
            shots_inside_box=side_stats.get("shots_inside_box"),
            passes=side_stats.get("passes"),
            accurate_passes=side_stats.get("accurate_passes"),
            pass_accuracy=_compute_pass_accuracy(
                side_stats.get("accurate_passes"),
                side_stats.get("passes")
            ),
            tackles=side_stats.get("tackles"),
            interceptions=side_stats.get("interceptions"),
            recoveries=side_stats.get("recoveries"),
            clearances=side_stats.get("clearances"),
            fouls=side_stats.get("fouls"),
            final_third_entries=side_stats.get("final_third_entries"),
            long_balls=str(side_stats.get("long_balls", "")) or None,
            crosses=str(side_stats.get("crosses", "")) or None,
            goalkeeper_saves=side_stats.get("goalkeeper_saves"),
            goals_prevented=side_stats.get("goals_prevented"),
        )

    with get_session() as session:
        # Delete existing stats for this match before re-inserting
        session.query(MatchStat).filter_by(match_id=match_id).delete()

        home_row = _build_stat_row(stats["home"], home_team_id, is_home=True)
        away_row = _build_stat_row(stats["away"], away_team_id, is_home=False)

        session.add(home_row)
        session.add(away_row)

    return 2


def _compute_pass_accuracy(accurate: int | None, total: int | None) -> float | None:
    """
    Computes pass accuracy percentage from accurate and total passes.

    WHY COMPUTE HERE INSTEAD OF STORING THE CLEANER VALUE:
        SofaScore returns pass accuracy as a display string in some
        responses (e.g. "89%"). Computing it ourselves from the raw
        counts (accurate_passes / passes * 100) is more reliable and
        gives us a clean float rather than a string to parse.
        If either value is missing, returns None — no fake zeros.
    """
    if accurate is None or total is None or total == 0:
        return None
    return round((accurate / total) * 100, 1)


def save_match_events(match_id: int, incidents: dict) -> int:
    """
    Saves parsed match events (goals, cards, substitutions) to the DB.

    Strategy: delete all existing events for this match first, then
    re-insert. Idempotent — safe to re-run the pipeline.

    NOTE on is_home bug:
        clean_match_incidents() stores team name (string) not is_home
        (bool) in each incident. We can't reliably derive is_home from
        team name in this function without passing in home_team_name.
        This is a known minor issue — is_home in match_events is not
        used anywhere in the API or frontend currently.
        Fix when the API needs it: pass home_team_name parameter and
        compare incident["team"] == home_team_name.
    """
    if not incidents:
        return 0

    with get_session() as session:
        session.query(MatchEvent).filter_by(match_id=match_id).delete()

        saved = 0

        for goal in incidents.get("goals", []):
            event = MatchEvent(
                match_id=match_id,
                event_type="goal",
                minute=goal["minute"],
                is_home=False,  # placeholder — see NOTE above
                player_name=goal["scorer"],
                secondary_player_name=goal.get("assist"),
                detail=goal.get("type", "regular"),
                reason=None,
            )
            session.add(event)
            saved += 1

        for card in incidents.get("cards", []):
            event = MatchEvent(
                match_id=match_id,
                event_type="card",
                minute=card["minute"],
                is_home=False,  # placeholder
                player_name=card["player"],
                secondary_player_name=None,
                detail=card["card_type"],
                reason=card.get("reason"),
            )
            session.add(event)
            saved += 1

        for sub in incidents.get("substitutions", []):
            event = MatchEvent(
                match_id=match_id,
                event_type="substitution",
                minute=sub["minute"],
                is_home=False,  # placeholder
                player_name=sub["player_off"],
                secondary_player_name=sub["player_on"],
                detail="injury" if sub.get("injury") else "tactical",
                reason=None,
            )
            session.add(event)
            saved += 1

    return saved


def save_summary(match_id: int, content: str) -> None:
    """
    Saves or updates the AI-generated summary for a match.
    Checks for an existing summary and updates it rather than
    inserting — avoids UNIQUE constraint errors on re-runs.
    """
    with get_session() as session:
        existing = session.query(Summary).filter_by(match_id=match_id).first()
        if existing:
            existing.content = content
        else:
            summary = Summary(match_id=match_id, content=content)
            session.add(summary)


def get_match_ids_in_db() -> list:
    """
    Returns all match IDs currently stored in the DB.
    Used by the pipeline to skip already-stored matches.
    """
    with get_session() as session:
        results = session.query(Match.id).all()
        return [r[0] for r in results]


# -------------------------------------------------------------------------
# Quick test
# -------------------------------------------------------------------------

if __name__ == "__main__":
    from backend.db.schema import init_db
    from backend.processors.cleaner import clean_competition, clean_team, clean_match

    init_db()

    sample_comp = clean_competition({
        "id": 2021, "name": "Premier League", "code": "PL",
        "area": {"name": "England"}
    })
    sample_teams = [
        clean_team({"id": 57, "name": "Arsenal FC",
                    "shortName": "Arsenal", "tla": "ARS"}),
        clean_team({"id": 65, "name": "Manchester City FC",
                    "shortName": "Man City", "tla": "MCI"}),
    ]
    sample_match = clean_match({
        "id": 419884, "utcDate": "2024-01-15T20:00:00Z",
        "status": "FINISHED", "matchday": 21,
        "homeTeam": {"id": 57, "name": "Arsenal FC",
                     "shortName": "Arsenal", "tla": "ARS"},
        "awayTeam": {"id": 65, "name": "Manchester City FC",
                     "shortName": "Man City", "tla": "MCI"},
        "score": {"fullTime": {"home": 1, "away": 0}}
    }, competition_id=2021)

    print(f"Saved {save_competitions([sample_comp])} competition(s)")
    print(f"Saved {save_teams(sample_teams)} team(s)")
    print(f"Saved {save_matches([sample_match])} match(es)")
    print(f"Total match IDs in DB: {len(get_match_ids_in_db())}")
