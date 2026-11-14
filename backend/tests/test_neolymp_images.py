import json

import pytest

from backend.api.exercise_routes import NEOLYMP_MANIFEST
from backend.app import create_app
from backend.extensions import db
from backend.tests.test_auth import AuthTestConfig, login

NAME = "Brustpresse mit Bänderstange"


@pytest.fixture()
def instance_dir(tmp_path):
    (tmp_path / "neolymp" / "images").mkdir(parents=True)
    (tmp_path / "neolymp" / "images" / "brustpresse-1.jpg").write_bytes(b"jpg")
    (tmp_path / "neolymp" / "index.json").write_text(json.dumps({NAME: ["brustpresse-1.jpg"]}), encoding="utf-8")
    return tmp_path


@pytest.fixture()
def secured_client(instance_dir):
    application = create_app(AuthTestConfig)
    application.instance_path = str(instance_dir)
    with application.app_context():
        db.create_all()
        yield application.test_client()
        db.session.remove()
        db.drop_all()


def test_image_requires_login(secured_client):
    assert secured_client.get("/api/exercises/neolymp-image/brustpresse-1.jpg").status_code == 401


def test_image_is_served_after_login(secured_client):
    login(secured_client)
    response = secured_client.get("/api/exercises/neolymp-image/brustpresse-1.jpg")
    assert (response.status_code, response.data) == (200, b"jpg")


def test_image_rejects_path_traversal_and_missing_files(secured_client):
    login(secured_client)
    assert secured_client.get("/api/exercises/neolymp-image/../index.json").status_code == 404
    assert secured_client.get("/api/exercises/neolymp-image/nope.jpg").status_code == 404


def test_illustrations_merge_repo_index_with_neolymp_images(secured_client):
    login(secured_client)
    body = secured_client.get("/api/exercises/illustrations").get_json()
    assert body[NAME]["srcs"] == ["../api/exercises/neolymp-image/brustpresse-1.jpg"]
    assert body[NAME]["video"]
    assert body["Bird Dog"]["img"] == "bird-dog.svg"  # Repo-Eintrag bleibt


def test_illustrations_without_instance_images_keep_video_links(client, tmp_path):
    client.application.instance_path = str(tmp_path)  # kein neolymp-Ordner
    body = client.get("/api/exercises/illustrations").get_json()
    assert "srcs" not in body[NAME] and body[NAME]["video"]


def test_manifest_entries_have_video_queries():
    manifest = json.loads(NEOLYMP_MANIFEST.read_text(encoding="utf-8"))
    assert manifest and all(entry["video"].strip() for entry in manifest.values())
