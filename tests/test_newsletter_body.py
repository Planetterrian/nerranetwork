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
        """May 6 2026: bumped emerald-500 (#10b981, 2.32:1 on cream)
        to emerald-700 (#047857, 5.01:1) so the up arrow clears WCAG
        AA on the TSLA price block's cream background. The prior
        color triggered the newsletter contrast hard-block on
        TST Ep465."""
        text = "**REAL-TIME TSLA price:** $390.82 ▲ $9.44 (2.5%)"
        out = render_tsla_price_block(text)
        assert "TSLA today" in out
        assert "$390.82" in out
        assert "#047857" in out
        assert "#10b981" not in out  # old color must not regress

    def test_renders_down_arrow_red(self):
        """Same fix for the down arrow: red-500 (#ef4444, 3.44:1) →
        red-700 (#b91c1c, 5.91:1)."""
        text = "**TSLA today:** $372.80 ▼ $5.20 (-1.4%)"
        out = render_tsla_price_block(text)
        assert "$372.80" in out
        assert "#b91c1c" in out
        assert "#ef4444" not in out  # old color must not regress

    def test_no_match_returns_unchanged(self):
        text = "Some prose, no TSLA price line here."
        assert render_tsla_price_block(text) == text

    def test_price_is_neutral_high_contrast_not_brand_red(self):
        """The PRICE must stay a high-contrast neutral (dark `#111827`,
        flipped to light in dark mode) — NOT brand red on the tinted
        surface, which rendered as muddy red-on-red on down days
        (operator screenshot, Ep502, Jun 2026). Only the delta carries
        direction colour, via the ``delta-up``/``delta-down`` classes that
        survive the dark-mode text override."""
        up = render_tsla_price_block("**TSLA today:** $390.82 ▲ $9.44 (2.5%)")
        assert "color:#111827" in up           # neutral price
        assert "brand-text-tesla" not in up     # not the muddy red class
        assert 'class="delta-up"' in up         # direction survives dark mode
        down = render_tsla_price_block("**TSLA today:** $372.80 ▼ $5.20 (-1.4%)")
        assert "color:#111827" in down
        assert 'class="delta-down"' in down


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

    def test_skips_decorative_subtitle_with_inline_bold(self):
        """Planetterrian's canonical .md emits a decorative subtitle
        line right under the title (``🌍 **Planetterrian Daily** -
        Science, Longevity & Health Discoveries``). The actual hook
        is below it. Without this skip, the subtitle was being
        promoted instead of the real hook (operator screenshot,
        2026-05-03)."""
        text = (
            "# Planetterrian Daily\n"
            "🌍 **Planetterrian Daily** - Science, Longevity & Health Discoveries\n"
            "\n"
            "A blood test for p-tau217 can predict Alzheimer's risk years before symptoms.\n"
            "\n"
            "---\n"
        )
        out = promote_hook_to_blockquote(text)
        # The subtitle line stays as-is — never wrapped.
        assert (
            "🌍 **Planetterrian Daily** - Science, Longevity & Health Discoveries"
            in out
        )
        assert "> **🌍" not in out
        # The real hook one line down IS wrapped.
        assert (
            "> **A blood test for p-tau217 can predict Alzheimer's risk years before symptoms.**"
            in out
        )
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

    def test_handles_source_post_prefix_bare_url(self):
        """May 14 2026: Short Spot lines use ``Source/Post:`` (not
        ``Source:``). Before the fix, those passed through unchanged
        and the 600-char Google News blob bled into the email body."""
        long_url = (
            "https://news.google.com/rss/articles/CBMivg" + "x" * 400
            + "?oc=5"
        )
        text = f"Short Spot body. Source/Post: {long_url}"
        out = shorten_source_urls(text)
        assert "Source/Post: [Google News]" in out
        # Prefix preserved (not silently rewritten to "Source:") so
        # downstream blog cite-pill rendering still distinguishes.
        assert "Source/Post:" in out
        # Original bare URL is no longer dangling after the prefix.
        assert f"Source/Post: {long_url}" not in out

    def test_handles_markdown_link_form(self):
        """Top 10 News items already arrive as ``Source: [Label](URL)``
        markdown. The label should be normalised to the URL's domain
        so the canonical form is the same as the bare-URL path."""
        long_url = (
            "https://news.google.com/rss/articles/CBMivg" + "x" * 400
            + "?oc=5"
        )
        text = f"Story body. Source: [Google News]({long_url})"
        out = shorten_source_urls(text)
        # Still labelled "Google News" (we collapse news.google.* to
        # the literal label).
        assert "[Google News]" in out
        # No raw bracketed-link with the long URL leaking through.
        # The output's markdown link still contains the URL but no
        # additional ``[Label]`` outside the link.
        assert out.count("[Google News]") == 1

    def test_handles_source_post_markdown_form(self):
        """Combined: ``Source/Post: [Label](URL)`` rare but possible."""
        text = (
            "Body. Source/Post: [insideevs.com]"
            "(https://insideevs.com/news/12345/story-path/)"
        )
        out = shorten_source_urls(text)
        assert "Source/Post: [insideevs.com]" in out
        assert "(https://insideevs.com/news/12345/story-path/)" in out

    def test_rewrites_markdown_label_to_domain(self):
        """A markdown-form Source with a verbose label (not a domain)
        gets the label rewritten to the URL's domain for consistency."""
        text = (
            "Body. Source: [Read more at this article]"
            "(https://insideevs.com/foo)"
        )
        out = shorten_source_urls(text)
        # Label collapses to the domain.
        assert "[insideevs.com]" in out
        assert "Read more at this article" not in out


class TestRenderSourceLinksAsHtml:
    """Email-stage: convert canonical ``Source: [label](url)``
    markdown into inline HTML ``<a>`` so Buttondown's markdown
    renderer doesn't choke on long Google News redirect URLs
    (operator caught May 14 2026: the markdown source rendered as
    visible text in Apple Mail, exposing the 600-char URL)."""

    def setup_method(self):
        from engine.newsletter_body import render_source_links_as_html
        self._html = render_source_links_as_html

    def test_converts_source_markdown_to_anchor(self):
        text = "Body. Source: [Google News](https://news.google.com/foo?oc=5)"
        out = self._html(text)
        assert 'href="https://news.google.com/foo?oc=5"' in out
        assert ">Google News</a>" in out
        # Original markdown syntax is gone.
        assert "[Google News]" not in out
        assert "](https://" not in out

    def test_converts_source_post_markdown_to_anchor(self):
        text = "Body. Source/Post: [news.google.com](https://news.google.com/x)"
        out = self._html(text)
        assert "Source/Post:" in out
        assert 'href="https://news.google.com/x"' in out
        assert ">news.google.com</a>" in out

    def test_includes_security_attributes(self):
        """Every Source link must open in a new tab without leaking
        the referrer (rel=noopener)."""
        text = "Source: [insideevs.com](https://insideevs.com/foo)"
        out = self._html(text)
        assert 'target="_blank"' in out
        assert 'rel="noopener"' in out

    def test_idempotent(self):
        text = "Source: [example.com](https://example.com/foo)"
        once = self._html(text)
        twice = self._html(once)
        assert once == twice

    def test_no_match_returns_unchanged(self):
        text = "Body with no source line at all."
        assert self._html(text) == text

    def test_leaves_other_markdown_links_alone(self):
        """The regex anchors on ``Source:`` / ``Source/Post:`` —
        random markdown links elsewhere in the body must pass
        through untouched."""
        text = (
            "See the [latest update](https://example.com/x) for details. "
            "Source: [news.google.com](https://news.google.com/y)"
        )
        out = self._html(text)
        # Source line converted.
        assert 'href="https://news.google.com/y"' in out
        # Random markdown link still in markdown form.
        assert "[latest update](https://example.com/x)" in out


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


# ---------------------------------------------------------------------------
# TSLA-arrow contrast guard (May 6 2026 — operator caught hard-block fire)
# ---------------------------------------------------------------------------

class TestTeslaArrowAaGuard:
    """Both arrow colors must clear WCAG AA (4.5:1) on the price
    block's neutral `#f8fafc` card background so the newsletter contrast
    hard-block doesn't fire on any future TST send. Pin the arrow
    colors AND the AA result so a future palette tweak can't drop
    below the threshold without CI flagging it. (Surface moved from the
    old red-tinted cream to a neutral card in Jun 2026 — the muddy
    red-price-on-red-tint down-day render, Ep502.)"""

    CREAM_BG = "#f8fafc"

    def _ratio(self, fg, bg):
        from engine.contrast_validator import contrast_ratio
        def _rgb(h):
            h = h.lstrip("#")
            return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        return contrast_ratio(_rgb(fg), _rgb(bg))

    def test_up_arrow_color_clears_aa_on_price_block(self):
        text = "**TSLA today:** $390.82 ▲ $9.44 (2.5%)"
        out = render_tsla_price_block(text)
        import re
        # Span surrounding the arrow carries the color. The render
        # places the color span BEFORE the arrow text, so search
        # backward from the ▲ for the nearest preceding ``color:#...``.
        i = out.find("▲")
        assert i >= 0, f"▲ not found: {out[:200]}"
        m = re.search(r"color:(#[0-9a-fA-F]{6})[^>]*>[^<]*$", out[:i])
        assert m, f"up arrow color not found near ▲: {out[max(0,i-200):i]!r}"
        ratio = self._ratio(m.group(1), self.CREAM_BG)
        assert ratio >= 4.5, (
            f"Up arrow {m.group(1)} measures {ratio:.2f}:1 on cream — "
            f"would trigger newsletter contrast hard-block."
        )

    def test_down_arrow_color_clears_aa_on_price_block(self):
        text = "**TSLA today:** $372.80 ▼ $5.20 (-1.4%)"
        out = render_tsla_price_block(text)
        import re
        i = out.find("▼")
        assert i >= 0, f"▼ not found: {out[:200]}"
        m = re.search(r"color:(#[0-9a-fA-F]{6})[^>]*>[^<]*$", out[:i])
        assert m, f"down arrow color not found near ▼: {out[max(0,i-200):i]!r}"
        ratio = self._ratio(m.group(1), self.CREAM_BG)
        assert ratio >= 4.5, (
            f"Down arrow {m.group(1)} measures {ratio:.2f}:1 on cream — "
            f"would trigger newsletter contrast hard-block."
        )
