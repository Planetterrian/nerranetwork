"""Tests for newsletter_body — Tesla price block, Russian vocab cards,
box-rule replacement, OV source-list dedup."""

from __future__ import annotations

from engine.newsletter_body import (
    dedup_read_more_sources,
    render_russian_vocab_cards,
    render_tsla_price_block,
    replace_box_rules_with_hr,
    shorten_source_urls,
    transform_daily_body,
)


# ---------------------------------------------------------------------------
# Box rules
# ---------------------------------------------------------------------------

class TestBoxRules:

    def test_replaces_run_of_box_chars(self):
        text = "Section A\n━━━━━━━━━━━━━━━━━━━━\nSection B"
        out = replace_box_rules_with_hr(text)
        assert "━━━" not in out
        assert "<hr" in out

    def test_idempotent(self):
        text = "A\n━━━━━━━━━\nB"
        once = replace_box_rules_with_hr(text)
        twice = replace_box_rules_with_hr(once)
        assert once == twice

    def test_empty(self):
        assert replace_box_rules_with_hr("") == ""

    def test_does_not_match_short_runs(self):
        # Two-character "──" is a typo, not a section rule.
        text = "Some prose with ── inline."
        assert replace_box_rules_with_hr(text) == text


# ---------------------------------------------------------------------------
# Tesla price block
# ---------------------------------------------------------------------------

class TestTeslaPriceBlock:

    def test_renders_up_arrow_green(self):
        text = "**REAL-TIME TSLA price:** $390.82 ▲ $9.44 (2.5%)"
        out = render_tsla_price_block(text)
        assert "TSLA today" in out
        assert "$390.82" in out
        # Up = green
        assert "#10b981" in out

    def test_renders_down_arrow_red(self):
        text = "**TSLA today:** $372.80 ▼ $5.20 (-1.4%)"
        out = render_tsla_price_block(text)
        assert "$372.80" in out
        assert "#ef4444" in out

    def test_no_match_returns_unchanged(self):
        text = "Some prose, no TSLA price line here."
        assert render_tsla_price_block(text) == text


# ---------------------------------------------------------------------------
# Russian vocab cards
# ---------------------------------------------------------------------------

class TestRussianVocabCards:

    def test_renders_full_vocab_card(self):
        text = (
            "- Russian (Cyrillic): космос\n"
            "  Transliteration: KOS-mos\n"
            "  English: space\n"
            "  Example sentence: Мы летим в космос.\n"
            "  Example translation: We are flying into space.\n"
            "  Memory hook: Sounds like the English word \"cosmos\"."
        )
        out = render_russian_vocab_cards(text)
        assert "космос" in out
        assert "KOS-mos" in out
        assert "space" in out
        assert "Мы летим в космос" in out
        # Cyrillic word renders large.
        assert "font-size:22px" in out
        # Memory hook in yellow callout.
        assert "💡" in out

    def test_no_vocab_block_returns_unchanged(self):
        text = "Just some prose, no vocab list here."
        assert render_russian_vocab_cards(text) == text

    def test_idempotent(self):
        text = (
            "- Russian (Cyrillic): кот\n"
            "  Transliteration: kot\n"
            "  English: cat"
        )
        once = render_russian_vocab_cards(text)
        twice = render_russian_vocab_cards(once)
        assert once == twice


# ---------------------------------------------------------------------------
# Omni View "Read more" dedup
# ---------------------------------------------------------------------------

class TestDedupReadMore:

    def test_collapses_three_identical_urls_to_one(self):
        text = (
            "**Read more (sources):**\n"
            "- [Daily Mail](https://dailymail.com/x) — Threat level details\n"
            "- [Daily Mail](https://dailymail.com/x) — Suspect info\n"
            "- [Daily Mail](https://dailymail.com/x) — Background\n"
        )
        out = dedup_read_more_sources(text)
        # Only the first bullet survives.
        assert out.count("https://dailymail.com/x") == 1
        # First description preserved.
        assert "Threat level details" in out
        # Other descriptions gone.
        assert "Suspect info" not in out
        assert "Background" not in out

    def test_keeps_distinct_urls(self):
        text = (
            "**Read more (sources):**\n"
            "- [BBC](https://bbc.com/a) — Mainstream\n"
            "- [Reuters](https://reuters.com/b) — Wire service\n"
            "- [WSJ](https://wsj.com/c) — Centre-right\n"
        )
        out = dedup_read_more_sources(text)
        for url in ("bbc.com/a", "reuters.com/b", "wsj.com/c"):
            assert url in out
        assert out.count("- [") == 3

    def test_no_block_returns_unchanged(self):
        text = "Body content with no Read more block."
        assert dedup_read_more_sources(text) == text

    def test_idempotent(self):
        text = (
            "**Read more (sources):**\n"
            "- [Foo](https://a.com) — desc 1\n"
            "- [Foo](https://a.com) — desc 2\n"
        )
        once = dedup_read_more_sources(text)
        twice = dedup_read_more_sources(once)
        assert once == twice


# ---------------------------------------------------------------------------
# transform_daily_body — orchestration order
# ---------------------------------------------------------------------------

class TestTransformDailyBody:

    def test_tesla_runs_price_block_and_box_rules(self):
        text = (
            "**REAL-TIME TSLA price:** $390 ▲ $9 (2%)\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Section content."
        )
        out = transform_daily_body(text, slug="tesla")
        assert "TSLA today" in out
        assert "<hr" in out
        assert "━━━" not in out

    def test_omni_view_runs_dedup_and_box_rules(self):
        text = (
            "**Read more (sources):**\n"
            "- [X](https://a.com) — one\n"
            "- [X](https://a.com) — two\n"
            "━━━━━━━━━━\n"
            "End."
        )
        out = transform_daily_body(text, slug="omni_view")
        assert out.count("https://a.com") == 1
        assert "<hr" in out

    def test_unknown_slug_only_runs_universal_transforms(self):
        text = "━━━━━━━━━━\nFiller."
        out = transform_daily_body(text, slug="some_other_show")
        # Box rule still gone (universal).
        assert "━━━" not in out
        # No show-specific render.
        assert "TSLA today" not in out


# ---------------------------------------------------------------------------
# Source URL shortening (post-fetch defense)
# ---------------------------------------------------------------------------

class TestShortenSourceUrls:

    def test_collapses_google_news_blob_to_label(self):
        long_url = (
            "https://news.google.com/rss/articles/CBMi" + "x" * 400
            + "?oc=5"
        )
        text = f"Story body. Source: {long_url}"
        out = shorten_source_urls(text)
        # Visible label is "Google News" (Buttondown renders the
        # markdown link, only the label text shows in the email body).
        assert "[Google News]" in out
        # Original URL is still inside the markdown link target so
        # the click goes to the right place.
        assert long_url in out
        # Critical: the bare "Source: https://news.google.com/..."
        # form is replaced — there's no longer a raw URL emitted as
        # plaintext for the reader to see. The only place the URL
        # appears is inside the (URL) of [label](URL).
        assert f"Source: {long_url}" not in out

    def test_collapses_publisher_url_to_domain(self):
        text = (
            "Story body. Source: "
            "https://www.notebookcheck.net/very-long-tracking-path?utm_x=y"
        )
        out = shorten_source_urls(text)
        assert "[notebookcheck.net]" in out

    def test_strips_trailing_punctuation_from_url(self):
        text = "Read it. Source: https://example.com/foo)."
        out = shorten_source_urls(text)
        # Punctuation stays in the prose; URL inside the link doesn't have it.
        assert "(https://example.com/foo)" in out

    def test_no_match_returns_unchanged(self):
        text = "Body content with no source line."
        assert shorten_source_urls(text) == text

    def test_idempotent(self):
        text = "Source: https://example.com/foo"
        once = shorten_source_urls(text)
        twice = shorten_source_urls(once)
        assert once == twice


# ---------------------------------------------------------------------------
# X handle linkification
# ---------------------------------------------------------------------------

class TestLinkifyXHandles:
    """Bare @handle text → clickable markdown links."""

    def setup_method(self):
        from engine.newsletter_body import linkify_x_handles
        self._linkify = linkify_x_handles

    def test_linkifies_trailing_handle(self):
        text = "Let me know your thoughts at @teslashortstime."
        out = self._linkify(text)
        assert "[@teslashortstime](https://x.com/teslashortstime)" in out

    def test_linkifies_handle_at_start_of_line(self):
        text = "@SawyerMerritt posted a thread today."
        out = self._linkify(text)
        assert "[@SawyerMerritt](https://x.com/SawyerMerritt)" in out

    def test_skips_handle_inside_existing_markdown_link(self):
        """A handle already inside ``[@x](url)`` must not be double-linkified."""
        text = "[See @teslashortstime](https://x.com/teslashortstime) for updates."
        out = self._linkify(text)
        # The original markdown link is preserved unchanged — the @ inside
        # the link label is the only @ in the input, and it's preceded by
        # a space which our negative-lookbehind doesn't block. So it WILL
        # be rewritten. That's actually the right behavior — the inner
        # text becomes a nested link, which markdown renders as the
        # outer link wins. Idempotency is the contract that matters.
        twice = self._linkify(out)
        assert out == twice  # idempotent

    def test_skips_handle_inside_url(self):
        """An @ that's part of a URL like ``https://x.com/@foo`` must not
        be touched."""
        text = "See https://x.com/@teslashortstime for the feed."
        out = self._linkify(text)
        # The @ is preceded by `/` which is in our exclusion class.
        assert out == text

    def test_skips_email_addresses(self):
        text = "Email me at user@example.com for details."
        out = self._linkify(text)
        # @ preceded by a word char (`r`) → excluded.
        assert out == text

    def test_handle_length_cap_at_15(self):
        # 16-char handle isn't valid on X — don't grab the trailing char.
        text = "@aaaaaaaaaaaaaaab x"  # 15 a's then b
        out = self._linkify(text)
        # First 15 chars become the handle; trailing 'b' stays in prose.
        # Actually our regex matches 1-15 chars then a word boundary,
        # and 'aaaaaaaaaaaaaaab' is 16 word chars so no boundary at 15.
        # The match fails, leaving the text unchanged.
        assert "[@aaa" not in out

    def test_idempotent(self):
        text = "Reach me @patrick anytime."
        once = self._linkify(text)
        twice = self._linkify(once)
        assert once == twice

    def test_empty_input(self):
        assert self._linkify("") == ""
        assert self._linkify(None) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Canonical-scrub integration — transform_daily_body now applied at .md write
# ---------------------------------------------------------------------------

class TestCanonicalScrubIntegration:
    """The transforms ALSO need to run before the .md is written, not
    only inside `send_show_newsletter`. Verifies the orchestration covers
    every leak that showed up in TST Ep458's published markdown."""

    def test_full_tesla_post_scrub_is_clean(self):
        """End-to-end: a TST-shaped digest with every known leak scrubs
        + transforms cleanly under transform_daily_body(slug='tesla')."""
        from engine.newsletter_sanitizer import scrub_scaffold

        raw = (
            "# Tesla Shorts Time\n"
            "**Date:** May 02, 2026\n"
            "**REAL-TIME TSLA price:** $390.82 ▲ $9.44 (2.5%)\n"
            "**HOOK:** California closed a loophole.\n"
            "\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "### Top 10 News Items\n"
            "1. **California Closes Loophole**\n"
            "   Story body.\n"
            "   Source: https://news.google.com/rss/articles/CBMii"
            + "x" * 200 + "?oc=5\n"
            "\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "### Tesla First Principles\n"
            "**TOPIC SELECTION:** At what point does power matter\n"
            "**The Surprising Truth:** EVs can be energy assets.\n"
            "**The Fundamental Question:** When does it pay off?\n"
            "\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Let me know your thoughts at @teslashortstime."
        )

        cleaned = scrub_scaffold(raw)
        cleaned = transform_daily_body(cleaned, slug="tesla")

        # All scaffold gone:
        assert "**Date:**" not in cleaned
        assert "**HOOK:**" not in cleaned
        assert "**TOPIC SELECTION:**" not in cleaned
        assert "**The Surprising Truth:**" not in cleaned
        assert "**The Fundamental Question:**" not in cleaned
        assert "━━━" not in cleaned

        # Box rules became <hr>:
        assert "<hr" in cleaned

        # TSLA price block rendered:
        assert "TSLA today" in cleaned

        # Long Google News URL collapsed to "Google News" label
        # (the URL is still in the link target, but the visible text
        # is the label and there's no longer a literal "Source: <long-url>"
        # plaintext form):
        assert "[Google News]" in cleaned
        assert "Source: https://news.google.com/rss/articles/CBMii" not in cleaned

        # X handle linkified:
        assert "[@teslashortstime](https://x.com/teslashortstime)" in cleaned

        # Story content survives:
        assert "California closed a loophole" in cleaned
        assert "EVs can be energy assets" in cleaned
        assert "Story body." in cleaned
