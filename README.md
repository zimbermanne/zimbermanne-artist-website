# Zimbermanne: artist website (React + FastAPI)

Same layout as MoneyTracer: a FastAPI backend (`backend/`) and a Vite + React frontend (`frontend/`).
In production one Railway service builds both (see `Dockerfile`) and FastAPI serves the built React app.

| Part | What it does |
|---|---|
| `backend/app/routers/public.py` | `/api/music`, `/api/song/:slug`, `/api/site`, `/api/visit`, `/api/contact`, `/api/subscribe`, `/api/unsubscribe/:token`, `/download/:slug.mp3` |
| `backend/app/routers/auth.py` | Admin login (JWT), change password |
| `backend/app/routers/admin.py` | Albums and songs CRUD, inbox, fan list + CSV, stats (all need the admin token) |
| `frontend/src/pages.jsx` | Home, song pages, unsubscribe |
| `frontend/src/admin.jsx` | `/admin`: overview, albums & songs, inbox, fan list, account |

On first start the database is filled from `backend/music.json`. After that you manage music in `/admin`.

## Platform sync (Admin > Sync)
Runs every `SYNC_INTERVAL_HOURS` (default 12) and on "Run now". It only fills in and adds; titles, lyrics and
anything you edited are never overwritten, and songs are matched by Suno ID or exact title.

| Source | Needs | Gives |
|---|---|---|
| Suno | nothing (public profile + album pages) | songs, albums, artwork, plays |
| Spotify | `SPOTIFY_CLIENT_ID` / `SECRET` (app owner needs Premium) | Spotify links + cover art for matching songs |
| SoundCloud | `SOUNDCLOUD_CLIENT_ID` / `SECRET` (Artist Pro to register an app) | plays, followers, links, artwork |

Spotify no longer returns followers/popularity to apps and never returned monthly listeners: type that
number in Admin > Sync. Suno shows plays, not "listeners". New database columns are added automatically on start.

## Run locally
```
# terminal 1: API on :8000
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
ADMIN_EMAIL=you@example.com ADMIN_PASSWORD=change-me-please uvicorn app.main:app --reload

# terminal 2: React on :5173 (proxies /api and /download to :8000)
cd frontend && npm install && npm run dev
```
Public site: http://localhost:5173 · Admin: http://localhost:5173/admin

## Deploy on Railway
1. Push this folder as the repo root. Railway uses `railway.json` + `Dockerfile`.
2. Variables: copy from `.env.example`. `DATABASE_URL` is a reference to the Postgres service,
   `SECRET_KEY` a long random string, `ADMIN_EMAIL` / `ADMIN_PASSWORD` create your admin on first boot.
3. Check `/healthz`, the home page, then sign in at `/admin/login` and change the password.

## Tests
`cd backend && pytest`
