"""Produktions-Einstieg: waitress hinter dem Reverse Proxy (Caddy), nur auf 127.0.0.1.

Port ueber Umgebungsvariable CPC_PORT (Default 8101). Secrets aus instance/config.py.
"""

import logging
import os
import sys

from waitress import serve
from werkzeug.middleware.proxy_fix import ProxyFix

from backend.app import create_app

logger = logging.getLogger(__name__)

DEFAULT_PORT = 8101


def main() -> None:
    """Startet die App; verweigert den Start ohne Login-Konfiguration."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = create_app()
    missing = [key for key in ("SECRET_KEY", "PASSWORD_HASH") if not app.config.get(key)]
    if missing:
        logger.error("Fehlt in instance/config.py: %s - Start abgebrochen", ", ".join(missing))
        sys.exit(1)
    # Caddy setzt X-Forwarded-For/-Proto/-Host und X-Forwarded-Prefix (z.B. /cpc)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    port = int(os.environ.get("CPC_PORT", DEFAULT_PORT))
    logger.info("Cycle Pass laeuft auf 127.0.0.1:%d", port)
    serve(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
