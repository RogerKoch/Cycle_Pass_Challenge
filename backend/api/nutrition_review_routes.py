"""API-Endpunkt fuer die Wochenanalyse der Ernaehrung (Ist gegen Tagesablauf)."""

import logging
from datetime import date, timedelta

from flask import Blueprint, jsonify, request

from backend.api.plan_routes import MAX_OVERVIEW_DAYS, _PlanError, build_plan
from backend.engine.nutrition_review import MACROS, DayInput, review_days
from backend.models.food import FoodLogEntry

logger = logging.getLogger(__name__)

nutrition_review_bp = Blueprint("nutrition_review", __name__, url_prefix="/api/nutrition")

DEFAULT_DAYS = 7


@nutrition_review_bp.get("/review")
def get_review():
    """Analyse Ist gegen Tagesablauf (?from&to, Standard: die letzten 7 abgeschlossenen Tage, hoechstens 62 Tage).

    Voraussetzung: Basis-Tageswerte im Profil (Tagesablauf-Modus), sonst 422.
    """
    try:
        end = date.fromisoformat(request.args["to"]) if "to" in request.args else date.today() - timedelta(days=1)
        start = date.fromisoformat(request.args["from"]) if "from" in request.args else end - timedelta(days=DEFAULT_DAYS - 1)
    except ValueError:
        return jsonify({"error": "from und to erwartet (YYYY-MM-DD)"}), 400
    if end < start or (end - start).days >= MAX_OVERVIEW_DAYS:
        return jsonify({"error": f"Zeitraum muss 1 bis {MAX_OVERVIEW_DAYS} Tage umfassen"}), 400

    eaten: dict[date, dict[str, dict[str, float]]] = {}
    for entry in FoodLogEntry.query.filter(
        FoodLogEntry.entry_date >= start, FoodLogEntry.entry_date <= end, FoodLogEntry.status == "eaten"
    ).all():
        meal = eaten.setdefault(entry.entry_date, {}).setdefault(entry.meal, dict.fromkeys(MACROS, 0.0))
        for key in MACROS:
            meal[key] += getattr(entry, key)

    days = []
    for offset in range((end - start).days + 1):
        current = start + timedelta(days=offset)
        if current not in eaten:
            continue
        try:
            plan = build_plan(current)
        except _PlanError:
            continue
        if plan["timeline"] is None:
            return jsonify({"error": "Analyse braucht die Basis-Tageswerte im Profil (Tagesablauf)"}), 422
        days.append(DayInput(day=current, plan=plan["timeline"], eaten=eaten[current]))
    return jsonify({"from": start.isoformat(), "to": end.isoformat(), **review_days(days)}), 200
