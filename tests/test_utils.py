"""
Unit tests for the pure utility functions in engine/.

Tests cover:
  - number_to_words()      (engine.utils)
  - calculate_similarity()  (engine.utils)
  - remove_similar_items()  (engine.utils)

Pronunciation tests for the shared module live in test_pronunciation.py.
"""

import re
from pathlib import Path

import pytest

from engine.utils import number_to_words as tesla_number_to_words
from engine.utils import number_to_words as omni_number_to_words
from engine.utils import calculate_similarity as tesla_calculate_similarity
from engine.utils import remove_similar_items as tesla_remove_similar_items
from engine.utils import remove_similar_items as omni_remove_similar_items


# ===================================================================
# TEST: number_to_words
# ===================================================================

class TestNumberToWords:
    """Tests for number_to_words() — the Tesla version."""

    @pytest.mark.parametrize("num, expected", [
        (0, "zero"),
        (1, "one"),
        (42, "forty-two"),
        (100, "one hundred"),
        (999, "nine hundred ninety-nine"),
        (1000, "one thousand"),
        (12345, "twelve thousand three hundred forty-five"),
    ])
    def test_integers(self, num, expected):
        assert tesla_number_to_words(num) == expected

    def test_million_returns_string(self):
        # >= 1_000_000 falls through to str(integer_part)
        result = tesla_number_to_words(1_000_000)
        assert result == "1000000"

    def test_negative(self):
        result = tesla_number_to_words(-7)
        assert result == "negative seven"

    def test_decimal_point_one_seven(self):
        result = tesla_number_to_words(0.17)
        assert "point" in result
        assert "one" in result
        assert "seven" in result

    def test_decimal_pi(self):
        result = tesla_number_to_words(3.14)
        assert result.startswith("three point")
        assert "one" in result
        assert "four" in result

    def test_negative_decimal(self):
        result = tesla_number_to_words(-3.14)
        assert result.startswith("negative three point")

    def test_zero_decimal_no_point(self):
        # Pure integer should not contain "point"
        assert "point" not in tesla_number_to_words(42)

    @pytest.mark.parametrize("num, expected", [
        (0, "zero"),
        (1, "one"),
        (42, "forty-two"),
        (100, "one hundred"),
        (999, "nine hundred ninety-nine"),
        (1000, "one thousand"),
        (12345, "twelve thousand three hundred forty-five"),
    ])
    def test_omni_integers_match_tesla(self, num, expected):
        """The two scripts' number_to_words should agree on integers."""
        assert omni_number_to_words(num) == expected


# ===================================================================
# ===================================================================
# TEST: calculate_similarity
# ===================================================================

class TestCalculateSimilarity:

    def test_identical_strings(self):
        assert tesla_calculate_similarity("hello world", "hello world") == 1.0

    def test_empty_strings(self):
        assert tesla_calculate_similarity("", "anything") == 0.0
        assert tesla_calculate_similarity("anything", "") == 0.0

    def test_both_empty(self):
        assert tesla_calculate_similarity("", "") == 0.0

    def test_none_inputs(self):
        assert tesla_calculate_similarity(None, "text") == 0.0
        assert tesla_calculate_similarity("text", None) == 0.0

    def test_similar_strings_high_ratio(self):
        s1 = "Tesla stock surged 3.5% today on FSD news"
        s2 = "Tesla stock surged 3.5% today on FSD update"
        ratio = tesla_calculate_similarity(s1, s2)
        assert ratio > 0.8

    def test_dissimilar_strings_low_ratio(self):
        s1 = "Tesla stock surged today"
        s2 = "NASA launched a new satellite"
        ratio = tesla_calculate_similarity(s1, s2)
        assert ratio < 0.4

    def test_case_insensitive(self):
        """Similarity normalizes to lowercase."""
        assert tesla_calculate_similarity("HELLO", "hello") == 1.0

    def test_whitespace_normalized(self):
        """Extra whitespace is collapsed."""
        assert tesla_calculate_similarity("hello  world", "hello world") == 1.0


# ===================================================================
# TEST: remove_similar_items
# ===================================================================

class TestRemoveSimilarItems:

    def test_empty_list(self):
        result = tesla_remove_similar_items([])
        assert result == [] or result is None or result == []  # tesla returns items, omni returns []

    def test_no_duplicates(self):
        items = [
            {"title": "Tesla launches new Model 3"},
            {"title": "NASA discovers new exoplanet"},
            {"title": "Federal Reserve raises interest rates"},
        ]
        result = tesla_remove_similar_items(items)
        assert len(result) == 3

    def test_near_duplicates_removed(self):
        items = [
            {"title": "Tesla stock surges 5% on FSD news"},
            {"title": "Tesla stock surges 5% on FSD update"},  # near-dup
            {"title": "NASA announces Mars mission timeline"},
        ]
        result = tesla_remove_similar_items(items)
        assert len(result) == 2
        # First occurrence kept, near-duplicate removed
        assert result[0]["title"] == "Tesla stock surges 5% on FSD news"
        assert result[1]["title"] == "NASA announces Mars mission timeline"

    def test_custom_threshold(self):
        items = [
            {"title": "Tesla stock up 5%"},
            {"title": "Tesla stock up 6%"},
        ]
        # With a very high threshold, both should survive
        result = tesla_remove_similar_items(items, similarity_threshold=0.99)
        assert len(result) == 2
        # With a low threshold, only the first survives
        result = tesla_remove_similar_items(items, similarity_threshold=0.5)
        assert len(result) == 1

    def test_custom_get_text_func(self):
        items = [
            {"headline": "Breaking: Tesla FSD v13"},
            {"headline": "Breaking: Tesla FSD v13 released"},
        ]
        result = tesla_remove_similar_items(
            items,
            get_text_func=lambda x: x["headline"],
        )
        assert len(result) == 1

    def test_string_items(self):
        items = [
            "Tesla stock surges on FSD news",
            "Tesla stock surges on FSD update",
            "NASA mission update",
        ]
        result = tesla_remove_similar_items(items)
        assert len(result) == 2

    def test_skips_empty_text(self):
        """Items with empty text are skipped (tesla version)."""
        items = [
            {"title": ""},
            {"title": "Real headline"},
        ]
        result = tesla_remove_similar_items(items)
        assert len(result) == 1
        assert result[0]["title"] == "Real headline"

    def test_omni_version_basic(self):
        """Omni View version uses slightly different key lookup."""
        items = [
            {"title": "Federal Reserve holds rates"},
            {"title": "Federal Reserve holds rates steady"},
            {"content": "Completely different story about sports"},
        ]
        result = omni_remove_similar_items(items)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# strip_speech_tags — Grok TTS speech-tag scrubber for non-TTS consumers
# ---------------------------------------------------------------------------

class TestStripSpeechTags:
    """Speech tags must never reach blog/RSS/X — only the TTS engine sees them."""

    def setup_method(self):
        from engine.utils import strip_speech_tags
        self._strip = strip_speech_tags

    def test_strips_inline_breath_tag(self):
        out = self._strip("Sentence one. [breath] Sentence two.")
        assert "[breath]" not in out
        assert "Sentence one. Sentence two." == out

    def test_strips_inline_pause_and_long_pause(self):
        out = self._strip("Section A. [pause] Section B. [long-pause] Section C.")
        assert "[pause]" not in out
        assert "[long-pause]" not in out
        assert out == "Section A. Section B. Section C."

    def test_strips_all_documented_inline_tags(self):
        """All Grok TTS inline tags must be removed."""
        text = (
            "[pause][long-pause][laugh][cry][sniff][kiss]"
            "[throat-clear][breath][sigh][gasp]"
        )
        assert self._strip(text) == ""

    def test_case_insensitive_stripping(self):
        assert self._strip("Hi [BREATH] world.") == "Hi world."
        assert self._strip("Hi [Pause] world.") == "Hi world."

    def test_strips_emphasis_open_and_close_keeps_inner_text(self):
        """Wrapping tags drop the brackets but preserve the prose."""
        out = self._strip("This is <emphasis>critical</emphasis>.")
        assert out == "This is critical."

    def test_strips_whisper_brackets(self):
        out = self._strip("She said <whisper>be quiet</whisper> firmly.")
        assert out == "She said be quiet firmly."

    def test_strips_all_documented_wrapping_tags(self):
        text = (
            "<soft>a</soft><loud>b</loud><whisper>c</whisper>"
            "<slow>d</slow><fast>e</fast><high>f</high><low>g</low>"
            "<singing>h</singing><emphasis>i</emphasis>"
        )
        assert self._strip(text) == "abcdefghi"

    def test_strips_build_intensity_wrap(self):
        """The May-2026 chunk wrap (``<fast><build-intensity>...</...></...>``)
        must strip cleanly even though it normally never appears in the
        non-TTS surfaces — defense-in-depth in case a future code path
        leaks it. ``build-intensity`` was added to ``_WRAPPING_TAGS``
        alongside the other documented wrapping tags."""
        out = self._strip(
            "<fast><build-intensity>Hello world.</build-intensity></fast>"
        )
        assert out == "Hello world."

    def test_idempotent(self):
        text = "[breath] Hello, <emphasis>world</emphasis>."
        once = self._strip(text)
        twice = self._strip(once)
        assert once == twice

    def test_empty_and_none(self):
        assert self._strip("") == ""
        assert self._strip(None) is None  # type: ignore[arg-type]

    def test_collapses_double_space_left_by_inline_tag(self):
        """Removing `[breath]` between two spaces shouldn't leave a double space."""
        out = self._strip("Word one [breath] word two.")
        assert "  " not in out
        assert out == "Word one word two."

    def test_preserves_unrelated_brackets(self):
        """Brackets not matching a known tag must survive (e.g. citations)."""
        out = self._strip("Per [Smith 2024], the data shows growth.")
        assert "[Smith 2024]" in out

    def test_preserves_unrelated_html_like_tags(self):
        """Wrapping tags outside the speech-tag whitelist are preserved
        (the strip is conservative — false positives would mangle prose)."""
        out = self._strip("She wrote <em>important</em> things.")
        assert "<em>" in out and "</em>" in out

    def test_real_world_podcast_excerpt(self):
        text = (
            "Welcome to Tesla Shorts Time. [breath] Today, "
            "<emphasis>three</emphasis> stories rocked the EV world. "
            "[pause] Let's get into it."
        )
        out = self._strip(text)
        assert "[breath]" not in out
        assert "[pause]" not in out
        assert "<emphasis>" not in out and "</emphasis>" not in out
        assert "three" in out  # inner text preserved
        assert "Let's get into it." in out


# ---------------------------------------------------------------------------
# drop_excluded_titles — almanac / evergreen content filter
# ---------------------------------------------------------------------------

from engine.utils import drop_excluded_titles as _drop_excluded_titles


class TestDropExcludedTitles:
    """Suppress recurring almanac/evergreen titles (FF Ep087 shipped 12 as
    100%-identical cross-episode repeats). Must drop the recurring content
    while never touching real news."""

    def test_no_patterns_is_noop(self):
        arts = [{"title": "Anything goes"}]
        kept, dropped = _drop_excluded_titles(arts, [])
        assert dropped == 0 and kept == arts

    def test_empty_articles(self):
        assert _drop_excluded_titles([], ["x"]) == ([], 0)

    def test_drops_real_ff_almanac_titles(self):
        pats = [
            r"full moon calendar", r"(moon|lunar) calendar",
            r"this day in (space )?history", r"on \w+ \d{1,2},? 1[89]\d{2}",
            r"evening skies?\b", r"highest point in (the )?(evening|morning) sky",
            r"(super|blue|strawberry|blood)\s+moon\b",
            r"best (telescopes?|binoculars?)\b",
        ]
        almanac = [
            "Full Moon Calendar Lists All 2026 Dates and Phases",
            "Venus Jupiter and Mercury Shine in June Evening Skies",
            "Lick Observatory Ownership Transfers on June 1 1888",
            "May Blue Moon Appears Smallest of 2026 in Global Photos",
            "Mercury Reaches Highest Point in Evening Sky for 2026",
            "The Best Telescopes for Beginners in 2026",
        ]
        kept, dropped = _drop_excluded_titles([{"title": t} for t in almanac], pats)
        assert dropped == len(almanac) and kept == []

    def test_keeps_real_news(self):
        pats = [r"full moon calendar", r"evening skies?\b", r"(blue|super)\s+moon\b"]
        news = [
            "Giant Star Likely Destroyed in Rare Pair-Instability Supernova",
            "China Launches Long March 12B on Unannounced Maiden Flight",
            "Young Exoplanets Found With Longest Known Orbital Periods",
        ]
        arts = [{"title": t} for t in news]
        kept, dropped = _drop_excluded_titles(arts, pats)
        assert dropped == 0 and kept == arts

    def test_case_insensitive(self):
        kept, dropped = _drop_excluded_titles(
            [{"title": "FULL MOON CALENDAR for the year"}], [r"full moon calendar"]
        )
        assert dropped == 1 and kept == []

    def test_invalid_pattern_is_skipped_not_raised(self):
        # A bad regex must not crash the fetch.
        kept, dropped = _drop_excluded_titles(
            [{"title": "Real news story"}], [r"(unclosed"]
        )
        assert dropped == 0 and len(kept) == 1


def test_ff_yaml_exclude_patterns_filter_almanac_keep_news():
    """End-to-end: the patterns committed in fascinating_frontiers.yaml drop
    the recurring almanac titles and keep real news."""
    from engine.config import load_config

    cfg = load_config("shows/fascinating_frontiers.yaml")
    assert cfg.exclude_title_patterns, "FF must declare exclude_title_patterns"
    almanac = [
        "Full Moon Calendar Lists All 2026 Dates and Phases",
        "Venus Jupiter and Mercury Shine in June Evening Skies",
        "Lick Observatory Ownership Transfers on June 1 1888",
        "Mercury Reaches Highest Point in Evening Sky for 2026",
    ]
    news = [
        "Giant Star Likely Destroyed in Rare Pair-Instability Supernova",
        "Webb Telescope Reveals Water Vapor on Distant Exoplanet",
    ]
    kept, dropped = _drop_excluded_titles(
        [{"title": t} for t in almanac + news], cfg.exclude_title_patterns
    )
    kept_titles = {a["title"] for a in kept}
    assert dropped == len(almanac)
    assert all(t in kept_titles for t in news)
