"""Tests fuer den Import der Sport-Produkte und ihre Vorschlaege im Tagesablauf."""

import pytest

from backend.engine.day_timeline import BaseTargets, build_timeline
from backend.engine.nutrition_calc import CyclingIntensity
from backend.engine.sport_products import DRINK, GEL, JELLY_COLA, PRODUCTS
from backend.extensions import db
from backend.integrations.sport_products_import import import_sport_products
from backend.models.food import Food

BASE = BaseTargets(kcal=2050, protein_g=107, carbs_g=198, fat_g=83)


def _intra(minutes: float, intensity: CyclingIntensity) -> list[str]:
    slots = build_timeline(BASE, minutes, intensity, 0, evening=True, weekend=False)
    return next(s for s in slots if s.slot == "intra").options


def test_import_creates_all_products_as_custom_foods(app):
    created, present = import_sport_products()
    assert (created, present) == (len(PRODUCTS), 0)
    maurten = Food.query.filter_by(source="custom", source_id=DRINK.source_id).one()
    assert maurten.portion_g == 42.0
    assert maurten.carbs_100g * maurten.portion_g / 100 == pytest.approx(39, abs=0.1)


def test_import_is_idempotent_and_keeps_manual_corrections(app):
    import_sport_products()
    salt = Food.query.filter_by(source_id="sport:on-electrolyte-forest-berry").one()
    salt.kcal_100g = 120.0
    db.session.commit()

    created, present = import_sport_products()

    assert (created, present) == (0, len(PRODUCTS))
    assert Food.query.filter(Food.source_id.like("sport:%")).count() == len(PRODUCTS)
    assert Food.query.filter_by(source_id="sport:on-electrolyte-forest-berry").one().kcal_100g == 120.0


def test_short_ride_suggests_only_salt():
    options = _intra(45, CyclingIntensity.MODERAT_BASE)
    assert len(options) == 1 and "Electrolyte" in options[0]


def test_medium_ride_suggests_drink_salt_and_half_bar():
    options = " | ".join(_intra(90, CyclingIntensity.MODERAT_BASE))
    assert DRINK.short_name in options and "Electrolyte" in options and f"½ {JELLY_COLA.short_name}" in options
    assert GEL.short_name in options  # als Alternative zur halben Bar


def test_long_ride_adds_gel_or_bar_per_hour():
    options = " | ".join(_intra(180, CyclingIntensity.MODERAT_BASE))
    assert f"1 {GEL.short_name}" in options and f"1 {JELLY_COLA.short_name}" in options


def test_pre_options_include_half_jelly_bar():
    slots = build_timeline(BASE, 60, CyclingIntensity.MODERAT_BASE, 0, evening=True, weekend=False)
    pre = next(s for s in slots if s.slot == "pre")
    assert any("Jelly Bar" in option for option in pre.options)
