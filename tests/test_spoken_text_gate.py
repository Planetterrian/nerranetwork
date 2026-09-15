"""Drift guards for the spoken-text gate (Sep 14 2026, Tesla Ep605).

Tesla Shorts Time Ep605 opened with 45 s of Grok TTS reading its own
text-normalizer's reasoning aloud ("One thing, the input has line
breaks, preserve them ... Rules. Do not convert at sign in code ...")
in place of the hook and identity line. ``_tts.txt`` was clean, the
tag-leak detector read 0, and the episode shipped everywhere. These
tests pin:

* the checker against the COMMITTED artifacts of that episode and of
  the healthy episode before it;
* the two Whisper-artifact filters against the committed episodes that
  motivated them (M&A Ep140 hallucination, MIT Ep162 repetition loop);
* the calibration: every English episode committed in a fixed window
  passes except Ep605 (a fixed window so new commits cannot move it);
* the config defaults (enforce network-wide, shadow on the RU shows);
* the runner wiring (closure, retry, skip) and the Grok
  ``text_normalization`` plumbing that did not exist before.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from engine import tts
from engine.spoken_text_gate import (
    DEFAULT_MAX_UNMATCHED_RUN,
    DEFAULT_MIN_OPENING_MATCH,
    check_spoken_text,
    check_transcript_files,
    collapse_loops,
    filter_segments,
    normalize_words,
    resolve_gate_mode,
)

ROOT = Path(__file__).resolve().parent.parent
DIGESTS = ROOT / "digests"

EP605 = "tesla_shorts_time/Tesla_Shorts_Time_Pod_Ep605_20260914"
EP604 = "tesla_shorts_time/Tesla_Shorts_Time_Pod_Ep604_20260913"
MA_EP140 = "models_agents/Models_Agents_Ep140_20260813"
MIT_EP162 = "modern_investing/Modern_Investing_Ep162_20260906"
ON_EP001 = "offshore_north/Offshore_North_Ep001_20260818"

LEAK = (
    "One thing, the input has line breaks, preserve them. The text ends "
    "abruptly, matter more. Since no conversions needed, output the same. "
    "But the human message is, followed by the text, I think, is part of the "
    "input, perhaps a tag for fast speech or something. But rules say leave "
    "as is. Rules. Do not convert at sign in code. But here, probably leave. "
    "So the output should be the entire text unchanged inside. But looking at "
    "previous, for hello, it's hello, then"
)


def _committed(base: str):
    tts_path = DIGESTS / f"{base}_tts.txt"
    json_path = DIGESTS / f"{base}_transcript.json"
    if not tts_path.exists() or not json_path.exists():
        pytest.skip(f"{base} artifacts not committed")
    return tts_path.read_text(encoding="utf-8"), json_path


def _segments_from_text(text: str, words_per_second: float = 2.5) -> list[dict]:
    """Synthetic Whisper segments: one per sentence at a natural rate."""
    segs, t = [], 0.0
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        n = len(sentence.split())
        if not n:
            continue
        span = n / words_per_second
        segs.append({"start": round(t, 2), "end": round(t + span, 2), "text": sentence})
        t += span + 0.4
    return segs


# ---------------------------------------------------------------------------
# The Ep605 defect against the committed artifacts
# ---------------------------------------------------------------------------

class TestEp605Fixture:
    def test_ep605_fails_on_both_measures(self):
        script, json_path = _committed(EP605)
        report = check_transcript_files(script, json_path)
        assert not report.passed
        assert set(report.reasons) == {"opening_mismatch", "foreign_passage"}
        assert report.opening_match < 0.25, report.summary()
        assert report.longest_unmatched_run >= 50, report.summary()
        assert report.unmatched_position < 0.05, "the leak was the opening"
        assert "human message" in report.unmatched_snippet

    def test_ep604_passes(self):
        script, json_path = _committed(EP604)
        report = check_transcript_files(script, json_path)
        assert report.passed, report.summary()
        assert report.opening_match >= 0.75
        assert report.longest_unmatched_run <= 20

    def test_the_saved_tts_text_was_clean(self):
        """The defect was injected server-side: nothing we sent contained
        the leaked reasoning, so no text-side scrubber could have caught it."""
        script, _ = _committed(EP605)
        assert "input has line breaks" not in script
        assert script.lstrip().startswith("Tesla's forty-six eighty battery")


# ---------------------------------------------------------------------------
# Whisper artifacts must never fail the gate
# ---------------------------------------------------------------------------

class TestWhisperArtifactFilters:
    def test_hallucinated_segment_is_dropped(self):
        """M&A Ep140: 70 words inside a 2.3 s segment over audio Whisper
        could not decode. Real speech runs 2-3.5 words/s."""
        script, json_path = _committed(MA_EP140)
        report = check_transcript_files(script, json_path)
        assert report.passed, report.summary()
        assert report.segments_dropped >= 1

    def test_repetition_loop_is_collapsed(self):
        """MIT Ep162: "S&P-S&P-S&P-…" forty times at a segment boundary
        where the audio says "the S&P 500 closed at"."""
        script, json_path = _committed(MIT_EP162)
        report = check_transcript_files(script, json_path)
        assert report.passed, report.summary()
        assert report.loops_collapsed >= 1
        assert report.longest_unmatched_run < DEFAULT_MAX_UNMATCHED_RUN

    def test_hard_foreign_names_pass(self):
        """Offshore North's debut is full of French place names Whisper
        garbles; matched words between them keep the runs short."""
        script, json_path = _committed(ON_EP001)
        report = check_transcript_files(script, json_path)
        assert report.passed, report.summary()

    def test_filter_segments_rate(self):
        segs = [
            {"start": 0.0, "end": 10.0, "text": "twenty five ordinary words " * 5},
            {"start": 10.0, "end": 12.0, "text": "junk " * 70},
        ]
        words, dropped = filter_segments(segs)
        assert dropped == 1
        assert "junk" not in words

    def test_collapse_loops_unigram_bigram_trigram(self):
        words = "the s p s p s p s p s p 500 closed".split()
        out, n = collapse_loops(words)
        assert out == "the s p 500 closed".split()
        assert n == 1
        out, n = collapse_loops("go go go go go now".split())
        assert out == ["go", "now"] and n == 1
        # Three repeats is normal prose ("no, no, no") and is left alone.
        out, n = collapse_loops("no no no way".split())
        assert out == "no no no way".split() and n == 0


# ---------------------------------------------------------------------------
# Synthetic shapes
# ---------------------------------------------------------------------------

class TestSyntheticShapes:
    SCRIPT = (
        "Tesla's forty-six eighty battery improvements could lift output rates "
        "for vehicles and Megapacks at the same time. This is Tesla Shorts Time, "
        "episode six hundred five. Tesla improved its forty-six eighty batteries. "
        "Teslarati reports the refinements target higher output rates. Yield and "
        "consistency gains matter more than headline density for throughput and "
        "cost. Structural pack integration lets cell-level changes reduce parts "
        "and labor hours. Battery cell chemistry improvements rarely arrive in "
        "isolation. When Tesla refines the format the change ripples through "
        "every downstream process that depends on those cells. The real "
        "constraint is not the headline energy density number but how quickly "
        "the new cells can be produced at acceptable yield and cost. Yield "
        "improvements directly affect how many usable cells leave the line each "
        "week which in turn sets the pace for both vehicle production and "
        "Megapack output. Conventional lines treat cell manufacturing as a "
        "separate business from pack integration and final assembly."
    )

    def test_clean_read_passes_with_whisper_digits(self):
        spoken = self.SCRIPT.replace("forty-six eighty", "4680").replace(
            "six hundred five", "605",
        )
        report = check_spoken_text(self.SCRIPT, segments=_segments_from_text(spoken))
        assert report.passed, report.summary()

    def test_leaked_reasoning_at_the_opening_fails(self):
        spoken = LEAK + " " + self.SCRIPT.split("headline density", 1)[1]
        report = check_spoken_text(self.SCRIPT, segments=_segments_from_text(spoken))
        assert not report.passed
        assert "opening_mismatch" in report.reasons
        assert "foreign_passage" in report.reasons

    def test_leaked_reasoning_mid_episode_fails(self):
        head, tail = self.SCRIPT.split("Battery cell chemistry", 1)
        spoken = head + LEAK + " Battery cell chemistry" + tail
        report = check_spoken_text(self.SCRIPT, segments=_segments_from_text(spoken))
        assert not report.passed
        assert report.reasons == ("foreign_passage",)
        assert 0.2 < report.unmatched_position < 0.6

    def test_plain_transcript_text_fallback(self):
        report = check_spoken_text(self.SCRIPT, transcript_text=self.SCRIPT)
        assert report.passed and report.opening_match == 1.0

    def test_missing_audio_words_are_not_a_foreign_passage(self):
        """A dropped sentence is a coverage problem, not injected material:
        the run measure counts SPOKEN words absent from the script."""
        spoken = self.SCRIPT.replace(
            "Battery cell chemistry improvements rarely arrive in isolation. ", "",
        )
        report = check_spoken_text(self.SCRIPT, segments=_segments_from_text(spoken))
        assert report.passed, report.summary()

    def test_empty_inputs_fail_closed(self):
        assert "empty_transcript" in check_spoken_text(self.SCRIPT, segments=[]).reasons
        assert "empty_script" in check_spoken_text("", transcript_text="hello").reasons

    def test_normalize_strips_tags_and_case(self):
        assert normalize_words("<fast>Hello, [pause] World!</fast>") == ["hello", "world"]


# ---------------------------------------------------------------------------
# Calibration: a FIXED window of committed English episodes
# ---------------------------------------------------------------------------

class TestCalibrationWindow:
    """Every English episode committed 2026-09-01..2026-09-14 passes
    except Ep605. The window is fixed on purpose: a future shipped defect
    must be caught by the gate at run time, not by this test failing on
    an unrelated PR — and a threshold change that re-fails a healthy
    episode in this window is a regression."""

    RU_SHOWS = {"finansy_prosto", "privet_russian"}

    def _pairs(self):
        for tts_path in sorted(DIGESTS.glob("*/*_tts.txt")):
            m = re.search(r"_(\d{8})_tts\.txt$", tts_path.name)
            if not m or not ("20260901" <= m.group(1) <= "20260914"):
                continue
            if tts_path.parent.name in self.RU_SHOWS:
                continue
            json_path = tts_path.with_name(tts_path.name[:-8] + "_transcript.json")
            if json_path.exists():
                yield tts_path, json_path

    def test_window_fails_only_ep605(self):
        pairs = list(self._pairs())
        if len(pairs) < 50:
            pytest.skip("calibration window not committed in this checkout")
        failures = []
        for tts_path, json_path in pairs:
            report = check_transcript_files(tts_path.read_text(encoding="utf-8"), json_path)
            if not report.passed:
                failures.append((tts_path.name, report.summary()))
        assert [f for f, _ in failures] == ["Tesla_Shorts_Time_Pod_Ep605_20260914_tts.txt"], failures


# ---------------------------------------------------------------------------
# Mode resolution + config
# ---------------------------------------------------------------------------

class TestModeAndConfig:
    def test_resolve_mode(self):
        assert resolve_gate_mode("enforce", "en") == "enforce"
        assert resolve_gate_mode("enforce", "ru") == "shadow"
        assert resolve_gate_mode("shadow", "en") == "shadow"
        assert resolve_gate_mode("off", "ru") == "off"
        assert resolve_gate_mode("bogus", "en") == "shadow"

    def test_defaults_enforce_and_thresholds_match_module(self):
        from engine.config import load_config
        cfg = load_config(ROOT / "shows" / "tesla.yaml")
        assert cfg.tts.spoken_text_gate == "enforce"
        assert cfg.tts.spoken_text_gate_retries == 1
        assert cfg.tts.spoken_text_gate_min_opening_match == DEFAULT_MIN_OPENING_MATCH
        assert cfg.tts.spoken_text_gate_max_unmatched_run == DEFAULT_MAX_UNMATCHED_RUN

    @pytest.mark.parametrize("slug", ["finansy_prosto", "privet_russian"])
    def test_russian_shows_pin_shadow(self, slug):
        from engine.config import load_config
        cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
        assert cfg.tts.spoken_text_gate == "shadow"

    def test_every_run_show_english_show_enforces(self):
        from engine.config import load_config
        import yaml
        for path in sorted((ROOT / "shows").glob("*.yaml")):
            if path.name.startswith("_") or path.name in ("network_meta.yaml", "nerra_voices.yaml"):
                continue
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not raw.get("name"):
                continue
            cfg = load_config(path)
            if (cfg.tts.language_code or "en").lower().startswith("ru"):
                continue
            assert cfg.tts.spoken_text_gate == "enforce", path.name


# ---------------------------------------------------------------------------
# Runner wiring + Grok text_normalization plumbing
# ---------------------------------------------------------------------------

class TestRunnerWiring:
    def test_gate_sits_between_transcript_and_mix(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        i_synth_def = src.index("def _synthesize_raw_mp3()")
        i_synth_call = src.index("\n                _synthesize_raw_mp3()\n")
        i_transcribe = src.index("_transcript_result = _transcribe_raw()")
        i_gate = src.index("from engine.spoken_text_gate import")
        i_retry = src.index("_synthesize_raw_mp3()\n", i_gate)
        i_skip = src.index('_skip_episode(\n                        "spoken_text_gate"')
        i_mix = src.index("# 10. Audio mixing")
        assert i_synth_def < i_synth_call < i_transcribe < i_gate < i_retry < i_skip < i_mix
        assert 'metrics.record("spoken_text_gate", _gate_outcome)' in src
        assert "record_tts_usage(\n                            tracker" in src, (
            "the re-synthesis must be costed like the first pass"
        )

    def test_grok_text_normalization_flag(self):
        assert tts.grok_text_normalization_flag("on") is True
        assert tts.grok_text_normalization_flag("auto") is True
        assert tts.grok_text_normalization_flag("") is True
        assert tts.grok_text_normalization_flag("off") is False
        assert tts.grok_text_normalization_flag("OFF ") is False

    @pytest.mark.parametrize("setting, expected", [("on", True), ("off", False)])
    def test_synthesize_forwards_normalization_to_grok(self, tmp_path, monkeypatch, setting, expected):
        """Before Sep 14 2026 ``apply_text_normalization`` reached only the
        ElevenLabs path; the Grok request was hard-wired ``True``."""
        seen: list[dict] = []

        def fake_chunk(text, voice_id, out_path, **kwargs):
            seen.append(kwargs)
            Path(out_path).write_bytes(b"\xff\xfb\x90")

        monkeypatch.setattr(tts, "grok_speak_chunk", fake_chunk)
        monkeypatch.setattr(tts.subprocess, "run", lambda *a, **kw: MagicMock(returncode=0))
        tts.synthesize(
            "A short script.", "kdif6sqjcyiq", tmp_path / "o.mp3",
            api_key="k", provider="grok", apply_text_normalization=setting,
        )
        assert len(seen) == 1
        assert seen[0]["text_normalization"] is expected

    def test_default_request_is_byte_identical(self, tmp_path, monkeypatch):
        seen: list[dict] = []

        def fake_chunk(text, voice_id, out_path, **kwargs):
            seen.append(kwargs)
            Path(out_path).write_bytes(b"\xff\xfb\x90")

        monkeypatch.setattr(tts, "grok_speak_chunk", fake_chunk)
        monkeypatch.setattr(tts.subprocess, "run", lambda *a, **kw: MagicMock(returncode=0))
        tts.synthesize("A short script.", "kdif6sqjcyiq", tmp_path / "o.mp3",
                       api_key="k", provider="grok")
        assert seen[0]["text_normalization"] is True


class TestAuditScript:
    def test_audit_script_exists_and_imports_the_gate(self):
        src = (ROOT / "scripts" / "audit_spoken_text.py").read_text(encoding="utf-8")
        assert "from engine.spoken_text_gate import check_transcript_files" in src
