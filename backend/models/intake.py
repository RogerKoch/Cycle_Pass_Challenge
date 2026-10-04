"""Tatsaechliche Nahrungszufuhr (Tagessummen, z.B. aus dem Tracker-Import-Job)."""

from datetime import date, datetime, timezone

from backend.extensions import db


class IntakeDay(db.Model):
    """Tagessumme der Zufuhr. Ein Datensatz je Datum, wird beim erneuten Senden ueberschrieben."""

    __tablename__ = "intake_days"

    id: int = db.Column(db.Integer, primary_key=True)
    intake_date: date = db.Column(db.Date, nullable=False, unique=True)
    kcal: float = db.Column(db.Float, nullable=False)
    protein_g: float = db.Column(db.Float, nullable=False)
    carbs_g: float = db.Column(db.Float, nullable=False)
    fat_g: float = db.Column(db.Float, nullable=False)
    updated_at: datetime = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
