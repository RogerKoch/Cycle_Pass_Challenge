"""Geteilte Lebensmittel und Mahlzeit-Vorlagen: eigene SQLite-Datei als Schema `shared`.

Jede Instanz haengt dieselbe Datei beim Verbindungsaufbau an (ATTACH). Bestehende Daten aus der
Haupt-DB werden einmalig kopiert (mit gleichen IDs, damit Tagebuch-Eintraege und Vorlagen gueltig
bleiben); die alten Tabellen bleiben als Sicherung stehen.
"""

import logging
from pathlib import Path

import click
from flask import Flask
from flask.cli import with_appcontext
from sqlalchemy import event, inspect, text
from sqlalchemy.engine import Engine

from backend.extensions import db
from backend.models.food import SHARED_SCHEMA, Food, MealTemplate, MealTemplateItem

logger = logging.getLogger(__name__)

# Elterntabellen vor den Kindern
SHARED_MODELS = (Food, MealTemplate, MealTemplateItem)


def attach_shared_db(engine: Engine, path: str | Path) -> None:
    """Haengt die geteilte DB bei jeder neuen Verbindung unter dem Alias `shared` an.

    Args:
        engine: SQLite-Engine der App.
        path: Pfad der geteilten Datei (oder ":memory:" fuer Tests).
    """

    @event.listens_for(engine, "connect")
    def _attach(dbapi_connection, _record) -> None:
        dbapi_connection.execute(f"ATTACH DATABASE ? AS {SHARED_SCHEMA}", (str(path),))


def copy_legacy_tables() -> dict[str, int]:
    """Kopiert Lebensmittel und Vorlagen aus der Haupt-DB in `shared`, sofern dort noch leer.

    Returns:
        Tabellenname -> Anzahl kopierter Zeilen (leer, wenn nichts zu tun war).
    """
    inspector = inspect(db.engine)
    copied: dict[str, int] = {}
    for model in SHARED_MODELS:
        table = model.__table__.name
        if not inspector.has_table(table, schema="main"):  # Haupt-DB ohne Alt-Tabelle (zweite Instanz, frische DB)
            continue
        if db.session.execute(text(f"SELECT 1 FROM {SHARED_SCHEMA}.{table} LIMIT 1")).first() is not None:
            continue
        legacy_columns = {c["name"] for c in inspector.get_columns(table, schema="main")}
        columns = ", ".join(c.name for c in model.__table__.columns if c.name in legacy_columns)
        result = db.session.execute(
            text(f"INSERT INTO {SHARED_SCHEMA}.{table} ({columns}) SELECT {columns} FROM main.{table}")
        )
        if result.rowcount:
            copied[table] = result.rowcount
            logger.info("%d Zeilen aus %s nach %s.%s kopiert", result.rowcount, table, SHARED_SCHEMA, table)
    db.session.commit()
    return copied


@click.command("copy-shared-foods")
@with_appcontext
def copy_shared_foods_command() -> None:
    """Kopiert Alt-Lebensmittel und -Vorlagen der Haupt-DB in die geteilte DB (laeuft auch beim Start)."""
    copied = copy_legacy_tables()
    click.echo(", ".join(f"{t}: {n}" for t, n in copied.items()) or "nichts zu kopieren")


def register_shared_foods(app: Flask) -> None:
    """Haengt die geteilte DB an die Engine; muss nach db.init_app laufen."""
    with app.app_context():
        attach_shared_db(db.engine, app.config["SHARED_DB_PATH"])
    app.cli.add_command(copy_shared_foods_command)
