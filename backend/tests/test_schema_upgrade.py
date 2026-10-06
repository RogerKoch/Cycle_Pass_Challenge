from sqlalchemy import inspect, text

from backend.app import add_missing_columns
from backend.extensions import db


def test_adds_missing_activity_level_column_to_existing_db(app):
    # Stand vor activity_level: Tabelle ohne die Spalte, mit einem bestehenden Profil
    db.session.execute(text("DROP TABLE user_profile"))
    db.session.execute(text(
        "CREATE TABLE user_profile (id INTEGER PRIMARY KEY, age INTEGER NOT NULL, height_cm FLOAT NOT NULL, "
        "program_start_date DATE NOT NULL, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL)"
    ))
    db.session.execute(text(
        "INSERT INTO user_profile VALUES (1, 49, 173, '2026-10-01', '2026-10-01 00:00:00', '2026-10-01 00:00:00')"
    ))
    db.session.commit()

    add_missing_columns()
    add_missing_columns()  # zweiter Lauf darf nichts tun

    assert "activity_level" in {c["name"] for c in inspect(db.engine).get_columns("user_profile")}
    assert db.session.execute(text("SELECT activity_level FROM user_profile")).scalar() == "buero"
