"""Nutzerprofil (Einzelperson, kein Multi-User-System)."""

from datetime import date, datetime, timezone

from backend.extensions import db


class UserProfile(db.Model):
    """Statische Profildaten. Es existiert immer maximal eine Zeile."""

    __tablename__ = "user_profile"

    id: int = db.Column(db.Integer, primary_key=True)
    age: int = db.Column(db.Integer, nullable=False)
    height_cm: float = db.Column(db.Float, nullable=False)
    program_start_date: date = db.Column(db.Date, nullable=False)
    created_at: datetime = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
