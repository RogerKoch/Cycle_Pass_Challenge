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
    assert db.session.execute(text("SELECT strength_focus FROM user_profile")).scalar() == "none"
    assert db.session.execute(text("SELECT benchmark_interval_weeks FROM user_profile")).scalar() == 4
    assert db.session.execute(text("SELECT equipment_missing FROM user_profile")).scalar() == ""


def test_adds_status_column_and_old_log_entries_count_as_eaten(app):
    db.session.execute(text("DROP TABLE food_log_entries"))
    db.session.execute(text(
        "CREATE TABLE food_log_entries (id INTEGER PRIMARY KEY, entry_date DATE NOT NULL, meal VARCHAR(20) NOT NULL, "
        "food_id INTEGER, grams FLOAT, label VARCHAR(200) NOT NULL, kcal FLOAT NOT NULL, protein_g FLOAT NOT NULL, "
        "carbs_g FLOAT NOT NULL, fat_g FLOAT NOT NULL, created_at DATETIME NOT NULL)"
    ))
    db.session.execute(text(
        "INSERT INTO food_log_entries VALUES (1, '2026-10-01', 'snack', NULL, NULL, 'Gel', 100, 0, 25, 0, '2026-10-01 00:00:00')"
    ))
    db.session.commit()

    add_missing_columns()

    assert "status" in {c["name"] for c in inspect(db.engine).get_columns("food_log_entries")}
    assert db.session.execute(text("SELECT status FROM food_log_entries")).scalar() == "eaten"
