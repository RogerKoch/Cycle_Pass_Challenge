import pytest
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash

from backend import auth
from backend.app import create_app
from backend.config import TestConfig
from backend.extensions import db

PASSWORD = "geheim-123"


class AuthTestConfig(TestConfig):
    SECRET_KEY = "test-secret"
    PASSWORD_HASH = generate_password_hash(PASSWORD)


@pytest.fixture()
def auth_app():
    auth._failed_logins.clear()
    application = create_app(AuthTestConfig)
    application.wsgi_app = ProxyFix(application.wsgi_app, x_prefix=1)
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def auth_client(auth_app):
    return auth_app.test_client()


def login(client, password=PASSWORD, next_path=None):
    url = "/login" if next_path is None else f"/login?next={next_path}"
    return client.post(url, data={"password": password})


def test_without_password_hash_everything_is_open(client):
    assert client.get("/api/foods").status_code == 200
    assert client.get("/").status_code == 200


def test_api_requires_login(auth_client):
    response = auth_client.get("/api/foods")
    assert response.status_code == 401
    assert response.get_json()["error"] == "nicht angemeldet"


def test_page_redirects_to_login_with_next(auth_client):
    response = auth_client.get("/ernaehrung/")
    assert response.status_code == 302
    assert response.headers["Location"] == "/login?next=/ernaehrung/"


def test_redirect_respects_forwarded_prefix(auth_client):
    response = auth_client.get("/ernaehrung/", headers={"X-Forwarded-Prefix": "/cpc"})
    assert response.headers["Location"] == "/cpc/login?next=/ernaehrung/"


def test_wrong_password_is_rejected(auth_client):
    response = login(auth_client, password="falsch")
    assert response.status_code == 401
    assert auth_client.get("/api/foods").status_code == 401


def test_correct_password_grants_access_with_permanent_named_cookie(auth_client):
    response = login(auth_client, next_path="/ernaehrung/")
    assert response.headers["Location"] == "/ernaehrung/"
    cookie = response.headers["Set-Cookie"]
    assert cookie.startswith("cpc_session=")
    assert "Expires=" in cookie
    assert auth_client.get("/api/foods").status_code == 200


def test_login_redirect_keeps_prefix(auth_client):
    response = auth_client.post("/login?next=/", data={"password": PASSWORD}, headers={"X-Forwarded-Prefix": "/cpc"})
    assert response.headers["Location"] == "/cpc/"


@pytest.mark.parametrize("target", ["https://evil.example", "//evil.example", "/\\evil.example"])
def test_external_next_is_ignored(auth_client, target):
    response = login(auth_client, next_path=target)
    assert response.headers["Location"] == "/"


def test_logout_ends_session(auth_client):
    login(auth_client)
    auth_client.post("/logout")
    assert auth_client.get("/api/foods").status_code == 401


@pytest.mark.parametrize("page", ["ernaehrung", "training"])
@pytest.mark.parametrize("filename", ["manifest.webmanifest", "icon.svg"])
def test_manifest_and_icon_are_public(auth_client, page, filename):
    assert auth_client.get(f"/{page}/{filename}").status_code == 200


def test_training_page_requires_login(auth_client):
    assert auth_client.get("/training/").status_code == 302


def test_password_hash_without_secret_key_fails_fast():
    class Broken(TestConfig):
        PASSWORD_HASH = generate_password_hash(PASSWORD)

    with pytest.raises(RuntimeError):
        create_app(Broken)


def test_help_page_requires_login(auth_client):
    assert auth_client.get("/hilfe/").status_code == 302


def test_profile_page_requires_login(auth_client):
    assert auth_client.get("/profil/").status_code == 302


def test_shared_files_require_login(auth_client):
    assert auth_client.get("/shared/nav.js").status_code == 302


def test_too_many_failed_logins_are_blocked_even_with_correct_password(auth_client):
    for _ in range(auth.FAILED_LOGIN_LIMIT):
        assert login(auth_client, password="falsch").status_code == 401
    assert login(auth_client, password="falsch").status_code == 429
    assert login(auth_client).status_code == 429


def test_failed_logins_expire_after_the_window(auth_client, monkeypatch):
    for _ in range(auth.FAILED_LOGIN_LIMIT):
        login(auth_client, password="falsch")
    monkeypatch.setattr(auth, "FAILED_LOGIN_WINDOW_S", -1.0)
    assert login(auth_client).status_code == 302
