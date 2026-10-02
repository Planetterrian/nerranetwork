"""Soft Personal hero capture + Worker newsletter forms (Sep 2026).

Backlog item 4: put a one-field Soft Personal form on the pages YouTube
actually lands on; map utm_source → src-* on every Worker capture form;
replace Buttondown popupwindow embeds so captures get attribution and
honest success/error (no fake 500ms "Check your email ✓").
"""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

HERO_SLUGS = (
    "fascinating_frontiers",
    "spacex",
    "tesla",
    "models_agents",
    "models_agents_beginners",
)


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _scrub_jinja_comments(src: str) -> str:
    return re.sub(r"\{#.*?#\}", "", src, flags=re.S)


class _FormCollector(HTMLParser):
    """Collect start-tag attrs for every <form> in a document."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms: list[dict[str, str | None]] = []

    def handle_starttag(self, tag, attrs):
        if tag == "form":
            self.forms.append(dict(attrs))


# ---------------------------------------------------------------------------
# Shared JS: utm → SOURCE_TAGS + Soft Personal contract
# ---------------------------------------------------------------------------


class TestSubscribeJsSourceMapping:
    def test_maps_youtube_utm_sources(self):
        js = _read("assets/js/footer-subscribe.js")
        for utm, tag in (
            ("youtube", "src-youtube"),
            ("youtube_ru", "src-youtube-ru"),
            ("youtube_fr", "src-youtube-fr"),
            ("podcast", "src-podcast"),
            ("newsletter", "src-newsletter"),
            ("x", "src-x"),
            ("nerranetwork", "src-nerranetwork"),
            ("facebook", "src-facebook"),
            ("linkedin", "src-linkedin"),
            ("whatsapp", "src-whatsapp"),
            ("telegram", "src-telegram"),
            ("email_share", "src-email-share"),
        ):
            assert f"{utm}:" in js or f"'{utm}':" in js or f'"{utm}":' in js
            assert tag in js

    def test_resolve_source_exported_and_prefers_utm(self):
        js = _read("assets/js/footer-subscribe.js")
        assert "function resolveSource" in js
        assert "utm_source" in js
        assert "NNSubscribe.resolveSource" in js
        # Must not hard-wire only src-nerranetwork when a YouTube utm is present.
        assert "UTM_SOURCE_TAGS[utm]" in js

    def test_source_map_matches_worker_allow_list(self):
        js = _read("assets/js/footer-subscribe.js")
        handlers = _read("workers/gallery/src/handlers.ts")
        # Every tag the client may emit must sit in SOURCE_TAGS.
        for tag in (
            "src-youtube", "src-youtube-ru", "src-youtube-fr",
            "src-podcast", "src-newsletter", "src-x", "src-nerranetwork",
            "src-facebook", "src-linkedin", "src-whatsapp",
            "src-telegram", "src-email-share",
        ):
            assert f'"{tag}"' in handlers, f"Worker missing {tag}"
            assert tag in js, f"client map missing {tag}"

    def test_soft_personal_requires_ok_true_before_ga(self):
        js = _read("assets/js/footer-subscribe.js")
        assert "soft_personal_interest_submit" in js
        assert "data.ok === true" in js or "r.data.ok === true" in js
        # Soft event must sit after the success gate, not before fetch.
        success_idx = js.index("r.data.ok === true") if "r.data.ok === true" in js else js.index("data.ok === true")
        ga_idx = js.index("soft_personal_interest_submit")
        assert ga_idx > success_idx

    def test_soft_personal_posts_personal_interest_list(self):
        js = _read("assets/js/footer-subscribe.js")
        assert "personal-interest" in js
        assert "company" in js  # honeypot field

    def test_no_fake_500ms_success(self):
        js = _read("assets/js/footer-subscribe.js")
        assert "setTimeout" not in js


class TestSoftPersonalPageUsesSharedSourceResolver:
    def test_page_calls_nnsubscribe_resolve_source(self):
        src = _read("templates/personal_interest_page.html.j2")
        assert "NNSubscribe.resolveSource" in src
        assert "SOURCE_DEFAULT" in src
        assert "capture_source_site" in src

    def test_still_fires_soft_event_only_on_ok_true(self):
        src = _read("templates/personal_interest_page.html.j2")
        assert 'r.data.ok !== true' in src or "r.data.ok !== true" in src
        assert 'gtag("event", "soft_personal_interest_submit"' in src


# ---------------------------------------------------------------------------
# Show page hero Soft Personal + Worker newsletter forms
# ---------------------------------------------------------------------------


class TestSoftPersonalHeroWiring:
    def test_closed_slug_set_in_generator(self):
        from generate_html import SOFT_PERSONAL_HERO_SLUGS

        assert set(SOFT_PERSONAL_HERO_SLUGS) == set(HERO_SLUGS)

    def test_generator_passes_flag_into_show_context(self):
        src = _read("generate_html.py")
        assert "soft_personal_hero" in src
        assert "SOFT_PERSONAL_HERO_SLUGS" in src

    def test_template_has_soft_personal_hero_form(self):
        src = _scrub_jinja_comments(_read("templates/show_page.html.j2"))
        assert "soft_personal_hero" in src
        assert 'data-nn-subscribe="soft-personal"' in src
        assert 'data-list="personal-interest"' in src
        assert 'name="company"' in src  # honeypot
        assert "Save my email" in src
        assert "Or start Personal now" in src
        # Soft hero is free interest only — no paid-price copy in the band.
        hero_start = src.index('id="soft-personal-hero"')
        hero_end = src.index("</section>", hero_start)
        hero = src[hero_start:hero_end]
        assert "Shows stay free either way." in hero
        assert "$4.99" not in hero
        assert "/mo" not in hero

    def test_show_page_has_no_buttondown_popup(self):
        src = _scrub_jinja_comments(_read("templates/show_page.html.j2"))
        assert "popupwindow" not in src
        assert "buttondown.com/api/emails/embed-subscribe" not in src
        assert "setTimeout" not in src

    def test_show_newsletter_forms_use_worker(self):
        src = _scrub_jinja_comments(_read("templates/show_page.html.j2"))
        assert 'data-nn-subscribe="show-hero"' in src or 'data-nn-subscribe="show-inline"' in src
        assert 'data-list="member"' in src
        assert "data-source=" in src
        assert "capture_source_site" in src


class TestBlogPostSubscribeIsWorkerBacked:
    def test_no_buttondown_popup_or_fake_timeout(self):
        src = _scrub_jinja_comments(_read("templates/blog_post.html.j2"))
        assert "popupwindow" not in src
        assert "buttondown.com/api/emails/embed-subscribe" not in src
        assert "setTimeout" not in src
        assert 'data-nn-subscribe="blog-cta"' in src
        assert 'data-list="member"' in src
        assert "capture_source_site" in src


# ---------------------------------------------------------------------------
# Rendered markup (fresh generate into tmp — never committed HTML)
# ---------------------------------------------------------------------------


def _render_show(slug: str, tmp_path) -> str:
    import generate_html as G
    import inspect

    sig = inspect.signature(G.generate_show_page)
    assert "output_dir" in sig.parameters, (
        "generate_show_page must accept output_dir= for this guard"
    )
    written = G.generate_show_page(slug, output_dir=str(tmp_path))
    assert written is not None
    return Path(written).read_text(encoding="utf-8")


class TestRenderedSoftPersonalHero:
    @pytest.mark.parametrize("slug", HERO_SLUGS)
    def test_hero_form_attributes(self, slug, tmp_path):
        html = _render_show(slug, tmp_path)

        parser = _FormCollector()
        parser.feed(html)
        soft = [
            f for f in parser.forms
            if f.get("data-nn-subscribe") == "soft-personal"
            or f.get("data-list") == "personal-interest"
        ]
        assert soft, f"{slug}: Soft Personal hero form missing from rendered HTML"
        form = soft[0]
        assert (form.get("method") or "").lower() == "post"
        assert form.get("data-list") == "personal-interest"
        assert (form.get("data-source") or "").startswith("src-")
        assert "onsubmit" not in form
        assert "popupwindow" not in (form.get("target") or "")
        # Script must be linked so utm mapping + Soft GA fire.
        assert "assets/js/footer-subscribe.js" in html
        assert "buttondown.com/api/emails/embed-subscribe" not in html
        assert 'target="popupwindow"' not in html

    @pytest.mark.parametrize("slug", HERO_SLUGS)
    def test_hero_band_has_no_paid_price_copy(self, slug, tmp_path):
        """Soft Personal is free interest; paid path is /join.html only."""
        html = _render_show(slug, tmp_path)
        hero_start = html.index('id="soft-personal-hero"')
        hero_end = html.index("</section>", hero_start)
        hero = html[hero_start:hero_end]
        assert "Shows stay free either way." in hero
        assert "$4.99" not in hero
        assert "/mo" not in hero
        assert "$4.99/mo when you want it" not in hero

    def test_non_hero_show_keeps_newsletter_worker_form_not_soft(self, tmp_path):
        import generate_html as G

        slug = "omni_view"
        assert slug not in G.SOFT_PERSONAL_HERO_SLUGS
        html = _render_show(slug, tmp_path)
        parser = _FormCollector()
        parser.feed(html)
        soft = [f for f in parser.forms if f.get("data-list") == "personal-interest"]
        assert soft == [], "Soft Personal hero must not appear on non-target shows"
        worker = [
            f for f in parser.forms
            if (f.get("data-nn-subscribe") or "").startswith("show-")
        ]
        # omni_view has a newsletter_tag — expect at least one Worker form.
        assert worker, "newsletter Worker form missing on non-hero show page"
        assert 'target="popupwindow"' not in html
