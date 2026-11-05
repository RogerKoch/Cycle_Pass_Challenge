"""Import der Sport-Produkte (backend.engine.sport_products) als eigene Lebensmittel in die geteilte DB."""

import logging

import click
from flask.cli import with_appcontext

from backend.engine.food_calc import normalize_search
from backend.engine.sport_products import CATEGORY, PRODUCTS
from backend.extensions import db
from backend.models.food import Food

logger = logging.getLogger(__name__)


def import_sport_products() -> tuple[int, int]:
    """Legt fehlende Sport-Produkte an (Schluessel: source='custom', source_id='sport:<slug>').

    Vorhandene Eintraege bleiben unveraendert, damit Korrekturen per PATCH /api/foods/<id> nicht ueberschrieben werden.

    Returns:
        (neu angelegt, bereits vorhanden)
    """
    existing = {f.source_id for f in Food.query.filter_by(source="custom").filter(Food.source_id.like("sport:%"))}
    created = 0
    for product in PRODUCTS:
        if product.source_id in existing:
            continue
        db.session.add(Food(
            name=product.name, category=CATEGORY, source="custom", source_id=product.source_id,
            search_name=normalize_search(product.name),
            kcal_100g=product.kcal_100g, protein_100g=0.0, carbs_100g=product.carbs_100g, fat_100g=0.0,
            portion_label=product.portion_label, portion_g=product.portion_g,
        ))
        created += 1
    db.session.commit()
    logger.info("Sport-Produkte: %d neu, %d vorhanden", created, len(PRODUCTS) - created)
    return created, len(PRODUCTS) - created


@click.command("import-sport-products")
@with_appcontext
def import_sport_products_command() -> None:
    """Legt die Sport-Produkte (Maurten, Jelly Bar, Ice Gel, ON Electrolyte) als Lebensmittel an."""
    created, present = import_sport_products()
    click.echo(f"Sport-Produkte: {created} neu, {present} bereits vorhanden")
