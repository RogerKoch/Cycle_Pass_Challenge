"""Lebensmittel, Tagebuch-Eintraege und Mahlzeit-Vorlagen.

Lebensmittel und Mahlzeit-Vorlagen liegen im angehaengten Schema `shared` (eigene SQLite-Datei, siehe
backend.shared_foods) und gelten fuer alle Instanzen; das Tagebuch bleibt je Instanz in der Haupt-DB.
"""

from datetime import date, datetime, timezone

from backend.extensions import db

MEALS: tuple[str, ...] = ("fruehstueck", "mittag", "abend", "snack", "training")
SHARED_SCHEMA = "shared"
FOOD_SOURCES: tuple[str, ...] = ("blv", "custom", "off")
ENTRY_STATUSES: tuple[str, ...] = ("eaten", "planned")  # planned zaehlt nie als Ist


class Food(db.Model):
    """Lebensmittel mit Naehrwerten pro 100 g. Quelle: BLV-Datenbank, Open Food Facts oder eigene Eingabe."""

    __tablename__ = "foods"
    __table_args__ = (db.UniqueConstraint("source", "source_id"), {"schema": SHARED_SCHEMA})

    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String(200), nullable=False)
    category: str | None = db.Column(db.String(200))
    kcal_100g: float = db.Column(db.Float, nullable=False)
    protein_100g: float = db.Column(db.Float, nullable=False)
    carbs_100g: float = db.Column(db.Float, nullable=False)
    fat_100g: float = db.Column(db.Float, nullable=False)
    source: str = db.Column(db.String(10), nullable=False)
    source_id: str | None = db.Column(db.String(50))
    search_name: str = db.Column(db.String(400), nullable=False, index=True)
    portion_label: str | None = db.Column(db.String(50))
    portion_g: float | None = db.Column(db.Float)
    use_count: int = db.Column(db.Integer, nullable=False, default=0)


class FoodLogEntry(db.Model):
    """Ein Tagebuch-Eintrag. Naehrwerte sind ein Snapshot zum Erfassungszeitpunkt;
    Schnelleintraege haben keine food_id und keine Menge. status=planned: vorgeplant, noch nicht gegessen."""

    __tablename__ = "food_log_entries"

    id: int = db.Column(db.Integer, primary_key=True)
    entry_date: date = db.Column(db.Date, nullable=False, index=True)
    meal: str = db.Column(db.String(20), nullable=False)
    food_id: int | None = db.Column(db.Integer, db.ForeignKey(f"{SHARED_SCHEMA}.foods.id"))
    grams: float | None = db.Column(db.Float)
    label: str = db.Column(db.String(200), nullable=False)
    kcal: float = db.Column(db.Float, nullable=False)
    protein_g: float = db.Column(db.Float, nullable=False)
    carbs_g: float = db.Column(db.Float, nullable=False)
    fat_g: float = db.Column(db.Float, nullable=False)
    status: str = db.Column(db.String(10), nullable=False, default="eaten", server_default="eaten")
    created_at: datetime = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    food = db.relationship(Food)


class MealTemplate(db.Model):
    """Wiederverwendbare Mahlzeit (z.B. "Fruehstueck Standard")."""

    __tablename__ = "meal_templates"
    __table_args__ = {"schema": SHARED_SCHEMA}

    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String(100), nullable=False)
    meal: str = db.Column(db.String(20), nullable=False)

    items = db.relationship("MealTemplateItem", cascade="all, delete-orphan", order_by="MealTemplateItem.id")


class MealTemplateItem(db.Model):
    """Ein Lebensmittel mit Menge innerhalb einer Vorlage."""

    __tablename__ = "meal_template_items"
    __table_args__ = {"schema": SHARED_SCHEMA}

    id: int = db.Column(db.Integer, primary_key=True)
    template_id: int = db.Column(db.Integer, db.ForeignKey(f"{SHARED_SCHEMA}.meal_templates.id"), nullable=False)
    food_id: int = db.Column(db.Integer, db.ForeignKey(f"{SHARED_SCHEMA}.foods.id"), nullable=False)
    grams: float = db.Column(db.Float, nullable=False)

    food = db.relationship(Food)
