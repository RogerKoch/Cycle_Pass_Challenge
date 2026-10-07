"""API-Endpunkte fuer Kraft-Benchmarks (Tests, abgeleitete Stufen, Meilensteine)."""

import logging
from dataclasses import asdict
from datetime import date

from flask import Blueprint, jsonify, request

from backend.engine.strength_benchmarks import (
    DEFAULT_INTERVAL_WEEKS,
    PUSHUP_VARIANTS,
    exercise_stages,
    milestones,
    next_due,
)
from backend.extensions import db
from backend.models.strength_benchmarks import StrengthBenchmark, all_benchmarks, current_benchmark
from backend.models.user_profile import UserProfile

logger = logging.getLogger(__name__)

benchmarks_bp = Blueprint("benchmarks", __name__, url_prefix="/api/strength-benchmarks")

MAX_REPS = 200
MAX_HOLD_S = 1200
_INT_FIELDS: dict[str, int] = {
    "pushup_reps": MAX_REPS,
    "row_reps": MAX_REPS,
    "side_plank_s": MAX_HOLD_S,
    "sl_bridge_s": MAX_HOLD_S,
    "plank_s": MAX_HOLD_S,
}


def _serialize(benchmark: StrengthBenchmark) -> dict:
    return {"id": benchmark.id, **asdict(benchmark.to_result()), "test_date": benchmark.test_date.isoformat()}


def _int_value(body: dict, key: str, maximum: int) -> int | None:
    value = body.get(key)
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError(f"{key} muss eine Zahl sein")
    if isinstance(value, float) and not value.is_integer():  # auch inf/nan
        raise ValueError(f"{key} muss eine ganze Zahl sein")
    number = int(value)
    if not 0 <= number <= maximum:
        raise ValueError(f"{key} muss zwischen 0 und {maximum} liegen")
    return number


@benchmarks_bp.get("")
def get_benchmarks():
    """Alle Tests (neueste zuerst), aktuelle Werte, Stufen je Uebung, Meilensteine und naechster Termin."""
    tests = all_benchmarks()
    current = current_benchmark(tests)
    profile = UserProfile.query.first()
    interval = profile.benchmark_interval_weeks if profile else DEFAULT_INTERVAL_WEEKS
    return jsonify({
        "tests": [_serialize(t) for t in reversed(tests)],
        "current": {**asdict(current), "test_date": current.test_date.isoformat()} if current else None,
        "stages": asdict(exercise_stages(current)),
        "milestones": [asdict(m) for m in milestones(current)],
        "interval_weeks": interval,
        "next_due": next_due(tests[-1].test_date if tests else None, interval, date.today()).isoformat(),
        "pushup_variants": [{"id": key, "label": label} for key, label in PUSHUP_VARIANTS.items()],
    }), 200


@benchmarks_bp.post("")
def create_benchmark():
    """Legt einen Benchmark-Termin an; mindestens ein Testwert, Liegestuetze nur mit Variante."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "JSON-Objekt erwartet"}), 400
    try:
        values = {key: _int_value(body, key, maximum) for key, maximum in _INT_FIELDS.items()}
        test_date = date.fromisoformat(body["test_date"]) if body.get("test_date") else date.today()
    except (TypeError, ValueError) as exc:
        return jsonify({"error": f"ungueltige Benchmark-Daten: {exc}"}), 400
    if all(v is None for v in values.values()):
        return jsonify({"error": "mindestens einen Testwert angeben"}), 400
    variant = body.get("pushup_variant") or None
    if values["pushup_reps"] is not None and variant not in PUSHUP_VARIANTS:
        return jsonify({"error": f"pushup_variant muss einer von {', '.join(PUSHUP_VARIANTS)} sein"}), 400
    straight = body.get("side_plank_straight")
    if values["side_plank_s"] is not None and not isinstance(straight, bool):
        return jsonify({"error": "side_plank_straight (true/false) erforderlich"}), 400

    benchmark = StrengthBenchmark(
        test_date=test_date,
        pushup_variant=variant if values["pushup_reps"] is not None else None,
        side_plank_straight=straight if values["side_plank_s"] is not None else None,
        **values,
    )
    db.session.add(benchmark)
    db.session.commit()
    return jsonify(_serialize(benchmark)), 201
