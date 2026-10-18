"""API-Endpunkte fuer das Nutzerprofil."""

import logging
from datetime import date

from flask import Blueprint, jsonify, request

from backend.engine.nutrition_calc import ACTIVITY_LEVELS, DEFAULT_ACTIVITY_LEVEL, SEX_BMR_CONSTANT, SEX_MALE
from backend.engine.strength_alternatives import EQUIPMENT_OPTIONS
from backend.engine.strength_benchmarks import DEFAULT_INTERVAL_WEEKS, MAX_INTERVAL_WEEKS, MIN_INTERVAL_WEEKS
from backend.engine.strength_sessions import FOCUS_NONE, FOCUS_OPTIONS
from backend.engine.week_plan import SPORT_CYCLING, SPORTS, STANDARD_WEEK, STATUS_PLANNED, default_day_plan
from backend.extensions import db
from backend.models.baseline_measurements import BaselineMeasurement
from backend.models.training_days import TrainingDay
from backend.models.user_profile import UserProfile

logger = logging.getLogger(__name__)

profile_bp = Blueprint("profile", __name__, url_prefix="/api/profile")

DEFAULT_REST_WEEKDAY = 1  # Dienstag


def _activity_level(value: object) -> str:
    """Prueft die Alltags-/Beruf-Stufe gegen ACTIVITY_LEVELS."""
    if value not in ACTIVITY_LEVELS:
        raise ValueError(f"unbekannte Alltags-Stufe: {value}")
    return value


def _sex(value: object) -> str:
    """Prueft das Geschlecht gegen SEX_BMR_CONSTANT."""
    if value not in SEX_BMR_CONSTANT:
        raise ValueError(f"sex muss einer von {', '.join(SEX_BMR_CONSTANT)} sein")
    return value


def _sport(value: object) -> str:
    """Prueft den Ausdauersport gegen SPORTS."""
    if value not in SPORTS:
        raise ValueError(f"sport muss einer von {', '.join(SPORTS)} sein")
    return value


def _strength_focus(value: object) -> str:
    """Prueft den Kraft-Fokus gegen FOCUS_OPTIONS."""
    if value not in FOCUS_OPTIONS:
        raise ValueError(f"unbekannter Kraft-Fokus: {value}")
    return value


def _equipment_missing(value: object) -> str:
    """Prueft die Liste fehlenden Materials gegen EQUIPMENT_OPTIONS; liefert die kommagetrennte Form."""
    if not isinstance(value, list) or any(item not in EQUIPMENT_OPTIONS for item in value):
        raise ValueError(f"equipment_missing muss eine Liste aus {sorted(EQUIPMENT_OPTIONS)} sein")
    return ",".join(sorted(set(value)))


WEEKDAYS: list[str] = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _evening_training_days(value: object) -> str:
    """Prueft die Wochentage (0 = Mo ... 6 = So); liefert die kommagetrennte Form."""
    valid = isinstance(value, list) and all(
        isinstance(day, int) and not isinstance(day, bool) and 0 <= day <= 6 for day in value
    )
    if not valid:
        raise ValueError("evening_training_days muss eine Liste von Wochentagen 0 (Mo) bis 6 (So) sein")
    return ",".join(str(day) for day in sorted(set(value)))


def _rest_weekday(value: object) -> int:
    """Prueft den Ruhetag der Standardwoche (0 = Mo ... 6 = So)."""
    if isinstance(value, bool) or (isinstance(value, float) and not value.is_integer()):
        raise ValueError("rest_weekday muss ein Wochentag 0 (Mo) bis 6 (So) sein")
    weekday = int(value)
    if not 0 <= weekday <= len(STANDARD_WEEK) - 1:
        raise ValueError("rest_weekday muss ein Wochentag 0 (Mo) bis 6 (So) sein")
    return weekday


def _replan_future_days(profile: UserProfile) -> None:
    """Setzt heutige und kuenftige, unveraenderte Plan-Tage auf die Standardwoche des neuen Ruhetags."""
    today = date.today()
    rows = TrainingDay.query.filter(TrainingDay.day_date >= today, TrainingDay.status == STATUS_PLANNED).all()
    for row in rows:
        if row.planned_minutes is not None or row.note is not None:
            continue  # vom Nutzer angepasst
        row.cycling_slot, row.strength_session = default_day_plan(
            profile.program_start_date, row.day_date, profile.rest_weekday, profile.sport
        )


def _interval_weeks(value: object) -> int:
    """Prueft das Benchmark-Intervall (Wochen)."""
    if isinstance(value, bool):
        raise ValueError("benchmark_interval_weeks muss eine Zahl sein")
    if isinstance(value, float) and not value.is_integer():  # auch inf/nan
        raise ValueError("benchmark_interval_weeks muss eine ganze Zahl sein")
    weeks = int(value)
    if not MIN_INTERVAL_WEEKS <= weeks <= MAX_INTERVAL_WEEKS:
        raise ValueError(f"benchmark_interval_weeks muss zwischen {MIN_INTERVAL_WEEKS} und {MAX_INTERVAL_WEEKS} liegen")
    return weeks


def _options() -> dict:
    """Auswahllisten fuer das Profilformular (auch ohne bestehendes Profil noetig)."""
    return {
        "activity_levels": [
            {"id": key, "label": label, "factor": factor} for key, (label, factor) in ACTIVITY_LEVELS.items()
        ],
        "sex_options": [{"id": "m", "label": "Mann"}, {"id": "f", "label": "Frau"}],
        "sport_options": [{"id": "cycling", "label": "Rad"}, {"id": "running", "label": "Laufen"}],
        "weekday_options": [{"id": i, "label": label} for i, label in enumerate(WEEKDAYS)],
        "equipment_options": [{"id": key, "label": label} for key, label in EQUIPMENT_OPTIONS.items()],
        "focus_options": [{"id": key, "label": label} for key, label in FOCUS_OPTIONS.items()],
    }


def _target_weight(value: object) -> float:
    """Prueft das Zielgewicht (kg)."""
    if isinstance(value, bool):
        raise ValueError("target_weight_kg muss eine Zahl sein")
    weight = float(value)
    if not 30 <= weight <= 200:  # auch inf/nan
        raise ValueError("target_weight_kg muss zwischen 30 und 200 liegen")
    return weight


def _target_bodyfat(value: object) -> float:
    """Prueft das Ziel-Koerperfett (%)."""
    if isinstance(value, bool):
        raise ValueError("target_bodyfat_pct muss eine Zahl sein")
    bodyfat = float(value)
    if not 3 <= bodyfat <= 60:  # auch inf/nan
        raise ValueError("target_bodyfat_pct muss zwischen 3 und 60 liegen")
    return bodyfat


def _apply_goal(profile: UserProfile, body: dict) -> None:
    """Setzt das Ziel aus target_weight_kg oder target_bodyfat_pct (hoechstens eins; das andere entfaellt)."""
    if "target_weight_kg" in body and "target_bodyfat_pct" in body:
        raise ValueError("entweder target_weight_kg oder target_bodyfat_pct angeben")
    measured = BaselineMeasurement.query.filter_by(field_name="target_bodyfat_pct").first()
    if body.get("target_weight_kg") is not None:
        profile.target_weight_kg = _target_weight(body["target_weight_kg"])
        if measured is not None:
            db.session.delete(measured)
    elif body.get("target_bodyfat_pct") is not None:
        value = _target_bodyfat(body["target_bodyfat_pct"])
        profile.target_weight_kg = None
        if measured is None:
            db.session.add(BaselineMeasurement(field_name="target_bodyfat_pct", measured_value=value))
        else:
            measured.measured_value = value


def _serialize(profile: UserProfile) -> dict:
    measured = BaselineMeasurement.query.filter_by(field_name="target_bodyfat_pct").first()
    return {
        **_options(),
        "target_weight_kg": profile.target_weight_kg,
        "target_bodyfat_pct": measured.measured_value if measured is not None else None,
        "id": profile.id,
        "age": profile.age,
        "height_cm": profile.height_cm,
        "program_start_date": profile.program_start_date.isoformat(),
        "activity_level": profile.activity_level,
        "sex": profile.sex,
        "sport": profile.sport,
        "strength_focus": profile.strength_focus,
        "benchmark_interval_weeks": profile.benchmark_interval_weeks,
        "rest_weekday": profile.rest_weekday,
        "equipment_missing": [item for item in profile.equipment_missing.split(",") if item],
        "evening_training_days": [int(d) for d in profile.evening_training_days.split(",") if d],
        "created_at": profile.created_at.isoformat(),
        "updated_at": profile.updated_at.isoformat(),
    }


@profile_bp.get("")
def get_profile():
    """Gibt das aktuelle Profil zurueck, oder 404 (mit Auswahllisten) falls keins existiert."""
    profile = UserProfile.query.first()
    if profile is None:
        return jsonify({"error": "kein Profil vorhanden", **_options()}), 404
    return jsonify(_serialize(profile)), 200


@profile_bp.post("")
def create_profile():
    """Legt das Profil an. 409 falls bereits eins existiert."""
    if UserProfile.query.first() is not None:
        return jsonify({"error": "Profil existiert bereits, PUT zum Aktualisieren verwenden"}), 409

    body = request.get_json(force=True, silent=True) or {}
    try:
        profile = UserProfile(
            age=int(body["age"]),
            height_cm=float(body["height_cm"]),
            program_start_date=date.fromisoformat(body["program_start_date"]),
            activity_level=_activity_level(body.get("activity_level", DEFAULT_ACTIVITY_LEVEL)),
            sex=_sex(body.get("sex", SEX_MALE)),
            sport=_sport(body.get("sport", SPORT_CYCLING)),
            strength_focus=_strength_focus(body.get("strength_focus", FOCUS_NONE)),
            benchmark_interval_weeks=_interval_weeks(body.get("benchmark_interval_weeks", DEFAULT_INTERVAL_WEEKS)),
            rest_weekday=_rest_weekday(body.get("rest_weekday", DEFAULT_REST_WEEKDAY)),
            equipment_missing=_equipment_missing(body.get("equipment_missing", [])),
            evening_training_days=_evening_training_days(body.get("evening_training_days", [1, 2, 3, 4])),
        )
        _apply_goal(profile, body)
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify({"error": f"ungueltige Profildaten: {exc}"}), 400

    db.session.add(profile)
    db.session.commit()
    return jsonify(_serialize(profile)), 201


@profile_bp.put("")
def update_profile():
    """Aktualisiert das bestehende Profil. 404 falls keins existiert."""
    profile = UserProfile.query.first()
    if profile is None:
        return jsonify({"error": "kein Profil vorhanden"}), 404

    body = request.get_json(force=True, silent=True) or {}
    try:
        if "age" in body:
            profile.age = int(body["age"])
        if "height_cm" in body:
            profile.height_cm = float(body["height_cm"])
        if "program_start_date" in body:
            profile.program_start_date = date.fromisoformat(body["program_start_date"])
        if "activity_level" in body:
            profile.activity_level = _activity_level(body["activity_level"])
        if "sex" in body:
            profile.sex = _sex(body["sex"])
        sport_changed = False
        if "sport" in body:
            new_sport = _sport(body["sport"])
            sport_changed = new_sport != profile.sport
            profile.sport = new_sport
        if "strength_focus" in body:
            profile.strength_focus = _strength_focus(body["strength_focus"])
        if "benchmark_interval_weeks" in body:
            profile.benchmark_interval_weeks = _interval_weeks(body["benchmark_interval_weeks"])
        if "equipment_missing" in body:
            profile.equipment_missing = _equipment_missing(body["equipment_missing"])
        if "evening_training_days" in body:
            profile.evening_training_days = _evening_training_days(body["evening_training_days"])
        rest_changed = False
        if "rest_weekday" in body:
            new_rest = _rest_weekday(body["rest_weekday"])
            rest_changed = new_rest != profile.rest_weekday
            profile.rest_weekday = new_rest
        _apply_goal(profile, body)
    except (TypeError, ValueError) as exc:
        return jsonify({"error": f"ungueltige Profildaten: {exc}"}), 400

    if rest_changed or sport_changed:
        _replan_future_days(profile)
    db.session.commit()
    return jsonify(_serialize(profile)), 200
