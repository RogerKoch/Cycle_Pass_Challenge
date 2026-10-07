"""Kraft-Benchmark-Tests (Woche-0-Tests der Kraft-Recherche, wiederholt im Benchmark-Intervall)."""

from datetime import date, datetime, timezone

from backend.engine.strength_benchmarks import BenchmarkResult, combine
from backend.extensions import db


class StrengthBenchmark(db.Model):
    """Ein Benchmark-Termin; nicht getestete Werte bleiben NULL (Teiltest erlaubt)."""

    __tablename__ = "strength_benchmarks"

    id: int = db.Column(db.Integer, primary_key=True)
    test_date: date = db.Column(db.Date, nullable=False, index=True)
    pushup_reps: int | None = db.Column(db.Integer, nullable=True)
    pushup_variant: str | None = db.Column(db.String(20), nullable=True)
    row_reps: int | None = db.Column(db.Integer, nullable=True)
    side_plank_s: int | None = db.Column(db.Integer, nullable=True)
    side_plank_straight: bool | None = db.Column(db.Boolean, nullable=True)
    sl_bridge_s: int | None = db.Column(db.Integer, nullable=True)  # schwaechere Seite
    plank_s: int | None = db.Column(db.Integer, nullable=True)
    created_at: datetime = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_result(self) -> BenchmarkResult:
        """Sicht fuer die Engine."""
        return BenchmarkResult(
            test_date=self.test_date,
            pushup_reps=self.pushup_reps,
            pushup_variant=self.pushup_variant,
            row_reps=self.row_reps,
            side_plank_s=self.side_plank_s,
            side_plank_straight=self.side_plank_straight,
            sl_bridge_s=self.sl_bridge_s,
            plank_s=self.plank_s,
        )


def all_benchmarks() -> list[StrengthBenchmark]:
    """Alle Termine aufsteigend nach Datum, bei gleichem Datum nach Anlage (neuester zuletzt)."""
    return StrengthBenchmark.query.order_by(StrengthBenchmark.test_date, StrengthBenchmark.id).all()


def current_benchmark(benchmarks: list[StrengthBenchmark] | None = None) -> BenchmarkResult | None:
    """Neuester Wert je Test ueber alle Termine (siehe engine.strength_benchmarks.combine).

    Args:
        benchmarks: bereits geladene Termine (aufsteigend, siehe all_benchmarks); None = aus der DB laden.
    """
    benchmarks = all_benchmarks() if benchmarks is None else benchmarks
    return combine([b.to_result() for b in benchmarks])
