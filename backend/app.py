"""Flask-Application-Factory."""

import logging

from flask import Flask

from backend.config import Config
from backend.extensions import db

logger = logging.getLogger(__name__)


def create_app(config_class: type[Config] = Config) -> Flask:
    """Erstellt und konfiguriert die Flask-App.

    Args:
        config_class: Konfigurationsklasse (Config fuer normalen Betrieb,
            TestConfig fuer Tests).

    Returns:
        Konfigurierte Flask-App mit registrierten Extensions und Blueprints.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    from backend.api.checkin_routes import checkins_bp
    from backend.api.plan_routes import plan_bp
    from backend.api.profile_routes import profile_bp

    app.register_blueprint(profile_bp)
    app.register_blueprint(checkins_bp)
    app.register_blueprint(plan_bp)

    if not app.config.get("TESTING"):
        with app.app_context():
            db.create_all()

    return app
