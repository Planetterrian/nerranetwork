"""Tests for the chapter-title auto-derivation introduced May 8 2026.

Operator caught (Tesla Ep465 / Ep466) chapter markers shipping as
``Introduction`` + ``Segment 2`` + ``Segment 3`` … + ``Closing``
because the per-show ``section_markers`` regex didn't match the LLM's
section openers, so the auto-segmentation fallback fired with the
original generic-numeric placeholder titles.

Apple Podcasts and Pocket Casts surface chapter titles in the player
UI; "Segment 2" tells listeners nothing about whether to skip ahead.
The new behaviour derives titles from each segment's first sentence
(truncated to ~60 chars). These tests pin both the helper and the
end-to-end fallback so a future refactor doesn't silently regress.
"""

from __future__ import annotations

import pytest

from engine.chapters import (
    Chapter,
    parse_chapters,
    _first_sentence_as_title,
)


# ---------------------------------------------------------------------------
# _first_sentence_as_title — pure-function tests
# ---------------------------------------------------------------------------


class TestFirstSentenceAsTitle:

    def test_extracts_first_sentence(self):
        text = "Tesla unveiled new robotaxi service in Texas. Followed by other news."
        assert _first_sentence_as_title(text) == "Tesla unveiled new robotaxi service in Texas"

    def test_truncates_at_word_boundary(self):
        text = "California regulators just disclosed the Tesla Semi battery sizes at 822 kWh and 548 kWh per truck."
        title = _first_sentence_as_title(text, max_chars=50)
        assert len(title) <= 50
        # Ends with ellipsis and no mid-word cut.
        assert title.endswith("…")
        assert " " not in title[-2:]  # no trailing partial word

    def test_strips_leading_markdown(self):
        text = "**Bold** intro. Tesla news here."
        # Should pick up the first sentence with the bold-strip applied.
        result = _first_sentence_as_title(text)
        assert "**" not in result
        assert "Bold intro" in result

    def test_handles_russian_text(self):
        """Russian shows (FP, PR) get the same fallback path."""
        text = "Канадский фондовый рынок открылся ростом сегодня утром. Далее обсудим причины."
        title = _first_sentence_as_title(text)
        assert title == "Канадский фондовый рынок открылся ростом сегодня утром"

    def test_returns_empty_for_blank_text(self):
        assert _first_sentence_as_title("") == ""
        assert _first_sentence_as_title("   \n\n  ") == ""

    def test_returns_empty_for_too_short_text(self):
        """Single-word fragments aren't useful chapter titles. Fall back
        to the numeric placeholder instead."""
        assert _first_sentence_as_title("Yes.") == ""
        assert _first_sentence_as_title("OK") == ""

    def test_returns_empty_for_pure_number(self):
        assert _first_sentence_as_title("420.") == ""

    def test_handles_no_sentence_terminator(self):
        """Some segments are mid-paragraph fragments without a clean .!?
        terminator. Use the whole text up to max_chars."""
        text = "Long stretch of text without any punctuation that should still produce a usable title even if no sentence end is visible"
        title = _first_sentence_as_title(text, max_chars=40)
        assert len(title) <= 40
        assert "Long stretch" in title

    def test_handles_ellipsis_terminator(self):
        text = "Wait for it… and now the punchline."
        title = _first_sentence_as_title(text)
        # Should treat ``…`` as a sentence boundary.
        assert title == "Wait for it"


# ---------------------------------------------------------------------------
# End-to-end: auto-segment fallback uses real titles
# ---------------------------------------------------------------------------


# A long script with NO matching section markers — forces the auto-
# segmentation fallback. Three paragraphs of substantial length so the
# splitter spawns at least 2-3 segments.
_LONG_SCRIPT = """\
Welcome back to Tesla Shorts Time, your daily Tesla newsfeed. Today we have
quite a lot to unpack including the new battery sizes for the Tesla Semi,
the latest from FSD beta, and a surprise from China.

Tesla unveiled new robotaxi service in three Texas cities today. The pilot
launches with a fleet of about two hundred Model Y vehicles operating in
Austin, Houston, and Dallas. Riders will hail rides through the existing
Tesla mobile app, with fares starting at three dollars per ride. This marks
a major step in Tesla's autonomous strategy and follows months of regulatory
preparation. Analysts expect the service to expand to additional cities
within ninety days if the initial rollout meets safety benchmarks.

California regulators just disclosed the Tesla Semi's battery sizes at
eight hundred twenty two kilowatt-hours and five hundred forty eight
kilowatt-hours respectively. The disclosure came as part of a routine
safety filing. The larger pack supports the long-haul variant while the
smaller pack targets regional fleets. Tesla had previously declined to
publish exact capacity numbers, citing competitive sensitivity. Industry
observers say the figures align with prior estimates from third-party
teardowns.

That wraps up today's show. Thanks for listening, and we'll see you tomorrow.
"""


def test_auto_segment_titles_derive_from_content():
    """End-to-end: with no section markers matching, the fallback fires
    AND uses real first-sentence titles instead of "Segment 2"."""
    chapters = parse_chapters(
        _LONG_SCRIPT,
        section_markers=[
            {"pattern": r"\bWelcome back\b", "title": "Introduction"},
        ],
        show_name="TestShow",
        # Force at least 3 segments so the fallback definitely fires.
        min_chapters=3,
        # Short target so even short paragraphs trip the splitter.
        auto_segment_target_seconds=10.0,
        estimated_words_per_minute=165.0,
    )

    # First chapter is the matched ``Introduction``. Subsequent chapters
    # should NOT be the legacy "Segment N" placeholder — they should
    # carry a content-derived title.
    titles = [c.title for c in chapters]
    assert titles[0] == "Introduction"
    # At least one auto-segmented chapter has a non-placeholder title.
    auto_titles = titles[1:]
    assert auto_titles, "Auto-segmentation should have produced extra chapters"
    has_real_title = any(
        not t.startswith("Segment ") and len(t) >= 10
        for t in auto_titles
    )
    assert has_real_title, (
        f"At least one auto-segment should have a content-derived title; "
        f"got {auto_titles!r}"
    )


def test_auto_segment_falls_back_to_segment_n_when_text_unusable():
    """If a segment's text is too short / unparseable, we fall back to
    the numeric placeholder so chapters always get *some* title."""
    # Construct a script where the auto-split lands on near-empty regions.
    text = "Welcome back. " + ("Yes. " * 5) + "\n\n" + ("OK. " * 5)
    chapters = parse_chapters(
        text,
        section_markers=[{"pattern": r"\bWelcome back\b", "title": "Introduction"}],
        min_chapters=3,
        auto_segment_target_seconds=1.0,
    )
    # All chapters MUST have a title — even the unusable ones get a
    # ``Segment N`` placeholder, never empty.
    for c in chapters:
        assert c.title.strip(), "Every chapter must have a non-empty title"
