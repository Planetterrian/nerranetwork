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

    # Nov 9 2026 (operator: "Rework the ad landing page"): the page leads
    # with the product and its sample; the email form is the Nerra Daily
    # signup. The old "occasional Personal tips" promise is gone because no
    # send ever kept it.
    def test_the_product_and_its_sample_lead(self):
        src = _read("templates/personal_interest_page.html.j2")
        assert "Your shows, one private morning edition, read to you by name" in src
        assert "Every Nerra show stays free; Personal is optional." in src
        assert "SpaceX Daily included" in src
        assert src.index('id="sample"') < src.index('id="spi-form"')
        assert 'data-nn-sample="personal-interest"' in src
        assert "Build yours →" in src
        assert src.index("Build yours →") < src.index('id="spi-form"')
        assert "cancel anytime" in src.lower()
        assert "privacy-policy.html" in src

    def test_no_promise_of_tips_nobody_sends(self):
        src = _read("templates/personal_interest_page.html.j2").lower()
        assert "personal tips" not in src
        assert "reminder" not in src
        assert "when you’re ready" not in src and "when you're ready" not in src

    def test_fields_and_buttons(self):
        src = _read("templates/personal_interest_page.html.j2")
        assert 'id="spi-email"' in src and "required" in src
        assert 'id="spi-name"' in src
        assert "Not ready? Get the free Nerra Daily email" in src
        assert "Send me Nerra Daily" in src
        assert "join.html" in src
        assert "You’re on the list. Your first Nerra Daily arrives at 7:00 AM Eastern." in src

    def test_brand_error_copy(self):
        src = _read("templates/personal_interest_page.html.j2")
        assert "That email doesn’t look right. Try again." in src
        assert "Couldn’t save that just now. Try again in a moment." in src
        assert "Please enter a valid email address." not in src
        assert "Please try again in a moment." not in src

    def test_posts_a_nerra_daily_signup_on_the_personal_interest_list(self):
        src = _read("templates/personal_interest_page.html.j2")
        assert 'var list = "personal-interest";' in src
        assert 'var tags = ["SpaceX Daily"];' in src
        assert "newsletter: true," in src
        assert 'API_BASE = "https://api.nerranetwork.com"' in src
        assert 'API_BASE + "/api/subscribe"' in src
        # utm_source → src-* via the shared helper.
        assert "NNSubscribe.resolveSource" in src
        assert "SOURCE_DEFAULT" in src

    def test_the_worker_tags_it_for_nerra_daily(self):
        """list personal-interest + newsletter: true → personal-interest and
        nerra-member, the tag the one email goes to. No Worker change."""
        handlers = _read("workers/gallery/src/handlers.ts")
        assert '"personal-interest": ["personal-interest"]' in handlers
        assert "networkNewsletter: body?.newsletter === true" in handlers
        assert 'tags.push("nerra-member")' in handlers

    def test_submit_fires_the_ads_conversion_event(self):
        src = _read("templates/personal_interest_page.html.j2")
        assert (
            "fireSoftPersonalInterestSubmit" in src
            and 'gtag("event", "soft_personal_interest_submit"' in src
        )
        assert 'form_id: "personal-interest"' in src
        assert 'page_path: "/personal-interest.html"' in src
        assert '"newsletter_signup"' not in src
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
        assert "Get Personal tips by email — no charge, no card →" in src
        assert "Not ready yet?" not in src
        assert "Not ready to pay?" not in src
        assert "reminder" not in src.lower()
        # ENG-SPEC: interest block above Stripe plans (does not replace checkout)
        assert 'id="soft-interest"' in src
        assert 'id="plans"' in src
        soft_at = src.index('id="soft-interest"')
        plans_at = src.index('id="plans"')
        assert soft_at < plans_at
        # Oct 31 2026 (Patrick): free-account form above paid tiers — RSS
        # items promise "sources and notes by email, free" and must not
        # land the listener on the paid tier cards first. (Hero copy may
        # still mention $4.99; assert against the tier price markup.)
        assert 'id="join-free"' in src
        join_at = src.index('id="join-free"')
        assert soft_at < join_at < plans_at
        assert src.index('<p class="price">$4.99') > join_at
        assert src.index('<p class="price">$8.99') > join_at
        join_html = _read("join.html")
        assert join_html.index('id="join-free"') < join_html.index('id="plans"')
        assert join_html.index('id="join-free"') < join_html.index('<p class="price">$4.99')
        assert join_html.index('id="join-free"') < join_html.index('<p class="price">$8.99')
        assert 'data-success-redirect="account.html"' in join_html
        assert join_html.count('id="join-free"') == 1

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
        assert "Get Personal tips by email — no charge, no card →" in join_tpl
        assert "Not ready yet?" not in join_tpl
        assert "Not ready to pay?" not in join_tpl
        assert "Soft Personal" not in join_tpl

        join = _read("join.html")
        daily = _read("nerra-daily.html")
        assert "Not ready to pay?" not in join
        assert "Not ready to pay?" not in daily
        assert "Soft Personal" not in join
        assert "Soft Personal" not in daily
        assert "Get Personal tips by email — no charge, no card →" in join
        assert "Not ready yet?" not in join
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
