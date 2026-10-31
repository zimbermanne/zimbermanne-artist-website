"""Zimbermanne artist website: FastAPI + Jinja2 (port of the PHP site)."""
import csv
import hmac
import io
import os
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape as xml_escape

import httpx
from fastapi import BackgroundTasks, FastAPI, Form, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import audio, db, music

APP_DIR = Path(__file__).resolve().parent
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Shown number = real count x VIEW_MULTIPLIER (set the variable to 1 for the exact count)
VIEW_MULTIPLIER = int(os.getenv("VIEW_MULTIPLIER", "100"))
BOT_WORDS = ("bot", "crawl", "spider", "slurp", "preview", "facebookexternalhit")

SITE_URL = os.getenv("SITE_URL", "https://zimbermanne.com").rstrip("/")
WHATSAPP_NUMBER = re.sub(r"\D", "", os.getenv("WHATSAPP_NUMBER", ""))  # digits only, with country code
PLAUSIBLE_DOMAIN = os.getenv("PLAUSIBLE_DOMAIN", "")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
# changes whenever the CSS/JS change, so browsers can cache them for a long time
ASSET_V = str(int(max((APP_DIR / "static" / f).stat().st_mtime for f in ("style.css", "app.js", "download.js"))))

templates = Jinja2Templates(directory=str(APP_DIR / "templates"))

# status messages shown after the contact / fan-list form redirect
FORM_MESSAGES = {
    "sent": ("success", "Thank you! Your booking inquiry has been received."),
    "invalid": ("error", "Please provide your name, a valid email address and a message."),
    "limit": ("error", "Too many messages from your connection. Please try again later."),
    "subscribed": ("success", "You're on the list! We'll let you know when new songs land."),
    "badsub": ("error", "Please enter a valid email address."),
    "sublimit": ("error", "Too many sign-ups from your connection. Please try again later."),
}
SUBSCRIBE_STATUSES = {"subscribed", "badsub", "sublimit"}


class CachedStatic(StaticFiles):
    """Static files with cache headers: 1 year when the URL carries ?v=, 1 hour otherwise."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            versioned = b"v=" in scope.get("query_string", b"")
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable" if versioned else "public, max-age=3600"
        return response


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Zimbermanne", lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(GZipMiddleware, minimum_size=800)
app.mount("/static", CachedStatic(directory=str(APP_DIR / "static")), name="static")

_hits: dict[str, list[float]] = {}


def rate_limited(key: str, limit: int = 5, window: int = 3600) -> bool:
    now = time.time()
    recent = [t for t in _hits.get(key, []) if now - t < window]
    if len(recent) >= limit:
        _hits[key] = recent
        return True
    recent.append(now)
    _hits[key] = recent
    return False


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def page_context(**extra) -> dict:
    """Values every page template needs."""
    return {"site_url": SITE_URL, "asset_v": ASSET_V, "plausible_domain": PLAUSIBLE_DOMAIN, **extra}


def render_notice(request: Request, title: str, text: str, status_code: int = 200, **extra):
    return templates.TemplateResponse(
        request, "notice.html", page_context(title=title, text=text, **extra), status_code=status_code)


# ---------- email (Resend) ----------

def _resend(payload: dict) -> bool:
    """Send one email through Resend. Returns True on success; never raises."""
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        return False
    payload.setdefault("from", os.getenv("CONTACT_FROM", "Zimbermanne Site <onboarding@resend.dev>"))
    try:
        r = httpx.post("https://api.resend.com/emails", headers={"Authorization": f"Bearer {api_key}"},
                       json=payload, timeout=10)
        return r.status_code < 300
    except httpx.HTTPError:
        return False


def send_email(message_id: int, name: str, email: str, message: str) -> None:
    """Email the inquiry. The message is already saved in the database."""
    ok = _resend({
        "to": [os.getenv("CONTACT_TO", "hello@zimbermanne.com")],
        "reply_to": email,
        "subject": f"Booking inquiry from {name}",
        "text": f"From: {name} <{email}>\n\n{message}",
    })
    if ok:
        db.mark_emailed(message_id)


def send_welcome(email: str, token: str) -> None:
    unsub = f"{SITE_URL}/unsubscribe/{token}"
    _resend({
        "to": [email],
        "subject": "You're on the Zimbermanne list",
        "text": ("Thanks for joining! You'll get a short note when new Zimbermanne songs are out.\n\n"
                 f"Listen anytime: {SITE_URL}\n\nNo longer want these? Unsubscribe: {unsub}"),
        "headers": {"List-Unsubscribe": f"<{unsub}>"},
    })


# ---------- pages ----------

@app.get("/")
async def index(request: Request, status: str | None = None):
    ua = request.headers.get("user-agent", "").lower()
    is_bot = any(w in ua for w in BOT_WORDS)
    # every page load counts, including refreshes; only search-engine and preview bots are skipped
    views = db.get_views() if is_bot else db.bump_views()

    kind_msg = FORM_MESSAGES.get(status or "")
    form_status = {"type": kind_msg[0], "msg": kind_msg[1]} if kind_msg else None

    albums = music.load().get("albums", [])
    whatsapp_url = (f"https://wa.me/{WHATSAPP_NUMBER}?text="
                    + quote("Hello Zimbermanne, I'd like to book you for...")) if WHATSAPP_NUMBER else None
    response = templates.TemplateResponse(
        request, "index.html",
        page_context(albums=albums, views=f"{views * VIEW_MULTIPLIER:,}", form_status=form_status,
                     whatsapp_url=whatsapp_url,
                     form_section="subscribe" if status in SUBSCRIBE_STATUSES else "contact", albums_ld=music.json_script(music.albums_ld(albums, SITE_URL))),
    )
    return response


@app.get("/song/{slug}")
async def song_page(request: Request, slug: str):
    song = music.get_song(slug)
    if not song:
        return render_notice(request, "Song not found", "We couldn't find that song.", 404, back_to_home=True)
    return templates.TemplateResponse(
        request, "song.html",
        page_context(song=song, track=song["track"], album=song["album"],
                     song_ld=music.json_script(music.song_page_ld(song, SITE_URL))),
    )


# ---------- MP3 download ----------

def download_filename(track: dict) -> str:
    name = track["title"] + (f" {track['subtitle']}" if track.get("subtitle") else "")
    return re.sub(r"[^\w .()'&-]+", "", name).strip() + " - Zimbermanne.mp3"


@app.get("/download/{slug}.mp3", include_in_schema=False)
async def download_song(request: Request, slug: str):
    song = music.get_song(slug)
    if not song or not audio.song_id(song["track"]):
        return JSONResponse({"detail": "No audio for this song"}, status_code=404)
    if rate_limited("dl:" + client_ip(request), limit=200, window=3600):
        return JSONResponse({"detail": "Too many downloads, try again later"}, status_code=429)
    try:
        path = await audio.ensure_mp3(song["track"], song["album"]["title"])
    except audio.AudioError as e:
        print(f"download failed for {slug}: {e}", flush=True)  # shows in the Railway logs
        return JSONResponse({"detail": "Audio source unavailable"}, status_code=502)
    filename = download_filename(song["track"])
    return FileResponse(
        path, media_type="audio/mpeg",
        headers={
            "Content-Disposition": f"attachment; filename=\"{slug}.mp3\"; filename*=UTF-8''{quote(filename)}",
            "Cache-Control": "public, max-age=3600",
            "Content-Encoding": "identity",  # keeps gzip off the mp3 so Content-Length (progress) survives
        },
    )


# ---------- contact + fan list ----------

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

    if rate_limited(f"contact:{client_ip(request)}"):
        return RedirectResponse("/?status=limit#contact", status_code=303)

    name, email, message = name.strip(), email.strip(), message.strip()
    if not name or not message or len(name) > 120 or len(message) > 5000 or not EMAIL_RE.match(email) or len(email) > 254:
        return RedirectResponse("/?status=invalid#contact", status_code=303)

    message_id = db.save_message(name, email, message)
    background.add_task(send_email, message_id, name, email, message)
    return RedirectResponse("/?status=sent#contact", status_code=303)


@app.post("/subscribe")
async def subscribe(
    request: Request,
    background: BackgroundTasks,
    email: str = Form(""),
    website: str = Form(""),  # honeypot
):
    if website:
        return RedirectResponse("/?status=subscribed#subscribe", status_code=303)
    if rate_limited(f"subscribe:{client_ip(request)}", limit=10):
        return RedirectResponse("/?status=sublimit#subscribe", status_code=303)

    email = email.strip()
    if len(email) > 254 or not EMAIL_RE.match(email):
        return RedirectResponse("/?status=badsub#subscribe", status_code=303)

    token, is_new = db.add_subscriber(email)
    if is_new:
        background.add_task(send_welcome, email.lower(), token)
    return RedirectResponse("/?status=subscribed#subscribe", status_code=303)


@app.get("/unsubscribe/{token}")
async def unsubscribe_page(request: Request, token: str):
    # GET only asks for confirmation: mail scanners that prefetch links must not unsubscribe people
    if not db.subscriber_exists(token):
        return render_notice(request, "Link not valid", "This unsubscribe link is not valid.", 404, back_to_home=True)
    return render_notice(request, "Unsubscribe", "Stop receiving new-song updates from Zimbermanne?",
                         unsubscribe_token=token)


@app.post("/unsubscribe/{token}")
async def unsubscribe_confirm(request: Request, token: str):
    if not db.unsubscribe(token):
        return render_notice(request, "Link not valid", "This unsubscribe link is not valid.", 404, back_to_home=True)
    return render_notice(request, "Unsubscribed", "You have been unsubscribed. You won't get any more updates.",
                         back_to_home=True)


def _csv_cell(value: str) -> str:
    """Stop spreadsheet programs from running a cell that starts like a formula."""
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


@app.get("/admin/subscribers.csv", include_in_schema=False)
async def export_subscribers(request: Request, token: str = "", all: bool = False):
    """Fan list as CSV. Send `Authorization: Bearer <ADMIN_TOKEN>` (or ?token=). ?all=1 includes unsubscribed."""
    if not ADMIN_TOKEN:
        return PlainTextResponse("Not found", status_code=404)
    header = request.headers.get("authorization", "")
    supplied = header[7:] if header.lower().startswith("bearer ") else token
    if not hmac.compare_digest(supplied.encode(), ADMIN_TOKEN.encode()):
        return PlainTextResponse("Unauthorized", status_code=401)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["email", "subscribed_at", "unsubscribed_at"])
    for row in db.list_subscribers(active_only=not all):
        writer.writerow([_csv_cell(row["email"]), row["created_at"].isoformat(),
                         row["unsubscribed_at"].isoformat() if row["unsubscribed_at"] else ""])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="subscribers.csv"',
                             "Cache-Control": "no-store"})


# ---------- utility routes ----------

@app.get("/healthz")
async def healthz():
    return JSONResponse({"ok": True})


@app.get("/favicon.svg", include_in_schema=False)
async def favicon():
    return FileResponse(APP_DIR / "static" / "favicon.svg", media_type="image/svg+xml")


@app.get("/robots.txt", include_in_schema=False)
async def robots():
    return PlainTextResponse(
        "User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /unsubscribe/\nDisallow: /download/\n\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n")


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap():
    data = music.load()
    lastmod = xml_escape(str(data.get("lastUpdated", "")))
    lm = f"<lastmod>{lastmod}</lastmod>" if lastmod else ""
    images = "".join(
        f"<image:image><image:loc>{xml_escape(a['cover'])}</image:loc>"
        f"<image:title>{xml_escape('Zimbermanne — ' + a['title'] + ' album artwork')}</image:title></image:image>"
        for a in data.get("albums", []) if a.get("cover"))
    urls = [f"<url><loc>{SITE_URL}/</loc>{lm}<changefreq>weekly</changefreq><priority>1.0</priority>{images}</url>"]
    for slug in music.all_slugs():
        urls.append(f"<url><loc>{SITE_URL}/song/{xml_escape(slug)}</loc>{lm}"
                    "<changefreq>monthly</changefreq><priority>0.7</priority></url>")
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
           'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'
           + "\n".join(urls) + "\n</urlset>\n")
    return Response(xml, media_type="application/xml")
