"""API-Endpunkt fuer das tagesaktuelle Rad-/Ernaehrungs-Ziel."""

import logging
from dataclasses import asdict
from datetime import date

from flask import Blueprint, jsonify, request

from backend.engine.cycling_zones import compute_cycling_zones
from backend.engine.nutrition_calc import CyclingIntensity, DayType, calculate_daily_kcal_target, calculate_macro_targets
from backend.engine.training_phase import get_current_phase
from backend.models.checkins import Checkin
from backend.models.ftp_tests import FtpTest
from backend.models.user_profile import UserProfile

logger = logging.getLogger(__name__)

plan_bp = Blueprint("plan", __name__, url_prefix="/api/plan")


@plan_bp.get("/today")
def get_today_plan():
    """Berechnet Rad-Zonen und Ernaehrungsziel fuer heute.

    Query-Parameter (alle Pflicht ausser anders vermerkt):
        cycling_hours: geplante Radzeit heute (float, z.B. "1.5").
        cycling_intensity: eine von CyclingIntensity.
        strength_sessions: Anzahl Krafteinheiten heute (int).
        day_type: eine von DayType (fuer die Makro-Periodisierung).
    """
    profile = UserProfile.query.first()
    if profile is None:
        return jsonify({"error": "kein Profil vorhanden"}), 404

    checkin = Checkin.query.order_by(Checkin.checkin_date.desc(), Checkin.created_at.desc()).first()
    if checkin is None:
        return jsonify({"error": "kein Check-in vorhanden, kcal-Ziel kann nicht berechnet werden"}), 422

    ftp_test = FtpTest.query.order_by(FtpTest.test_date.desc(), FtpTest.created_at.desc()).first()

    try:
        cycling_hours = float(request.args["cycling_hours"])
        cycling_intensity = CyclingIntensity(request.args["cycling_intensity"])
        strength_sessions = int(request.args["strength_sessions"])
        day_type = DayType(request.args["day_type"])
    except (KeyError, ValueError) as exc:
        return jsonify({"error": f"ungueltige oder fehlende Query-Parameter: {exc}"}), 400

    today = date.today()
    phase = get_current_phase(profile.program_start_date, today)
    zones = compute_cycling_zones(ftp_test.ftp_watts if ftp_test else None)

    try:
        nutrition = calculate_daily_kcal_target(
            weight_kg=checkin.weight_kg,
            height_cm=profile.height_cm,
            age=profile.age,
            phase_id=phase.phase_id,
            cycling_hours=cycling_hours,
            cycling_intensity=cycling_intensity,
            strength_sessions=strength_sessions,
        )
    except ValueError as exc:
        return jsonify({"error": f"ungueltige Trainingsparameter: {exc}"}), 400

    macros = calculate_macro_targets(
        weight_kg=checkin.weight_kg, ffm_kg=checkin.ffm_kg, day_type=day_type, target_kcal=nutrition.target_kcal
    )

    return jsonify(
        {
            "date": today.isoformat(),
            "phase": {
                "phase_id": phase.phase_id,
                "phase_start": phase.phase_start.isoformat(),
                "phase_end": phase.phase_end.isoformat() if phase.phase_end else None,
                "day_in_phase": phase.day_in_phase,
            },
            "zones": {
                "available": zones.available,
                "ftp_watts": zones.ftp_watts,
                "message": zones.message,
                "zones": [asdict(z) for z in zones.zones] if zones.zones else None,
            },
            "nutrition": asdict(nutrition),
            "macros": asdict(macros),
        }
    ), 200
