"""API-Endpunkte fuer die tatsaechliche Nahrungszufuhr (Tagessummen)."""

import logging
import math
from datetime import date

from flask import Blueprint, jsonify, request

from backend.extensions import db
from backend.models.intake import IntakeDay

logger = logging.getLogger(__name__)

intake_bp = Blueprint("intake", __name__, url_prefix="/api/intake")


def _serialize(day: IntakeDay) -> dict:
    return {
        "intake_date": day.intake_date.isoformat(),
        "kcal": day.kcal,
        "protein_g": day.protein_g,
        "carbs_g": day.carbs_g,
        "fat_g": day.fat_g,
        "updated_at": day.updated_at.isoformat(),
    }


@intake_bp.put("/<intake_date>")
def upsert_intake(intake_date: str):
    """Legt die Tagessumme an oder ueberschreibt sie (idempotent, fuer wiederholte Import-Jobs)."""
    body = request.get_json(force=True, silent=True) or {}
    try:
        parsed_date = date.fromisoformat(intake_date)
        values = {key: float(body[key]) for key in ("kcal", "protein_g", "carbs_g", "fat_g")}
        for key, value in values.items():
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{key} muss >= 0 sein, war {value}")
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify({"error": f"ungueltige Intake-Daten: {exc}"}), 400

    day = IntakeDay.query.filter_by(intake_date=parsed_date).first()
    status = 200
    if day is None:
        day = IntakeDay(intake_date=parsed_date, **values)
        db.session.add(day)
        status = 201
    else:
        for key, value in values.items():
            setattr(day, key, value)
    db.session.commit()
    return jsonify(_serialize(day)), status


@intake_bp.get("/<intake_date>")
def get_intake(intake_date: str):
    """Gibt die Tagessumme eines Datums zurueck, oder 404 falls keine existiert."""
    try:
        parsed_date = date.fromisoformat(intake_date)
    except ValueError as exc:
        return jsonify({"error": f"ungueltiges Datum: {exc}"}), 400
    day = IntakeDay.query.filter_by(intake_date=parsed_date).first()
    if day is None:
        return jsonify({"error": "keine Zufuhr fuer dieses Datum"}), 404
    return jsonify(_serialize(day)), 200


@intake_bp.get("")
def list_intake():
    """Listet Tagessummen, optional gefiltert mit ?from=YYYY-MM-DD&to=YYYY-MM-DD (neueste zuerst)."""
    query = IntakeDay.query
    try:
        if "from" in request.args:
            query = query.filter(IntakeDay.intake_date >= date.fromisoformat(request.args["from"]))
        if "to" in request.args:
            query = query.filter(IntakeDay.intake_date <= date.fromisoformat(request.args["to"]))
    except ValueError as exc:
        return jsonify({"error": f"ungueltiges Datum: {exc}"}), 400
    days = query.order_by(IntakeDay.intake_date.desc()).all()
    return jsonify([_serialize(d) for d in days]), 200
