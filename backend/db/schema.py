"""
backend/db/schema.py

Defines the database schema using SQLAlchemy ORM.
Creates the SQLite database file at data/football.db if it doesn't exist.

Tables:
    - competitions:  league/cup info
    - teams:         team info
    - matches:       match results linked to competitions and teams
    - players:       player info linked to a team
    - player_stats:  per-match stats per player (reserved for future player-level data)
    - match_stats:   per-match team-level stats (possession, xG, shots, etc.)  ← NEW
    - match_events:  goals, cards, substitutions per match
    - summaries:     AI-generated summaries linked to a match

DESIGN NOTE — match_stats vs player_stats:
    player_stats stores one row PER PLAYER per match.
    match_stats stores one row PER TEAM per match (two rows total per match).

    Possession, xG, shots, tackles etc. come from SofaScore's
    /match/statistics endpoint, which returns team-level aggregates —
    not broken down by player. Storing them in player_stats would mean
    duplicating the same team value across 11 player rows and then
    averaging it back out, which is architecturally wrong.

    match_stats is the correct home for team-level stats from SofaScore.
"""

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import os

# -------------------------------------------------------------------------
# Engine setup
# -------------------------------------------------------------------------
# create_engine() connects SQLAlchemy to a database.
# "sqlite:///..." is the connection URL — three slashes = relative path.
# We build the path dynamically using __file__ so it works regardless
# of which directory the script is called from.
# echo=False: SQLAlchemy won't print every SQL statement it executes.

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "football.db")
DB_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DB_URL, echo=False)

# -------------------------------------------------------------------------
# Base class
# -------------------------------------------------------------------------
# declarative_base() returns a class that all table models inherit from.
# SQLAlchemy uses this registry to know which classes represent tables.

Base = declarative_base()


# -------------------------------------------------------------------------
# Table definitions
# -------------------------------------------------------------------------

class Competition(Base):
    """
    Represents a football competition (e.g. Premier League, Champions League).
    """
    __tablename__ = "competitions"

    id = Column(Integer, primary_key=True)          # Football-Data.org competition ID
    name = Column(String(100), nullable=False)       # e.g. "Premier League"
    code = Column(String(20), unique=True)           # e.g. "PL"
    country = Column(String(50))                     # e.g. "England"

    matches = relationship("Match", back_populates="competition")

    def __repr__(self):
        return f"<Competition {self.name}>"


class Team(Base):
    """
    Represents a football club.
    """
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True)           # Football-Data.org team ID
    name = Column(String(100), nullable=False)       # e.g. "Arsenal FC"
    short_name = Column(String(50))                  # e.g. "Arsenal"
    tla = Column(String(5))                          # Three Letter Abbreviation

    players = relationship("Player", back_populates="team")

    def __repr__(self):
        return f"<Team {self.name}>"


class Match(Base):
    """
    Represents a single football match.
    Links to Competition and to two Teams (home and away).
    """
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True)           # Football-Data.org match ID
    competition_id = Column(Integer, ForeignKey("competitions.id"))
    home_team_id = Column(Integer, ForeignKey("teams.id"))
    away_team_id = Column(Integer, ForeignKey("teams.id"))
    matchday = Column(Integer)
    status = Column(String(20))                      # FINISHED, SCHEDULED, etc.
    utc_date = Column(DateTime)
    home_score = Column(Integer)
    away_score = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    competition = relationship("Competition", back_populates="matches")
    home_team = relationship("Team", foreign_keys=[home_team_id])
    away_team = relationship("Team", foreign_keys=[away_team_id])
    player_stats = relationship("PlayerStat", back_populates="match")
    match_stats = relationship("MatchStat", back_populates="match")
    match_events = relationship("MatchEvent", back_populates="match")
    summary = relationship("Summary", back_populates="match", uselist=False)

    def __repr__(self):
        return f"<Match {self.home_team_id} vs {self.away_team_id}>"


class Player(Base):
    """
    Represents a football player linked to a team.
    """
    __tablename__ = "players"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    position = Column(String(50))
    nationality = Column(String(50))
    team_id = Column(Integer, ForeignKey("teams.id"))

    team = relationship("Team", back_populates="players")
    stats = relationship("PlayerStat", back_populates="player")

    def __repr__(self):
        return f"<Player {self.name}>"


class PlayerStat(Base):
    """
    Per-match statistics for a single player.
    Reserved for future player-level data sources.
    Currently unpopulated — team-level stats live in MatchStat.
    """
    __tablename__ = "player_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("matches.id"))
    player_id = Column(Integer, ForeignKey("players.id"))
    team_id = Column(Integer, ForeignKey("teams.id"))

    goals = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    minutes_played = Column(Integer, default=0)
    yellow_cards = Column(Integer, default=0)
    red_cards = Column(Integer, default=0)
    shots = Column(Integer, default=0)
    shots_on_target = Column(Integer, default=0)
    xg = Column(Float, default=0.0)
    passes = Column(Integer, default=0)
    pass_accuracy = Column(Float, default=0.0)
    tackles = Column(Integer, default=0)
    interceptions = Column(Integer, default=0)

    match = relationship("Match", back_populates="player_stats")
    player = relationship("Player", back_populates="stats")

    def __repr__(self):
        return f"<PlayerStat player={self.player_id} match={self.match_id}>"


class MatchStat(Base):
    """
    Team-level statistics for one side in a match.
    Two rows per match — one for home team, one for away team.

    All values sourced from SofaScore /match/statistics endpoint.
    Populated by the pipeline when SofaScore data is available.

    WHY TWO ROWS PER MATCH (not one row with home_ and away_ columns):
        Two rows per match follows the same pattern as MatchEvent —
        each row belongs to one team (identified by team_id + is_home).
        This makes it easy to query "all stats for team X across all
        matches" without needing to union home and away columns.
        It also means adding a new stat column adds it once, not twice.

    COLUMN NAMING:
        Names match the keys in clean_sofascore_stats() output exactly
        (home/away sub-dicts) so writer.py can pass them directly
        without a remapping step.
    """
    __tablename__ = "match_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    is_home = Column(Boolean, nullable=False)

    # Possession and chance quality
    possession = Column(Float)            # ball possession % e.g. 62.0
    xg = Column(Float)                    # expected goals e.g. 3.18
    big_chances = Column(Integer)         # clear-cut chances

    # Shots
    total_shots = Column(Integer)
    shots_on_target = Column(Integer)
    shots_off_target = Column(Integer)
    shots_inside_box = Column(Integer)

    # Passing
    passes = Column(Integer)              # total passes attempted
    accurate_passes = Column(Integer)     # passes completed
    pass_accuracy = Column(Float)         # computed: accurate/total * 100

    # Defensive
    tackles = Column(Integer)
    interceptions = Column(Integer)
    recoveries = Column(Integer)          # total ball recoveries (pressing indicator)
    clearances = Column(Integer)
    fouls = Column(Integer)

    # Attacking movement
    final_third_entries = Column(Integer)
    long_balls = Column(String(20))       # stored as display string e.g. "34/67"
    crosses = Column(String(20))          # stored as display string e.g. "3/8"

    # Goalkeeper
    goalkeeper_saves = Column(Integer)
    goals_prevented = Column(Float)       # xG prevented by GK

    match = relationship("Match", back_populates="match_stats")

    def __repr__(self):
        side = "Home" if self.is_home else "Away"
        return f"<MatchStat {side} match={self.match_id} xg={self.xg}>"


class MatchEvent(Base):
    """
    Stores individual match events — goals, cards, substitutions.

    For goals:
        player_name = scorer, secondary_player_name = assist (nullable)
        detail = "regular", "penalty", or "own-goal"

    For cards:
        player_name = player carded, secondary_player_name = None
        detail = "yellow", "yellow-red", or "red"
        reason = foul reason string (nullable)

    For substitutions:
        player_name = player coming OFF
        secondary_player_name = player coming ON
        detail = "injury" or "tactical"
    """
    __tablename__ = "match_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    event_type = Column(String(20), nullable=False)
    minute = Column(Integer, nullable=False)
    is_home = Column(Boolean, nullable=False)
    player_name = Column(String(100))
    secondary_player_name = Column(String(100))
    detail = Column(String(50))
    reason = Column(String(100))

    match = relationship("Match", back_populates="match_events")

    def __repr__(self):
        return (
            f"<MatchEvent {self.event_type} {self.minute}' "
            f"{self.player_name} match={self.match_id}>"
        )


class Summary(Base):
    """
    Stores the AI-generated performance summary for a match.
    One summary per match.
    """
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("matches.id"), unique=True)
    content = Column(Text, nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow)

    match = relationship("Match", back_populates="summary")

    def __repr__(self):
        return f"<Summary match={self.match_id}>"


# -------------------------------------------------------------------------
# Database initializer
# -------------------------------------------------------------------------

def init_db():
    """
    Creates all tables that don't already exist.
    Safe to call multiple times — won't touch existing tables or data.

    IMPORTANT — SQLite migration limitation:
        create_all() creates NEW tables only. It does NOT alter existing
        tables to add columns. If you add a column to an existing model,
        you must either:
          a) Delete data/football.db and let it recreate (dev only), or
          b) Use a migration tool like Alembic (production standard).
        Adding a NEW table (like match_stats) is always safe — create_all()
        will create it without touching any existing tables.
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    Base.metadata.create_all(engine)
    print(f"Database initialized at: {DB_PATH}")


if __name__ == "__main__":
    init_db()
