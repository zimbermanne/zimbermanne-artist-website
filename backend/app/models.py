import json
import secrets
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def now():
    return datetime.now(timezone.utc)


class AdminUser(Base):
    __tablename__ = "admin_users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Album(Base):
    __tablename__ = "albums"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)  # url-friendly id
    number: Mapped[str] = mapped_column(String(40), default="")
    title: Mapped[str] = mapped_column(String(200))
    tagline: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    cover: Mapped[str] = mapped_column(String(600), default="")
    chips_json: Mapped[str] = mapped_column(Text, default="[]")
    position: Mapped[int] = mapped_column(Integer, default=0)
    suno_album_id: Mapped[str] = mapped_column(String(60), default="")
    spotify_album_id: Mapped[str] = mapped_column(String(60), default="")
    spotify_url: Mapped[str] = mapped_column(String(600), default="")
    soundcloud_url: Mapped[str] = mapped_column(String(600), default="")
    tracks: Mapped[list["Track"]] = relationship(
        back_populates="album", cascade="all, delete-orphan", order_by="Track.position"
    )

    @property
    def chips(self) -> list[str]:
        try:
            return json.loads(self.chips_json or "[]")
        except ValueError:
            return []

    @chips.setter
    def chips(self, value: list[str]):
        self.chips_json = json.dumps(value or [])


class Track(Base):
    __tablename__ = "tracks"
    id: Mapped[int] = mapped_column(primary_key=True)
    album_id: Mapped[int] = mapped_column(ForeignKey("albums.id", ondelete="CASCADE"), index=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    subtitle: Mapped[str] = mapped_column(String(200), default="")
    url: Mapped[str] = mapped_column(String(600), default="")
    audio_url: Mapped[str] = mapped_column(String(600), default="")
    image: Mapped[str] = mapped_column(String(600), default="")
    duration: Mapped[str] = mapped_column(String(20), default="")
    lyrics: Mapped[str] = mapped_column(Text, default="")
    position: Mapped[int] = mapped_column(Integer, default=0)
    spotify_url: Mapped[str] = mapped_column(String(600), default="")
    soundcloud_url: Mapped[str] = mapped_column(String(600), default="")
    suno_plays: Mapped[int] = mapped_column(Integer, default=0)
    soundcloud_plays: Mapped[int] = mapped_column(Integer, default=0)
    album: Mapped[Album] = relationship(back_populates="tracks")


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254))
    # Same column names as the first version of the site, so existing rows keep working.
    body: Mapped[str] = mapped_column("message", Text)
    emailed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Subscriber(Base):
    __tablename__ = "subscribers"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, default=lambda: secrets.token_urlsafe(24))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @hybrid_property
    def active(self) -> bool:  # active = has not unsubscribed (same rule as the first version)
        return self.unsubscribed_at is None

    @active.expression
    def active(cls):
        return cls.unsubscribed_at.is_(None)


class Counter(Base):
    __tablename__ = "counters"
    name: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, default=0)


class PlatformStat(Base):
    """One number per key, e.g. suno_plays. `source` is "auto" (set by a sync) or "manual" (typed in the admin)."""
    __tablename__ = "platform_stats"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(10), default="auto")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SyncRun(Base):
    __tablename__ = "sync_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(20), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    ok: Mapped[bool] = mapped_column(Boolean, default=False)
    summary: Mapped[str] = mapped_column(String(300), default="")
    log: Mapped[str] = mapped_column(Text, default="")
