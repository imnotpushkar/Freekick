"""
backend/api/routes.py

Defines all REST API endpoints for the Football Analytics system.
"""

from flask import Blueprint, jsonify, request
from sqlalchemy.orm import sessionmaker
from backend.db.schema import engine, Match, Summary, MatchEvent, Team, Competition, MatchStat

api = Blueprint("api", __name__)
SessionLocal = sessionmaker(bind=engine)


def _get_db():
    return SessionLocal()


def _match_to_dict(match: Match, session) -> dict:
    home_team = session.query(Team).filter_by(id=match.home_team_id).first()
    away_team = session.query(Team).filter_by(id=match.away_team_id).first()
    competition = session.query(Competition).filter_by(id=match.competition_id).first()
    summary_exists = session.query(Summary).filter_by(match_id=match.id).first() is not None

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


@api.route("/health")
def health():
    return jsonify({"status": "ok", "service": "football-analytics-api"})


@api.route("/matches")
def get_matches():
    """
    GET /api/matches
    Returns finished matches ordered by date descending.
    Query params: limit (default 20), competition (e.g. PL)
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
        if competition_code:
            query = (
                query
                .join(Competition, Match.competition_id == Competition.id)
                .filter(Competition.code == competition_code)
            )
        matches = query.limit(limit).all()
        return jsonify([_match_to_dict(m, session) for m in matches])
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


@api.route("/matches/<int:match_id>/stats")
def get_match_stats(match_id: int):
    """
    GET /api/matches/<id>/stats

    Returns team-level stats from the match_stats table.
    Two rows per match — one home (is_home=True), one away (is_home=False).
    Populated by the pipeline from SofaScore /match/statistics endpoint.

    WHY match_stats AND NOT player_stats:
        SofaScore returns possession, xG, shots as team aggregates.
        match_stats stores them directly as two rows per match.
        player_stats is for future per-player data sources and is
        currently empty — querying it would always return available:false.

    Returns available:false if pipeline hasn't run for this match,
    or if SofaScore data was unavailable when it did.
    """
    session = _get_db()
    try:
        match = session.query(Match).filter_by(id=match_id).first()
        if not match:
            return jsonify({"error": f"Match {match_id} not found"}), 404

        home_team = session.query(Team).filter_by(id=match.home_team_id).first()
        away_team = session.query(Team).filter_by(id=match.away_team_id).first()

        stat_rows = session.query(MatchStat).filter_by(match_id=match_id).all()

        if not stat_rows:
            return jsonify({
                "match_id": match_id,
                "available": False,
                "note": "No stats found. Run the pipeline for this match."
            })

        def _row_to_dict(row: MatchStat) -> dict:
            # None values are preserved — frontend handles missing data.
            # We never substitute fake zeros: a 0 on a stat bar looks
            # like real data, which is misleading if the value is absent.
            return {
                "possession":          row.possession,
                "xg":                  row.xg,
                "big_chances":         row.big_chances,
                "total_shots":         row.total_shots,
                "shots_on_target":     row.shots_on_target,
                "shots_off_target":    row.shots_off_target,
                "shots_inside_box":    row.shots_inside_box,
                "passes":              row.passes,
                "accurate_passes":     row.accurate_passes,
                "pass_accuracy":       row.pass_accuracy,
                "tackles":             row.tackles,
                "interceptions":       row.interceptions,
                "recoveries":          row.recoveries,
                "clearances":          row.clearances,
                "fouls":               row.fouls,
                "final_third_entries": row.final_third_entries,
                "goalkeeper_saves":    row.goalkeeper_saves,
                "goals_prevented":     row.goals_prevented,
            }

        home_row = next((r for r in stat_rows if r.is_home), None)
        away_row = next((r for r in stat_rows if not r.is_home), None)

        home_dict = _row_to_dict(home_row) if home_row else {}
        away_dict = _row_to_dict(away_row) if away_row else {}

        home_dict["team"] = home_team.name if home_team else "Home"
        away_dict["team"] = away_team.name if away_team else "Away"

        return jsonify({
            "match_id": match_id,
            "available": True,
            "home": home_dict,
            "away": away_dict,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@api.route("/matches/<int:match_id>/summary")
def get_summary(match_id: int):
    """GET /api/matches/<id>/summary — AI-generated match analysis."""
    session = _get_db()
    try:
        summary = session.query(Summary).filter_by(match_id=match_id).first()
        if not summary:
            return jsonify({"error": f"No summary for match {match_id}."}), 404
        return jsonify({
            "match_id": match_id,
            "content": summary.content,
            "generated_at": summary.generated_at.isoformat() if summary.generated_at else None,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@api.route("/matches/<int:match_id>/events")
def get_events(match_id: int):
    """GET /api/matches/<id>/events — goals, cards, substitutions."""
    session = _get_db()
    try:
        events = (
            session.query(MatchEvent)
            .filter_by(match_id=match_id)
            .order_by(MatchEvent.minute)
            .all()
        )
        if not events:
            return jsonify({"match_id": match_id, "events": [], "note": "No events recorded."})

        return jsonify({
            "match_id": match_id,
            "events": [{
                "type": e.event_type,
                "minute": e.minute,
                "player": e.player_name,
                "secondary_player": e.secondary_player_name,
                "detail": e.detail,
                "reason": e.reason,
            } for e in events]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@api.route("/pipeline/run", methods=["POST"])
def run_pipeline():
    """POST /api/pipeline/run — triggers ETL + summarization pipeline."""
    try:
        from backend.main import run_pipeline as _run_pipeline, COMPETITIONS

        body = request.get_json(silent=True) or {}
        competition_code = body.get("competition", "PL")

        if competition_code not in COMPETITIONS:
            return jsonify({
                "error": f"Unknown competition: {competition_code}",
                "supported": list(COMPETITIONS.keys()),
            }), 400

        comp_name = COMPETITIONS[competition_code]["name"]
        results = _run_pipeline(competition_code=competition_code)
        ok_count = sum(1 for r in results if r["status"] == "ok")
        fail_count = len(results) - ok_count

        return jsonify({
            "status": "pipeline_complete",
            "competition": comp_name,
            "analysed": ok_count,
            "failed": fail_count,
            "results": results,
        })

    except Exception as e:
        return jsonify({"error": str(e), "status": "pipeline_failed"}), 500
