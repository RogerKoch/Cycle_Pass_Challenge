"""API-Endpunkte fuer das Ernaehrungs-Tagebuch. Jede Aenderung berechnet die Tagessumme in
`intake_days` neu, damit /api/plan/today (Soll/Ist, Energy Availability) unveraendert funktioniert."""

import logging
import math
from datetime import date

from flask import Blueprint, jsonify, request

from backend.engine.food_calc import Nutrients, scale_nutrients
from backend.extensions import db
from backend.models.food import ENTRY_STATUSES, MEALS, Food, FoodLogEntry
from backend.models.intake import IntakeDay

logger = logging.getLogger(__name__)

food_log_bp = Blueprint("food_log", __name__, url_prefix="/api/food-log")

TOTAL_FIELDS: tuple[str, ...] = ("kcal", "protein_g", "carbs_g", "fat_g")


def parse_meal(value: object) -> str:
    """Validiert eine Mahlzeit gegen MEALS."""
    if value not in MEALS:
        raise ValueError(f"meal muss eine von {MEALS} sein, war {value!r}")
    return value


def parse_status(value: object) -> str:
    """Validiert den Status (Default eaten)."""
    if value is None:
        return "eaten"
    if value not in ENTRY_STATUSES:
        raise ValueError(f"status muss einer von {ENTRY_STATUSES} sein, war {value!r}")
    return value


def parse_grams(value: object) -> float:
    """Menge in Gramm, muss > 0 sein."""
    grams = float(value)
    if not math.isfinite(grams) or grams <= 0:
        raise ValueError(f"grams muss > 0 sein, war {value}")
    return grams


def _serialize(entry: FoodLogEntry) -> dict:
    return {
        "id": entry.id,
        "entry_date": entry.entry_date.isoformat(),
        "meal": entry.meal,
        "status": entry.status,
        "food_id": entry.food_id,
        "grams": entry.grams,
        "label": entry.label,
        "portion_label": entry.food.portion_label if entry.food else None,
        "portion_g": entry.food.portion_g if entry.food else None,
        **{key: getattr(entry, key) for key in TOTAL_FIELDS},
    }


def _snapshot(food: Food, grams: float) -> Nutrients:
    per_100g = Nutrients(food.kcal_100g, food.protein_100g, food.carbs_100g, food.fat_100g)
    return scale_nutrients(per_100g, grams)


def add_food_entry(entry_date: date, meal: str, food: Food, grams: float, status: str = "eaten") -> FoodLogEntry:
    """Legt einen Eintrag mit Naehrwert-Snapshot an und zaehlt die Nutzung des Lebensmittels hoch (ohne Commit)."""
    nutrients = _snapshot(food, grams)
    entry = FoodLogEntry(
        entry_date=entry_date,
        meal=meal,
        status=status,
        food=food,
        grams=grams,
        label=food.name,
        kcal=nutrients.kcal,
        protein_g=nutrients.protein_g,
        carbs_g=nutrients.carbs_g,
        fat_g=nutrients.fat_g,
    )
    food.use_count += 1
    db.session.add(entry)
    return entry


def _day_totals(entries: list[FoodLogEntry]) -> dict:
    return {key: round(sum(getattr(e, key) for e in entries), 1) for key in TOTAL_FIELDS}


def recompute_intake_day(entry_date: date) -> None:
    """Schreibt die Summe der gegessenen Eintraege nach intake_days; ohne solche wird der Tag geloescht (ohne Commit).

    Geplante Eintraege zaehlen nie als Ist."""
    db.session.flush()
    entries = FoodLogEntry.query.filter_by(entry_date=entry_date, status="eaten").all()
    day = IntakeDay.query.filter_by(intake_date=entry_date).first()
    if not entries:
        if day is not None:
            db.session.delete(day)
        return
    totals = _day_totals(entries)
    if day is None:
        db.session.add(IntakeDay(intake_date=entry_date, **totals))
    else:
        for key, value in totals.items():
            setattr(day, key, value)


@food_log_bp.get("/<entry_date>")
def get_day(entry_date: str):
    """Eintraege eines Tages, gruppiert nach Mahlzeit, plus Tagessumme."""
    try:
        parsed_date = date.fromisoformat(entry_date)
    except ValueError as exc:
        return jsonify({"error": f"ungueltiges Datum: {exc}"}), 400
    entries = FoodLogEntry.query.filter_by(entry_date=parsed_date).order_by(FoodLogEntry.id).all()
    meals = {meal: [_serialize(e) for e in entries if e.meal == meal] for meal in MEALS}
    eaten = [e for e in entries if e.status == "eaten"]
    planned = [e for e in entries if e.status == "planned"]
    return jsonify({
        "date": parsed_date.isoformat(), "meals": meals,
        "totals": _day_totals(eaten), "planned_totals": _day_totals(planned),
    }), 200


@food_log_bp.post("")
def create_entry():
    """Eintrag aus Lebensmittel {date, meal, food_id, grams} oder Schnelleintrag
    {date, meal, label?, kcal, protein_g, carbs_g, fat_g}."""
    body = request.get_json(force=True, silent=True) or {}
    try:
        entry_date = date.fromisoformat(body["date"])
        meal = parse_meal(body.get("meal"))
        status = parse_status(body.get("status"))
        if body.get("food_id") is not None:
            food = db.session.get(Food, int(body["food_id"]))
            if food is None:
                return jsonify({"error": "Lebensmittel nicht gefunden"}), 404
            entry = add_food_entry(entry_date, meal, food, parse_grams(body.get("grams")), status)
        else:
            values = {key: float(body[key]) for key in TOTAL_FIELDS}
            for key, value in values.items():
                if not math.isfinite(value) or value < 0:
                    raise ValueError(f"{key} muss >= 0 sein, war {value}")
            label = (body.get("label") or "").strip() or "Schnelleintrag"
            entry = FoodLogEntry(entry_date=entry_date, meal=meal, status=status, label=label, **values)
            db.session.add(entry)
    except (KeyError, TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({"error": f"ungueltiger Eintrag: {exc}"}), 400
    if status == "eaten":  # Plan-Eintraege duerfen intake_days nicht anfassen (auch kein altes manuelles Ist loeschen)
        recompute_intake_day(entry_date)
    db.session.commit()
    return jsonify(_serialize(entry)), 201


@food_log_bp.patch("/<int:entry_id>")
def update_entry(entry_id: int):
    """Aendert die Menge eines Lebensmittel-Eintrags (Naehrwerte werden neu berechnet)."""
    entry = db.session.get(FoodLogEntry, entry_id)
    if entry is None:
        return jsonify({"error": "Eintrag nicht gefunden"}), 404
    if entry.food is None:
        return jsonify({"error": "Schnelleintraege haben keine Menge, bitte loeschen und neu erfassen"}), 400
    body = request.get_json(force=True, silent=True) or {}
    try:
        grams = parse_grams(body.get("grams"))
    except (TypeError, ValueError) as exc:
        return jsonify({"error": f"ungueltige Menge: {exc}"}), 400
    nutrients = _snapshot(entry.food, grams)
    entry.grams = grams
    for key in TOTAL_FIELDS:
        setattr(entry, key, getattr(nutrients, key))
    if entry.status == "eaten":
        recompute_intake_day(entry.entry_date)
    db.session.commit()
    return jsonify(_serialize(entry)), 200


@food_log_bp.delete("/<int:entry_id>")
def delete_entry(entry_id: int):
    """Loescht einen Eintrag."""
    entry = db.session.get(FoodLogEntry, entry_id)
    if entry is None:
        return jsonify({"error": "Eintrag nicht gefunden"}), 404
    entry_date, was_eaten = entry.entry_date, entry.status == "eaten"
    db.session.delete(entry)
    if was_eaten:
        recompute_intake_day(entry_date)
    db.session.commit()
    return "", 204


@food_log_bp.post("/<int:entry_id>/consume")
def consume_entry(entry_id: int):
    """Uebernimmt einen geplanten Eintrag als gegessen."""
    entry = db.session.get(FoodLogEntry, entry_id)
    if entry is None:
        return jsonify({"error": "Eintrag nicht gefunden"}), 404
    if entry.status != "planned":
        return jsonify({"error": "Eintrag ist nicht geplant"}), 400
    entry.status = "eaten"
    recompute_intake_day(entry.entry_date)
    db.session.commit()
    return jsonify(_serialize(entry)), 200


@food_log_bp.post("/consume")
def consume_planned():
    """Uebernimmt alle geplanten Eintraege eines Tages {date} bzw. einer Mahlzeit {date, meal} als gegessen."""
    body = request.get_json(force=True, silent=True) or {}
    try:
        entry_date = date.fromisoformat(body["date"])
        meal = parse_meal(body["meal"]) if body.get("meal") is not None else None
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify({"error": f"ungueltige Daten: {exc}"}), 400
    query = FoodLogEntry.query.filter_by(entry_date=entry_date, status="planned")
    if meal is not None:
        query = query.filter_by(meal=meal)
    entries = query.all()
    for entry in entries:
        entry.status = "eaten"
    if entries:
        recompute_intake_day(entry_date)
    db.session.commit()
    return jsonify({"consumed": len(entries)}), 200
