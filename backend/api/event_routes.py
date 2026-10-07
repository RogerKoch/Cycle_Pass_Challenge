"""API-Endpunkte fuer Events (Rennen, Touren) und ihre Vorbereitung."""

import logging
import math
from datetime import date, timedelta

from flask import Blueprint, jsonify, request

from backend.engine.event_prep import (
    KINDS,
    LOAD_DAYS,
    PRIORITIES,
    TAPER_DAYS,
    EventSpan,
    carbs_g_per_kg,
    deficit_factor,
    event_context,
    event_hints,
    recovery_window_days,
    strength_blocked,
    taper_volume_factor,
)
from backend.extensions import db
from backend.models.checkins import Checkin
from backend.models.events import Event

logger = logging.getLogger(__name__)

events_bp = Blueprint("events", __name__, url_prefix="/api/events")

MAX_NAME_LENGTH = 120
MAX_NOTE_LENGTH = 200
MIN_EXPECTED_MINUTES, MAX_EXPECTED_MINUTES = 30, 900
DEFAULT_WEIGHT_KG = 70.0


def _serialize(event: Event) -> dict:
    return {
        "id": event.id,
        "event_date": event.event_date.isoformat(),
        "name": event.name,
        "priority": event.priority,
        "expected_minutes": event.expected_minutes,
        "kind": event.kind,
        "note": event.note,
    }


def _validate(payload: dict, current: Event | None = None) -> tuple[dict | None, tuple | None]:
    """Prueft das Payload; fehlende Felder fallen bei einem Update auf den aktuellen Wert zurueck."""

    def value(key: str, default=None):
        return payload.get(key, getattr(current, key) if current is not None else default)

    try:
        event_date = date.fromisoformat(str(value("event_date")))
    except ValueError:
        return None, (jsonify({"error": "event_date (YYYY-MM-DD) erforderlich"}), 400)
    name = value("name")
    if not isinstance(name, str) or not name.strip() or len(name) > MAX_NAME_LENGTH:
        return None, (jsonify({"error": f"name: Text mit 1–{MAX_NAME_LENGTH} Zeichen erforderlich"}), 400)
    priority = value("priority", "B")
    if priority not in PRIORITIES:
        return None, (jsonify({"error": f"priority muss eine von {', '.join(PRIORITIES)} sein"}), 400)
    kind = value("kind", "rennen")
    if kind not in KINDS:
        return None, (jsonify({"error": f"kind muss einer von {', '.join(KINDS)} sein"}), 400)
    minutes = value("expected_minutes")
    if (
        isinstance(minutes, bool)
        or not isinstance(minutes, (int, float))
        or not math.isfinite(minutes)
        or not MIN_EXPECTED_MINUTES <= minutes <= MAX_EXPECTED_MINUTES
    ):
        return None, (
            jsonify({"error": f"expected_minutes muss zwischen {MIN_EXPECTED_MINUTES} und {MAX_EXPECTED_MINUTES} liegen"}),
            400,
        )
    note = value("note")
    if note is not None and (not isinstance(note, str) or len(note) > MAX_NOTE_LENGTH):
        return None, (jsonify({"error": f"note: Text mit max. {MAX_NOTE_LENGTH} Zeichen"}), 400)
    return {
        "event_date": event_date,
        "name": name.strip(),
        "priority": priority,
        "expected_minutes": float(minutes),
        "kind": kind,
        "note": note,
    }, None


@events_bp.get("")
def list_events():
    """Events, optional ab `from` (YYYY-MM-DD); Standard: ab heute, aufsteigend nach Datum."""
    raw = request.args.get("from")
    try:
        start = date.fromisoformat(raw) if raw else date.today()
    except ValueError:
        return jsonify({"error": "from muss YYYY-MM-DD sein"}), 400
    events = Event.query.filter(Event.event_date >= start).order_by(Event.event_date).all()
    return jsonify([_serialize(e) for e in events]), 200


@events_bp.post("")
def create_event():
    """Legt ein Event an (event_date, name, expected_minutes; priority A/B/C, kind rennen/tour)."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "JSON-Objekt erwartet"}), 400
    data, error = _validate(payload)
    if error:
        return error
    event = Event(**data)
    db.session.add(event)
    db.session.commit()
    return jsonify(_serialize(event)), 201


@events_bp.put("/<int:event_id>")
def update_event(event_id: int):
    """Aendert ein Event; nicht gesendete Felder bleiben unveraendert."""
    event = db.session.get(Event, event_id)
    if event is None:
        return jsonify({"error": "Event nicht gefunden"}), 404
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "JSON-Objekt erwartet"}), 400
    data, error = _validate(payload, event)
    if error:
        return error
    for key, val in data.items():
        setattr(event, key, val)
    db.session.commit()
    return jsonify(_serialize(event)), 200


@events_bp.delete("/<int:event_id>")
def delete_event(event_id: int):
    """Loescht ein Event; der Kalender faellt zur Lesezeit auf den Standardplan zurueck."""
    event = db.session.get(Event, event_id)
    if event is None:
        return jsonify({"error": "Event nicht gefunden"}), 404
    db.session.delete(event)
    db.session.commit()
    return "", 204


@events_bp.get("/<int:event_id>/prep")
def event_prep(event_id: int):
    """Countdown des Events: je Tag Phase, Taper-Volumen, KH-Ziel, Defizit-Anteil und Hinweise."""
    event = db.session.get(Event, event_id)
    if event is None:
        return jsonify({"error": "Event nicht gefunden"}), 404
    checkin = Checkin.query.order_by(Checkin.checkin_date.desc(), Checkin.created_at.desc()).first()
    weight = checkin.weight_kg if checkin else DEFAULT_WEIGHT_KG
    span: EventSpan = event.to_span()
    first = -max(TAPER_DAYS[span.priority], LOAD_DAYS)
    last = recovery_window_days(span.expected_minutes)
    days = []
    for offset in range(first, last + 1):
        day = span.event_date + timedelta(days=offset)
        ctx = event_context(day, [span])
        if ctx is None:
            continue
        factor = taper_volume_factor(ctx)
        gpk = carbs_g_per_kg(ctx)
        days.append(
            {
                "date": day.isoformat(),
                "label": ctx.label,
                "phase": ctx.phase,
                "volume_pct": round(factor * 100) if factor is not None else None,
                "carbs_g_per_kg": gpk,
                "carbs_g": round(gpk * weight) if gpk is not None else None,
                "deficit_factor": deficit_factor(ctx),
                "strength_blocked": strength_blocked(ctx),
                "hints": event_hints(ctx, weight),
            }
        )
    return jsonify({"event": _serialize(event), "weight_kg": weight, "days": days}), 200
