"""Spotify Web API (client credentials). What it can give you:
albums/singles, tracks, Spotify links and cover art. What it cannot, since the 2026 API changes:
artist followers and popularity; monthly listeners were never in the API (type that number in Admin > Sync).
Songs are matched to the ones you already have by title; Spotify songs with no match are reported, not added,
because they are normally the same songs you made on Suno.
"""
import base64

import httpx
from sqlalchemy.orm import Session

from .. import config
from .common import Report, SyncError, all_albums, all_tracks, by_title, normalize, set_attr, set_stat

API = "https://api.spotify.com/v1"


def configured() -> bool:
    return bool(config.SPOTIFY_CLIENT_ID and config.SPOTIFY_CLIENT_SECRET)


def token(client: httpx.Client) -> str:
    basic = base64.b64encode(f"{config.SPOTIFY_CLIENT_ID}:{config.SPOTIFY_CLIENT_SECRET}".encode()).decode()
    r = client.post("https://accounts.spotify.com/api/token", data={"grant_type": "client_credentials"},
                    headers={"Authorization": f"Basic {basic}"})
    if r.status_code != 200:
        raise SyncError(f"Spotify login failed ({r.status_code}): check SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET")
    return r.json()["access_token"]


def _get(client: httpx.Client, url: str, tok: str, **params):
    r = client.get(url if url.startswith("http") else API + url, params=params or None,
                   headers={"Authorization": f"Bearer {tok}"})
    if r.status_code == 429:
        raise SyncError("Spotify rate limit reached, try again later")
    if r.status_code == 403:
        raise SyncError("Spotify refused the request (403): developer apps now need a Premium account owner")
    if r.status_code != 200:
        raise SyncError(f"Spotify error {r.status_code} on {url}")
    return r.json()


def _paged(client, url, tok, **params):
    page = _get(client, url, tok, **params)
    while page:
        yield from page.get("items", [])
        page = _get(client, page["next"], tok) if page.get("next") else None


def run(db: Session, client: httpx.Client | None = None) -> Report:
    if not configured():
        raise SyncError("Spotify is not set up: add SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET")
    report = Report()
    own = client is None
    client = client or httpx.Client(timeout=30)
    try:
        tok = token(client)
        aid = config.SPOTIFY_ARTIST_ID
        artist = _get(client, f"/artists/{aid}", tok)
        followers = (artist.get("followers") or {}).get("total")
        if followers:
            set_stat(db, "spotify_followers", followers)
        report.note(f"artist: {artist.get('name')}")

        albums, tracks = all_albums(db), all_tracks(db)
        album_titles, track_titles = by_title(albums), by_title(tracks)
        unmatched, matched_tracks = [], 0
        for sa in _paged(client, f"/artists/{aid}/albums", tok, include_groups="album,single", limit=10):
            full = _get(client, f"/albums/{sa['id']}", tok)
            cover = (full.get("images") or [{}])[0].get("url", "")
            url = (full.get("external_urls") or {}).get("spotify", "")
            cand = album_titles.get(normalize(full["name"]), [])
            album = cand[0] if len(cand) == 1 else None
            if album:
                set_attr(album, "spotify_album_id", full["id"], report, album.title)
                set_attr(album, "spotify_url", url, report, album.title)
                if not album.cover and cover:
                    album.cover = cover
            for st in (full.get("tracks") or {}).get("items", []):
                turl = (st.get("external_urls") or {}).get("spotify", "")
                pool = [t for t in track_titles.get(normalize(st["name"]), [])]
                inside = [t for t in pool if album and t.album_id == album.id]
                pick = inside or pool
                if len(pick) >= 1:
                    t = pick[0]
                    matched_tracks += 1
                    set_attr(t, "spotify_url", turl, report, t.title)
                    if not t.image and cover:
                        t.image = cover
                else:
                    unmatched.append(st["name"])
        if unmatched:
            report.note(f"on Spotify but not on this site (not added): {', '.join(unmatched[:20])}")
        db.commit()
        report.note(f"done: {matched_tracks} songs linked to Spotify")
        return report
    finally:
        if own:
            client.close()
