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
| `CONTACT_FROM` | Optional. Sender address verified in Resend (also used for the fan-list welcome email). |
| `WHATSAPP_NUMBER` | Optional. Number with country code, e.g. `255700000000`. Shows a "Book on WhatsApp" button. |
| `ADMIN_TOKEN` | Optional. Long random string. Enables the fan-list CSV export (see below). |
| `SITE_URL` | Optional. Public address used in canonical links, sitemap and emails (default `https://zimbermanne.com`). |
| `PLAUSIBLE_DOMAIN` | Optional. Your domain as registered in Plausible (e.g. `zimbermanne.com`). Turns analytics on. |
| `VIEW_MULTIPLIER` | Optional. The visitor counter shows real count x this number (default 100, set 1 for exact). |

Every inquiry is saved in the `messages` table first, so nothing is lost if email is not set up.

## Fan list
Visitors sign up under "Stay close". Addresses go in the `subscribers` table, each with a private
unsubscribe link (`/unsubscribe/<token>`, asks for confirmation first). With Resend set up, new
subscribers also get a welcome email containing that link. Export the list:

```
curl -H "Authorization: Bearer $ADMIN_TOKEN" https://zimbermanne.com/admin/subscribers.csv -o fans.csv
```
Add `?all=1` to include people who unsubscribed (never email them).

## Song pages
Every track in `music.json` gets `/song/<slug>` (slug from the title, duplicates get `-2`), with cover,
lyrics, player, Suno link, share button and share preview tags. `/sitemap.xml` and `robots.txt` are
generated, so a new song is in the sitemap as soon as it is in `music.json`.

## Update the music
Edit `music.json` by hand, or let the sync do it: `.github/workflows/sync-music.yml` runs
`python sync_suno.py` every day and commits `music.json` only when a link changed. Run it yourself with
`python sync_suno.py --dry-run`. If Suno's page changes and nothing can be read, the file is left alone
and the run fails (visible in the GitHub Actions tab).
The sync updates each track's `url`, `audioUrl` and `image` (its Suno artwork, used on the song page,
share preview and player bar). A track with no `image` falls back to its album cover. Album covers are
not synced; change them by hand in `music.json`. New songs on Suno are listed in the log but must be
added to `music.json` by hand, because the script cannot know which album they belong to.

## MP3 download
Every track has an `MP3` link on the home page and a "Download MP3" button on its song page. They point to
`/download/<slug>.mp3`, which streams the song's MP3 from Suno's CDN (`cdn1.suno.ai/<song id>.mp3`, the id is taken
from the track's `url`) through the site, with the right filename. `app/static/download.js` reads that stream in
chunks while showing progress, and when the stream is complete builds one MP3 file and saves it. Without JavaScript
the link is a normal download. Only Suno's CDN is ever fetched, the route is rate limited, and `/download/` is
disallowed in `robots.txt`. If a download fails with "Failed, retry", Suno has no MP3 at that address for the song
(check the `/download/<slug>.mp3` response on Railway).

## Tests
```
pip install -r requirements-dev.txt
pytest
```

## Files
- `app/main.py` routes, contact form, fan list, sitemap, rate limit, email
- `app/music.py` music.json loader, song slugs, schema.org markup
- `app/db.py` visitor counter, messages and subscribers
- `app/templates/` home page, song page, notices; `app/static/` styles and player script
- `sync_suno.py` Suno sync, `.github/workflows/sync-music.yml` its schedule
- `railway.json` start command and health check
