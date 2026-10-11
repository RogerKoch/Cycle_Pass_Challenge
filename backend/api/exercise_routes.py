"""API-Endpunkte fuer den dauerhaften Tausch von Kraftuebungen."""

import logging

from flask import Blueprint, jsonify, request

from backend.engine.strength_alternatives import alternatives_for
from backend.extensions import db
from backend.models.exercise_swaps import ExerciseSwap, exercise_swaps

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
