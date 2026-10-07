"""API-Endpunkte fuer das Nutzerprofil."""

import logging
from datetime import date

from flask import Blueprint, jsonify, request

from backend.engine.nutrition_calc import ACTIVITY_LEVELS, DEFAULT_ACTIVITY_LEVEL
from backend.engine.strength_sessions import FOCUS_NONE, FOCUS_OPTIONS
from backend.extensions import db
from backend.models.user_profile import UserProfile

logger = logging.getLogger(__name__)

profile_bp = Blueprint("profile", __name__, url_prefix="/api/profile")


def _activity_level(value: object) -> str:
    """Prueft die Alltags-/Beruf-Stufe gegen ACTIVITY_LEVELS."""
    if value not in ACTIVITY_LEVELS:
        raise ValueError(f"unbekannte Alltags-Stufe: {value}")
    return value


def _strength_focus(value: object) -> str:
    """Prueft den Kraft-Fokus gegen FOCUS_OPTIONS."""
    if value not in FOCUS_OPTIONS:
        raise ValueError(f"unbekannter Kraft-Fokus: {value}")
    return value


def _serialize(profile: UserProfile) -> dict:
    return {
        "id": profile.id,
        "age": profile.age,
        "height_cm": profile.height_cm,
        "program_start_date": profile.program_start_date.isoformat(),
        "activity_level": profile.activity_level,
        "activity_levels": [
            {"id": key, "label": label, "factor": factor} for key, (label, factor) in ACTIVITY_LEVELS.items()
        ],
        "strength_focus": profile.strength_focus,
        "focus_options": [{"id": key, "label": label} for key, label in FOCUS_OPTIONS.items()],
        "created_at": profile.created_at.isoformat(),
        "updated_at": profile.updated_at.isoformat(),
    }


@profile_bp.get("")
def get_profile():
    """Gibt das aktuelle Profil zurueck, oder 404 falls keins existiert."""
    profile = UserProfile.query.first()
    if profile is None:
        return jsonify({"error": "kein Profil vorhanden"}), 404
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
            strength_focus=_strength_focus(body.get("strength_focus", FOCUS_NONE)),
        )
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
        if "strength_focus" in body:
            profile.strength_focus = _strength_focus(body["strength_focus"])
    except (TypeError, ValueError) as exc:
        return jsonify({"error": f"ungueltige Profildaten: {exc}"}), 400

    db.session.commit()
    return jsonify(_serialize(profile)), 200
