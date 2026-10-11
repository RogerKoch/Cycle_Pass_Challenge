"""Dauerhafte Uebungstausche (Originaluebung -> Alternative), gelten bis zum naechsten Tausch."""

from datetime import datetime, timezone

from backend.extensions import db


class ExerciseSwap(db.Model):
    """Eine getauschte Kraftuebung. Pro Originaluebung hoechstens eine Zeile."""

    __tablename__ = "exercise_swaps"

    id: int = db.Column(db.Integer, primary_key=True)
    original_name: str = db.Column(db.String(100), nullable=False, unique=True)
    alternative_name: str = db.Column(db.String(100), nullable=False)
    updated_at: datetime = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


def exercise_swaps() -> dict[str, str]:
    """Alle aktiven Tausche als Originalname -> Alternativname."""
    return {row.original_name: row.alternative_name for row in ExerciseSwap.query.all()}
