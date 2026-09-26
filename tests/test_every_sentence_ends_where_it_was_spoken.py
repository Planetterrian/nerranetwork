"""Patrick's notes on Dr. Michael Brandt and Chad Law (Sept 25 2026).

* Every sentence faded out at the end, the guest's and Mira's alike. The
  per-speaker levelling (dynaudnorm over a 1.8 s window with a silence
  threshold) held each pause at unity gain while lifting the speech before
  it, and smoothed between the two: a ramp down across the last half second
  of every phrase. Levelling is now a fixed gain per voice.
* Mira talked over Chad twice in the middle of his answers. With one voice
  per track, her voice can be muted there while his plays on.
* The introduction opened on Dr. Brandt's own sentence read in Mira's voice,
  and the conversation opened on his reply to a welcome nobody heard. The
  episode now opens on a clip of the guest in their own voice after one line
  of context, and the conversation on Mira's welcome.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
V = ROOT / "pipelines" / "voices"
sys.path.insert(0, str(V))
sys.path.insert(0, str(ROOT / "pipelines"))

ASSEMBLE = (V / "assemble_edit.py").read_text(encoding="utf-8")
AUTO = (V / "auto_edit.py").read_text(encoding="utf-8")

HAVE_FFMPEG = shutil.which("ffmpeg") is not None


def _phrases(path: Path, sr: int = 16000) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1",
                          "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


@pytest.mark.skipif(not HAVE_FFMPEG, reason="needs ffmpeg")
class TestAPhraseEndsAtTheLevelItWasSpoken:
    def test_the_levelling_chain_does_not_fade_the_tail(self, tmp_path):
        import assemble_edit as ae

        # Three "phrases" of steady noise at a quiet voice level, each followed
        # by silence — the shape of anyone's track in a conversation.
        sr = 48000
        rng = np.random.default_rng(7)
        phrase = (rng.standard_normal(int(2.0 * sr)) * 0.02).astype(np.float32)
        gap = np.zeros(int(1.2 * sr), dtype=np.float32)
        signal = np.concatenate([phrase, gap] * 3)
        src = tmp_path / "voice.wav"
        pcm = (signal * 32767).astype("<i2").tobytes()
        import wave
        with wave.open(str(src), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(pcm)

        chain = ae.CLEAN_SIDE.format(restore="anull", gain=ae._speech_gain(src))
        out = tmp_path / "levelled.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-af",
                        chain, str(out)], check=True)
        y = _phrases(out)
        hop = 16000 // 50
        n = len(y) // hop
        db = 20 * np.log10(np.sqrt(np.mean(y[:n * hop].reshape(n, hop) ** 2, axis=1)) + 1e-9)
        per_phrase = int(3.2 * 50)
        for k in range(3):
            body = db[k * per_phrase + 25:k * per_phrase + 75]      # 0.5-1.5 s in
            tail = db[k * per_phrase + 85:k * per_phrase + 98]      # last 0.3 s
            assert np.median(body) - np.median(tail) < 1.5, (
                f"phrase {k}: the last 0.3 s sits "
                f"{np.median(body) - np.median(tail):.1f} dB under the body")

    def test_the_voice_is_brought_to_one_level(self, tmp_path):
        import assemble_edit as ae
        import wave

        sr = 48000
        t = np.arange(sr * 3) / sr
        quiet = (np.sin(2 * np.pi * 440 * t) * 0.01 * np.sqrt(2)).astype(np.float32)
        src = tmp_path / "quiet.wav"
        with wave.open(str(src), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes((quiet * 32767).astype("<i2").tobytes())
        ae._GAIN_CACHE.clear()
        gain = ae._speech_gain(src)
        # 0.01 RMS is -40 dBFS; the target is -20.
        assert 18.0 < gain < 22.0


class TestNoPerFrameLevellingOnAVoice:
    def test_dynaudnorm_is_gone_from_the_conversation_chains(self):
        chains = ASSEMBLE[ASSEMBLE.index("SPEECH_TARGET_DB ="):ASSEMBLE.index("BALANCE_GLUE =")]
        code = "\n".join(l.split("#")[0] for l in chains.splitlines())
        assert "dynaudnorm" not in code

    def test_one_gain_per_voice_across_every_cut(self):
        # Measured on the whole track, so a short cut and a long one beside it
        # come out at the same level and the seam does not jump.
        body = ASSEMBLE[ASSEMBLE.index("def _speech_gain("):ASSEMBLE.index("def _piece(")]
        assert "_speech_level_db(src, None, None, pan)" in body
        assert "_GAIN_CACHE[key] = gain" in body


class TestMiraCanBeTakenOutFromUnderTheGuest:
    def test_a_mute_becomes_a_timed_volume_on_her_track_only(self):
        import assemble_edit as ae

        cut = {"from": "mix:clean", "start": 100.0, "end": 400.0,
               "mute": [{"role": "mira", "from": 189.3, "to": 192.0}]}
        assert ae._mutes(cut, "guest") == ""
        assert ae._mutes(cut, "mira") == ",volume=0:enable='between(t,89.300,92.000)'"

    def test_the_clean_fold_applies_it(self):
        body = ASSEMBLE[ASSEMBLE.index("def _piece_clean("):ASSEMBLE.index("def _silence(")]
        assert "extra += _mutes(cut, role)" in body

    def test_the_detector_finds_an_interjection_and_spares_a_question(self, monkeypatch):
        from audio import overlap

        hop = overlap.HOP_SEC
        n = int(60 / hop)
        guest = np.zeros(n, dtype=bool)
        mira = np.zeros(n, dtype=bool)

        def span(arr, a, b):
            arr[int(a / hop):int(b / hop)] = True

        # 1. Guest answering 10-30 s; Mira says two words at 18 s; he goes on.
        span(guest, 10, 30)
        span(mira, 18, 19.5)
        # 2. Guest says "Yes" at 40 s over the start of Mira's real question,
        #    then stops and listens: a question, not an interruption.
        span(mira, 39.8, 46)
        span(guest, 40, 40.5)
        tracks = {"g": guest, "m": mira}
        monkeypatch.setattr(overlap, "_activity", lambda p: tracks[str(p)])
        found = overlap.interruptions(Path("g"), Path("m"))
        assert len(found) == 1
        a, b = found[0]
        assert a < 18 and 19.5 < b < 20.5


class TestTheOpen:
    def test_without_a_clip_the_introduction_still_reads(self):
        import auto_edit

        lead, clip = auto_edit._cold_open({"cold_open": None}, True,
                                          lambda t: t, 30.0, 2000.0)
        assert (lead, clip) == ("", None)
        assert 're.sub(r"^That\'s\\s+", "My guest is ", intro)' in AUTO

    def test_a_clip_is_the_guest_track_with_a_lead(self):
        import auto_edit

        lead, clip = auto_edit._cold_open(
            {"cold_open": {"from_sec": 98.4, "to_sec": 106.2,
                           "lead": "Chad Law argues about politics for a living."}},
            True, lambda t: t, 30.0, 2000.0)
        assert lead.startswith("Chad Law")
        assert clip["from"] == "track:guest" and clip["gaps"] is False
        assert clip["start"] == pytest.approx(98.3) and clip["end"] == pytest.approx(106.5)

    def test_no_clip_without_the_guest_track(self):
        import auto_edit

        lead, clip = auto_edit._cold_open(
            {"cold_open": {"from_sec": 98.4, "to_sec": 106.2, "lead": "x"}},
            False, lambda t: t, 30.0, 2000.0)
        assert clip is None


class TestTheTwoEpisodesPatrickHeard:
    @pytest.mark.parametrize("slug", ["dr_michael_brandt_2026_09_24", "chad_law_2026_09_24"])
    def test_they_open_on_the_guest_and_then_the_welcome(self, slug):
        spec = json.loads((V / "edl" / f"{slug}.json").read_text(encoding="utf-8"))
        froms = [c.get("from") for c in spec["cuts"] if "from" in c]
        assert froms[:3] == ["narration:lead", "track:guest", "narration:intro"]
        narration = json.loads((V / "narration" / f"{slug}.json").read_text(encoding="utf-8"))
        ids = [s["id"] for s in narration["segments"]]
        assert ids == ["lead", "intro", "outro"]
        intro = narration["segments"][1]["text"]
        assert intro.startswith("That's ")
        assert narration["segments"][2]["text"].endswith(
            "I'm Mira. Until next time — the next voice could be yours.")

    def test_chad_is_not_talked_over(self):
        spec = json.loads((V / "edl" / "chad_law_2026_09_24.json").read_text(encoding="utf-8"))
        mutes = [m for c in spec["cuts"] for m in c.get("mute", [])]
        assert any(m["role"] == "mira" and m["from"] <= 189.5 and m["to"] >= 191.9 for m in mutes)
        assert any(m["role"] == "mira" and m["from"] <= 2277.9 and m["to"] >= 2278.4 for m in mutes)


def _wav(path: Path, samples: np.ndarray, sr: int = 48000) -> Path:
    import wave
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
    return path


@pytest.mark.skipif(not HAVE_FFMPEG, reason="needs ffmpeg")
class TestTheEndKeepsTheGoodbye:
    """Sept 26 2026, Dr. Brandt. The published cut lost "My pleasure, thank you
    so much for having me": the end probe heard Mira's muted line over it and
    found no pause after it, because Mira's live "That's the end of the
    recording" began a third of a second after his last word."""

    def test_a_goodbye_under_a_muted_line_survives(self, tmp_path):
        import assemble_edit as ae

        sr = 48000
        rng = np.random.default_rng(3)

        def talk(total, spans, level):
            y = np.zeros(int(total * sr), dtype=np.float32)
            for a, b in spans:
                y[int(a * sr):int(b * sr)] = rng.standard_normal(int(b * sr) - int(a * sr)) * level
            return y

        # Mira thanks him (0-5 s), he says goodbye (7.0-9.0 s) while she talks
        # over it (7.2-8.9 s, muted), and she starts again at 9.3 s.
        guest = _wav(tmp_path / "g.wav", talk(12, [(7.0, 9.0)], 0.01))
        mira = _wav(tmp_path / "m.wav", talk(12, [(0.2, 5.0), (7.2, 8.9), (9.3, 11)], 0.05))
        ae._GAIN_CACHE.clear()
        cut = {"from": "mix:clean", "start": 0.0, "end": 9.2,
               "mute": [{"role": "mira", "from": 7.1, "to": 9.2}]}
        ae._end_on_the_last_word(cut, [("guest", guest), ("mira", mira)])
        assert cut["end"] >= 9.0, f"the goodbye was cut: end moved to {cut['end']}"

    def test_a_hand_set_end_is_left_alone(self):
        import assemble_edit as ae

        cut = {"from": "mix:clean", "start": 0.0, "end": 9.2, "exact_end": True}
        ae._end_on_the_last_word(cut, [("guest", Path("/nonexistent"))])
        assert cut["end"] == 9.2
