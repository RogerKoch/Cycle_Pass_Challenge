"""API-Endpunkte fuer den Trainingskalender (Woche, Tag, Tauschen, Anpassen, Rueckmeldung)."""

import logging
import math
from dataclasses import asdict, dataclass
from datetime import date, timedelta

from flask import Blueprint, jsonify, request

from backend.engine.cycling_sessions import (
    ALL_SLOTS,
    ENDURANCE_SLOTS,
    CyclingSession,
    adjust_duration,
    build_cycling_session,
    is_deload_week,
    session_watts,
)
from backend.engine.nutrition_calc import CyclingIntensity
from backend.engine.strength_sessions import MOBILITY_ROUTINE
from backend.engine.week_plan import (
    STATUS_DONE,
    STATUS_MODIFIED,
    STATUS_PLANNED,
    STATUS_SKIPPED,
    STATUSES,
    DayPlan,
    default_day_plan,
    has_blocking,
    phase_week,
    resolve_strength,
    suggest_reschedule,
    swap_plans,
    validate_week,
    week_start,
)
from backend.extensions import db
from backend.models.ftp_tests import FtpTest
from backend.models.training_days import TrainingDay
from backend.models.user_profile import UserProfile

logger = logging.getLogger(__name__)

calendar_bp = Blueprint("calendar", __name__, url_prefix="/api/calendar")

MAX_PLANNED_MINUTES = 600
MAX_NOTE_LENGTH = 200
SWAPPABLE_STATUSES = frozenset({STATUS_PLANNED, STATUS_SKIPPED})


@dataclass
class TrainingParams:
    """Trainingsparameter eines Tages fuer die Ernaehrungsberechnung (geplant oder Ist)."""

    cycling_minutes: float
    cycling_intensity: CyclingIntensity | None
    strength_sessions: int


def ensure_week(profile: UserProfile, day: date) -> list[TrainingDay]:
    """Liefert die 7 Tage der Woche von `day`; fehlende Tage werden aus der Standardwoche angelegt.

    Args:
        profile: Nutzerprofil (Programmstart).
        day: beliebiges Datum der Woche.

    Returns:
        TrainingDay-Zeilen Montag bis Sonntag.
    """
    monday = week_start(day)
    sunday = monday + timedelta(days=6)
    rows = {
        r.day_date: r
        for r in TrainingDay.query.filter(TrainingDay.day_date >= monday, TrainingDay.day_date <= sunday).all()
    }
    created = False
    for offset in range(7):
        current = monday + timedelta(days=offset)
        if current not in rows:
            slot, strength = default_day_plan(profile.program_start_date, current)
            rows[current] = TrainingDay(day_date=current, cycling_slot=slot, strength_session=strength)
            db.session.add(rows[current])
            created = True
    if created:
        db.session.commit()
    return [rows[monday + timedelta(days=offset)] for offset in range(7)]


def _day_plan(row: TrainingDay) -> DayPlan:
    return DayPlan(row.day_date, row.cycling_slot, row.strength_session, row.status)


def resolve_cycling(row: TrainingDay, phase_id: str, week: int) -> CyclingSession | None:
    """Rad-Einheit eines Kalendertags inklusive Dauer-Override."""
    if row.cycling_slot is None:
        return None
    session = build_cycling_session(row.cycling_slot, phase_id, week)
    if session is not None and row.planned_minutes is not None:
        session = adjust_duration(session, row.planned_minutes)
    return session


def training_params(row: TrainingDay, session: CyclingSession | None) -> TrainingParams:
    """Parameter fuer die kcal-Berechnung: Ist-Werte bei done/modified, 0 bei skipped, sonst geplant."""
    planned_strength = 1 if row.strength_session else 0
    if row.status == STATUS_SKIPPED:
        return TrainingParams(0.0, None, 0)
    if row.status in (STATUS_DONE, STATUS_MODIFIED):
        minutes = row.actual_minutes if row.actual_minutes is not None else (session.minutes if session else 0.0)
        if row.actual_intensity is not None:
            intensity = CyclingIntensity(row.actual_intensity)
        else:
            intensity = session.intensity if session else (CyclingIntensity.MODERAT_BASE if minutes else None)
        strength = planned_strength if row.actual_strength_done is None else int(row.actual_strength_done)
        return TrainingParams(minutes, intensity if minutes else None, strength)
    if session is None:
        return TrainingParams(0.0, None, planned_strength)
    return TrainingParams(session.minutes, session.intensity, planned_strength)


def _latest_ftp() -> int | None:
    ftp_test = FtpTest.query.order_by(FtpTest.test_date.desc(), FtpTest.created_at.desc()).first()
    return ftp_test.ftp_watts if ftp_test else None


def _serialize_cycling(session: CyclingSession, ftp_watts: int | None) -> dict:
    watts = session_watts(session, ftp_watts)
    return {
        "slot": session.slot,
        "title": session.title,
        "minutes": session.minutes,
        "intensity": session.intensity.value,
        "is_key": session.is_key,
        "adjustable": session.slot in ENDURANCE_SLOTS,
        "adjusted": session.adjusted,
        "zwift_hint": session.zwift_hint,
        "note": session.note,
        "ftp_watts": watts.ftp_watts,
        "message": watts.message,
        "segments": [asdict(s) for s in watts.segments],
    }


def _slot_options(phase_id: str, week: int) -> list[dict]:
    options, seen = [], set()
    for slot in ALL_SLOTS:
        session = build_cycling_session(slot, phase_id, week)
        if session is None or (session.title, session.minutes) in seen:
            continue
        seen.add((session.title, session.minutes))
        options.append(
            {"slot": slot, "title": session.title, "minutes": session.minutes, "adjustable": slot in ENDURANCE_SLOTS}
        )
    return options


def serialize_day(
    row: TrainingDay, profile: UserProfile, week_rows: list[TrainingDay], ftp_watts: int | None, full: bool = True
) -> dict:
    """Kalendertag als JSON; `full` ergaenzt Mobility, Slot-Auswahl und Ersatztage."""
    phase, week = phase_week(profile.program_start_date, row.day_date)
    started = row.day_date >= profile.program_start_date
    session = resolve_cycling(row, phase.phase_id, week)
    strength = resolve_strength(row.strength_session, phase.phase_id, week) if row.strength_session else None
    week_plans = [_day_plan(r) for r in week_rows]
    result = {
        "date": row.day_date.isoformat(),
        "status": row.status,
        "note": row.note,
        "started": started,
        "phase": {"phase_id": phase.phase_id, "week_in_phase": week, "deload": is_deload_week(phase.phase_id, week)},
        "cycling": _serialize_cycling(session, ftp_watts) if session else None,
        "strength": asdict(strength) if strength else None,
        "actual": {
            "minutes": row.actual_minutes,
            "intensity": row.actual_intensity,
            "strength_done": row.actual_strength_done,
        },
        "warnings": [
            {"message": v.message, "blocking": v.blocking} for v in validate_week(week_plans) if v.day == row.day_date
        ],
    }
    if full:
        result["mobility"] = [asdict(e) for e in MOBILITY_ROUTINE]
        result["slot_options"] = _slot_options(phase.phase_id, week) if started else []
        result["reschedule_options"] = (
            [d.isoformat() for d in suggest_reschedule(week_plans, row.day_date, date.today())]
            if row.status == STATUS_SKIPPED
            else []
        )
    return result


def _serialize_week(profile: UserProfile, rows: list[TrainingDay]) -> dict:
    ftp_watts = _latest_ftp()
    return {
        "week_start": rows[0].day_date.isoformat(),
        "days": [serialize_day(r, profile, rows, ftp_watts, full=False) for r in rows],
    }


def _serialize_single(profile: UserProfile, day: date) -> dict:
    rows = ensure_week(profile, day)
    row = next(r for r in rows if r.day_date == day)
    return serialize_day(row, profile, rows, _latest_ftp())


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _profile_or_error():
    profile = UserProfile.query.first()
    if profile is None:
        return None, (jsonify({"error": "kein Profil vorhanden"}), 404)
    return profile, None


def _violation_response(violations) -> tuple:
    blocking = [v.message for v in violations if v.blocking]
    return jsonify({"error": "Regelverstoss: " + " ".join(blocking), "violations": blocking}), 409


@calendar_bp.get("/week/<day>")
def get_week(day: str):
    """Woche (Mo–So) des Datums; fehlende Tage werden aus der Standardwoche erzeugt."""
    profile, error = _profile_or_error()
    if error:
        return error
    try:
        parsed = _parse_date(day)
    except ValueError:
        return jsonify({"error": "ungueltiges Datum, erwartet YYYY-MM-DD"}), 400
    return jsonify(_serialize_week(profile, ensure_week(profile, parsed))), 200


@calendar_bp.get("/day/<day>")
def get_day(day: str):
    """Ein Tag voll aufgeloest: Rad mit Watt, Kraft, Mobility, Hinweise, Auswahl fuer Anpassungen."""
    profile, error = _profile_or_error()
    if error:
        return error
    try:
        parsed = _parse_date(day)
    except ValueError:
        return jsonify({"error": "ungueltiges Datum, erwartet YYYY-MM-DD"}), 400
    return jsonify(_serialize_single(profile, parsed)), 200


@calendar_bp.post("/swap")
def swap_days():
    """Tauscht die geplanten Inhalte zweier Tage derselben Woche (Status bleibt beim Datum)."""
    profile, error = _profile_or_error()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    try:
        day_a, day_b = _parse_date(payload["date_a"]), _parse_date(payload["date_b"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "date_a und date_b (YYYY-MM-DD) erforderlich"}), 400
    if day_a == day_b or week_start(day_a) != week_start(day_b):
        return jsonify({"error": "nur zwei verschiedene Tage derselben Woche tauschbar"}), 400
    if min(day_a, day_b) < date.today():
        return jsonify({"error": "vergangene Tage können nicht getauscht werden"}), 400

    rows = ensure_week(profile, day_a)
    by_day = {r.day_date: r for r in rows}
    a, b = by_day[day_a], by_day[day_b]
    if a.status not in SWAPPABLE_STATUSES or b.status not in SWAPPABLE_STATUSES:
        return jsonify({"error": "erledigte Tage können nicht getauscht werden"}), 409
    violations = validate_week(swap_plans([_day_plan(r) for r in rows], day_a, day_b))
    if has_blocking(violations):
        return _violation_response(violations)

    for field in ("cycling_slot", "planned_minutes", "strength_session"):
        value_a, value_b = getattr(a, field), getattr(b, field)
        setattr(a, field, value_b)
        setattr(b, field, value_a)
    db.session.commit()
    return jsonify(_serialize_week(profile, rows)), 200


@calendar_bp.put("/day/<day>/plan")
def update_day_plan(day: str):
    """Passt die geplante Einheit an: Rad-Slot, Dauer (nur Ausdauerfahrten), Krafteinheit."""
    profile, error = _profile_or_error()
    if error:
        return error
    try:
        parsed = _parse_date(day)
    except ValueError:
        return jsonify({"error": "ungueltiges Datum, erwartet YYYY-MM-DD"}), 400
    if parsed < date.today() or parsed < profile.program_start_date:
        return jsonify({"error": "nur heutige und künftige Tage ab Programmstart anpassbar"}), 400
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "JSON-Objekt erwartet"}), 400

    rows = ensure_week(profile, parsed)
    row = next(r for r in rows if r.day_date == parsed)
    if row.status != STATUS_PLANNED:
        return jsonify({"error": "nur geplante Tage anpassbar (Absage zuerst rückgängig machen)"}), 409

    phase, week = phase_week(profile.program_start_date, parsed)
    slot = payload.get("cycling_slot", row.cycling_slot)
    if slot is not None and (slot not in ALL_SLOTS or build_cycling_session(slot, phase.phase_id, week) is None):
        return jsonify({"error": f"Einheit '{slot}' gibt es in dieser Phase nicht"}), 400
    if "planned_minutes" in payload:
        minutes = payload["planned_minutes"]
    else:
        minutes = row.planned_minutes if slot == row.cycling_slot else None
    if minutes is not None:
        if slot not in ENDURANCE_SLOTS:
            return jsonify({"error": "Dauer nur bei Ausdauerfahrten (Grundlage, lang, Rekom) anpassbar"}), 400
        if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or not math.isfinite(minutes):
            return jsonify({"error": "planned_minutes muss eine Zahl sein"}), 400
        if not 0 < minutes <= MAX_PLANNED_MINUTES:
            return jsonify({"error": f"planned_minutes muss zwischen 1 und {MAX_PLANNED_MINUTES} liegen"}), 400
    strength = payload.get("strength_session", row.strength_session)
    if strength not in (None, "A", "B"):
        return jsonify({"error": "strength_session muss 'A', 'B' oder null sein"}), 400

    plans = [
        DayPlan(r.day_date, slot, strength, r.status) if r is row else _day_plan(r) for r in rows
    ]
    violations = validate_week(plans)
    if has_blocking(violations):
        return _violation_response(violations)

    row.cycling_slot, row.planned_minutes, row.strength_session = slot, minutes, strength
    db.session.commit()
    return jsonify(serialize_day(row, profile, rows, _latest_ftp())), 200


@calendar_bp.patch("/day/<day>")
def update_day_status(day: str):
    """Rueckmeldung bzw. Absage: status planned | done | modified | skipped."""
    profile, error = _profile_or_error()
    if error:
        return error
    try:
        parsed = _parse_date(day)
    except ValueError:
        return jsonify({"error": "ungueltiges Datum, erwartet YYYY-MM-DD"}), 400
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or payload.get("status") not in STATUSES:
        return jsonify({"error": f"status muss einer von {', '.join(STATUSES)} sein"}), 400
    status = payload["status"]
    if status in (STATUS_DONE, STATUS_MODIFIED) and parsed > date.today():
        return jsonify({"error": "künftige Tage können nur abgesagt werden"}), 400

    note = payload.get("note")
    if note is not None and (not isinstance(note, str) or len(note) > MAX_NOTE_LENGTH):
        return jsonify({"error": f"note: Text mit max. {MAX_NOTE_LENGTH} Zeichen"}), 400
    actual_minutes = payload.get("actual_minutes")
    if actual_minutes is not None and (
        isinstance(actual_minutes, bool)
        or not isinstance(actual_minutes, (int, float))
        or not 0 <= actual_minutes <= MAX_PLANNED_MINUTES
    ):
        return jsonify({"error": f"actual_minutes muss zwischen 0 und {MAX_PLANNED_MINUTES} liegen"}), 400
    if status == STATUS_MODIFIED and actual_minutes is None:
        return jsonify({"error": "bei 'modified' ist actual_minutes erforderlich"}), 400
    actual_intensity = payload.get("actual_intensity")
    if actual_intensity is not None and actual_intensity not in {i.value for i in CyclingIntensity}:
        return jsonify({"error": "ungueltige actual_intensity"}), 400
    strength_done = payload.get("actual_strength_done")
    if strength_done is not None and not isinstance(strength_done, bool):
        return jsonify({"error": "actual_strength_done muss true/false sein"}), 400

    rows = ensure_week(profile, parsed)
    row = next(r for r in rows if r.day_date == parsed)
    row.status = status
    row.note = note
    if status in (STATUS_DONE, STATUS_MODIFIED):
        row.actual_minutes, row.actual_intensity, row.actual_strength_done = actual_minutes, actual_intensity, strength_done
    else:
        row.actual_minutes = row.actual_intensity = row.actual_strength_done = None
    db.session.commit()
    return jsonify(serialize_day(row, profile, rows, _latest_ftp())), 200


@calendar_bp.post("/week/<day>/reset")
def reset_week(day: str):
    """Setzt heutige und kuenftige, nicht erledigte Tage der Woche auf die Standardwoche zurueck."""
    profile, error = _profile_or_error()
    if error:
        return error
    try:
        parsed = _parse_date(day)
    except ValueError:
        return jsonify({"error": "ungueltiges Datum, erwartet YYYY-MM-DD"}), 400
    rows = ensure_week(profile, parsed)
    today = date.today()
    for row in rows:
        if row.day_date < today or row.status not in SWAPPABLE_STATUSES:
            continue
        row.cycling_slot, row.strength_session = default_day_plan(profile.program_start_date, row.day_date)
        row.planned_minutes = row.note = None
        row.status = STATUS_PLANNED
    db.session.commit()
    return jsonify(_serialize_week(profile, rows)), 200
