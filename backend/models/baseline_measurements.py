"""Gemessene Baseline-Werte aus dem Diagnostik-Termin."""

from datetime import datetime, timezone

from backend.extensions import db


class BaselineMeasurement(db.Model):
    """Ein Messwert je Feld (siehe engine.baseline.BASELINE_FIELDS). Schaetzwerte werden nicht gespeichert."""

    __tablename__ = "baseline_measurements"

    id: int = db.Column(db.Integer, primary_key=True)
    field_name: str = db.Column(db.String(40), nullable=False, unique=True)
    measured_value: float = db.Column(db.Float, nullable=False)
    updated_at: datetime = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
