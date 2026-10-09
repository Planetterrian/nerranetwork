"""Soft Personal ask on blog episode posts (Oct 9 2026, eng plan item E1).

Blog episode posts are ~34% of measured landing sessions with ~70% bounce
(PR #1374) and had no Soft Personal ask. This guard pins the band on EN
posts: same approved copy, list, honeypot and Worker path as the show-page
hero, its own id, no paid link or price inside the no-charge block, the
privacy note, and none on RU posts.
"""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SOFT_COPY = (
    "Get a quiet nudge with occasional Personal tips. "
    "No charge, no card. Shows stay free either way."
)
_MD = "## Top Story\n\nSpaceX flew again today. " * 5


def _render(slug: str) -> str:
    from engine.blog import generate_blog_post_html
    from generate_html import NETWORK_SHOWS, _get_jinja_env

    meta = {
        "episode_num": 999,
        "date": "2026-10-08",
        "date_iso": "2026-10-08",
        "hook": "A probe hook for the Soft Personal blog band.",
        "source_urls": ["https://example.com/a"],
        "word_count": 500,
        "reading_time_min": 3,
        "_md_path": str(ROOT / "digests" / slug / "probe.md"),
    }
    return generate_blog_post_html(_MD, meta, NETWORK_SHOWS[slug], _get_jinja_env())


class _Forms(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = []

    def handle_starttag(self, tag, attrs):
        if tag == "form":
            self.forms.append(dict(attrs))


def _band(html: str) -> str:
    start = html.rindex("<aside", 0, html.index('id="soft-personal-post"'))
    return html[start:html.index("</aside>", start)]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s)


def test_en_post_has_exactly_one_soft_band():
    html = _render("spacex")
    assert html.count('id="soft-personal-post"') == 1
    assert 'id="soft-personal-hero"' not in html
    assert SOFT_COPY in _norm(_band(html))


def test_form_posts_through_the_worker_contract():
    html = _render("spacex")
    p = _Forms()
    p.feed(_band(html))
    assert len(p.forms) == 1
    f = p.forms[0]
    assert (f.get("method") or "").lower() == "post"
    assert f.get("data-nn-subscribe") == "soft-personal"
    assert f.get("data-list") == "personal-interest"
    assert (f.get("data-source") or "").startswith("src-")
    assert f.get("data-show") == "spacex"
    assert f.get("data-form-id") == "blog-spacex-soft-personal"
    assert "onsubmit" not in f
    assert 'name="company"' in _band(html)
    assert "assets/js/footer-subscribe.js" in html


class _Visible(HTMLParser):
    """User-visible text plus the data-label-* strings the JS shows."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k.startswith("data-label") or k in ("placeholder", "aria-label"):
                self.parts.append(v or "")

    def handle_data(self, data):
        self.parts.append(data)


def test_band_stays_inside_brand_truth():
    band = _band(_render("spacex"))
    v = _Visible()
    v.feed(band)
    text = _norm(" ".join(v.parts)).lower()
    # "Unsubscribe anytime." is the approved privacy note; any other
    # "subscribe" wording is banned inside a Soft ask.
    assert not re.search(r"(?<!un)subscribe", text)
    for banned in ("$", "/mo", "trial", "reminder",
                   "when you’re ready", "when you're ready",
                   "not ready to pay", "soft"):
        assert banned not in text, banned
    assert "join.html" not in band
    assert "We’ll only email you about Nerra Personal. Unsubscribe anytime." in _norm(band)
    assert "privacy-policy.html" in band


def test_status_line_reserves_space_for_cls():
    band = _band(_render("spacex"))
    assert re.search(r'data-nn-subscribe-status[^>]*min-height:1\.3em', band)


def test_ru_post_has_no_personal_offer():
    """No Personal offer on RU surfaces until Patrick decides."""
    import engine.blog as B
    from generate_html import NETWORK_SHOWS

    ru = [s for s in NETWORK_SHOWS if B._show_lang.is_russian(s)]
    assert ru, "expected at least one Russian-language show"
    html = _render(ru[0])
    assert 'id="soft-personal-post"' not in html


def test_fr_gate_matches_page_lang_and_is_live_noop():
    """FR Soft exclusion: same page_lang detection as RU; currently a no-op.

    Blog posts take ``page_lang`` from ``engine.show_lang.page_lang`` (YAML
    ``tts.language_code`` / registry ``page_lang``). That module returns only
    ``en`` or ``ru`` for every registered show today — there is no French
    show page and no separate FR blog HTML — so a live render never hits
    ``_is_fr``. The template still gates Soft on ``not _is_fr`` so a future
    ``page_lang: fr`` show stays Soft-free without inventing a second flag.
    """
    import re

    import engine.blog as B
    from generate_html import NETWORK_SHOWS

    tpl = (ROOT / "templates" / "blog_post.html.j2").read_text(encoding="utf-8")
    scrubbed = re.sub(r"\{#.*?#\}", "", tpl, flags=re.S)
    assert "_is_fr = (page_lang | default('en')) == 'fr'" in scrubbed
    assert "not _is_ru and not _is_fr" in scrubbed

    langs = {B._show_lang.page_lang(s) for s in NETWORK_SHOWS}
    assert langs <= {"en", "ru"}
    assert "fr" not in langs

    # Force page_lang=fr through the real render path to prove the gate.
    real = B._show_lang.page_lang

    def _fr_for_spacex(slug):
        if slug == "spacex":
            return "fr"
        return real(slug)

    B._show_lang._reset_cache()
    try:
        B._show_lang.page_lang = _fr_for_spacex  # type: ignore[method-assign]
        html = _render("spacex")
    finally:
        B._show_lang.page_lang = real  # type: ignore[method-assign]
        B._show_lang._reset_cache()
    assert 'id="soft-personal-post"' not in html
