"""Tests for engine.generator post-processing helpers added during the
TST Ep465 audit (May 6 2026).

Two LLM-output cleanup helpers covered here:

  1. ``_strip_hallucinated_timestamps`` — Tesla's grok-4.3 occasionally
     pads every Top-N headline with an invented "publication" timestamp
     like "May 06, 2026, 9:04 AM PDT". 11 of these landed in TST Ep465
     and the repetition guard couldn't shake them on retry.
  2. Speaker-prefix strip in ``_sanitize_podcast_script`` — same episode
     had "Patrick: Tesla..." opening 5 paragraphs. The TTS would say
     the host name out loud as a literal speaker tag.
"""

from __future__ import annotations

import re

import pytest


# ---------------------------------------------------------------------------
# _strip_hallucinated_timestamps
# ---------------------------------------------------------------------------

class TestStripHallucinatedTimestamps:

    def test_strips_pdt_stamp_from_numbered_headline(self):
        from engine.generator import _strip_hallucinated_timestamps
        text = (
            "1. Tesla Semi Incentives Available Across Multiple "
            "States: May 06, 2026, 9:04 AM PDT\n"
            "2. Tesla and bk World Open New Supercharger Lounge Near "
            "Lyon: May 06, 2026, 9:04 AM PDT"
        )
        out = _strip_hallucinated_timestamps(text)
        assert "May 06, 2026" not in out
        assert "AM PDT" not in out
        assert "Tesla Semi Incentives Available Across Multiple States" in out
        assert "Tesla and bk World Open New Supercharger Lounge Near Lyon" in out

    def test_strips_bullet_headlines_too(self):
        from engine.generator import _strip_hallucinated_timestamps
        text = (
            "- Tesla announces Q4 results — May 06, 2026, 9:04 AM PDT\n"
            "* Tesla recall affects 200K vehicles: May 6, 2026"
        )
        out = _strip_hallucinated_timestamps(text)
        assert "9:04 AM PDT" not in out
        assert "May 6, 2026" not in out
        assert "Tesla announces Q4 results" in out
        assert "Tesla recall affects 200K vehicles" in out

    def test_strips_bold_headlines(self):
        from engine.generator import _strip_hallucinated_timestamps
        text = "**Tesla announces Q4 results: May 06, 2026, 9:04 AM PDT**"
        out = _strip_hallucinated_timestamps(text)
        assert "May 06" not in out
        assert "Tesla announces Q4 results" in out

    def test_leaves_body_prose_untouched(self):
        """Don't strip legitimate in-body date references like
        ``On May 6, 2026, Tesla announced...`` — only headline tails."""
        from engine.generator import _strip_hallucinated_timestamps
        text = (
            "On May 6, 2026, Tesla announced its Q4 results.\n"
            "The numbers exceeded expectations across every segment.\n"
            "Tesla followed up on May 6, 2026 with a press release."
        )
        out = _strip_hallucinated_timestamps(text)
        assert out == text  # unchanged — none of these are headline-shaped

    def test_does_not_strip_when_only_word_remaining(self):
        """If stripping would leave the line empty / punctuation-only,
        keep the original — defensive against malformed input."""
        from engine.generator import _strip_hallucinated_timestamps
        text = "1. May 06, 2026, 9:04 AM PDT"
        out = _strip_hallucinated_timestamps(text)
        # Leaves the original since stripping would erase the line.
        assert "May 06" in out

    def test_empty_input(self):
        from engine.generator import _strip_hallucinated_timestamps
        assert _strip_hallucinated_timestamps("") == ""

    def test_no_timestamp_returns_input_unchanged(self):
        from engine.generator import _strip_hallucinated_timestamps
        text = "1. Tesla announces results.\n2. Another headline."
        assert _strip_hallucinated_timestamps(text) == text


# ---------------------------------------------------------------------------
# Speaker-prefix strip in _sanitize_podcast_script
# ---------------------------------------------------------------------------

class TestSpeakerPrefixStrip:

    def test_strips_patrick_speaker_prefix_at_start_of_paragraph(self):
        from engine.generator import _sanitize_podcast_script
        script = (
            "Patrick: Tesla announced strong Q4 results today.\n"
            "Patrick: Tesla also unveiled a new charging network.\n"
            "Patrick: That wraps up today's update.\n"
        )
        out = _sanitize_podcast_script(script)
        for line in out.splitlines():
            assert not line.lstrip().lower().startswith("patrick:")
        assert "Tesla announced strong Q4 results today." in out
        assert "Tesla also unveiled a new charging network." in out

    def test_strips_olya_prefix_for_russian_shows(self):
        from engine.generator import _sanitize_podcast_script
        script = (
            "Olya: Сегодня важные новости о ставке Bank of Canada.\n"
            "Оля: Что это значит для ваших ипотек.\n"
        )
        out = _sanitize_podcast_script(script)
        for line in out.splitlines():
            stripped = line.lstrip().lower()
            assert not stripped.startswith("olya:")
            assert not stripped.startswith("оля:")
        assert "Сегодня важные новости" in out
        assert "Что это значит для ваших ипотек." in out

    def test_strips_generic_host_prefix(self):
        from engine.generator import _sanitize_podcast_script
        script = "Host: Welcome back to the show."
        out = _sanitize_podcast_script(script)
        assert "Host:" not in out
        assert "Welcome back to the show." in out

    def test_does_not_strip_inline_references_to_patrick(self):
        """Stripping must be anchored at line start — the host name
        appearing mid-sentence (e.g. quoting the host) stays."""
        from engine.generator import _sanitize_podcast_script
        script = (
            "The producer asked Patrick: did you see the news?\n"
            "Patrick: Yes, I did.\n"
        )
        out = _sanitize_podcast_script(script)
        # Mid-sentence reference preserved.
        assert "asked Patrick: did you see the news?" in out
        # Line-start prefix stripped.
        assert "Yes, I did." in out
        assert "Patrick: Yes" not in out


# ---------------------------------------------------------------------------
# _retry_word_count_ok — guard for repetition-retry word-count regression
# ---------------------------------------------------------------------------

class TestRetryWordCountOk:
    """Operator caught (Omni View Ep059, 2026-05-23) the anti-repetition
    retry replacing an 883-word original with a 555-word retry. The old
    guard used ``len(text_retry) < len(text) * 0.5`` on CHAR length,
    which passed (3870 / 6163 ≈ 0.63), the swap went through, and the
    555-word script then tripped the runner's 600-word hard floor and
    aborted the episode. The new ``_retry_word_count_ok`` helper gates
    both repetition-retry paths on WORD count, with the per-show floor
    + 50 as a hard minimum so the hard-floor check downstream has
    headroom."""

    def test_ov_ep059_scenario_rejects_retry(self):
        """The exact OV Ep059 numbers: 883-word original, 555-word
        retry, network default floor=600. Must reject so the runner
        keeps the (repetitive but usable) 883-word original instead
        of swapping in the (clean but too-short) 555-word retry."""
        from engine.generator import _retry_word_count_ok
        assert _retry_word_count_ok(
            orig_words=883, retry_words=555, show_floor=600,
        ) is False

    def test_healthy_retry_accepted(self):
        """Retry that keeps >=80% of original word count AND stays
        well above the floor — the happy path. Accept."""
        from engine.generator import _retry_word_count_ok
        assert _retry_word_count_ok(
            orig_words=1000, retry_words=900, show_floor=600,
        ) is True

    def test_retry_below_floor_plus_margin_rejected(self):
        """Even when the retry keeps 80%+ of the word count, if it
        would land within 50 words of the per-show floor we reject —
        the runner's hard-floor check happens AFTER the swap, so we
        leave a 50-word buffer for ``loudnorm`` / ``_sanitize`` /
        anti-tag-strip rounding."""
        from engine.generator import _retry_word_count_ok
        # 80% of 800 = 640. Floor + 50 = 650. Retry of 640 fails
        # the floor-margin guard.
        assert _retry_word_count_ok(
            orig_words=800, retry_words=640, show_floor=600,
        ) is False
        # 651 clears floor+50.
        assert _retry_word_count_ok(
            orig_words=800, retry_words=651, show_floor=600,
        ) is True

    def test_env_intel_low_floor_lets_short_shows_swap(self):
        """env_intel has ``min_podcast_word_floor: 450`` (PR #395) so
        retries that land at 500-600 words still pass when the show
        deliberately ships shorter episodes. Show-specific floor is
        honored end-to-end."""
        from engine.generator import _retry_word_count_ok
        # env_intel: orig 700 → retry 580. 80% = 560, floor+50 = 500.
        # 580 >= max(560, 500) = 560 → ACCEPT.
        assert _retry_word_count_ok(
            orig_words=700, retry_words=580, show_floor=450,
        ) is True

    def test_uses_max_of_two_constraints(self):
        """When the two constraints (80% and floor+50) disagree, the
        STRICTER one wins. A short original (e.g. 500 words) with a
        retry at 400 words clears 80%-of-original (400 >= 400) but
        not floor+50 (400 < 650 for floor=600) → REJECT."""
        from engine.generator import _retry_word_count_ok
        assert _retry_word_count_ok(
            orig_words=500, retry_words=400, show_floor=600,
        ) is False


# ---------------------------------------------------------------------------
# _correct_common_llm_text_mistakes (TST Ep489/Ep490 branding + grammar slips)
# ---------------------------------------------------------------------------

class TestCorrectCommonLLMTextMistakes:
    """Regression tests for the post-generation brand / title / grammar
    fixer added after operator reported mangled openings in TST Ep490
    (and similar issues in Ep489 and older runs).
    """

    def test_fixes_tela_brand(self):
        from engine.generator import _correct_common_llm_text_mistakes
        bad = "Tela never sleeps, and neither do's the news cycle."
        out = _correct_common_llm_text_mistakes(bad)
        assert "Tesla never sleeps" in out
        assert "Tela" not in out

    def test_fixes_tesla_rati_split(self):
        from engine.generator import _correct_common_llm_text_mistakes
        bad = "According to a Tesla Rati editor and Tesla Ratie analysis..."
        out = _correct_common_llm_text_mistakes(bad)
        assert "Teslarati" in out
        assert "Tesla Rati" not in out
        assert "Tesla Ratie" not in out

    def test_normalizes_mangled_show_title_variants(self):
        from engine.generator import _correct_common_llm_text_mistakes
        cases = [
            "welcome to Tela Short's Time, daily, episode four hundred ninety.",
            "Welcome to Tesla Short's Time Daily.",
            "welcome to Tela Shorts Time, daily",
            "Thanks for tuning in to Tesla Shorts Time daily.",
        ]
        for bad in cases:
            out = _correct_common_llm_text_mistakes(bad)
            assert "Tesla Shorts Time Daily" in out
            # No possessive on Short or Time, title case Daily
            assert "Short's" not in out
            assert "Shorts Time, daily" not in out.lower()

    def test_fixes_dos_in_famous_framing_line(self):
        from engine.generator import _correct_common_llm_text_mistakes
        bad = "Tela never sleeps, and neither do's the news cycle."
        out = _correct_common_llm_text_mistakes(bad)
        assert "neither does the news cycle" in out
        assert "do's" not in out

    def test_is_idempotent_and_preserves_good_text(self):
        from engine.generator import _correct_common_llm_text_mistakes
        good = (
            "Tesla never sleeps and neither does the news cycle. "
            "Welcome to Tesla Shorts Time Daily, episode 490. "
            "According to Teslarati..."
        )
        out = _correct_common_llm_text_mistakes(good)
        assert out == good  # no change on clean input

