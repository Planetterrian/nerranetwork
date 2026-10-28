"""The video version, second pass (Oct 28 2026, Patrick on the first preview).

1. "Mira's simulated video talking needs to line up to when she is speaking
   and stop when she is not." Who speaks when is measured from the audio
   (her own track moved onto the edit's clock, the edit itself where it
   plays her narration), and her picture is the talking loop only inside
   those runs, from its first frame, easing back to rest when she stops.
2. "Videos ideally need to be YouTube Shorts and sharing to social media
   friendly." Beside the long form (16:9, side by side), up to three
   vertical 1080x1920 Shorts are cut from the clip pass's moments: the guest
   stacked over Mira, the words burned in. YouTube gets them as Shorts
   (staggered), X gets the first one.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
V = ROOT / "pipelines" / "voices"
sys.path.insert(0, str(V))
sys.path.insert(0, str(ROOT))

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")


def _frames_gray(path: Path, w: int, h: int) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo",
                          "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)


def _probe(path: Path) -> dict:
    out = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-show_entries",
         "stream=codec_type,width,height,nb_read_frames", "-of", "json", str(path)],
        capture_output=True, text=True).stdout)
    return {s["codec_type"]: s for s in out["streams"]}


# ---------------------------------------------------------------------------
# 1. She moves only while she speaks
# ---------------------------------------------------------------------------

class TestWhoSpeaksWhen:
    # Narration 0-5 s; the room 10-20 at edit 5-15; a cold-open cut of the
    # guest's own track (room 30-33) at edit 15-18.
    EDIT = {"clock": [[10.0, 20.0, 5.0], [30.0, 33.0, 15.0]], "room_offset_sec": 0.0,
            "pieces": [{"from": 0.0, "to": 5.0, "kind": "narration"},
                       {"from": 5.0, "to": 15.0, "kind": "room"},
                       {"from": 15.0, "to": 18.0, "kind": "guest"}]}

    def test_her_speech_is_her_track_on_the_edit_clock_plus_her_narration(self):
        import render_video as rv
        spans = rv.speech_on_edit(
            self.EDIT,
            edit_runs=[(0.5, 4.0), (6.0, 8.0), (12.0, 14.0), (16.0, 17.0)],
            mira_runs=[(11.0, 13.0), (31.0, 32.0)],     # the second is under the guest-only cut
            guest_runs=[(14.0, 19.5), (30.0, 33.0)],
            total_sec=18.0)
        assert spans["mira_talk"] == [(0.5, 4.0), (6.0, 8.0)]
        assert spans["guest"] == [(9.0, 18.0)]     # the border holds across a half-second

    def test_a_breath_keeps_her_talking_a_pause_stops_her(self):
        import render_video as rv
        spans = rv.speech_on_edit({"clock": [[0.0, 20.0, 0.0]]}, [],
                                  [(1.0, 2.0), (2.3, 3.0), (4.0, 5.0)], [], 20.0)
        assert spans["mira_talk"] == [(1.0, 3.0), (4.0, 5.0)]   # 0.3 s breath, 1.0 s pause
        assert spans["mira"] == [(1.0, 3.0), (4.0, 5.0)]
        # A click is not talking.
        assert rv.speech_on_edit({"clock": [[0.0, 9.0, 0.0]]}, [], [(1.0, 1.1)], [], 9.0)[
            "mira_talk"] == []

    def test_an_edit_built_before_it_named_its_pieces_reads_narration_off_the_clock(self):
        import render_video as rv
        edit = {"clock": [[10.0, 20.0, 5.0]]}
        assert rv.narration_regions(edit, 18.0) == [(0.0, 5.0), (15.0, 18.0)]

    def test_the_guest_is_not_heard_where_the_edit_plays_only_mira(self):
        import render_video as rv
        edit = {"clock": [[0.0, 10.0, 0.0], [20.0, 25.0, 10.0]],
                "pieces": [{"from": 0.0, "to": 10.0, "kind": "room"},
                           {"from": 10.0, "to": 15.0, "kind": "mira"}]}
        spans = rv.speech_on_edit(edit, [], [], [(2.0, 4.0), (21.0, 24.0)], 15.0)
        assert spans["guest"] == [(2.0, 4.0)]

    def test_runs_move_through_the_clock_and_its_offset_and_scale(self):
        import render_video as rv
        assert rv.runs_to_edit([(5.0, 8.0)], [[105.0, 107.0, 0.0], [107.5, 120.0, 2.0, 0.5]],
                               room_offset=100.0) == [(0.0, 2.0), (2.0, 2.25)]

    def test_her_picture_is_the_loop_only_inside_her_speech(self):
        import render_video as rv
        plan = rv.mira_plan([(1.0, 2.0), (3.0, 3.5)], 150, loop_frames=300)
        assert plan == [
            {"part": "rest", "n": 30},
            {"part": "talk", "at": 0, "n": 30},
            {"part": "settle", "from": 29, "n": rv.SETTLE_FRAMES},
            {"part": "rest", "n": 30 - rv.SETTLE_FRAMES},
            {"part": "talk", "at": 0, "n": 15},
            {"part": "settle", "from": 14, "n": rv.SETTLE_FRAMES},
            {"part": "rest", "n": 45 - rv.SETTLE_FRAMES},
        ]
        assert sum(p["n"] for p in plan) == 150

    def test_a_long_answer_runs_the_loop_again_from_its_start(self):
        import render_video as rv
        plan = rv.mira_plan([(0.0, 25.0)], 750, loop_frames=300)
        assert [(p["part"], p.get("at"), p["n"]) for p in plan] == [
            ("talk", 0, 300), ("talk", 0, 300), ("talk", 0, 150)]

    @needs_ffmpeg
    def test_the_rendered_track_is_still_while_she_is_quiet_and_moves_while_she_speaks(self, tmp_path):
        import render_video as rv
        out = rv.render_mira_track([(1.0, 2.5)], 4.0, (320, 180), tmp_path / "m")
        fr = _frames_gray(out, 320, 180)
        assert len(fr) == 120
        step = np.array([np.abs(fr[i + 1] - fr[i]).mean() for i in range(len(fr) - 1)])
        quiet_before = step[3:29]               # first frames carry encoder start-up
        talking = step[30:74]
        quiet_after = step[30 + 45 + rv.SETTLE_FRAMES + 1:]
        assert quiet_before.max() < 0.2 and quiet_after.max() < 0.2
        # The loop is 24 fps, so at 30 one frame in five repeats.
        assert talking.mean() > 0.3 and (talking > 0.2).mean() > 0.7
        # Speech starts from her rest face: no jump at the cut in.
        assert step[29] < 2 * talking.mean() + 0.5

    def test_her_tile_is_head_and_shoulders_like_a_camera(self):
        import render_video as rv
        assert rv.mira_crop((1000, 560)).startswith("crop=480:268:0:56,scale=1000:560")
        assert rv.mira_crop((880, 496)).startswith("crop=480:270:0:56,scale=880:496")
        # A tile taller than her portrait takes the whole height.
        assert rv.mira_crop((200, 400)).startswith("crop=364:730:58:0,scale=200:400")

    @needs_ffmpeg
    def test_the_long_form_still_renders_1080p_with_her_track(self, tmp_path):
        import render_video as rv
        tile = tmp_path / "tile.mp4"
        audio = tmp_path / "a.wav"
        for cmd in (["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                     f"color=c=gray:size={rv.TILE_W}x{rv.TILE_H}:rate=30:duration=2",
                     "-c:v", "libx264", "-pix_fmt", "yuv420p", str(tile)],
                    ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                     "sine=frequency=220:duration=2", str(audio)]):
            subprocess.run(cmd, check=True, capture_output=True)
        out = rv.compose(tile, audio, tmp_path / "out.mp4", total_sec=2.0,
                         spans={"mira_talk": [(0.5, 1.5)], "mira": [(0.5, 1.5)],
                                "guest": []},
                         guest_name="Jane Doe", show_name="The Age of AI", brand="#7C3AED",
                         workdir=tmp_path)
        video = _probe(out)["video"]
        assert (video["width"], video["height"]) == (1920, 1080)
        assert abs(int(video["nb_read_frames"]) - 60) <= 1


class TestTheEditNamesItsPieces:
    def test_each_cut_is_recorded_with_what_it_plays(self):
        import assemble_edit as ae
        cuts = [{"from": "narration:intro"}, {"gap": 0.5},
                {"from": "track:guest", "start": 1, "end": 4},
                {"from": "mix:clean", "start": 10, "end": 70},
                {"from": "track:mira", "start": 80, "end": 82},
                {"from": "track:host", "start": 90, "end": 91}]
        assert ae.pieces_of(cuts, [6.0, 0.5, 3.0, 60.0, 2.0, 1.0]) == [
            {"from": 0.0, "to": 6.0, "kind": "narration"},
            {"from": 6.0, "to": 6.5, "kind": "gap"},
            {"from": 6.5, "to": 9.5, "kind": "guest"},
            {"from": 9.5, "to": 69.5, "kind": "room"},
            {"from": 69.5, "to": 71.5, "kind": "mira"},
            {"from": 71.5, "to": 72.5, "kind": "guest"},
        ]

    def test_the_assembler_stores_them_beside_the_clock(self):
        src = (V / "assemble_edit.py").read_text(encoding="utf-8")
        assert '"pieces": edit_pieces,' in src

    def test_the_render_measures_speech_from_the_tracks_first(self):
        src = (V / "render_video.py").read_text(encoding="utf-8")
        body = src.split("def render_for_run")[1].split("\ndef ")[0]
        assert body.index("measured_speech(") < body.index("speaker_spans(")


# ---------------------------------------------------------------------------
# 2. Shorts
# ---------------------------------------------------------------------------

class TestShortsAreCutFromTheSuggestedMoments:
    RUN = {"grok_session_log": {"tracks": {"edit": {
        "url": "https://a/edit.mp3",
        "clock": [[100.0, 400.0, 20.0], [500.0, 1500.0, 330.0]]}}}}

    def test_moments_move_to_the_edit_and_fit_a_short(self):
        import render_video as rv
        pkg = {"clip_suggestions": [
            {"start": 150, "end": 190, "title": "Why the model forgets"},
            {"start": 160, "end": 200, "title": "overlaps the first"},
            {"start": 600, "end": 900, "title": "too long, capped"},
            {"start": 1000, "title": "no end"},
            {"start": 1200, "end": 1230, "title": "a fourth"},
        ]}
        wins = rv.clip_windows(pkg, self.RUN, total_sec=1400.0)
        assert wins == [
            {"start": 70.0, "seconds": 40.0, "title": "Why the model forgets"},
            {"start": 430.0, "seconds": rv.SHORT_MAX_SEC, "title": "too long, capped"},
            {"start": 830.0, "seconds": 45.0, "title": "no end"},
        ]

    def test_a_moment_near_the_end_that_cannot_fill_a_short_is_skipped(self):
        import render_video as rv
        pkg = {"clip_suggestions": [{"start": 1490, "end": 1500, "title": "x"}]}
        assert rv.clip_windows(pkg, self.RUN, total_sec=1325.0) == []
        assert rv.clip_windows({}, self.RUN) == []
        assert rv.clip_windows(None, None) == []

    def test_the_guest_tile_and_speech_are_sliced_to_the_moment(self):
        import render_video as rv
        runs = [{"start": 0, "end": 90, "card": True},
                {"start": 90, "end": 360, "take": 0, "at": 8.0}]
        assert rv.slice_runs(runs, 60, 150) == [
            {"start": 0, "end": 30, "card": True},
            {"start": 30, "end": 90, "take": 0, "at": 8.0}]
        assert rv.slice_runs(runs, 120, 150) == [{"start": 0, "end": 30, "take": 0, "at": 9.0}]
        assert rv.shift_spans([(1.0, 3.0), (5.0, 9.0)], 2.0, 6.0) == [(0.0, 1.0), (3.0, 4.0)]

    @needs_ffmpeg
    def test_a_short_is_vertical_captioned_and_exactly_as_long_as_its_moment(self, tmp_path, monkeypatch):
        import render_video as rv
        take = tmp_path / "take.mkv"
        audio = tmp_path / "edit.wav"
        for cmd in (["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                     "testsrc=size=320x180:rate=30:duration=12", "-c:v", "libx264", str(take)],
                    ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                     "sine=frequency=220:duration=8", str(audio)]):
            if subprocess.run(cmd, capture_output=True).returncode != 0:
                pytest.skip("this ffmpeg cannot build the fixtures")
        ass = tmp_path / "c.ass"
        ass.write_text("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n"
                       "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, Alignment, "
                       "MarginV\nStyle: Default,DejaVu Sans,60,&H00FFFFFF,2,70\n\n[Events]\n"
                       "Format: Layer, Start, End, Style, Text\n"
                       "Dialogue: 0,0:00:00.00,0:00:03.00,Default,hello there\n", encoding="utf-8")
        monkeypatch.setattr(rv, "short_captions", lambda *a, **k: ass)
        runs = rv.plan_guest_track([[0.0, 8.0, 0.0]], 0.0,
                                   [{"pieces": [{"from": 0.0, "to": 12.0, "delay": 0.0}]}], 8.0)
        out = rv.render_short(window={"start": 2.0, "seconds": 3.0}, runs=runs,
                              take_paths=[take],
                              spans={"mira_talk": [(2.5, 3.5)], "mira": [(2.5, 3.5)],
                                     "guest": [(3.5, 8.0)]},
                              audio=audio, guest_name="Jane Doe", subtitle="Founder",
                              show_name="The Age of AI", brand="#7C3AED",
                              workdir=tmp_path / "s", out=tmp_path / "short.mp4")
        streams = _probe(out)
        assert (streams["video"]["width"], streams["video"]["height"]) == (1080, 1920)
        assert abs(int(streams["video"]["nb_read_frames"]) - 90) <= 1
        assert "audio" in streams
        assert "subtitles=" in (tmp_path / "s" / "v_graph.txt").read_text(encoding="utf-8")

    def test_the_shorts_are_recorded_against_the_edit_they_were_cut_from(self):
        src = (V / "render_video.py").read_text(encoding="utf-8")
        assert '"shorts": shorts, "shorts_of": edit["url"]' in src


class TestShortsArePublished:
    def run(self, **edit):
        return {"grok_session_log": {"tracks": {"edit": {"url": "https://a/edit.mp3", **edit}}}}

    def test_only_shorts_of_the_published_edit_and_never_for_audio_only(self):
        import publish_episode as pe
        shorts = [{"url": "https://a/s1.mp4", "start": 1, "seconds": 40, "title": "t"}]
        good = self.run(shorts=shorts, shorts_of="https://a/edit.mp3")
        assert pe.episode_shorts(good, {}) == shorts
        assert pe.episode_shorts(self.run(shorts=shorts, shorts_of="https://a/old.mp3"), {}) == []
        assert pe.episode_shorts(good, {"guest_video_ok": False}) == []
        assert pe.episode_shorts(None, None) == []

    def test_a_short_title_says_shorts_and_fits(self):
        import publish_episode as pe
        from engine.titles import YOUTUBE_TITLE_MAX
        t = pe.short_title({"title": "word " * 40}, "Jane Doe", "The Age of AI")
        assert t.endswith(" #Shorts") and len(t) <= YOUTUBE_TITLE_MAX
        assert pe.short_title({}, "Jane Doe", "The Age of AI") == "Jane Doe on The Age of AI #Shorts"

    def test_the_first_goes_up_now_and_the_rest_are_scheduled(self, monkeypatch, tmp_path):
        import publish_episode as pe
        import engine.youtube as yt_mod
        uploads, recorded = [], []
        monkeypatch.setattr(yt_mod, "get_channel_credentials_from_env", lambda ch: object())
        monkeypatch.setattr(yt_mod, "upload_video", lambda path, **kw: uploads.append(kw)
                            or SimpleNamespace(video_id=f"v{len(uploads)}"))
        monkeypatch.setattr(pe, "_download", lambda url, dest: Path(dest))
        monkeypatch.setattr(pe, "_record_youtube_video",
                            lambda *a, **k: recorded.append((a[4], k.get("kind"))))
        show = SimpleNamespace(slug="age_of_ai", page_url="https://nerranetwork.com/age-of-ai.html")
        cfg = SimpleNamespace(name="The Age of AI", youtube=SimpleNamespace(
            enabled=True, channel="en", tags=["AI"], category_id=24, privacy_status="public"))
        shorts = [{"url": f"https://a/s{i}.mp4", "title": f"Moment {i}"} for i in range(3)]
        import datetime as dt
        n = pe.maybe_publish_shorts(show, cfg, 12, dt.date(2026, 10, 29), shorts, "Jane Doe",
                                    long_video_id="LONG1")
        assert n == 3
        assert uploads[0]["publish_at"] is None and uploads[0]["privacy_status"] == "public"
        assert all(u["privacy_status"] == "private" and u["publish_at"] for u in uploads[1:])
        assert uploads[1]["publish_at"] < uploads[2]["publish_at"]
        assert all("youtube.com/watch?v=LONG1" in u["description"] for u in uploads)
        assert all("hosted by Mira, an AI" in u["description"] for u in uploads)
        assert all(u["contains_synthetic_media"] for u in uploads)
        assert recorded == [("v1", "short"), ("v2", "short"), ("v3", "short")]

    def test_nothing_happens_without_youtube_or_shorts(self):
        import publish_episode as pe
        import datetime as dt
        off = SimpleNamespace(youtube=SimpleNamespace(enabled=False))
        assert pe.maybe_publish_shorts(None, off, 1, dt.date.today(), [{"url": "x"}], "J") == 0
        assert pe.maybe_publish_shorts(None, None, 1, dt.date.today(), [], "J") == 0

    def test_x_gets_the_vertical_short_first(self):
        src = (V / "publish_episode.py").read_text(encoding="utf-8")
        body = src.split("def maybe_post_x")[1].split("\ndef ")[0]
        assert body.index("_download(short_url") < body.index("x_video_clip(")
        publish = src.split("def publish_one")[1].split("\ndef ")[0]
        assert "short_url=shorts[0][\"url\"] if shorts else \"\"" in publish
        assert publish.index("maybe_publish_youtube(") < publish.index("maybe_publish_shorts(")
