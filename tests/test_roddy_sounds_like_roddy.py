"""Sept 27 2026, Roddy de la Garza: Patrick heard distortion under every line.

His browser's own recording was a steady hiss at -39 dBFS with his voice three
decibels above it; the room's recording of the same leg was clean. The
pipeline preferred the browser take, and the levelling lifted the hiss with
the voice. Also: his cold-open clip ran nine seconds past his last word.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
V = ROOT / "pipelines" / "voices"
sys.path.insert(0, str(V))
sys.path.insert(0, str(ROOT / "pipelines"))
POST = (V / "post_interview.py").read_text(encoding="utf-8")
ASSEMBLE = (V / "assemble_edit.py").read_text(encoding="utf-8")
AUTO = (V / "auto_edit.py").read_text(encoding="utf-8")


def _wav(path: Path, x: np.ndarray, sr: int = 48000) -> Path:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
    return path


class TestAHissIsNotAVoice:
    def test_the_gate_is_wired_in_front_of_the_local_take(self):
        assert "and _clean_enough(local_guest, guest_vox, \"guest\")" in POST
        assert "MIN_SPREAD_DB = 15.0" in POST

    @pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
    def test_a_hissy_take_loses_to_a_clean_leg(self, tmp_path):
        import post_interview as pi

        sr = 48000
        rng = np.random.default_rng(5)
        t = 60
        speech = np.zeros(sr * t, dtype=np.float32)
        for k in range(0, t, 4):              # two seconds of "voice" every four
            speech[k * sr:(k + 2) * sr] = rng.standard_normal(2 * sr) * 0.05
        hiss = rng.standard_normal(sr * t).astype(np.float32) * 0.012
        clean = _wav(tmp_path / "leg.wav", speech)
        hissy = _wav(tmp_path / "local.wav", speech * 0.4 + hiss)
        assert pi._clean_enough(hissy, clean, "guest") is False
        assert pi._clean_enough(clean, clean, "guest") is True


class TestOneSideOfAStereoLeg:
    def test_the_run_row_can_name_a_side(self):
        assert '"processed_channels"' in ASSEMBLE
        assert "_TRACK_PAN[str(path)] = CHANNEL_FILTERS[side]" in ASSEMBLE
        body = ASSEMBLE[ASSEMBLE.index("def _piece_clean("):ASSEMBLE.index("def _silence(")]
        assert 'pick = _pan_of(_src) or "aformat=channel_layouts=mono"' in body

    def test_a_clip_from_that_track_takes_the_same_side(self):
        assert 'if ref.startswith("track:") and not cut.get("channel"):' in ASSEMBLE


class TestTheColdOpenEndsOnTheWord:
    def test_clips_are_edge_trimmed(self):
        assert '"trim_edges": True' in AUTO
        assert "elif cut.get(\"trim_edges\"):" in ASSEMBLE
        assert "areverse" in ASSEMBLE[ASSEMBLE.index("EDGE_TRIM ="):ASSEMBLE.index("CHANNEL_FILTERS = {")]
