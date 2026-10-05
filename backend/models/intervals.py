"""Aus intervals.icu importierte Daten und Sync-Zustand."""

from datetime import date, datetime, timezone

from backend.engine.imported_training import ActivityRecord
from backend.extensions import db


class IcuActivity(db.Model):
    """Eine importierte Aktivitaet (Upsert nach icu_id)."""

    __tablename__ = "icu_activities"

    id: int = db.Column(db.Integer, primary_key=True)
    icu_id: str = db.Column(db.String(32), nullable=False, unique=True)
    day: date = db.Column(db.Date, nullable=False, index=True)
    type: str = db.Column(db.String(40), nullable=False)
    name: str | None = db.Column(db.String(200), nullable=True)
    moving_seconds: int | None = db.Column(db.Integer, nullable=True)
    joules: float | None = db.Column(db.Float, nullable=True)
    calories: float | None = db.Column(db.Float, nullable=True)
    training_load: float | None = db.Column(db.Float, nullable=True)
    avg_watts: float | None = db.Column(db.Float, nullable=True)
    weighted_watts: float | None = db.Column(db.Float, nullable=True)
    avg_hr: float | None = db.Column(db.Float, nullable=True)
    intensity: float | None = db.Column(db.Float, nullable=True)

    def to_record(self) -> ActivityRecord:
        """Sicht fuer die Engine."""
        return ActivityRecord(
            icu_id=self.icu_id,
            day=self.day,
            type=self.type,
            name=self.name,
            moving_seconds=self.moving_seconds,
            joules=self.joules,
            calories=self.calories,
            training_load=self.training_load,
            avg_watts=self.avg_watts,
            weighted_watts=self.weighted_watts,
            avg_hr=self.avg_hr,
            intensity=self.intensity,
        )


class IcuWellness(db.Model):
    """Wellness-Werte eines Tages; checkin_id verweist auf den daraus erzeugten Auto-Check-in."""

    __tablename__ = "icu_wellness"

    id: int = db.Column(db.Integer, primary_key=True)
    day: date = db.Column(db.Date, nullable=False, unique=True)
    resting_hr: float | None = db.Column(db.Float, nullable=True)
    hrv: float | None = db.Column(db.Float, nullable=True)
    weight_kg: float | None = db.Column(db.Float, nullable=True)
    body_fat_pct: float | None = db.Column(db.Float, nullable=True)
    sleep_secs: int | None = db.Column(db.Integer, nullable=True)
    sleep_score: float | None = db.Column(db.Float, nullable=True)
    checkin_id: int | None = db.Column(db.Integer, db.ForeignKey("checkins.id"), nullable=True)


class IntegrationState(db.Model):
    """Schluessel/Wert fuer den Sync-Zustand (last_sync, last_error)."""

    __tablename__ = "integration_state"

    id: int = db.Column(db.Integer, primary_key=True)
    key: str = db.Column(db.String(64), nullable=False, unique=True)
    value: str | None = db.Column(db.String(500), nullable=True)
    updated_at: datetime = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


def imported_records(day_from: date, day_to: date) -> dict[date, list[ActivityRecord]]:
    """Importierte Aktivitaeten im Zeitraum, nach Tag gruppiert."""
    result: dict[date, list[ActivityRecord]] = {}
    for row in IcuActivity.query.filter(IcuActivity.day >= day_from, IcuActivity.day <= day_to).all():
        result.setdefault(row.day, []).append(row.to_record())
    return result
