"""Music data: loads music.json, builds song slugs and schema.org JSON-LD."""
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MUSIC_FILE = ROOT / "music.json"

_cache = {"mtime": 0.0, "data": {"albums": []}, "songs": {}, "order": []}


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


def load() -> dict:
    """Reload music.json only when the file changes; keep the last good copy on errors."""
    try:
        mtime = MUSIC_FILE.stat().st_mtime
        if mtime != _cache["mtime"]:
            data = json.loads(MUSIC_FILE.read_text(encoding="utf-8"))
            _cache["songs"], _cache["order"] = _index(data)
            _cache["data"], _cache["mtime"] = data, mtime
    except (OSError, json.JSONDecodeError):
        pass
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
        ld["image"] = album.get("cover")
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
