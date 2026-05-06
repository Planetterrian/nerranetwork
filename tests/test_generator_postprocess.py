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
