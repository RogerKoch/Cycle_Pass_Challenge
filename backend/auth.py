"""Einzel-Login (ein Passwort, Session-Cookie). Aktiv nur, wenn PASSWORD_HASH konfiguriert ist."""

import logging
import time

import click
from flask import Blueprint, Flask, current_app, jsonify, redirect, render_template_string, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)

FAILED_LOGIN_DELAY_S = 1.0
# iOS/Android laden Manifest und Icon ohne Cookie
PUBLIC_PWA_FILES: frozenset[str] = frozenset({"manifest.webmanifest", "icon.svg"})
PWA_ENDPOINTS: frozenset[str] = frozenset({"nutrition", "training"})

LOGIN_PAGE = """<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Anmelden</title>
  <style>
    body { font: 16px system-ui, sans-serif; max-width: 320px; margin: 15vh auto; padding: 0 16px; }
    input, button { width: 100%; font: inherit; padding: 10px; margin: 6px 0; box-sizing: border-box; }
    button { background: #2e7d32; color: #fff; border: 0; border-radius: 8px; }
    .msg { color: #b3261e; }
  </style>
</head>
<body>
  <h1>Anmelden</h1>
  <form method="post">
    <input name="password" type="password" placeholder="Passwort" autocomplete="current-password" autofocus required>
    <button type="submit">Anmelden</button>
  </form>
  {% if error %}<p class="msg">{{ error }}</p>{% endif %}
</body>
</html>"""


def _safe_next(target: str | None) -> str:
    """Nur relative Pfade innerhalb der App zulassen (kein Open Redirect)."""
    if not target or not target.startswith("/") or target.startswith("//") or "\\" in target:
        return "/"
    return target


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Login-Formular; bei Erfolg permanente Session und Redirect auf `next`."""
    if request.method == "GET":
        return render_template_string(LOGIN_PAGE, error=None)
    if check_password_hash(current_app.config["PASSWORD_HASH"] or "", request.form.get("password", "")):
        session.clear()
        session["logged_in"] = True
        session.permanent = True
        return redirect(request.script_root + _safe_next(request.args.get("next")))
    logger.warning("Fehlgeschlagener Login von %s", request.remote_addr)
    time.sleep(FAILED_LOGIN_DELAY_S)
    return render_template_string(LOGIN_PAGE, error="Falsches Passwort"), 401


@auth_bp.post("/logout")
def logout():
    """Beendet die Session."""
    session.clear()
    return redirect(url_for("auth.login"))


def require_login():
    """before_request-Guard: API ohne Session -> 401, Seiten -> Redirect auf /login."""
    if not current_app.config.get("PASSWORD_HASH") or session.get("logged_in"):
        return None
    if request.endpoint == "auth.login":
        return None
    if request.endpoint in PWA_ENDPOINTS and (request.view_args or {}).get("filename") in PUBLIC_PWA_FILES:
        return None
    if request.path.startswith("/api/"):
        return jsonify({"error": "nicht angemeldet"}), 401
    target = request.full_path.rstrip("?")
    return redirect(url_for("auth.login", next=target))


@click.command("hash-password")
def hash_password_command() -> None:
    """Fragt ein Passwort ab und gibt den Hash fuer PASSWORD_HASH in instance/config.py aus."""
    password = click.prompt("Passwort", hide_input=True, confirmation_prompt=True)
    click.echo(generate_password_hash(password))


def register_auth(app: Flask) -> None:
    """Registriert Login-Routen, Guard und CLI-Befehl."""
    app.register_blueprint(auth_bp)
    app.before_request(require_login)
    app.cli.add_command(hash_password_command)
