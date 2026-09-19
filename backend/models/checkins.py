"""Woechentliche Check-in-Daten (Gewicht, Koerperfett, Muskelmasse)."""

from datetime import date, datetime, timezone

from backend.extensions import db


class Checkin(db.Model):
    """Ein Check-in-Datensatz. `ffm_kg` wird aus weight_kg/bodyfat_pct abgeleitet,
    nicht gespeichert, um nicht mit diesen Feldern auseinanderzulaufen."""

    __tablename__ = "checkins"

    id: int = db.Column(db.Integer, primary_key=True)
    checkin_date: date = db.Column(db.Date, nullable=False, index=True)
    weight_kg: float = db.Column(db.Float, nullable=False)
    bodyfat_pct: float = db.Column(db.Float, nullable=False)
    muscle_kg: float = db.Column(db.Float, nullable=False)
    created_at: datetime = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    @property
    def ffm_kg(self) -> float:
        """Fettfreie Masse: weight_kg * (1 - bodyfat_pct / 100)."""
        return self.weight_kg * (1 - self.bodyfat_pct / 100)
