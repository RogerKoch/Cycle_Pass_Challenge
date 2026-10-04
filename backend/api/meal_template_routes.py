"""API-Endpunkte fuer Mahlzeit-Vorlagen (anlegen, aus einer erfassten Mahlzeit speichern, anwenden)."""

import logging
from datetime import date

from flask import Blueprint, jsonify, request

from backend.api.food_log_routes import add_food_entry, parse_grams, parse_meal, recompute_intake_day
from backend.extensions import db
from backend.models.food import Food, FoodLogEntry, MealTemplate, MealTemplateItem

logger = logging.getLogger(__name__)

meal_templates_bp = Blueprint("meal_templates", __name__, url_prefix="/api/meal-templates")


def _serialize(template: MealTemplate) -> dict:
    return {
        "id": template.id,
        "name": template.name,
        "meal": template.meal,
        "kcal": round(sum(i.food.kcal_100g * i.grams / 100 for i in template.items), 1),
        "items": [{"food_id": i.food_id, "name": i.food.name, "grams": i.grams} for i in template.items],
    }


@meal_templates_bp.get("")
def list_templates():
    """Alle Vorlagen, alphabetisch."""
    templates = MealTemplate.query.order_by(MealTemplate.name).all()
    return jsonify([_serialize(t) for t in templates]), 200


@meal_templates_bp.post("")
def create_template():
    """Vorlage aus {name, meal, items: [{food_id, grams}]} oder aus einer erfassten Mahlzeit
    {name, meal, from_date} (Schnelleintraege werden dabei uebersprungen)."""
    body = request.get_json(force=True, silent=True) or {}
    try:
        name = (body.get("name") or "").strip()
        if not name:
            raise ValueError("name fehlt")
        meal = parse_meal(body.get("meal"))
        if "from_date" in body:
            entries = FoodLogEntry.query.filter(
                FoodLogEntry.entry_date == date.fromisoformat(body["from_date"]),
                FoodLogEntry.meal == meal,
                FoodLogEntry.food_id.isnot(None),
            ).order_by(FoodLogEntry.id)
            items = [(e.food_id, e.grams) for e in entries]
        else:
            items = [(int(i["food_id"]), parse_grams(i.get("grams"))) for i in body.get("items") or []]
        if not items:
            raise ValueError("Vorlage braucht mindestens ein Lebensmittel")
        unknown = {food_id for food_id, _ in items if db.session.get(Food, food_id) is None}
        if unknown:
            raise ValueError(f"unbekannte food_id: {sorted(unknown)}")
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify({"error": f"ungueltige Vorlage: {exc}"}), 400

    template = MealTemplate(name=name, meal=meal)
    template.items = [MealTemplateItem(food_id=food_id, grams=grams) for food_id, grams in items]
    db.session.add(template)
    db.session.commit()
    return jsonify(_serialize(template)), 201


@meal_templates_bp.delete("/<int:template_id>")
def delete_template(template_id: int):
    """Loescht eine Vorlage (erfasste Eintraege bleiben bestehen)."""
    template = db.session.get(MealTemplate, template_id)
    if template is None:
        return jsonify({"error": "Vorlage nicht gefunden"}), 404
    db.session.delete(template)
    db.session.commit()
    return "", 204


@meal_templates_bp.post("/<int:template_id>/apply")
def apply_template(template_id: int):
    """Legt die Eintraege der Vorlage fuer {date, meal?} an (meal: Default aus der Vorlage)."""
    template = db.session.get(MealTemplate, template_id)
    if template is None:
        return jsonify({"error": "Vorlage nicht gefunden"}), 404
    body = request.get_json(force=True, silent=True) or {}
    try:
        entry_date = date.fromisoformat(body["date"])
        meal = parse_meal(body.get("meal", template.meal))
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify({"error": f"ungueltige Daten: {exc}"}), 400
    entries = [add_food_entry(entry_date, meal, item.food, item.grams) for item in template.items]
    recompute_intake_day(entry_date)
    db.session.commit()
    return jsonify({"created": len(entries)}), 201
