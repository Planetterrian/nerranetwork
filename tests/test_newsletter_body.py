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
