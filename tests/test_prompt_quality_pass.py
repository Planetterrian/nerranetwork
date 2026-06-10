"""Drift guards for the June 10 2026 Grok prompt + voice review
(docs/prompt_review_2026_06_10.md)."""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


class TestPhoneticGarbleRepair:
    def test_known_garbles_repaired(self):
        from engine.utils import fix_phonetic_garbles
        out = fix_phonetic_garbles(
            "Posted on the nassa site; Chwen 3 and en-vidia beat nay-toe "
            "estimates, says open-ay-eye and Star-mer."
        )
        assert "NASA" in out and "Qwen 3" in out and "Nvidia" in out
        assert "NATO" in out and "OpenAI" in out and "Starmer" in out
        assert "nassa" not in out.lower().replace("nasa", "")

    def test_legitimate_words_untouched(self):
        from engine.utils import fix_phonetic_garbles
        text = "The star merger produced data; the chwenless token stays."
        # "star merger" must survive (why space-variants are excluded);
        # word boundaries keep substrings inside other tokens intact.
        assert fix_phonetic_garbles(text) == text

    def test_wired_into_both_pipeline_stages(self):
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert src.count("fix_phonetic_garbles(") >= 2  # digest + podcast script


class TestStaleTtsClaimsGone:
    def test_no_prompt_mentions_elevenlabs(self):
        """All shows are on Grok TTS (landmine #17); prompts claiming the
        'ElevenLabs engine' handles pronunciation were stale on all 9
        non-Tesla podcast prompts."""
        offenders = [
            f.name for f in (_ROOT / "shows" / "prompts").glob("*.txt")
            if "ElevenLabs" in f.read_text(encoding="utf-8")
        ]
        assert offenders == [], f"stale ElevenLabs claims in: {offenders}"


class TestXFetchPromptDemandsSubstance:
    def test_substantive_rule_present(self):
        """The X-post fetch returned emoji spam and slur one-liners
        (Tesla Ep505 log: 'Laughing Emojis', 'Video post') straight into
        digest prompts — the fetch prompt now requires substantive posts."""
        src = (_ROOT / "engine" / "fetcher.py").read_text(encoding="utf-8")
        assert "SUBSTANTIVE posts only" in src
