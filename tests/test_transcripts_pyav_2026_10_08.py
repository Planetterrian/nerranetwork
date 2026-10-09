"""Oct 8 2026 — every episode shipped with no transcript, the second time.

Dependabot's #1365 rewrote the Sep 30 pin ``av>=11,<19`` to
``av>=19.0.1,<20`` and was merged in a batch of routine bumps on the night
of Oct 7. PyAV 19 removed the ``metadata_errors`` keyword faster-whisper
1.2.1 passes to ``av.open``, so all 21 episodes of 10-08 logged
"transcription failed … TypeError", the spoken-text gate recorded
``no_transcript`` on every show, Shorts and the caption tracks went out
without captions, and Nerra Daily Ep049 shipped all 21 segments whole
(``cut_kind: none``) because the promo cut reads the transcript.

What binds now:
* Whisper never decodes through PyAV: ``engine.transcripts.load_whisper_audio``
  decodes with ffmpeg (bit-identical samples to faster-whisper's own decoder
  on SpaceX Ep124) and both call sites hand ``transcribe`` the array.
* The PyAV ceiling stays (tests/test_repetition_pass_2026_09_30.py) and
  Dependabot ignores PyAV 19+ so the bump is not proposed again.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import transcripts as tr  # noqa: E402

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")


def _tone(path: Path, seconds: float = 1.5) -> Path:
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
         f"sine=frequency=440:duration={seconds}", "-ar", "48000", "-ac", "2",
         "-y", str(path)], check=True)
    return path


def _fake_whisper(monkeypatch, seen: list):
    class Info:
        language = "en"
        language_probability = 1.0
        duration = 1.5

    class Model:
        def __init__(self, *a, **k):
            pass

        def transcribe(self, audio, **kw):
            seen.append(audio)
            if isinstance(audio, str):
                # What faster-whisper does with a path under PyAV 19.
                raise TypeError("open() got an unexpected keyword argument 'metadata_errors'")
            return iter(()), Info()

    fake = types.ModuleType("faster_whisper")
    fake.WhisperModel = Model
    monkeypatch.setitem(sys.modules, "faster_whisper", fake)


class TestWhisperNeverDecodesThroughPyAV:
    @needs_ffmpeg
    def test_the_audio_is_16k_mono_float(self, tmp_path):
        import numpy as np
        audio = tr.load_whisper_audio(_tone(tmp_path / "t.mp3"))
        assert isinstance(audio, np.ndarray) and audio.dtype == np.float32
        assert abs(len(audio) / tr.WHISPER_SAMPLE_RATE - 1.5) < 0.1
        assert 0.05 < float(np.max(np.abs(audio))) <= 1.0

    @needs_ffmpeg
    def test_generate_transcript_hands_whisper_an_array(self, monkeypatch, tmp_path):
        seen: list = []
        _fake_whisper(monkeypatch, seen)
        monkeypatch.setattr("builtins.print", lambda *a, **k: None)
        result = tr.generate_transcript(_tone(tmp_path / "ep.mp3"), tmp_path,
                                        "Show_Ep001_20261008")
        assert result is not None, "transcript failed on the PyAV-19 failure shape"
        assert seen and not isinstance(seen[0], str)
        assert result.json_path.exists() and result.vtt_path.exists()

    def test_without_ffmpeg_the_library_decoder_is_used(self, monkeypatch, tmp_path):
        monkeypatch.setattr(shutil, "which", lambda name: None)
        p = tmp_path / "ep.mp3"
        p.write_bytes(b"\x00" * 16)
        assert tr.load_whisper_audio(p) == str(p)

    @needs_ffmpeg
    def test_an_undecodable_file_falls_back_to_the_path(self, tmp_path):
        p = tmp_path / "ep.mp3"
        p.write_bytes(b"\x00" * 16)
        assert tr.load_whisper_audio(p) == str(p)

    def test_every_whisper_call_site_uses_it(self):
        for rel in ("engine/transcripts.py", "engine/tts_validation.py"):
            src = (ROOT / rel).read_text(encoding="utf-8")
            assert "load_whisper_audio(" in src, rel
            assert not re.search(r"\.transcribe\(\s*str\(audio_path\)", src), rel


class TestTheBumpIsNotProposedAgain:
    def test_dependabot_ignores_pyav_19(self):
        cfg = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
        m = re.search(r'dependency-name:\s*"av"\s*\n\s*versions:\s*\[">=19"\]', cfg)
        assert m, "Dependabot must not propose PyAV 19 (it proposed #1365)"

    def test_the_ceiling_comment_names_both_outages(self):
        req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        assert "Sep 30 2026" in req and "Oct 8 2026" in req
        # The CEILING is the guard; the floor may rise with the routine bumps
        # (Oct 9 2026: ``>=18.1.0`` with the runner upgrade).
        assert re.search(r"^av>=[\d.]+,<19\s*$", req, re.M)
