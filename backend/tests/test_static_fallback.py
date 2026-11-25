from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.staticfiles import FallbackStaticFiles


def make(tmp_path):
    server, site = tmp_path / "server", tmp_path / "site"
    (server / "img").mkdir(parents=True)
    (site / "img").mkdir(parents=True)
    (server / "img" / "both.jpg").write_bytes(b"from-server")
    (site / "img" / "both.jpg").write_bytes(b"from-site")
    (site / "img" / "cover.jpg").write_bytes(b"cover-bytes")
    (tmp_path / "secret.txt").write_text("private")
    app = FastAPI()
    app.mount("/static", FallbackStaticFiles(directory=server, fallback=site))
    return TestClient(app)


def test_a_file_only_in_the_front_end_folder_is_served(tmp_path):
    r = make(tmp_path).get("/static/img/cover.jpg")
    assert r.status_code == 200 and r.content == b"cover-bytes"


def test_the_server_folder_wins_when_a_file_is_in_both(tmp_path):
    assert make(tmp_path).get("/static/img/both.jpg").content == b"from-server"


def test_a_file_in_neither_folder_is_a_404(tmp_path):
    assert make(tmp_path).get("/static/img/nope.jpg").status_code == 404


def test_the_fallback_cannot_be_used_to_read_other_files(tmp_path):
    c = make(tmp_path)
    for path in ("/static/../secret.txt", "/static/img/../../secret.txt", "/static/%2e%2e/secret.txt"):
        assert c.get(path).status_code in (404, 400) and b"private" not in c.get(path).content


def test_the_real_app_serves_the_cover_from_the_front_end_folder(tmp_path, monkeypatch):
    from app import config, main
    site = tmp_path / "dist"
    (site / "static" / "img").mkdir(parents=True)
    (site / "static" / "img" / "mimi-ni-odogwu.jpg").write_bytes(b"cover")
    monkeypatch.setattr(config, "FRONTEND_DIST", site)
    app = FastAPI()
    app.mount("/static", main.FallbackStaticFiles(directory=main.STATIC_DIR, fallback=config.FRONTEND_DIST / "static"))
    assert TestClient(app).get("/static/img/mimi-ni-odogwu.jpg").content == b"cover"
