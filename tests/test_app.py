import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(tempfile.mkdtemp())  # local SQLite goes to a throwaway data/ folder
os.environ.update(ADMIN_TOKEN="secret", WHATSAPP_NUMBER="+255 700 000 000", PLAUSIBLE_DOMAIN="example.com")

from fastapi.testclient import TestClient  # noqa: E402

from app import db, music  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_slugs_are_unique():
    slugs = music.all_slugs() or (music.load() and music.all_slugs())
    assert len(slugs) == len(set(slugs)) > 0
    assert "taarifa-yako" in slugs and "taarifa-yako-2" in slugs


def test_home_has_whatsapp_analytics_and_jsonld(client):
    html = client.get("/").text
    assert "wa.me/255700000000" in html and "plausible.io" in html and '"MusicAlbum"' in html


def test_song_page_and_404(client):
    r = client.get("/song/mimi-ni-odogwu")
    assert r.status_code == 200 and "MusicRecording" in r.text and 'og:type" content="music.song"' in r.text
    assert client.get("/song/does-not-exist").status_code == 404


def test_sitemap_lists_every_song(client):
    xml = client.get("/sitemap.xml").text
    assert xml.count("/song/") == len(music.all_slugs())


def test_subscribe_unsubscribe_and_export(client):
    r = client.post("/subscribe", data={"email": "Fan@Example.com"}, follow_redirects=False)
    assert r.status_code == 303 and "subscribed" in r.headers["location"]
    client.post("/subscribe", data={"email": "fan@example.com"})            # duplicate: still one row
    assert [x["email"] for x in db.list_subscribers()] == ["fan@example.com"]

    assert client.get("/admin/subscribers.csv").status_code == 401
    csv_text = client.get("/admin/subscribers.csv", headers={"Authorization": "Bearer secret"}).text
    assert "fan@example.com" in csv_text

    import sqlalchemy as sa
    with db.engine.connect() as c:
        token = c.execute(sa.select(db.subscribers.c.token)).scalar()
    assert db.list_subscribers()                                            # GET alone must not unsubscribe
    client.get(f"/unsubscribe/{token}")
    assert db.list_subscribers()
    assert client.post(f"/unsubscribe/{token}").status_code == 200
    assert db.list_subscribers() == []
    assert client.get("/unsubscribe/not-a-token").status_code == 404


def test_bad_subscribe_email(client):
    r = client.post("/subscribe", data={"email": "nope"}, follow_redirects=False)
    assert "badsub" in r.headers["location"]
