"""Runs one source or all of them, records each run, and the background schedule."""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from .. import config
from ..database import SessionLocal
from ..models import SyncRun
from . import soundcloud, spotify, suno
from .common import SyncError

log = logging.getLogger("zimbermanne.sync")
SOURCES = {"suno": suno, "spotify": spotify, "soundcloud": soundcloud}
_lock = {"busy": False}


def is_configured(name: str) -> bool:
    return True if name == "suno" else SOURCES[name].configured()


def run_source(name: str) -> dict:
    """Blocking. Returns {ok, summary, log}. Never raises."""
    if name not in SOURCES:
        return {"ok": False, "summary": "Unknown source", "log": ""}
    with SessionLocal() as db:
        run = SyncRun(source=name, started_at=datetime.now(timezone.utc))
        try:
            report = SOURCES[name].run(db)
            run.ok = True
            run.summary = f"{report.changed} changes" if report.changed else "nothing changed"
            run.log = report.text
        except SyncError as e:
            db.rollback()
            run.summary, run.log = str(e)[:300], str(e)
        except Exception as e:  # a layout change or network problem must not crash the site
            db.rollback()
            log.exception("sync %s crashed", name)
            run.summary, run.log = f"Unexpected error: {type(e).__name__}", f"{type(e).__name__}: {e}"
        db.add(run)
        db.commit()
        return {"ok": run.ok, "summary": run.summary, "log": run.log}


def run_all() -> dict:
    if _lock["busy"]:
        return {}
    _lock["busy"] = True
    try:
        return {n: run_source(n) for n in SOURCES if is_configured(n)}
    finally:
        _lock["busy"] = False


def last_runs() -> dict:
    out = {}
    with SessionLocal() as db:
        for n in SOURCES:
            r = db.scalar(select(SyncRun).where(SyncRun.source == n).order_by(SyncRun.started_at.desc()).limit(1))
            out[n] = None if not r else {"ok": r.ok, "summary": r.summary, "log": r.log, "at": r.started_at.isoformat()}
    return out


async def scheduler():
    """Every SYNC_INTERVAL_HOURS (first run 2 minutes after boot, so deploys stay fast)."""
    if config.SYNC_INTERVAL_HOURS <= 0:
        return
    await asyncio.sleep(120)
    while True:
        try:
            await asyncio.to_thread(run_all)
        except Exception:
            log.exception("scheduled sync failed")
        await asyncio.sleep(config.SYNC_INTERVAL_HOURS * 3600)
