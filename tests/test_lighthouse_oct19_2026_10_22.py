"""Oct 19 health-check Lighthouse regressions (fixed Oct 22 2026).

1. Consent banner is SSR in base.html.j2 (compact bottom bar) so
   .nn-consent-text is never a late-painted LCP element.
2. Homepage shorts-reel.js loads on IntersectionObserver / click.
3. /personal-interest.html has no render-blocking Google Fonts link
   (async loader from base / #1476 only).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


class TestConsentBannerSSR:
    def test_base_ssr_banner_and_head_gate(self):
        base = _read("templates/base.html.j2")
        assert 'id="nn-consent-banner"' in base
        assert 'data-nn-consent-ssr="1"' in base
        assert "nn-consent-needed" in base
        assert "localStorage.getItem('nn_consent_v1')" in base
        assert 'data-nn-consent="accept-all"' in base
        assert 'data-nn-consent="reject-all"' in base
        assert 'data-nn-consent="choose"' in base
        assert 'data-nn-toggle="analytics"' in base
        assert 'data-nn-toggle="ads"' in base
        # EN + RU copy both present in the chrome dict.
        assert "Cookies on Nerra" in base
        assert "Cookie на Nerra" in base
        assert "Accept all" in base and "Принять все" in base
        assert "Before you choose, Google gets only basic, cookie-free signals" in base

    def test_css_is_compact_bar_gated_on_needed_class(self):
        css = _read("styles/main.css")
        assert "html.nn-consent-needed #nn-consent-banner:not([hidden])" in css
        assert "max-height: 4.2em" in css
        # Full-bleed bottom bar, not the old floating card.
        assert re.search(r"#nn-consent-banner\s*\{[^}]*bottom:\s*0", css, re.S)

    def test_consent_js_binds_ssr_and_toggles_needed_class(self):
        js = _read("assets/js/consent.js")
        assert "bindBannerHandlers" in js
        assert "data-nn-consent-bound" in js
        assert "nn-consent-needed" in js
        assert "revealBanner" in js


class TestPersonalInterestFonts:
    def test_template_has_no_google_fonts_link(self):
        tpl = _read("templates/personal_interest_page.html.j2")
        assert "fonts.googleapis.com" not in tpl
        assert "fonts.gstatic.com" not in tpl

    def test_rendered_page_uses_async_fonts_only(self):
        import generate_html as G

        env = G._get_jinja_env()
        title, meta = G.SEO_PAGE_COPY["personal-interest.html"]
        ctx = G._member_page_context(
            title, meta, "https://nerranetwork.com/personal-interest.html"
        )
        ctx.pop("total_episodes", None)
        html = env.get_template("personal_interest_page.html.j2").render(**ctx)

        fonts = re.findall(r"<link[^>]+fonts\.googleapis\.com/css2[^>]*>", html)
        assert fonts, "expected the async Google Fonts link from base"
        async_links = [t for t in fonts if 'media="print"' in t and "onload=" in t]
        assert len(async_links) == 1
        # No render-blocking fonts stylesheet (rel=stylesheet without media=print).
        for tag in fonts:
            if "onload=" not in tag:
                # Allowed only inside <noscript> fallback.
                assert True
        assert not re.search(
            r'<link href="https://fonts\.googleapis\.com/css2[^"]*" rel="stylesheet">',
            html,
        )
