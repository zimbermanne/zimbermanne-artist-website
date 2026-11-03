import re
import secrets
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audio, catalog, config, mailer
from ..database import get_db
from ..models import Counter, Message, Subscriber, Track
from ..security import client_ip, rate_limited

router = APIRouter()
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
BOTS = re.compile(r"bot|crawl|spider|slurp|preview|facebookexternalhit|curl|python-requests|httpx", re.I)


def _views(db: Session) -> int:
    row = db.get(Counter, "views")
    return (row.value if row else 0) * config.VIEW_MULTIPLIER


@router.get("/api/music")
def music(db: Session = Depends(get_db)):
    return {"albums": [catalog.album_out(a) for a in catalog.ordered_albums(db)]}


@router.get("/api/song/{slug}")
def song(slug: str, db: Session = Depends(get_db)):
    track = db.scalar(select(Track).where(Track.slug == slug))
    if not track:
        return JSONResponse({"detail": "Song not found"}, status_code=404)
    queue = [t for a in catalog.ordered_albums(db) for t in a.tracks]
    i = next(n for n, t in enumerate(queue) if t.id == track.id)
    nb = lambda t: {"slug": t.slug, "title": t.title} if t else None  # noqa: E731
    return {
        "track": catalog.track_out(track), "album": catalog.album_out(track.album, with_tracks=False),
        "prev": nb(queue[i - 1]) if i > 0 else None,
        "next": nb(queue[i + 1]) if i < len(queue) - 1 else None,
    }


@router.get("/api/site")
def site(db: Session = Depends(get_db)):
    wa = f"https://wa.me/{config.WHATSAPP_NUMBER}?text=" + quote("Hi Zimbermanne, I'd like to book you.") if config.WHATSAPP_NUMBER else None
    return {"whatsappUrl": wa, "views": _views(db)}


@router.post("/api/visit")
def visit(request: Request, response: Response, db: Session = Depends(get_db)):
    """Counts one view per browser (cookie), ignoring bots."""
    if not request.cookies.get("zv") and not BOTS.search(request.headers.get("user-agent", "")):
        row = db.get(Counter, "views") or Counter(name="views", value=0)
        row.value += 1
        db.add(row)
        db.commit()
        response.set_cookie("zv", "1", max_age=60 * 60 * 24 * 365, httponly=True, samesite="lax")
    return {"views": _views(db)}


class ContactIn(BaseModel):
    name: str = Field(max_length=120)
    email: str = Field(max_length=254)
    message: str = Field(max_length=5000)
    website: str = ""  # honeypot


class SubscribeIn(BaseModel):
    email: str = Field(max_length=254)
    website: str = ""


def _reply(ok: bool, message: str, status: int = 200):
    return JSONResponse({"ok": ok, "type": "success" if ok else "error", "message": message}, status_code=status)


@router.post("/api/contact")
def contact(body: ContactIn, request: Request, tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if body.website:  # bots fill the hidden field; pretend it worked
        return _reply(True, "Thank you, your message was sent.")
    if rate_limited("contact:" + client_ip(request), 5, 3600):
        return _reply(False, "Too many messages, please try again later.", 429)
    name, email, text = body.name.strip(), body.email.strip(), body.message.strip()
    if not name or not text or not EMAIL.match(email):
        return _reply(False, "Please fill in your name, a valid email and a message.", 422)
    db.add(Message(name=name, email=email, body=text))
    db.commit()
    tasks.add_task(mailer.send_email, config.CONTACT_TO, f"Booking inquiry from {name}", f"{name} <{email}>\n\n{text}", email)
    return _reply(True, "Thank you, your message was sent.")


@router.post("/api/subscribe")
def subscribe(body: SubscribeIn, request: Request, tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if body.website:
        return _reply(True, "You're on the list.")
    if rate_limited("sub:" + client_ip(request), 8, 3600):
        return _reply(False, "Too many attempts, please try again later.", 429)
    email = body.email.strip().lower()
    if not EMAIL.match(email):
        return _reply(False, "Please enter a valid email address.", 422)
    sub = db.scalar(select(Subscriber).where(Subscriber.email == email))
    if sub and sub.active:
        return _reply(True, "You're already on the list.")
    if sub:
        sub.active, sub.unsubscribed_at = True, None
    else:
        sub = Subscriber(email=email)
        db.add(sub)
    db.commit()
    link = f"{config.SITE_URL}/unsubscribe/{sub.token}"
    tasks.add_task(mailer.send_email, email, "Welcome to Zimbermanne", f"Thank you for staying close.\n\nLeave anytime: {link}")
    return _reply(True, "You're on the list. Thank you!")


@router.get("/api/unsubscribe/{token}")
def unsubscribe_info(token: str, db: Session = Depends(get_db)):
    sub = db.scalar(select(Subscriber).where(Subscriber.token == token))
    return {"valid": bool(sub), "active": bool(sub and sub.active)}


@router.post("/api/unsubscribe/{token}")
def unsubscribe(token: str, db: Session = Depends(get_db)):
    sub = db.scalar(select(Subscriber).where(Subscriber.token == token))
    if not sub:
        return _reply(False, "This link is not valid.", 404)
    sub.active, sub.unsubscribed_at = False, datetime.now(timezone.utc)
    db.commit()
    return _reply(True, "You have been removed from the list.")


@router.get("/download/{slug}.mp3", include_in_schema=False)
async def download(request: Request, slug: str, db: Session = Depends(get_db)):
    t = db.scalar(select(Track).where(Track.slug == slug))
    data = {"title": t.title, "url": t.url, "audioUrl": t.audio_url} if t else None
    if not data or not audio.song_id(data):
        return JSONResponse({"detail": "No audio for this song"}, status_code=404)
    if rate_limited("dl:" + client_ip(request), 200, 3600):
        return JSONResponse({"detail": "Too many downloads, try again later"}, status_code=429)
    try:
        path = await audio.ensure_mp3(data, t.album.title)
    except audio.AudioError as e:
        print(f"download failed for {slug}: {e}", flush=True)
        return JSONResponse({"detail": "Audio source unavailable"}, status_code=502)
    name = re.sub(r"[^\w .()'&-]+", "", t.title + (f" {t.subtitle}" if t.subtitle else "")).strip() + " - Zimbermanne.mp3"
    return FileResponse(path, media_type="audio/mpeg", headers={
        "Content-Disposition": f"attachment; filename=\"{slug}.mp3\"; filename*=UTF-8''{quote(name)}",
        "Cache-Control": "public, max-age=3600", "Content-Encoding": "identity",
    })
