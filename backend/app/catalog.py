"""Slugs, serialising albums/tracks for the API, and seeding from music.json."""
import json
import re
import unicodedata

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from . import config
from .models import Album, Track


# Languages of the music. Codes are stored on each song; labels are what visitors see.
LANGUAGES = {
    "en": "English", "sw": "Kiswahili", "fr": "Français", "de": "Deutsch", "pt-BR": "Português (Brasil)",
    "ko": "한국어", "zh": "中文", "ru": "Русский", "es": "Español",
}
# Words that name a language, as they might appear in a Suno playlist or song title.
_ALIASES = {
    "en": ("english", "weight of gold", "inglés", "ingles", "anglais"),
    "sw": ("uzito wa dhahabu", "swahili", "kiswahili"),
    "fr": ("poids de l'or", "french", "français", "francais", "francaise", "française"),
    "de": ("gewicht des goldes", "german", "deutsch", "allemand"),
    "pt-BR": ("peso do ouro", "portuguese", "português", "portugues", "brazilian", "brasil", "brazil", "pt-br", "ptbr"),
    "ko": ("korean", "한국어", "korea"),
    "zh": ("chinese", "中文", "mandarin", "china", "chinois"),
    "ru": ("russian", "русский", "russia", "russe"),
    "es": ("peso del oro", "spanish", "español", "espanol", "spain", "espagnol", "castellano"),
}
_HANGUL = re.compile(r"[\uac00-\ud7af\u1100-\u11ff]")
_KANA = re.compile(r"[\u3040-\u30ff]")
_HAN = re.compile(r"[\u4e00-\u9fff]")
_CYRILLIC = re.compile(r"[\u0400-\u04ff]")


def detect_language(text: str) -> str:
    """A language code when `text` clearly names or is written in one, else "".

    Looks for a language name first ("Série - Español"), then for a distinctive writing system
    (Hangul, Chinese characters, Cyrillic). Latin-script titles on their own are never guessed:
    English, French, Spanish and Swahili look alike, so those are set from the playlist name or by hand.
    """
    text = text or ""
    low = text.lower()
    found = [code for code, names in _ALIASES.items()
             if any(re.search(rf"(?<![a-z]){re.escape(n)}(?![a-z])", low) for n in names)]
    if len(found) == 1:
        return found[0]
    if len(found) > 1:
        return ""  # names several languages: do not guess
    if _HANGUL.search(text):
        return "ko"
    if _HAN.search(text) and not _KANA.search(text):
        return "zh"
    if _CYRILLIC.search(text):
        return "ru"
    return ""


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
    if t.language:
        d["language"] = t.language
    if t.audio_url:
        d["audioUrl"] = t.audio_url
    if t.image:
        d["image"] = t.image
    if t.spotify_url:
        d["spotifyUrl"] = t.spotify_url
    if t.soundcloud_url:
        d["soundcloudUrl"] = t.soundcloud_url
    plays = {"suno": t.suno_plays, "soundcloud": t.soundcloud_plays}
    d["plays"] = {k: v for k, v in plays.items() if v}
    return d


def album_out(a: Album, with_tracks: bool = True) -> dict:
    d = {
        "id": a.key, "dbId": a.id, "number": a.number, "title": a.title, "tagline": a.tagline,
        "description": a.description, "cover": a.cover, "chips": a.chips,
        "spotifyUrl": a.spotify_url, "soundcloudUrl": a.soundcloud_url,
    }
    if with_tracks:
        d["tracks"] = [track_out(t) for t in a.tracks]
    return d


def _legacy_catalog(db: Session):
    """The first version of the site kept its albums as one JSON blob in a `catalog` table. Prefer it: it
    holds everything the old Suno sync added since music.json was last committed."""
    try:
        row = db.execute(text("SELECT data FROM catalog WHERE id = 1")).first()
        data = json.loads(row[0]) if row else None
    except Exception:
        db.rollback()  # no such table (fresh database)
        return None
    if isinstance(data, list):
        data = {"albums": data}
    return data if isinstance(data, dict) and data.get("albums") else None


def seed_catalog(db: Session) -> int:
    """Fill an empty albums table from the old `catalog` table, else from music.json. Returns songs added."""
    if db.scalar(select(Album).limit(1)):
        return 0
    data = _legacy_catalog(db)
    if data is None:
        if not config.MUSIC_SEED.exists():
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
                language=t.get("language", "") if t.get("language", "") in LANGUAGES else "",
            ))
            db.flush()
            added += 1
    db.commit()
    return added


def ordered_albums(db: Session) -> list[Album]:
    return list(db.scalars(select(Album).order_by(Album.position, Album.id)))
