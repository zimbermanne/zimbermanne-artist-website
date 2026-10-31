"""Storage: Postgres on Railway (DATABASE_URL), SQLite file locally."""
import os
from datetime import datetime, timezone

from sqlalchemy import (BigInteger, Boolean, Column, DateTime, Integer,
                        MetaData, String, Table, Text, create_engine, select)


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


def init_db() -> None:
    metadata.create_all(engine)
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
