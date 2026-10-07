import sqlite3

import pytest

from backend.app import create_app
from backend.backup import backup_database, backup_db_command
from backend.config import TestConfig


def _make_db(path):
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE checkins (weight_kg REAL)")
        connection.execute("INSERT INTO checkins VALUES (74.0)")
    connection.close()


def test_backup_contains_current_data(tmp_path):
    source = tmp_path / "app.db"
    _make_db(source)
    backup = backup_database(source, tmp_path / "backups")
    with sqlite3.connect(backup) as connection:
        assert connection.execute("SELECT weight_kg FROM checkins").fetchall() == [(74.0,)]
    connection.close()


def test_keeps_only_newest_backups(tmp_path):
    source = tmp_path / "app.db"
    _make_db(source)
    target = tmp_path / "backups"
    target.mkdir()
    for day in ("2026-10-01", "2026-10-02", "2026-10-03"):
        (target / f"alpenpaesse-{day}_030000.db").write_bytes(b"")
    newest = backup_database(source, target, keep=2)
    assert sorted(p.name for p in target.iterdir()) == ["alpenpaesse-2026-10-03_030000.db", newest.name]


def test_backup_command_writes_file(tmp_path):
    db_file = tmp_path / "app.db"
    _make_db(db_file)

    class FileConfig(TestConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_file}"

    result = create_app(FileConfig).test_cli_runner().invoke(backup_db_command, ["--target", str(tmp_path / "out")])
    assert result.exit_code == 0, result.output
    assert len(list((tmp_path / "out").glob("alpenpaesse-*.db"))) == 1


def test_missing_source_raises_and_creates_no_backup(tmp_path):
    with pytest.raises(sqlite3.OperationalError):
        backup_database(tmp_path / "missing.db", tmp_path / "backups")
    assert not (tmp_path / "missing.db").exists()
    assert list((tmp_path / "backups").iterdir()) == []


def test_failed_backup_leaves_no_partial_file(tmp_path, monkeypatch):
    source = tmp_path / "app.db"
    _make_db(source)

    real_connect = sqlite3.connect

    class Failing(sqlite3.Connection):
        def backup(self, target, **kwargs):
            raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(sqlite3, "connect", lambda *a, **k: real_connect(*a, factory=Failing, **k))
    with pytest.raises(sqlite3.OperationalError):
        backup_database(source, tmp_path / "backups")
    assert list((tmp_path / "backups").iterdir()) == []
