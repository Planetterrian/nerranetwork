"""Tests for the newsletter scaffold-leak sanitizer."""

from __future__ import annotations

import pytest

from engine.newsletter_sanitizer import (
    SCAFFOLD_PATTERNS,
    ScaffoldLeakError,
    assert_clean,
    find_scaffold_leaks,
    scrub_scaffold,
)


# ---------------------------------------------------------------------------
# scrub_scaffold
# ---------------------------------------------------------------------------

class TestScrubScaffold:

    def test_strips_hook_label(self):
        text = (
            "**HOOK:** Tesla has introduced its cheapest Model 3 in Canada.\n\n"
            "More body text here."
        )
        out = scrub_scaffold(text)
        assert "**HOOK:**" not in out
        # The hook content survives — the prompt scaffold is just the label.
        assert "cheapest Model 3" in out

    def test_strips_date_line(self):
        text = "**Date:** May 02, 2026\n\n## Section header"
        out = scrub_scaffold(text)
        assert "**Date:**" not in out
        assert "May 02, 2026" not in out  # the whole line goes
        assert "## Section header" in out

    def test_strips_russian_zagolovok(self):
        text = (
            "**ЗАГОЛОВОК:** Космос — наш сегодняшний урок.\n\n"
            "Body."
        )
        out = scrub_scaffold(text)
        assert "**ЗАГОЛОВОК:**" not in out
        assert "Космос" in out

    def test_does_not_strip_box_drawing_rules(self):
        """Spec v2 follow-up: the sanitizer leaves box rules alone so
        engine.newsletter_body.replace_box_rules_with_md_hr can convert
        them to ``---``. Stripping here would defeat that conversion."""
        text = (
            "Section A\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Section B"
        )
        out = scrub_scaffold(text)
        # Rules survive the scrub stage.
        assert "━━━" in out
        assert "Section A" in out
        assert "Section B" in out

    def test_strips_first_principles_labels(self):
        text = (
            "**The Surprising Truth:** Tesla's pricing strategy is misread.\n\n"
            "**The Fundamental Question:** What does the market actually need?\n\n"
            "**The Data Says:** Sales rose 22%.\n\n"
            "**The Tesla Approach:** Vertical integration.\n\n"
            "**The Bottom Line:** This works.\n"
        )
        out = scrub_scaffold(text)
        for label in (
            "**The Surprising Truth:**",
            "**The Fundamental Question:**",
            "**The Data Says:**",
            "**The Tesla Approach:**",
            "**The Bottom Line:**",
        ):
            assert label not in out
        # Content survives.
        assert "pricing strategy is misread" in out
        assert "Sales rose 22%." in out

    def test_strips_general_concept_source_line(self):
        text = (
            "Some body content.\n"
            "Source: General concept\n"
            "More body content."
        )
        out = scrub_scaffold(text)
        assert "General concept" not in out

    def test_strips_pre_fetched_url_marker(self):
        text = "Read more about it (full URL from pre-fetched: https://example.com/foo)."
        out = scrub_scaffold(text)
        assert "pre-fetched" not in out

    def test_idempotent(self):
        text = "**HOOK:** a\n\n**Date:** b\n\n━━━\n\nContent."
        once = scrub_scaffold(text)
        twice = scrub_scaffold(once)
        assert once == twice

    def test_empty_and_none(self):
        assert scrub_scaffold("") == ""
        assert scrub_scaffold(None) is None  # type: ignore[arg-type]

    def test_does_not_scrub_legitimate_bold_phrase(self):
        """A bolded phrase mid-sentence isn't a label — leave it alone."""
        text = "Tesla revealed **the cheapest Model 3** in Canadian history."
        out = scrub_scaffold(text)
        assert "**the cheapest Model 3**" in out


# ---------------------------------------------------------------------------
# find_scaffold_leaks (post-scrub tripwire)
# ---------------------------------------------------------------------------

class TestFindScaffoldLeaks:

    def test_clean_text_has_no_leaks(self):
        text = "Welcome to today's episode. Here's what's new in Tesla world."
        assert find_scaffold_leaks(text) == []

    def test_bare_label_line_is_caught_by_generic_rule(self):
        """A new label we forgot to add to the blocklist still trips
        the generic ``^**Capitalized:**$`` catch-all."""
        text = "**Today's Insight:**"
        leaks = find_scaffold_leaks(text)
        assert any("bare-label line" in m for m in leaks)

    def test_after_scrubbing_known_labels_clean(self):
        text = "**HOOK:** Body content.\n\n**Date:** May 02, 2026\n\nDone."
        scrubbed = scrub_scaffold(text)
        assert find_scaffold_leaks(scrubbed) == []


# ---------------------------------------------------------------------------
# assert_clean (raises on leaks)
# ---------------------------------------------------------------------------

class TestAssertClean:

    def test_passes_for_clean(self):
        # Should not raise.
        assert_clean("Hello world.")

    def test_raises_for_unknown_bare_label(self):
        with pytest.raises(ScaffoldLeakError) as exc_info:
            assert_clean("**Mystery New Label:**")
        assert "bare-label line" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Pattern coverage — every spec §2.2 pattern is in the blocklist
# ---------------------------------------------------------------------------

class TestPatternCoverage:

    def test_blocklist_covers_spec_v2_patterns(self):
        """Every pattern called out in spec v2 §2.2 must be present."""
        names = [name for _re, _repl, name in SCAFFOLD_PATTERNS]
        required = [
            "**HOOK:**",
            "**Date:** line",
            "**Theme:** line",
            "**ЗАГОЛОВОК:**",
            "**The Surprising Truth:**",
            "**The Fundamental Question:**",
            "**The Data Says:**",
            "**The Tesla Approach:**",
            "**The Bottom Line:**",
            "**Vocabulary List (..):**",
            "**Memory hook:**",
            "Source: General concept",
            "(full URL from pre-fetched: …)",
            # Box-drawing rules are NOT in the sanitizer anymore — they're
            # converted to markdown ``---`` by engine.newsletter_body in
            # the canonical body-transform stage, then upgraded to styled
            # ``<hr>`` in the email-only transform. Both are exercised
            # in tests/test_newsletter_body.py.
            #
            # Added in the canonical-digest-scrub follow-up — Tesla
            # Ep458 .md leaked **TOPIC SELECTION:** verbatim.
            "**TOPIC SELECTION:** ... line",
            "**TOPIC FRESHNESS:** ... line",
            "**WHAT TO SKIP:** ... line",
            "**LENGTH TARGET:** ... line",
            # Added in the description+voice polish follow-up — Tesla
            # Ep459 leaked the literal ``Catchy Title:`` placeholder.
            "**Catchy Title: ...**",
        ]
        for r in required:
            assert r in names, (
                f"Spec v2 §2.2 requires pattern {r!r} in the blocklist; "
                f"it's missing — extend SCAFFOLD_PATTERNS."
            )

    def test_strips_topic_selection_with_trailing_text(self):
        """The **TOPIC SELECTION:** label is sometimes echoed with the
        rest of the prompt instruction concatenated on the same line.
        Strip the whole line, not just the label."""
        text = (
            "Some prose.\n"
            "**TOPIC SELECTION:** At what point does bidirectional charging "
            "turn an EV into an energy asset\n"
            "More prose."
        )
        out = scrub_scaffold(text)
        assert "TOPIC SELECTION" not in out
        # The instruction tail is also gone (whole-line strip).
        assert "bidirectional charging" not in out
        assert "Some prose." in out
        assert "More prose." in out

    def test_strips_topic_freshness_block(self):
        text = "**TOPIC FRESHNESS — MUST choose a different topic:** Recent: A, B, C\nNext line."
        out = scrub_scaffold(text)
        assert "TOPIC FRESHNESS" not in out
        assert "Next line." in out

    def test_strips_catchy_title_placeholder_keeps_real_title(self):
        """Tesla Ep459 leaked ``**Catchy Title: <real title>: <date>...**``
        because the LLM mirrored the prompt's placeholder. The sanitizer
        strips the ``Catchy Title:`` prefix while preserving the real
        headline that follows."""
        text = (
            "## Short Spot\n"
            "**Catchy Title: Brand-New Cybertruck Crashed: May 02, 2026, Yahoo**\n"
            "Body about the crash."
        )
        out = scrub_scaffold(text)
        assert "Catchy Title:" not in out
        # The real headline survives, still bold.
        assert "**Brand-New Cybertruck Crashed: May 02, 2026, Yahoo**" in out
        assert "Body about the crash." in out

    def test_catchy_title_strip_idempotent(self):
        text = "**Catchy Title: Some Real Headline: May 02, Source**"
        once = scrub_scaffold(text)
        twice = scrub_scaffold(once)
        assert once == twice
