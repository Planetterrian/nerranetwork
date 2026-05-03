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
