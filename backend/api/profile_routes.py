"""API-Endpunkte fuer das Nutzerprofil."""

import logging
from datetime import date

from flask import Blueprint, jsonify, request

from backend.extensions import db
from backend.models.user_profile import UserProfile

logger = logging.getLogger(__name__)

profile_bp = Blueprint("profile", __name__, url_prefix="/api/profile")


def _serialize(profile: UserProfile) -> dict:
    return {
        "id": profile.id,
        "age": profile.age,
        "height_cm": profile.height_cm,
        "program_start_date": profile.program_start_date.isoformat(),
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
    except (TypeError, ValueError) as exc:
        return jsonify({"error": f"ungueltige Profildaten: {exc}"}), 400

    db.session.commit()
    return jsonify(_serialize(profile)), 200
