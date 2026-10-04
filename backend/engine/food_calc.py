"""Naehrwert-Skalierung und Such-Normalisierung fuer das Ernaehrungs-Tagebuch."""

import logging
import unicodedata
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Nutrients:
    """Energie und Makros, entweder pro 100 g oder fuer eine konkrete Menge."""

    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


def scale_nutrients(per_100g: Nutrients, grams: float) -> Nutrients:
    """Rechnet Naehrwerte pro 100 g auf eine Menge um.

    Args:
        per_100g: Naehrwerte pro 100 g.
        grams: Menge in Gramm (>= 0).

    Returns:
        Naehrwerte fuer die Menge, auf eine Nachkommastelle gerundet.
    """
    if grams < 0:
        raise ValueError(f"grams muss >= 0 sein, war {grams}")
    factor = grams / 100
    return Nutrients(
        kcal=round(per_100g.kcal * factor, 1),
        protein_g=round(per_100g.protein_g * factor, 1),
        carbs_g=round(per_100g.carbs_g * factor, 1),
        fat_g=round(per_100g.fat_g * factor, 1),
    )


def normalize_search(text: str) -> str:
    """Normalisiert Text fuer die Suche: Kleinschreibung, ohne Akzente/Umlaut-Punkte, ß -> ss.

    "Äpfel" und "apfel" werden so beide zu "apfel"; Mehrfach-Leerzeichen werden zusammengefasst.
    """
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.split())
