import re
import unicodedata
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Album, PlatformStat, Track

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)


class SyncError(Exception):
    """The source could not be read at all; nothing was changed."""


class Report:
    """What a sync did, shown in the admin and stored in sync_runs."""

    def __init__(self):
        self.lines: list[str] = []
        self.changed = 0

    def change(self, line: str):
        self.changed += 1
        self.lines.append(line)

    def note(self, line: str):
        self.lines.append(line)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)[:20000]


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def song_id(url: str | None) -> str | None:
    m = UUID_RE.search(url or "")
    return m[0].lower() if m else None


def set_attr(obj, field: str, value, report: Report, label: str):
    """Set a field only when the new value is real and different."""
    if value in (None, "", 0) or getattr(obj, field) == value:
        return False
    report.change(f"{label}: {field} -> {value}")
    setattr(obj, field, value)
    return True


def set_stat(db: Session, key: str, value: int):
    """Store an automatic stat, but never overwrite a number someone typed in by hand."""
    row = db.get(PlatformStat, key)
    if row and row.source == "manual":
        return
    now = datetime.now(timezone.utc)
    if row:
        row.value, row.updated_at = int(value), now
    else:
        db.add(PlatformStat(key=key, value=int(value), source="auto", updated_at=now))


def all_tracks(db: Session) -> list[Track]:
    return list(db.scalars(select(Track)))


def all_albums(db: Session) -> list[Album]:
    return list(db.scalars(select(Album)))


def by_title(items) -> dict[str, list]:
    out: dict[str, list] = {}
    for it in items:
        out.setdefault(normalize(it.title), []).append(it)
    return out
