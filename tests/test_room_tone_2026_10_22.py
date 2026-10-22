"""Oct 22 2026, Stan Lewis: the edit bed never drops to digital silence.

His gated iPhone take switched its background off and on 1,181 times in
one episode. ``audio.room_tone.fill_gate_holes`` puts his own pauses back
into the gate's holes, in the edit bed only.
"""
from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
V = ROOT / "pipelines" / "voices"
sys.path.insert(0, str(V))
sys.path.insert(0, str(ROOT))

pytest.importorskip("numpy")
from audio import room_tone as rt  # noqa: E402

SR = 48000


def _write(path: Path, x: np.ndarray) -> Path:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(np.clip(x, -32768, 32767).astype(np.int16).tobytes())
    return path


def _read(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)


def _rms_db(x: np.ndarray) -> float:
    return float(20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-9))


def _gated_take(seed: int = 7):
    """20 s: room tone at ~-50 dBFS, a 0.6 s phrase every 2 s at ~-20 dBFS,
    and the gate's zeros for 0.6 s between phrases."""
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 100, SR * 20).astype(np.float32)          # room tone
    holes = np.zeros(len(x), dtype=bool)
    for k in range(10):
        a = k * 2 * SR
        x[a:a + int(0.6 * SR)] += rng.normal(0, 3000, int(0.6 * SR))   # a phrase
        h = a + int(1.2 * SR)
        holes[h:h + int(0.6 * SR)] = True
    x[holes] = 0.0
    return x, holes


@pytest.mark.skipif(not __import__("shutil").which("ffmpeg"), reason="ffmpeg needed")
class TestFillGateHoles:
    def test_every_hole_gets_the_speakers_own_tone(self, tmp_path):
        x, holes = _gated_take()
        out, stats = rt.fill_gate_holes(_write(tmp_path / "g.wav", x), tmp_path / "f.wav")
        y = _read(out)
        assert stats["filled_sec"] == pytest.approx(6.0, abs=0.2)
        # No digital silence left, and the fill sits at the room's own level.
        frames = np.abs(y[: len(y) // 480 * 480]).reshape(-1, 480).max(1)
        assert (frames <= 1).sum() == 0
        room = x[~holes][np.abs(x[~holes]) < 400]
        filled = y[holes]
        assert abs(_rms_db(filled) - _rms_db(room)) < 3.0
        # What was not a hole is untouched.
        assert np.allclose(y[~holes], np.clip(x[~holes], -32768, 32767), atol=1.0)

    def test_a_take_without_holes_is_left_alone(self, tmp_path):
        x = np.random.default_rng(1).normal(0, 200, SR * 5).astype(np.float32)
        src = _write(tmp_path / "g.wav", x)
        out, stats = rt.fill_gate_holes(src, tmp_path / "f.wav")
        assert out == src and stats["filled_sec"] == 0.0

    def test_no_pauses_means_no_invented_tone(self, tmp_path):
        x = np.zeros(SR * 5, dtype=np.float32)
        x[: SR] = np.random.default_rng(2).normal(0, 3000, SR)  # one phrase, no pause
        src = _write(tmp_path / "g.wav", x)
        out, stats = rt.fill_gate_holes(src, tmp_path / "f.wav")
        assert out == src and stats["filled_sec"] == 0.0


class TestOnlyTheEditBed:
    POST = (V / "post_interview.py").read_text(encoding="utf-8")

    def test_the_leg_file_is_filled(self):
        body = self.POST[self.POST.index("def build_leg_local("):]
        body = body[:body.index("\ndef ")]
        assert "fill_gate_holes(guest" in body
        assert "except Exception" in body          # holes beat no leg file

    def test_the_processed_tracks_keep_their_zeros(self):
        assert self.POST.count("fill_gate_holes(") == 1
