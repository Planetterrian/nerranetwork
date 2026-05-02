"""Tests for newsletter_body — Tesla price block, Russian vocab cards,
box-rule replacement, OV source-list dedup, and the canonical/email
two-stage split."""

from __future__ import annotations

from engine.newsletter_body import (
    dedup_read_more_sources,
    promote_hook_to_blockquote,
    render_russian_vocab_cards,
    render_tsla_price_block,
    replace_box_rules_with_md_hr,
    shorten_source_urls,
    transform_daily_body,
    transform_email_body,
    upgrade_md_hr_to_html,
)


# ---------------------------------------------------------------------------
# Box rules — canonical (markdown) and email (HTML) stages
# ---------------------------------------------------------------------------

class TestBoxRulesCanonical:

    def test_replaces_run_of_box_chars_with_md_hr(self):
        text = "Section A\n━━━━━━━━━━━━━━━━━━━━\nSection B"
        out = replace_box_rules_with_md_hr(text)
        assert "━━━" not in out
        assert "---" in out
        # No HTML at canonical stage.
        assert "<hr" not in out

    def test_idempotent(self):
        text = "A\n━━━━━━━━━\nB"
        once = replace_box_rules_with_md_hr(text)
        twice = replace_box_rules_with_md_hr(once)
        assert once == twice

    def test_empty(self):
        assert replace_box_rules_with_md_hr("") == ""

    def test_does_not_match_short_runs(self):
        text = "Some prose with ── inline."
        assert replace_box_rules_with_md_hr(text) == text


class TestBoxRulesEmail:

    def test_upgrades_md_hr_to_styled_hr(self):
        text = "Section A\n---\nSection B"
        out = upgrade_md_hr_to_html(text)
        assert "<hr" in out
        # Inline-styled (dark-mode-aware via _DARK_MODE_STYLE).
        assert "border-top:1px solid" in out

    def test_idempotent(self):
        text = "A\n---\nB"
        once = upgrade_md_hr_to_html(text)
        twice = upgrade_md_hr_to_html(once)
        assert once == twice


# ---------------------------------------------------------------------------
# Tesla price block — email stage only
# ---------------------------------------------------------------------------

class TestTeslaPriceBlock:

    def test_renders_up_arrow_green(self):
        text = "**REAL-TIME TSLA price:** $390.82 ▲ $9.44 (2.5%)"
        out = render_tsla_price_block(text)
        assert "TSLA today" in out
        assert "$390.82" in out
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
# Hook → blockquote
# ---------------------------------------------------------------------------

class TestHookBlockquote:
    """After ``scrub_scaffold`` strips the ``**HOOK:**`` label, the
    hook becomes plain prose. ``promote_hook_to_blockquote`` wraps it
    in a markdown blockquote so it stands out across every surface."""

    def test_promotes_first_prose_after_header(self):
        text = (
            "# Tesla Shorts Time\n"
            "**TSLA today:** $390 ▲ $9 (2%)\n"
            "\n"
            "Tesla introduced the Roadster.\n"
            "\n"
            "---\n"
            "More content.\n"
        )
        out = promote_hook_to_blockquote(text)
        assert "> **Tesla introduced the Roadster.**" in out

    def test_idempotent(self):
        text = (
            "# Tesla Shorts Time\n"
            "**TSLA today:** $390 ▲ $9 (2%)\n"
            "\n"
            "The hook line.\n"
        )
        once = promote_hook_to_blockquote(text)
        twice = promote_hook_to_blockquote(once)
        assert once == twice

    def test_skips_when_first_line_is_already_blockquote(self):
        text = (
            "# Tesla Shorts Time\n"
            "\n"
            "> **Already a quote.**\n"
        )
        out = promote_hook_to_blockquote(text)
        # Already a blockquote — no double-wrap.
        assert out.count("> **") == 1

    def test_skips_when_no_prose_before_structure(self):
        text = (
            "# Tesla Shorts Time\n"
            "\n"
            "## Top 10 News Items\n"
            "1. First item\n"
        )
        out = promote_hook_to_blockquote(text)
        # Hit a heading before any prose — bail.
        assert out == text

    def test_strips_existing_bold_wrapping(self):
        text = (
            "# Tesla Shorts Time\n"
            "\n"
            "**Already bold hook**\n"
        )
        out = promote_hook_to_blockquote(text)
        # Don't end up with `> ****Already bold hook****` — the inner
        # ** are stripped before re-wrapping.
        assert "> **Already bold hook**" in out
        assert "****" not in out

    def test_empty_input(self):
        assert promote_hook_to_blockquote("") == ""


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
        assert "font-size:22px" in out
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
        assert out.count("https://dailymail.com/x") == 1
        assert "Threat level details" in out
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
# transform_daily_body — canonical (markdown-safe) orchestration
# ---------------------------------------------------------------------------

class TestTransformDailyBody:
    """Canonical-stage: every transform output must be valid markdown
    that renders cleanly on the blog, RSS, and GitHub Pages surfaces."""

    def test_tesla_keeps_price_line_as_markdown(self):
        text = (
            "# Tesla Shorts Time\n"
            "**REAL-TIME TSLA price:** $390 ▲ $9 (2%)\n"
            "\n"
            "Tesla introduced something.\n"
            "\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Section content."
        )
        out = transform_daily_body(text, slug="tesla")
        # No inline HTML at canonical stage.
        assert "<table" not in out
        assert "<hr" not in out
        # TSLA price stays as a bold-label markdown line.
        assert "**REAL-TIME TSLA price:**" in out
        # Box rule became markdown ---.
        assert "---" in out
        assert "━━━" not in out

    def test_tesla_promotes_hook_to_blockquote(self):
        text = (
            "# Tesla Shorts Time\n"
            "**REAL-TIME TSLA price:** $390 ▲ $9 (2%)\n"
            "\n"
            "Tesla introduced the Roadster.\n"
        )
        out = transform_daily_body(text, slug="tesla")
        assert "> **Tesla introduced the Roadster.**" in out

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
        # Markdown HR, not HTML.
        assert "---" in out
        assert "<hr" not in out

    def test_unknown_slug_only_runs_universal_transforms(self):
        text = "━━━━━━━━━━\nFiller."
        out = transform_daily_body(text, slug="some_other_show")
        assert "━━━" not in out
        assert "TSLA today" not in out


# ---------------------------------------------------------------------------
# transform_email_body — HTML upgrades
# ---------------------------------------------------------------------------

class TestTransformEmailBody:
    """Email-stage: applied AFTER transform_daily_body, layers in the
    inline HTML that would corrupt non-email surfaces."""

    def test_tesla_renders_html_table_for_tsla_line(self):
        # Body comes in already canonical-transformed.
        body = (
            "# Tesla Shorts Time\n"
            "**REAL-TIME TSLA price:** $390 ▲ $9 (2%)\n"
            "\n"
            "> **Tesla introduced something.**\n"
            "\n"
            "---\n"
            "Section."
        )
        out = transform_email_body(body, slug="tesla")
        # Stock-watch table appears.
        assert "TSLA today" in out
        assert "<table" in out
        assert "$390" in out
        # Markdown HR upgraded to styled <hr>.
        assert "<hr" in out

    def test_non_tesla_only_runs_hr_upgrade(self):
        body = "Section A\n---\nSection B"
        out = transform_email_body(body, slug="omni_view")
        assert "<hr" in out
        assert "TSLA today" not in out

    def test_idempotent_after_canonical(self):
        canonical = transform_daily_body(
            "**REAL-TIME TSLA price:** $390 ▲ $9 (2%)\n\nHook line.\n\n---\nA",
            slug="tesla",
        )
        once = transform_email_body(canonical, slug="tesla")
        twice = transform_email_body(once, slug="tesla")
        assert once == twice


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
        assert "[Google News]" in out
        assert long_url in out
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
        text = "[See @teslashortstime](https://x.com/teslashortstime) for updates."
        out = self._linkify(text)
        twice = self._linkify(out)
        assert out == twice  # idempotent

    def test_skips_handle_inside_url(self):
        text = "See https://x.com/@teslashortstime for the feed."
        out = self._linkify(text)
        assert out == text

    def test_skips_email_addresses(self):
        text = "Email me at user@example.com for details."
        out = self._linkify(text)
        assert out == text

    def test_handle_length_cap_at_15(self):
        text = "@aaaaaaaaaaaaaaab x"
        out = self._linkify(text)
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
# Canonical + email integration — end-to-end TST shape
# ---------------------------------------------------------------------------

class TestCanonicalScrubIntegration:
    """The transforms run at TWO sites: canonical-write in run_show.py
    (markdown only) and email-send in send_show_newsletter (HTML
    upgrades on top). Verifies both stages cover every leak that
    showed up in TST Ep458 / Ep459's published output."""

    def _raw_tst(self) -> str:
        return (
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
            "## Short Spot\n"
            "**Catchy Title: Brand-New Cybertruck Crashed: May 02, Yahoo**\n"
            "Body about the crash.\n"
            "\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Let me know your thoughts at @teslashortstime."
        )

    def test_canonical_stage_is_markdown_only(self):
        from engine.newsletter_sanitizer import scrub_scaffold

        cleaned = scrub_scaffold(self._raw_tst())
        cleaned = transform_daily_body(cleaned, slug="tesla")

        # Scaffold removed.
        assert "**Date:**" not in cleaned
        assert "**HOOK:**" not in cleaned
        # Catchy Title placeholder stripped, real title preserved.
        assert "Catchy Title:" not in cleaned
        assert "Brand-New Cybertruck Crashed" in cleaned
        # Box rules → markdown ---, no HTML.
        assert "━━━" not in cleaned
        assert "<hr" not in cleaned
        assert "---" in cleaned
        # TSLA price stays as bold-label markdown.
        assert "**REAL-TIME TSLA price:**" in cleaned
        assert "<table" not in cleaned
        # Hook gets blockquote prominence.
        assert "> **California closed a loophole" in cleaned
        # Long Google News URL collapsed to label.
        assert "[Google News]" in cleaned
        assert "Source: https://news.google.com/rss/articles/CBMii" not in cleaned
        # X handle linkified.
        assert "[@teslashortstime](https://x.com/teslashortstime)" in cleaned

    def test_email_stage_layers_html_on_top(self):
        from engine.newsletter_sanitizer import scrub_scaffold

        cleaned = scrub_scaffold(self._raw_tst())
        cleaned = transform_daily_body(cleaned, slug="tesla")
        emailed = transform_email_body(cleaned, slug="tesla")

        # Markdown --- now becomes styled HTML <hr>.
        assert "<hr" in emailed
        # TSLA price line becomes the styled stock-watch table.
        assert "<table" in emailed
        assert "TSLA today" in emailed
        # Canonical content survives.
        assert "California closed a loophole" in emailed
        assert "Story body." in emailed
        assert "Brand-New Cybertruck Crashed" in emailed
