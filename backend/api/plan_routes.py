"""API-Endpunkt fuer das tagesaktuelle Rad-/Ernaehrungs-Ziel."""

import logging
from dataclasses import asdict, replace
from datetime import date, timedelta

from flask import Blueprint, jsonify, request

from backend.api.baseline_routes import resolve_baseline
from backend.api.calendar_routes import (
    _serialize_event,
    ensure_week,
    imported_day,
    peek_week,
    resolve_cycling,
    serialize_day,
    training_params,
)
from backend.engine.baseline import calculate_energy_availability
from backend.engine.cycling_zones import compute_cycling_zones
from backend.engine.event_prep import PHASE_EVENT, event_context, event_nutrition, strength_blocked
from backend.engine.nutrition_calc import (
    ACTIVITY_LEVELS,
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
from backend.models.events import event_spans
from backend.models.ftp_tests import FtpTest
from backend.models.food import FoodLogEntry
from backend.models.intake import IntakeDay
from backend.models.plan_adjustments import adjustment_spans
from backend.models.user_profile import UserProfile

logger = logging.getLogger(__name__)

plan_bp = Blueprint("plan", __name__, url_prefix="/api/plan")

MAX_OVERVIEW_DAYS = 62


class _PlanError(Exception):
    """Plan fuer den Tag nicht berechenbar (Meldung + HTTP-Status)."""

    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


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
    try:
        return jsonify(build_plan(date.today(), dict(request.args) or None)), 200
    except _PlanError as exc:
        return jsonify({"error": exc.message}), exc.status


@plan_bp.get("/days")
def get_days_overview():
    """Soll und Ist je Tag fuer einen Zeitraum (?from=YYYY-MM-DD&to=YYYY-MM-DD, hoechstens 62 Tage).

    Soll ist None, wenn fuer den Tag kein Ziel berechenbar ist (kein Profil/Check-in, vor Programmstart);
    Ist ist None ohne gegessene Zufuhr, planned ist None ohne vorgeplante Eintraege.
    """
    try:
        start = date.fromisoformat(request.args["from"])
        end = date.fromisoformat(request.args["to"])
    except (KeyError, ValueError):
        return jsonify({"error": "from und to erwartet (YYYY-MM-DD)"}), 400
    if end < start or (end - start).days >= MAX_OVERVIEW_DAYS:
        return jsonify({"error": f"Zeitraum muss 1 bis {MAX_OVERVIEW_DAYS} Tage umfassen"}), 400

    eaten = {
        d.intake_date: {"kcal": d.kcal, "protein_g": d.protein_g, "carbs_g": d.carbs_g, "fat_g": d.fat_g}
        for d in IntakeDay.query.filter(IntakeDay.intake_date >= start, IntakeDay.intake_date <= end).all()
    }
    planned: dict[date, dict] = {}
    for entry in FoodLogEntry.query.filter(
        FoodLogEntry.entry_date >= start, FoodLogEntry.entry_date <= end, FoodLogEntry.status == "planned"
    ).all():
        total = planned.setdefault(entry.entry_date, {"kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0})
        for key in total:
            total[key] += getattr(entry, key)
    days = []
    for offset in range((end - start).days + 1):
        current = start + timedelta(days=offset)
        try:
            plan = build_plan(current)
            target = {"kcal": plan["nutrition"]["target_kcal"], **{k: plan["macros"][k] for k in ("protein_g", "carbs_g", "fat_g")}}
        except _PlanError:
            target = None
        days.append({"date": current.isoformat(), "target": target, "eaten": eaten.get(current),
                     "planned": planned.get(current)})
    return jsonify({"from": start.isoformat(), "to": end.isoformat(), "days": days}), 200


@plan_bp.get("/<day>")
def get_day_plan(day: str):
    """Ziel eines beliebigen Tages (YYYY-MM-DD), Gewicht = neuester Check-in bis zu diesem Tag."""
    try:
        parsed = date.fromisoformat(day)
    except ValueError:
        return jsonify({"error": "ungueltiges Datum, erwartet YYYY-MM-DD"}), 400
    try:
        return jsonify(build_plan(parsed)), 200
    except _PlanError as exc:
        return jsonify({"error": exc.message}), exc.status


def build_plan(day: date, manual: dict | None = None) -> dict:
    """Rad-Zonen und Ernaehrungsziel fuer `day`.

    Args:
        day: Tag; fuer vergangene und kuenftige Tage wird nichts in die DB geschrieben.
        manual: manuelle Trainingsparameter (nur heute), siehe get_today_plan.

    Returns:
        Antwort-Dict wie /api/plan/today.

    Raises:
        _PlanError: Profil/Check-in fehlt, Tag vor Programmstart oder ungueltige Parameter.
    """
    profile = UserProfile.query.first()
    if profile is None:
        raise _PlanError("kein Profil vorhanden", 404)
    is_today = day == date.today()
    if day < profile.program_start_date and not is_today:
        raise _PlanError("vor Programmstart", 422)

    newest = Checkin.query.order_by(Checkin.checkin_date.desc(), Checkin.created_at.desc())
    checkin = newest.filter(Checkin.checkin_date <= day).first() or newest.first()
    if checkin is None:
        raise _PlanError("kein Check-in vorhanden, kcal-Ziel kann nicht berechnet werden", 422)

    ftp_test = FtpTest.query.order_by(FtpTest.test_date.desc(), FtpTest.created_at.desc()).first()

    training = None
    measured_cycling_kcal = None
    spans = adjustment_spans()
    events = event_spans()
    event_ctx = event_context(day, events)
    if manual:
        try:
            cycling_hours = float(manual["cycling_hours"])
            cycling_intensity = CyclingIntensity(manual["cycling_intensity"])
            strength_sessions = int(manual["strength_sessions"])
            day_type = DayType(manual["day_type"])
        except (KeyError, ValueError) as exc:
            raise _PlanError(f"ungueltige oder fehlende Query-Parameter: {exc}", 400) from exc
    else:
        week_rows = ensure_week(profile, day) if is_today else peek_week(profile, day)
        row = next(r for r in week_rows if r.day_date == day)
        today_phase, week = phase_week(profile.program_start_date, day)
        params = training_params(row, resolve_cycling(row, today_phase.phase_id, week, spans, events), imported_day(day, checkin.weight_kg))
        measured_cycling_kcal = params.cycling_kcal
        cycling_hours = params.cycling_minutes / 60
        # ohne Rad ist die Intensitaet fuer die kcal irrelevant (0 h)
        cycling_intensity = params.cycling_intensity or CyclingIntensity.LEICHT_REKOM
        strength_sessions = 0 if strength_blocked(event_ctx) else params.strength_sessions
        day_type = derive_day_type(params.cycling_minutes, params.cycling_intensity, strength_sessions)
        training = serialize_day(row, profile, week_rows, ftp_test.ftp_watts if ftp_test else None, spans=spans, events=events)

    if event_ctx is not None and event_ctx.phase == PHASE_EVENT:
        day_type = DayType.LANGER_HARTER_TAG
    phase = get_current_phase(profile.program_start_date, day)
    zones = compute_cycling_zones(ftp_test.ftp_watts if ftp_test else None)

    baseline = resolve_baseline(profile, checkin)
    rmr, ffm = baseline["rmr_kcal"][0], baseline["ffm_kg"][0]
    event_nut = event_nutrition(event_ctx, checkin.weight_kg) if event_ctx is not None else None
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
            deficit_kcal=effective_deficit(day, phase.phase_id, spans) * (event_nut.deficit_factor if event_nut else 1.0),
            cycling_kcal=measured_cycling_kcal,
            non_exercise_factor=ACTIVITY_LEVELS[profile.activity_level][1],
        )
    except ValueError as exc:
        raise _PlanError(f"ungueltige Trainingsparameter: {exc}", 400) from exc

    macros = calculate_macro_targets(
        weight_kg=checkin.weight_kg,
        ffm_kg=ffm.value,
        day_type=day_type,
        target_kcal=nutrition.target_kcal,
        carbs_g_per_kg=event_nut.carbs_g_per_kg if event_nut else None,
        fat_g_per_kg=event_nut.fat_g_per_kg if event_nut else None,
    )
    if event_nut is not None and event_nut.carbs_g_per_kg is not None:
        # Carb-Loading: das kcal-Ziel folgt den Makros (sonst passen 9-10 g/kg KH nicht ins Tagesziel)
        macro_kcal = (macros.protein_g + macros.carbs_g) * 4 + macros.fat_g * 9
        nutrition = replace(nutrition, target_kcal=max(nutrition.target_kcal, macro_kcal))

    fueling = intra_fueling(cycling_hours * 60, cycling_intensity)
    # Training nach der Arbeit: Post-Workout-Mahlzeit ist das Abendessen (nur an Tagen mit Training)
    evening_days = {int(d) for d in profile.evening_training_days.split(",") if d}
    evening = day.weekday() in evening_days and (cycling_hours > 0 or strength_sessions > 0)
    intake_today = IntakeDay.query.filter_by(intake_date=day).first()
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

    return {
        "date": day.isoformat(),
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
        "meals": [asdict(m) for m in distribute_meals(nutrition.target_kcal, macros.protein_g, evening)],
        "fueling": asdict(fueling) if fueling else None,
        "timing_hints": [
            *(event_nut.hints if event_nut else []),
            *nutrition_timing_hints(cycling_hours > 0, strength_sessions > 0, checkin.weight_kg, evening),
        ],
        "event": _serialize_event(event_ctx),
        "training": training,
        "adjustments": sorted(active_kinds(day, spans)),
        "targets_source": targets_source,
        "intake": intake,
    }
