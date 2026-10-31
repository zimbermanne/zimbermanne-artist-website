"""Zimbermanne artist website: FastAPI + Jinja2 (port of the PHP site)."""
import json
import os
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import BackgroundTasks, FastAPI, Form, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import db

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
MUSIC_FILE = ROOT / "music.json"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Shown number = real count x VIEW_MULTIPLIER (set the variable to 1 for the exact count)
VIEW_MULTIPLIER = int(os.getenv("VIEW_MULTIPLIER", "10"))
BOT_WORDS = ("bot", "crawl", "spider", "slurp", "preview", "facebookexternalhit")

templates = Jinja2Templates(directory=str(APP_DIR / "templates"))

# status messages shown after the contact form redirect
FORM_MESSAGES = {
    "sent": ("success", "Thank you! Your booking inquiry has been received."),
    "invalid": ("error", "Please provide your name, a valid email address and a message."),
    "limit": ("error", "Too many messages from your connection. Please try again later."),
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Zimbermanne", lifespan=lifespan, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")

_music_cache = {"mtime": 0.0, "data": {"albums": []}}


def load_music() -> dict:
    """Reload music.json only when the file changes."""
    try:
        mtime = MUSIC_FILE.stat().st_mtime
        if mtime != _music_cache["mtime"]:
            _music_cache["data"] = json.loads(MUSIC_FILE.read_text(encoding="utf-8"))
            _music_cache["mtime"] = mtime
    except (OSError, json.JSONDecodeError):
        pass  # keep the last good copy
    return _music_cache["data"]


_hits: dict[str, list[float]] = {}


def rate_limited(ip: str, limit: int = 5, window: int = 3600) -> bool:
    now = time.time()
    recent = [t for t in _hits.get(ip, []) if now - t < window]
    if len(recent) >= limit:
        _hits[ip] = recent
        return True
    recent.append(now)
    _hits[ip] = recent
    return False


def send_email(message_id: int, name: str, email: str, message: str) -> None:
    """Email the inquiry through Resend. The message is already saved in the database."""
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        return
    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "from": os.getenv("CONTACT_FROM", "Zimbermanne Site <onboarding@resend.dev>"),
                "to": [os.getenv("CONTACT_TO", "hello@zimbermanne.com")],
                "reply_to": email,
                "subject": f"Booking inquiry from {name}",
                "text": f"From: {name} <{email}>\n\n{message}",
            },
            timeout=10,
        )
        if r.status_code < 300:
            db.mark_emailed(message_id)
    except httpx.HTTPError:
        pass


@app.get("/")
async def index(request: Request, status: str | None = None):
    ua = request.headers.get("user-agent", "").lower()
    is_bot = any(w in ua for w in BOT_WORDS)
    new_visitor = "zv" not in request.cookies and not is_bot
    views = db.bump_views() if new_visitor else db.get_views()

    kind_msg = FORM_MESSAGES.get(status or "")
    form_status = {"type": kind_msg[0], "msg": kind_msg[1]} if kind_msg else None

    response = templates.TemplateResponse(
        request, "index.html",
        {"albums": load_music().get("albums", []), "views": f"{views * VIEW_MULTIPLIER:,}", "form_status": form_status},
    )
    if new_visitor:
        response.set_cookie("zv", "1", max_age=86400, httponly=True, samesite="lax")
    return response


@app.post("/contact")
async def contact(
    request: Request,
    background: BackgroundTasks,
    name: str = Form(""),
    email: str = Form(""),
    message: str = Form(""),
    website: str = Form(""),  # honeypot: real visitors leave it empty
):
    if website:  # bot filled the hidden field: pretend it worked
        return RedirectResponse("/?status=sent#contact", status_code=303)

    ip = request.client.host if request.client else "unknown"
    if rate_limited(ip):
        return RedirectResponse("/?status=limit#contact", status_code=303)

    name, email, message = name.strip(), email.strip(), message.strip()
    if not name or not message or len(name) > 120 or len(message) > 5000 or not EMAIL_RE.match(email) or len(email) > 254:
        return RedirectResponse("/?status=invalid#contact", status_code=303)

    message_id = db.save_message(name, email, message)
    background.add_task(send_email, message_id, name, email, message)
    return RedirectResponse("/?status=sent#contact", status_code=303)


@app.get("/healthz")
async def healthz():
    return JSONResponse({"ok": True})


@app.get("/favicon.svg", include_in_schema=False)
async def favicon():
    return FileResponse(APP_DIR / "static" / "favicon.svg", media_type="image/svg+xml")


@app.get("/robots.txt", include_in_schema=False)
async def robots():
    return FileResponse(APP_DIR / "static" / "robots.txt", media_type="text/plain")


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap():
    return FileResponse(APP_DIR / "static" / "sitemap.xml", media_type="application/xml")
