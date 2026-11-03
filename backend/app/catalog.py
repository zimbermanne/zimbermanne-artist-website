"""Slugs, serialising albums/tracks for the API, and seeding from music.json."""
import json
import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config
from .models import Album, Track


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-") or "song"


def unique_slug(db: Session, title: str, exclude_id: int | None = None) -> str:
    base, n = slugify(title), 2
    slug = base
    while True:
        hit = db.scalar(select(Track).where(Track.slug == slug))
        if not hit or hit.id == exclude_id:
            return slug
        slug, n = f"{base}-{n}", n + 1


def unique_album_key(db: Session, title: str, exclude_id: int | None = None) -> str:
    base, n = slugify(title), 2
    key = base
    while True:
        hit = db.scalar(select(Album).where(Album.key == key))
        if not hit or hit.id == exclude_id:
            return key
        key, n = f"{base}-{n}", n + 1


def track_out(t: Track) -> dict:
    d = {"id": t.id, "slug": t.slug, "title": t.title, "url": t.url, "duration": t.duration, "lyrics": t.lyrics}
    if t.subtitle:
        d["subtitle"] = t.subtitle
    if t.audio_url:
        d["audioUrl"] = t.audio_url
    if t.image:
        d["image"] = t.image
    return d


def album_out(a: Album, with_tracks: bool = True) -> dict:
    d = {
        "id": a.key, "dbId": a.id, "number": a.number, "title": a.title, "tagline": a.tagline,
        "description": a.description, "cover": a.cover, "chips": a.chips,
    }
    if with_tracks:
        d["tracks"] = [track_out(t) for t in a.tracks]
    return d


def seed_catalog(db: Session) -> int:
    """Import music.json once, when the albums table is empty. Returns number of tracks added."""
    if db.scalar(select(Album).limit(1)) or not config.MUSIC_SEED.exists():
        return 0
    data = json.loads(config.MUSIC_SEED.read_text(encoding="utf-8"))
    added = 0
    for ai, a in enumerate(data.get("albums", [])):
        album = Album(
            key=unique_album_key(db, a.get("id") or a["title"]), number=a.get("number", ""), title=a["title"],
            tagline=a.get("tagline", ""), description=a.get("description", ""), cover=a.get("cover", ""),
            position=ai,
        )
        album.chips = a.get("chips", [])
        db.add(album)
        db.flush()
        for ti, t in enumerate(a.get("tracks", [])):
            db.add(Track(
                album_id=album.id, slug=unique_slug(db, t["title"]), title=t["title"],
                subtitle=t.get("subtitle", ""), url=t.get("url", ""), audio_url=t.get("audioUrl", ""),
                image=t.get("image", ""), duration=t.get("duration", ""), lyrics=t.get("lyrics", ""), position=ti,
            ))
            db.flush()
            added += 1
    db.commit()
    return added


def ordered_albums(db: Session) -> list[Album]:
    return list(db.scalars(select(Album).order_by(Album.position, Album.id)))
