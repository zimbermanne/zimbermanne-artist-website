"""Storage: Postgres on Railway (DATABASE_URL), SQLite file locally."""
import os
import secrets
from datetime import datetime, timezone

from sqlalchemy import (BigInteger, Boolean, Column, DateTime, Integer, LargeBinary,
                        MetaData, String, Table, Text, create_engine, delete, select)
from sqlalchemy.exc import IntegrityError


def _database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        os.makedirs("data", exist_ok=True)
        return "sqlite:///data/site.db"
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


engine = create_engine(_database_url(), pool_pre_ping=True)
metadata = MetaData()

counters = Table(
    "counters", metadata,
    Column("name", String(50), primary_key=True),
    Column("value", BigInteger, nullable=False, default=0),
)

messages = Table(
    "messages", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("name", String(120), nullable=False),
    Column("email", String(254), nullable=False),
    Column("message", Text, nullable=False),
    Column("emailed", Boolean, nullable=False, default=False),
)

catalog = Table(
    "catalog", metadata,
    Column("id", Integer, primary_key=True),          # single row, id = 1
    Column("data", Text, nullable=False),             # the full albums/tracks JSON
    Column("source_hash", String(64), nullable=False),  # sha256 of the music.json it was imported from
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

song_sync = Table(
    "song_sync", metadata,
    Column("song_id", String(36), primary_key=True),   # Suno song id
    Column("image", Text, nullable=False),             # artwork address found by the sync
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

new_songs = Table(
    "new_songs", metadata,
    Column("song_id", String(36), primary_key=True),
    Column("title", Text, nullable=False),
    Column("url", Text, nullable=False),
    Column("audio_url", Text, nullable=False),
    Column("image", Text, nullable=True),
    Column("added_at", DateTime(timezone=True), nullable=False),
)

media = Table(
    "media", metadata,
    Column("id", String(16), primary_key=True),        # first 16 hex characters of sha1(source_url)
    Column("source_url", Text, nullable=False),
    Column("content_type", String(100), nullable=False),
    Column("data", LargeBinary, nullable=False),
    Column("size", Integer, nullable=False),
    Column("fetched_at", DateTime(timezone=True), nullable=False),
)

sync_runs = Table(
    "sync_runs", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True), nullable=True),
    Column("ok", Boolean, nullable=True),
    Column("summary", Text, nullable=True),
)

MEDIA_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}

subscribers = Table(
    "subscribers", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email", String(254), nullable=False, unique=True),
    Column("token", String(64), nullable=False, unique=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("unsubscribed_at", DateTime(timezone=True), nullable=True),
)


_tables_ready = False


def _ensure_tables() -> None:
    global _tables_ready
    if not _tables_ready:
        metadata.create_all(engine)
        _tables_ready = True


def get_catalog() -> tuple[str, str] | None:
    """Return (music JSON text, source hash) stored in the database, or None when empty."""
    _ensure_tables()
    with engine.connect() as c:
        row = c.execute(select(catalog.c.data, catalog.c.source_hash).where(catalog.c.id == 1)).first()
    return (row.data, row.source_hash) if row else None


def set_catalog(data: str, source_hash: str) -> None:
    _ensure_tables()
    now = datetime.now(timezone.utc)
    with engine.begin() as c:
        res = c.execute(catalog.update().where(catalog.c.id == 1)
                        .values(data=data, source_hash=source_hash, updated_at=now))
        if res.rowcount == 0:
            c.execute(catalog.insert().values(id=1, data=data, source_hash=source_hash, updated_at=now))


def get_overlay() -> tuple[dict[str, str], list[dict]]:
    """What the Suno sync found: ({song id: artwork url}, [songs not in music.json])."""
    _ensure_tables()
    with engine.connect() as c:
        images = {r.song_id: r.image for r in c.execute(select(song_sync.c.song_id, song_sync.c.image))}
        new = [dict(r._mapping) for r in c.execute(select(new_songs).order_by(new_songs.c.added_at, new_songs.c.song_id))]
    return images, new


def save_overlay(images: dict[str, str], new: list[dict]) -> None:
    """Replace the sync results. `new` items: song_id, title, url, audio_url, image."""
    _ensure_tables()
    now = datetime.now(timezone.utc)
    with engine.begin() as c:
        c.execute(delete(song_sync))
        if images:
            c.execute(song_sync.insert(), [{"song_id": k, "image": v, "updated_at": now} for k, v in images.items()])
        existing = {r.song_id: r.added_at for r in c.execute(select(new_songs.c.song_id, new_songs.c.added_at))}
        c.execute(delete(new_songs))
        if new:
            c.execute(new_songs.insert(), [{
                "song_id": n["song_id"], "title": n["title"], "url": n["url"], "audio_url": n["audio_url"],
                "image": n.get("image"), "added_at": existing.get(n["song_id"], now)} for n in new])


def get_mirror_map() -> dict[str, str]:
    """{original Suno image address: address on this site} for every image copied into the database."""
    _ensure_tables()
    with engine.connect() as c:
        rows = c.execute(select(media.c.id, media.c.source_url, media.c.content_type)).all()
    return {r.source_url: f"/media/{r.id}.{MEDIA_EXT.get(r.content_type, 'jpg')}" for r in rows}


def has_media(media_id: str) -> bool:
    _ensure_tables()
    with engine.connect() as c:
        return c.execute(select(media.c.id).where(media.c.id == media_id)).first() is not None


def save_media(media_id: str, source_url: str, content_type: str, data: bytes) -> None:
    _ensure_tables()
    with engine.begin() as c:
        c.execute(delete(media).where(media.c.id == media_id))
        c.execute(media.insert().values(id=media_id, source_url=source_url, content_type=content_type,
                                        data=data, size=len(data), fetched_at=datetime.now(timezone.utc)))


def get_media(media_id: str) -> tuple[str, bytes] | None:
    _ensure_tables()
    with engine.connect() as c:
        row = c.execute(select(media.c.content_type, media.c.data).where(media.c.id == media_id)).first()
    return (row.content_type, bytes(row.data)) if row else None


def start_sync_run() -> int:
    _ensure_tables()
    with engine.begin() as c:
        res = c.execute(sync_runs.insert().values(started_at=datetime.now(timezone.utc)))
        return int(res.inserted_primary_key[0])


def finish_sync_run(run_id: int, ok: bool, summary: str) -> None:
    with engine.begin() as c:
        c.execute(sync_runs.update().where(sync_runs.c.id == run_id)
                  .values(finished_at=datetime.now(timezone.utc), ok=ok, summary=summary[:6000]))


def list_sync_runs(limit: int = 5) -> list[dict]:
    _ensure_tables()
    with engine.connect() as c:
        rows = c.execute(select(sync_runs).order_by(sync_runs.c.id.desc()).limit(limit)).all()
    return [dict(r._mapping) for r in rows]


def init_db() -> None:
    _ensure_tables()
    with engine.begin() as c:
        if c.execute(select(counters.c.name).where(counters.c.name == "views")).first() is None:
            c.execute(counters.insert().values(name="views", value=0))


def get_views() -> int:
    with engine.connect() as c:
        row = c.execute(select(counters.c.value).where(counters.c.name == "views")).first()
        return int(row[0]) if row else 0


def bump_views() -> int:
    with engine.begin() as c:
        c.execute(counters.update().where(counters.c.name == "views")
                  .values(value=counters.c.value + 1))
        row = c.execute(select(counters.c.value).where(counters.c.name == "views")).first()
        return int(row[0])


def save_message(name: str, email: str, message: str) -> int:
    with engine.begin() as c:
        res = c.execute(messages.insert().values(
            created_at=datetime.now(timezone.utc), name=name, email=email,
            message=message, emailed=False))
        return int(res.inserted_primary_key[0])


def mark_emailed(message_id: int) -> None:
    with engine.begin() as c:
        c.execute(messages.update().where(messages.c.id == message_id).values(emailed=True))


def add_subscriber(email: str) -> tuple[str, bool]:
    """Add (or re-activate) a subscriber. Returns (unsubscribe token, needs_welcome_email)."""
    email = email.strip().lower()
    now = datetime.now(timezone.utc)
    with engine.begin() as c:
        row = c.execute(select(subscribers.c.token, subscribers.c.unsubscribed_at)
                        .where(subscribers.c.email == email)).first()
        if row:
            if row.unsubscribed_at is None:
                return row.token, False  # already on the list: no second welcome email
            c.execute(subscribers.update().where(subscribers.c.email == email)
                      .values(unsubscribed_at=None, created_at=now))
            return row.token, True
    token = secrets.token_urlsafe(24)
    try:
        with engine.begin() as c:
            c.execute(subscribers.insert().values(email=email, token=token, created_at=now))
    except IntegrityError:  # two simultaneous sign-ups with the same address
        with engine.connect() as c:
            row = c.execute(select(subscribers.c.token).where(subscribers.c.email == email)).first()
        return row.token, False
    return token, True


def subscriber_exists(token: str) -> bool:
    with engine.connect() as c:
        return c.execute(select(subscribers.c.id).where(subscribers.c.token == token)).first() is not None


def unsubscribe(token: str) -> bool:
    """Mark the subscriber as unsubscribed. False when the token is unknown."""
    with engine.begin() as c:
        res = c.execute(subscribers.update().where(subscribers.c.token == token)
                        .where(subscribers.c.unsubscribed_at.is_(None))
                        .values(unsubscribed_at=datetime.now(timezone.utc)))
        if res.rowcount:
            return True
    return subscriber_exists(token)  # already unsubscribed counts as success


def list_subscribers(active_only: bool = True) -> list[dict]:
    q = select(subscribers.c.email, subscribers.c.created_at, subscribers.c.unsubscribed_at)
    if active_only:
        q = q.where(subscribers.c.unsubscribed_at.is_(None))
    with engine.connect() as c:
        return [dict(r._mapping) for r in c.execute(q.order_by(subscribers.c.id))]
