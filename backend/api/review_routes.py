"""API-Endpunkte fuer Fragebogen, Check-in-Review und Plan-Anpassungen."""

import logging
from dataclasses import asdict
from datetime import date, timedelta

from flask import Blueprint, jsonify, request

from backend.api.baseline_routes import resolve_baseline
from backend.api.calendar_routes import ensure_week, imported_day, resolve_cycling, training_params
from backend.engine.baseline import calculate_energy_availability, calculate_target_weight_kg
from backend.engine.checkin_triggers import (
    LOSS_TREND_WINDOW_DAYS,
    CheckinPoint,
    EaDay,
    Finding,
    FtpPoint,
    SignalPoint,
    TriggerInputs,
    WellnessPoint,
    average_energy_availability,
    deficit_streak_start,
    evaluate,
    weight_trend,
)
from backend.engine.cycling_sessions import SLOT_FTP_TEST
from backend.engine.nutrition_calc import calculate_cycling_kcal, calculate_strength_kcal
from backend.engine.plan_adjustments import AdjustmentSpan, active_kinds, effective_deficit
from backend.engine.week_plan import STATUS_SKIPPED, phase_week
from backend.extensions import db
from backend.models.checkins import Checkin
from backend.models.ftp_tests import FtpTest
from backend.models.intake import IntakeDay
from backend.models.intervals import IcuWellness
from backend.models.plan_adjustments import PlanAdjustment, ReviewDecision, adjustment_spans
from backend.models.strength_benchmarks import StrengthBenchmark
from backend.models.training_days import TrainingDay
from backend.models.user_profile import UserProfile
from backend.models.wellbeing import WellbeingSignal

logger = logging.getLogger(__name__)

review_bp = Blueprint("review", __name__, url_prefix="/api")

SIGNAL_FIELDS: tuple[str, ...] = ("sleep", "legs", "hunger", "back", "effort")
RESTING_HR_RANGE = (30, 120)
MAX_NOTE_LENGTH = 200
EA_LOOKBACK_DAYS = 8
WELLNESS_WINDOW_DAYS = 31  # 3 aktuelle + 28 Basistage
DECISIONS = ("accepted", "dismissed")


def _serialize_signal(signal: WellbeingSignal) -> dict:
    return {
        "date": signal.signal_date.isoformat(),
        **{name: getattr(signal, name) for name in SIGNAL_FIELDS},
        "resting_hr": signal.resting_hr,
        "note": signal.note,
    }


def _serialize_adjustment(adjustment: PlanAdjustment, today: date) -> dict:
    return {
        "id": adjustment.id,
        "kind": adjustment.kind,
        "label": adjustment.label,
        "start_date": adjustment.start_date.isoformat(),
        "end_date": adjustment.end_date.isoformat() if adjustment.end_date else None,
        "value": adjustment.value,
        "active": adjustment.to_span().covers(today),
    }


@review_bp.get("/signals")
def list_signals():
    """Frageboegen, neueste zuerst."""
    signals = WellbeingSignal.query.order_by(WellbeingSignal.signal_date.desc()).all()
    return jsonify([_serialize_signal(s) for s in signals]), 200


@review_bp.post("/signals")
def upsert_signals():
    """Erfasst den Fragebogen eines Tages (ueberschreibt einen bestehenden desselben Datums)."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "JSON-Objekt erwartet"}), 400
    values = {}
    for name in SIGNAL_FIELDS:
        value = payload.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 3:
            return jsonify({"error": f"{name} muss eine ganze Zahl 0–3 sein"}), 400
        values[name] = value
    resting_hr = payload.get("resting_hr")
    if resting_hr is not None and (
        isinstance(resting_hr, bool)
        or not isinstance(resting_hr, int)
        or not RESTING_HR_RANGE[0] <= resting_hr <= RESTING_HR_RANGE[1]
    ):
        return jsonify({"error": f"resting_hr muss zwischen {RESTING_HR_RANGE[0]} und {RESTING_HR_RANGE[1]} liegen"}), 400
    note = payload.get("note")
    if note is not None and (not isinstance(note, str) or len(note) > MAX_NOTE_LENGTH):
        return jsonify({"error": f"note: Text mit max. {MAX_NOTE_LENGTH} Zeichen"}), 400
    try:
        signal_date = date.fromisoformat(payload["date"]) if payload.get("date") else date.today()
    except (TypeError, ValueError):
        return jsonify({"error": "date muss YYYY-MM-DD sein"}), 400
    if signal_date > date.today():
        return jsonify({"error": "Fragebogen nicht für künftige Tage"}), 400

    signal = WellbeingSignal.query.filter_by(signal_date=signal_date).first()
    created = signal is None
    if created:
        signal = WellbeingSignal(signal_date=signal_date)
        db.session.add(signal)
    for name, value in values.items():
        setattr(signal, name, value)
    signal.resting_hr, signal.note = resting_hr, note
    db.session.commit()
    return jsonify(_serialize_signal(signal)), 201 if created else 200


def _ea_days(profile: UserProfile, checkin: Checkin, ffm_kg: float, spans: list[AdjustmentSpan], today: date) -> list[EaDay]:
    """EA der letzten Tage aus Ist-Zufuhr und Trainings-kcal laut Kalender (Ist vor geplant)."""
    start = today - timedelta(days=EA_LOOKBACK_DAYS)
    intake_days = IntakeDay.query.filter(IntakeDay.intake_date >= start, IntakeDay.intake_date < today).all()
    rows: dict[date, TrainingDay] = {}
    result = []
    for intake in intake_days:
        if intake.intake_date not in rows:
            rows.update({r.day_date: r for r in ensure_week(profile, intake.intake_date)})
        row = rows[intake.intake_date]
        phase, week = phase_week(profile.program_start_date, row.day_date)
        params = training_params(row, resolve_cycling(row, phase.phase_id, week, spans), imported_day(row.day_date, checkin.weight_kg))
        if params.cycling_kcal is not None:
            cycling = params.cycling_kcal
        elif params.cycling_intensity:
            cycling = calculate_cycling_kcal(params.cycling_minutes / 60, params.cycling_intensity, checkin.weight_kg)
        else:
            cycling = 0.0
        training_kcal = cycling + calculate_strength_kcal(params.strength_sessions)
        result.append(EaDay(intake.intake_date, calculate_energy_availability(intake.kcal, training_kcal, ffm_kg)))
    return result


def _review_state(profile: UserProfile, today: date) -> tuple[list[Finding], dict]:
    """Befunde (ohne bereits entschiedene) und Kennzahlen fuer das Review."""
    spans = adjustment_spans()
    checkins = Checkin.query.all()
    latest = max(checkins, key=lambda c: (c.checkin_date, c.created_at)) if checkins else None
    ftp_tests = FtpTest.query.all()

    def deficit_on(day: date) -> float:
        return effective_deficit(day, phase_week(profile.program_start_date, day)[0].phase_id, spans)

    ea_days: list[EaDay] = []
    target_weight = None
    if latest is not None:
        baseline = resolve_baseline(profile, latest)
        ffm, target_bf = baseline["ffm_kg"][0].value, baseline["target_bodyfat_pct"][0].value
        target_weight = calculate_target_weight_kg(ffm, target_bf)
        ea_days = _ea_days(profile, latest, ffm, spans, today)

    planned_tests = TrainingDay.query.filter(
        TrainingDay.cycling_slot == SLOT_FTP_TEST,
        TrainingDay.day_date < today,
        TrainingDay.status != STATUS_SKIPPED,
    ).all()
    inputs = TriggerInputs(
        today=today,
        checkins=[CheckinPoint(c.checkin_date, c.weight_kg) for c in checkins],
        ftp_tests=[FtpPoint(t.id, t.test_date, t.ftp_watts) for t in ftp_tests],
        signals=[
            SignalPoint(s.signal_date, s.sleep, s.legs, s.hunger, s.back, s.effort, s.resting_hr)
            for s in WellbeingSignal.query.all()
        ],
        ea_days=ea_days,
        deficit_active_today=deficit_on(today) > 0,
        deficit_streak_start=deficit_streak_start(today, lambda d: deficit_on(d) > 0),
        target_weight_kg=target_weight,
        planned_ftp_tests=[r.day_date for r in planned_tests],
        wellness=[
            WellnessPoint(w.day, w.resting_hr, w.hrv)
            for w in IcuWellness.query.filter(IcuWellness.day >= today - timedelta(days=WELLNESS_WINDOW_DAYS)).all()
        ],
        last_strength_benchmark=db.session.query(db.func.max(StrengthBenchmark.test_date)).scalar(),
        benchmark_interval_weeks=profile.benchmark_interval_weeks,
    )
    decided = {d.finding_key for d in ReviewDecision.query.all()}
    findings = [f for f in evaluate(inputs) if f.key not in decided]

    trend = weight_trend(inputs.checkins, today, LOSS_TREND_WINDOW_DAYS)
    latest_ftp = max(ftp_tests, key=lambda t: (t.test_date, t.created_at)) if ftp_tests else None
    ea = average_energy_availability(ea_days, today)
    summary = {
        "weight_kg": latest.weight_kg if latest else None,
        "target_weight_kg": target_weight,
        "trend_kg_per_week": trend.kg_per_week if trend else None,
        "trend_pct_per_week": trend.pct_per_week if trend else None,
        "ftp_watts": latest_ftp.ftp_watts if latest_ftp else None,
        "watts_per_kg": latest_ftp.ftp_watts / latest.weight_kg if latest_ftp and latest else None,
        "deficit_kcal": deficit_on(today),
        "energy_availability_avg": ea[0] if ea else None,
        "active_adjustments": sorted(active_kinds(today, spans)),
    }
    return findings, summary


def _serialize_finding(finding: Finding) -> dict:
    result = asdict(finding)
    result["action"] = asdict(finding.action) if finding.action else None
    return result


@review_bp.get("/review")
def get_review():
    """Kennzahlen, offene Befunde und Anpassungen fuer das Check-in-Review."""
    profile = UserProfile.query.first()
    if profile is None:
        return jsonify({"error": "kein Profil vorhanden"}), 404
    today = date.today()
    findings, summary = _review_state(profile, today)
    adjustments = PlanAdjustment.query.order_by(PlanAdjustment.start_date.desc()).all()
    return jsonify({
        "date": today.isoformat(),
        "summary": summary,
        "findings": [_serialize_finding(f) for f in findings],
        "adjustments": [_serialize_adjustment(a, today) for a in adjustments],
    }), 200


@review_bp.post("/review/decisions")
def decide_finding():
    """Uebernimmt oder verwirft einen offenen Befund. Uebernehmen legt dessen Anpassung ab heute an."""
    profile = UserProfile.query.first()
    if profile is None:
        return jsonify({"error": "kein Profil vorhanden"}), 404
    payload = request.get_json(silent=True) or {}
    key, decision = payload.get("key"), payload.get("decision")
    if not isinstance(key, str) or decision not in DECISIONS:
        return jsonify({"error": "key und decision (accepted|dismissed) erforderlich"}), 400
    today = date.today()
    findings, _ = _review_state(profile, today)
    finding = next((f for f in findings if f.key == key), None)
    if finding is None:
        return jsonify({"error": "kein offener Befund mit diesem key"}), 404

    adjustment = None
    if decision == "accepted" and finding.action is not None:
        action = finding.action
        adjustment = PlanAdjustment(
            kind=action.kind,
            start_date=today,
            end_date=today + timedelta(days=action.days - 1) if action.days else None,
            value=action.value,
            label=action.label,
            finding_key=key,
        )
        db.session.add(adjustment)
    db.session.add(ReviewDecision(finding_key=key, decision=decision))
    db.session.commit()
    return jsonify({
        "key": key,
        "decision": decision,
        "adjustment": _serialize_adjustment(adjustment, today) if adjustment else None,
    }), 201


@review_bp.get("/adjustments")
def list_adjustments():
    """Alle Anpassungen, neueste zuerst, mit Flag `active` fuer heute."""
    today = date.today()
    adjustments = PlanAdjustment.query.order_by(PlanAdjustment.start_date.desc()).all()
    return jsonify([_serialize_adjustment(a, today) for a in adjustments]), 200


@review_bp.delete("/adjustments/<int:adjustment_id>")
def delete_adjustment(adjustment_id: int):
    """Nimmt eine Anpassung zurueck; der zugehoerige Befund wird wieder offen, falls er noch zutrifft."""
    adjustment = db.session.get(PlanAdjustment, adjustment_id)
    if adjustment is None:
        return jsonify({"error": "Anpassung nicht gefunden"}), 404
    if adjustment.finding_key:
        ReviewDecision.query.filter_by(finding_key=adjustment.finding_key).delete()
    db.session.delete(adjustment)
    db.session.commit()
    return "", 204
