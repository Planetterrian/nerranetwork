"""Spoken-open shape (Sep 22 2026) — staged on tesla / spacex / FF.

The digest **HOOK:** line is read aloud word for word as the episode's
first sentence. Opens measured 14-32 words with no digit in 10 of 15 and
6 of 15 over the prompts' own 120-character ask, and nothing in code
checked either. The shape lives in one shared snippet (shape only, no
quotable specimen), the ceiling in engine.titles, and the gate in
run_show's structural regeneration. Landmine #17: A/B-listen.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNIPPET = ROOT / "shows" / "prompts" / "_shared" / "hook_shape.txt"
ARM = ("tesla", "spacex", "fascinating_frontiers")
INCLUDE = "<<include: _shared/hook_shape.txt>>"


class TestSnippet:
    def test_shape_only_no_specimen(self):
        text = SNIPPET.read_text(encoding="utf-8")
        assert '"' not in text and "“" not in text
        assert not re.search(r"\d", text), "a number is a quotable specimen"
        assert "{" not in text and "}" not in text
        assert not re.search(r"^\s*[A-Z]+:\s", text, re.M), "no speaker label"
        assert "WEAK" not in text and "STRONG" not in text
        low = text.lower()
        for phrase in ("one sentence", "twenty words", "first ten words",
                       "same sentence", "not a question", "no source name"):
            assert phrase in low, phrase

    def test_snippet_renders_through_the_include_mechanism(self):
        from engine.generator import load_prompt
        for slug in ARM:
            rendered = load_prompt(f"shows/prompts/{slug}_digest.txt")
            assert "<<include" not in rendered
            assert "HOOK SHAPE" in rendered
            assert rendered.index("**HOOK:**") < rendered.index("HOOK SHAPE")


class TestArmPrompts:
    def test_included_in_exactly_the_three_arm_prompts(self):
        with_it = sorted(
            p.name for p in (ROOT / "shows" / "prompts").glob("*_digest.txt")
            if INCLUDE in p.read_text(encoding="utf-8"))
        assert with_it == sorted(f"{s}_digest.txt" for s in ARM)

    def test_specimen_hooks_are_gone_from_the_arm(self):
        for slug in ARM:
            text = (ROOT / "shows" / "prompts" / f"{slug}_digest.txt").read_text(encoding="utf-8")
            hook_block = text[text.index("**HOOK:**"):text.index("**HOOK:**") + 900]
            assert "WEAK" not in hook_block and "STRONG" not in hook_block, slug
            assert "vs STRONG" not in text, slug


class TestCeilingAndGate:
    def test_one_owner_of_the_limit(self):
        from engine.titles import SPOKEN_HOOK_MAX_CHARS
        assert SPOKEN_HOOK_MAX_CHARS == 150
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "from engine.titles import SPOKEN_HOOK_MAX_CHARS" in src
        assert "150" not in src[src.index("_hook_too_long = "):src.index("_hook_too_long = ") + 200]

    def test_gate_regenerates_never_truncates(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "if (_val_factory or _hook_too_long) and not is_deep_dive:" in src
        assert "over the {_HOOK_MAX} spoken ceiling" in src
        assert 'metrics.record("digest_hook_over_length", len(_hook_now))' in src
        # The retry is accepted only when its hook fits; the original is
        # never sliced.
        assert "and (not _hook_too_long or len(_retry_hook) <= _HOOK_MAX)" in src
        gate = src[src.index("_hook_too_long = "):src.index("hook = _extract_hook(x_thread)")]
        assert "[:_HOOK_MAX]" not in gate and "clip_words(" not in gate


class TestColdOpenBullet:
    def test_first_sentence_shape_is_stated_without_a_specimen(self):
        from engine.intros import _COLD_OPEN_BANNED, build_cold_open_spec
        spec = build_cold_open_spec("tesla")
        assert "THE FIRST SENTENCE HAS A SHAPE" in spec
        assert "twenty words" in spec and "first ten" in spec
        for q in re.findall(r'"([^"]+)"', spec):
            assert q.lower() in _COLD_OPEN_BANNED
        assert spec.index("HAS A SHAPE") < spec.index("ONLY AFTER the cold open")
