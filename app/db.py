"""Storage: Postgres on Railway (DATABASE_URL), SQLite file locally."""
import os
import secrets
from datetime import datetime, timezone

from sqlalchemy import (BigInteger, Boolean, Column, DateTime, Integer,
                        MetaData, String, Table, Text, create_engine, select)
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
