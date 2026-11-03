#!/usr/bin/env python3
"""Keep music.json in step with the Suno profile.

Usage:
    python sync_suno.py            # update music.json when something changed
    python sync_suno.py --dry-run  # show what would change, write nothing

How it works
  1. Every track is identified by its Suno song ID (taken from its `url`), never by its title.
     Suno makes two versions of a song with the same title, so title matching could silently
     point a track at the wrong version.
  2. Each known track's own song page is fetched and its share image (og:image) is saved as
     `image`. `audioUrl` is derived from the song ID. A track's `url` and `title` are never
     changed by the sync.
  3. A track that has no Suno link yet is linked by title, but only when exactly one song on
     the profile has that title.
  4. Songs on the profile that are not in music.json yet are added to an album called
     "New Releases" (created when needed), at most MAX_NEW per run. Move them to the right
     album and add lyrics by hand; the sync will not touch them again.
  5. If a song has the same title as an existing track but a different ID, it is treated as an
     alternate version and only reported.

Safety: music.json is the fallback and is only rewritten when something really changed. If
neither the profile nor any song page can be reached, nothing is written and the script exits
with code 1, so the scheduled run shows up as failed.
"""
import json
import re
import sys
import time
import unicodedata
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
MUSIC_JSON = ROOT / "music.json"

MAX_NEW = 5                      # new songs added per run (guards against a page that lists someone else's songs)
INBOX_ID = "new-releases"
SKIP_WORDS = ("Suno", "Sharing", "Publish", "Edit")  # UI strings that look like clip titles
CLIP_RE = re.compile(r'"id":"([0-9a-f-]{36})"[^}]*?"title":"([^"]+)"')
UUID_RE = re.compile(r"[0-9a-f-]{36}", re.I)
ID_RE = re.compile(r'"id":"[0-9a-f-]{36}"')
HANDLE_RE = re.compile(r'"handle":"([^"]+)"')
IMAGE_KEYS = ("image_large_url", "imageLargeUrl", "image_url", "imageUrl")
IMAGE_HOST_RE = re.compile(r"^https://([a-z0-9-]+\.)*suno\.(ai|com)/", re.I)
USER_AGENTS = (
    "Mozilla/5.0 (compatible; zimbermanne-sync/2.0)",
    "Twitterbot/1.0",  # link-preview bots are usually let through when other clients are not
)
MISSING = {"missing": True}      # the song page no longer exists


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def song_id(url: str | None) -> str | None:
    m = UUID_RE.search(url or "")
    return m[0].lower() if m else None


def audio_url(sid: str) -> str:
    return f"https://cdn1.suno.ai/{sid}.mp4"


def suno_image(url: str | None) -> str | None:
    """Only Suno-hosted https images are accepted."""
    url = (url or "").replace("\\u0026", "&").strip()
    return url if IMAGE_HOST_RE.match(url) else None


# ---------------------------------------------------------------- parsing
def _decode_title(raw: str) -> str:
    try:  # the profile embeds JSON strings, so handle \u2019 style escapes
        return json.loads(f'"{raw}"').strip()
    except json.JSONDecodeError:
        return raw.strip()


def find_image(window: str) -> str | None:
    for key in IMAGE_KEYS:
        m = re.search(rf'"{key}":"([^"]+)"', window)
        if m and suno_image(m[1]):
            return suno_image(m[1])
    return None


def parse_clips(html: str, handle: str | None = None) -> dict[str, dict]:
    """Songs found on the profile page, as {song id: clip}, in page order.

    A clip whose own data names a different account (`"handle":"someone-else"`) is skipped.
    """
    text = html.replace('\\"', '"').replace("\\\\", "\\")
    starts = [m.start() for m in ID_RE.finditer(text)] + [len(text)]
    clips: dict[str, dict] = {}
    for m in CLIP_RE.finditer(text):
        clip_id, raw_title = m.groups()
        clip_id = clip_id.lower()
        title = _decode_title(raw_title)
        if any(w in title for w in SKIP_WORDS) or clip_id in clips:
            continue
        nxt = next((x for x in starts if x > m.start()), len(text))
        window = text[m.start():min(nxt, m.start() + 4000)]
        owner = HANDLE_RE.search(window)
        if handle and owner and owner[1].lstrip("@").lower() != handle.lstrip("@").lower():
            continue
        clips[clip_id] = {
            "id": clip_id,
            "title": title,
            "url": f"https://suno.com/song/{clip_id}",
            "audioUrl": audio_url(clip_id),
            "image": find_image(window),
        }
    return clips


class _MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        if tag == "meta":
            a = dict(attrs)
            key = a.get("property") or a.get("name")
            if key and a.get("content"):
                self.meta.setdefault(key.lower(), a["content"])


def parse_song_page(html: str) -> dict:
    """What a single song page tells us: its share image, from the og:image / twitter:image tags."""
    p = _MetaParser()
    p.feed(html)
    return {"image": suno_image(p.meta.get("og:image") or p.meta.get("twitter:image"))}


# ---------------------------------------------------------------- network
def fetch_song(client: httpx.Client, sid: str):
    """Song page info: {'image': ...}, MISSING for a 404, or None when it could not be read."""
    for agent in USER_AGENTS:
        try:
            r = client.get(f"https://suno.com/song/{sid}", headers={"User-Agent": agent})
        except httpx.HTTPError:
            continue
        if r.status_code == 404:
            return MISSING
        if r.status_code == 200:
            info = parse_song_page(r.text)
            if info["image"]:
                return info
    return None


# ---------------------------------------------------------------- applying
def _set(track: dict, field: str, value, changes: list[str]) -> None:
    if value and track.get(field) != value:
        changes.append(f"{track.get('title')}: {field} {track.get(field)!r} -> {value!r}")
        track[field] = value


def _inbox(data: dict, first_image: str | None) -> dict:
    albums = data.setdefault("albums", [])
    for album in albums:
        if album.get("id") == INBOX_ID:
            return album
    fallback = albums[0].get("cover") if albums else None
    album = {
        "id": INBOX_ID, "number": "New", "title": "New Releases",
        "cover": first_image or fallback or "",
        "tagline": "Fresh from the studio",
        "description": "The latest songs, added automatically from Suno.",
        "chips": [], "tracks": [],
    }
    albums.append(album)
    return album


def apply_sync(data: dict, clips: dict[str, dict], song_lookup) -> dict:
    """Update `data` in place. `song_lookup(song_id)` returns {'image':..}, MISSING or None.

    Returns {'changes': [...], 'new': [...], 'alternates': [...], 'missing': [...], 'checked': n, 'read': n}.
    """
    out = {"changes": [], "new": [], "alternates": [], "missing": [], "checked": 0, "read": 0}
    changes = out["changes"]
    tracks = [t for a in data.get("albums", []) for t in a.get("tracks", [])]
    known = {song_id(t.get("url")) for t in tracks} - {None}
    titles = {normalize(t.get("title", "")) for t in tracks}

    # 1. refresh every known track by its own song ID
    for track in tracks:
        sid = song_id(track.get("url"))
        if not sid:
            continue
        _set(track, "audioUrl", audio_url(sid), changes)
        out["checked"] += 1
        info = song_lookup(sid)
        if info is MISSING:
            out["missing"].append(track["title"])
            continue
        image = (info or {}).get("image") or (clips.get(sid) or {}).get("image")
        if info or sid in clips:
            out["read"] += 1
        _set(track, "image", image, changes)

    # 2. tracks without a Suno link: link by title only when it is unambiguous
    by_title: dict[str, list[dict]] = {}
    for c in clips.values():
        by_title.setdefault(normalize(c["title"]), []).append(c)
    for track in tracks:
        if song_id(track.get("url")):
            continue
        matches = by_title.get(normalize(track.get("title", "")), [])
        if len(matches) == 1 and matches[0]["id"] not in known:
            c = matches[0]
            known.add(c["id"])
            _set(track, "url", c["url"], changes)
            _set(track, "audioUrl", c["audioUrl"], changes)
            _set(track, "image", c.get("image"), changes)

    # 3. songs on the profile that music.json does not have
    fresh = []
    for cid, c in clips.items():
        if cid in known:
            continue
        if normalize(c["title"]) in titles:
            out["alternates"].append(c["title"])
        else:
            fresh.append(c)
    for c in fresh[:MAX_NEW]:
        album = _inbox(data, c.get("image"))
        track = {"id": f"new-{len(album['tracks']) + 1}", "title": c["title"], "url": c["url"],
                 "audioUrl": c["audioUrl"]}
        if c.get("image"):
            track["image"] = c["image"]
        album["tracks"].append(track)
        titles.add(normalize(c["title"]))
        out["new"].append(c["title"])
        changes.append(f"added new song {c['title']!r} to New Releases")
    out["left_out"] = [c["title"] for c in fresh[MAX_NEW:]]
    return out


# ---------------------------------------------------------------- main
def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    try:
        music = json.loads(MUSIC_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[sync] cannot read music.json: {exc}", file=sys.stderr)
        return 1
    handle = music.get("handle", "")
    profile_url = music.get("sunoProfile") or f"https://suno.com/{handle}"

    client = httpx.Client(timeout=30, follow_redirects=True)
    clips: dict[str, dict] = {}
    print(f"[sync] fetching {profile_url}")
    try:
        r = client.get(profile_url, headers={"User-Agent": USER_AGENTS[0]})
        r.raise_for_status()
        clips = parse_clips(r.text, handle)
        print(f"[sync] profile lists {len(clips)} songs")
    except httpx.HTTPError as exc:
        print(f"[sync] profile could not be fetched ({exc}); new songs cannot be found this run")
    if not clips:
        print("[sync] no songs found on the profile page (blocked or layout changed?)")

    def lookup(sid):
        time.sleep(0.3)  # be polite to Suno
        return fetch_song(client, sid)

    result = apply_sync(music, clips, lookup)
    print(f"[sync] song pages: {result['read']} of {result['checked']} tracks read successfully")
    if result["checked"] and result["read"] == 0 and not clips:
        print("[sync] nothing could be read from Suno, music.json left unchanged", file=sys.stderr)
        return 1
    for line in result["changes"]:
        print(f"[sync] changed {line}")
    if result["missing"]:
        print(f"[sync] song page not found (deleted or private?): {', '.join(result['missing'])}")
    if result["alternates"]:
        print(f"[sync] same title, different version (ignored): {', '.join(result['alternates'])}")
    if result["left_out"]:
        print(f"[sync] more than {MAX_NEW} new songs; not added this run: {', '.join(result['left_out'])}")
    if not result["changes"]:
        print("[sync] nothing changed")
        return 0
    if dry_run:
        print("[sync] dry run, nothing written")
        return 0
    music["lastUpdated"] = date.today().isoformat()
    MUSIC_JSON.write_text(json.dumps(music, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[sync] wrote music.json ({len(result['changes'])} changes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
