"""Drift guards for the June 10 2026 Omni View quality pass
(docs/reviews/omni_view_review_2026_06_10.md) — the same review process as
the Tesla flagship pass, the four-show pass, and the env_intel pass, applied
to a show that was missed in every prior chapter / length / expand round.

Pins:
* chapter `where` positional anchors (Introduction=start, Tomorrow
  Teaser/Closing=end) — the Tesla chapter-bug class;
* the Closing chapter pattern matches BOTH closing-pool variants from
  engine.intros (the dominant "That wraps up today's Omni View…" variant
  previously matched NO pattern — 7 of the last 10 episodes shipped with
  no Closing chapter, the MAB orphan-closing bug);
* the "Understanding the Issue" pattern matches the real spoken deep-dive
  opener so the deep dive gets its own chapter AND the auto-segment
  garbage-title fallback stops firing (Ep061 shipped a chapter literally
  titled "Knowing this, when you hear claims that the system worked…");
* parse_chapters on every recent committed script produces a Closing
  chapter and no sentence-fragment chapter titles;
* the steel-man scaffolding tic is attacked at the prompt root — the
  digest no longer seeds the literal "The strongest case for X rests on…"
  lead-in (it shipped 12-20× per episode), the anonymous "one side / the
  other side / advocates on each side" frame is banned in both prompts,
  and the prompt caps "the strongest case" at once;
* one unified podcast length target (the prompt had demanded "8-12
  minutes", "at least 2000 words", and "40+ sentences" at once) plus the
  podcast_expand_below_target opt-in the June network pass missed.
"""

from __future__ import annotations

import re
import sys
import glob
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.intros import _SHOW_PERSONALITIES  # noqa: E402

_YAML = _ROOT / "shows/omni_view.yaml"
_DIGEST_PROMPT = _ROOT / "shows/prompts/omni_view_digest.txt"
_PODCAST_PROMPT = _ROOT / "shows/prompts/omni_view_podcast.txt"


def _cfg():
    return yaml.safe_load(_YAML.read_text(encoding="utf-8"))


def _markers():
    return {m["title"]: m for m in _cfg()["chapters"]["section_markers"]}


# ---------------------------------------------------------------------------
# Chapter positional anchors + pattern coverage
# ---------------------------------------------------------------------------

class TestChapterAnchors:
    def test_introduction_anchored_to_start(self):
        assert _markers()["Introduction"].get("where") == "start"

    def test_teaser_and_closing_anchored_to_end(self):
        by = _markers()
        assert by["Closing"].get("where") == "end"
        assert by["Tomorrow Teaser"].get("where") == "end"

    def test_closing_pattern_matches_both_closing_pool_variants(self):
        regex = re.compile(_markers()["Closing"]["pattern"], re.IGNORECASE)
        closings = _SHOW_PERSONALITIES["omni_view"]["closings"]
        assert closings, "omni_view must have closing-pool variants"
        for closing in closings:
            assert regex.search(closing), (
                f"Closing chapter pattern does not match closing-pool "
                f"variant: {closing[:80]!r}"
            )

    def test_deep_dive_pattern_matches_real_openers(self):
        regex = re.compile(_markers()["Understanding the Issue"]["pattern"],
                           re.IGNORECASE)
        # The actual spoken deep-dive openers seen across Ep069-077.
        for opener in (
            "Now, to really understand this story, there is something most coverage leaves out.",
            "Now, to really understand the tariff proposal, there is an administrative sequence most headlines leave out.",
            "To understand the defence spending announcement more fully, most coverage treats it as simple.",
            "To understand the Hormuz situation more fully, the picture is layered.",
        ):
            assert regex.search(opener), f"deep-dive pattern missed: {opener!r}"


class TestRealScriptChapters:
    """parse_chapters on every recent committed _tts.txt must produce a
    Closing chapter and no sentence-fragment garbage titles."""

    def _scripts(self):
        files = sorted(glob.glob(str(_ROOT / "digests/omni_view/Omni_View_Ep*_tts.txt")))
        # Skip the weekly-recap episodes (different structure, no deep dive).
        return files[-10:]

    def test_every_recent_script_gets_a_closing_chapter(self):
        from engine.config import load_config
        from engine.chapters import parse_chapters
        import logging
        logging.disable(logging.CRITICAL)
        markers = load_config(str(_YAML)).chapters.section_markers
        scripts = self._scripts()
        assert scripts, "expected recent omni_view scripts on disk"
        missing = []
        for f in scripts:
            script = Path(f).read_text(encoding="utf-8")
            titles = [c.title for c in parse_chapters(script, markers, show_name="Omni View")]
            if "Closing" not in titles:
                missing.append(Path(f).name)
        assert not missing, f"episodes missing a Closing chapter: {missing}"

    def test_no_garbage_sentence_fragment_chapter_titles(self):
        from engine.config import load_config
        from engine.chapters import parse_chapters
        import logging
        logging.disable(logging.CRITICAL)
        markers = load_config(str(_YAML)).chapters.section_markers
        bad = []
        for f in self._scripts():
            script = Path(f).read_text(encoding="utf-8")
            for c in parse_chapters(script, markers, show_name="Omni View"):
                # Garbage titles are raw deep-dive sentences: long and/or
                # ending in an ellipsis (the auto-segment fallback's
                # first-sentence truncation).
                if c.title.endswith("…") or len(c.title) > 45:
                    bad.append((Path(f).name, c.title))
        assert not bad, f"garbage sentence-fragment chapter titles: {bad}"


# ---------------------------------------------------------------------------
# Steel-man scaffolding tic (prompt root cause)
# ---------------------------------------------------------------------------

class TestSteelManTemplate:
    def test_digest_does_not_seed_the_canonical_strongest_case_lead_in(self):
        # The prompt used to PRESCRIBE the literal lead-in
        #   Lead each with its best supporting reason ("The strongest case
        #   for X rests on [specific value / mechanism / evidence]…")
        # which shipped 5-7×/digest → 12-20×/podcast. The phrase may now
        # appear ONLY inside the instruction that bans over-using it, never
        # as the prescribed lead-in template.
        text = _DIGEST_PROMPT.read_text(encoding="utf-8")
        assert 'best supporting reason ("The strongest case' not in text
        assert '[specific value / mechanism / evidence]' not in text

    def test_digest_caps_strongest_case_and_bans_anonymous_sides(self):
        text = _DIGEST_PROMPT.read_text(encoding="utf-8").lower()
        assert "at most once" in text
        assert "one side" in text and "the other side" in text  # named as banned

    def test_podcast_bans_the_one_side_frames_template(self):
        text = _PODCAST_PROMPT.read_text(encoding="utf-8").lower()
        assert "one side frames" in text  # mentioned only to ban it
        assert "advocates on each side" in text
        assert "banned" in text


# ---------------------------------------------------------------------------
# Unified length target + expansion opt-in
# ---------------------------------------------------------------------------

class TestLengthTarget:
    def test_podcast_prompt_has_no_contradictory_length_claims(self):
        text = _PODCAST_PROMPT.read_text(encoding="utf-8")
        assert "8–12 minute" not in text and "8-12 minute" not in text
        assert "at least 2000 words" not in text
        assert "1,700" in text  # the unified target

    def test_yaml_opts_into_expansion_and_raises_floor(self):
        llm = _cfg()["llm"]
        assert llm.get("podcast_expand_below_target") is True
        assert llm.get("min_podcast_words", 0) >= 1200
