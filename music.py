"""Music data: loads music.json, builds song slugs and schema.org JSON-LD."""
import copy
import hashlib
import json
import re
import time
import unicodedata
from pathlib import Path

from . import db

ROOT = Path(__file__).resolve().parent.parent
MUSIC_FILE = ROOT / "music.json"

INBOX_ID = "new-releases"
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)

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


def song_id(url: str | None) -> str | None:
    m = UUID_RE.search(url or "")
    return m[0].lower() if m else None


def base_catalog() -> dict | None:
    """The catalog as stored in the database (seeded from music.json), before the Suno sync results."""
    text = _current_text(_read_file())
    try:
        return json.loads(text) if text is not None else None
    except json.JSONDecodeError:
        return None


def build(base: dict, mirror: bool = True) -> dict:
    """Catalog + Suno sync results: artwork found for tracks, songs new on Suno (in 'New Releases'),
    and, when `mirror` is set, Suno image addresses swapped for the copies kept in the database.
    A track's own `image` in music.json always wins over the synced one."""
    data = copy.deepcopy(base)
    try:
        images, new = db.get_overlay()
        mirrors = db.get_mirror_map() if mirror else {}
    except Exception:  # database unavailable: serve the catalog as it is
        images, new, mirrors = {}, [], {}
    albums = data.setdefault("albums", [])

    known = set()
    for album in albums:
        for track in album.get("tracks", []):
            sid = song_id(track.get("url"))
            if sid:
                known.add(sid)
                if sid in images and not track.get("image"):
                    track["image"] = images[sid]

    fresh = [n for n in new if n["song_id"] not in known]  # moved into a real album by hand: ignored
    if fresh:
        inbox = next((a for a in albums if a.get("id") == INBOX_ID), None)
        if inbox is None:
            cover = next((n["image"] for n in fresh if n.get("image")), None) or (albums[0].get("cover") if albums else "")
            inbox = {"id": INBOX_ID, "number": "New", "title": "New Releases", "cover": cover or "",
                     "tagline": "Fresh from the studio",
                     "description": "The latest songs, added automatically from Suno.", "chips": [], "tracks": []}
            albums.append(inbox)
        for n in fresh:
            track = {"id": f"new-{n['song_id'][:8]}", "title": n["title"], "url": n["url"], "audioUrl": n["audio_url"]}
            if n.get("image"):
                track["image"] = n["image"]
            inbox.setdefault("tracks", []).append(track)

    if mirrors:
        for album in albums:
            album["cover"] = mirrors.get(album.get("cover"), album.get("cover"))
            for track in album.get("tracks", []):
                if track.get("image"):
                    track["image"] = mirrors.get(track["image"], track["image"])
    return data


def invalidate() -> None:
    """Make the next load() re-read everything (used after a sync run)."""
    _cache["mtime"], _cache["checked"] = None, 0.0


def load() -> dict:
    """Return the music data: the database catalog (seeded from music.json) plus the Suno sync results."""
    try:
        mtime = MUSIC_FILE.stat().st_mtime
    except OSError:
        mtime = None
    now = time.time()
    if mtime != _cache["mtime"] or now - _cache["checked"] > RECHECK_SECONDS:
        base = base_catalog()
        if base is not None:
            data = build(base)
            _cache["songs"], _cache["order"] = _index(data)
            _cache["data"] = data
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


def absolute(url: str | None, site_url: str) -> str | None:
    """'/static/x.jpg' -> 'https://site/static/x.jpg' (search engines and link previews need full URLs)."""
    return site_url + url if url and url.startswith("/") else url


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
        ld["image"] = absolute(track.get("image") or album.get("cover"), site_url)
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
            "image": absolute(album.get("cover"), site_url),
            "byArtist": _artist(site_url),
            "numTracks": len(tracks),
            "track": tracks,
        })
    return {"@context": "https://schema.org", "@graph": graph}
