"""Nov 24 2026: every show page has a stable search title, and three
accessibility faults an axe sweep measured are fixed.

Before: 18 show pages had no row in docs/seo-titles-final.md, so their
``<title>`` led with the day's episode hook, clipped, up to 104 characters,
and changed with every episode.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _english_show_pages() -> dict[str, str]:
    import generate_html as G
    from engine import show_lang

    out = {}
    for slug, cfg in G.NETWORK_SHOWS.items():
        page = cfg.get("show_page", "")
        if page and not show_lang.is_russian(slug) and (ROOT / page).exists():
            out[slug] = page
    return out


def test_every_english_show_page_has_seo_copy():
    import generate_html as G

    missing = [p for p in _english_show_pages().values() if p not in G.SEO_PAGE_COPY]
    assert not missing, f"add a row to docs/seo-titles-final.md for: {missing}"


def test_no_free_claim_on_a_members_show():
    import generate_html as G
    from engine import access

    for slug, page in _english_show_pages().items():
        if page not in G.SEO_PAGE_COPY:
            continue
        title, meta = G.SEO_PAGE_COPY[page]
        assert "ad-free" not in (title + meta).lower(), page
        if access.mode_for_slug(slug) != "public":
            assert "free" not in meta.lower(), (page, meta)


@pytest.mark.parametrize("page", ["nerra-voices-apply.html", "age-of-ai-apply.html"])
def test_apply_pages_have_a_canonical(page):
    assert f'<link rel="canonical" href="https://nerranetwork.com/{page}">' in _read(page)


def test_footer_group_label_is_not_dimmed():
    css = _read("styles/main.css")
    block = css.split(".nn-footer-col .nn-footer-grouplabel {", 1)[1].split("}", 1)[0]
    assert not re.search(r"^\s*opacity\s*:", block, re.M)


def test_primary_button_text_is_white_on_the_accent():
    css = _read("templates/_landing_styles.html.j2")
    assert re.search(r"\.lt-btn--primary \{[^}]*color: #fff;", css)


def test_markets_list_is_keyboard_reachable():
    assert '<ul tabindex="0" aria-label="Market quotes and upcoming launches">' in _read(
        "templates/network_page.html.j2"
    )
