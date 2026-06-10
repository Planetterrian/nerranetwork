"""Tests for engine.blog — focused on the surfaces a reader sees.

The most important contract: speech tags ([pause], <emphasis>, etc.)
that exist in the TTS script for the audio engine must NEVER reach
the rendered blog HTML, because readers don't have an audio engine to
consume them — they'd see literal "[pause]" / "<emphasis>" text.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock


class TestBlogTranscriptStripsTags:
    """``generate_blog_post_html`` reads the ``_tts.txt`` file and
    passes it to the template as ``transcript``. The TTS script carries
    Grok speech tags — strip before the template sees the string."""

    def test_blog_transcript_has_no_pause_tag(self, tmp_path: Path):
        from engine.blog import generate_blog_post_html

        # Lay down a digest .md and a paired _tts.txt with tags.
        digest_md = tmp_path / "Tesla_Shorts_Time_Pod_Ep458_20260502.md"
        digest_md.write_text(
            "# Tesla Shorts Time\n\n**HOOK:** Test hook.\n\nBody content.\n",
            encoding="utf-8",
        )
        tts_txt = tmp_path / "Tesla_Shorts_Time_Pod_Ep458_20260502_tts.txt"
        tts_txt.write_text(
            "Welcome to the show. [breath]\n"
            "Today's lead story is exciting. [pause]\n"
            "And here's why it matters: <emphasis>scale</emphasis>.\n"
            "[long-pause]\n"
            "That's all for today.\n",
            encoding="utf-8",
        )

        # Capture what reaches the template.
        captured: dict = {}

        class FakeTemplate:
            def render(self, **kwargs):
                captured.update(kwargs)
                return "<html>rendered</html>"

        fake_env = MagicMock()
        fake_env.get_template.return_value = FakeTemplate()

        metadata = {
            "title": "Test",
            "date_iso": "2026-05-02",
            "date": "May 2, 2026",
            "episode_num": 458,
            "hook": "Test hook.",
            "source_urls": [],
            "_md_path": str(digest_md),
        }
        show_config = {
            "slug": "tesla",
            "name": "Tesla Shorts Time",
            "rss_link": "https://nerranetwork.com/tesla.rss",
            "brand_color": "#E31937",
            "brand_color_dark": "#FF4D4D",
            "theme_color": "#E31937",
            "podcast_image": "tesla.png",
            "description": "Daily Tesla podcast",
            "meta_keywords": "tesla, ev",
        }

        generate_blog_post_html(
            digest_md.read_text(encoding="utf-8"),
            metadata,
            show_config,
            fake_env,
        )

        transcript = captured.get("transcript", "")
        assert "[breath]" not in transcript
        assert "[pause]" not in transcript
        assert "[long-pause]" not in transcript
        assert "<emphasis>" not in transcript
        assert "</emphasis>" not in transcript
        # Inner prose preserved (only brackets stripped on wrapping tags).
        assert "scale" in transcript
        assert "Today's lead story is exciting." in transcript


class TestExtractBlogMetadataHook:
    """Hook extraction must keep up with the canonical .md format
    changes. After PR #292:

      - ``**HOOK:**`` label is scrubbed
      - Hook prose is wrapped as ``> **<text>**`` blockquote
      - TSLA price stays as ``**REAL-TIME TSLA price:** ...``

    The previous extractor fell back to "first long content line",
    which picked the TSLA price (Tesla) or the literal ``> **<hook>**``
    string with leading ``>`` (other shows). Operator screenshots
    showed both bugs in production on 2026-05-03.
    """

    def setup_method(self):
        from engine.blog import extract_blog_metadata
        self._extract = extract_blog_metadata

    def test_blockquote_hook_is_extracted_clean(self):
        """The new ``> **<text>**`` form (PR #292) extracts the inner
        text without the ``>`` or ``**`` decorations."""
        md = (
            "# Tesla Shorts Time\n"
            "**REAL-TIME TSLA price:** $390.82 ▲ $9.44 (2.5%)\n"
            "> **Tesla has started high-volume production of the Semi.**\n"
            "\n"
            "---\n"
            "### Top 10 News Items\n"
        )
        meta = self._extract(md, "tesla", "Tesla_Shorts_Time_Pod_Ep460_20260502.md")
        assert meta["hook"] == "Tesla has started high-volume production of the Semi."

    def test_tsla_price_line_is_never_the_hook(self):
        """Listing card preview must not show the TSLA price line
        (operator screenshot 5)."""
        md = (
            "# Tesla Shorts Time\n"
            "**REAL-TIME TSLA price:** $390.82 ▲ $9.44 (2.5%)\n"
            "\n"
            "---\n"
            "Some other prose that's long enough to qualify.\n"
        )
        meta = self._extract(md, "tesla", "Tesla_Shorts_Time_Pod_Ep461_20260503.md")
        assert "TSLA price" not in (meta["hook"] or "")
        assert "$390" not in (meta["hook"] or "")

    def test_legacy_html_table_hook_is_html_stripped(self):
        """Legacy episodes (pre-PR #292) had inline ``<table>`` HTML for
        the TSLA price. Without sanitization the literal ``<table>``
        landed in the listing card preview, and because Jinja runs
        with ``autoescape=False`` the unclosed tag swallowed every
        subsequent card (operator screenshot 3 — outer red border)."""
        md = (
            "# Tesla Shorts Time\n"
            "<table role=\"presentation\" class=\"surface-tsla\">"
            "<tr><td>$390.82 ▲ $9.44</td></tr></table>\n"
            "The final Model X to roll off the line carries a hidden tribute.\n"
            "<hr style=\"border:none;\" />\n"
        )
        meta = self._extract(md, "tesla", "Tesla_Shorts_Time_Pod_Ep459_20260502.md")
        # Hook MUST NOT contain raw HTML.
        assert "<table" not in (meta["hook"] or "")
        assert "<tr" not in (meta["hook"] or "")
        assert "<td" not in (meta["hook"] or "")
        # And it should pick the actual prose line below the table.
        assert "Model X" in (meta["hook"] or "")

    def test_decorative_subtitle_skipped_for_hook(self):
        """Planetterrian's subtitle line (``🌍 **Planetterrian Daily**
        - ...``) was being picked as the hook. The actual hook
        (below it) is what should appear in the listing card
        (operator screenshot 4)."""
        md = (
            "# Planetterrian Daily\n"
            "🌍 **Planetterrian Daily** - Science, Longevity & Health Discoveries\n"
            "> **A blood test for p-tau217 predicts Alzheimer's risk years early.**\n"
            "---\n"
        )
        meta = self._extract(md, "planetterrian", "Planetterrian_Daily_Ep054_20260503.md")
        # The blockquote pattern should match the actual hook.
        assert (
            meta["hook"]
            == "A blood test for p-tau217 predicts Alzheimer's risk years early."
        )

    def test_hook_does_not_carry_leading_blockquote_marker(self):
        """Defense — even if the blockquote pattern misses, the
        fallback must not leak a literal ``>`` into the preview
        (operator screenshot 4)."""
        md = (
            "# Models & Agents\n"
            "> Mistral AI launches a 128B model with remote agents.\n"
            "\n"
            "Other prose that's long enough.\n"
        )
        meta = self._extract(md, "models_agents", "Models_Agents_Ep039_20260503.md")
        # If we extracted anything, it doesn't start with the literal ``>``.
        assert not (meta["hook"] or "").startswith(">")


class TestAIDisclosureProviderAgnostic:
    """The AI disclosure is appended to every podcast script (read aloud)
    AND to the RSS show notes. It must not name a specific TTS provider —
    the network has migrated providers twice in 2026 and both old
    disclosures broadcast misinformation until caught."""

    def test_spoken_disclosure_does_not_mention_specific_provider(self):
        from run_show import _AI_DISCLOSURE
        # Network was on ElevenLabs Jan-May 2026, then Grok TTS network-wide.
        # Disclosure should be provider-agnostic for forward compat.
        assert "ElevenLabs" not in _AI_DISCLOSURE
        assert "Grok" not in _AI_DISCLOSURE
        assert "xAI" not in _AI_DISCLOSURE
        # Still mentions it's AI-generated (the disclosure's whole purpose).
        assert "AI voice synthesis" in _AI_DISCLOSURE

    def test_rss_disclosure_does_not_mention_specific_provider(self):
        from run_show import _AI_DISCLOSURE_RSS
        assert "ElevenLabs" not in _AI_DISCLOSURE_RSS
        assert "Grok" not in _AI_DISCLOSURE_RSS
        assert "AI Disclosure" in _AI_DISCLOSURE_RSS


class TestCitationHoverCards:
    """Phase 3.4 of the May 2026 audit — bare ``Source: <url>`` lines
    in the digest now render as a small pill showing the publisher
    domain, with a CSS-only hover/focus popover that reveals the full
    URL. Pure CSS, no JS — works everywhere the page stylesheet runs."""

    def test_md_inline_renders_source_url_as_cite_pill(self):
        from engine.blog import _md_inline

        out = _md_inline(
            "Some claim. Source: https://example.com/article/path?q=1"
        )
        # The visible chip + its popover wrapper.
        assert 'class="cite-pill"' in out
        assert 'class="cite-card"' in out
        # ARIA wiring: the pill describes the popover so screen readers
        # announce the full URL on focus.
        assert 'aria-describedby="cite-card"' in out
        assert 'role="tooltip"' in out
        # Domain shown inline (no scheme, no trailing path).
        assert ">example.com<" in out
        # Full URL preserved INSIDE the popover for verification.
        assert "https://example.com/article/path?q=1" in out
        # Pill is still a real link — opens in new tab, no referrer leak.
        assert 'target="_blank"' in out
        assert 'rel="noopener"' in out

    def test_md_inline_strips_www_from_pill_label(self):
        from engine.blog import _md_inline

        out = _md_inline("Source: https://www.bbc.co.uk/news/world-12345")
        # Pill label drops "www." — but the full URL stays intact in
        # the cite-card.
        assert ">bbc.co.uk<" in out
        assert "https://www.bbc.co.uk/news/world-12345" in out

    def test_md_inline_leaves_other_inline_markdown_untouched(self):
        from engine.blog import _md_inline

        out = _md_inline(
            "**Bold** and *italic* and [link](https://x.com). "
            "Source: https://example.com/page"
        )
        assert "<strong>Bold</strong>" in out
        assert "<em>italic</em>" in out
        # Markdown link preserved as a normal anchor.
        assert '<a href="https://x.com"' in out
        # Cite pill still rendered for the bare Source: URL.
        assert 'class="cite-pill"' in out

    def test_md_inline_renders_source_post_url_as_cite_pill(self):
        """The Short Spot section in the Tesla digest uses
        ``Source/Post:`` (not ``Source:``) for its citation line.
        Before May 14 2026 the cite-pill regex only matched
        ``Source:``, so Short Spot's URL bled into the rendered HTML
        as a raw token stream — operator caught a Google News redirect
        URL spilling across the Tesla blog (Ep472)."""
        from engine.blog import _md_inline

        out = _md_inline(
            "**Spot title.** Some text describing the issue. "
            "Source/Post: https://news.google.com/rss/articles/CBMiabc123?oc=5"
        )
        # The cite-pill structure renders just like Source: lines.
        assert 'class="cite-pill"' in out
        assert 'class="cite-card"' in out
        # Pill label is the domain only — no raw URL bleed in visible text.
        assert ">news.google.com<" in out
        # Full URL is preserved inside the popover for verification.
        assert "news.google.com/rss/articles/CBMiabc123?oc=5" in out
        # The literal "Source/Post:" prefix stays before the pill.
        assert "Source/Post:" in out


class TestCrossShowRelatedCuratedFirst:
    """The curated sibling (NETWORK_SHOWS[slug]['related_show']) must take
    the first cross-show rec slot when it has a recent post (June 2026
    growth pass)."""

    def _posts(self, *slugs):
        return [
            {"show_slug": s, "title": f"{s} post", "url": f"/blog/{s}/ep1.html"}
            for s in slugs
        ]

    def test_curated_sibling_takes_first_slot(self):
        from generate_html import NETWORK_SHOWS, _pick_cross_show_related

        curated = NETWORK_SHOWS["tesla"]["related_show"]
        pool = self._posts(
            "planetterrian", "models_agents", curated, "env_intel",
        )
        picked = _pick_cross_show_related("tesla", pool)
        assert picked, "expected non-empty recommendations"
        assert picked[0]["show_slug"] == curated
        assert len(picked) == 3

    def test_own_show_excluded_and_empty_pool_ok(self):
        from generate_html import _pick_cross_show_related

        assert _pick_cross_show_related("tesla", []) == []
        picked = _pick_cross_show_related("tesla", self._posts("tesla"))
        assert picked == []

    def test_every_curated_sibling_is_a_known_show(self):
        from generate_html import NETWORK_SHOWS

        for slug, meta in NETWORK_SHOWS.items():
            related = meta.get("related_show")
            if related:
                assert related in NETWORK_SHOWS, (
                    f"NETWORK_SHOWS[{slug}].related_show={related!r} unknown"
                )
