"""Import von Aktivitaeten und Wellness-Daten aus intervals.icu (buendelt die Garmin-Daten).

API: https://intervals.icu/api/v1/docs – HTTP Basic mit Username "API_KEY" und dem persoenlichen
Key als Passwort, Athlet "0" = eigener Account. Der Key steht nur in instance/config.py
(INTERVALS_ICU_API_KEY) und wird weder geloggt noch ans Frontend gegeben.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import requests
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from backend.engine.cycling_sessions import CyclingSession
from backend.engine.imported_training import ActivityRecord
from backend.engine.zwo_export import session_to_zwo
from backend.extensions import db
from backend.integrations.numbers import finite_number as _number
from backend.models.checkins import Checkin
from backend.models.intervals import IcuActivity, IcuWellness, IntegrationState

logger = logging.getLogger(__name__)

BASE_URL = "https://intervals.icu/api/v1"
TIMEOUT_S = 20
SYNC_WINDOW_DAYS = 14
STALE_AFTER = timedelta(minutes=30)
STATE_LAST_SYNC = "last_sync"
STATE_LAST_ERROR = "last_error"
STATE_LAST_PUSH_ERROR = "last_push_error"
EXTERNAL_ID_PREFIX = "cpc-"  # markiert die von der App angelegten Workouts
ACTIVITY_FIELDS = (
    "id,start_date_local,type,name,moving_time,icu_joules,calories,icu_training_load,"
    "icu_average_watts,icu_weighted_avg_watts,average_heartrate,icu_intensity"
)


class IcuError(Exception):
    """intervals.icu nicht erreichbar, Key ungueltig oder unerwartete Antwort."""


@dataclass
class WellnessRecord:
    """Wellness-Werte eines Tages (metrisch, wie von intervals.icu geliefert)."""

    day: date
    resting_hr: float | None = None
    hrv: float | None = None
    weight_kg: float | None = None
    body_fat_pct: float | None = None
    sleep_secs: int | None = None
    sleep_score: float | None = None


@dataclass
class SyncResult:
    """Ergebnis eines Syncs."""

    activities: int = 0
    activities_removed: int = 0
    wellness_days: int = 0
    checkins_created: int = 0
    checkins_updated: int = 0
    notes: list[str] = field(default_factory=list)


@dataclass
class PushResult:
    """Ergebnis eines Workout-Pushs."""

    upserted: int = 0
    deleted: int = 0


def parse_activity(data: dict) -> ActivityRecord | None:
    """Aktivitaet aus der API-Antwort; None bei Eintraegen ohne Datum (z. B. gesperrte Strava-Importe)."""
    start = data.get("start_date_local")
    if not data.get("id") or not isinstance(start, str):
        return None
    moving = _number(data.get("moving_time"))
    return ActivityRecord(
        icu_id=str(data["id"]),
        day=date.fromisoformat(start[:10]),
        type=str(data.get("type") or "Other"),
        name=data.get("name"),
        moving_seconds=int(moving) if moving is not None else None,
        joules=_number(data.get("icu_joules")),
        calories=_number(data.get("calories")),
        training_load=_number(data.get("icu_training_load")),
        avg_watts=_number(data.get("icu_average_watts")),
        weighted_watts=_number(data.get("icu_weighted_avg_watts")),
        avg_hr=_number(data.get("average_heartrate")),
        intensity=_number(data.get("icu_intensity")),
    )


def parse_wellness(data: dict) -> WellnessRecord | None:
    """Wellness-Tag aus der API-Antwort (`id` ist das Datum)."""
    day = data.get("id")
    if not isinstance(day, str):
        return None
    sleep = _number(data.get("sleepSecs"))
    return WellnessRecord(
        day=date.fromisoformat(day[:10]),
        resting_hr=_number(data.get("restingHR")),
        hrv=_number(data.get("hrv")),
        weight_kg=_number(data.get("weight")),
        body_fat_pct=_number(data.get("bodyFat")),
        sleep_secs=int(sleep) if sleep is not None else None,
        sleep_score=_number(data.get("sleepScore")),
    )


class IcuClient:
    """Minimaler Lese-Client fuer die intervals.icu-API."""

    def __init__(self, api_key: str, athlete_id: str = "0") -> None:
        self._auth = ("API_KEY", api_key)
        self._athlete = athlete_id

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        try:
            response = requests.request(method, f"{BASE_URL}{path}", auth=self._auth, timeout=TIMEOUT_S, **kwargs)
        except requests.RequestException as exc:
            raise IcuError(f"intervals.icu nicht erreichbar: {exc.__class__.__name__}") from exc
        if response.status_code in (401, 403):
            raise IcuError("API-Key ungültig (intervals.icu → Settings → Developer Settings)")
        if response.status_code != 200:
            raise IcuError(f"intervals.icu antwortet mit HTTP {response.status_code}")
        return response

    def _get(self, path: str, params: dict) -> list:
        response = self._request("GET", path, params=params)
        try:
            body = response.json()
        except ValueError as exc:
            raise IcuError("keine gültige JSON-Antwort von intervals.icu") from exc
        if not isinstance(body, list):
            raise IcuError("unerwartete Antwort von intervals.icu")
        return body

    @staticmethod
    def _parsed(parser, row: dict):
        """Parst einen Eintrag; ein kaputtes Feld (Datum, Zahl) wird zu IcuError statt zu einem 500."""
        try:
            return parser(row)
        except (ValueError, OverflowError) as exc:
            raise IcuError("unerwartete Felder in der Antwort von intervals.icu") from exc

    def fetch_activities(self, oldest: date, newest: date) -> list[ActivityRecord]:
        """Aktivitaeten im Zeitraum (inklusive)."""
        rows = self._get(
            f"/athlete/{self._athlete}/activities",
            {"oldest": oldest.isoformat(), "newest": newest.isoformat(), "fields": ACTIVITY_FIELDS},
        )
        return [a for a in (self._parsed(parse_activity, r) for r in rows if isinstance(r, dict)) if a is not None]

    def fetch_wellness(self, oldest: date, newest: date) -> list[WellnessRecord]:
        """Wellness-Tage im Zeitraum (inklusive)."""
        rows = self._get(f"/athlete/{self._athlete}/wellness", {"oldest": oldest.isoformat(), "newest": newest.isoformat()})
        return [w for w in (self._parsed(parse_wellness, r) for r in rows if isinstance(r, dict)) if w is not None]

    def fetch_workout_events(self, oldest: date, newest: date) -> list[dict]:
        """Geplante Workouts (Kalender-Events) im Zeitraum (inklusive)."""
        rows = self._get(
            f"/athlete/{self._athlete}/events",
            {"oldest": oldest.isoformat(), "newest": newest.isoformat(), "category": "WORKOUT"},
        )
        return [r for r in rows if isinstance(r, dict)]

    def upsert_workouts(self, events: list[dict]) -> None:
        """Legt Workouts an bzw. aktualisiert sie anhand von external_id."""
        self._request("POST", f"/athlete/{self._athlete}/events/bulk", params={"upsert": "true"}, json=events)

    def delete_event(self, event_id: int | str) -> None:
        """Loescht ein Kalender-Event."""
        self._request("DELETE", f"/athlete/{self._athlete}/events/{event_id}")


def get_state(key: str) -> str | None:
    """Wert aus integration_state."""
    row = IntegrationState.query.filter_by(key=key).first()
    return row.value if row else None


def _set_state(key: str, value: str | None) -> None:
    row = IntegrationState.query.filter_by(key=key).first()
    if row is None:
        db.session.add(IntegrationState(key=key, value=value))
    else:
        row.value = value


def _upsert_activities(records: list[ActivityRecord], oldest: date, newest: date, result: SyncResult) -> None:
    existing = {
        a.icu_id: a for a in IcuActivity.query.filter(IcuActivity.day >= oldest, IcuActivity.day <= newest).all()
    }
    seen = set()
    for record in records:
        seen.add(record.icu_id)
        row = existing.get(record.icu_id) or IcuActivity.query.filter_by(icu_id=record.icu_id).first()
        if row is None:
            row = IcuActivity(icu_id=record.icu_id)
            db.session.add(row)
        for name in ("day", "type", "name", "moving_seconds", "joules", "calories", "training_load",
                     "avg_watts", "weighted_watts", "avg_hr", "intensity"):
            setattr(row, name, getattr(record, name))
        result.activities += 1
    for icu_id, row in existing.items():
        if icu_id not in seen:
            db.session.delete(row)
            result.activities_removed += 1


def _auto_checkin(row: IcuWellness, linked_ids: set[int], result: SyncResult, fresh: bool) -> None:
    """Legt aus dem Wiegewert einen Check-in an bzw. aktualisiert den verknuepften.

    `fresh`: der Wert hat sich seit dem letzten Sync geaendert; nur dann wird ein verknuepfter Check-in
    ueberschrieben, damit manuelle Korrekturen nicht bei jedem Sync verloren gehen.
    """
    if row.checkin_id is not None:
        checkin = db.session.get(Checkin, row.checkin_id)
        if checkin is not None:
            if not fresh:
                return
            changed = checkin.weight_kg != row.weight_kg or (
                row.body_fat_pct is not None and checkin.bodyfat_pct != row.body_fat_pct
            )
            checkin.weight_kg = row.weight_kg
            if row.body_fat_pct is not None:
                checkin.bodyfat_pct = row.body_fat_pct
            result.checkins_updated += int(changed)
            return
    same_day = Checkin.query.filter_by(checkin_date=row.day).all()
    if any(c.id not in linked_ids for c in same_day):
        return  # manueller Check-in hat Vorrang
    previous = (
        Checkin.query.filter(Checkin.checkin_date <= row.day)
        .order_by(Checkin.checkin_date.desc(), Checkin.created_at.desc())
        .first()
    ) or Checkin.query.order_by(Checkin.checkin_date.asc()).first()
    if previous is None:
        note = "Für Auto-Check-ins einmal manuell einchecken (Muskelmasse/Körperfett als Startwert)."
        if note not in result.notes:
            result.notes.append(note)
        return
    checkin = Checkin(
        checkin_date=row.day,
        weight_kg=row.weight_kg,
        bodyfat_pct=row.body_fat_pct if row.body_fat_pct is not None else previous.bodyfat_pct,
        muscle_kg=previous.muscle_kg,  # liefert intervals.icu nicht; fliesst in keine Berechnung ein
    )
    db.session.add(checkin)
    db.session.flush()
    row.checkin_id = checkin.id
    linked_ids.add(checkin.id)
    result.checkins_created += 1


def _upsert_wellness(records: list[WellnessRecord], result: SyncResult) -> None:
    linked_ids = {w.checkin_id for w in IcuWellness.query.filter(IcuWellness.checkin_id.isnot(None)).all()}
    for record in sorted(records, key=lambda r: r.day):
        row = IcuWellness.query.filter_by(day=record.day).first()
        if row is None:
            row = IcuWellness(day=record.day)
            db.session.add(row)
        fresh = (row.weight_kg, row.body_fat_pct) != (record.weight_kg, record.body_fat_pct)
        for name in ("resting_hr", "hrv", "weight_kg", "body_fat_pct", "sleep_secs", "sleep_score"):
            setattr(row, name, getattr(record, name))
        result.wellness_days += 1
        if row.weight_kg:
            db.session.flush()
            _auto_checkin(row, linked_ids, result, fresh)


def sync(client: IcuClient, today: date, days: int = SYNC_WINDOW_DAYS) -> SyncResult:
    """Holt Aktivitaeten und Wellness der letzten `days` Tage und gleicht die DB ab.

    Args:
        client: intervals.icu-Client (in Tests ein Fake mit denselben Methoden).
        today: Bezugsdatum (Ende des Fensters).
        days: Fenstergroesse rueckwaerts.

    Returns:
        SyncResult mit Anzahlen und Hinweisen.

    Raises:
        IcuError: bei Fehlern der API; last_error wird gespeichert.
    """
    oldest = today - timedelta(days=days)
    result = SyncResult()
    try:
        activities = client.fetch_activities(oldest, today)
        wellness = client.fetch_wellness(oldest, today)
        _upsert_activities(activities, oldest, today, result)
        _upsert_wellness(wellness, result)
        _set_state(STATE_LAST_SYNC, datetime.now(timezone.utc).isoformat())
        _set_state(STATE_LAST_ERROR, None)
        db.session.commit()
    except (IcuError, SQLAlchemyError) as exc:
        db.session.rollback()
        error = exc if isinstance(exc, IcuError) else IcuError("Datenbankfehler beim Sync")
        _set_state(STATE_LAST_ERROR, str(error))
        db.session.commit()
        logger.warning("intervals.icu-Sync fehlgeschlagen: %s", exc)
        raise error from exc
    logger.info("intervals.icu-Sync: %s", result)
    return result


def is_stale(now: datetime, max_age: timedelta = STALE_AFTER) -> bool:
    """True, wenn noch nie oder vor mehr als `max_age` synchronisiert wurde."""
    last = get_state(STATE_LAST_SYNC)
    return last is None or now - datetime.fromisoformat(last) > max_age


def configured_client() -> "IcuClient | None":
    """Client aus der App-Konfiguration; INTERVALS_ICU_CLIENT ersetzt ihn in Tests durch einen Fake."""
    injected = current_app.config.get("INTERVALS_ICU_CLIENT")
    if injected is not None:
        return injected
    api_key = current_app.config.get("INTERVALS_ICU_API_KEY")
    return IcuClient(api_key) if api_key else None


def _external_id(day: date) -> str:
    return f"{EXTERNAL_ID_PREFIX}{day.isoformat()}"


def _workout_event(day: date, session: CyclingSession) -> dict:
    return {
        "category": "WORKOUT",
        "type": "Ride",
        "start_date_local": f"{day.isoformat()}T00:00:00",
        "name": session.title,
        "external_id": _external_id(day),
        "filename": f"{day.isoformat()}.zwo",
        "file_contents": session_to_zwo(session),
    }


def push_workouts(client: IcuClient, sessions: dict[date, CyclingSession | None]) -> PushResult:
    """Gleicht die geplanten Radeinheiten mit dem intervals.icu-Kalender ab (von dort weiter zu Zwift).

    Tage mit Einheit werden angelegt/aktualisiert (Upsert ueber external_id), eigene Workouts an Tagen
    ohne Einheit geloescht. Fremde Kalender-Eintraege und Tage ausserhalb von `sessions` bleiben unberuehrt.

    Args:
        client: intervals.icu-Client (in Tests ein Fake mit denselben Methoden).
        sessions: Tag -> Einheit, None = an diesem Tag kein Workout.

    Returns:
        PushResult mit Anzahlen.

    Raises:
        IcuError: bei Fehlern der API; last_push_error wird gespeichert.
    """
    result = PushResult()
    if not sessions:
        return result
    events = [_workout_event(day, s) for day, s in sorted(sessions.items()) if s is not None]
    empty_ids = {_external_id(day) for day, s in sessions.items() if s is None}
    try:
        if events:
            client.upsert_workouts(events)
        if empty_ids:
            for event in client.fetch_workout_events(min(sessions), max(sessions)):
                if event.get("external_id") in empty_ids:
                    client.delete_event(event["id"])
                    result.deleted += 1
    except IcuError as exc:
        _set_state(STATE_LAST_PUSH_ERROR, str(exc))
        db.session.commit()
        logger.warning("Workout-Push zu intervals.icu fehlgeschlagen: %s", exc)
        raise
    result.upserted = len(events)
    _set_state(STATE_LAST_PUSH_ERROR, None)
    db.session.commit()
    logger.info("Workout-Push zu intervals.icu: %s", result)
    return result
