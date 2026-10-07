"""Backup der SQLite-Datenbank (CLI `flask backup-db`).

Die Kopie laeuft ueber die SQLite-Backup-API und ist damit auch bei laufender App konsistent.
Zeitplan und Offsite-Kopie (rclone -> Google Drive) liegen im Repo server-infra.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

import click
from flask.cli import with_appcontext

from backend.config import REPO_ROOT
from backend.extensions import db

logger = logging.getLogger(__name__)

BACKUP_PREFIX = "alpenpaesse-"
DEFAULT_BACKUP_DIR = REPO_ROOT / "backups"
DEFAULT_KEEP = 30


def backup_database(db_path: Path, target_dir: Path, keep: int = DEFAULT_KEEP) -> Path:
    """Schreibt eine konsistente Kopie der Datenbank und behaelt nur die neuesten Backups.

    Args:
        db_path: Pfad der SQLite-Datei.
        target_dir: Zielordner (wird angelegt).
        keep: Anzahl Backups, die behalten werden (aelteste werden geloescht).

    Returns:
        Pfad der neuen Backup-Datei.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{BACKUP_PREFIX}{datetime.now():%Y-%m-%d_%H%M%S_%f}.db"
    partial = target.with_suffix(".db.part")  # passt nicht auf das Rotations-Muster *.db
    # read-only per URI: connect() legt sonst bei falschem Pfad still eine leere DB an
    source = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    destination = sqlite3.connect(partial)
    try:
        with destination:
            source.backup(destination)
    except BaseException:
        destination.close()
        source.close()
        partial.unlink(missing_ok=True)
        raise
    destination.close()
    source.close()
    partial.replace(target)

    # Zeitstempel im Namen -> alphabetisch = chronologisch
    for old in sorted(target_dir.glob(f"{BACKUP_PREFIX}*.db"))[:-keep]:
        old.unlink()
        logger.info("Altes Backup geloescht: %s", old.name)
    return target


@click.command("backup-db")
@click.option("--target", type=click.Path(file_okay=False, path_type=Path), default=DEFAULT_BACKUP_DIR,
              show_default=True, help="Zielordner")
@click.option("--keep", type=click.IntRange(min=1), default=DEFAULT_KEEP, show_default=True,
              help="Anzahl Backups, die behalten werden")
@with_appcontext
def backup_db_command(target: Path, keep: int) -> None:
    """Sichert die App-Datenbank in den Zielordner."""
    path = backup_database(Path(db.engine.url.database), target, keep)
    click.echo(f"Backup: {path}")
