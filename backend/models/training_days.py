"""Trainingskalender: ein Datensatz je Tag (geplanter Slot, Anpassungen, Rueckmeldung)."""

from datetime import date, datetime, timezone

from backend.extensions import db


class TrainingDay(db.Model):
    """Geplanter bzw. erledigter Trainingstag.

    Gespeichert werden nur Slot und Nutzerentscheidungen; Intervalle, Watt und Uebungen
    werden beim Lesen aus Phase/Woche aufgeloest (engine.cycling_sessions, engine.strength_sessions).
    """

    __tablename__ = "training_days"

    id: int = db.Column(db.Integer, primary_key=True)
    day_date: date = db.Column(db.Date, nullable=False, unique=True)
    cycling_slot: str | None = db.Column(db.String(32), nullable=True)
    planned_minutes: float | None = db.Column(db.Float, nullable=True)  # Dauer-Override bei Ausdauerfahrten
    strength_session: str | None = db.Column(db.String(1), nullable=True)
    status: str = db.Column(db.String(16), nullable=False, default="planned")
    actual_minutes: float | None = db.Column(db.Float, nullable=True)
    actual_intensity: str | None = db.Column(db.String(32), nullable=True)
    actual_strength_done: bool | None = db.Column(db.Boolean, nullable=True)
    note: str | None = db.Column(db.String(200), nullable=True)
    created_at: datetime = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
