# Zimbermanne artist website (FastAPI)

Server-rendered artist site: FastAPI + Jinja2, music data from `music.json`,
Postgres on Railway (SQLite locally).

## Run locally
```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000. Local data goes to `data/site.db`.

## Environment variables (Railway → service → Variables)
| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Add it as a reference to the Postgres service. Without it the app uses a local SQLite file, which Railway wipes on every deploy. |
| `RESEND_API_KEY` | Optional. When set, booking inquiries are also emailed through Resend. |
| `CONTACT_TO` | Optional. Where inquiries go (default `hello@zimbermanne.com`). |
| `CONTACT_FROM` | Optional. Sender address verified in Resend. |

Every inquiry is saved in the `messages` table first, so nothing is lost if email is not set up.

## Update the music
Edit `music.json` (or run `node sync-suno.js`) and push. The page reloads the file when it changes.

## Files
- `app/main.py` routes, contact form, rate limit, email
- `app/db.py` visitor counter and message storage
- `app/templates/index.html`, `app/static/` page, styles, player script
- `railway.json` start command and health check
