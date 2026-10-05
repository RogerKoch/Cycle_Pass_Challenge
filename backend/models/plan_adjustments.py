"""Bestaetigte Plan-Anpassungen und Review-Entscheidungen."""

from datetime import date, datetime, timezone

from backend.engine.plan_adjustments import AdjustmentSpan
from backend.extensions import db


class PlanAdjustment(db.Model):
    """Eine aus dem Check-in-Review uebernommene Anpassung (Zeitfenster, end_date None = offen)."""

    __tablename__ = "plan_adjustments"

    id: int = db.Column(db.Integer, primary_key=True)
    kind: str = db.Column(db.String(32), nullable=False)
    start_date: date = db.Column(db.Date, nullable=False)
    end_date: date | None = db.Column(db.Date, nullable=True)
    value: float | None = db.Column(db.Float, nullable=True)
    label: str = db.Column(db.String(120), nullable=False)
    finding_key: str | None = db.Column(db.String(120), nullable=True)
    created_at: datetime = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_span(self) -> AdjustmentSpan:
        """Sicht fuer die Engine."""
        return AdjustmentSpan(self.kind, self.start_date, self.end_date, self.value)


class ReviewDecision(db.Model):
    """Entscheidung zu einem Befund; entschiedene Befunde werden nicht erneut angezeigt."""

    __tablename__ = "review_decisions"

    id: int = db.Column(db.Integer, primary_key=True)
    finding_key: str = db.Column(db.String(120), nullable=False, unique=True)
    decision: str = db.Column(db.String(16), nullable=False)  # accepted | dismissed
    created_at: datetime = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


def adjustment_spans() -> list[AdjustmentSpan]:
    """Alle bestaetigten Anpassungen als Engine-Zeitfenster."""
    return [a.to_span() for a in PlanAdjustment.query.all()]
