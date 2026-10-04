"""Import der Schweizer Naehrwertdatenbank (BLV, naehrwertdaten.ch) in die Tabelle `foods`.

Quelle: Schweizer Naehrwertdatenbank, Bundesamt fuer Lebensmittelsicherheit und Veterinaerwesen
(BLV). Nutzung inkl. Ernaehrungstagebuch-Apps mit Quellenvermerk erlaubt.
"""

import logging
from pathlib import Path

import click
import openpyxl
from flask.cli import with_appcontext

from backend.engine.food_calc import normalize_search
from backend.extensions import db
from backend.models.food import Food

logger = logging.getLogger(__name__)

SHEETS: tuple[str, ...] = ("Generische Lebensmittel", "Markenprodukte")
HEADER_ROW = 3  # Zeile 1 = Titel, Zeile 2 leer
COLUMNS: dict[str, str] = {
    "ID": "source_id",
    "Name": "name",
    "Synonyme": "synonyms",
    "Kategorie": "category",
    "Energie, Kilokalorien (kcal)": "kcal_100g",
    "Protein (g)": "protein_100g",
    "Kohlenhydrate, verfügbar (g)": "carbs_100g",
    "Fett, total (g)": "fat_100g",
}
NUTRIENT_FIELDS: tuple[str, ...] = ("kcal_100g", "protein_100g", "carbs_100g", "fat_100g")


def _to_number(value: object) -> float:
    """BLV-Zellwert als Zahl; 'Sp.' (Spuren), '<0.5' und leere Zellen zaehlen als 0."""
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def read_blv_rows(path: Path) -> list[dict]:
    """Liest alle Lebensmittel aus den BLV-Sheets.

    Args:
        path: Pfad zur BLV-Excel-Datei.

    Returns:
        Liste von Dicts mit den Feldern aus COLUMNS (Naehrwerte als float).

    Raises:
        ValueError: wenn eine erwartete Spalte fehlt.
    """
    workbook = openpyxl.load_workbook(path, read_only=True)
    rows: list[dict] = []
    for sheet_name in SHEETS:
        sheet_rows = workbook[sheet_name].iter_rows(min_row=HEADER_ROW, values_only=True)
        header = list(next(sheet_rows, ()))
        missing = [col for col in COLUMNS if col not in header]
        if missing:
            raise ValueError(f"Sheet '{sheet_name}': Spalten fehlen: {missing}")
        index = {field: header.index(col) for col, field in COLUMNS.items()}
        for raw in sheet_rows:
            if raw[index["source_id"]] is None:
                continue
            row = {field: raw[i] for field, i in index.items()}
            row["source_id"] = str(row["source_id"])
            for field in NUTRIENT_FIELDS:
                row[field] = _to_number(row[field])
            rows.append(row)
    workbook.close()
    return rows


def import_blv(path: Path) -> tuple[int, int]:
    """Upsert aller BLV-Lebensmittel (Schluessel: source='blv', source_id). Eigene Portionen bleiben erhalten.

    Returns:
        (neu angelegt, aktualisiert)
    """
    existing = {f.source_id: f for f in Food.query.filter_by(source="blv")}
    created = updated = 0
    for row in read_blv_rows(path):
        synonyms = row.pop("synonyms") or ""
        row["search_name"] = normalize_search(f"{row['name']} {synonyms}")
        food = existing.get(row["source_id"])
        if food is None:
            db.session.add(Food(source="blv", **row))
            created += 1
        else:
            for key, value in row.items():
                setattr(food, key, value)
            updated += 1
    db.session.commit()
    logger.info("BLV-Import: %d neu, %d aktualisiert", created, updated)
    return created, updated


@click.command("import-blv")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@with_appcontext
def import_blv_command(path: Path) -> None:
    """Importiert die BLV-Naehrwertdatenbank (Excel) in die Tabelle foods."""
    created, updated = import_blv(path)
    click.echo(f"BLV-Import: {created} neu, {updated} aktualisiert")
