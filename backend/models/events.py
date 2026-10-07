"""Events (Rennen, Touren) fuer die Vorbereitung."""

from datetime import date, datetime, timezone

from backend.engine.event_prep import EventSpan
from backend.extensions import db


class Event(db.Model):
    """Ein einzelnes Event; Taper, Carb-Loading und Recovery werden daraus abgeleitet, nicht gespeichert."""

    __tablename__ = "events"

    id: int = db.Column(db.Integer, primary_key=True)
    event_date: date = db.Column(db.Date, nullable=False, index=True)
    name: str = db.Column(db.String(120), nullable=False)
    priority: str = db.Column(db.String(1), nullable=False, default="B")
    expected_minutes: float = db.Column(db.Float, nullable=False)
    kind: str = db.Column(db.String(16), nullable=False, default="rennen")
    note: str | None = db.Column(db.String(200), nullable=True)
    created_at: datetime = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_span(self) -> EventSpan:
        """Sicht fuer die Engine."""
        return EventSpan(self.event_date, self.name, self.priority, self.expected_minutes, self.kind)


def event_spans() -> list[EventSpan]:
    """Alle Events als Engine-Sicht."""
    return [e.to_span() for e in Event.query.all()]
