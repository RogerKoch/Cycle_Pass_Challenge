"""API-Endpunkte fuer den intervals.icu-Import (Status, Sync)."""

import logging
from dataclasses import asdict
from datetime import date, datetime, timezone

from flask import Blueprint, current_app, jsonify, request

from backend.integrations.intervals_icu import (
    STATE_LAST_ERROR,
    STATE_LAST_SYNC,
    IcuClient,
    IcuError,
    get_state,
    is_stale,
    sync,
)
from backend.models.intervals import IcuActivity, IcuWellness

logger = logging.getLogger(__name__)

intervals_bp = Blueprint("intervals", __name__, url_prefix="/api/intervals")


def _client() -> IcuClient | None:
    """Client aus der Konfiguration; INTERVALS_ICU_CLIENT ersetzt ihn in Tests durch einen Fake."""
    injected = current_app.config.get("INTERVALS_ICU_CLIENT")
    if injected is not None:
        return injected
    api_key = current_app.config.get("INTERVALS_ICU_API_KEY")
    return IcuClient(api_key) if api_key else None


@intervals_bp.get("/status")
def get_status():
    """Konfiguriert?, letzter Sync, letzter Fehler, Anzahl importierter Datensaetze."""
    return jsonify({
        "configured": _client() is not None,
        "last_sync": get_state(STATE_LAST_SYNC),
        "last_error": get_state(STATE_LAST_ERROR),
        "activities": IcuActivity.query.count(),
        "wellness_days": IcuWellness.query.count(),
    }), 200


@intervals_bp.post("/sync")
def run_sync():
    """Synchronisiert die letzten 14 Tage. `?if_stale=1`: nur, wenn der letzte Sync > 30 min her ist."""
    client = _client()
    if client is None:
        return jsonify({"synced": False, "error": "intervals.icu nicht konfiguriert (INTERVALS_ICU_API_KEY)"}), 409
    if request.args.get("if_stale") and not is_stale(datetime.now(timezone.utc)):
        return jsonify({"synced": False, "error": None}), 200
    try:
        result = sync(client, date.today())
    except IcuError as exc:
        return jsonify({"synced": False, "error": str(exc)}), 502
    return jsonify({"synced": True, "error": None, **asdict(result)}), 200
