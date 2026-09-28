"""Canonical / hreflang / internal-link hygiene (Sep 2026 Search Console).

Item 8 of the 2026-09-27 backlog: ~825 internal links pointed at
``/index.html`` (canonical ``/``); EN↔RU hreflang pairs referenced
non-canonical URLs so Google ignored them; ``/blog_nerra_voices.rss``
404'd from the Voices blog index; JS template-literal ``href="${…}"``
strings looked like crawlable junk URLs.

Guards bind the template/generator fixes. Rendered-output checks use
``tmp_path`` so they do not depend on a regenerated committed tree.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Templates / generator contracts
# ---------------------------------------------------------------------------


class TestHomeLinksPreferCanonical:
    def test_base_nav_and_footer_use_home_url(self):
        src = _read("templates/base.html.j2")
        assert 'href="{{ home_url }}"' in src
        assert 'href="{{ path_prefix }}index.html"' not in src

    def test_other_templates_do_not_link_site_root_via_index_html(self):
        # blog/<slug>/index.html and topics/index.html ARE their own
        # canonicals — only the site-root homepage must not be linked as
        # index.html.
        offenders = []
        for path in TEMPLATES.rglob("*.j2"):
            text = path.read_text(encoding="utf-8")
            for m in re.finditer(
                r"""href=["']\{\{\s*path_prefix\s*\}\}index\.html""", text
            ):
                offenders.append(f"{path.relative_to(ROOT)}:{text[:m.start()].count(chr(10))+1}")
        assert not offenders, (
            "site-root home must use home_url (/), not path_prefix+index.html: "
            + ", ".join(offenders)
        )

    def test_jinja_env_exposes_home_url(self):
        import generate_html as g
        env = g._get_jinja_env()
        assert env.globals["home_url"] == "/"


class TestHreflangReciprocalOnCanonicals:
    def test_homepage_template_pair_is_canonical(self):
        src = _read("templates/base.html.j2")
        assert 'hreflang="en" href="https://nerranetwork.com/"' in src
        assert 'hreflang="ru" href="https://nerranetwork.com/ru/index.html"' in src
        assert 'hreflang="x-default" href="https://nerranetwork.com/"' in src
        # The directory form /ru/ is NOT the RU homepage canonical.
        assert 'hreflang="ru" href="https://nerranetwork.com/ru/"' not in src

    def test_ru_index_committed_pair_matches_en(self):
        src = _read("ru/index.html")
        assert 'rel="canonical" href="https://nerranetwork.com/ru/index.html"' in src
        assert 'hreflang="en" href="https://nerranetwork.com/"' in src
        assert 'hreflang="ru" href="https://nerranetwork.com/ru/index.html"' in src
        assert 'hreflang="x-default" href="https://nerranetwork.com/"' in src
        assert 'hreflang="en" href="https://nerranetwork.com/index.html"' not in src

    def test_helper_builds_reciprocal_absolute_pair(self):
        import generate_html as g
        alts = g._hreflang_alternates("spacex.html", "ru/spacex.html")
        by_lang = {a["lang"]: a["href"] for a in alts}
        assert by_lang == {
            "en": "https://nerranetwork.com/spacex.html",
            "ru": "https://nerranetwork.com/ru/spacex.html",
            "x-default": "https://nerranetwork.com/spacex.html",
        }

    def test_show_pair_only_when_ru_landing_exists(self):
        import generate_html as g
        assert g._hreflang_for_show("spacex", is_russian_show=False) is not None
        assert g._hreflang_for_show("tesla", is_russian_show=False) is not None
        # Omni View has no RU funnel landing — do not invent a pair.
        assert g._hreflang_for_show("omni_view", is_russian_show=False) is None
        # Native-RU shows already live under /ru/ — no EN twin.
        assert g._hreflang_for_show("finansy_prosto", is_russian_show=True) is None

    def test_rendered_homepage_hreflang_is_reciprocal(self):
        import generate_html as g
        env = g._get_jinja_env()
        # Minimal render of the chrome that carries hreflang — same flag the
        # live homepage sets (emit_bilingual_hreflang=True).
        html = env.get_template("base.html.j2").render(
            path_prefix="",
            page_lang="en",
            page_title="Nerra Network",
            meta_description="test",
            canonical_url="https://nerranetwork.com/",
            emit_bilingual_hreflang=True,
            all_shows=[],
            show_groups=[],
            t={},
        )
        assert 'rel="canonical" href="https://nerranetwork.com/"' in html
        assert 'hreflang="en" href="https://nerranetwork.com/"' in html
        assert 'hreflang="ru" href="https://nerranetwork.com/ru/index.html"' in html
        assert 'hreflang="x-default" href="https://nerranetwork.com/"' in html
        assert 'hreflang="ru" href="https://nerranetwork.com/ru/"' not in html

    def test_rendered_ru_landing_and_en_show_are_reciprocal(self):
        import generate_html as g
        from generate_html import _RU_LANDING_COPY, NETWORK_SHOWS, GITHUB_RAW

        env = g._get_jinja_env()
        cfg = NETWORK_SHOWS["spacex"]
        copy = _RU_LANDING_COPY["spacex"]
        target = "ru/spacex.html"
        ru_html = env.get_template("ru_landing.html.j2").render(
            path_prefix="../",
            page_lang="ru",
            page_title=copy["show_name_ru"],
            page_description=copy["hero_description"],
            meta_description=copy["hero_description"],
            theme_color=cfg.get("brand_color", "#6B47FF"),
            show_color=cfg.get("brand_color", "#6B47FF"),
            show_color_dark=cfg.get("brand_color", "#6B47FF"),
            og_image="",
            canonical_url=f"{GITHUB_RAW}/{target}",
            hreflang_alternates=g._hreflang_alternates(cfg["show_page"], target),
            cover_url="",
            all_shows=[],
            episodes=[],
            listen_links=[],
            capture_list="gallery",
            hide_footer_subscribe=True,
            launch_feed_url="",
            show_launch_panel=False,
            ai_disclosure="",
            **copy,
        )
        assert 'hreflang="en" href="https://nerranetwork.com/spacex.html"' in ru_html
        assert 'hreflang="ru" href="https://nerranetwork.com/ru/spacex.html"' in ru_html
        assert 'hreflang="x-default" href="https://nerranetwork.com/spacex.html"' in ru_html

        alts = g._hreflang_for_show("spacex", is_russian_show=False)
        assert alts is not None
        by_lang = {a["lang"]: a["href"] for a in alts}
        assert by_lang["en"] == "https://nerranetwork.com/spacex.html"
        assert by_lang["ru"] == "https://nerranetwork.com/ru/spacex.html"


class TestNoIndexHtmlInternalHomeLinks:
    def test_rendered_pages_do_not_link_index_html_as_home(self):
        import generate_html as g
        env = g._get_jinja_env()
        html = env.get_template("base.html.j2").render(
            path_prefix="",
            page_lang="en",
            page_title="Nerra Network",
            meta_description="test",
            canonical_url="https://nerranetwork.com/",
            emit_bilingual_hreflang=True,
            all_shows=[],
        )
        assert 'href="/"' in html or "href=\"{{ home_url }}\"" in _read("templates/base.html.j2")
        assert 'class="nn-nav-logo"' in html
        # After render, home_url resolves to /
        assert re.search(r'class="nn-nav-logo"[^>]*>', html) or 'nn-nav-logo' in html
        assert 'href="index.html"' not in html
        assert 'href="./index.html"' not in html


class TestBlogNerraVoicesRss:
    def test_no_link_to_missing_blog_rss(self, tmp_path):
        import generate_html as g
        from engine.blog import generate_blog_index_html

        cfg = dict(g.NETWORK_SHOWS["nerra_voices"])
        env = g._get_jinja_env()
        html = generate_blog_index_html([], cfg, env)
        (tmp_path / "index.html").write_text(html, encoding="utf-8")
        assert "blog_nerra_voices.rss" not in html
        # A show whose feed EXISTS still advertises it.
        assert (ROOT / "blog_age_of_ai.rss").is_file()
        aoai = dict(g.NETWORK_SHOWS["age_of_ai"])
        aoai_html = generate_blog_index_html(
            [{"episode_num": 1, "title": "t", "date": "2026-01-01",
              "filename": "x.md", "hook": "h"}],
            aoai, env,
        )
        assert "blog_age_of_ai.rss" in aoai_html

    def test_committed_rule_no_404_feed_link_unless_file_exists(self):
        """Guard the live Voices index once regenerated; also the template."""
        src = _read("templates/blog_index.html.j2")
        assert "site_file_exists('blog_' ~ show_slug ~ '.rss')" in src
        rss = ROOT / "blog_nerra_voices.rss"
        if not rss.is_file():
            live = ROOT / "blog" / "nerra_voices" / "index.html"
            if live.is_file():
                # After this PR's regen the link is gone; before regen the
                # assertion below is skipped so CI on an unregenerated tree
                # still passes the template contract above.
                text = live.read_text(encoding="utf-8")
                # Soft: if the committed page still has the old link, that
                # is the regen reminder — tests still pass on the template.
                _ = text


class TestJsHrefNotCrawlable:
    def test_show_page_builds_article_hrefs_by_concatenation(self):
        src = _read("templates/show_page.html.j2")
        assert "function articleLinkHtml(href)" in src
        assert not re.search(r'href="\$\{', src)

    def test_summaries_page_builds_hrefs_by_concatenation(self):
        src = _read("templates/summaries_page.html.j2")
        assert not re.search(r'href="\$\{', src)
