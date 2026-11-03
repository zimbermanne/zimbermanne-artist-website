import copy
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sync_suno as s

A = "10f15313-4ec6-49d6-870d-288439f06937"
B = "6398559a-cb90-4dc7-88a5-ff2b9d7724e7"
B2 = "bbbbbbbb-0000-4000-8000-000000000002"   # second version of the same title as B
NEW = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
IMG_A = f"https://cdn2.suno.ai/image_large_{A}.jpeg"
IMG_B = f"https://cdn2.suno.ai/image_large_{B}.jpeg"


def clip(cid, title, extra=""):
    # the profile embeds JSON inside a JS string, so quotes are backslash-escaped
    return f'{{\\"id\\":\\"{cid}\\",\\"title\\":\\"{title}\\"{extra}}}'


def page(*clips):
    return "<script>self.__next_f.push([1,\"" + "".join(clips) + "\"])</script>"


def music():
    return {"albums": [{"id": "one", "cover": "https://cdn2.suno.ai/cover.jpeg", "tracks": [
        {"id": "t1", "title": "Wife’s Best Friend", "url": f"https://suno.com/song/{A}"},
        {"id": "t2", "title": "Ukombozi wa Kifikra", "url": f"https://suno.com/song/{B}",
         "audioUrl": f"https://cdn1.suno.ai/{B}.mp4"},
        {"id": "t3", "title": "No link yet"},
    ]}]}


def lookup_from(table):
    return lambda sid: table.get(sid)


# ---------------------------------------------------------------- parsing
def test_parse_clips_by_id_decodes_titles_and_skips_ui_strings():
    clips = s.parse_clips(page(clip(A, "Wife\\u2019s Best Friend"), clip(NEW, "Edit profile")))
    assert list(clips) == [A]
    assert clips[A]["title"] == "Wife’s Best Friend"
    assert clips[A]["audioUrl"] == f"https://cdn1.suno.ai/{A}.mp4"


def test_two_versions_with_the_same_title_are_both_kept():
    clips = s.parse_clips(page(clip(B, "Same Title"), clip(B2, "Same Title")))
    assert set(clips) == {B, B2}


def test_artwork_prefers_large_and_rejects_foreign_hosts():
    extra = f',\\"image_url\\":\\"https://cdn2.suno.ai/image_{A}.jpeg\\",\\"image_large_url\\":\\"{IMG_A}\\"'
    clips = s.parse_clips(page(clip(A, "One", extra),
                               clip(B, "Two", ',\\"image_url\\":\\"https://evil.example.com/x.jpg\\"')))
    assert clips[A]["image"] == IMG_A
    assert clips[B]["image"] is None


def test_other_accounts_songs_are_skipped():
    clips = s.parse_clips(page(clip(A, "Mine", ',\\"handle\\":\\"zimbermannelit\\"'),
                               clip(B, "Theirs", ',\\"handle\\":\\"someone_else\\"')), handle="@zimbermannelit")
    assert list(clips) == [A]


def test_empty_page_finds_nothing():
    assert s.parse_clips("<html>layout changed</html>") == {}


def test_song_page_share_image_is_read_in_any_attribute_order():
    html = f'<head><meta content="{IMG_A}" property="og:image"><meta name="x" content="y"></head>'
    assert s.parse_song_page(html)["image"] == IMG_A
    assert s.parse_song_page('<meta property="og:image" content="https://evil.example.com/a.jpg">')["image"] is None
    assert s.parse_song_page("<html></html>")["image"] is None


# ---------------------------------------------------------------- applying
def test_known_tracks_get_artwork_from_their_own_song_page():
    data = music()
    out = s.apply_sync(data, {}, lookup_from({A: {"image": IMG_A}, B: {"image": IMG_B}}))
    t = data["albums"][0]["tracks"]
    assert t[0]["image"] == IMG_A and t[1]["image"] == IMG_B
    assert t[0]["audioUrl"] == f"https://cdn1.suno.ai/{A}.mp4"
    assert out["read"] == 2


def test_a_same_titled_clip_never_repoints_a_track():
    """Regression: the old title matching switched 'Muddy Waters' to a different version."""
    data = music()
    clips = s.parse_clips(page(clip(B2, "Ukombozi wa Kifikra")))
    out = s.apply_sync(data, clips, lookup_from({}))
    assert data["albums"][0]["tracks"][1]["url"].endswith(B)
    assert out["alternates"] == ["Ukombozi wa Kifikra"] and out["new"] == []


def test_unreachable_song_page_changes_nothing_and_does_not_crash():
    data = music()
    before = copy.deepcopy(data)
    out = s.apply_sync(data, {}, lookup_from({}))   # lookup returns None
    assert out["read"] == 0
    assert "image" not in data["albums"][0]["tracks"][0]
    assert data["albums"][0]["tracks"][1] == before["albums"][0]["tracks"][1]


def test_deleted_song_is_reported_and_kept():
    data = music()
    out = s.apply_sync(data, {}, lookup_from({B: s.MISSING}))
    assert out["missing"] == ["Ukombozi wa Kifikra"]
    assert data["albums"][0]["tracks"][1]["url"].endswith(B)


def test_track_without_a_link_is_linked_only_when_the_title_is_unique():
    data = music()
    clips = s.parse_clips(page(clip(NEW, "No link yet")))
    s.apply_sync(data, clips, lookup_from({}))
    assert data["albums"][0]["tracks"][2]["url"].endswith(NEW)

    data = music()
    dup = "cccccccc-0000-4000-8000-000000000003"
    clips = s.parse_clips(page(clip(NEW, "No link yet"), clip(dup, "No link yet")))
    s.apply_sync(data, clips, lookup_from({}))
    assert "url" not in data["albums"][0]["tracks"][2]   # two candidates: do not guess


def test_new_songs_go_to_a_new_releases_album_and_a_second_run_is_a_no_op():
    data = music()
    clips = s.parse_clips(page(clip(A, "Wife’s Best Friend"), clip(NEW, "Brand New Song",
                               f',\\"image_large_url\\":\\"https://cdn2.suno.ai/image_large_{NEW}.jpeg\\"')))
    out = s.apply_sync(data, clips, lookup_from({}))
    inbox = data["albums"][-1]
    assert inbox["id"] == s.INBOX_ID and out["new"] == ["Brand New Song"]
    assert inbox["tracks"][0]["url"].endswith(NEW) and inbox["cover"].endswith(f"{NEW}.jpeg")
    snapshot = json.dumps(data)
    again = s.apply_sync(data, clips, lookup_from({}))
    assert again["new"] == [] and json.dumps(data) == snapshot


def test_at_most_max_new_songs_are_added_per_run():
    data = music()
    ids = [f"dddddddd-0000-4000-8000-{i:012d}" for i in range(s.MAX_NEW + 2)]
    clips = s.parse_clips(page(*[clip(i, f"Song {n}") for n, i in enumerate(ids)]))
    out = s.apply_sync(data, clips, lookup_from({}))
    assert len(out["new"]) == s.MAX_NEW and len(out["left_out"]) == 2


def test_the_real_music_json_is_stable_when_suno_cannot_be_read():
    real = json.loads((Path(__file__).resolve().parent.parent / "music.json").read_text(encoding="utf-8"))
    before = copy.deepcopy(real)
    out = s.apply_sync(real, {}, lookup_from({}))
    assert real == before and out["changes"] == []


# ---------------------------------------------------------------- whole script
REAL_CLIENT = httpx.Client


def _run(monkeypatch, tmp_path, argv, profile_html, song_html):
    f = tmp_path / "music.json"
    data = music()
    data.update({"handle": "@zimbermannelit", "sunoProfile": "https://suno.com/@zimbermannelit"})
    f.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(s, "MUSIC_JSON", f)
    monkeypatch.setattr(s.time, "sleep", lambda *_: None)

    def handler(request):
        if request.url.path.startswith("/song/"):
            return httpx.Response(200, text=song_html)
        return httpx.Response(200, text=profile_html)

    monkeypatch.setattr(s.httpx, "Client", lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(handler), **kw))
    code = s.main(argv)
    return code, json.loads(f.read_text(encoding="utf-8"))


def test_main_writes_changes_and_dry_run_does_not(monkeypatch, tmp_path):
    song = f'<meta property="og:image" content="{IMG_A}">'
    profile = page(clip(NEW, "Brand New Song"))
    code, out = _run(monkeypatch, tmp_path, ["--dry-run"], profile, song)
    assert code == 0 and "image" not in out["albums"][0]["tracks"][0] and len(out["albums"]) == 1
    code, out = _run(monkeypatch, tmp_path, [], profile, song)
    assert code == 0 and out["albums"][0]["tracks"][0]["image"] == IMG_A
    assert out["albums"][-1]["id"] == s.INBOX_ID and out["lastUpdated"]


def test_main_fails_when_nothing_can_be_read(monkeypatch, tmp_path):
    code, out = _run(monkeypatch, tmp_path, [], "<html>blocked</html>", "<html>blocked</html>")
    assert code == 1 and len(out["albums"]) == 1 and "image" not in out["albums"][0]["tracks"][0]
