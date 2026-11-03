"""The Age of AI edit is encoded like the network and its pads carry the room
(Nov 3 2026, six-month review item audio-10).

The flagship interview was the only published file at ``-b:a 128k`` CBR
mono (every show masters at ``-q:a 0`` VBR) and carried 50.6 s of exact
zeros: every ``gap`` in an EDL was ``anullsrc``, and the breath between
Mira's paragraph takes was too. What binds now:

* the master encode has ONE owner, ``engine.audio.JOIN_MP3_ENCODE_ARGS``
  (VBR ``-q:a 0``, never a CBR cap — a mono 48 kHz speech file lands
  wherever the encoder puts it, measured ~130 kbps, so no number is
  promised), and the edit, the narration and Nerra Daily all import it;
* a pad is the quietest 120 ms of the adjacent GUEST piece's facing edge,
  looped (``engine.story_breaks.write_room_tone_pad``); a gated track's
  zeros are not a room; no source, or no window, falls back to the silence
  it was, and the attempt never raises;
* the file that ships is measured from itself: ``encode_kbps`` and
  ``digital_zero_sec`` (``None`` when unmeasured, never 0 for "unknown").
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
sys.path.insert(0, str(ROOT))

import assemble_edit as ae  # noqa: E402
import audio_metrics as am  # noqa: E402
import learning  # noqa: E402
import narrate  # noqa: E402
from engine import story_breaks as sb  # noqa: E402
from engine.audio import JOIN_MP3_ENCODE_ARGS  # noqa: E402

HAVE_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
needs_ffmpeg = pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg not installed")

RATE = 48000
FRAME = int(am.ZERO_FRAME_SEC * RATE)  # 960 samples


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _write_wav(path: Path, samples: np.ndarray, rate: int = RATE) -> Path:
    pcm = np.clip(np.round(np.asarray(samples, dtype=np.float64) * 32767), -32768, 32767)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.astype(np.int16).tobytes())
    return path


def _tone(seconds: float, level: float = 0.1) -> np.ndarray:
    """A speech-shaped tone: 180 Hz, modulated at 3 Hz, about -20 dBFS."""
    t = np.arange(int(seconds * RATE)) / RATE
    return level * np.sin(2 * np.pi * 180 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t))


def _noise(seconds: float, level: float = 0.001, seed: int = 11) -> np.ndarray:
    """A room's floor: white noise at about -60 dBFS (never an exact zero)."""
    x = np.random.default_rng(seed).normal(0, level, int(seconds * RATE))
    x[x == 0] = level
    return x


def _decode(path: Path, rate: int = RATE) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1",
                          "-ar", str(rate), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def _rms_db(x: np.ndarray) -> float:
    return float(20 * np.log10(np.sqrt(np.mean(np.asarray(x, dtype=np.float64) ** 2)) + 1e-12))


# ---------------------------------------------------------------------------
# One owner for the master encode
# ---------------------------------------------------------------------------

class TestTheEditIsEncodedLikeTheNetwork:
    def test_the_master_encode_has_one_owner(self):
        from engine.daily_edition import EDITION_ENCODE_ARGS

        assert JOIN_MP3_ENCODE_ARGS == ["-c:a", "libmp3lame", "-q:a", "0"]
        assert "-b:a" not in JOIN_MP3_ENCODE_ARGS, "VBR -q:a 0, never a CBR cap"
        # Nerra Daily's edition encode is the same object's arguments, not a copy.
        assert EDITION_ENCODE_ARGS[-len(JOIN_MP3_ENCODE_ARGS):] == JOIN_MP3_ENCODE_ARGS

    def test_the_assemble_command_carries_the_shared_setting(self, tmp_path):
        cmd = ae._master_cmd([tmp_path / "a.wav", tmp_path / "b.wav"], tmp_path / "e.mp3")
        tail = cmd[cmd.index("-map") + 2:]
        assert tail[:4] == ["-ar", "48000", "-ac", "1"], "the Voices files stay 48 kHz mono"
        assert tail[4:4 + len(JOIN_MP3_ENCODE_ARGS)] == JOIN_MP3_ENCODE_ARGS
        assert "128k" not in cmd and "-b:a" not in cmd
        assert cmd.count("-i") == 2 and "concat=n=2" in cmd[cmd.index("-filter_complex") + 1]

    def test_the_stitch_command_carries_the_shared_setting(self, tmp_path):
        cmd = narrate._stitch_cmd([tmp_path / "t1.wav", tmp_path / "breath.wav",
                                   tmp_path / "t2.wav"], tmp_path / "seg.mp3", -16.0)
        tail = cmd[cmd.index("-map") + 2:]
        assert tail[:4] == ["-ac", "1", "-ar", "48000"]
        assert tail[4:4 + len(JOIN_MP3_ENCODE_ARGS)] == JOIN_MP3_ENCODE_ARGS
        assert "128k" not in cmd and "-b:a" not in cmd
        assert "concat=n=3" in cmd[cmd.index("-filter_complex") + 1]
        assert "loudnorm=I=-16.0" in cmd[cmd.index("-filter_complex") + 1]

    @pytest.mark.parametrize("rel", ["pipelines/voices/assemble_edit.py",
                                     "pipelines/voices/narrate.py"])
    def test_no_voices_module_types_its_own_bitrate(self, rel):
        src = _read(rel)
        assert '"128k"' not in src and '"-b:a"' not in src
        assert "from engine.audio import JOIN_MP3_ENCODE_ARGS" in src
        assert "*JOIN_MP3_ENCODE_ARGS" in src

    def test_stitch_runs_the_shared_command_with_a_breath_per_seam(self, monkeypatch, tmp_path):
        """``_stitch`` reaches ffmpeg only through ``_stitch_cmd``, and puts
        one breath between every pair of takes (built from the take before
        it). ffmpeg is faked, so this runs anywhere."""
        calls = []

        class _Done:
            returncode = 0
            stdout = ""
            stderr = ""

        def fake_run(cmd, *a, **k):
            calls.append(list(cmd))
            return _Done()

        monkeypatch.setattr(subprocess, "run", fake_run)
        parts = [tmp_path / "p1_trim.wav", tmp_path / "p2_trim.wav", tmp_path / "p3_trim.wav"]
        out = narrate._stitch(parts, tmp_path / "intro.mp3", -16.0)
        assert out == tmp_path / "intro.mp3"
        final = calls[-1]
        assert "libmp3lame" in final and "-q:a" in final and "128k" not in final
        inputs = [Path(final[i + 1]) for i, a in enumerate(final) if a == "-i"]
        assert inputs == [parts[0], tmp_path / "breath_001.wav", parts[1],
                          tmp_path / "breath_002.wav", parts[2]]
        # Each breath was asked for from the take before it (the probe of
        # that take is the first ffmpeg-side call of each breath).
        probed = [c[-1] for c in calls if c and c[0] == "ffprobe"]
        assert probed == [str(parts[0]), str(parts[1])]


# ---------------------------------------------------------------------------
# The pads carry the room
# ---------------------------------------------------------------------------

class TestPadsCarryTheRoom:
    def test_quietest_window_can_refuse_digital_zero(self):
        buf = np.concatenate([np.zeros(RATE // 2), _noise(0.5, 0.01)])
        # Default: the zeros win, as before.
        assert sb.quietest_window(buf, RATE) == (0.0, sb.ROOM_TONE_WINDOW)
        # An RMS floor alone is not enough: a window that is mostly zeros
        # with a sliver of room clears it and still wins.
        straddle = sb.quietest_window(buf, RATE, min_rms=sb.ROOM_TONE_MIN_RMS)
        assert straddle is not None and straddle[0] < 0.5 < straddle[1]
        # With the zero-run rule the window lands in the noise.
        win = sb.quietest_window(buf, RATE, min_rms=sb.ROOM_TONE_MIN_RMS,
                                 max_zero_run=sb.ROOM_TONE_MAX_ZERO_RUN)
        assert win is not None and win[0] >= 0.5 - sb.ROOM_TONE_MAX_ZERO_RUN
        assert sb.quietest_window(np.zeros(RATE), RATE, min_rms=1e-5) is None
        assert sb.quietest_window(np.zeros(RATE), RATE, max_zero_run=0.002) is None
        assert sb.quietest_window(np.zeros(100), RATE, min_rms=1e-5) is None
        assert sb.quietest_window(np.zeros(100), RATE, max_zero_run=0.002) is None
        assert sb.quietest_window([], RATE, min_rms=1e-5) is None
        # A real floor crossing zero on single samples is not a run.
        floor = _noise(0.5, 0.0001, seed=3)
        floor[::7] = 0.0
        assert sb.quietest_window(floor, RATE, max_zero_run=0.002) is not None

    def test_a_gap_takes_the_room_of_the_conversation_beside_it(self):
        cuts = [{"from": "narration:intro"}, {"gap": 0.7}, {"from": "mix:clean"},
                {"gap": 0.4}, {"from": "track:guest"}, {"gap": 0.9}, {"from": "narration:outro"}]
        pieces = [Path("0.wav"), None, Path("2.wav"), None, Path("4.wav"), None, Path("6.wav")]
        # Narration before, conversation after: the conversation's opening edge.
        assert ae._tone_source(cuts, pieces, 1) == (Path("2.wav"), False)
        # Conversation on both sides: the one before, its closing edge.
        assert ae._tone_source(cuts, pieces, 3) == (Path("2.wav"), True)
        # Guest track before, narration after: the guest's edge.
        assert ae._tone_source(cuts, pieces, 5) == (Path("4.wav"), True)
        # Narration on both sides: Mira's own floor rather than zeros.
        assert ae._tone_source([{"from": "narration:a"}, {"gap": 0.5}, {"from": "narration:b"}],
                               [Path("a.wav"), None, Path("b.wav")], 1) == (Path("a.wav"), True)
        # Nothing rendered beside it: silence.
        assert ae._tone_source([{"gap": 0.5}], [None], 0) == (None, True)
        assert ae._tone_source([{"gap": 0.5}, {"gap": 0.5}], [None, None], 0) == (None, True)

    def test_assemble_renders_every_gap_from_its_neighbours(self):
        src = _read("pipelines/voices/assemble_edit.py")
        assert "_silence(float(cut" not in src, "a gap is never anullsrc first"
        assert "pieces[i] = _room_tone(seconds, out, src, at_end=at_end)" in src
        assert "_tone_source(cuts, pieces, i)" in src
        assert "subprocess.run(_master_cmd(pieces, episode), check=True)" in src
        assert "audio_metrics.shipped_file_metrics(episode)" in src
        assert '"shipped": shipped' in src

    @needs_ffmpeg
    def test_a_pad_from_a_guest_piece_has_no_digital_zero(self, tmp_path):
        guest = _write_wav(tmp_path / "guest.wav", np.concatenate([_tone(1.5), _noise(0.5)]))
        pad = ae._room_tone(0.7, tmp_path / "pad.wav", guest, at_end=True)
        x = _decode(pad)
        assert abs(len(x) / RATE - 0.7) < 0.01
        pcm = np.round(x.astype(np.float64) * 32767).astype(np.int16)
        assert am.digital_zero_sec(pcm, RATE) == 0.0
        frames = pcm[: (len(pcm) // FRAME) * FRAME].reshape(-1, FRAME)
        assert (np.abs(frames).max(axis=1) > 0).all(), "no 20 ms frame of exact zeros"

    @needs_ffmpeg
    def test_the_pad_is_the_room_not_the_speech(self, tmp_path):
        guest = _write_wav(tmp_path / "guest.wav", np.concatenate([_tone(1.5), _noise(0.5)]))
        pad = _decode(ae._room_tone(0.7, tmp_path / "pad.wav", guest, at_end=True))
        level = _rms_db(pad)
        assert -75 < level < -50, f"the pad sits at the -60 dBFS floor, not the -20 tone: {level:.1f}"
        # The opening edge of a piece that STARTS on its room works the same way.
        guest2 = _write_wav(tmp_path / "next.wav", np.concatenate([_noise(0.4, seed=5), _tone(1.5)]))
        pad2 = _decode(ae._room_tone(0.4, tmp_path / "pad2.wav", guest2, at_end=False))
        assert -75 < _rms_db(pad2) < -50

    @needs_ffmpeg
    def test_a_gated_tracks_zeros_are_not_a_room(self, tmp_path):
        """A per-speaker track gated to exact zeros at its edge: the window
        is the real floor further in, never the zeros."""
        gated = _write_wav(tmp_path / "gated.wav",
                           np.concatenate([_tone(1.0), _noise(0.3), np.zeros(RATE // 2)]))
        span = sb.room_tone_span(gated, at_end=True)
        assert span is not None and 1.0 <= span[0] < 1.3
        pad = _decode(ae._room_tone(0.6, tmp_path / "pad.wav", gated, at_end=True))
        pcm = np.round(pad.astype(np.float64) * 32767).astype(np.int16)
        assert am.digital_zero_sec(pcm, RATE) == 0.0
        assert -75 < _rms_db(pad) < -50

    @needs_ffmpeg
    def test_no_source_falls_back_to_silence(self, tmp_path):
        pad = _decode(ae._room_tone(0.5, tmp_path / "pad.wav", None))
        assert abs(len(pad) / RATE - 0.5) < 0.01
        assert not pad.any()

    @needs_ffmpeg
    def test_a_missing_or_all_zero_source_falls_back_without_raising(self, tmp_path):
        pad = _decode(ae._room_tone(0.5, tmp_path / "pad.wav", tmp_path / "nope.wav"))
        assert abs(len(pad) / RATE - 0.5) < 0.01 and not pad.any()
        zeros = _write_wav(tmp_path / "zeros.wav", np.zeros(RATE))
        assert sb.room_tone_span(zeros) is None
        assert sb.write_room_tone_pad(tmp_path / "pad2.wav", 0.5, zeros) == "silence"
        assert not _decode(tmp_path / "pad2.wav").any()

    def test_room_tone_span_never_raises(self, tmp_path):
        assert sb.room_tone_span(tmp_path / "missing.wav") is None
        assert sb.room_tone_span(Path("/dev/null")) is None

    @needs_ffmpeg
    def test_the_breath_between_takes_is_miras_own_floor(self, tmp_path):
        take = _write_wav(tmp_path / "take_trim.wav", np.concatenate([_tone(1.2), _noise(0.4)]))
        breath = _decode(narrate._breath(tmp_path / "breath_001.wav", take))
        assert abs(len(breath) / RATE - narrate.BREATH_SEC) < 0.01
        assert breath.any() and -75 < _rms_db(breath) < -50


# ---------------------------------------------------------------------------
# The shipped file is measured
# ---------------------------------------------------------------------------

class TestTheShippedFileIsMeasured:
    def test_digital_zero_counts_whole_frames_only(self):
        x = np.ones(FRAME * 60, dtype=np.int16)
        x[FRAME * 10:FRAME * 35] = 0          # 25 frames = 0.50 s
        x[FRAME * 40:FRAME * 43] = 0          # 3 frames = 0.06 s
        x[FRAME * 50 + FRAME // 2:FRAME * 51 + FRAME // 2] = 0  # straddles two frames: none
        assert am.zero_frames(x, FRAME) == 28
        assert am.digital_zero_sec(x, RATE) == 0.56
        assert am.digital_zero_sec(np.ones(FRAME * 10, dtype=np.int16), RATE) == 0.0

    def test_unknown_is_none_never_zero(self):
        assert am.digital_zero_sec([], RATE) is None
        assert am.digital_zero_sec(np.ones(10), 0) is None
        assert am.zero_frames([], FRAME) == 0
        assert am.shipped_file_metrics(Path("/nonexistent/edit.mp3")) == {
            "encode_kbps": None, "digital_zero_sec": None}
        assert am.encode_kbps(Path("/nonexistent/edit.mp3")) is None
        assert am.digital_zero_sec_of(Path("/nonexistent/edit.mp3")) is None
        assert set(am.SHIPPED_KEYS) == {"encode_kbps", "digital_zero_sec"}

    def test_a_stereo_frame_is_zero_only_on_both_channels(self):
        stereo = np.ones(FRAME * 2 * 10, dtype=np.int16)
        stereo[0::2] = 0                      # left silent, right not
        assert am.digital_zero_sec(stereo, RATE, channels=2) == 0.0
        stereo[FRAME * 2 * 2:FRAME * 2 * 4] = 0  # two whole stereo frames
        assert am.digital_zero_sec(stereo, RATE, channels=2) == 0.04

    @needs_ffmpeg
    def test_a_file_is_measured_from_its_own_samples(self, tmp_path):
        wav = _write_wav(tmp_path / "edit.wav",
                         np.concatenate([_noise(1.0, 0.03), np.zeros(RATE // 2), _noise(0.5, 0.03)]))
        measured = am.shipped_file_metrics(wav)
        assert measured["digital_zero_sec"] == 0.5
        assert measured["encode_kbps"] == 768  # 48 kHz x 16 bit, mono
        mp3 = tmp_path / "edit.mp3"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-ar", "48000", "-ac", "1",
                        *JOIN_MP3_ENCODE_ARGS, str(mp3)], check=True)
        shipped = am.shipped_file_metrics(mp3)
        # The encoder's frame edges eat a little of the stretch; the rest is read.
        assert 0.4 <= shipped["digital_zero_sec"] <= 0.5
        assert isinstance(shipped["encode_kbps"], int) and shipped["encode_kbps"] > 0
        assert shipped["encode_kbps"] != 128, "VBR lands where the encoder puts it, never on the old cap"

    def test_the_record_keeps_every_other_note(self, monkeypatch):
        updates = []
        monkeypatch.setattr(learning, "sb_select", lambda table, q="": [
            {"interview_id": "iv1", "notes": {"audio": {"overlap_spans": []}, "dead_air_basis": "x"}}])
        monkeypatch.setattr(learning, "sb_update", lambda table, q, row: updates.append((table, q, row)) or True)
        shipped = {"encode_kbps": 131, "digital_zero_sec": 0.0}
        assert learning.record_shipped_metrics("iv1", shipped) is True
        (table, q, row), = updates
        assert table == "episode_metrics" and q == "interview_id=eq.iv1"
        assert set(row) == {"notes"}, "a merge of notes, never a replace of the row"
        assert row["notes"]["shipped"] == shipped
        assert row["notes"]["audio"] == {"overlap_spans": []} and row["notes"]["dead_air_basis"] == "x"

    def test_the_record_never_raises_and_never_invents_a_row(self, monkeypatch):
        updates = []
        monkeypatch.setattr(learning, "sb_select", lambda table, q="": [])
        monkeypatch.setattr(learning, "sb_update", lambda *a, **k: updates.append(a) or True)
        assert learning.record_shipped_metrics("iv1", {"encode_kbps": 131}) is False
        assert updates == []
        assert learning.record_shipped_metrics("", {"encode_kbps": 131}) is False
        assert learning.record_shipped_metrics("iv1", {}) is False

        def boom(*a, **k):
            raise RuntimeError("supabase down")

        monkeypatch.setattr(learning, "sb_select", boom)
        assert learning.record_shipped_metrics("iv1", {"encode_kbps": 131}) is False
