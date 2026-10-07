"""Barcode-Lookup bei Open Food Facts (offene, kostenlose Produktdatenbank)."""

import logging
from dataclasses import dataclass

import requests

from backend.integrations.numbers import finite_number as _number

logger = logging.getLogger(__name__)

PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{ean}"
FIELDS = "product_name,product_name_de,brands,nutriments"
USER_AGENT = "CyclePassChallenge/0.1 (private single-user app)"  # OFF wuenscht einen eigenen User-Agent
TIMEOUT_S = 10
KJ_PER_KCAL = 4.184


class OffUnavailableError(Exception):
    """Open Food Facts nicht erreichbar oder unerwartete Antwort."""


@dataclass
class OffProduct:
    """Produkt aus Open Food Facts; Naehrwerte pro 100 g sind None, wenn OFF sie nicht kennt."""

    name: str
    kcal_100g: float | None
    protein_100g: float | None
    carbs_100g: float | None
    fat_100g: float | None

    @property
    def complete(self) -> bool:
        """True, wenn alle vier Naehrwerte vorhanden sind."""
        return None not in (self.kcal_100g, self.protein_100g, self.carbs_100g, self.fat_100g)


def lookup_product(ean: str) -> OffProduct | None:
    """Sucht ein Produkt per Barcode.

    Args:
        ean: Barcode (nur Ziffern).

    Returns:
        OffProduct, oder None wenn OFF den Barcode nicht kennt.

    Raises:
        OffUnavailableError: bei Netzwerkfehler oder unerwarteter Antwort.
    """
    try:
        response = requests.get(
            PRODUCT_URL.format(ean=ean),
            params={"fields": FIELDS},
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_S,
        )
    except requests.RequestException as exc:
        raise OffUnavailableError(str(exc)) from exc
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise OffUnavailableError(f"HTTP {response.status_code}")
    try:
        body = response.json()
    except ValueError as exc:
        raise OffUnavailableError("keine gueltige JSON-Antwort") from exc
    if not isinstance(body, dict):
        raise OffUnavailableError("unerwartete Antwort")
    if body.get("status") != 1:
        return None

    product = body.get("product")
    product = product if isinstance(product, dict) else {}
    nutriments = product.get("nutriments")
    nutriments = nutriments if isinstance(nutriments, dict) else {}
    name = product.get("product_name_de") or product.get("product_name") or f"Produkt {ean}"
    brand = (product.get("brands") or "").split(",")[0].strip()
    if brand and brand.casefold() not in name.casefold():
        name = f"{name} ({brand})"
    kcal = _number(nutriments.get("energy-kcal_100g"))
    if kcal is None and (kj := _number(nutriments.get("energy_100g"))) is not None:
        kcal = round(kj / KJ_PER_KCAL, 1)
    return OffProduct(
        name=name,
        kcal_100g=kcal,
        protein_100g=_number(nutriments.get("proteins_100g")),
        carbs_100g=_number(nutriments.get("carbohydrates_100g")),
        fat_100g=_number(nutriments.get("fat_100g")),
    )
