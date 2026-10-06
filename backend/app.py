"""Flask-Application-Factory."""

import logging

from flask import Flask, send_from_directory

from backend.config import INSTANCE_DIR, REPO_ROOT, Config
from backend.extensions import db

logger = logging.getLogger(__name__)

FRONTEND_DIR = REPO_ROOT / "frontend" / "dashboard"
NUTRITION_DIR = REPO_ROOT / "frontend" / "ernaehrung"
TRAINING_DIR = REPO_ROOT / "frontend" / "training"
HELP_DIR = REPO_ROOT / "frontend" / "hilfe"


def create_app(config_class: type[Config] = Config) -> Flask:
    """Erstellt und konfiguriert die Flask-App.

    Args:
        config_class: Konfigurationsklasse (Config fuer normalen Betrieb,
            TestConfig fuer Tests).

    Returns:
        Konfigurierte Flask-App mit registrierten Extensions und Blueprints.
    """
    app = Flask(
        __name__,
        static_folder=str(FRONTEND_DIR),
        static_url_path="",
        instance_path=str(INSTANCE_DIR),
        instance_relative_config=True,
    )
    app.config.from_object(config_class)
    if not app.config.get("TESTING"):
        app.config.from_pyfile("config.py", silent=True)
    if app.config.get("PASSWORD_HASH") and not app.config.get("SECRET_KEY"):
        raise RuntimeError("PASSWORD_HASH gesetzt, aber SECRET_KEY fehlt (instance/config.py)")

    @app.get("/")
    def index():
        """Liefert das Dashboard."""
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.get("/ernaehrung/")
    @app.get("/ernaehrung/<path:filename>")
    def nutrition(filename: str = "index.html"):
        """Liefert die mobile Ernaehrungs-Seite (PWA)."""
        return send_from_directory(NUTRITION_DIR, filename)

    @app.get("/training/")
    @app.get("/training/<path:filename>")
    def training(filename: str = "index.html"):
        """Liefert die mobile Trainings-Seite (PWA)."""
        return send_from_directory(TRAINING_DIR, filename)

    @app.get("/hilfe/")
    @app.get("/hilfe/<path:filename>")
    def help_page(filename: str = "index.html"):
        """Liefert die Erklaer-Seite (Begriffe, Formeln, Regeln)."""
        return send_from_directory(HELP_DIR, filename)

    db.init_app(app)

    from backend.api.baseline_routes import baseline_bp
    from backend.api.calendar_routes import calendar_bp
    from backend.api.checkin_routes import checkins_bp
    from backend.api.food_log_routes import food_log_bp
    from backend.api.food_routes import foods_bp
    from backend.api.intake_routes import intake_bp
    from backend.api.meal_template_routes import meal_templates_bp
    from backend.api.plan_routes import plan_bp
    from backend.api.profile_routes import profile_bp
    from backend.api.intervals_routes import intervals_bp
    from backend.api.review_routes import review_bp

    app.register_blueprint(profile_bp)
    app.register_blueprint(checkins_bp)
    app.register_blueprint(baseline_bp)
    app.register_blueprint(intake_bp)
    app.register_blueprint(plan_bp)
    app.register_blueprint(foods_bp)
    app.register_blueprint(food_log_bp)
    app.register_blueprint(meal_templates_bp)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(review_bp)
    app.register_blueprint(intervals_bp)

    from backend.auth import register_auth
    from backend.backup import backup_db_command
    from backend.integrations.blv_import import import_blv_command

    register_auth(app)

    app.cli.add_command(import_blv_command)
    app.cli.add_command(backup_db_command)

    if not app.config.get("TESTING"):
        with app.app_context():
            db.create_all()

    return app
