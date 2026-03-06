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

from flask import Blueprint, jsonify, request
from sqlalchemy.orm import sessionmaker
from backend.db.schema import engine, Match, Summary, MatchEvent, Team, Competition

api = Blueprint("api", __name__)
SessionLocal = sessionmaker(bind=engine)


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def _get_db():
    return SessionLocal()


def _match_to_dict(match: Match, session) -> dict:
    """
    Serializes a Match ORM object to a plain dict for JSON response.

    WHY has_summary EXISTS:
        The frontend MatchCard needs to know whether a summary exists
        so it can show "Analysis ready" vs "No analysis yet".
        We include this boolean in the matches list response rather
        than making the frontend fire a separate request per match
        (that would be 50 extra requests for 50 cards). One query
        that gives you everything you need — this is called eager loading.
    """
    home_team = session.query(Team).filter_by(id=match.home_team_id).first()
    away_team = session.query(Team).filter_by(id=match.away_team_id).first()
    competition = session.query(Competition).filter_by(
        id=match.competition_id
    ).first()

    summary_exists = session.query(Summary).filter_by(
        match_id=match.id
    ).first() is not None

    return {
        "id": match.id,
        "competition": competition.name if competition else "Unknown",
        "competition_code": competition.code if competition else None,
        "matchday": match.matchday,
        "date": match.utc_date.strftime("%Y-%m-%d") if match.utc_date else None,
        "status": match.status,
        "home_team": home_team.name if home_team else "Unknown",
        "away_team": away_team.name if away_team else "Unknown",
        "home_score": match.home_score,
        "away_score": match.away_score,
        "has_summary": summary_exists,
    }


# -------------------------------------------------------------------------
# Health check
# -------------------------------------------------------------------------

@api.route("/health")
def health():
    """GET /api/health — simple liveness check."""
    return jsonify({"status": "ok", "service": "football-analytics-api"})


# -------------------------------------------------------------------------
# Matches
# -------------------------------------------------------------------------

@api.route("/matches")
def get_matches():
    """
    GET /api/matches

    Returns finished matches ordered by date descending.

    Query parameters:
        limit:       max results (default 20)
        competition: filter by competition code e.g. ?competition=PL
                     If omitted, returns matches across all competitions.

    WHY A QUERY PARAMETER INSTEAD OF A URL SEGMENT:
        /api/matches/PL would suggest PL is a specific match resource.
        /api/matches?competition=PL makes it clear PL is a filter on
        the matches collection — semantically correct REST design.
        Query parameters are for filtering, sorting, and pagination.
        URL segments are for identifying specific resources.

    The competition filter joins to the Competition table to match
    by code (e.g. "PL") rather than by the full name string, which
    is more robust if names change slightly.
    """
    limit = request.args.get("limit", 20, type=int)
    competition_code = request.args.get("competition", None)

    session = _get_db()
    try:
        query = (
            session.query(Match)
            .filter(Match.status == "FINISHED")
            .order_by(Match.utc_date.desc())
        )

        # If a competition code filter is provided, join to Competition
        # table and filter by code. This means ?competition=PL only
        # returns Premier League matches.
        if competition_code:
            query = (
                query
                .join(Competition, Match.competition_id == Competition.id)
                .filter(Competition.code == competition_code)
            )

        matches = query.limit(limit).all()
        result = [_match_to_dict(m, session) for m in matches]
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@api.route("/matches/<int:match_id>")
def get_match(match_id: int):
    """GET /api/matches/<id> — single match detail."""
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

    Returns the AI-generated match analysis.
    404 if no summary generated yet.
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

    Triggers the ETL + summarization pipeline.
    Processes all unanalysed matches from the most complete matchday.

    Optional JSON body:
        { "competition": "CL" }   — run for a specific competition
        Omit body or competition for default (Premier League auto mode).

    WHY SYNCHRONOUS:
        Async job queues (Celery, RQ) add significant complexity.
        The pipeline takes 2-3 minutes for a full matchday. The frontend
        PipelineButton shows a spinner during this time — acceptable UX
        for a development tool at this stage of the project.

    Response shape:
        {
            "status": "pipeline_complete",
            "competition": "Premier League",
            "analysed": 8,
            "failed": 0,
            "results": [ { "match_id": ..., "status": "ok" }, ... ]
        }
    """
    try:
        from backend.main import run_pipeline as _run_pipeline, COMPETITIONS

        # Read optional competition from JSON body
        # request.get_json() returns None if body is empty or not JSON
        body = request.get_json(silent=True) or {}
        competition_code = body.get("competition", "PL")

        if competition_code not in COMPETITIONS:
            return jsonify({
                "error": f"Unknown competition: {competition_code}",
                "supported": list(COMPETITIONS.keys()),
            }), 400

        comp_name = COMPETITIONS[competition_code]["name"]
        results = _run_pipeline(competition_code=competition_code)

        ok_count   = sum(1 for r in results if r["status"] == "ok")
        fail_count = sum(1 for r in results if r["status"] == "error")

        return jsonify({
            "status": "pipeline_complete",
            "competition": comp_name,
            "analysed": ok_count,
            "failed": fail_count,
            "results": results,
        })

    except Exception as e:
        return jsonify({"error": str(e), "status": "pipeline_failed"}), 500
