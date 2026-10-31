"""Capture a song's audio stream and turn it into a real MP3 (cached on disk).

Flow for one song:
  1. stream the audio from Suno's CDN into a temporary file (chunk by chunk)
  2. when the stream is complete, convert it to MP3 with ffmpeg (skipped if Suno already sent an MP3)
  3. keep the MP3 in a cache folder, so each song is converted only once
"""
import asyncio
import os
import re
import shutil
import tempfile
import time
from pathlib import Path

import httpx

CACHE_DIR = Path(os.environ.get("AUDIO_CACHE_DIR") or Path(tempfile.gettempdir()) / "zimbermanne-audio")
CACHE_MAX_BYTES = int(os.environ.get("AUDIO_CACHE_MAX_MB", "400")) * 1024 * 1024
MAX_SOURCE_BYTES = 80 * 1024 * 1024
FFMPEG_TIMEOUT = 180
ALLOWED_HOSTS = {"cdn1.suno.ai", "cdn2.suno.ai"}  # audio is only ever fetched from Suno's CDN
SONG_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)

_locks: dict[str, asyncio.Lock] = {}
_convert_slots = asyncio.Semaphore(2)  # at most two ffmpeg runs at once


class AudioError(Exception):
    """The song's audio could not be fetched or converted."""


def song_id(track: dict) -> str | None:
    for key in ("url", "audioUrl"):
        m = SONG_ID.search(track.get(key) or "")
        if m:
            return m.group(0).lower()
    return None


def sources(track: dict) -> list[str]:
    """Where to try, best first: Suno's plain MP3 (no conversion needed), then the stream the player uses."""
    sid = song_id(track)
    urls = []
    if sid:
        urls.append(f"https://cdn1.suno.ai/{sid}.mp3")
    if track.get("audioUrl"):
        urls.append(track["audioUrl"])
    elif sid:
        urls.append(f"https://cdn1.suno.ai/{sid}.mp4")
    return [u for u in dict.fromkeys(urls) if httpx.URL(u).host in ALLOWED_HOSTS]


def ffmpeg_path() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:  # the pip package ships its own ffmpeg binary, so Railway needs no extra setup
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def http_client() -> httpx.AsyncClient:  # tests replace this
    return httpx.AsyncClient(timeout=httpx.Timeout(15.0, read=60.0), follow_redirects=True)


def cached_file(sid: str) -> Path:
    return CACHE_DIR / f"{sid}.mp3"


async def _capture(url: str, dest: Path) -> str:
    """Stream the audio into dest, chunk by chunk. Returns the content type."""
    async with http_client() as client:
        async with client.stream("GET", url) as r:
            if r.status_code != 200:
                raise AudioError(f"source answered {r.status_code}")
            ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
            got = 0
            with open(dest, "wb") as f:
                async for chunk in r.aiter_bytes(65536):
                    got += len(chunk)
                    if got > MAX_SOURCE_BYTES:
                        raise AudioError("source too large")
                    f.write(chunk)
    if got == 0:
        raise AudioError("source was empty")
    return ctype


async def _convert(src: Path, dest: Path, tags: dict) -> None:
    exe = ffmpeg_path()
    if not exe:
        raise AudioError("ffmpeg is not available")
    cmd = [exe, "-y", "-loglevel", "error", "-i", str(src), "-vn", "-map_metadata", "-1",
           "-codec:a", "libmp3lame", "-q:a", "2"]
    for k, v in tags.items():
        if v:
            cmd += ["-metadata", f"{k}={v}"]
    cmd += ["-f", "mp3", str(dest)]
    async with _convert_slots:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        try:
            _, err = await asyncio.wait_for(proc.communicate(), FFMPEG_TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise AudioError("conversion timed out")
    if proc.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
        raise AudioError("conversion failed: " + err.decode("utf-8", "replace")[-200:])


def _prune() -> None:
    """Keep the cache under its size limit by deleting the least recently used files."""
    files = sorted(CACHE_DIR.glob("*.mp3"), key=lambda p: p.stat().st_mtime)
    total = sum(p.stat().st_size for p in files)
    while files and total > CACHE_MAX_BYTES:
        victim = files.pop(0)
        total -= victim.stat().st_size
        victim.unlink(missing_ok=True)


async def ensure_mp3(track: dict, album_title: str = "") -> Path:
    """Return the path of this song's MP3, capturing and converting it first if it is not cached yet."""
    sid = song_id(track)
    urls = sources(track)
    if not sid or not urls:
        raise AudioError("no audio source for this song")
    final = cached_file(sid)
    if final.exists():
        final.touch()
        return final
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    lock = _locks.setdefault(sid, asyncio.Lock())  # many people asking at once -> convert once
    async with lock:
        if final.exists():
            return final
        tags = {"title": track.get("title"), "artist": "Zimbermanne", "album": album_title}
        last_error = "no source worked"
        for url in urls:
            src = CACHE_DIR / f"{sid}.{int(time.time() * 1000)}.src"
            tmp = CACHE_DIR / f"{sid}.{int(time.time() * 1000)}.tmp"
            try:
                ctype = await _capture(url, src)          # 1. capture the stream
                if ctype == "audio/mpeg" or url.endswith(".mp3"):
                    os.replace(src, tmp)                  #    already an MP3, nothing to convert
                else:
                    await _convert(src, tmp, tags)        # 2. stream complete -> compile to MP3
                os.replace(tmp, final)                    # 3. cache it
                _prune()
                return final
            except (AudioError, httpx.HTTPError, OSError) as e:
                last_error = str(e)
            finally:
                src.unlink(missing_ok=True)
                tmp.unlink(missing_ok=True)
        raise AudioError(last_error)
