"""SoundCloud official API (client credentials). soundcloud.com itself blocks scraping, so this needs
SOUNDCLOUD_CLIENT_ID / SOUNDCLOUD_CLIENT_SECRET (a SoundCloud Artist Pro account can register an app).
Gives: play counts per song, follower count, SoundCloud links, artwork (when a song has none).
"""
import base64
import time

import httpx
from sqlalchemy.orm import Session

from .. import config
from .common import Report, SyncError, all_albums, all_tracks, by_title, normalize, set_attr, set_stat

API = "https://api.soundcloud.com"
_tok = {"value": "", "exp": 0.0}  # cached: client-credential tokens are rate limited


def configured() -> bool:
    return bool(config.SOUNDCLOUD_CLIENT_ID and config.SOUNDCLOUD_CLIENT_SECRET)


def token(client: httpx.Client) -> str:
    if _tok["value"] and time.time() < _tok["exp"] - 60:
        return _tok["value"]
    basic = base64.b64encode(f"{config.SOUNDCLOUD_CLIENT_ID}:{config.SOUNDCLOUD_CLIENT_SECRET}".encode()).decode()
    r = client.post("https://secure.soundcloud.com/oauth/token", data={"grant_type": "client_credentials"},
                    headers={"Authorization": f"Basic {basic}", "accept": "application/json; charset=utf-8"})
    if r.status_code != 200:
        raise SyncError(f"SoundCloud login failed ({r.status_code}): check SOUNDCLOUD_CLIENT_ID / SOUNDCLOUD_CLIENT_SECRET")
    d = r.json()
    _tok["value"], _tok["exp"] = d["access_token"], time.time() + int(d.get("expires_in", 3600))
    return _tok["value"]


def _get(client, path, tok, **params):
    r = client.get(path if path.startswith("http") else API + path, params=params or None,
                   headers={"Authorization": f"OAuth {tok}", "accept": "application/json; charset=utf-8"})
    if r.status_code != 200:
        raise SyncError(f"SoundCloud error {r.status_code} on {path}")
    return r.json()


def _collection(client, path, tok, **params):
    page = _get(client, path, tok, linked_partitioning="true", limit=200, **params)
    while True:
        items = page.get("collection", page if isinstance(page, list) else [])
        yield from items
        nxt = page.get("next_href") if isinstance(page, dict) else None
        if not nxt:
            return
        page = _get(client, nxt, tok)


def _art(url: str | None) -> str:
    return (url or "").replace("-large.", "-t500x500.")


def run(db: Session, client: httpx.Client | None = None) -> Report:
    if not configured():
        raise SyncError("SoundCloud is not set up: add SOUNDCLOUD_CLIENT_ID and SOUNDCLOUD_CLIENT_SECRET")
    report = Report()
    own = client is None
    client = client or httpx.Client(timeout=30, follow_redirects=True)
    try:
        tok = token(client)
        user = _get(client, "/resolve", tok, url=config.SOUNDCLOUD_PROFILE_URL)
        if user.get("kind") != "user":
            raise SyncError("SOUNDCLOUD_PROFILE_URL must be a profile link like https://soundcloud.com/your-name")
        uid = user["id"]
        report.note(f"profile: {user.get('username')}")
        if user.get("followers_count") is not None:
            set_stat(db, "soundcloud_followers", user["followers_count"])

        titles = by_title(all_tracks(db))
        total, linked, unmatched = 0, 0, []
        for sc in _collection(client, f"/users/{uid}/tracks", tok):
            plays = int(sc.get("playback_count") or 0)
            total += plays
            cand = titles.get(normalize(sc.get("title", "")), [])
            if not cand:
                unmatched.append(sc.get("title", "?"))
                continue
            t = cand[0]
            linked += 1
            set_attr(t, "soundcloud_url", sc.get("permalink_url", ""), report, t.title)
            if plays != t.soundcloud_plays:
                t.soundcloud_plays = plays
            if not t.image and (sc.get("artwork_url") or user.get("avatar_url")):
                t.image = _art(sc.get("artwork_url") or user.get("avatar_url"))
        set_stat(db, "soundcloud_plays", total)

        albums = by_title(all_albums(db))
        for pl in _collection(client, f"/users/{uid}/playlists", tok):
            cand = albums.get(normalize(pl.get("title", "")), [])
            if len(cand) == 1:
                set_attr(cand[0], "soundcloud_url", pl.get("permalink_url", ""), report, cand[0].title)
        if unmatched:
            report.note(f"on SoundCloud but not on this site (not added): {', '.join(unmatched[:20])}")
        db.commit()
        report.note(f"done: {linked} songs linked, {total} plays in total")
        return report
    finally:
        if own:
            client.close()
