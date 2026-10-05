"""API-Endpunkt fuer das tagesaktuelle Rad-/Ernaehrungs-Ziel."""

import logging
from dataclasses import asdict
from datetime import date

from flask import Blueprint, jsonify, request

from backend.api.baseline_routes import resolve_baseline
from backend.api.calendar_routes import ensure_week, imported_day, resolve_cycling, serialize_day, training_params
from backend.engine.baseline import calculate_energy_availability
from backend.engine.cycling_zones import compute_cycling_zones
from backend.engine.nutrition_calc import (
    CyclingIntensity,
    DayType,
    calculate_daily_kcal_target,
    calculate_macro_targets,
    derive_day_type,
    distribute_meals,
    intra_fueling,
    nutrition_timing_hints,
)
from backend.engine.plan_adjustments import active_kinds, effective_deficit
from backend.engine.training_phase import get_current_phase
from backend.engine.week_plan import phase_week
from backend.models.checkins import Checkin
from backend.models.ftp_tests import FtpTest
from backend.models.intake import IntakeDay
from backend.models.plan_adjustments import adjustment_spans
from backend.models.user_profile import UserProfile

logger = logging.getLogger(__name__)

plan_bp = Blueprint("plan", __name__, url_prefix="/api/plan")


@plan_bp.get("/today")
def get_today_plan():
    """Berechnet Rad-Zonen und Ernaehrungsziel fuer heute.

    Ohne Query-Parameter kommen die Trainingsparameter aus dem Trainingskalender (geplant bzw.
    Ist-Werte der Rueckmeldung) und die Antwort enthaelt den aufgeloesten Tag unter `training`.
    Mit Query-Parametern (dann alle Pflicht) gilt die manuelle Eingabe:
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

    today = date.today()
    training = None
    measured_cycling_kcal = None
    spans = adjustment_spans()
    if request.args:
        try:
            cycling_hours = float(request.args["cycling_hours"])
            cycling_intensity = CyclingIntensity(request.args["cycling_intensity"])
            strength_sessions = int(request.args["strength_sessions"])
            day_type = DayType(request.args["day_type"])
        except (KeyError, ValueError) as exc:
            return jsonify({"error": f"ungueltige oder fehlende Query-Parameter: {exc}"}), 400
    else:
        week_rows = ensure_week(profile, today)
        row = next(r for r in week_rows if r.day_date == today)
        today_phase, week = phase_week(profile.program_start_date, today)
        params = training_params(row, resolve_cycling(row, today_phase.phase_id, week, spans), imported_day(today))
        measured_cycling_kcal = params.cycling_kcal
        cycling_hours = params.cycling_minutes / 60
        # ohne Rad ist die Intensitaet fuer die kcal irrelevant (0 h)
        cycling_intensity = params.cycling_intensity or CyclingIntensity.LEICHT_REKOM
        strength_sessions = params.strength_sessions
        day_type = derive_day_type(params.cycling_minutes, params.cycling_intensity, strength_sessions)
        training = serialize_day(row, profile, week_rows, ftp_test.ftp_watts if ftp_test else None, spans=spans)

    phase = get_current_phase(profile.program_start_date, today)
    zones = compute_cycling_zones(ftp_test.ftp_watts if ftp_test else None)

    baseline = resolve_baseline(profile, checkin)
    rmr, ffm = baseline["rmr_kcal"][0], baseline["ffm_kg"][0]
    targets_source = "measured" if "measured" in (rmr.source, ffm.source) else "estimated"

    try:
        nutrition = calculate_daily_kcal_target(
            weight_kg=checkin.weight_kg,
            height_cm=profile.height_cm,
            age=profile.age,
            phase_id=phase.phase_id,
            cycling_hours=cycling_hours,
            cycling_intensity=cycling_intensity,
            strength_sessions=strength_sessions,
            rmr_kcal=rmr.value,
            deficit_kcal=effective_deficit(today, phase.phase_id, spans),
            cycling_kcal=measured_cycling_kcal,
        )
    except ValueError as exc:
        return jsonify({"error": f"ungueltige Trainingsparameter: {exc}"}), 400

    macros = calculate_macro_targets(
        weight_kg=checkin.weight_kg, ffm_kg=ffm.value, day_type=day_type, target_kcal=nutrition.target_kcal
    )

    fueling = intra_fueling(cycling_hours * 60, cycling_intensity)
    intake_today = IntakeDay.query.filter_by(intake_date=today).first()
    intake = None
    if intake_today is not None:
        intake = {
            "kcal": intake_today.kcal,
            "protein_g": intake_today.protein_g,
            "carbs_g": intake_today.carbs_g,
            "fat_g": intake_today.fat_g,
            "energy_availability": calculate_energy_availability(
                intake_today.kcal, nutrition.cycling_kcal + nutrition.strength_kcal, ffm.value
            ),
        }

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
            "day_type": day_type.value,
            "meals": [asdict(m) for m in distribute_meals(nutrition.target_kcal, macros.protein_g)],
            "fueling": asdict(fueling) if fueling else None,
            "timing_hints": nutrition_timing_hints(cycling_hours > 0, strength_sessions > 0, checkin.weight_kg),
            "training": training,
            "adjustments": sorted(active_kinds(today, spans)),
            "targets_source": targets_source,
            "intake": intake,
        }
    ), 200
