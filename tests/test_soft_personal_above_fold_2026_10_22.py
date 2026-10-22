"""Soft Personal form above the fold (Oct 22 2026 placement test).

Moves the existing one-field Soft Personal form under the hero / episode
player on /, show pages (spacex / tesla / models_agents), and the SpaceX
blog index. Same footer-subscribe.js + list=personal-interest; distinct
data-source=src-above_fold so GA4 soft_personal_interest_submit can tell
this surface from mid-page asks. Approved pitch only — no new claims.
"""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

APPROVED_PITCH = "Occasional Personal tips by email — no charge, no card"
ABOVE_FOLD_SOURCE = "src-above_fold"
TARGET_SHOW_SLUGS = ("spacex", "tesla", "models_agents")


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _scrub(src: str) -> str:
    return re.sub(r"\{#.*?#\}", "", src, flags=re.S)


def _hero_inner(html: str) -> str:
    start = html.index('id="soft-personal-hero"')
    end = html.index("</section>", start)
    return html[start:end]


class _FormCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms: list[dict[str, str | None]] = []

    def handle_starttag(self, tag, attrs):
        if tag == "form":
            self.forms.append(dict(attrs))


def _soft_forms(html: str) -> list[dict[str, str | None]]:
    parser = _FormCollector()
    parser.feed(html)
    return [
        f for f in parser.forms
        if f.get("data-nn-subscribe") == "soft-personal"
        or f.get("data-list") == "personal-interest"
    ]


class TestMacroAboveFoldContract:
    def test_pitch_is_approved_string_only(self):
        macros = _scrub(_read("templates/_macros.html.j2"))
        hero = _hero_inner(macros)
        # Visible pitch paragraph only (soft-done / join labels are separate).
        pitch_m = re.search(
            r"<p[^>]*>\s*(Occasional Personal tips by email[^<]*)</p>",
            hero,
        )
        assert pitch_m, "approved Soft pitch <p> missing from hero macro"
        pitch = pitch_m.group(1).strip()
        assert pitch == APPROVED_PITCH
        assert "quiet nudge" not in pitch.lower()
        assert "ad-free" not in pitch.lower()
        assert "$4.99" not in pitch
        assert not re.search(r"\b\d+\s+shows?\b", pitch, flags=re.I)

    def test_default_source_is_above_fold(self):
        macros = _scrub(_read("templates/_macros.html.j2"))
        assert "capture_source='src-above_fold'" in macros
        assert 'data-list="personal-interest"' in macros
        assert 'data-nn-subscribe="soft-personal"' in macros


class TestHomepageAboveFoldPlacement:
    def test_template_places_soft_under_masthead_once(self):
        src = _scrub(_read("templates/network_page.html.j2"))
        content = src.split("{% block content %}", 1)[1]
        mast = content.index("lt-masthead")
        soft = content.index("home-soft-personal")
        markets = content.index("lt-markets")
        assert mast < soft < markets
        # Exactly one call in the content block — never duplicated lower.
        assert content.count("soft_personal_hero_band(") == 1
        assert content.count("home-soft-personal") == 1

    def test_rendered_homepage_one_form_above_fold_source(
        self, tmp_path, monkeypatch
    ):
        import generate_html as G

        monkeypatch.setattr(G, "ROOT", tmp_path)
        (tmp_path / "api").mkdir()
        (tmp_path / "site" / "data").mkdir(parents=True)
        (tmp_path / "digests").mkdir()
        written = G.generate_network_page()
        html = Path(written).read_text(encoding="utf-8")

        assert html.count('id="soft-personal-hero"') == 1
        assert html.count('id="home-soft-personal"') == 1
        soft = _soft_forms(html)
        assert len(soft) == 1
        form = soft[0]
        assert form.get("data-list") == "personal-interest"
        assert form.get("data-source") == ABOVE_FOLD_SOURCE
        assert form.get("data-show") == "network"
        assert APPROVED_PITCH in _hero_inner(html)

        # Under masthead, before markets / lead — above the fold.
        home_soft = html.index('id="home-soft-personal"')
        assert html.index("lt-masthead") < home_soft
        if 'id="markets"' in html:
            assert home_soft < html.index('id="markets"')
        elif 'id="latest"' in html:
            assert home_soft < html.index('id="latest"')


class TestShowPageAboveFoldPlacement:
    def test_template_places_soft_under_latest_player(self):
        src = _scrub(_read("templates/show_page.html.j2"))
        content = src.split("{% block content %}", 1)[1]
        player = content.index('id="latest-player"')
        soft_call = content.index("soft_personal_hero_band(")
        assert player < soft_call
        # Only one Soft hero call on the show page.
        assert content.count("soft_personal_hero_band(") == 1

    @pytest.mark.parametrize("slug", TARGET_SHOW_SLUGS)
    def test_rendered_show_one_form_above_fold_source(self, slug, tmp_path):
        import generate_html as G
        import inspect

        assert "output_dir" in inspect.signature(G.generate_show_page).parameters
        written = G.generate_show_page(slug, output_dir=str(tmp_path))
        html = Path(written).read_text(encoding="utf-8")

        assert html.count('id="soft-personal-hero"') == 1
        soft = _soft_forms(html)
        assert soft
        assert soft[0].get("data-source") == ABOVE_FOLD_SOURCE
        assert soft[0].get("data-list") == "personal-interest"
        assert soft[0].get("data-show") == slug
        assert APPROVED_PITCH in _hero_inner(html)
        # Under the latest episode player when the feed exists.
        if 'id="latest-player"' in html:
            assert html.index('id="latest-player"') < html.index(
                'id="soft-personal-hero"'
            )


class TestBlogIndexAboveFoldPlacement:
    def test_template_uses_hero_band_not_interest_link(self):
        src = _scrub(_read("templates/blog_index.html.j2"))
        content = src.split("{% block content %}", 1)[1]
        assert "soft_personal_hero_band(" in content
        assert "soft_personal_interest" not in src
        assert "soft_personal_cta" in content
        # Under the blog hero header.
        assert content.index("blog-idx-hero") < content.index(
            "soft_personal_hero_band("
        )

    def test_rendered_spacex_blog_index_form(self, tmp_path):
        import generate_html as G
        import inspect

        assert "output_dir" in inspect.signature(G.generate_blog_index).parameters
        written = G.generate_blog_index("spacex", output_dir=str(tmp_path))
        assert written is not None
        html = Path(written).read_text(encoding="utf-8")

        assert html.count('id="soft-personal-hero"') == 1
        soft = _soft_forms(html)
        assert soft
        assert soft[0].get("data-source") == ABOVE_FOLD_SOURCE
        assert soft[0].get("data-list") == "personal-interest"
        assert soft[0].get("data-show") == "spacex"
        assert APPROVED_PITCH in _hero_inner(html)
        assert html.index("blog-idx-hero") < html.index('id="soft-personal-hero"')


class TestFooterSubscribeUnchanged:
    def test_soft_personal_handler_still_reads_data_source(self):
        js = _read("assets/js/footer-subscribe.js")
        assert "soft_personal_interest_submit" in js
        assert "resolveSource" in js
        assert "data-source" in js or "getAttribute('data-source')" in js
        # Worker allow-list unchanged here — do not invent src-above_fold
        # mapping in the client UTM table (data-source is the fallback).
        assert "src-above_fold" not in js
