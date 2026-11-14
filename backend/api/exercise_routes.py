"""API-Endpunkte fuer den dauerhaften Tausch von Kraftuebungen und das Abhaken von Saetzen."""

import json
import logging
from datetime import date
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_from_directory

from backend.config import REPO_ROOT
from backend.engine.strength_alternatives import alternatives_for
from backend.extensions import db
from backend.models.exercise_swaps import ExerciseSwap, exercise_swaps
from backend.models.set_logs import SetLog, sets_done

logger = logging.getLogger(__name__)

exercises_bp = Blueprint("exercises", __name__, url_prefix="/api/exercises")

REPO_ILLUSTRATIONS = REPO_ROOT / "frontend" / "training" / "img" / "exercises" / "index.json"
NEOLYMP_MANIFEST = REPO_ROOT / "backend" / "data" / "neolymp_exercises.json"
NEOLYMP_IMAGE_ROUTE = "../api/exercises/neolymp-image/"  # relativ zu <praefix>/training/


def _neolymp_dir() -> Path:
    """Ordner mit den NEOLYMP-Bildern; liegt nur auf dem Server (instance/), nicht im Git (© NEOLYMP)."""
    return Path(current_app.instance_path) / "neolymp"


def _read_json(path: Path) -> dict:
    """Liest eine JSON-Datei; fehlende oder defekte Datei = leeres Dict."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


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
    """Hebt den Tausch einer Uebung auf (zurueck zum Original)."""
    original = (request.get_json(force=True, silent=True) or {}).get("original")
    swap = ExerciseSwap.query.filter_by(original_name=original).first()
    if swap is not None:
        db.session.delete(swap)
        db.session.commit()
    return jsonify(exercise_swaps()), 200


@exercises_bp.get("/illustrations")
def list_illustrations():
    """Skizzen/Videos je Uebung: Repo-Index plus NEOLYMP-Uebungen (Bilder nur, wenn auf dem Server vorhanden)."""
    illustrations = _read_json(REPO_ILLUSTRATIONS)
    images = _read_json(_neolymp_dir() / "index.json")
    for name, entry in _read_json(NEOLYMP_MANIFEST).items():
        files = images.get(name, [])
        illustrations[name] = {"video": entry["video"]}
        if files:
            illustrations[name]["srcs"] = [NEOLYMP_IMAGE_ROUTE + file for file in files]
    return jsonify(illustrations), 200


@exercises_bp.get("/neolymp-image/<path:filename>")
def neolymp_image(filename: str):
    """Liefert ein NEOLYMP-Bild aus instance/neolymp/images (nur nach Login, 404 wenn nicht vorhanden)."""
    return send_from_directory(_neolymp_dir() / "images", filename)


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
