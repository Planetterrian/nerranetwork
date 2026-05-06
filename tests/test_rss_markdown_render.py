"""Tests for engine.publisher._markdown_to_rss_html — converts the
podcast-script markdown to lightweight HTML before publishing in the
``<description>`` and ``<itunes:summary>`` of each RSS item.

Operator caught (May 6 2026 audit) Apple Podcasts and Spotify
rendering ``**HOOK:**`` / ``## Top stories`` literally on episode
list pages, which looked broken to anyone browsing podcast apps.
"""

from __future__ import annotations

from engine.publisher import _markdown_to_rss_html


class TestMarkdownToRssHtml:

    def test_strips_block_headers(self):
        out = _markdown_to_rss_html("# Tesla Shorts Time\n\nBody paragraph.")
        assert "#" not in out
        assert "Tesla Shorts Time" in out
        assert "Body paragraph." in out

    def test_converts_bold_to_b_tag(self):
        out = _markdown_to_rss_html("**Hook line.**\n\nBody.")
        assert "<b>Hook line.</b>" in out
        assert "**" not in out

    def test_converts_italic_to_i_tag(self):
        out = _markdown_to_rss_html("*Emphasis* in prose.")
        assert "<i>Emphasis</i>" in out

    def test_converts_markdown_links_to_anchors(self):
        out = _markdown_to_rss_html(
            "Read [the source](https://example.com/article) for details."
        )
        assert '<a href="https://example.com/article">the source</a>' in out

    def test_strips_blockquote_markers(self):
        out = _markdown_to_rss_html("> **Tesla unveils Cybertruck.**\n\nBody.")
        # Markdown blockquote prefix gone; HTML tags survive.
        assert not out.lstrip().startswith(">")
        assert "<b>Tesla unveils Cybertruck.</b>" in out

    def test_converts_list_markers_to_bullets(self):
        out = _markdown_to_rss_html("- First item\n- Second item")
        assert "• First item" in out
        assert "• Second item" in out

    def test_strips_horizontal_rules(self):
        out = _markdown_to_rss_html("Top\n\n---\n\nBottom")
        assert "---" not in out
        assert "Top" in out and "Bottom" in out

    def test_paragraph_wrapping_preserved(self):
        out = _markdown_to_rss_html("Para one.\n\nPara two.\n\nPara three.")
        # Paragraphs separated by blank lines.
        assert out.count("\n\n") == 2

    def test_empty_input_returns_empty(self):
        assert _markdown_to_rss_html("") == ""

    def test_already_clean_text_passes_through(self):
        out = _markdown_to_rss_html("Just plain text with no markdown.")
        assert out == "Just plain text with no markdown."

    def test_realistic_tesla_digest_block(self):
        """Typical TST digest snippet ships into RSS — confirm the
        rendered output reads cleanly without literal markdown."""
        md = (
            "# Tesla Shorts Time\n"
            "**REAL-TIME TSLA price:** $390.82\n"
            "\n"
            "> **Tesla unveils robotaxi service in three Texas cities.**\n"
            "\n"
            "## Top 10 News Items\n"
            "1. WattEV ordered 370 Tesla Semis.\n"
            "2. Tesla recalls 218K vehicles.\n"
        )
        out = _markdown_to_rss_html(md)
        assert "**" not in out
        assert "##" not in out
        assert "#" not in out.split("\n\n")[0]  # first paragraph clean
        assert "<b>REAL-TIME TSLA price:</b>" in out
        assert "<b>Tesla unveils robotaxi" in out
        assert "WattEV ordered 370 Tesla Semis." in out
