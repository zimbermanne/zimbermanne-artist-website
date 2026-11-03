"""Suno sync that writes straight into the database: no GitHub commit, no redeploy.

What one run does
  1. Reads the catalog (albums and tracks) and the Suno profile.
  2. Uses the same ID-based rules as sync_suno.py: every known track gets its artwork from its own
     Suno song page, and songs that are not in music.json yet are added to "New Releases".
  3. Saves those results in the database (tables song_sync and new_songs).
  4. Copies every Suno-hosted image (album covers and track artwork) into the `media` table, so the
     site serves them from its own database at /media/<id>.<ext> and no longer depends on Suno.
  5. Records the run (sync_runs table) so a failure can be read afterwards.

music.json stays the place where albums, lyrics, titles and order are edited by hand.
"""
import asyncio
import hashlib
import logging
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from . import db, music

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import sync_suno as core  # noqa: E402  (repo-root module with the parsing rules)

log = logging.getLogger("sync")
MAX_IMAGE_BYTES = 5 * 1024 * 1024
REQUEST_DELAY = 0.3          # seconds between Suno requests
_lock = threading.Lock()


def media_key(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def mirror_image(client: httpx.Client, url: str) -> str:
    """Copy one Suno-hosted image into the database. Returns 'stored', 'have' or 'failed: <why>'."""
    if core.suno_image(url) != url:
        return "failed: not a Suno image address"
    key = media_key(url)
    if db.has_media(key):
        return "have"
    try:
        r = client.get(url, headers={"User-Agent": core.USER_AGENTS[0]})
    except httpx.HTTPError as exc:
        return f"failed: {exc.__class__.__name__}"
    if r.status_code != 200:
        return f"failed: HTTP {r.status_code}"
    if not core.IMAGE_HOST_RE.match(str(r.url)):
        return "failed: redirected away from Suno"
    ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
    if ctype not in db.MEDIA_EXT:
        return f"failed: unsupported type {ctype or 'unknown'}"
    if not r.content or len(r.content) > MAX_IMAGE_BYTES:
        return "failed: empty or too large"
    db.save_media(key, url, ctype, r.content)
    return "stored"


def _image_urls(data: dict) -> list[str]:
    urls = []
    for album in data.get("albums", []):
        urls.append(album.get("cover"))
        urls.extend(t.get("image") for t in album.get("tracks", []))
    seen, out = set(), []
    for u in urls:
        if u and core.suno_image(u) == u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def run_sync() -> dict:
    """One full sync run. Safe to call from any thread; a second call while one runs is skipped."""
    if not _lock.acquire(blocking=False):
        return {"ok": False, "skipped": True, "summary": "a sync is already running"}
    run_id = None
    lines: list[str] = []
    ok = False
    try:
        run_id = db.start_sync_run()
        base = music.base_catalog()
        if base is None:
            lines.append("no catalog found (music.json missing or invalid)")
            return {"ok": False, "summary": "\n".join(lines), "run_id": run_id}

        data = music.build(base, mirror=False)          # catalog + earlier sync results, original image URLs
        base_ids = {music.song_id(t.get("url")): bool(t.get("image"))
                    for a in base.get("albums", []) for t in a.get("tracks", [])} 
        base_ids.pop(None, None)
        handle = base.get("handle", "")
        profile_url = base.get("sunoProfile") or f"https://suno.com/{handle}"

        with httpx.Client(timeout=30, follow_redirects=True) as client:
            clips: dict[str, dict] = {}
            try:
                r = client.get(profile_url, headers={"User-Agent": core.USER_AGENTS[0]})
                r.raise_for_status()
                clips = core.parse_clips(r.text, handle)
                lines.append(f"profile lists {len(clips)} songs")
            except httpx.HTTPError as exc:
                lines.append(f"profile could not be fetched: {exc}")

            def lookup(sid):
                time.sleep(REQUEST_DELAY)
                return core.fetch_song(client, sid)

            result = core.apply_sync(data, clips, lookup)
            lines.append(f"song pages read: {result['read']} of {result['checked']} tracks")
            readable = bool(clips) or result["read"] > 0
            if readable:
                images: dict[str, str] = {}
                new: list[dict] = []
                for album in data.get("albums", []):
                    for t in album.get("tracks", []):
                        sid = music.song_id(t.get("url"))
                        if not sid:
                            continue
                        if sid not in base_ids:        # a song the catalog does not have: keep it as "new"
                            new.append({"song_id": sid, "title": t["title"], "url": t["url"],
                                        "audio_url": t.get("audioUrl") or core.audio_url(sid),
                                        "image": t.get("image")})
                        elif t.get("image") and not base_ids[sid]:
                            images[sid] = t["image"]
                db.save_overlay(images, new)
                lines.append(f"saved: {len(images)} track artworks, {len(new)} new songs")
                for title in result["new"]:
                    lines.append(f"new song added: {title}")
            else:
                lines.append("nothing could be read from Suno (blocked or layout changed); earlier results kept")
            for key in ("alternates", "missing", "left_out"):
                if result.get(key):
                    label = {"alternates": "same title, different version (ignored)",
                             "missing": "song page not found", "left_out": "not added this run (limit)"}[key]
                    lines.append(f"{label}: {', '.join(result[key])}")

            # copy every Suno image into the database
            tally = {"stored": 0, "have": 0, "failed": 0}
            for url in _image_urls(data):
                outcome = mirror_image(client, url)
                tally["failed" if outcome.startswith("failed") else outcome] += 1
                if outcome.startswith("failed"):
                    lines.append(f"image not copied ({outcome}): {url}")
                if outcome == "stored":
                    time.sleep(REQUEST_DELAY)
            lines.append(f"images: {tally['stored']} copied, {tally['have']} already stored, {tally['failed']} failed")
            ok = readable                      # did we manage to read anything from Suno itself?

        music.invalidate()
        return {"ok": ok, "summary": "\n".join(lines), "run_id": run_id}
    except Exception as exc:  # never let a sync problem reach the website
        log.exception("sync failed")
        lines.append(f"error: {exc.__class__.__name__}: {exc}")
        return {"ok": False, "summary": "\n".join(lines), "run_id": run_id}
    finally:
        if run_id is not None:
            try:
                db.finish_sync_run(run_id, ok, "\n".join(lines))
            except Exception:
                log.exception("could not record sync run")
        _lock.release()


async def scheduler(interval_hours: float, first_delay: float = 120) -> None:
    """Run the sync every `interval_hours`. After a deploy it waits until the last run is due."""
    delay = first_delay
    try:
        last = db.list_sync_runs(1)
        if last and last[0].get("finished_at"):
            finished = last[0]["finished_at"]
            if finished.tzinfo is None:
                finished = finished.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - finished).total_seconds()
            delay = max(first_delay, interval_hours * 3600 - age)
    except Exception:
        pass
    while True:
        await asyncio.sleep(delay)
        try:
            await asyncio.to_thread(run_sync)
        except Exception:
            log.exception("scheduled sync failed")
        delay = interval_hours * 3600
