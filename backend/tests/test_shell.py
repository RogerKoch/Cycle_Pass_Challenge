import re

import pytest

from backend.config import REPO_ROOT

FRONTEND = REPO_ROOT / "frontend"
PAGES = {"heute": "heute/index.html", "profil": "profil/index.html", "training": "training/index.html",
         "ernaehrung": "ernaehrung/index.html", "hilfe": "hilfe/index.html"}
NAV_KEYS = set(re.findall(r'key: "(\w+)"', (FRONTEND / "shared" / "nav.js").read_text(encoding="utf-8")))


@pytest.mark.parametrize("filename", ["shared.css", "nav.js"])
def test_shared_files_are_served(client, filename):
    assert client.get(f"/shared/{filename}").status_code == 200


@pytest.mark.parametrize("key", PAGES)
def test_every_page_registers_itself_in_the_navigation(key):
    html = (FRONTEND / PAGES[key]).read_text(encoding="utf-8")
    assert f'data-nav="{key}"' in html
    assert key in NAV_KEYS
    assert "shared/shared.css" in html and "shared/nav.js" in html


def test_every_navigation_entry_has_a_page():
    assert NAV_KEYS == set(PAGES)


def test_root_serves_today_and_profile_page_is_served(client):
    assert b'data-nav="heute"' in client.get("/").data
    response = client.get("/profil/")
    assert response.status_code == 200 and b'data-nav="profil"' in response.data
    assert client.get("/profil/app.js").status_code == 200
