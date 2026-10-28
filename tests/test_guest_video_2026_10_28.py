"""The interviews on video: the guest's camera beside Mira (Oct 28 2026).

Patrick, after the Oct 28 test room: record video and use it for future
episodes on YouTube, X and the website. His choices: use it with the guest
able to opt out, the guest beside Mira's picture, built now and rehearsed
before any guest gets it.

The Voximplant video recorder could not be the source (Glenn Broder's hour
came back at ~16 kbps with 502 gaps over two seconds; the Oct 28 test room's
had no video packets at all), so the studio page records the guest's camera
itself, in its own lane beside the audio take (video_take.py places it on
the guest leg's clock), and render_video.py cuts it exactly as the edit cut
the sound. These pin each step on inputs whose answer is known.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
V = ROOT / "pipelines" / "voices"
sys.path.insert(0, str(V))
sys.path.insert(0, str(ROOT))

STUDIO = (ROOT / "age-of-ai-studio.html").read_text(encoding="utf-8")
WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")
FIRE = (V / "fire_interviews.py").read_text(encoding="utf-8")
POST = (V / "post_interview.py").read_text(encoding="utf-8")
INTERVIEWS = (ROOT / "engine" / "interviews.py").read_text(encoding="utf-8")
BLOG = (ROOT / "templates" / "blog_post.html.j2").read_text(encoding="utf-8")
WORKFLOWS = ROOT / ".github" / "workflows"

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")


# ---------------------------------------------------------------------------
# 1. The take: assembled from its chunks and placed on the leg's clock
# ---------------------------------------------------------------------------

class TestTheTake:
    def test_only_the_chunks_before_a_gap_can_be_read(self):
        import video_take as vt
        m = {"chunks": ["a", "b", "c", "d"], "missing": ["c"]}
        assert vt.usable_chunks(m) == ["a", "b"]
        assert vt.usable_chunks({"chunks": ["a"], "missing": []}) == ["a"]
        assert vt.usable_chunks(None) == []

    def test_takes_are_listed_oldest_first_and_empty_ones_dropped(self):
        import video_take as vt
        run = {"grok_session_log": {"local_video_takes": {"guest": [
            {"manifest": "m2", "chunks": 4, "started_at": "2026-10-28T17:10:00Z"},
            {"manifest": "m0", "chunks": 0, "started_at": "2026-10-28T17:00:00Z"},
            {"manifest": "m1", "chunks": 9, "started_at": "2026-10-28T17:01:00Z"},
            {"chunks": 3}]}}}
        assert [t["manifest"] for t in vt.video_takes(run)] == ["m1", "m2"]
        assert vt.video_takes({}) == []

    def test_a_later_take_shows_the_moment_it_covers(self):
        import video_take as vt
        takes = [{"pieces": [{"from": 0.0, "to": 100.0, "delay": 5.0}]},
                 {"pieces": [{"from": 0.0, "to": 50.0, "delay": 60.0}]}]
        assert vt.video_time(takes, 30.0) == (0, 25.0)
        assert vt.video_time(takes, 70.0) == (1, 10.0)      # the rejoin wins
        assert vt.video_time(takes, 200.0) is None

    @needs_ffmpeg
    def test_a_take_is_rebuilt_from_its_chunks_and_placed_by_its_own_microphone(self, tmp_path):
        import video_take as vt
        sr, dur = 48000, 90
        rng = np.random.default_rng(5)
        gate = np.repeat(rng.random(dur * 4) > 0.45, sr // 4).astype(np.float32)
        mic = (0.2 * rng.standard_normal(dur * sr) * gate).astype(np.float32)

        def wav(path, a):
            with wave.open(str(path), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sr)
                w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())

        wav(tmp_path / "mic.wav", mic)
        # The guest leg heard the same microphone 3 s later on its clock.
        wav(tmp_path / "leg.wav", np.concatenate([np.zeros(3 * sr, np.float32), mic,
                                                  np.zeros(10 * sr, np.float32)]))
        enc = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
             f"testsrc=size=64x36:rate=5:duration={dur}", "-i", str(tmp_path / "mic.wav"),
             "-c:v", "libvpx-vp9", "-b:v", "50k", "-c:a", "libopus", "-shortest",
             "-f", "webm", str(tmp_path / "src.webm")], capture_output=True)
        if enc.returncode != 0:
            pytest.skip("this ffmpeg cannot encode VP9/Opus")
        data = (tmp_path / "src.webm").read_bytes()
        size = len(data) // 7 + 1
        chunks = {f"k/{i:05d}.webm": data[i * size:(i + 1) * size] for i in range(7)}
        manifest = {"mime": "video/webm;codecs=vp9,opus", "chunks": list(chunks), "missing": []}

        def download(key, dest):
            Path(dest).write_bytes(chunks[key])
            return Path(dest)

        run = {"grok_session_log": {"local_video_takes": {"guest": [
            {"manifest": "k/manifest.json", "sid": "v1", "chunks": 7, "started_at": "x",
             "mime": manifest["mime"]}]}}}
        uploads = []
        track = vt.build_video_track(
            run, tmp_path / "leg.wav", tmp_path / "work",
            upload=lambda p, k: uploads.append(k) or f"https://audio.test/{k}",
            key_for=lambda name: f"raw/{name}", read_json=lambda k: manifest, download=download)
        assert track and track["fps"] == 30
        take = track["takes"][0]
        assert take["url"] == "https://audio.test/raw/guest_video_v1.mkv"
        assert take["delay_sec"] == pytest.approx(3.0, abs=0.05)
        assert take["agreement"] > 0.9
        assert take["duration_sec"] == pytest.approx(dur, abs=0.5)
        assert uploads == ["raw/guest_video_v1.mkv"]

        # A take whose first chunk never arrived cannot be read at all.
        manifest["missing"] = ["k/00000.webm"]
        assert vt.build_video_track(run, tmp_path / "leg.wav", tmp_path / "work2",
                                    upload=lambda p, k: "x", key_for=lambda n: n,
                                    read_json=lambda k: manifest, download=download) is None

    def test_post_production_builds_it_without_ever_risking_the_audio(self):
        assert "from video_take import build_video_track" in POST
        body = POST[POST.index("from video_take import build_video_track"):]
        body = body[:body.index('session_log["tracks"]["video"] = video_track')]
        assert "except Exception:" in body and "non-fatal" in body


# ---------------------------------------------------------------------------
# 2. The cut: the picture follows the edit's own clock
# ---------------------------------------------------------------------------

class TestTheCut:
    CLOCK = [[10.0, 19.0, 3.0], [21.0, 29.0, 12.0], [30.0, 36.0, 24.0]]
    TAKES = [{"pieces": [{"from": 0.0, "to": 40.0, "delay": 2.0}]}]   # leg_t = video_t + 2

    def test_each_kept_stretch_shows_its_own_moment_and_the_rest_shows_the_card(self):
        import render_video as rv
        runs = rv.plan_guest_track(self.CLOCK, 0.0, self.TAKES, 30.0)
        assert runs == [
            {"start": 0, "end": 90, "card": True},             # her narration
            {"start": 90, "end": 360, "take": 0, "at": 8.0},   # room 10-19
            {"start": 360, "end": 600, "take": 0, "at": 19.0},  # room 21-29
            {"start": 600, "end": 720, "card": True},           # narration
            {"start": 720, "end": 900, "take": 0, "at": 28.0},  # room 30-36
        ]

    def test_the_room_offset_is_taken_off_and_unplaced_moments_get_the_card(self):
        import render_video as rv
        runs = rv.plan_guest_track([[110.0, 119.0, 0.0]], 100.0,
                                   [{"pieces": [{"from": 0.0, "to": 13.0, "delay": 2.0}]}], 9.0)
        # Room 110-119 is leg 10-19; the take covers leg 2-15 only.
        assert runs[0] == {"start": 0, "end": 150, "take": 0, "at": 8.0}
        assert runs[1] == {"start": 150, "end": 270, "card": True}

    def test_a_stretch_whose_pauses_were_closed_blind_gets_the_card(self):
        import render_video as rv
        runs = rv.plan_guest_track([[10.0, 19.0, 0.0, 0.8]], 0.0, self.TAKES, 7.2)
        assert runs == [{"start": 0, "end": 216, "card": True}]

    def test_overlapping_runs_give_way_and_keep_their_picture_in_step(self):
        import render_video as rv
        out = rv._non_overlapping([{"start": 0, "end": 60, "take": 0, "at": 1.0},
                                   {"start": 30, "end": 90, "take": 0, "at": 5.0}])
        assert out[1] == {"start": 60, "end": 90, "take": 0, "at": 6.0}

    def test_the_speaker_lights_their_tile(self):
        import render_video as rv
        spans = rv.speaker_spans("[00:00] Mira (narration): Welcome.\n[00:03] Mira: Question?\n"
                                 "[00:06] Jane Doe: Answer.\n[00:20] Mira: Next.\n", 30.0)
        assert spans == {"mira": [(0.0, 6.0), (20.0, 30.0)], "guest": [(6.0, 20.0)]}
        assert rv.enable_expr([]) == "0"
        assert rv.enable_expr([(1.0, 2.5)]) == "between(t,1.00,2.50)"

    def test_a_guest_who_asked_for_audio_only_gets_no_video(self):
        import render_video as rv
        assert rv.video_allowed(None) and rv.video_allowed({"guest_video_ok": None})
        assert rv.video_allowed({"guest_video_ok": True})
        assert not rv.video_allowed({"guest_video_ok": False})

    @needs_ffmpeg
    def test_the_picture_is_1080p_side_by_side_and_exactly_as_long_as_the_edit(self, tmp_path):
        import render_video as rv
        take = tmp_path / "take.mkv"
        audio = tmp_path / "edit.mp3"
        for cmd in (["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                     "testsrc=size=320x180:rate=30:duration=12", "-c:v", "libx264", str(take)],
                    ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                     "sine=frequency=220:duration=3", str(audio)]):
            if subprocess.run(cmd, capture_output=True).returncode != 0:
                pytest.skip("this ffmpeg cannot build the fixtures")
        runs = rv.plan_guest_track([[4.0, 6.0, 1.0]], 0.0,
                                   [{"pieces": [{"from": 0.0, "to": 12.0, "delay": 0.0}]}], 3.0)
        card = rv.name_card("Jane Doe", "Founder · Acme", tmp_path / "card.png")
        tile = rv.render_guest_tile(runs, [take], card, tmp_path / "tile")
        out = rv.compose(tile, audio, tmp_path / "out.mp4", total_sec=3.0,
                         spans={"mira": [(0.0, 1.0)], "guest": [(1.0, 3.0)]},
                         guest_name="Jane Doe", show_name="The Age of AI", brand="#7C3AED",
                         workdir=tmp_path)
        probe = json.loads(subprocess.run(
            ["ffprobe", "-v", "error", "-count_frames", "-show_entries",
             "stream=codec_type,width,height,nb_read_frames", "-of", "json", str(out)],
            capture_output=True, text=True).stdout)
        video = [s for s in probe["streams"] if s["codec_type"] == "video"][0]
        assert (video["width"], video["height"]) == (1920, 1080)
        assert abs(int(video["nb_read_frames"]) - 90) <= 1
        assert any(s["codec_type"] == "audio" for s in probe["streams"])


class TestTheTestRoomPreview:
    """A test room is never post-processed, so its camera is previewed uncut
    against the room's own stereo recording (guest left, Mira right)."""

    def test_speech_runs_become_who_holds_the_floor(self):
        import render_video as rv
        assert rv.merge_spans([(0.0, 1.0), (1.5, 3.0), (5.0, 6.0)]) == [(0.0, 3.0), (5.0, 6.0)]

    @needs_ffmpeg
    def test_the_camera_is_placed_on_the_room_and_rendered_uncut(self, tmp_path, monkeypatch):
        import common
        import render_video as rv
        import requests
        sr, dur = 48000, 60
        rng = np.random.default_rng(9)
        gate = np.repeat(rng.random(dur * 4) > 0.5, sr // 4).astype(np.float32)
        mic = (0.2 * rng.standard_normal(dur * sr) * gate).astype(np.float32)
        mira = (0.2 * rng.standard_normal(dur * sr) * (1 - gate)).astype(np.float32)

        def wav(path, a, ch=1):
            with wave.open(str(path), "wb") as w:
                w.setnchannels(ch)
                w.setsampwidth(2)
                w.setframerate(sr)
                w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())

        # The room heard the guest 2 s after their camera's microphone did.
        left = np.concatenate([np.zeros(2 * sr, np.float32), mic])
        right = np.concatenate([mira, np.zeros(2 * sr, np.float32)])
        wav(tmp_path / "room.wav", np.stack([left, right], axis=1).reshape(-1), ch=2)
        wav(tmp_path / "mic.wav", mic)
        room_mp3 = tmp_path / "room.mp3"
        steps = [["ffmpeg", "-y", "-v", "error", "-i", str(tmp_path / "room.wav"), str(room_mp3)],
                 ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                  f"testsrc=size=64x36:rate=5:duration={dur}", "-i", str(tmp_path / "mic.wav"),
                  "-c:v", "libvpx-vp9", "-b:v", "50k", "-c:a", "libopus", "-shortest",
                  "-f", "webm", str(tmp_path / "take.webm")]]
        for cmd in steps:
            if subprocess.run(cmd, capture_output=True).returncode != 0:
                pytest.skip("this ffmpeg cannot build the fixtures")
        data = (tmp_path / "take.webm").read_bytes()
        chunks = {f"k/{i:05d}.webm": data[i * 20000:(i + 1) * 20000]
                  for i in range((len(data) + 19999) // 20000)}
        manifest = {"mime": "video/webm", "chunks": list(chunks), "missing": []}
        run = {"id": "r1", "interview_id": "i1", "recording_guest_url": "https://vox/room.mp3",
               "grok_session_log": {"local_video_takes": {"guest": [
                   {"manifest": "k/manifest.json", "sid": "v1", "chunks": len(chunks),
                    "started_at": "x"}]}}}

        class Show:
            name, brand_color = "The Age of AI", "#7C3AED"

            @staticmethod
            def r2_key(kind, name):
                return f"age_of_ai/{kind}/{name}"

        class Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def raise_for_status(self):
                return None

            def iter_content(self, n):
                yield room_mp3.read_bytes()

        uploads = []
        monkeypatch.setattr(common, "sb_select", lambda table, q="": {
            "interview_runs": [run], "interviews": [{"application_id": "a1"}],
            "guest_applications": [{"name": "Patrick Novak"}]}[table])
        monkeypatch.setattr(common, "show_for", lambda iv, app: Show)
        monkeypatch.setattr(common, "r2_read_json", lambda key: manifest)
        monkeypatch.setattr(common, "r2_download",
                            lambda key, dest: Path(dest).write_bytes(chunks[key]) and Path(dest))
        monkeypatch.setattr(common, "r2_upload", lambda path, key: uploads.append(
            (key, Path(path).stat().st_size)) or f"https://audio.test/{key}")
        monkeypatch.setattr(requests, "get", lambda url, **kw: Resp())
        url = rv.preview_for_run("r1")
        assert url == "https://audio.test/age_of_ai/raw/r1_preview_video.mp4"
        assert uploads and uploads[0][1] > 10000

    def test_the_workflow_can_ask_for_it(self):
        text = (WORKFLOWS / "nerra_voices_render_video.yml").read_text(encoding="utf-8")
        assert "preview:" in text and "PREVIEW: ${{ inputs.preview }}" in text


# ---------------------------------------------------------------------------
# 3. Publishing: YouTube, X and the episode's page, never against the wrong edit
# ---------------------------------------------------------------------------

class TestPublishing:
    def run(self, **edit):
        return {"grok_session_log": {"tracks": {"edit": {"url": "https://a/edit.mp3", **edit}}}}

    def test_the_video_is_used_only_with_the_edit_it_was_cut_from(self):
        import publish_episode as pe
        good = self.run(video_url="https://a/edit_video.mp4", video_of="https://a/edit.mp3")
        assert pe.episode_video(good, {}) == "https://a/edit_video.mp4"
        stale = self.run(video_url="https://a/old_video.mp4", video_of="https://a/old.mp3")
        assert pe.episode_video(stale, {}) == ""
        assert pe.episode_video(good, {"guest_video_ok": False}) == ""
        assert pe.episode_video(None, None) == ""

    def test_the_x_clip_is_the_first_suggested_moment_on_the_published_clock(self):
        import publish_episode as pe
        run = {"grok_session_log": {"tracks": {"edit": {"clock": [[100.0, 400.0, 20.0]]}}}}
        pkg = {"clip_suggestions": [{"start": 150.0, "end": 210.0}, {"start": 300.0}]}
        assert pe.x_clip_window(pkg, run) == (70.0, 60.0)
        assert pe.x_clip_window({"clip_suggestions": []}, run) is None
        long = {"clip_suggestions": [{"start": 120.0, "end": 390.0}]}
        assert pe.x_clip_window(long, run)[1] == pe.X_CLIP_MAX_SEC

    def test_the_episode_page_plays_only_our_own_video_file(self):
        assert 'video.startswith("https://audio.nerranetwork.com/")' in INTERVIEWS
        assert 'endswith(".mp4")' in INTERVIEWS
        assert "{% if interview.video_url %}" in BLOG and "<video controls" in BLOG

    def test_the_render_runs_after_the_edit_and_never_fails_it(self):
        for name in ("nerra_voices_post_interview.yml", "nerra_voices_assemble_edit.yml"):
            text = (WORKFLOWS / name).read_text(encoding="utf-8")
            job = text[text.index("\n  video:"):]
            assert "continue-on-error: true" in job and "render_video.py" in job
        assert (WORKFLOWS / "nerra_voices_render_video.yml").exists()


# ---------------------------------------------------------------------------
# 4. The studio and the switch
# ---------------------------------------------------------------------------

class TestTheStudio:
    def test_the_camera_is_recorded_in_the_browser_not_sent_to_the_call(self):
        assert "callSentVideo = sendVideo && !videoTake;" in STUDIO
        assert "video: { sendVideo: callSentVideo, receiveVideo: false }" in STUDIO
        assert 'videoTake = s.video_take === true && !isHost;' in STUDIO
        assert '"&kind=video&seq="' in STUDIO

    def test_it_starts_with_the_call_and_is_flushed_when_it_ends(self):
        connected = STUDIO.index("startLocalVideo();")
        assert STUDIO.rfind("startLocalRecording", 0, connected) > 0
        assert "Promise.all([stopLocalRecording(), stopLocalVideo()])" in STUDIO

    def test_safari_records_mp4(self):
        mimes = STUDIO[STUDIO.index("var VIDEO_MIMES"):]
        mimes = mimes[:mimes.index("];")]
        assert "video/webm" in mimes and "video/mp4" in mimes

    def test_the_guest_is_told_before_the_room(self):
        assert "video version" in STUDIO
        assert "audio only" in STUDIO.lower()

    def test_guests_get_it_only_after_a_test_room_and_test_rooms_always_do(self):
        from shows import get_show
        assert get_show("age_of_ai").local_video is False
        assert get_show("nerra_voices").local_video is False
        assert '**({"grok_session_log": {"local_video": True}} if show.local_video else {})' in FIRE
        import rehearsal
        src = Path(rehearsal.__file__).read_text(encoding="utf-8")
        assert '"grok_session_log": {"local_video": True, "rehearsal": {' in src

    def test_the_review_page_offers_audio_only(self):
        assert 'id="audioOnly"' in WORKER
        assert "guest_video_ok: !body.audio_only" in WORKER
        mig = (ROOT / "supabase" / "migrations" / "20261028_guest_video_choice.sql").read_text()
        assert "guest_video_ok" in mig and "editorial_packages" in mig
