"""Sport-Produkte (Getraenk, Gel, Riegel, Salz) fuer Pre/Intra-Vorschlaege und den Lebensmittel-Import.

Eine Quelle fuer beides: der Import (`backend.integrations.sport_products_import`) legt daraus Lebensmittel an,
`day_timeline` nennt sie in den Vorschlaegen. Werte stammen von den Produktseiten (sportbenzin.ch) und sind nicht
verifiziert; Aenderungen am Lebensmittel gehen ueber PATCH /api/foods/<id>, Vorschlaege hier anpassen.
"""

from dataclasses import dataclass

CATEGORY = "Sportnahrung"


@dataclass(frozen=True)
class SportProduct:
    """Ein Produkt mit Naehrwerten pro 100 g und einer Portion (Beutel, Riegel, Gel)."""

    slug: str
    name: str
    short_name: str
    kcal_100g: float
    carbs_100g: float
    portion_label: str
    portion_g: float
    sodium_mg: float | None = None  # pro Portion, nur fuer Vorschlags-Texte (Food hat keine Natrium-Spalte)

    @property
    def source_id(self) -> str:
        """Schluessel in der Tabelle foods (source='custom'); kollidiert nicht mit EAN-Barcodes."""
        return f"sport:{self.slug}"

    @property
    def carbs_per_portion(self) -> float:
        """KH pro Portion in g."""
        return self.carbs_100g * self.portion_g / 100


# Maurten: 160 kcal / 39 g KH pro Beutel, Salz 0,55 g (~220 mg Natrium, aus Salz umgerechnet)
DRINK = SportProduct("maurten-drink-mix-160", "Maurten Drink Mix 160", "Maurten Drink Mix", 381.0, 93.0,
                     "1 Beutel (500 ml)", 42.0, sodium_mg=220.0)
# Santa Madre Jelly Bar: 150 kcal / 37 g KH pro Riegel (45 g), Zucker 1:0,5
JELLY_COLA = SportProduct("jelly-bar-cola", "Santa Madre Jelly Bar Cola", "Jelly Bar", 333.3, 82.2, "1 Riegel", 45.0)
JELLY_MELON = SportProduct("jelly-bar-melone", "Santa Madre Jelly Bar Melone", "Jelly Bar", 333.3, 82.2, "1 Riegel", 45.0)
# AMACX Ice Gel: 120 kcal / 30 g KH pro Gel, 2:1, 200 mg Natrium, einfrierbar
GEL = SportProduct("amacx-turbo-ice-gel-cola-lime", "AMACX Turbo Ice Gel Cola Lime", "Ice Gel", 156.0, 39.0,
                   "1 Gel", 77.0, sodium_mg=200.0)
# ON Electrolyte: Nährwerte stehen nicht auf der Produktseite, deshalb 0 bis zur Kontrolle der Dose
SALT = SportProduct("on-electrolyte-forest-berry", "Optimum Nutrition Electrolyte Powder Forest Berry", "ON Electrolyte",
                    0.0, 0.0, "1 Portion (450 ml)", 8.0, sodium_mg=400.0)

PRODUCTS: tuple[SportProduct, ...] = (DRINK, JELLY_COLA, JELLY_MELON, GEL, SALT)
