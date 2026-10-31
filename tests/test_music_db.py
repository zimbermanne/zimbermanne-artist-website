"""Music catalog lives in the database and is imported from music.json when that file changes."""
import json

import pytest

from app import db, music


@pytest.fixture()
def isolated(monkeypatch, tmp_path):
    original = db.get_catalog()
    f = tmp_path / "music.json"
    monkeypatch.setattr(music, "MUSIC_FILE", f)
    monkeypatch.setattr(music, "RECHECK_SECONDS", 0)  # always re-read in tests

    def reset():
        music._cache.update({"mtime": None, "checked": 0.0})

    reset()
    yield f, reset
    if original:
        db.set_catalog(*original)
    monkeypatch.undo()
    reset()


def _album(title):
    return {"albums": [{"title": title, "tracks": [{"title": "One"}]}]}


def test_music_json_is_imported_into_the_database(isolated):
    f, _ = isolated
    f.write_text(json.dumps(_album("First")))
    assert music.load()["albums"][0]["title"] == "First"
    stored = json.loads(db.get_catalog()[0])
    assert stored["albums"][0]["title"] == "First"


def test_database_copy_is_served_when_the_file_is_missing(isolated):
    f, reset = isolated
    f.write_text(json.dumps(_album("Stored")))
    music.load()
    f.unlink()
    reset()
    assert music.load()["albums"][0]["title"] == "Stored"


def test_changed_file_replaces_the_database_copy(isolated):
    f, reset = isolated
    f.write_text(json.dumps(_album("Old")))
    music.load()
    f.write_text(json.dumps(_album("New")))
    reset()
    assert music.load()["albums"][0]["title"] == "New"
    assert json.loads(db.get_catalog()[0])["albums"][0]["title"] == "New"


def test_direct_database_edit_survives_while_the_file_is_unchanged(isolated):
    f, reset = isolated
    f.write_text(json.dumps(_album("File")))
    music.load()
    h = db.get_catalog()[1]
    db.set_catalog(json.dumps(_album("Edited in DB")), h)  # same hash: file not changed
    reset()
    assert music.load()["albums"][0]["title"] == "Edited in DB"
