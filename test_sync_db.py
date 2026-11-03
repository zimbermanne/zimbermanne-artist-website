"""The database sync: Suno results and copied images are stored in the database and served from it."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app import db, main, music, sync

REAL_CLIENT = httpx.Client
NEW = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
IMG = b"\xff\xd8\xff" + b"fake-jpeg-bytes" * 20


def clip(cid, title, extra=""):
    return f'{{\\"id\\":\\"{cid}\\",\\"title\\":\\"{title}\\"{extra}}}'


PROFILE = ("<script>self.__next_f.push([1,\""
           + clip(NEW, "Brand New Song", f',\\"image_large_url\\":\\"https://cdn2.suno.ai/image_large_{NEW}.jpeg\\"')
           + "\"])</script>")


def wipe():
    with db.engine.begin() as c:
        c.execute(db.delete(db.media))
    db.save_overlay({}, [])
    music.invalidate()


@pytest.fixture(autouse=True)
def clean():
    wipe()
    yield
    wipe()


@pytest.fixture()
def suno(monkeypatch):
    state = {"blocked": False, "image_requests": 0}

    def handler(request):
        host, path = request.url.host, request.url.path
        if host.endswith("suno.ai"):
            state["image_requests"] += 1
            return httpx.Response(200, content=IMG, headers={"content-type": "image/jpeg"})
        if state["blocked"]:
            return httpx.Response(403, text="blocked")
        if path.startswith("/song/"):
            sid = path.rsplit("/", 1)[-1]
            return httpx.Response(200, text=f'<meta property="og:image" content="https://cdn2.suno.ai/image_large_{sid}.jpeg">')
        return httpx.Response(200, text=PROFILE)

    monkeypatch.setattr(sync.httpx, "Client", lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(sync, "REQUEST_DELAY", 0)
    return state


def all_tracks(data):
    return [t for a in data["albums"] for t in a["tracks"]]


def test_sync_stores_artwork_new_songs_and_image_copies(suno):
    result = sync.run_sync()
    assert result["ok"], result["summary"]
    data = music.load()
    tracks = all_tracks(data)
    assert all(t["image"].startswith("/media/") for t in tracks if "image" in t and not t["id"].startswith("new-"))
    assert sum(1 for t in tracks if t.get("image")) >= 20          # almost every track got artwork
    inbox = data["albums"][-1]
    assert inbox["id"] == music.INBOX_ID and inbox["tracks"][0]["title"] == "Brand New Song"
    assert inbox["tracks"][0]["image"].startswith("/media/")
    covers = [a["cover"] for a in data["albums"]]
    assert not any("cdn2.suno.ai" in c for c in covers)             # Suno covers now come from the database
    assert any(c == "/static/img/mimi-ni-odogwu.jpg" for c in covers)  # own files are left alone


def test_copied_image_is_served_from_the_database(suno):
    sync.run_sync()
    path = next(t["image"] for t in all_tracks(music.load()) if t.get("image", "").startswith("/media/"))
    r = TestClient(main.app).get(path)
    assert r.status_code == 200 and r.content == IMG
    assert r.headers["content-type"] == "image/jpeg"
    assert "immutable" in r.headers["cache-control"]


def test_second_run_copies_nothing_again_and_does_not_duplicate_songs(suno):
    sync.run_sync()
    copied = suno["image_requests"]
    result = sync.run_sync()
    assert suno["image_requests"] == copied and "0 copied" in result["summary"]
    assert [t["title"] for t in music.load()["albums"][-1]["tracks"]] == ["Brand New Song"]


def test_when_suno_is_blocked_earlier_results_are_kept(suno):
    sync.run_sync()
    suno["blocked"] = True
    result = sync.run_sync()
    assert not result["ok"] and "nothing could be read" in result["summary"]
    assert music.load()["albums"][-1]["tracks"][0]["title"] == "Brand New Song"
    assert db.list_sync_runs(1)[0]["ok"] is False


def test_a_song_moved_into_a_real_album_leaves_new_releases():
    base = {"albums": [{"id": "a", "cover": "/c.jpg", "tracks": [
        {"id": "t", "title": "Moved", "url": f"https://suno.com/song/{NEW}"}]}]}
    db.save_overlay({}, [{"song_id": NEW, "title": "Moved", "url": f"https://suno.com/song/{NEW}",
                          "audio_url": "x", "image": None}])
    out = music.build(base)
    assert [a["id"] for a in out["albums"]] == ["a"]


def test_a_manual_image_in_music_json_beats_the_synced_one():
    base = {"albums": [{"id": "a", "cover": "/c.jpg", "tracks": [
        {"id": "t1", "title": "Mine", "url": f"https://suno.com/song/{NEW}", "image": "/static/mine.jpg"}]}]}
    db.save_overlay({NEW: "https://cdn2.suno.ai/synced.jpeg"}, [])
    assert music.build(base)["albums"][0]["tracks"][0]["image"] == "/static/mine.jpg"


def test_image_copy_rejects_foreign_hosts_and_non_images(monkeypatch):
    def handler(request):
        return httpx.Response(200, content=b"<html>", headers={"content-type": "text/html"})
    client = REAL_CLIENT(transport=httpx.MockTransport(handler))
    assert sync.mirror_image(client, "https://evil.example.com/a.jpg").startswith("failed")
    assert sync.mirror_image(client, "https://cdn2.suno.ai/a.jpeg").startswith("failed: unsupported type")


def test_media_route_only_serves_known_hash_names():
    c = TestClient(main.app)
    assert c.get("/media/not-a-hash.jpg").status_code == 404
    assert c.get("/media/0123456789abcdef.jpg").status_code == 404


def test_admin_sync_routes_need_the_token(monkeypatch, suno):
    c = TestClient(main.app)
    monkeypatch.setattr(main, "ADMIN_TOKEN", "")
    assert c.post("/admin/sync").status_code == 404
    monkeypatch.setattr(main, "ADMIN_TOKEN", "secret")
    assert c.post("/admin/sync").status_code == 401
    assert c.get("/admin/sync", headers={"Authorization": "Bearer wrong"}).status_code == 401
    ok = c.post("/admin/sync", headers={"Authorization": "Bearer secret"})
    assert ok.status_code == 202
    status = c.get("/admin/sync", headers={"Authorization": "Bearer secret"})
    assert status.status_code == 200 and status.json()["runs"][0]["ok"] is True
