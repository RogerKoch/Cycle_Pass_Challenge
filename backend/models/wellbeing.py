"""Woechentlicher Kurz-Fragebogen (subjektive Signale fuer die Check-in-Trigger)."""

from datetime import date, datetime, timezone

from backend.extensions import db


class WellbeingSignal(db.Model):
    """Ein Fragebogen je Datum. Scores 0 = kein, 1 = leicht, 2 = deutlich, 3 = stark (Problem)."""

    __tablename__ = "wellbeing_signals"

    id: int = db.Column(db.Integer, primary_key=True)
    signal_date: date = db.Column(db.Date, nullable=False, unique=True)
    sleep: int = db.Column(db.Integer, nullable=False)  # Schlaf schlecht
    legs: int = db.Column(db.Integer, nullable=False)  # Beine platt
    hunger: int = db.Column(db.Integer, nullable=False)  # Dauerhunger
    back: int = db.Column(db.Integer, nullable=False)  # Ruecken nach langen Fahrten
    effort: int = db.Column(db.Integer, nullable=False)  # Anstrengung hoeher bei gleicher Leistung
    resting_hr: int | None = db.Column(db.Integer, nullable=True)
    note: str | None = db.Column(db.String(200), nullable=True)
    updated_at: datetime = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
