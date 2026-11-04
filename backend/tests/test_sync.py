import json

import httpx
import pytest

from tests import test_api  # noqa: F401  (sets up the temp database + env)
from app import config
from app.database import SessionLocal
from app.models import Album, PlatformStat, Track
from app.sync import soundcloud, spotify, suno
from app.sync.common import Report, SyncError

H = "zimbermannelit"
A, B, C = ("11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222", "33333333-3333-3333-3333-333333333333")
ALB = "99999999-9999-9999-9999-999999999999"
IMG = "https://cdn2.suno.ai/img.jpeg"


def clip(cid, title, plays=0, handle=H):
    return f'{{"id":"{cid}","title":"{title}","handle":"{handle}","play_count":{plays},"image_large_url":"{IMG}"}}'


def page(*clips, meta=""):
    return f"<html><head>{meta}</head><body><script>{''.join(clips)}</script></body></html>"


def test_parse_clips_counts_plays_and_skips_other_accounts():
    html = page(clip(A, "Song A", 120), clip(B, "Other", 5, handle="someone"))
    c = suno.parse_clips(html, H)
    assert list(c) == [A] and c[A]["plays"] == 120 and c[A]["image"] == IMG


def test_album_ids_and_meta():
    html = f'<meta property="og:title" content="Mimi ni odogwu | Suno"><meta property="og:image" content="{IMG}"><a href="/album/{ALB}">x</a>'
    assert suno.parse_album_ids(html) == [ALB]
    assert suno.parse_meta(html) == {"title": "Mimi ni odogwu", "image": IMG}


def fresh_db():
    with SessionLocal() as db:
        for m in (Track, Album, PlatformStat):
            db.query(m).delete()
        db.commit()


def test_suno_apply_adds_albums_songs_stats_and_is_stable():
    fresh_db()
    profile = page(clip(A, "Song A", 100), clip(B, "Song B", 40), clip(C, "Loose Song", 7))
    albums = [{"id": ALB, "title": "Fresh Album", "image": IMG, "clips": suno.parse_clips(page(clip(A, "Song A", 100), clip(B, "Song B", 40)), H)}]
    with SessionLocal() as db:
        r = Report()
        suno.apply_suno(db, profile, albums, lambda sid: None, r)
        db.commit()
        assert {t.title for t in db.query(Track)} == {"Song A", "Song B", "Loose Song"}
        a = db.query(Album).filter(Album.title == "Fresh Album").one()
        assert a.suno_album_id == ALB and len(a.tracks) == 2
        assert db.query(Album).filter(Album.key == "new-releases").one().tracks[0].title == "Loose Song"
        assert db.get(PlatformStat, "suno_plays").value == 147
    with SessionLocal() as db:  # second run changes nothing
        r2 = Report()
        suno.apply_suno(db, profile, albums, lambda sid: None, r2)
        assert r2.changed == 0


def test_manual_stat_is_never_overwritten():
    fresh_db()
    with SessionLocal() as db:
        db.add(PlatformStat(key="suno_plays", value=999, source="manual"))
        db.commit()
        from app.sync.common import set_stat
        set_stat(db, "suno_plays", 5)
        db.commit()
        assert db.get(PlatformStat, "suno_plays").value == 999


def seed_one():
    with SessionLocal() as db:
        al = Album(key="mimi", title="Mimi ni Odogwu")
        db.add(al); db.flush()
        db.add(Track(album_id=al.id, slug="kibati", title="Kibati cha Kijiji"))
        db.commit()


def test_spotify_links_matching_songs_and_reports_the_rest(monkeypatch):
    fresh_db(); seed_one()
    monkeypatch.setattr(config, "SPOTIFY_CLIENT_ID", "id"); monkeypatch.setattr(config, "SPOTIFY_CLIENT_SECRET", "sec")

    def handler(req: httpx.Request):
        u = str(req.url)
        if "accounts.spotify.com" in u:
            return httpx.Response(200, json={"access_token": "t"})
        if u.endswith("/artists/" + config.SPOTIFY_ARTIST_ID):
            return httpx.Response(200, json={"name": "zimbermanne"})
        if "/artists/" in u and "/albums" in u:
            return httpx.Response(200, json={"items": [{"id": "al1"}], "next": None})
        if "/albums/al1" in u:
            return httpx.Response(200, json={"id": "al1", "name": "Mimi ni Odogwu", "images": [{"url": "https://i.scdn.co/x"}],
                "external_urls": {"spotify": "https://open.spotify.com/album/al1"},
                "tracks": {"items": [{"name": "Kibati cha Kijiji", "external_urls": {"spotify": "https://open.spotify.com/track/k"}},
                                     {"name": "Unknown", "external_urls": {}}]}})
        return httpx.Response(404)

    with SessionLocal() as db, httpx.Client(transport=httpx.MockTransport(handler)) as c:
        r = spotify.run(db, c)
        t = db.query(Track).one()
        assert t.spotify_url.endswith("/track/k") and t.image == "https://i.scdn.co/x"
        assert db.query(Album).one().spotify_album_id == "al1"
        assert "Unknown" in r.text


def test_soundcloud_plays_followers_and_links(monkeypatch):
    fresh_db(); seed_one()
    monkeypatch.setattr(config, "SOUNDCLOUD_CLIENT_ID", "id"); monkeypatch.setattr(config, "SOUNDCLOUD_CLIENT_SECRET", "sec")
    soundcloud._tok.update(value="", exp=0)

    def handler(req: httpx.Request):
        u = str(req.url)
        if "oauth/token" in u:
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        if "/resolve" in u:
            return httpx.Response(200, json={"kind": "user", "id": 7, "username": "z", "followers_count": 12})
        if "/users/7/tracks" in u:
            return httpx.Response(200, json={"collection": [{"title": "Kibati cha Kijiji", "playback_count": 321, "permalink_url": "https://soundcloud.com/z/k"}]})
        if "/users/7/playlists" in u:
            return httpx.Response(200, json={"collection": []})
        return httpx.Response(404)

    with SessionLocal() as db, httpx.Client(transport=httpx.MockTransport(handler)) as c:
        soundcloud.run(db, c)
        t = db.query(Track).one()
        assert t.soundcloud_plays == 321 and t.soundcloud_url.endswith("/z/k")
        assert db.get(PlatformStat, "soundcloud_followers").value == 12
        assert db.get(PlatformStat, "soundcloud_plays").value == 321


def test_unconfigured_sources_explain_themselves(monkeypatch):
    monkeypatch.setattr(config, "SPOTIFY_CLIENT_ID", "")
    with SessionLocal() as db, pytest.raises(SyncError):
        spotify.run(db)


def test_migration_adds_new_columns_to_an_old_database(tmp_path):
    from sqlalchemy import create_engine, inspect, text
    from app.migrate import add_missing_columns
    eng = create_engine(f"sqlite:///{tmp_path}/old.db")
    with eng.begin() as c:  # the schema as deployed before the sync existed
        c.execute(text("CREATE TABLE albums (id INTEGER PRIMARY KEY, key VARCHAR(120), number VARCHAR(40), title VARCHAR(200), tagline VARCHAR(300), description TEXT, cover VARCHAR(600), chips_json TEXT, position INTEGER)"))
        c.execute(text("CREATE TABLE tracks (id INTEGER PRIMARY KEY, album_id INTEGER, slug VARCHAR(200), title VARCHAR(300), subtitle VARCHAR(200), url VARCHAR(600), audio_url VARCHAR(600), image VARCHAR(600), duration VARCHAR(20), lyrics TEXT, position INTEGER)"))
        c.execute(text("INSERT INTO tracks (id, album_id, slug, title) VALUES (1, 1, 's', 't')"))
    added = add_missing_columns(eng)
    assert "tracks.suno_plays" in added and "albums.spotify_url" in added
    cols = {c["name"] for c in inspect(eng).get_columns("tracks")}
    assert {"spotify_url", "soundcloud_url", "suno_plays", "soundcloud_plays"} <= cols
    with eng.connect() as c:
        assert c.execute(text("SELECT suno_plays, spotify_url FROM tracks")).one() == (0, "")
    assert add_missing_columns(eng) == []  # idempotent
