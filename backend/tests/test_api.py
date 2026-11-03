import os
import tempfile

os.environ["DATABASE_URL"] = ""
os.environ["ADMIN_EMAIL"] = "admin@test.dev"
os.environ["ADMIN_PASSWORD"] = "correct-horse-battery"
os.environ["SECRET_KEY"] = "test"
os.environ["FRONTEND_DIST"] = "/nonexistent"

from app import config  # noqa: E402

config.DATABASE_URL = "sqlite:///" + tempfile.mkdtemp() + "/t.db"
import app.database as database  # noqa: E402

database.engine.dispose()
from sqlalchemy import create_engine  # noqa: E402

database.engine = create_engine(config.DATABASE_URL, connect_args={"check_same_thread": False})
database.SessionLocal.configure(bind=database.engine)
import app.main as main  # noqa: E402

main.engine = database.engine
from fastapi.testclient import TestClient  # noqa: E402


def client():
    return TestClient(main.app)


def test_public_flow():
    with client() as c:
        albums = c.get("/api/music").json()["albums"]
        assert len(albums) == 3 and albums[0]["tracks"][0]["slug"]
        slug = albums[0]["tracks"][1]["slug"]
        d = c.get(f"/api/song/{slug}").json()
        assert d["prev"] and d["next"]
        assert c.get("/api/song/nope").status_code == 404
        assert c.post("/api/visit", headers={"user-agent": "Mozilla/5.0"}).json()["views"] == 1
        assert c.post("/api/visit").json()["views"] == 1  # same browser, cookie set
        r = c.post("/api/contact", json={"name": "A", "email": "a@b.co", "message": "hi", "website": ""})
        assert r.json()["ok"]
        assert c.post("/api/subscribe", json={"email": "bad"}).status_code == 422
        assert c.post("/api/subscribe", json={"email": "f@an.co"}).json()["ok"]


def test_admin_flow():
    with client() as c:
        assert c.get("/api/admin/stats").status_code == 401
        assert c.post("/api/auth/login", json={"email": "admin@test.dev", "password": "x"}).status_code == 401
        tok = c.post("/api/auth/login", json={"email": "admin@test.dev", "password": "correct-horse-battery"}).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        assert c.get("/api/admin/stats", headers=h).json()["albums"] == 3
        a = c.post("/api/admin/albums", json={"title": "New One", "chips": ["x"]}, headers=h).json()
        t = c.post(f"/api/admin/albums/{a['dbId']}/tracks", json={"title": "Fresh Song"}, headers=h).json()
        assert c.get(f"/api/song/{t['slug']}").status_code == 200
        c.put(f"/api/admin/tracks/{t['id']}", json={"title": "Fresher Song"}, headers=h)
        assert c.get("/api/admin/subscribers.csv", headers=h).text.startswith("email")
        c.delete(f"/api/admin/albums/{a['dbId']}", headers=h)
        assert c.get(f"/api/song/{t['slug']}").status_code in (404,)
