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
