"""API-Endpunkte fuer den intervals.icu-Import (Status, Sync)."""

import logging
from dataclasses import asdict
from datetime import date, datetime, timezone

from flask import Blueprint, jsonify, request

from backend.api.calendar_routes import push_planned_workouts
from backend.integrations.intervals_icu import (
    STATE_LAST_ERROR,
    STATE_LAST_SYNC,
    IcuError,
    configured_client,
    get_state,
    is_stale,
    sync,
)
from backend.models.intervals import IcuActivity, IcuWellness
from backend.models.user_profile import UserProfile

logger = logging.getLogger(__name__)

intervals_bp = Blueprint("intervals", __name__, url_prefix="/api/intervals")


@intervals_bp.get("/status")
def get_status():
    """Konfiguriert?, letzter Sync, letzter Fehler, Anzahl importierter Datensaetze."""
    return jsonify({
        "configured": configured_client() is not None,
        "last_sync": get_state(STATE_LAST_SYNC),
        "last_error": get_state(STATE_LAST_ERROR),
        "activities": IcuActivity.query.count(),
        "wellness_days": IcuWellness.query.count(),
    }), 200


@intervals_bp.post("/sync")
def run_sync():
    """Synchronisiert die letzten 14 Tage und schickt die Workouts der naechsten 7 Tage an intervals.icu.

    `?if_stale=1`: nur, wenn der letzte Sync > 30 min her ist.
    """
    client = configured_client()
    if client is None:
        return jsonify({"synced": False, "error": "intervals.icu nicht konfiguriert (INTERVALS_ICU_API_KEY)"}), 409
    if request.args.get("if_stale") and not is_stale(datetime.now(timezone.utc)):
        return jsonify({"synced": False, "error": None}), 200
    try:
        result = sync(client, date.today())
    except IcuError as exc:
        return jsonify({"synced": False, "error": str(exc)}), 502
    pushed, push_error = None, None
    profile = UserProfile.query.first()
    if profile is not None:
        try:
            pushed = push_planned_workouts(profile)
        except IcuError as exc:
            push_error = str(exc)
    return jsonify({
        "synced": True,
        "error": None,
        **asdict(result),
        "workouts_pushed": pushed.upserted if pushed else 0,
        "push_error": push_error,
    }), 200
