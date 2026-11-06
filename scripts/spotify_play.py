#!/usr/bin/env python3
"""Play everything by an artist on Spotify (default: zimbermanne).

Setup (one time)
  1. pip install spotipy
  2. Create an app at https://developer.spotify.com/dashboard and add this redirect URI:
         http://127.0.0.1:8888/callback
  3. Set these environment variables with the app's values:
         SPOTIPY_CLIENT_ID
         SPOTIPY_CLIENT_SECRET
         SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
  4. Open the Spotify app on any device (phone, computer) so there is a device to play on.
     Starting playback through the API needs a Spotify Premium account.

Usage
  python spotify_play.py                 # play all music by "zimbermanne"
  python spotify_play.py --shuffle       # same, shuffled
  python spotify_play.py --open          # just open the artist in the browser
  python spotify_play.py "Another Name"  # another artist

The first run opens a browser once to ask for permission; after that it remembers you.
The script starts the artist's catalog once and lets Spotify play it. It does not loop or
restart tracks: repeated automated plays count as artificial streams, which Spotify penalises.
"""
import argparse
import sys
import webbrowser
from urllib.parse import quote

SCOPE = "user-modify-playback-state user-read-playback-state"
DEFAULT_ARTIST = "zimbermanne"


def get_client():
    """Spotify client. Credentials come from the SPOTIPY_* environment variables."""
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth

    return spotipy.Spotify(auth_manager=SpotifyOAuth(scope=SCOPE, open_browser=True))


def find_artist(sp, name: str):
    """The artist whose name matches exactly (ignoring capitals), or None. It never guesses."""
    items = sp.search(q=f'artist:"{name}"', type="artist", limit=10)["artists"]["items"]
    for artist in items:
        if artist["name"].strip().lower() == name.strip().lower():
            return artist
    return None


def pick_device(sp):
    """The device that is playing now, otherwise any available device, otherwise None."""
    devices = sp.devices().get("devices", [])
    active = [d for d in devices if d.get("is_active")]
    return (active or devices or [None])[0]


def open_in_browser(name: str = DEFAULT_ARTIST, sp=None) -> str:
    """Open the artist page (or a search for the name) in the web browser."""
    url = f"https://open.spotify.com/search/{quote(name)}"
    try:
        artist = find_artist(sp or get_client(), name)
        if artist:
            url = artist["external_urls"]["spotify"]
    except Exception:
        pass  # no login or no network: fall back to the search page
    webbrowser.open(url)
    return url


def play_artist(name: str = DEFAULT_ARTIST, sp=None, shuffle: bool = False) -> bool:
    """Start playing the artist's music on the user's Spotify device. Returns True if it started."""
    sp = sp or get_client()

    artist = find_artist(sp, name)
    if not artist:
        print(f'No artist named "{name}" found on Spotify.')
        return False

    device = pick_device(sp)
    if not device:
        print("No Spotify device is available. Open the Spotify app on your phone or computer and try again.")
        print("Opening the artist page instead:", open_in_browser(name, sp))
        return False

    try:
        sp.shuffle(shuffle, device_id=device["id"])
        sp.start_playback(device_id=device["id"], context_uri=artist["uri"])
    except Exception as exc:  # spotipy.SpotifyException carries the HTTP status
        status = getattr(exc, "http_status", None)
        if status == 403:
            print("Spotify refused to start playback. This needs a Spotify Premium account.")
        else:
            print(f"Spotify could not start playback: {exc}")
        return False

    print(f'Playing {artist["name"]} on {device["name"]}{" (shuffled)" if shuffle else ""}.')
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Play all music by an artist on Spotify.")
    parser.add_argument("name", nargs="?", default=DEFAULT_ARTIST, help=f"artist name (default: {DEFAULT_ARTIST})")
    parser.add_argument("--shuffle", action="store_true", help="shuffle the artist's music")
    parser.add_argument("--open", action="store_true", help="only open the artist page in the browser")
    args = parser.parse_args(argv)

    if args.open:
        print("Opened:", open_in_browser(args.name))
        return 0
    return 0 if play_artist(args.name, shuffle=args.shuffle) else 1


if __name__ == "__main__":
    sys.exit(main())
