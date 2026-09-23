"""Soft Personal interest form — Sep 2026 SpaceX Daily hero funnel.

Copy SoT: WED-clip3 Soft Personal section (CMO PASS). Not a waitlist;
optional email capture for tips/reminder. Paid join stays on /join.html.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


class TestSoftPersonalInterestPage:
    def test_generator_and_template_exist(self):
        import generate_html as gh

        assert hasattr(gh, "generate_personal_interest_page")
        assert (ROOT / "templates" / "personal_interest_page.html.j2").exists()

    def test_sitemap_lists_the_page(self):
        src = _read("generate_html.py")
        assert '"personal-interest.html"' in src

    def test_wired_into_all_and_network_and_static(self):
        src = _read("generate_html.py")
        assert src.count("generate_personal_interest_page(") >= 3

    def test_copy_sot_header_body_confirmation(self):
        src = _read("templates/personal_interest_page.html.j2")
        assert "Your own morning show — when you’re ready" in src
        assert "All 18 Nerra shows stay free. Personal is optional" in src
        assert "SpaceX Daily included" in src
        assert "Want a quiet nudge with Personal tips" in src
        assert "No ads. No outrage diet. Curiosity only." in src
        assert "You’re on the list. Shows stay free either way." in src
        assert "cancel anytime" in src.lower() or "cancel anytime" in src

    def test_fields_and_buttons(self):
        src = _read("templates/personal_interest_page.html.j2")
        assert 'id="spi-email"' in src and "required" in src
        assert 'id="spi-name"' in src
        assert "I’m interested in Nerra Personal" in src
        assert "I’d like the free SpaceX Daily / network newsletter too" in src
        assert "Save my email" in src
        assert "Or start Personal now →" in src
        assert "join.html" in src

    def test_posts_to_personal_interest_list(self):
        src = _read("templates/personal_interest_page.html.j2")
        assert 'list = interested ? "personal-interest" : "member"' in src
        assert 'API_BASE = "https://api.nerranetwork.com"' in src
        assert 'API_BASE + "/api/subscribe"' in src
        assert 'tags.push("SpaceX Daily")' in src

    def test_no_scarcity_or_episode_totals(self):
        src = _read("templates/personal_interest_page.html.j2")
        banned = (
            "waitlist", "closing soon", "spots left", "limited time",
            "you're missing", "missing out", "FOMO", "last chance",
            "total_episodes", "episodes published",
        )
        lower = src.lower()
        for phrase in banned:
            assert phrase.lower() not in lower, phrase

    def test_join_page_links_soft_capture(self):
        src = _read("templates/join_page.html.j2")
        assert "personal-interest.html" in src
        assert "quiet nudge" in src.lower()

    def test_worker_owns_the_list(self):
        handlers = _read("workers/gallery/src/handlers.ts")
        assert '"personal-interest": ["personal-interest", "nerra-member"' in handlers
        assert "honeypot" in handlers.lower() or "company" in handlers

    def test_generator_does_not_inject_episode_totals(self):
        src = _read("generate_html.py")
        # Find the Soft Personal generator body and assert it pops totals.
        start = src.index("def generate_personal_interest_page")
        body = src[start:start + 1200]
        assert "total_episodes" in body
        assert "ctx.pop(\"total_episodes\"" in body or "ctx.pop('total_episodes'" in body
