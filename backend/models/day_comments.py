"""Freitext-Kommentar pro Kalendertag (unabhaengig von Trainings- und Ernaehrungsdaten)."""

from datetime import date, datetime, timezone

from backend.extensions import db

MAX_COMMENT_LENGTH = 2000


class DayComment(db.Model):
    """Ein Kommentar je Tag. Leerer Text wird nicht gespeichert (Zeile entfaellt)."""

    __tablename__ = "day_comments"

    id: int = db.Column(db.Integer, primary_key=True)
    day_date: date = db.Column(db.Date, nullable=False, unique=True)
    text: str = db.Column(db.String(MAX_COMMENT_LENGTH), nullable=False)
    updated_at: datetime = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
