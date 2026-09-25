"""Where the published conversation comes from (Sept 22 2026).

Until today every episode was cut from ``run:guest``: the Voximplant stereo
recording of the guest's leg, folded down the middle. Left is the guest's
microphone, right is everything the guest heard. That was the only thing we
had, and for a guest wearing headphones it is fine.

For a guest who is not, it is Mira twice. Her voice comes out of their
speakers, back into their microphone a few hundred milliseconds later, and
the fold puts that on top of her real track. Sameer Ranjan's and Meridan
Zerner's episodes both carry it, and it is the same artifact that put her
sentences into their transcripts as if they had said them.

The pipeline already builds the better answer and then did not use it: one
processed track per speaker, placed on the room's clock, with everyone
else's bleed gated out. This is the contract that the edit is cut from those
instead, and — because a gate that removes too much is a worse failure than
an echo — that the edit measures the gate before trusting it.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V = ROOT / "pipelines" / "voices"
ASSEMBLE = (V / "assemble_edit.py").read_text(encoding="utf-8")
AUTO = (V / "auto_edit.py").read_text(encoding="utf-8")
BLEED = (V / "audio" / "bleed.py").read_text(encoding="utf-8")


def _pyfn(name: str, src: str) -> str:
    start = src.index(f"def {name}(")
    rest = src[start:]
    end = rest.index("\ndef ", 1)
    return rest[:end]


class TestTheDefaultBed:
    def test_the_auto_edit_asks_before_it_chooses(self):
        assert "def _clean_bed(" in AUTO
        assert "clean, bed_why = _clean_bed(run)" in AUTO

    def test_it_cuts_from_the_clean_tracks_when_it_can(self):
        body = _pyfn("build", AUTO)
        assert '{"from": "mix:clean"} if clean else' in body

    def test_the_stereo_fold_survives_as_the_fallback(self):
        body = _pyfn("build", AUTO)
        assert '{"from": "run:guest", "balance": True, "voice_match": "right"}' in body

    def test_both_beds_take_the_same_cuts(self):
        # The drops, the start and the end are editorial decisions and do not
        # change with the bed. One dict, spread into every conversation cut.
        body = _pyfn("build", AUTO)
        assert body.count("{**bed,") == 2

    def test_the_reason_reaches_the_rationale(self):
        body = _pyfn("build", AUTO)
        assert "rationale = (rationale + \" \" if rationale else \"\") + bed_why" in body


class TestWhenItRefuses:
    """Three ways the processed tracks are not the better answer."""

    def test_no_processed_tracks(self):
        body = _pyfn("_clean_bed", AUTO)
        assert 'if not processed.get("guest") or not processed.get("mira"):' in body
        assert "CUT FROM THE STEREO" in body

    def test_a_track_off_the_clock(self):
        # Folding an unplaced track slides a speaker away from the
        # conversation, which is worse than any echo.
        body = _pyfn("_clean_bed", AUTO)
        assert 'tracks.get("unaligned")' in body
        assert "could not be placed on the room's clock" in body

    def test_a_gate_that_took_too_much(self):
        body = _pyfn("_clean_bed", AUTO)
        assert 'stats.get("loud_muted_sec")' in body
        assert "OVERREACH_MAX_SEC" in body
        assert "OVERREACH_MAX_SEC = 3.0" in AUTO

    def test_an_unmeasured_gate_is_said_out_loud(self):
        # Runs processed before the measurement existed still get the better
        # bed, but the note tells whoever listens what was not checked.
        body = _pyfn("_clean_bed", AUTO)
        assert "predates the over-reach" in body


class TestTheGateMeasuresItsOwnReach:
    def test_bleed_reports_what_it_took_from_the_speaker(self):
        assert "loud_muted_sec" in BLEED
        assert "BLEED_MIN_GAP_DB" in BLEED
        body = _pyfn("strip_bleed", BLEED)
        assert "mute & (tdb >= own_db - BLEED_MIN_GAP_DB)" in body

    def test_it_is_in_the_stats_the_edit_reads(self):
        body = _pyfn("strip_bleed", BLEED)
        assert '"loud_muted_sec": round(loud_muted_sec, 1)' in body


class TestTheFold:
    def test_every_speaker_is_levelled_alone(self):
        body = _pyfn("_piece_clean", ASSEMBLE)
        assert "CLEAN_SIDE.format(" in body
        assert "amix=inputs={len(srcs)}" in body
        assert "BALANCE_GLUE" in body

    def test_a_silent_track_is_not_levelled_up_into_hiss(self):
        # A per-speaker track is silence for most of an episode, and
        # dynaudnorm brought silence up (-58 dBFS room tone arrived at -37.2);
        # its threshold fix then faded every sentence out (Sept 25 2026). A
        # fixed gain measured on the SPEECH lifts neither: the silence keeps
        # its natural distance under the voice.
        levelling = ASSEMBLE[ASSEMBLE.index("SIDE_CHAIN ="):ASSEMBLE.index("BALANCE_GLUE =")]
        assert "dynaudnorm" not in levelling.split("#")[0]
        assert "CLEAN_SIDE = SIDE_CHAIN" in ASSEMBLE
        assert "speech = db[db > loud - 25.0]" in ASSEMBLE
        # The stereo path keeps the behaviour it was proven with.
        body = _pyfn("_piece", ASSEMBLE)
        assert "SIDE_CHAIN.format(" in body

    def test_only_mira_gets_her_presence_eq(self):
        # On the stereo path VOICE_MATCH landed on the channel carrying Mira
        # AND the co-host, so it was equalising a human being too.
        body = _pyfn("_piece_clean", ASSEMBLE)
        assert 'extra = ("," + VOICE_MATCH) if role == "mira" else ""' in body

    def test_the_guest_is_folded_first_and_mira_last(self):
        assert 'CLEAN_ROLES = ("guest", "host", "mira")' in ASSEMBLE

    def test_a_missing_track_is_not_silently_dropped(self):
        assert "mix:clean needs the processed per-speaker tracks" in ASSEMBLE

    def test_the_sources_come_off_the_run_row(self):
        body = _pyfn("_clean_sources", ASSEMBLE)
        assert 'sources[f"track:{role}"]' in body


# ---------------------------------------------------------------------------
# The decisions themselves, not the source text.

import shutil  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import wave  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402

sys.path.insert(0, str(V))
sys.path.insert(0, str(ROOT))


def _run(tracks: dict) -> dict:
    return {"grok_session_log": {"tracks": tracks}}


class TestTheDecision:
    def _bed(self, tracks):
        import auto_edit
        return auto_edit._clean_bed(_run(tracks))

    def test_a_clean_measured_run_uses_the_tracks(self):
        use, why = self._bed({"processed": {"guest": "u", "mira": "u"},
                              "unaligned": [],
                              "bleed": {"guest": {"bleed": True,
                                                  "loud_muted_sec": 0.4}}})
        assert use is True and "no echo" in why

    def test_a_run_with_no_tracks_falls_back(self):
        use, why = self._bed({})
        assert use is False and "no processed per-speaker tracks" in why

    def test_an_unplaced_track_falls_back(self):
        use, _ = self._bed({"processed": {"guest": "u", "mira": "u"},
                            "unaligned": ["guest"]})
        assert use is False

    def test_an_overreaching_gate_falls_back(self):
        use, why = self._bed({"processed": {"guest": "u", "mira": "u"},
                              "unaligned": [],
                              "bleed": {"guest": {"bleed": True,
                                                  "loud_muted_sec": 9.1}}})
        assert use is False and "guest 9s" in why

    def test_the_threshold_is_where_it_says_it_is(self):
        import auto_edit
        just_under = auto_edit.OVERREACH_MAX_SEC - 0.1
        use, _ = self._bed({"processed": {"guest": "u", "mira": "u"},
                            "unaligned": [],
                            "bleed": {"guest": {"bleed": True,
                                                "loud_muted_sec": just_under}}})
        assert use is True

    def test_a_track_the_gate_left_alone_is_fine(self):
        # "bleed": False means it found nothing to remove, not that it failed.
        use, _ = self._bed({"processed": {"guest": "u", "mira": "u"},
                            "unaligned": [],
                            "bleed": {"guest": {"bleed": False}}})
        assert use is True


def _tone(path: Path, freq: float, seconds: float, at: float,
          amp: float = 0.5, sr: int = 48000) -> Path:
    n = int(sr * seconds)
    t = np.arange(n) / sr
    x = amp * np.sin(2 * np.pi * freq * t)
    gate = np.zeros(n)
    gate[int(at * sr):int((at + 2.0) * sr)] = 1.0
    x = x * gate
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 32000).astype("<i2").tobytes())
    return path


def _band_db(path: Path, lo: int, hi: int) -> float:
    out = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path),
         "-af", f"highpass=f={lo},lowpass=f={hi},volumedetect", "-f", "null", "-"],
        capture_output=True, text=True, timeout=300)
    for line in out.stderr.splitlines():
        if "mean_volume" in line:
            return float(line.split("mean_volume:")[1].split("dB")[0])
    return -99.0


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
class TestTheFoldActuallyFolds:
    """Three speakers in, three speakers out — and the end measured across
    all of them rather than from whichever one happened to be first."""

    def test_nobody_is_lost_in_the_fold(self, tmp_path):
        import assemble_edit
        guest = _tone(tmp_path / "g.wav", 180, 10, at=0.5)
        host = _tone(tmp_path / "h.wav", 900, 10, at=4.0)
        mira = _tone(tmp_path / "m.wav", 3000, 10, at=7.0)
        out = tmp_path / "piece.wav"
        assemble_edit._piece_clean(
            {"start": 0.0, "end": 9.5, "gaps": False},
            [("guest", guest), ("host", host), ("mira", mira)], out)
        assert out.exists()
        assert 9.0 < assemble_edit._duration(out) < 10.0
        for lo, hi in ((120, 260), (700, 1200), (2400, 3600)):
            assert _band_db(out, lo, hi) > -45.0, f"{lo}-{hi} Hz went missing"

    def test_the_seam_waits_for_the_last_voice(self, tmp_path):
        import assemble_edit
        # The guest stops at 2.5s; Mira keeps going until 9.0. Asking the
        # guest's track alone would end the episode six seconds early.
        guest = _tone(tmp_path / "g.wav", 180, 12, at=0.5)
        mira = _tone(tmp_path / "m.wav", 900, 12, at=7.0)
        both = assemble_edit._last_silence_before([guest, mira], 9.4)
        assert both is not None and 9.0 < both < 9.8
        alone = assemble_edit._last_silence_before(guest, 9.4)
        assert alone is None or alone < both
