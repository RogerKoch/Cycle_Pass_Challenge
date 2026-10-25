"""API-Endpunkte fuer den dauerhaften Tausch von Kraftuebungen und das Abhaken von Saetzen."""

import logging
from datetime import date

from flask import Blueprint, jsonify, request

from backend.engine.strength_alternatives import alternatives_for
from backend.extensions import db
from backend.models.exercise_swaps import ExerciseSwap, exercise_swaps
from backend.models.set_logs import SetLog, sets_done

logger = logging.getLogger(__name__)

exercises_bp = Blueprint("exercises", __name__, url_prefix="/api/exercises")


@exercises_bp.get("/swaps")
def list_swaps():
    """Gibt alle aktiven Tausche zurueck (Originalname -> Alternative)."""
    return jsonify(exercise_swaps()), 200


@exercises_bp.put("/swap")
def set_swap():
    """Tauscht eine Uebung dauerhaft gegen eine Alternative. 400 bei unbekannter Alternative."""
    body = request.get_json(force=True, silent=True) or {}
    original, alternative = body.get("original"), body.get("alternative")
    if alternative not in {a.name for a in alternatives_for(original)}:
        return jsonify({"error": f"keine Alternative '{alternative}' fuer '{original}'"}), 400
    swap = ExerciseSwap.query.filter_by(original_name=original).first()
    if swap is None:
        db.session.add(ExerciseSwap(original_name=original, alternative_name=alternative))
    else:
        swap.alternative_name = alternative
    db.session.commit()
    return jsonify(exercise_swaps()), 200


@exercises_bp.delete("/swap")
def clear_swap():
    """Hebt den Tausch einer Uebung auf (zurueck zum Original bzw. zur Material-Automatik)."""
    original = (request.get_json(force=True, silent=True) or {}).get("original")
    swap = ExerciseSwap.query.filter_by(original_name=original).first()
    if swap is not None:
        db.session.delete(swap)
        db.session.commit()
    return jsonify(exercise_swaps()), 200


@exercises_bp.get("/sets/<day>")
def list_sets(day: str):
    """Erledigte Saetze eines Tages (Uebungsname -> Satz-Indizes). 400 bei ungueltigem Datum."""
    try:
        return jsonify(sets_done(date.fromisoformat(day))), 200
    except ValueError:
        return jsonify({"error": "ungueltiges Datum"}), 400


@exercises_bp.put("/sets")
def set_set_done():
    """Hakt einen Satz ab oder macht das rueckgaengig. Body: {date, exercise, set_index, done}."""
    body = request.get_json(force=True, silent=True) or {}
    exercise, set_index = body.get("exercise"), body.get("set_index")
    try:
        day = date.fromisoformat(body.get("date", ""))
    except (TypeError, ValueError):
        return jsonify({"error": "ungueltiges Datum"}), 400
    if not isinstance(exercise, str) or not exercise or len(exercise) > 100:
        return jsonify({"error": "Uebung fehlt"}), 400
    if not isinstance(set_index, int) or isinstance(set_index, bool) or not 0 <= set_index < 20:
        return jsonify({"error": "set_index muss eine Zahl von 0 bis 19 sein"}), 400
    row = SetLog.query.filter_by(day_date=day, exercise_name=exercise, set_index=set_index).first()
    if body.get("done", True) and row is None:
        db.session.add(SetLog(day_date=day, exercise_name=exercise, set_index=set_index))
    elif not body.get("done", True) and row is not None:
        db.session.delete(row)
    db.session.commit()
    return jsonify(sets_done(day)), 200
