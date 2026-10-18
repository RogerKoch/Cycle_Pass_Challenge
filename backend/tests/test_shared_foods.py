import sqlite3

from backend.app import create_app
from backend.config import TestConfig
from backend.extensions import db
from backend.models.food import Food, MealTemplate, MealTemplateItem
from backend.shared_foods import copy_legacy_tables

LEGACY_DDL = (
    "CREATE TABLE foods (id INTEGER PRIMARY KEY, name VARCHAR(200) NOT NULL, category VARCHAR(200), "
    "kcal_100g FLOAT NOT NULL, protein_100g FLOAT NOT NULL, carbs_100g FLOAT NOT NULL, fat_100g FLOAT NOT NULL, "
    "source VARCHAR(10) NOT NULL, source_id VARCHAR(50), search_name VARCHAR(400) NOT NULL, "
    "portion_label VARCHAR(50), portion_g FLOAT, use_count INTEGER NOT NULL)",
    "CREATE TABLE meal_templates (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, meal VARCHAR(20) NOT NULL)",
    "CREATE TABLE meal_template_items (id INTEGER PRIMARY KEY, template_id INTEGER NOT NULL, "
    "food_id INTEGER NOT NULL, grams FLOAT NOT NULL)",
    "INSERT INTO foods VALUES (7, 'Haferflocken', NULL, 370, 13, 60, 7, 'custom', 'c1', 'haferflocken', NULL, NULL, 2)",
    "INSERT INTO meal_templates VALUES (3, 'Standard', 'fruehstueck')",
    "INSERT INTO meal_template_items VALUES (1, 3, 7, 80)",
)


def _file_app(tmp_path, main_name):
    class FileConfig(TestConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / main_name}"
        SHARED_DB_PATH = str(tmp_path / "shared.db")

    return create_app(FileConfig)


def _legacy_db(path):
    connection = sqlite3.connect(path)
    for statement in LEGACY_DDL:
        connection.execute(statement)
    connection.commit()
    connection.close()


def test_legacy_foods_and_templates_are_copied_once_with_same_ids(tmp_path):
    _legacy_db(tmp_path / "main.db")
    app = _file_app(tmp_path, "main.db")
    with app.app_context():
        db.create_all()
        assert copy_legacy_tables() == {"foods": 1, "meal_templates": 1, "meal_template_items": 1}
        assert copy_legacy_tables() == {}
        assert db.session.get(Food, 7).name == "Haferflocken"
        assert db.session.get(MealTemplate, 3).items[0].food_id == 7
        db.session.remove()
        db.engine.dispose()


def test_second_instance_sees_foods_and_templates_added_by_the_first(tmp_path):
    first = _file_app(tmp_path, "a.db")
    with first.app_context():
        db.create_all()
        food = Food(name="Skyr", kcal_100g=63, protein_100g=11, carbs_100g=4, fat_100g=0.2, source="custom",
                    search_name="skyr")
        db.session.add(food)
        db.session.flush()
        template = MealTemplate(name="Zmorge", meal="fruehstueck", items=[MealTemplateItem(food_id=food.id, grams=200)])
        db.session.add(template)
        db.session.commit()
        db.session.remove()
        db.engine.dispose()

    second = _file_app(tmp_path, "b.db")
    with second.app_context():
        db.create_all()
        assert copy_legacy_tables() == {}  # frische DB ohne Alt-Tabellen
        assert Food.query.one().name == "Skyr"
        assert MealTemplate.query.one().items[0].food.name == "Skyr"
        db.session.remove()
        db.engine.dispose()


def test_fresh_instance_with_empty_shared_db_copies_nothing(tmp_path):
    app = _file_app(tmp_path, "fresh.db")
    with app.app_context():
        db.create_all()
        assert copy_legacy_tables() == {}
        assert Food.query.count() == 0
        db.session.remove()
        db.engine.dispose()
