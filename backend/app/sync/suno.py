"""Suno has no public API, so this reads the public profile and album pages (like your old sync_suno.py).

Per song it keeps: artwork, audio URL, play count. Per album: title, cover, and which songs belong to it.
Rules carried over from the old script: songs are matched by their Suno ID, never by title; a title or
link that is already set is never changed; a same-title song with a different ID is reported, not added.
"""
import json
import re
import time
from html.parser import HTMLParser

import httpx
from sqlalchemy.orm import Session

from .. import catalog, config
from ..models import Album, Track
from .common import Report, SyncError, all_albums, all_tracks, by_title, normalize, set_attr, set_stat, song_id

SKIP_WORDS = ("Suno", "Sharing", "Publish", "Edit")  # UI strings that look like clip titles
CLIP_RE = re.compile(r'"id":"([0-9a-f-]{36})"[^}]*?"title":"([^"]+)"')
ID_RE = re.compile(r'"id":"[0-9a-f-]{36}"')
HANDLE_RE = re.compile(r'"handle":"([^"]+)"')
ALBUM_RE = re.compile(r"/album/([0-9a-f]{8}-[0-9a-f-]{27})", re.I)
PLAYLIST_RE = re.compile(r"/playlist/([0-9a-f]{8}-[0-9a-f-]{27})", re.I)
IMAGE_KEYS = ("image_large_url", "imageLargeUrl", "image_url", "imageUrl")
IMAGE_HOST_RE = re.compile(r"^https://([a-z0-9-]+\.)*suno\.(ai|com)/", re.I)
USER_AGENTS = ("Mozilla/5.0 (compatible; zimbermanne-sync/3.0)", "Twitterbot/1.0")
INBOX_KEY = "new-releases"


def audio_url(sid: str) -> str:
    return f"https://cdn1.suno.ai/{sid}.mp4"


def suno_image(url: str | None) -> str | None:
    url = (url or "").replace("\\u0026", "&").strip()
    return url if IMAGE_HOST_RE.match(url) else None


def _decode(raw: str) -> str:
    try:
        return json.loads(f'"{raw}"').strip()
    except json.JSONDecodeError:
        return raw.strip()


def _number(window: str, *keys: str) -> int:
    for k in keys:
        m = re.search(rf'"{k}":\s*(\d+)', window)
        if m:
            return int(m[1])
    return 0


def parse_clips(html: str, handle: str | None = None) -> dict[str, dict]:
    """Songs on a profile or album page as {song id: clip}, in page order."""
    text = html.replace('\\"', '"').replace("\\\\", "\\")
    starts = [m.start() for m in ID_RE.finditer(text)] + [len(text)]
    clips: dict[str, dict] = {}
    for m in CLIP_RE.finditer(text):
        cid, raw = m.groups()
        cid, title = cid.lower(), _decode(raw)
        if any(w in title for w in SKIP_WORDS) or cid in clips:
            continue
        nxt = next((x for x in starts if x > m.start()), len(text))
        window = text[m.start():min(nxt, m.start() + 4000)]
        owner = HANDLE_RE.search(window)
        if handle and owner and owner[1].lstrip("@").lower() != handle.lower():
            continue
        image = next((suno_image(mm[1]) for k in IMAGE_KEYS if (mm := re.search(rf'"{k}":"([^"]+)"', window)) and suno_image(mm[1])), None)
        clips[cid] = {
            "id": cid, "title": title, "url": f"https://suno.com/song/{cid}", "audioUrl": audio_url(cid),
            "image": image, "plays": _number(window, "play_count", "playCount"),
        }
    return clips


class _Meta(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        if tag == "meta":
            a = dict(attrs)
            key = a.get("property") or a.get("name")
            if key and a.get("content"):
                self.meta.setdefault(key.lower(), a["content"])


def parse_meta(html: str) -> dict:
    p = _Meta()
    p.feed(html)
    title = re.sub(r"\s*[|–-]\s*(Suno|Join me on Suno).*$", "", p.meta.get("og:title", ""), flags=re.I).strip()
    return {"title": title, "image": suno_image(p.meta.get("og:image") or p.meta.get("twitter:image"))}


def parse_album_ids(html: str) -> list[str]:
    seen: list[str] = []
    for m in ALBUM_RE.finditer(html):
        if m[1].lower() not in seen:
            seen.append(m[1].lower())
    return seen


def parse_playlist_ids(html: str) -> list[str]:
    seen: list[str] = []
    for m in PLAYLIST_RE.finditer(html):
        if m[1].lower() not in seen:
            seen.append(m[1].lower())
    return seen


def parse_followers(html: str) -> int:
    return _number(html.replace('\\"', '"'), "follower_count", "num_followers", "followers_count")


# ------------------------------------------------------------ network
def _get(client: httpx.Client, url: str) -> str | None:
    for agent in USER_AGENTS:
        try:
            r = client.get(url, headers={"User-Agent": agent})
        except httpx.HTTPError:
            continue
        if r.status_code == 200 and r.text:
            return r.text
    return None


def fetch_profile(client: httpx.Client, handle: str):
    html = _get(client, f"https://suno.com/@{handle}")
    if not html:
        raise SyncError("Suno profile could not be fetched (blocked, or Suno is down)")
    return html


def fetch_album(client: httpx.Client, album_id: str) -> dict | None:
    time.sleep(0.3)  # be polite to Suno
    html = _get(client, f"https://suno.com/album/{album_id}")
    if not html:
        return None
    meta = parse_meta(html)
    return {"id": album_id, **meta, "clips": parse_clips(html, config.SUNO_HANDLE)}


def fetch_playlist(client: httpx.Client, playlist_id: str) -> dict | None:
    """Playlist pages list every song to a plain request (profile and album pages often do not).
    Songs are not filtered by owner: a playlist you built may hold songs from other accounts."""
    time.sleep(0.3)
    html = _get(client, f"https://suno.com/playlist/{playlist_id}")
    if not html:
        return None
    return {"id": playlist_id, "clips": parse_clips(html, config.SUNO_HANDLE)}


def fetch_song_image(client: httpx.Client, sid: str) -> str | None:
    time.sleep(0.3)
    html = _get(client, f"https://suno.com/song/{sid}")
    return parse_meta(html)["image"] if html else None


# ------------------------------------------------------------ apply
def _inbox(db: Session, first_image: str | None) -> Album:
    a = db.query(Album).filter(Album.key == INBOX_KEY).first()
    if a:
        return a
    last = max([x.position for x in all_albums(db)] or [0])
    a = Album(key=INBOX_KEY, number="New", title="New Releases", tagline="Fresh from the studio",
              description="The latest songs, added automatically from Suno.", cover=first_image or "", position=last + 1)
    db.add(a)
    db.flush()
    return a


def _add_track(db: Session, album: Album, clip: dict, report: Report):
    last = max([t.position for t in album.tracks] or [-1])
    t = Track(album_id=album.id, slug=catalog.unique_slug(db, clip["title"]), title=clip["title"], url=clip["url"],
              audio_url=clip["audioUrl"], image=clip.get("image") or "", suno_plays=clip.get("plays", 0), position=last + 1)
    db.add(t)
    db.flush()
    album.tracks.append(t)
    report.change(f"added song {clip['title']!r} to {album.title!r}")


def apply_suno(db: Session, profile_html: str, albums_data: list[dict], song_image, report: Report,
               playlists_data: list[dict] | None = None) -> dict:
    handle = config.SUNO_HANDLE
    clips = parse_clips(profile_html, handle)
    for a in list(albums_data) + list(playlists_data or []):  # songs only listed on an album or playlist page still count
        for cid, c in a["clips"].items():
            clips.setdefault(cid, c)
    if not clips:
        raise SyncError("no songs found on the Suno profile (layout changed?)")
    report.note(f"profile lists {len(clips)} songs, {len(albums_data)} albums and {len(playlists_data or [])} playlists")

    tracks = all_tracks(db)
    known = {song_id(t.url): t for t in tracks if song_id(t.url)}
    titles = by_title(tracks)

    # 1. refresh songs we already have, by Suno ID
    for sid, t in known.items():
        c = clips.get(sid)
        set_attr(t, "audio_url", audio_url(sid), report, t.title) if not t.audio_url else None
        if not c:
            continue
        if c["plays"] != t.suno_plays and c["plays"]:
            t.suno_plays = c["plays"]
        image = c.get("image") or (song_image(sid) if not t.image else None)
        if image and image != t.image:
            report.change(f"{t.title}: artwork updated")
            t.image = image

    # 2. a song without a Suno link is linked by title, but only if exactly one Suno song has that title
    clip_titles = {}
    for c in clips.values():
        clip_titles.setdefault(normalize(c["title"]), []).append(c)
    for t in tracks:
        if song_id(t.url):
            continue
        m = clip_titles.get(normalize(t.title), [])
        if len(m) == 1 and m[0]["id"] not in known:
            known[m[0]["id"]] = t
            t.url, t.audio_url = m[0]["url"], m[0]["audioUrl"]
            t.suno_plays = m[0]["plays"]
            t.image = t.image or (m[0].get("image") or "")
            report.change(f"{t.title}: linked to Suno")

    # 3. albums: match, create, and file new songs in the right album
    albums = all_albums(db)
    album_by_suno = {a.suno_album_id: a for a in albums if a.suno_album_id}
    album_by_title = by_title(albums)
    added, alternates = 0, []
    for ad in albums_data:
        album = album_by_suno.get(ad["id"])
        if not album and ad["title"]:
            cand = album_by_title.get(normalize(ad["title"]), [])
            album = cand[0] if len(cand) == 1 else None
        if not album:
            if not ad["title"]:
                continue
            last = max([x.position for x in albums] or [0])
            album = Album(key=catalog.unique_album_key(db, ad["title"]), number=f"Album {len(albums) + 1:02d}", title=ad["title"],
                          cover=ad.get("image") or "", position=last + 1)
            db.add(album)
            db.flush()
            albums.append(album)
            report.change(f"new album {ad['title']!r} from Suno")
        set_attr(album, "suno_album_id", ad["id"], report, album.title)
        if not album.cover and ad.get("image"):
            album.cover = ad["image"]
            report.change(f"{album.title}: cover set")
        for cid, c in ad["clips"].items():
            if cid in known:
                continue
            if normalize(c["title"]) in titles:
                alternates.append(c["title"])
            elif added < config.SYNC_MAX_NEW:
                _add_track(db, album, c, report)
                known[cid] = album.tracks[-1]
                titles.setdefault(normalize(c["title"]), []).append(album.tracks[-1])
                added += 1

    # 4. songs on the profile that no album page lists go to "New Releases"
    left_out = []
    for cid, c in clips.items():
        if cid in known:
            continue
        if normalize(c["title"]) in titles:
            alternates.append(c["title"])
        elif added < config.SYNC_MAX_NEW:
            _add_track(db, _inbox(db, c.get("image")), c, report)
            known[cid] = True
            titles.setdefault(normalize(c["title"]), []).append(True)
            added += 1
        else:
            left_out.append(c["title"])
    if alternates:
        report.note(f"same title, different version (ignored): {', '.join(sorted(set(alternates))[:15])}")
    if left_out:
        report.note(f"more than {config.SYNC_MAX_NEW} new songs, left for the next run: {', '.join(left_out[:15])}")

    # 5. numbers for the site
    mine = [c for cid, c in clips.items() if cid in known]
    set_stat(db, "suno_plays", sum(c["plays"] for c in mine))
    set_stat(db, "suno_songs", len(clips))
    followers = parse_followers(profile_html)
    if followers:
        set_stat(db, "suno_followers", followers)
    return {"songs": len(clips), "albums": len(albums_data), "added": added}


def run(db: Session, client: httpx.Client | None = None) -> Report:
    report = Report()
    own = client is None
    client = client or httpx.Client(timeout=30, follow_redirects=True)
    try:
        html = fetch_profile(client, config.SUNO_HANDLE)
        albums_data = [a for aid in parse_album_ids(html) if (a := fetch_album(client, aid))]
        playlists_data = [p for pid in parse_playlist_ids(html) if (p := fetch_playlist(client, pid))]
        res = apply_suno(db, html, albums_data, lambda sid: fetch_song_image(client, sid), report, playlists_data)
        db.commit()
        report.note(f"done: {res['songs']} songs, {res['albums']} albums, {res['added']} added")
        return report
    finally:
        if own:
            client.close()
