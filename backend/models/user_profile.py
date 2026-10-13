"""Nutzerprofil (Einzelperson, kein Multi-User-System)."""

from datetime import date, datetime, timezone

from backend.extensions import db


class UserProfile(db.Model):
    """Statische Profildaten. Es existiert immer maximal eine Zeile."""

    __tablename__ = "user_profile"

    id: int = db.Column(db.Integer, primary_key=True)
    age: int = db.Column(db.Integer, nullable=False)
    height_cm: float = db.Column(db.Float, nullable=False)
    program_start_date: date = db.Column(db.Date, nullable=False)
    # Alltags-/Beruf-Stufe, Schluessel aus engine.nutrition_calc.ACTIVITY_LEVELS
    activity_level: str = db.Column(db.String(20), nullable=False, default="buero", server_default="buero")
    # Kraft-Fokus, Schluessel aus engine.strength_sessions.FOCUS_OPTIONS
    strength_focus: str = db.Column(db.String(20), nullable=False, default="none", server_default="none")
    # Kraft-Benchmark alle N Wochen (engine.strength_benchmarks, Standard 4)
    benchmark_interval_weeks: int = db.Column(db.Integer, nullable=False, default=4, server_default="4")
    # Fehlendes Material, kommagetrennt, Schluessel aus engine.strength_alternatives.EQUIPMENT_OPTIONS
    equipment_missing: str = db.Column(db.String(100), nullable=False, default="", server_default="")
    # Wochentage (0 = Mo ... 6 = So), an denen nach der Arbeit trainiert wird; Standard Di–Fr
    evening_training_days: str = db.Column(db.String(20), nullable=False, default="1,2,3,4", server_default="1,2,3,4")
    # Zielgewicht in kg, falls als Gewicht (statt Ziel-Koerperfett) eingegeben; sonst None
    target_weight_kg: float | None = db.Column(db.Float, nullable=True)
    created_at: datetime = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
