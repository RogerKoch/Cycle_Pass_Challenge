"""Stuendlicher intervals.icu-Sync im Hintergrund (nur im Produktivbetrieb, gestartet von serve.py)."""

import logging
import threading
from datetime import datetime, timedelta

from flask import Flask

from backend.api.intervals_routes import sync_and_push
from backend.integrations.intervals_icu import configured_client

logger = logging.getLogger(__name__)


def seconds_until_next_hour(now: datetime) -> float:
    """Sekunden bis zur naechsten vollen Stunde (mindestens 1 s)."""
    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return max((next_hour - now).total_seconds(), 1.0)


def _run_once(app: Flask) -> None:
    """Ein Sync-Lauf; Fehler werden geloggt, damit der Job weiterlaeuft."""
    with app.app_context():
        client = configured_client()
        if client is None:
            return
        try:
            payload, _status = sync_and_push(client)
        except Exception:  # noqa: BLE001 - Hintergrundjob darf nie sterben
            logger.exception("Stuendlicher intervals.icu-Sync fehlgeschlagen")
            return
        if payload.get("error"):
            logger.warning("Stuendlicher intervals.icu-Sync: %s", payload["error"])


def start_hourly_sync(app: Flask) -> threading.Thread:
    """Startet den Daemon-Thread, der zu jeder vollen Stunde synchronisiert."""
    stop = threading.Event()

    def loop() -> None:
        while not stop.wait(seconds_until_next_hour(datetime.now())):
            _run_once(app)

    thread = threading.Thread(target=loop, name="icu-hourly-sync", daemon=True)
    thread.start()
    logger.info("Stuendlicher intervals.icu-Sync aktiv")
    return thread
