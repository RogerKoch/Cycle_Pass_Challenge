from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class Config:
    """Default configuration: SQLite database at the repo root."""

    SQLALCHEMY_DATABASE_URI = f"sqlite:///{REPO_ROOT / 'alpenpaesse.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class TestConfig(Config):
    """Configuration for tests: in-memory SQLite database."""

    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
