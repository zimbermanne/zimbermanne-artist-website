#!/usr/bin/env python3
"""Sync song links and audio URLs from the Suno profile into music.json.

Usage:
    python sync_suno.py            # update music.json when something changed
    python sync_suno.py --dry-run  # show what would change, write nothing

Safety rules (Suno's pages can change without notice):
  * music.json is the source of truth and the fallback. It is only rewritten when a
    track's link actually changed, never when the fetch or parsing failed.
  * If the profile cannot be fetched or no songs can be found, the file is left untouched
    and the script exits with code 1 so the scheduled run shows up as failed.
  * Songs found on Suno but missing from music.json are only listed in the log;
    adding them needs a human decision (which album, which lyrics).
"""
import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
MUSIC_JSON = ROOT / "music.json"
SKIP_WORDS = ("Suno", "Sharing", "Publish", "Edit")  # UI strings that look like clip titles
CLIP_RE = re.compile(r'"id":"([0-9a-f-]{36})"[^}]*?"title":"([^"]+)"')
UUID_RE = re.compile(r"[0-9a-f-]{36}", re.I)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def song_id(url: str | None) -> str | None:
    m = UUID_RE.search(url or "")
    return m[0] if m else None


def _decode_title(raw: str) -> str:
    try:  # the profile embeds JSON strings, so handle \u2019 style escapes
        return json.loads(f'"{raw}"').strip()
    except json.JSONDecodeError:
        return raw.strip()


def parse_clips(html: str) -> dict[str, dict]:
    """Extract {normalized title: clip} from the profile page HTML."""
    text = html.replace('\\"', '"').replace("\\\\", "\\")
    clips: dict[str, dict] = {}
    for clip_id, raw_title in CLIP_RE.findall(text):
        title = _decode_title(raw_title)
        if any(w in title for w in SKIP_WORDS):
            continue
        clips.setdefault(normalize(title), {
            "id": clip_id,
            "title": title,
            "url": f"https://suno.com/song/{clip_id}",
            "audioUrl": f"https://cdn1.suno.ai/{clip_id}.mp4",
        })
    return clips


def apply_clips(data: dict, clips: dict[str, dict]) -> tuple[list[str], list[str]]:
    """Update tracks in `data` in place. Returns (change descriptions, titles not in music.json)."""
    changes, seen = [], set()
    for album in data.get("albums", []):
        for track in album.get("tracks", []):
            key = normalize(track["title"])
            clip = clips.get(key)
            if clip:
                seen.add(key)
                new = {"url": clip["url"], "audioUrl": clip["audioUrl"]}
            elif song_id(track.get("url")):  # not on the profile page: keep the link, derive the stream URL
                new = {"audioUrl": f"https://cdn1.suno.ai/{song_id(track['url'])}.mp4"}
            else:
                continue
            for field, value in new.items():
                if track.get(field) != value:
                    changes.append(f"{track['title']}: {field} {track.get(field)!r} -> {value!r}")
                    track[field] = value
    unknown = [c["title"] for k, c in clips.items() if k not in seen]
    return changes, unknown


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    try:
        music = json.loads(MUSIC_JSON.read_text(encoding="utf-8"))
        profile_url = music.get("sunoProfile") or f"https://suno.com/{music.get('handle', '')}"
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[sync] cannot read music.json: {exc}", file=sys.stderr)
        return 1

    print(f"[sync] fetching {profile_url}")
    try:
        r = httpx.get(profile_url, timeout=30, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0 (compatible; zimbermanne-sync/1.0)"})
        r.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"[sync] fetch failed, music.json left unchanged: {exc}", file=sys.stderr)
        return 1

    clips = parse_clips(r.text)
    if not clips:
        print("[sync] no songs found on the page (layout changed?), music.json left unchanged", file=sys.stderr)
        return 1
    print(f"[sync] found {len(clips)} songs on the profile")

    changes, unknown = apply_clips(music, clips)
    for line in changes:
        print(f"[sync] changed {line}")
    if unknown:
        print(f"[sync] on Suno but not in music.json (add by hand): {', '.join(unknown)}")
    if not changes:
        print("[sync] nothing changed")
        return 0
    if dry_run:
        print("[sync] dry run, nothing written")
        return 0

    music["lastUpdated"] = date.today().isoformat()
    MUSIC_JSON.write_text(json.dumps(music, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[sync] wrote music.json ({len(changes)} changes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
