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


import asyncio
import shutil
import subprocess

import httpx

from app import audio


@pytest.fixture()
def suno(monkeypatch, tmp_path):
    """Fake Suno CDN: .mp3 -> 404 unless set, .mp4 -> an AAC-in-MP4 stream. Counts every request."""
    monkeypatch.setattr(audio, "CACHE_DIR", tmp_path / "cache")
    exe = audio.ffmpeg_path()
    if not exe:
        pytest.skip("ffmpeg not available")
    mp4 = tmp_path / "tone.mp4"
    subprocess.run([exe, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                    "-c:a", "aac", str(mp4)], check=True)
    state = {"mp3": None, "mp4": mp4.read_bytes(), "hits": []}

    def handler(request):
        url = str(request.url)
        state["hits"].append(url)
        body, ctype = (state["mp3"], "audio/mpeg") if url.endswith(".mp3") else (state["mp4"], "video/mp4")
        if body is None:
            return httpx.Response(404)
        return httpx.Response(200, stream=httpx.ByteStream(body), headers={"content-type": ctype})

    monkeypatch.setattr(audio, "http_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    return state


def test_download_captures_stream_and_converts_to_real_mp3(client, suno):
    slug = music.all_slugs()[0]
    r = client.get(f"/download/{slug}.mp3")  # default Accept-Encoding: gzip must not touch it
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg"
    assert r.content[:3] == b"ID3" and b"Zimbermanne" in r.content[:600]  # a real MP3 with tags
    assert r.headers["content-length"] == str(len(r.content))
    assert "attachment" in r.headers["content-disposition"] and "Zimbermanne.mp3" in r.headers["content-disposition"]
    assert any(u.endswith(".mp3") for u in suno["hits"]) and any(u.endswith(".mp4") for u in suno["hits"])


def test_second_download_comes_from_cache(client, suno):
    slug = music.all_slugs()[1]
    assert client.get(f"/download/{slug}.mp3").status_code == 200
    n = len(suno["hits"])
    assert client.get(f"/download/{slug}.mp3").status_code == 200
    assert len(suno["hits"]) == n  # nothing fetched again


def test_plain_mp3_from_suno_is_passed_through(client, suno):
    suno["mp3"] = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xff\xfb" * 500
    r = client.get(f"/download/{music.all_slugs()[2]}.mp3")
    assert r.status_code == 200 and r.content == suno["mp3"]
    assert not any(u.endswith(".mp4") for u in suno["hits"])  # no conversion needed


def test_simultaneous_requests_convert_once(suno):
    track = music.get_song(music.all_slugs()[3])["track"]

    async def both():
        return await asyncio.gather(audio.ensure_mp3(track, "A"), audio.ensure_mp3(track, "A"))

    p1, p2 = asyncio.run(both())
    assert p1 == p2 and len([u for u in suno["hits"] if u.endswith(".mp4")]) == 1


def test_download_handles_missing_song_and_dead_source(client, suno):
    assert client.get("/download/does-not-exist.mp3").status_code == 404
    suno["mp4"] = None
    suno["hits"].clear()
    assert client.get(f"/download/{music.all_slugs()[4]}.mp3").status_code == 502


def test_download_links_and_robots(client):
    slug = music.all_slugs()[0]
    assert f'href="/download/{slug}.mp3"' in client.get("/").text
    assert "Download MP3" in client.get(f"/song/{slug}").text
    assert "Disallow: /download/" in client.get("/robots.txt").text


def test_player_has_phone_controls(client):
    html = client.get("/").text
    for needle in ('id="playerExpand"', 'id="prevBtn"', 'id="nextBtn"', 'id="miniProgress"', 'id="playerCollapse"', 'role="slider"'):
        assert needle in html
    assert "viewport-fit=cover" in html
    css = client.get("/static/style.css").text
    assert ".player-bar.expanded" in css and "env(safe-area-inset-bottom)" in css
