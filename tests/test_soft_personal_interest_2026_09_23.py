"""Soft Personal interest form — Sep 2026 SpaceX Daily hero funnel.

Copy SoT: WED-clip3 Soft Personal section (CMO PASS). Not a waitlist;
optional email capture for tips/reminder. Paid join stays on /join.html.
"""
from __future__ import annotations

import re
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
        assert "Occasional Personal tips by email — no charge, no card" in src
        assert "when you’re ready" not in src
        assert "when you're ready" not in src
        assert "Every Nerra show stays free. Personal is optional" in src
        assert "SpaceX Daily included" in src
        assert "Want occasional Personal tips by email?" in src
        assert "No ads. No outrage diet. Curiosity only." in src
        assert "You’re on the list. Shows stay free either way." in src
        assert "We’ll only email you about Nerra Personal" in src
        assert "privacy-policy.html" in src
        assert "reminder" not in src.lower()
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
        assert "Couldn’t save that just now. Try again in a moment." in src
        assert "whenever you’re ready" not in src
        assert "whenever you're ready" not in src
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
        # utm_source → src-* via the shared helper (never hardcode only
        # src-nerranetwork when a YouTube landing is present).
        assert "NNSubscribe.resolveSource" in src
        assert "SOURCE_DEFAULT" in src

    def test_soft_submit_fires_distinct_ga4_event(self):
        """Soft north star must not conflate with newsletter_signup."""
        src = _read("templates/personal_interest_page.html.j2")
        assert 'gtag("event", "soft_personal_interest_submit"' in src
        assert 'form_id: "personal-interest"' in src
        assert 'page_path: "/personal-interest.html"' in src
        # Soft success path: interested branch fires Soft event only.
        soft_start = src.index("if (interested)")
        else_at = src.index("} else {", soft_start)
        soft_block = src[soft_start:else_at]
        assert "soft_personal_interest_submit" in soft_block
        assert "newsletter_signup" not in soft_block
        # Newsletter-only (Soft unchecked) may still use newsletter_signup.
        news_block = src[else_at:else_at + 350]
        assert "newsletter_signup" in news_block
        assert "soft_personal_interest_submit" not in news_block
        # Event must not collide with gallery / join CTA names.
        for banned in (
            "gallery_subscribe", "generate_lead", "select_personal_upsell",
        ):
            assert banned not in src

    def test_soft_event_is_fetched_not_as_conversion(self):
        """A result key is not a metric until the fetcher asks for it —
        and Soft must never inflate newsletter signup totals."""
        from scripts.fetch_ga4_stats import CONVERSION_EVENTS, ENGAGEMENT_EVENTS

        assert "soft_personal_interest_submit" in ENGAGEMENT_EVENTS
        assert "soft_personal_interest_submit" not in CONVERSION_EVENTS
        assert "newsletter_signup" in CONVERSION_EVENTS

    def test_funnel_exposes_soft_submits_null_when_unmeasured(self):
        from scripts.build_funnel import _soft_personal_submits

        assert _soft_personal_submits({})["total"] is None
        assert _soft_personal_submits({"site_events": None})["total"] is None
        assert _soft_personal_submits(None)["configured"] is False
        assert _soft_personal_submits({"site_events": []}) == {
            "configured": True, "total": 0, "by_page": {},
        }

    def test_funnel_counts_soft_submits_separately_from_upsell(self):
        from scripts.build_funnel import _soft_personal_submits, _upsell_clicks

        ga4 = {"site_events": [
            {"eventName": "soft_personal_interest_submit",
             "pagePath": "/personal-interest.html", "eventCount": "4"},
            {"eventName": "select_personal_upsell",
             "pagePath": "/nerra-daily.html", "eventCount": "7"},
            {"eventName": "newsletter_signup",
             "pagePath": "/personal-interest.html", "eventCount": "99"},
        ]}
        soft = _soft_personal_submits(ga4)
        assert soft["total"] == 4
        assert soft["by_page"] == {"/personal-interest.html": 4}
        # Upsell helper must ignore Soft events.
        assert _upsell_clicks(ga4)["total"] == 7

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
        assert "Get occasional Personal tips by email — no charge, no card." in src
        assert "Not ready yet? Get Personal tips by email — no charge, no card →" in src
        assert "Not ready to pay?" not in src
        assert "reminder" not in src.lower()
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
        assert "Get occasional Personal tips by email — no charge, no card" in src
        assert "Save my email on the Personal page →" in src
        start = src.index("macro soft_personal_interest")
        end = src.index("{%- endmacro -%}", start) + len("{%- endmacro -%}")
        body = src[start:end]
        assert "Not ready to pay?" not in body
        assert "reminder" not in body.lower()
        assert "Soft Personal" not in body
        # Must not imply a charge from the soft path.
        body_l = body.lower()
        for banned in ("$4.99", "stripe", "start checkout", "subscribe now", "4.99", "/mo"):
            assert banned not in body_l, banned

        hero_start = src.index("macro soft_personal_hero_band")
        hero_end = src.index("{%- endmacro -%}", hero_start) + len("{%- endmacro -%}")
        hero = src[hero_start:hero_end]
        assert "Get a quiet nudge with occasional Personal tips." in hero
        assert "We’ll only email you about Nerra Personal" in hero
        assert "privacy-policy.html" in hero
        assert "reminder" not in hero.lower()
        # User-visible Soft label must not appear (Jinja comments OK).
        visible = re.sub(r"\{#.*?#\}", "", hero, flags=re.S)
        assert "Soft Personal" not in visible
        assert "Save my email on the Soft" not in visible

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
        assert "Personal tips by email — no charge →" in src
        assert "Soft Personal" not in src
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
        # Upsell Soft line sits above the paid price line.
        assert "Not ready? Get free Personal tips by email — no charge, no card →" in show

    def test_join_and_nerra_daily_drop_pay_framing(self):
        join_tpl = _read("templates/join_page.html.j2")
        assert "Get occasional Personal tips by email — no charge, no card." in join_tpl
        assert "Save my email on the Personal page →" in join_tpl
        assert "Not ready yet? Get Personal tips by email — no charge, no card →" in join_tpl
        assert "Not ready to pay?" not in join_tpl
        assert "Soft Personal" not in join_tpl

        join = _read("join.html")
        daily = _read("nerra-daily.html")
        assert "Not ready to pay?" not in join
        assert "Not ready to pay?" not in daily
        assert "Soft Personal" not in join
        assert "Soft Personal" not in daily
        assert "Not ready yet? Get Personal tips by email — no charge, no card →" in join
        assert "Not ready? Get free Personal tips by email — no charge, no card →" in daily
        assert "Personal tips by email — no charge →" in join
        assert "Personal tips by email — no charge →" in daily

    def test_rendered_home_and_spacex_surfaces(self):
        home = _read("index.html")
        assert 'id="personal-promo"' in home
        promo = home.split('id="personal-promo"', 1)[1][:4000]
        assert "personal-interest.html" in promo
        assert "Get occasional Personal tips by email — no charge, no card" in promo
        assert "Not ready to pay?" not in promo
        assert "reminder" not in promo.lower()
        assert "Soft Personal" not in promo

        spacex = _read("spacex.html")
        assert "personal-interest.html" in spacex
        # One soft ask per page: since the Oct 7 site review the lower
        # soft-personal band renders only where no hero band already asks for
        # the same email (show_page.html.j2), so on SpaceX the hero IS the ask.
        assert 'id="soft-personal-hero"' in spacex
        assert 'id="soft-personal"' not in spacex
        # Soft hero band + soft_personal_interest CTA must share no-charge framing.
        assert "Not ready to pay?" not in spacex
        soft_hero = spacex[spacex.index('id="soft-personal-hero"'):
                           spacex.index("</section>", spacex.index('id="soft-personal-hero"'))]
        assert "No charge, no card" in soft_hero or "no charge, no card" in soft_hero
        assert "privacy-policy.html" in soft_hero
        assert "We’ll only email you about Nerra Personal" in soft_hero
        assert "reminder" not in soft_hero.lower()

        blog = _read("blog/spacex/index.html")
        assert "personal-interest.html" in blog
        # Soft copy must not imply payment (committed blog index; not regenerated here).
        soft = blog.lower()
        assert "no charge" in soft or "not ready to pay" in soft or "personal tips" in soft
        assert "waitlist" not in soft
