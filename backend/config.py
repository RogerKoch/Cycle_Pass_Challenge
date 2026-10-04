from datetime import timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTANCE_DIR = REPO_ROOT / "instance"


class Config:
    """Default configuration: SQLite database at the repo root.

    Secrets (SECRET_KEY, PASSWORD_HASH) kommen aus instance/config.py (nicht versioniert).
    Ohne PASSWORD_HASH ist der Login deaktiviert (lokale Entwicklung).
    """

    SQLALCHEMY_DATABASE_URI = f"sqlite:///{REPO_ROOT / 'alpenpaesse.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SECRET_KEY: str | None = None
    PASSWORD_HASH: str | None = None
    SESSION_COOKIE_NAME = "cpc_session"  # eindeutig, da mehrere Projekte unter derselben IP laufen
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(days=365)


class TestConfig(Config):
    """Configuration for tests: in-memory SQLite database."""

    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    SESSION_COOKIE_SECURE = False
