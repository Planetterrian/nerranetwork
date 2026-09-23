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

    def test_brand_error_copy(self):
        src = _read("templates/personal_interest_page.html.j2")
        assert (
            "That email doesn’t look right. Try again, or start Personal "
            "now at nerranetwork.com/join."
        ) in src
        assert (
            "Couldn’t save that just now. Try again in a moment — or start "
            "Personal whenever you’re ready at nerranetwork.com/join."
        ) in src
        # Superseded informal strings must not return.
        assert "Please enter a valid email address." not in src
        assert "Please try again in a moment." not in src

    def test_posts_to_personal_interest_list(self):
        src = _read("templates/personal_interest_page.html.j2")
        assert 'list = interested ? "personal-interest" : "member"' in src
        assert 'API_BASE = "https://api.nerranetwork.com"' in src
        assert 'API_BASE + "/api/subscribe"' in src
        assert 'tags.push("SpaceX Daily")' in src
        assert "newsletter: !!newsletter" in src

    def test_never_auto_charges_personal(self):
        src = _read("templates/personal_interest_page.html.j2")
        assert "stripe" not in src.lower()
        assert "STRIPE" not in src
        handlers = _read("workers/gallery/src/handlers.ts")
        assert "Never creates a paid Personal subscription" in handlers
        # Soft Personal SoT: interest segment only — no forced gallery tag.
        assert '"personal-interest": ["personal-interest"]' in handlers
        assert '"personal-interest": ["personal-interest", SUBSCRIBER_TAG]' not in handlers

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
        # ENG-SPEC: interest block above Stripe plans (does not replace checkout)
        assert 'id="soft-interest"' in src
        assert 'id="plans"' in src
        soft_at = src.index('id="soft-interest"')
        plans_at = src.index('id="plans"')
        assert soft_at < plans_at

    def test_worker_owns_the_list(self):
        handlers = _read("workers/gallery/src/handlers.ts")
        assert '"personal-interest": ["personal-interest"]' in handlers
        assert "networkNewsletter" in handlers
        assert "honeypot" in handlers.lower() or "company" in handlers
        # Unknown list must keep falling back to gallery — that fallthrough
        # is what made undeployed Workers write gallery-subscriber only.
        assert 'DEFAULT_LIST = "gallery"' in handlers

    def test_generator_does_not_inject_episode_totals(self):
        src = _read("generate_html.py")
        # Find the Soft Personal generator body and assert it pops totals.
        start = src.index("def generate_personal_interest_page")
        body = src[start:start + 1200]
        assert "total_episodes" in body
        assert "ctx.pop(\"total_episodes\"" in body or "ctx.pop('total_episodes'" in body


class TestSoftPersonalSurfaceCTAs:
    """Home + SpaceX were join-only; Soft interest must be clearly available."""

    def test_macro_owns_the_copy(self):
        src = _read("templates/_macros.html.j2")
        assert "macro soft_personal_interest" in src
        assert "personal-interest.html" in src
        assert "Not ready to pay?" in src
        assert "Shows stay free either way" in src
        # Must not imply a charge from the soft path.
        lower = src.lower()
        for banned in ("$4.99", "stripe", "start checkout", "subscribe now"):
            # The macro body itself (not the whole file) — soft_personal block.
            start = src.index("macro soft_personal_interest")
            body = src[start:start + 1800].lower()
            assert banned not in body, banned

    def test_home_personal_promo_offers_soft_interest(self):
        src = _read("templates/network_page.html.j2")
        assert "soft_personal_interest" in src
        assert 'id="personal-promo"' in src
        promo = src.split('id="personal-promo"', 1)[1][:3500]
        assert "personal-interest.html" in promo or "soft_personal_interest" in promo
        assert "join.html" in promo  # paid path remains

    def test_footer_no_longer_join_only(self):
        src = _read("templates/base.html.j2")
        assert "personal-interest.html" in src
        assert "Soft Personal" in src
        assert "no charge" in src.lower()
        assert "Or start Nerra Personal" in src

    def test_spacex_registry_gates_soft_cta(self):
        import yaml as _yaml
        registry = _yaml.safe_load(
            (ROOT / "shows" / "network_meta.yaml").read_text()
        )
        flagged = {
            slug for slug, cfg in registry.items()
            if isinstance(cfg, dict) and cfg.get("soft_personal_cta")
        }
        assert flagged == {"spacex"}

    def test_blog_index_and_show_page_wire_the_band(self):
        blog = _read("templates/blog_index.html.j2")
        show = _read("templates/show_page.html.j2")
        assert "soft_personal_interest" in blog
        assert "soft_personal_cta" in blog
        assert "soft_personal_interest" in show
        assert "soft_personal_cta" in show

    def test_rendered_home_and_spacex_surfaces(self):
        home = _read("index.html")
        assert 'id="personal-promo"' in home
        promo = home.split('id="personal-promo"', 1)[1][:4000]
        assert "personal-interest.html" in promo
        assert "Not ready to pay?" in promo

        spacex = _read("spacex.html")
        assert "personal-interest.html" in spacex
        assert 'id="soft-personal"' in spacex or 'id="soft-interest"' in spacex

        blog = _read("blog/spacex/index.html")
        assert "personal-interest.html" in blog
        assert "Shows stay free either way" in blog
        # Soft copy must not imply payment.
        soft = blog.lower()
        assert "no charge" in soft or "not ready to pay" in soft
        assert "waitlist" not in soft
