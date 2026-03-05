"""
backend/api/routes.py

Defines all REST API endpoints for the Football Analytics system.

REST (Representational State Transfer) is an architectural style for APIs.
Key conventions we follow:
    - GET requests read data, never modify it
    - POST requests trigger actions or create data
    - URLs identify resources: /matches/<id> = a specific match
    - Responses are always JSON
    - HTTP status codes communicate outcome:
        200 = success
        404 = resource not found
        500 = server error

Blueprint:
    A Blueprint is Flask's way of grouping related routes.
    We define all routes on the 'api' Blueprint here.
    app.py registers it with url_prefix="/api" so every
    route here is automatically prefixed with /api.

    Example: @api.route("/matches") becomes GET /api/matches
"""

from flask import Blueprint, jsonify
from sqlalchemy.orm import sessionmaker
from backend.db.schema import engine, Match, Summary, MatchEvent, Team, Competition

# Create the Blueprint — 'api' is its internal name
api = Blueprint("api", __name__)

# Create a SQLAlchemy session factory for read queries
SessionLocal = sessionmaker(bind=engine)


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def _get_db():
    """
    Returns a new SQLAlchemy session.
    Caller is responsible for closing it.
    """
    return SessionLocal()


def _match_to_dict(match: Match, session) -> dict:
    """
    Serializes a Match ORM object to a plain dict for JSON response.

    WHY has_summary EXISTS:
        The frontend MatchCard component needs to know whether a summary
        has been generated for each match so it can show "Analysis ready"
        vs "No analysis yet". Rather than making the frontend fire a
        separate request per match (50 extra requests for 50 cards),
        we include this boolean directly in the matches list response.
        This is called "eager loading" of related data — one query
        that gives you everything you need in one response.

    Args:
        match: SQLAlchemy Match instance
        session: Active DB session (needed to query related tables)

    Returns:
        Dict with match fields suitable for JSON serialization.
    """
    home_team = session.query(Team).filter_by(id=match.home_team_id).first()
    away_team = session.query(Team).filter_by(id=match.away_team_id).first()
    competition = session.query(Competition).filter_by(
        id=match.competition_id
    ).first()

    # Check if a summary exists for this match.
    # .first() returns None if no row found — bool(None) = False.
    # bool(summary_row) = True if a row exists.
    # This is a single lightweight query — just checks for existence.
    summary_exists = session.query(Summary).filter_by(
        match_id=match.id
    ).first() is not None

    return {
        "id": match.id,
        "competition": competition.name if competition else "Unknown",
        "matchday": match.matchday,
        "date": match.utc_date.strftime("%Y-%m-%d") if match.utc_date else None,
        "status": match.status,
        "home_team": home_team.name if home_team else "Unknown",
        "away_team": away_team.name if away_team else "Unknown",
        "home_score": match.home_score,
        "away_score": match.away_score,
        "has_summary": summary_exists,   # NEW — drives MatchCard badge
    }


# -------------------------------------------------------------------------
# Health check
# -------------------------------------------------------------------------

@api.route("/health")
def health():
    """
    GET /api/health

    Simple health check endpoint.
    Returns 200 with status "ok".
    """
    return jsonify({"status": "ok", "service": "football-analytics-api"})


# -------------------------------------------------------------------------
# Matches
# -------------------------------------------------------------------------

@api.route("/matches")
def get_matches():
    """
    GET /api/matches

    Returns all finished matches stored in the DB,
    ordered by date descending (most recent first).

    Query parameters (optional):
        limit: max number of matches to return (default 20)
    """
    from flask import request

    limit = request.args.get("limit", 20, type=int)

    session = _get_db()
    try:
        matches = (
            session.query(Match)
            .filter(Match.status == "FINISHED")
            .order_by(Match.utc_date.desc())
            .limit(limit)
            .all()
        )

        result = [_match_to_dict(m, session) for m in matches]
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        session.close()


@api.route("/matches/<int:match_id>")
def get_match(match_id: int):
    """
    GET /api/matches/<id>

    Returns details for a single match by its Football-Data.org ID.
    Returns 404 if match not found in DB.
    """
    session = _get_db()
    try:
        match = session.query(Match).filter_by(id=match_id).first()

        if not match:
            return jsonify({"error": f"Match {match_id} not found"}), 404

        return jsonify(_match_to_dict(match, session))

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        session.close()


# -------------------------------------------------------------------------
# Summaries
# -------------------------------------------------------------------------

@api.route("/matches/<int:match_id>/summary")
def get_summary(match_id: int):
    """
    GET /api/matches/<id>/summary

    Returns the AI-generated match analysis for a specific match.
    Returns 404 if no summary has been generated yet.

    Response shape:
        {
            "match_id": 538074,
            "content": "## THE STORY OF THE MATCH\n...",
            "generated_at": "2026-03-05T14:22:11"
        }
    """
    session = _get_db()
    try:
        summary = session.query(Summary).filter_by(match_id=match_id).first()

        if not summary:
            return jsonify({
                "error": f"No summary found for match {match_id}. "
                         f"Run the pipeline first."
            }), 404

        return jsonify({
            "match_id": match_id,
            "content": summary.content,
            "generated_at": summary.generated_at.isoformat()
            if summary.generated_at else None,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        session.close()


# -------------------------------------------------------------------------
# Match Events
# -------------------------------------------------------------------------

@api.route("/matches/<int:match_id>/events")
def get_events(match_id: int):
    """
    GET /api/matches/<id>/events

    Returns all match events (goals, cards, substitutions)
    ordered chronologically by minute.

    Response shape:
        {
            "match_id": 538074,
            "events": [
                {
                    "type": "card",
                    "minute": 26,
                    "player": "Jacob Ramsey",
                    "detail": "yellow",
                    "secondary_player": null,
                    "reason": "Foul"
                },
                ...
            ]
        }
    """
    session = _get_db()
    try:
        events = (
            session.query(MatchEvent)
            .filter_by(match_id=match_id)
            .order_by(MatchEvent.minute)
            .all()
        )

        if not events:
            return jsonify({
                "match_id": match_id,
                "events": [],
                "note": "No events recorded for this match."
            })

        result = []
        for e in events:
            result.append({
                "type": e.event_type,
                "minute": e.minute,
                "player": e.player_name,
                "secondary_player": e.secondary_player_name,
                "detail": e.detail,
                "reason": e.reason,
            })

        return jsonify({"match_id": match_id, "events": result})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        session.close()


# -------------------------------------------------------------------------
# Pipeline trigger
# -------------------------------------------------------------------------

@api.route("/pipeline/run", methods=["POST"])
def run_pipeline():
    """
    POST /api/pipeline/run

    Triggers the full ETL + summarization pipeline.
    Synchronous — waits for completion before responding (~22s).

    WHY POST AND NOT GET:
        GET requests must be side-effect free — safe to call
        repeatedly. This endpoint writes to the DB, so it's a POST.

    Returns the generated summary for the latest match.
    """
    try:
        from backend.main import run_pipeline as _run_pipeline

        _run_pipeline()

        session = _get_db()
        try:
            latest_match = (
                session.query(Match)
                .filter(Match.status == "FINISHED")
                .order_by(Match.utc_date.desc())
                .first()
            )

            if not latest_match:
                return jsonify({"error": "No finished matches found"}), 404

            summary = session.query(Summary).filter_by(
                match_id=latest_match.id
            ).first()

            match_info = _match_to_dict(latest_match, session)

            return jsonify({
                "status": "pipeline_complete",
                "match": match_info,
                "summary": summary.content if summary else None,
            })

        finally:
            session.close()

    except Exception as e:
        return jsonify({"error": str(e), "status": "pipeline_failed"}), 500
