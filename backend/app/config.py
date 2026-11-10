"""All settings come from environment variables (Railway -> service -> Variables)."""
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_db = os.environ.get("DATABASE_URL", "").strip()
if _db.startswith("postgres://"):
    _db = "postgresql://" + _db[len("postgres://"):]
if _db.startswith("postgresql://"):
    _db = "postgresql+psycopg://" + _db[len("postgresql://"):]
DATABASE_URL = _db or f"sqlite:///{ROOT / 'data' / 'site.db'}"

# Without SECRET_KEY, tokens stop working after every restart. Set it on Railway.
SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_urlsafe(48)
TOKEN_HOURS = int(os.environ.get("TOKEN_HOURS", "12"))

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "").strip().lower()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

SITE_URL = os.environ.get("SITE_URL", "https://zimbermanne.com").rstrip("/")
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
CONTACT_TO = os.environ.get("CONTACT_TO", "hello@zimbermanne.com")
CONTACT_FROM = os.environ.get("CONTACT_FROM", "")
WHATSAPP_NUMBER = "".join(c for c in os.environ.get("WHATSAPP_NUMBER", "") if c.isdigit())
VIEW_MULTIPLIER = int(os.environ.get("VIEW_MULTIPLIER", "1"))

MUSIC_SEED = ROOT / "music.json"
FRONTEND_DIST = Path(os.environ.get("FRONTEND_DIST") or ROOT.parent / "frontend" / "dist")

# ---- platform sync ----
SUNO_HANDLE = os.environ.get("SUNO_HANDLE", "zimbermanne").lstrip("@")
SPOTIFY_ARTIST_ID = os.environ.get("SPOTIFY_ARTIST_ID", "5Vu9W8pe9bnT644cJoo8YG")
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
SOUNDCLOUD_PROFILE_URL = os.environ.get("SOUNDCLOUD_PROFILE_URL", "https://soundcloud.com/zimbermann-elit")
SOUNDCLOUD_CLIENT_ID = os.environ.get("SOUNDCLOUD_CLIENT_ID", "")
SOUNDCLOUD_CLIENT_SECRET = os.environ.get("SOUNDCLOUD_CLIENT_SECRET", "")
SYNC_INTERVAL_HOURS = float(os.environ.get("SYNC_INTERVAL_HOURS", "12"))  # 0 = only when you press "Run now"
SYNC_MAX_NEW = int(os.environ.get("SYNC_MAX_NEW", "40"))                   # new songs added per run, per source
