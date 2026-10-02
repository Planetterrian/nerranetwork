"""Soft Personal one-field capture on / and /age-of-ai.html (N-PR2).

Extends the Sep 28 show-page Soft hero to the homepage and Age of AI.
Same form contract (Worker subscribe, utm→src-*, GA after ok:true);
exact free-interest copy; no numeric show count on /personal-interest.
"""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SOFT_HERO_COPY = (
    "Get a quiet nudge with Personal tips, or a reminder when you’re ready. "
    "No charge, no card. Shows stay free either way."
)


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _scrub_jinja_comments(src: str) -> str:
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


class TestSoftPersonalHomeAndAgeOfAi:
    def test_age_of_ai_in_hero_slug_set(self):
        from generate_html import SOFT_PERSONAL_HERO_SLUGS

        assert "age_of_ai" in SOFT_PERSONAL_HERO_SLUGS

    def test_network_page_calls_macro_with_home_wrapper(self):
        src = _scrub_jinja_comments(_read("templates/network_page.html.j2"))
        assert "soft_personal_hero_band" in src
        assert "home-soft-personal" in src
        assert "'network'" in src or '"network"' in src

    def test_macro_owns_exact_copy_and_no_price(self):
        macros = _scrub_jinja_comments(_read("templates/_macros.html.j2"))
        hero = _hero_inner(macros)
        assert SOFT_HERO_COPY in hero
        assert "$4.99" not in hero
        assert "4.99" not in hero
        assert "/mo" not in hero

    def test_rendered_homepage_has_exactly_one_soft_hero(self, tmp_path, monkeypatch):
        import generate_html as G

        # generate_network_page writes ROOT/index.html — redirect ROOT so
        # the test never touches the committed homepage.
        monkeypatch.setattr(G, "ROOT", tmp_path)
        # Minimal tree the generator reads from ROOT.
        (tmp_path / "api").mkdir()
        (tmp_path / "site" / "data").mkdir(parents=True)
        (tmp_path / "digests").mkdir()
        written = G.generate_network_page()
        assert written is not None
        html = Path(written).read_text(encoding="utf-8")
        assert html.count('id="soft-personal-hero"') == 1
        assert 'id="home-soft-personal"' in html
        hero = _hero_inner(html)
        assert SOFT_HERO_COPY in hero
        assert "$4.99" not in hero
        assert "/mo" not in hero
        assert "4.99" not in hero
        parser = _FormCollector()
        parser.feed(html)
        soft = [f for f in parser.forms if f.get("data-nn-subscribe") == "soft-personal"]
        assert soft, "homepage Soft Personal form missing"
        form = soft[0]
        assert form.get("data-list") == "personal-interest"
        assert form.get("data-show") == "network"
        assert (form.get("data-source") or "").startswith("src-")
        assert form.get("data-form-id") == "show-network-soft-personal"

    def test_rendered_age_of_ai_has_exactly_one_soft_hero(self, tmp_path):
        import generate_html as G
        import inspect

        sig = inspect.signature(G.generate_show_page)
        assert "output_dir" in sig.parameters
        written = G.generate_show_page("age_of_ai", output_dir=str(tmp_path))
        assert written is not None
        html = Path(written).read_text(encoding="utf-8")
        assert html.count('id="soft-personal-hero"') == 1
        hero = _hero_inner(html)
        assert SOFT_HERO_COPY in hero
        assert "$4.99" not in hero
        assert "/mo" not in hero
        parser = _FormCollector()
        parser.feed(html)
        soft = [f for f in parser.forms if f.get("data-nn-subscribe") == "soft-personal"]
        assert soft
        assert soft[0].get("data-show") == "age_of_ai"
        assert soft[0].get("data-list") == "personal-interest"


class TestPersonalInterestNoNumericShowCount:
    def test_template_and_meta_have_no_numeric_show_count(self):
        tpl = _read("templates/personal_interest_page.html.j2")
        gen = _read("generate_html.py")
        # Body + meta description must use the non-numeric phrasing.
        assert "Every Nerra show stays free" in tpl
        assert "All 18 Nerra shows stay free" not in tpl
        assert "Every Nerra show stays free" in gen
        assert "All 18 Nerra shows stay free" not in gen
        # No "N shows" / "all N" count patterns in the Soft page template body.
        body_start = tpl.index("{% block content %}")
        body = tpl[body_start:]
        assert not re.search(
            r"\b(?:all\s+)?\d+\s+Nerra\s+shows?\b", body, flags=re.I
        ), "numeric show count still on personal-interest template"
        assert not re.search(r"\b\d+\s+shows?\b", body, flags=re.I), (
            "numeric show count still on personal-interest template"
        )

    def test_rendered_page_has_no_numeric_show_count(self, tmp_path):
        import generate_html as G

        # generate_personal_interest_page writes to ROOT; render template
        # with the same context helper when available.
        env = G._get_jinja_env()
        ctx = G._member_page_context(
            "Nerra Personal — when you’re ready | Nerra Network",
            "Every Nerra show stays free. Leave your email for a quiet "
            "nudge with Personal tips — or a reminder when you’re ready. "
            "No ads. Curiosity only.",
            "https://nerranetwork.com/personal-interest.html",
        )
        ctx.pop("total_episodes", None)
        html = env.get_template("personal_interest_page.html.j2").render(**ctx)
        assert "Every Nerra show stays free" in html
        assert "All 18" not in html
        assert not re.search(
            r"\b(?:all\s+)?\d+\s+Nerra\s+shows?\b", html, flags=re.I
        )
        # Title / meta / OG must not carry a count either.
        assert not re.search(
            r'content="[^"]*\b\d+\s+(?:Nerra\s+)?shows?\b', html, flags=re.I
        )


class TestUtmSourceMappingUnchanged:
    def test_youtube_utm_still_maps_to_src_youtube(self):
        js = _read("assets/js/footer-subscribe.js")
        assert "utm_source" in js
        assert "src-youtube" in js
        assert "UTM_SOURCE_TAGS[utm]" in js
        assert "soft_personal_interest_submit" in js
        # GA params set unchanged.
        for key in ("form_id", "page_path", "list", "source", "show"):
            assert f"{key}:" in js or f"{key} :" in js
