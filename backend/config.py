import os
from datetime import timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# Zweite Instanz (z.B. fuer eine weitere Person): eigenes Instance-Dir, eigene DB, eigenes Backup-Verzeichnis
INSTANCE_DIR = Path(os.environ.get("CPC_INSTANCE_DIR", REPO_ROOT / "instance"))
DB_PATH = Path(os.environ.get("CPC_DB_PATH", REPO_ROOT / "alpenpaesse.db"))
# Geteilte Lebensmittel und Mahlzeit-Vorlagen: eine SQLite-Datei, die alle Instanzen als Schema `shared` anhaengen
SHARED_DB_PATH = os.environ.get("CPC_SHARED_DB_PATH", str(REPO_ROOT / "shared_foods.db"))
BACKUP_DIR = Path(os.environ.get("CPC_BACKUP_DIR", REPO_ROOT / "backups"))


class Config:
    """Default configuration: SQLite database at the repo root.

    Secrets (SECRET_KEY, PASSWORD_HASH) kommen aus instance/config.py (nicht versioniert).
    Ohne PASSWORD_HASH ist der Login deaktiviert (lokale Entwicklung).
    """

    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_PATH}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SHARED_DB_PATH = SHARED_DB_PATH

    SECRET_KEY: str | None = None
    PASSWORD_HASH: str | None = None
    # eindeutig, da mehrere Projekte unter derselben IP laufen; weitere Instanzen setzen einen eigenen Namen
    # in instance/config.py
    SESSION_COOKIE_NAME = "cpc_session"
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(days=365)


class TestConfig(Config):
    """Configuration for tests: in-memory SQLite database."""

    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SHARED_DB_PATH = ":memory:"
    TESTING = True
    SESSION_COOKIE_SECURE = False
