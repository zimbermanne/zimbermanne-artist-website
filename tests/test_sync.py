import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sync_suno as s

A = "10f15313-4ec6-49d6-870d-288439f06937"
B = "6398559a-cb90-4dc7-88a5-ff2b9d7724e7"
NEW = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

# the profile embeds JSON inside a JS string, so quotes are backslash-escaped
HTML = (
    f'<script>self.__next_f.push([1,"{{\\"id\\":\\"{A}\\",\\"x\\":1,\\"title\\":\\"Wife\\u2019s Best Friend\\"}}"])</script>'
    f'{{\\"id\\":\\"{B}\\",\\"title\\":\\"Ukombozi wa Kifikra\\"}}'
    f'{{\\"id\\":\\"{NEW}\\",\\"title\\":\\"Brand New Song\\"}}'
    f'{{\\"id\\":\\"{NEW[:-1]}f\\",\\"title\\":\\"Edit profile\\"}}'
)


def music():
    return {"albums": [{"tracks": [
        {"title": "Wife’s Best Friend", "url": "https://suno.com/song/old"},
        {"title": "Ukombozi wa Kifikra", "url": f"https://suno.com/song/{B}", "audioUrl": f"https://cdn1.suno.ai/{B}.mp4"},
        {"title": "Local only", "url": f"https://suno.com/song/{NEW[:-1]}0"},
    ]}]}


def test_parse_clips_decodes_titles_and_skips_ui_strings():
    clips = s.parse_clips(HTML)
    assert s.normalize("Wife’s Best Friend") in clips
    assert clips[s.normalize("Wife’s Best Friend")]["audioUrl"] == f"https://cdn1.suno.ai/{A}.mp4"
    assert not any("edit" in k for k in clips)


def test_apply_updates_only_what_changed():
    data = music()
    changes, unknown = s.apply_clips(data, s.parse_clips(HTML))
    t = data["albums"][0]["tracks"]
    assert t[0]["url"] == f"https://suno.com/song/{A}" and t[0]["audioUrl"].endswith(f"{A}.mp4")
    assert t[1] == music()["albums"][0]["tracks"][1]          # already current: untouched
    assert t[2]["audioUrl"].endswith(f"{NEW[:-1]}0.mp4")       # not on profile: derived from its own link
    assert unknown == ["Brand New Song"]
    assert len(changes) == 3


def test_second_run_is_a_no_op():
    data = music()
    s.apply_clips(data, s.parse_clips(HTML))
    snapshot = json.dumps(data)
    changes, _ = s.apply_clips(data, s.parse_clips(HTML))
    assert changes == [] and json.dumps(data) == snapshot


def test_empty_page_finds_nothing():
    assert s.parse_clips("<html>layout changed</html>") == {}
