"""The end-of-turn cue analysis (pipelines/voices/turn_cues.py, Oct 28 2026).

Patrick asked whether the guest's own cues, on camera and in the voice, can
tell the room an answer is over sooner than its ~4 s wait, without cutting
in. The tool labels every pause in a guest's speech by what happened next
(they went on: HOLD; they stopped and waited for the host: END; the host
decided for them: set aside), measures what was observable at the pause,
and scores silence alone against cues. These pin the labelling and the
scoring on signals whose answer is known.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))

import turn_cues as tc  # noqa: E402


class TestLabellingPauses:
    def test_a_pause_the_guest_fills_is_a_hold(self):
        guest = [(0.0, 3.0), (3.6, 6.0)]
        out = tc.label_pauses(guest, [])
        assert [(p.label, round(p.length, 2)) for p in out] == [("hold", 0.6)]

    def test_a_pause_the_host_answers_after_a_real_wait_is_an_end(self):
        guest = [(0.0, 3.0), (12.0, 15.0)]
        host = [(5.5, 11.0)]
        out = tc.label_pauses(guest, host)
        assert [(p.label, p.length) for p in out] == [("end", 2.5)]

    def test_the_host_speaking_too_soon_or_the_guest_coming_back_over_them_is_set_aside(self):
        soon = tc.label_pauses([(0.0, 3.0), (9.0, 12.0)], [(3.4, 8.0)])
        over = tc.label_pauses([(0.0, 3.0), (5.3, 9.0)], [(5.0, 6.0)])
        assert [p.label for p in soon] == ["cut"]
        assert [p.label for p in over] == ["cut"]

    def test_breaths_and_talked_over_pauses_are_not_counted(self):
        assert tc.label_pauses([(0.0, 3.0), (3.1, 5.0)], []) == []
        # The guest stopped while the host was already talking.
        assert tc.label_pauses([(0.0, 3.0), (4.0, 6.0)], [(2.0, 3.5)]) == []

    def test_a_long_silence_is_not_a_pause_in_a_conversation(self):
        assert tc.label_pauses([(0.0, 3.0), (40.0, 41.0)], []) == []

    def test_turn_length_runs_from_the_start_of_the_answer(self):
        guest = [(0.0, 3.0), (3.5, 6.0), (20.0, 22.0), (22.5, 24.0)]
        host = [(8.0, 18.0)]
        out = tc.label_pauses(guest, host)
        assert [p.label for p in out] == ["hold", "end", "hold"]
        assert out[0].turn_sec == pytest.approx(3.0)
        assert out[2].turn_sec == pytest.approx(2.0)


def tone(freqs, sr=tc.SR):
    """Voiced audio following ``freqs`` (one value per 10 ms)."""
    f = np.repeat(np.asarray(freqs, dtype=np.float64), sr // 100)
    phase = 2 * np.pi * np.cumsum(f) / sr
    return (0.3 * np.sin(phase) + 0.15 * np.sin(2 * phase)).astype(np.float32)


class TestTheVoice:
    def test_pitch_is_read_from_a_steady_voice(self):
        f0 = tc.pitch_track(tone([150.0] * 50))
        voiced = f0[f0 > 0]
        assert len(voiced) > 30 and abs(float(np.median(voiced)) - 150.0) < 6.0

    def test_a_falling_end_reads_as_a_fall(self):
        fall = tone(np.linspace(220, 120, 60))
        rise = tone(np.linspace(140, 230, 60))
        pad = np.zeros(tc.SR // 2, dtype=np.float32)
        runs = [(0.5, 1.1)]
        f_fall = tc.voice_features(np.concatenate([pad, fall]), 1.1, (110.0, 240.0), 1.0, runs)
        f_rise = tc.voice_features(np.concatenate([pad, rise]), 1.1, (110.0, 240.0), 1.0, runs)
        assert f_fall["f0_slope_st_per_s"] < -5 < 5 < f_rise["f0_slope_st_per_s"]
        assert f_fall["f0_final_in_range"] < 0.3 < 0.7 < f_rise["f0_final_in_range"]

    def test_speech_is_found_against_the_tracks_own_noise(self):
        rng = np.random.default_rng(1)
        sr = tc.SR
        audio = (0.003 * rng.standard_normal(sr * 10)).astype(np.float32)
        audio[: sr // 2] = 0.0                                     # digital silence
        audio[sr * 2: sr * 4] += tone([160.0] * 200)
        audio[sr * 6: int(sr * 7.5)] += tone([180.0] * 150)
        runs = tc.speech_runs(tc.frame_db(audio))
        assert len(runs) == 2
        assert runs[0][0] == pytest.approx(2.0, abs=0.06) and runs[0][1] == pytest.approx(4.0, abs=0.06)
        assert runs[1][0] == pytest.approx(6.0, abs=0.06) and runs[1][1] == pytest.approx(7.5, abs=0.06)

    def test_words_hold_or_hand_over_the_floor(self):
        words = [{"word": " the", "start": 0.0, "end": 0.2}, {"word": " budget", "start": 0.2, "end": 0.6},
                 {"word": " and", "start": 0.6, "end": 0.8}, {"word": " right?", "start": 2.0, "end": 2.3}]
        assert tc.word_features(words, 0.8)["last_word_holds"] == 1.0
        hand = tc.word_features(words, 2.3)
        assert hand["last_word_holds"] == 0.0 and hand["last_word_question"] == 1.0


class TestTheRoomsOwnRule:
    def test_the_clause_rule_is_the_rooms(self):
        scenario = (ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js").read_text(encoding="utf-8")
        js = scenario[scenario.index("const UNFINISHED_TAIL_RE = /") + len("const UNFINISHED_TAIL_RE = /"):]
        js = js[:js.index("/i;")]
        assert tc.UNFINISHED_TAIL_RE.pattern == js
        assert tc.room_reads_finished("I think so.")
        assert not tc.room_reads_finished("and the reason is")
        assert not tc.room_reads_finished("we built it, and")
        assert tc.room_reads_finished("that is the answer")


class TestTheCamera:
    def test_a_guest_who_settles_reads_as_a_motion_drop(self):
        rng = np.random.default_rng(2)
        n = 40
        frames = np.zeros((n, tc.VIDEO_H, tc.VIDEO_W), dtype=np.uint8)
        for i in range(n):
            # Moving while talking (frames 0-19), still once the pause begins.
            frames[i] = rng.integers(0, 255, (tc.VIDEO_H, tc.VIDEO_W)) if i < 20 else frames[19]
        whole, face = tc.motion_series(frames)
        f = tc.video_features(whole, face, 2.0)
        assert f["motion_drop"] < -2 and f["face_motion_drop"] < -2

    def test_no_picture_means_no_camera_cue(self):
        whole, face = tc.motion_series(np.zeros((1, tc.VIDEO_H, tc.VIDEO_W), dtype=np.uint8))
        assert tc.video_features(whole, face, 0.0) == {}


def synthetic_rooms(separation: float, rooms: int = 6, seed: int = 3):
    """Rooms whose ends and holds differ on one cue by ``separation``."""
    rng = np.random.default_rng(seed)
    out = {}
    for r in range(rooms):
        pauses = []
        for _ in range(120):
            hold_len = float(np.clip(rng.lognormal(np.log(0.5), 0.5), 0.25, 6.0))
            p = tc.Pause(at=0.0, length=hold_len, label="hold")
            p.features = {"f0_slope_st_per_s": float(rng.normal(0.0, 1.0))}
            pauses.append(p)
        for _ in range(20):
            p = tc.Pause(at=0.0, length=4.5, label="end", host_after=4.5)
            p.features = {"f0_slope_st_per_s": float(rng.normal(-separation, 1.0))}
            pauses.append(p)
        out[f"r{r}"] = {"pauses": pauses, "has_video": False,
                        "counts": {k: sum(1 for p in pauses if p.label == k) for k in ("hold", "end", "cut")}}
    return out


class TestScoring:
    def test_auc_is_the_chance_an_end_outscores_a_hold(self):
        assert tc._auc([3, 4, 5], [0, 1, 2]) == 1.0
        assert tc._auc([0, 1], [0, 1]) == pytest.approx(0.5)

    def test_silence_alone_counts_the_holds_it_would_cut(self):
        pauses = [tc.Pause(0, 0.5, "hold"), tc.Pause(0, 1.2, "hold"), tc.Pause(0, 2.2, "hold"),
                  tc.Pause(0, 4.0, "end", 4.0), tc.Pause(0, 1.5, "end", 1.5)]
        rows = {r["wait_sec"]: r for r in tc.silence_policy(pauses, grid=(1.0, 2.0, 3.0))}
        assert rows[1.0]["holds_cut"] == 2 and rows[2.0]["holds_cut"] == 1 and rows[3.0]["holds_cut"] == 0
        assert rows[1.0]["cut_per_100_answers"] == 100.0
        assert rows[2.0]["ends_observable"] == 1

    def test_a_real_cue_lets_the_room_answer_sooner_without_cutting_in_more(self):
        rep = tc.report(synthetic_rooms(separation=3.0))
        feat = {r["feature"]: r for r in rep["features"]}["f0_slope_st_per_s"]
        assert feat["auc"] < 0.1                       # ends fall, holds do not
        assert rep["models"]["1.0"]["auc"] > 0.9       # held out, room by room
        best = [r for r in rep["cue_policy"] if r["slow_sec"] == 2.0 and r["theta"] == 0.9
                and r["fast_sec"] == 1.0][0]
        assert best["early_share"] > 0.6 and best["mean_wait_sec"] < 1.5
        assert best["cut_per_100_answers"] <= best["silence_only_cut_per_100"] + 2

    def test_no_cue_buys_nothing(self):
        rep = tc.report(synthetic_rooms(separation=0.0))
        feat = {r["feature"]: r for r in rep["features"]}["f0_slope_st_per_s"]
        assert 0.4 < feat["auc"] < 0.6
        assert rep["models"]["1.0"]["auc"] < 0.6
        sure = [r for r in rep["cue_policy"] if r["theta"] == 0.9]
        assert all(r["early_share"] < 0.2 for r in sure)

    def test_a_guest_who_never_pauses_long_gets_a_shorter_wait(self):
        quick = [tc.Pause(at=float(i), length=0.6, label="hold") for i in range(40)]
        quick += [tc.Pause(at=100.0 + i, length=4.0, label="end", host_after=4.0) for i in range(10)]
        slow = [tc.Pause(at=float(i), length=0.6 if i % 4 else 2.6, label="hold") for i in range(40)]
        slow += [tc.Pause(at=100.0 + i, length=4.0, label="end", host_after=4.0) for i in range(10)]
        q = {(r["quantile"], r["margin_sec"]): r for r in tc.adaptive_policy({"q": quick})}
        s = {(r["quantile"], r["margin_sec"]): r for r in tc.adaptive_policy({"s": slow})}
        assert q[(0.98, 0.5)]["mean_wait_sec"] == pytest.approx(1.5)   # the floor
        assert s[(0.98, 0.5)]["mean_wait_sec"] == pytest.approx(3.1)   # 2.6 + 0.5
        # Nothing learned from the future: the first 20 pauses wait the start value.
        assert q[(0.98, 0.5)]["cut_per_100_answers"] == 0.0
        assert s[(0.98, 0.5)]["cut_per_100_answers"] == 0.0

    def test_the_report_renders(self):
        md = tc.to_markdown(tc.report(synthetic_rooms(separation=2.0, rooms=3)))
        assert md.startswith("# When has the guest finished?")
        assert "## Silence alone" in md and "## Each cue on its own" in md
        assert "## The guest's own habit" in md


class TestWhichTracks:
    def test_an_interview_reads_its_processed_tracks(self):
        run = {"grok_session_log": {"tracks": {"processed": {
            "guest": "g.wav", "mira": "m.wav", "host": "h.wav"}}}}
        assert tc.room_sources(run) == ("g.wav", ["m.wav", "h.wav"])

    def test_a_test_room_reads_the_two_sides_of_its_recording(self):
        run = {"grok_session_log": {}, "recording_guest_url": "https://vox/rec.mp3"}
        assert tc.room_sources(run) == (("https://vox/rec.mp3", 0), [("https://vox/rec.mp3", 1)])
        assert tc.room_sources({"grok_session_log": {}}) is None

    @pytest.mark.skipif(__import__("shutil").which("ffmpeg") is None, reason="no ffmpeg")
    def test_one_channel_of_a_stereo_file(self, tmp_path):
        import subprocess
        out = tmp_path / "st.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                        "sine=frequency=200:duration=1", "-f", "lavfi", "-i",
                        "anullsrc=r=44100:cl=mono", "-filter_complex",
                        "[0:a][1:a]amerge=inputs=2[a]", "-map", "[a]", "-t", "1", str(out)],
                       check=True)
        left, right = tc.load_audio((str(out), 0)), tc.load_audio((str(out), 1))
        assert np.abs(left).max() > 0.1 and np.abs(right).max() < 1e-3

    def test_placed_takes_are_used_as_they_are(self, tmp_path):
        video = {"fps": 30, "takes": [{"url": "x", "pieces": []}]}
        run = {"grok_session_log": {"tracks": {"video": video}}}
        assert tc.room_video(run, "g.wav", tmp_path) is video
        assert tc.room_video({"grok_session_log": {}}, "g.wav", tmp_path) is None


class TestItNeverTouchesARoom:
    def test_read_only(self):
        src = (ROOT / "pipelines" / "voices" / "turn_cues.py").read_text(encoding="utf-8")
        assert "sb_update" not in src and "r2_upload" not in src and "send_email" not in src
