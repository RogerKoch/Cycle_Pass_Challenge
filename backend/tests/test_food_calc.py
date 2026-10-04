import pytest

from backend.engine.food_calc import Nutrients, normalize_search, scale_nutrients

PER_100G = Nutrients(kcal=155, protein_g=12.6, carbs_g=1.1, fat_g=10.6)


def test_scales_nutrients_to_given_grams():
    result = scale_nutrients(PER_100G, 60)
    assert result == Nutrients(kcal=93.0, protein_g=7.6, carbs_g=0.7, fat_g=6.4)


def test_zero_grams_gives_zero_nutrients():
    assert scale_nutrients(PER_100G, 0) == Nutrients(0, 0, 0, 0)


def test_rejects_negative_grams():
    with pytest.raises(ValueError):
        scale_nutrients(PER_100G, -1)


def test_normalize_ignores_case_and_umlauts():
    assert normalize_search("Äpfel") == normalize_search("apfel") == "apfel"


def test_normalize_handles_accents_eszett_and_whitespace():
    assert normalize_search("  Crème   Fraîche ") == "creme fraiche"
    assert normalize_search("Weißbrot") == "weissbrot"
