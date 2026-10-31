"""Music data: loads music.json, builds song slugs and schema.org JSON-LD."""
import hashlib
import json
import re
import time
import unicodedata
from pathlib import Path

from . import db

ROOT = Path(__file__).resolve().parent.parent
MUSIC_FILE = ROOT / "music.json"

RECHECK_SECONDS = 60  # how often the database copy is re-read

_cache = {"mtime": None, "checked": 0.0, "data": {"albums": []}, "songs": {}, "order": []}


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return text or "song"


def _index(data: dict) -> tuple[dict, list]:
    """Give every track a unique slug and build the slug -> song lookup."""
    songs, order = {}, []
    for album in data.get("albums", []):
        for track in album.get("tracks", []):
            base = slugify(track.get("title", ""))
            slug, n = base, 2
            while slug in songs:  # e.g. two tracks both called "Taarifa Yako"
                slug, n = f"{base}-{n}", n + 1
            track["slug"] = slug
            songs[slug] = {"track": track, "album": album}
            order.append(slug)
    return songs, order


def _read_file() -> str | None:
    try:
        text = MUSIC_FILE.read_text(encoding="utf-8")
        json.loads(text)  # only accept valid JSON
        return text
    except (OSError, json.JSONDecodeError):
        return None


def _current_text(file_text: str | None) -> str | None:
    """Music JSON as stored in the database. music.json is the import source: when its
    content changes (e.g. the daily Suno sync), the database copy is replaced with it."""
    try:
        stored = db.get_catalog()
        if file_text is not None:
            digest = hashlib.sha256(file_text.encode("utf-8")).hexdigest()
            if stored is None or stored[1] != digest:
                db.set_catalog(file_text, digest)
                return file_text
        if stored is not None:
            return stored[0]
    except Exception:  # database unavailable: fall back to the file
        pass
    return file_text


def load() -> dict:
    """Return the music data, read from the database (seeded from music.json)."""
    try:
        mtime = MUSIC_FILE.stat().st_mtime
    except OSError:
        mtime = None
    now = time.time()
    if mtime != _cache["mtime"] or now - _cache["checked"] > RECHECK_SECONDS:
        text = _current_text(_read_file())
        if text is not None:
            try:
                data = json.loads(text)
                _cache["songs"], _cache["order"] = _index(data)
                _cache["data"] = data
            except json.JSONDecodeError:
                pass  # keep the last good copy
        _cache["mtime"], _cache["checked"] = mtime, now
    return _cache["data"]


def get_song(slug: str) -> dict | None:
    load()
    entry = _cache["songs"].get(slug)
    if not entry:
        return None
    i = _cache["order"].index(slug)
    prev_slug = _cache["order"][i - 1] if i > 0 else None
    next_slug = _cache["order"][i + 1] if i + 1 < len(_cache["order"]) else None
    return {**entry, "prev": _cache["songs"].get(prev_slug), "next": _cache["songs"].get(next_slug)}


def all_slugs() -> list[str]:
    load()
    return list(_cache["order"])


def iso_duration(value: str | None) -> str | None:
    """'3:45' -> 'PT3M45S'."""
    m = re.fullmatch(r"(\d+):(\d{2})", value or "")
    return f"PT{int(m[1])}M{int(m[2])}S" if m else None


def json_script(obj) -> str:
    """JSON for an inline <script> tag (cannot be closed early by the data)."""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def _artist(site_url: str) -> dict:
    return {"@type": "MusicGroup", "@id": f"{site_url}/#artist", "name": "Zimbermanne"}


def recording_ld(song: dict, site_url: str, full: bool = True) -> dict:
    track, album = song["track"], song["album"]
    ld = {
        "@type": "MusicRecording",
        "name": track["title"],
        "url": f"{site_url}/song/{track['slug']}",
        "byArtist": _artist(site_url),
        "inAlbum": {"@type": "MusicAlbum", "name": album["title"]},
    }
    if iso_duration(track.get("duration")):
        ld["duration"] = iso_duration(track["duration"])
    if full:
        ld["image"] = track.get("image") or album.get("cover")
        if track.get("audioUrl"):
            ld["audio"] = {"@type": "AudioObject", "contentUrl": track["audioUrl"], "encodingFormat": "audio/mp4"}
        if track.get("lyrics"):
            ld["recordingOf"] = {
                "@type": "MusicComposition",
                "name": track["title"],
                "lyrics": {"@type": "CreativeWork", "text": track["lyrics"]},
            }
    return ld


def song_page_ld(song: dict, site_url: str) -> dict:
    return {"@context": "https://schema.org", **recording_ld(song, site_url)}


def albums_ld(albums: list, site_url: str) -> dict:
    graph = []
    for album in albums:
        tracks = [recording_ld({"track": t, "album": album}, site_url, full=False) for t in album.get("tracks", [])]
        graph.append({
            "@type": "MusicAlbum",
            "name": album["title"],
            "description": album.get("description"),
            "image": album.get("cover"),
            "byArtist": _artist(site_url),
            "numTracks": len(tracks),
            "track": tracks,
        })
    return {"@context": "https://schema.org", "@graph": graph}
