"""API-Endpunkt zum Zuruecksetzen aller Nutzerdaten (Neustart der App)."""

import logging
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from backend.backup import DEFAULT_BACKUP_DIR, backup_database
from backend.extensions import db
from backend.models.baseline_measurements import BaselineMeasurement
from backend.models.checkins import Checkin
from backend.models.day_comments import DayComment
from backend.models.events import Event
from backend.models.exercise_swaps import ExerciseSwap
from backend.models.food import FoodLogEntry
from backend.models.ftp_tests import FtpTest
from backend.models.intake import IntakeDay
from backend.models.intervals import IcuActivity, IcuWellness, IntegrationState
from backend.models.plan_adjustments import PlanAdjustment, ReviewDecision
from backend.models.strength_benchmarks import StrengthBenchmark
from backend.models.training_days import TrainingDay
from backend.models.user_profile import UserProfile
from backend.models.wellbeing import WellbeingSignal

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")

RESET_CONFIRMATION = "ZURÜCKSETZEN"

# Reihenfolge beachtet die Fremdschluessel; `foods` und Mahlzeit-Vorlagen sind zwischen Instanzen geteilt
# (Schema `shared`) und bleiben bewusst erhalten
_RESET_ORDER = (
    FoodLogEntry, IntakeDay, IcuWellness, IcuActivity, IntegrationState,
    Checkin, BaselineMeasurement, WellbeingSignal, FtpTest, StrengthBenchmark, ExerciseSwap, Event,
    DayComment, PlanAdjustment, ReviewDecision, TrainingDay, UserProfile,
)


def _backup_before_reset() -> str | None:
    """Sichert die DB-Datei vor dem Loeschen; None bei In-Memory-DB (Tests)."""
    database = db.engine.url.database
    if not database or database == ":memory:":
        return None
    target_dir = Path(current_app.config.get("BACKUP_DIR", DEFAULT_BACKUP_DIR))
    return backup_database(Path(database), target_dir).name


@admin_bp.post("/reset")
def reset_all():
    """Loescht alle Nutzerdaten ausser Lebensmitteln, nach automatischem Backup.

    Body: {"confirm": "ZURÜCKSETZEN"}. Schlaegt das Backup fehl, wird nichts geloescht.
    """
    body = request.get_json(force=True, silent=True) or {}
    if body.get("confirm") != RESET_CONFIRMATION:
        return jsonify({"error": f"Bestätigung fehlt: '{RESET_CONFIRMATION}' eingeben"}), 400
    try:
        backup = _backup_before_reset()
    except OSError as exc:
        logger.exception("Backup vor Reset fehlgeschlagen")
        return jsonify({"error": f"Backup fehlgeschlagen, nichts gelöscht: {exc}"}), 500
    for model in _RESET_ORDER:
        db.session.query(model).delete()
    db.session.commit()
    logger.warning("App-Daten zurueckgesetzt (Backup: %s)", backup)
    return jsonify({"reset": True, "backup": backup}), 200
