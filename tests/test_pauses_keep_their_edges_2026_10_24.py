"""Patrick, Oct 24 2026, on Jason Shumard's and Stuart Berkowitz's episodes:
Mira's questions sounded cut off and answers were missing their first words.
The assembler closed long pauses with ffmpeg's silenceremove, which resumes
copying only once the level is back over -40 dB, so the soft start of a word
after a pause went out with the silence (about a tenth of a second of a
rising onset, measured). close_gaps shortens a pause in its middle and
leaves both edges alone."""

import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
sys.path.insert(0, str(ROOT))

import assemble_edit as ae  # noqa: E402

SR = 48000


def _write(path: Path, x: np.ndarray) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(np.clip(x * 32767, -32768, 32767).astype(np.int16).tobytes())


def _read(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32767


def _word(sec: float, onset_sec: float = 0.12) -> np.ndarray:
    t = np.arange(int(sec * SR)) / SR
    x = 0.1 * np.sin(2 * np.pi * 300 * t)
    n = int(onset_sec * SR)
    x[:n] *= 10 ** (np.linspace(-60, 0, n) / 20)  # a soft start, 60 dB below
    return x


def test_a_long_pause_is_shortened_and_the_next_word_keeps_its_start(tmp_path):
    word = _word(0.5)
    x = np.concatenate([_word(0.5), np.zeros(int(2.5 * SR)), word, np.zeros(int(0.3 * SR))])
    f = tmp_path / "p.wav"
    _write(f, x)
    stats = ae.close_gaps(f)
    y = _read(f)
    assert stats["closed"] == 1
    assert 1.4 < stats["removed_sec"] < 1.7
    # the second word, its soft start included, is all there, sample for
    # sample, just before the trailing 0.3 s (too short to be touched)
    at = len(y) - int(0.3 * SR) - len(word)
    assert np.allclose(y[at:at + len(word)], word, atol=2e-4)
    # and what is left of the pause before it is about a second
    assert 0.8 < at / SR - 0.5 < 1.1


def test_a_short_pause_is_left_alone(tmp_path):
    x = np.concatenate([_word(0.5), np.zeros(int(0.9 * SR)), _word(0.5)])
    f = tmp_path / "s.wav"
    _write(f, x)
    assert ae.close_gaps(f) == {"closed": 0, "removed_sec": 0.0}
    assert len(_read(f)) == len(x)


def test_what_is_left_of_a_pause_is_about_a_second(tmp_path):
    x = np.concatenate([_word(0.5), np.zeros(int(4.0 * SR)), _word(0.5)])
    f = tmp_path / "l.wav"
    _write(f, x)
    ae.close_gaps(f)
    y = _read(f)
    quiet = np.abs(y[int(0.5 * SR):]) < 1e-3
    run = np.flatnonzero(~quiet)[0] / SR   # silence before the second word
    assert 0.85 < run < 1.05
