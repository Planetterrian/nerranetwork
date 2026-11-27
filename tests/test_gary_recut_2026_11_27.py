"""Gary Amaral, Nov 13 2026, said on air "cut off the pauses please", and
Patrick asked (Nov 27) for the questions he passed on to come out too. The
hand EDL in pipelines/voices/edl/gary_amaral_2026_11_13.json does both: its
conversation cuts skip every passed question, and each carries ``max_gap``
so the assembler closes his pauses tighter than the network's one second.
Unset, close_gaps behaves exactly as before."""

import json
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
sys.path.insert(0, str(ROOT))

import assemble_edit as ae  # noqa: E402

SR = 48000
EDL = ROOT / "pipelines" / "voices" / "edl" / "gary_amaral_2026_11_13.json"


def _write(path: Path, x: np.ndarray) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(np.clip(x * 32767, -32768, 32767).astype(np.int16).tobytes())


def _tone(sec: float) -> np.ndarray:
    t = np.arange(int(sec * SR)) / SR
    return 0.1 * np.sin(2 * np.pi * 300 * t)


def _pause_left(max_gap, tmp_path, pause=2.0):
    f = tmp_path / f"p{max_gap}.wav"
    _write(f, np.concatenate([_tone(0.5), np.zeros(int(pause * SR)), _tone(0.5)]))
    stats = ae.close_gaps(f) if max_gap is None else ae.close_gaps(f, max_gap)
    return pause - stats["removed_sec"], stats


def test_default_is_unchanged(tmp_path):
    left, _ = _pause_left(None, tmp_path)
    assert 0.9 < left < 1.0
    left_explicit, _ = _pause_left(1.0, tmp_path)
    assert abs(left - left_explicit) < 1e-6


def test_max_gap_closes_tighter(tmp_path):
    left, stats = _pause_left(0.6, tmp_path)
    assert stats["closed"] == 1
    assert 0.5 < left < 0.62


def test_a_pause_under_max_gap_is_left_alone(tmp_path):
    left, stats = _pause_left(0.6, tmp_path, pause=0.55)
    assert stats["closed"] == 0 and abs(left - 0.55) < 1e-6


def test_the_edl_skips_every_passed_question():
    edl = json.loads(EDL.read_text())
    conv = [c for c in edl["cuts"] if str(c.get("from", "")).startswith("mix:")]
    kept = [(float(c["start"]), float(c["end"])) for c in conv]
    # Room-clock moments that must be out: each question Gary passed on, Mira's
    # acknowledgement of the pass, his note about the pauses, and the
    # restarted closing thought.
    out = {
        "campaign that clicked": 463.0, "Of course, a different one": 474.5,
        "cut off the pauses please": 656.5, "brand motion": 665.0, "Sure (1)": 676.0,
        "handoff break": 1050.0, "Fine": 1061.0,
        "one of the reps": 1335.0, "No problem": 1344.5,
        "what docket sits at": 1717.0, "Sure (2)": 1725.5,
        "come around": 2012.0, "Of course": 2020.3,
        "BANT or MEDDIC first": 2076.0, "Understood": 2087.5,
        "messiest part": 2093.0, "Taking those": 2102.4,
        "restart": 2430.0,
    }
    for name, t in out.items():
        assert not any(a <= t < b for a, b in kept), name
    assert all(c.get("max_gap") for c in conv)
