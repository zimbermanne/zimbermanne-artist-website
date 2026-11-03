import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import catalog, config
from ..database import get_db
from ..models import Album, Counter, Message, Subscriber, Track
from ..security import current_admin

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(current_admin)])


class AlbumIn(BaseModel):
    title: str
    number: str = ""
    tagline: str = ""
    description: str = ""
    cover: str = ""
    chips: list[str] = []
    position: int | None = None


class TrackIn(BaseModel):
    title: str
    subtitle: str = ""
    url: str = ""
    audioUrl: str = ""
    image: str = ""
    duration: str = ""
    lyrics: str = ""
    position: int | None = None


def _album(db: Session, album_id: int) -> Album:
    a = db.get(Album, album_id)
    if not a:
        raise HTTPException(404, "Album not found")
    return a


def _track(db: Session, track_id: int) -> Track:
    t = db.get(Track, track_id)
    if not t:
        raise HTTPException(404, "Song not found")
    return t


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    count = lambda q: db.scalar(q) or 0  # noqa: E731
    views = db.get(Counter, "views")
    return {
        "views": (views.value if views else 0) * config.VIEW_MULTIPLIER,
        "albums": count(select(func.count(Album.id))),
        "tracks": count(select(func.count(Track.id))),
        "subscribers": count(select(func.count(Subscriber.id)).where(Subscriber.active.is_(True))),
        "messages": count(select(func.count(Message.id))),
        "unread": count(select(func.count(Message.id)).where(Message.is_read.is_(False))),
    }


# ---- albums ----
@router.get("/albums")
def list_albums(db: Session = Depends(get_db)):
    return [catalog.album_out(a) for a in catalog.ordered_albums(db)]


@router.post("/albums", status_code=201)
def create_album(body: AlbumIn, db: Session = Depends(get_db)):
    if not body.title.strip():
        raise HTTPException(422, "Title is required")
    last = db.scalar(select(func.max(Album.position))) or 0
    a = Album(key=catalog.unique_album_key(db, body.title), number=body.number, title=body.title.strip(),
              tagline=body.tagline, description=body.description, cover=body.cover,
              position=body.position if body.position is not None else last + 1)
    a.chips = body.chips
    db.add(a)
    db.commit()
    return catalog.album_out(a)


@router.put("/albums/{album_id}")
def update_album(album_id: int, body: AlbumIn, db: Session = Depends(get_db)):
    a = _album(db, album_id)
    a.title, a.number, a.tagline = body.title.strip(), body.number, body.tagline
    a.description, a.cover, a.chips = body.description, body.cover, body.chips
    if body.position is not None:
        a.position = body.position
    db.commit()
    return catalog.album_out(a)


@router.delete("/albums/{album_id}", status_code=204)
def delete_album(album_id: int, db: Session = Depends(get_db)):
    db.delete(_album(db, album_id))
    db.commit()


# ---- tracks ----
@router.post("/albums/{album_id}/tracks", status_code=201)
def create_track(album_id: int, body: TrackIn, db: Session = Depends(get_db)):
    a = _album(db, album_id)
    if not body.title.strip():
        raise HTTPException(422, "Title is required")
    last = db.scalar(select(func.max(Track.position)).where(Track.album_id == a.id))
    t = Track(album_id=a.id, slug=catalog.unique_slug(db, body.title), title=body.title.strip(),
              subtitle=body.subtitle, url=body.url, audio_url=body.audioUrl, image=body.image,
              duration=body.duration, lyrics=body.lyrics,
              position=body.position if body.position is not None else (last if last is not None else -1) + 1)
    db.add(t)
    db.commit()
    return catalog.track_out(t)


@router.put("/tracks/{track_id}")
def update_track(track_id: int, body: TrackIn, db: Session = Depends(get_db)):
    t = _track(db, track_id)
    if body.title.strip() != t.title:  # the slug is the public link, so it only changes with the title
        t.slug = catalog.unique_slug(db, body.title, exclude_id=t.id)
    t.title, t.subtitle, t.url, t.audio_url = body.title.strip(), body.subtitle, body.url, body.audioUrl
    t.image, t.duration, t.lyrics = body.image, body.duration, body.lyrics
    if body.position is not None:
        t.position = body.position
    db.commit()
    return catalog.track_out(t)


@router.delete("/tracks/{track_id}", status_code=204)
def delete_track(track_id: int, db: Session = Depends(get_db)):
    db.delete(_track(db, track_id))
    db.commit()


# ---- inbox + fan list ----
@router.get("/messages")
def messages(db: Session = Depends(get_db)):
    rows = db.scalars(select(Message).order_by(Message.created_at.desc()))
    return [{"id": m.id, "name": m.name, "email": m.email, "message": m.body, "read": m.is_read,
             "createdAt": m.created_at.isoformat()} for m in rows]


class ReadIn(BaseModel):
    read: bool = True


@router.patch("/messages/{message_id}")
def mark_message(message_id: int, body: ReadIn, db: Session = Depends(get_db)):
    m = db.get(Message, message_id)
    if not m:
        raise HTTPException(404, "Message not found")
    m.is_read = body.read
    db.commit()
    return {"ok": True}


@router.delete("/messages/{message_id}", status_code=204)
def delete_message(message_id: int, db: Session = Depends(get_db)):
    m = db.get(Message, message_id)
    if m:
        db.delete(m)
        db.commit()


@router.get("/subscribers")
def subscribers(db: Session = Depends(get_db)):
    rows = db.scalars(select(Subscriber).order_by(Subscriber.created_at.desc()))
    return [{"id": s.id, "email": s.email, "active": s.active, "createdAt": s.created_at.isoformat()} for s in rows]


@router.get("/subscribers.csv")
def subscribers_csv(all: bool = False, db: Session = Depends(get_db)):
    q = select(Subscriber).order_by(Subscriber.created_at)
    if not all:
        q = q.where(Subscriber.active.is_(True))
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["email", "active", "subscribed_at"])
    for s in db.scalars(q):
        w.writerow([s.email, s.active, s.created_at.isoformat()])
    return Response(out.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=fans.csv"})
