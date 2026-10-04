"""API-Endpunkte fuer Lebensmittel: Suche, eigene Lebensmittel, Portionen, Barcode-Lookup."""

import logging
import math
import re

from flask import Blueprint, jsonify, request
from sqlalchemy import case, func

from backend.engine.food_calc import normalize_search
from backend.extensions import db
from backend.integrations.open_food_facts import OffUnavailableError, lookup_product
from backend.models.food import Food, FoodLogEntry

logger = logging.getLogger(__name__)

foods_bp = Blueprint("foods", __name__, url_prefix="/api/foods")

NUTRIENT_FIELDS: tuple[str, ...] = ("kcal_100g", "protein_100g", "carbs_100g", "fat_100g")
DEFAULT_LIMIT = 20
MAX_LIMIT = 50
EAN_PATTERN = re.compile(r"^\d{8,14}$")


def serialize_food(food: Food) -> dict:
    """Lebensmittel als JSON-Dict."""
    return {
        "id": food.id,
        "name": food.name,
        "category": food.category,
        "source": food.source,
        "kcal_100g": food.kcal_100g,
        "protein_100g": food.protein_100g,
        "carbs_100g": food.carbs_100g,
        "fat_100g": food.fat_100g,
        "portion_label": food.portion_label,
        "portion_g": food.portion_g,
    }


def _non_negative(value: object, key: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{key} muss >= 0 sein, war {value}")
    return number


def _parse_portion(body: dict) -> tuple[str | None, float | None]:
    """Portion ist entweder komplett (Label + Gramm > 0) oder leer."""
    label = (body.get("portion_label") or "").strip() or None
    grams = body.get("portion_g")
    if label is None and grams is None:
        return None, None
    if label is None or grams is None:
        raise ValueError("portion_label und portion_g nur gemeinsam angeben")
    grams = _non_negative(grams, "portion_g")
    if grams == 0:
        raise ValueError("portion_g muss > 0 sein")
    return label, grams


def _recent_foods(limit: int) -> list[Food]:
    """Zuletzt verwendete Lebensmittel (neuester Eintrag zuerst), ohne Duplikate."""
    last_used = (
        db.session.query(FoodLogEntry.food_id, func.max(FoodLogEntry.id).label("last_id"))
        .filter(FoodLogEntry.food_id.isnot(None))
        .group_by(FoodLogEntry.food_id)
        .subquery()
    )
    return (
        Food.query.join(last_used, Food.id == last_used.c.food_id)
        .order_by(last_used.c.last_id.desc())
        .limit(limit)
        .all()
    )


@foods_bp.get("")
def search_foods():
    """Sucht Lebensmittel (?q=...&limit=20). Alle Woerter muessen vorkommen. Rangfolge: erstes Wort
    als ganzes Wort am Anfang ("Ei, ..."), dann Praefix, dann Wortanfang, dann Teiltreffer; innerhalb
    gleicher Stufe haeufig genutzte zuerst. Ohne q: zuletzt verwendete Lebensmittel."""
    try:
        limit = min(max(int(request.args.get("limit", DEFAULT_LIMIT)), 1), MAX_LIMIT)
    except ValueError:
        return jsonify({"error": "limit muss eine Zahl sein"}), 400
    words = normalize_search(request.args.get("q", "")).split()
    if not words:
        return jsonify([serialize_food(f) for f in _recent_foods(limit)]), 200

    query = Food.query
    for word in words:
        query = query.filter(Food.search_name.contains(word, autoescape=True))
    first = words[0]
    whole_word_prefix = (
        (Food.search_name == first)
        | Food.search_name.startswith(f"{first},", autoescape=True)
        | Food.search_name.startswith(f"{first} ", autoescape=True)
    )
    rank = case(
        (whole_word_prefix, 0),
        (Food.search_name.startswith(first, autoescape=True), 1),
        (Food.search_name.contains(f" {first}", autoescape=True), 2),
        else_=3,
    )
    foods = query.order_by(rank, Food.use_count.desc(), func.length(Food.name), Food.name).limit(limit).all()
    return jsonify([serialize_food(f) for f in foods]), 200


@foods_bp.post("")
def create_food():
    """Legt ein eigenes Lebensmittel an (Werte pro 100 g von der Packung, optional Portion und Barcode)."""
    body = request.get_json(force=True, silent=True) or {}
    try:
        name = (body.get("name") or "").strip()
        if not name:
            raise ValueError("name fehlt")
        values = {key: _non_negative(body[key], key) for key in NUTRIENT_FIELDS}
        portion_label, portion_g = _parse_portion(body)
        barcode = body.get("barcode")
        if barcode is not None and not EAN_PATTERN.match(str(barcode)):
            raise ValueError("barcode muss aus 8-14 Ziffern bestehen")
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify({"error": f"ungueltiges Lebensmittel: {exc}"}), 400
    if barcode is not None and Food.query.filter_by(source="custom", source_id=str(barcode)).first():
        return jsonify({"error": "Barcode ist bereits einem eigenen Lebensmittel zugeordnet"}), 409

    food = Food(
        name=name,
        category=body.get("category"),
        source="custom",
        source_id=str(barcode) if barcode is not None else None,
        search_name=normalize_search(name),
        portion_label=portion_label,
        portion_g=portion_g,
        **values,
    )
    db.session.add(food)
    db.session.commit()
    return jsonify(serialize_food(food)), 201


@foods_bp.get("/<int:food_id>")
def get_food(food_id: int):
    """Ein Lebensmittel nach ID."""
    food = db.session.get(Food, food_id)
    if food is None:
        return jsonify({"error": "Lebensmittel nicht gefunden"}), 404
    return jsonify(serialize_food(food)), 200


@foods_bp.patch("/<int:food_id>")
def update_food(food_id: int):
    """Setzt/loescht die Portion; Name und Naehrwerte nur bei eigenen Lebensmitteln aenderbar."""
    food = db.session.get(Food, food_id)
    if food is None:
        return jsonify({"error": "Lebensmittel nicht gefunden"}), 404
    body = request.get_json(force=True, silent=True) or {}
    content_keys = [key for key in ("name", *NUTRIENT_FIELDS) if key in body]
    if content_keys and food.source != "custom":
        return jsonify({"error": "Name/Naehrwerte nur bei eigenen Lebensmitteln aenderbar"}), 400
    try:
        if "portion_label" in body or "portion_g" in body:
            food.portion_label, food.portion_g = _parse_portion(body)
        for key in NUTRIENT_FIELDS:
            if key in body:
                setattr(food, key, _non_negative(body[key], key))
        if "name" in body:
            name = (body["name"] or "").strip()
            if not name:
                raise ValueError("name darf nicht leer sein")
            food.name, food.search_name = name, normalize_search(name)
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({"error": f"ungueltige Daten: {exc}"}), 400
    db.session.commit()
    return jsonify(serialize_food(food)), 200


@foods_bp.get("/barcode/<ean>")
def lookup_barcode(ean: str):
    """Sucht einen Barcode zuerst lokal, sonst bei Open Food Facts (Treffer wird gespeichert).

    404 mit `name`, wenn OFF das Produkt kennt, aber Naehrwerte fehlen (UI fuellt damit das
    Formular fuer ein eigenes Lebensmittel vor).
    """
    if not EAN_PATTERN.match(ean):
        return jsonify({"error": "Barcode muss aus 8-14 Ziffern bestehen"}), 400
    local = Food.query.filter(Food.source.in_(("off", "custom")), Food.source_id == ean).first()
    if local is not None:
        return jsonify(serialize_food(local)), 200

    try:
        product = lookup_product(ean)
    except OffUnavailableError as exc:
        logger.warning("Open Food Facts nicht erreichbar: %s", exc)
        return jsonify({"error": "Open Food Facts nicht erreichbar"}), 502
    if product is None:
        return jsonify({"error": "Barcode unbekannt", "name": None}), 404
    if not product.complete:
        return jsonify({"error": "Naehrwerte bei Open Food Facts unvollstaendig", "name": product.name}), 404

    food = Food(
        name=product.name,
        source="off",
        source_id=ean,
        search_name=normalize_search(product.name),
        kcal_100g=product.kcal_100g,
        protein_100g=product.protein_100g,
        carbs_100g=product.carbs_100g,
        fat_100g=product.fat_100g,
    )
    db.session.add(food)
    db.session.commit()
    return jsonify(serialize_food(food)), 201
