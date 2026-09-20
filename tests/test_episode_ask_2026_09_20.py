"""Drift guards for engine.episode_ask — SpaceX Ask B (Sep 2026).

Pins the exact hero-week paste copy, the Ep-99 gate, the RSS footer
wiring, and the blog-template mount so a future edit cannot drop Ask B
from one surface while leaving it on the other.
"""

from __future__ import annotations

from pathlib import Path

from engine.episode_ask import (
    SHOW_EPISODE_ASKS,
    episode_ask_for,
    episode_ask_markdown,
)
from engine.publisher import build_show_notes_footer, _markdown_to_rss_html

REPO = Path(__file__).resolve().parents[1]

_ASK_B_P1 = (
    "Enjoyed this episode? A rating or short review on Apple Podcasts or "
    "Spotify helps SpaceX Daily reach the next listener who wants the same "
    "thing: sourced updates, zero ads, no outrage diet."
)
_ASK_B_P2 = (
    "SpaceX Daily is part of Nerra Network — 18 ad-free shows, most of them daily."
)


class TestSpaceXAskBCopy:
    def test_spacex_registered_from_ep99(self):
        cfg = SHOW_EPISODE_ASKS["spacex"]
        assert cfg["min_episode"] == 99
        assert cfg["paragraphs"] == [_ASK_B_P1, _ASK_B_P2]

    def test_gate_before_ep99(self):
        assert episode_ask_for("spacex", 98) is None
        assert episode_ask_markdown("spacex", 98) == ""

    def test_gate_from_ep99(self):
        ask = episode_ask_for("spacex", 99)
        assert ask is not None
        assert ask["paragraphs"] == [_ASK_B_P1, _ASK_B_P2]
        md = episode_ask_markdown("spacex", 105)
        assert _ASK_B_P1 in md
        assert _ASK_B_P2 in md
        assert "\n\n" in md

    def test_other_shows_are_noop(self):
        assert episode_ask_for("tesla", 610) is None
        assert episode_ask_for("offshore_north", 5) is None


class TestAskBInShowNotesFooter:
    BASE = "https://nerranetwork.com"

    def test_spacex_ep99_leads_with_ask(self):
        out = build_show_notes_footer(self.BASE, "spacex", 99, has_blog=True)
        assert out.startswith(_ASK_B_P1)
        assert _ASK_B_P2 in out
        assert f"{self.BASE}/blog/spacex/ep099.html" in out
        assert "Nerra Network" in out

    def test_spacex_ep98_has_no_ask(self):
        out = build_show_notes_footer(self.BASE, "spacex", 98, has_blog=True)
        assert "outrage diet" not in out
        assert f"{self.BASE}/blog/spacex/ep098.html" in out

    def test_tesla_footer_unchanged_shape(self):
        out = build_show_notes_footer(self.BASE, "tesla", 610, has_blog=True)
        assert "outrage diet" not in out
        assert out.startswith("📝 Full show notes")

    def test_ask_survives_empty_base_url(self):
        """A missing base_url must not silence the rating CTA."""
        out = build_show_notes_footer("", "spacex", 99, has_blog=True)
        assert _ASK_B_P1 in out
        assert _ASK_B_P2 in out
        assert "/blog/" not in out

    def test_ask_renders_as_plain_prose_in_rss_html(self):
        footer = build_show_notes_footer(self.BASE, "spacex", 99, has_blog=True)
        rendered = _markdown_to_rss_html("Body.\n\n" + footer)
        assert _ASK_B_P1 in rendered
        assert _ASK_B_P2 in rendered
        assert f'<a href="{self.BASE}/blog/spacex/ep099.html">' in rendered


class TestAskBBlogTemplateWiring:
    def test_template_mounts_episode_ask(self):
        tpl = (REPO / "templates" / "blog_post.html.j2").read_text(encoding="utf-8")
        assert "episode_ask" in tpl
        assert "episode_ask.paragraphs" in tpl
        assert "engine.episode_ask" in tpl

    def test_blog_context_passes_episode_ask(self):
        src = (REPO / "engine" / "blog.py").read_text(encoding="utf-8")
        assert "episode_ask_for" in src
        assert '"episode_ask": episode_ask_for(show_slug, ep_num)' in src

    def test_live_ep099_blog_carries_ask(self):
        """Ep 99 was the hero-week paste target — keep it in the committed HTML."""
        html = (REPO / "blog" / "spacex" / "ep099.html").read_text(encoding="utf-8")
        assert "episode-ask" in html
        assert _ASK_B_P1 in html
        assert _ASK_B_P2 in html

    def test_live_ep098_blog_has_no_ask(self):
        html = (REPO / "blog" / "spacex" / "ep098.html").read_text(encoding="utf-8")
        assert "outrage diet" not in html
