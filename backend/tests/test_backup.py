import sqlite3

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
