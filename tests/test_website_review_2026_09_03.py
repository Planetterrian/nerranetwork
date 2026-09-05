"""Drift guards for the Sep 3 2026 website review.

Canonical writeup: docs/website_review_2026_09_03.md. Each test pins one
fix from that pass so it cannot silently regress: the empty <title> on the
MIT performance page, the 1.7 MB blog hub, the hand-written legal pages,
the homepage claims that were false, the navigation defects, and the
Mission Control null-vs-zero / guarded-read fixes.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_T = _ROOT / "templates"


def _read(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# <title> plumbing
# ---------------------------------------------------------------------------

class TestTitlePlumbing:
    def test_base_title_honours_block_and_variable(self):
        src = _read("templates/base.html.j2")
        assert "<title>{% block title %}{{ page_title }}{% endblock %}</title>" in src

    def test_mit_performance_page_has_title_and_description(self):
        import generate_html as g
        env = g._get_jinja_env()
        tpl = env.get_template("mit_performance_page.html.j2")
        html = tpl.render(
            show=g.NETWORK_SHOWS["modern_investing"], performance_data=None,
            tracker=None, mit_charts=g._mit_chart_data(None), path_prefix="",
            page_title="Modern Investing Techniques — Performance & Lessons Learned | Nerra Network",
            meta_description="desc", page_description="desc", all_shows=[],
            canonical_url="https://nerranetwork.com/modern-investing-performance.html",
            youtube=None, image_provider="grok",
        )
        m = re.search(r"<title>(.*?)</title>", html, re.S)
        assert m and m.group(1).strip(), "MIT performance page rendered an empty <title>"
        assert 'name="description" content="desc"' in html

    def test_mit_generator_passes_metadata(self):
        src = _read("generate_html.py")
        i = src.index("def generate_mit_performance_page")
        body = src[i:i + 4000]
        assert '"page_title":' in body and '"meta_description":' in body
        assert '"canonical_url": "https://nerranetwork.com/modern-investing-performance.html"' in body

    def test_narrative_pages_get_canonical_and_absolute_og_image(self):
        src = _read("generate_html.py")
        i = src.index("def generate_narrative_page")
        body = src[i:i + 4000]
        assert '"canonical_url": "https://nerranetwork.com/" + cfg["show_page"].replace(".html", "-narrative.html")' in body
        assert 'f"https://nerranetwork.com/{cfg[\'podcast_image\']}"' in body
        j = src.index("def generate_tesla_narrative_page")
        assert '"canonical_url": "https://nerranetwork.com/tesla-narrative.html"' in src[j:j + 4000]


# ---------------------------------------------------------------------------
# Blog hub payload
# ---------------------------------------------------------------------------

class TestBlogHubPayload:
    def test_hub_is_capped(self):
        from engine.blog import NETWORK_BLOG_INDEX_MAX_POSTS
        assert 100 <= NETWORK_BLOG_INDEX_MAX_POSTS <= 400

    def test_hub_renders_archive_rail(self):
        import generate_html as g
        from engine.blog import generate_network_blog_index_html
        from datetime import date
        posts = [
            {"show_slug": "tesla", "episode_num": n, "title": f"T{n}", "hook": "",
             "date": "2026-09-01", "date_obj": date(2026, 9, 1), "reading_time_min": 3}
            for n in range(1, 301)
        ]
        html = generate_network_blog_index_html(posts, g.NETWORK_SHOWS, g._get_jinja_env())
        assert html.count('class="blog-idx-card"') <= 240
        assert "blog-archive-card" in html
        assert "300 articles" in html

    def test_hub_og_image_is_not_svg(self):
        src = _read("engine/blog.py")
        assert 'og_image": "https://nerranetwork.com/assets/nerra-logo-icon.svg"' not in src


# ---------------------------------------------------------------------------
# Legal / trust pages on the shared chrome
# ---------------------------------------------------------------------------

class TestLegalPages:
    @pytest.mark.parametrize("name", ["ai_disclosure", "privacy_policy", "terms_of_service"])
    def test_templates_extend_base(self, name):
        src = (_T / f"{name}.html.j2").read_text(encoding="utf-8")
        assert src.startswith('{% extends "base.html.j2" %}')
        assert '{% include "_legal_page.html.j2" %}' in src

    def test_generator_and_flags(self):
        import generate_html as g
        assert set(g._LEGAL_PAGES) == {"ai_disclosure", "privacy_policy", "terms_of_service"}
        assert g.generate_legal_page("ai_disclosure", dry_run=True) is None
        src = _read("generate_html.py")
        assert '"--legal"' in src and '"--static-pages"' in src
        assert "generate_legal_pages(dry_run=args.dry_run)" in src

    def test_ai_disclosure_does_not_overclaim_human_review(self):
        src = (_T / "ai_disclosure.html.j2").read_text(encoding="utf-8")
        assert "personally reviewed and approved" not in src
        assert "Supreme Court" not in src
        assert "Mira" in src
        assert "Source-integrity gate" in src

    def test_nightly_regenerates_every_static_page(self):
        wf = _read(".github/workflows/nightly-maintenance.yml")
        assert "python generate_html.py --static-pages" in wf

    def test_editorial_page_is_honest_about_analytics(self):
        src = (_T / "editorial.html.j2").read_text(encoding="utf-8")
        assert "no third-party analytics" not in src
        assert "Consent Mode v2" in src
        assert "25 seconds of music" not in src
        # Only one description / canonical per page — base emits them.
        assert 'name="description"' not in src
        assert 'rel="canonical"' not in src


# ---------------------------------------------------------------------------
# Navigation + chrome
# ---------------------------------------------------------------------------

class TestNavigationChrome:
    def test_no_redundant_home_link_and_more_dropdown(self):
        src = _read("templates/base.html.j2")
        assert "{{ t.nav_home }}</a></li>" not in src
        assert "nn-nav-dropdown-menu--compact" in src
        for page in ("books.html", "gallery.html", "data.html", "editorial.html", "support.html"):
            assert f'href="{{{{ path_prefix }}}}{page}"' in src

    def test_mobile_links_use_delegated_close(self):
        for rel in ("templates/base.html.j2", "templates/network_page.html.j2"):
            src = _read(rel)
            assert "onclick=\"document.getElementById('mobileMenu')" not in src, rel
        src = _read("templates/base.html.j2")
        assert "document.body.classList.remove('menu-open')" in src

    def test_dropdowns_are_click_and_keyboard_operable(self):
        src = _read("templates/base.html.j2")
        assert "dd.classList.toggle('open', willOpen)" in src
        assert "e.key === 'Escape'" in src

    def test_footer_about_column_inside_grid(self):
        src = _read("templates/base.html.j2")
        grid_start = src.index('<div class="nn-footer-grid">')
        about = src.index("<h4>{{ t.footer_about }}</h4>")
        subscribe = src.index("nn-footer-subscribe")
        # The About column must appear before the grid closes (before the
        # subscribe block, which follows the grid).
        assert grid_start < about < subscribe
        css = _read("styles/main.css")
        assert "grid-template-columns: 1.6fr repeat(5, 1fr);" in css

    def test_css_tokens_and_scroll_padding(self):
        css = _read("styles/main.css")
        assert "--nn-accent:" in css and "--nn-text-secondary:" in css
        assert "scroll-padding-top: calc(var(--nav-height, 72px) + 8px);" in css
        assert "html { scroll-behavior: auto; }" in css
        assert "max-height: min(72vh, 620px);" in css

    def test_search_result_styles_are_not_mobile_only(self):
        css = _read("styles/main.css")
        mobile = css.index("@media (max-width: 639px)")
        assert css.index(".search-result mark {") < mobile

    def test_copyright_year_is_computed(self):
        src = _read("templates/base.html.j2")
        assert "© 2026 Nerra Network" not in src
        assert "current_year" in src
        import generate_html as g
        assert "current_year" in g._get_jinja_env().globals

    def test_hreflang_and_homepage_canonical_use_bare_origin(self):
        src = _read("templates/base.html.j2")
        assert 'hreflang="x-default" href="https://nerranetwork.com/"' in src
        gen = _read("generate_html.py")
        assert '"canonical_url": f"{GITHUB_RAW}/",' in gen

    def test_network_status_footer_link_lands_on_sponsor_view(self):
        src = _read("templates/base.html.j2")
        assert 'management.html?view=sponsor' in src


# ---------------------------------------------------------------------------
# Homepage claims
# ---------------------------------------------------------------------------

class TestHomepageClaims:
    def test_ticker_and_stats_driven_by_registry(self):
        src = _read("templates/network_page.html.j2")
        assert "Tesla & EV Markets" not in src, "hand-maintained ticker is back"
        assert '<div class="topic-ticker" aria-hidden="true">' in src
        assert "{{ all_shows|length }}</strong>" in src

    def test_no_false_daily_or_free_forever_claims(self):
        src = _read("templates/network_page.html.j2")
        assert "published daily" not in src
        assert "Free forever" not in src
        assert "no paywalls" not in src
        assert "The most recent episodes from all shows" not in src

    def test_homepage_newsletter_uses_account_worker(self):
        src = _read("templates/network_page.html.j2")
        assert "buttondown.com/api/emails/embed-subscribe" not in src
        assert "https://api.nerranetwork.com/api/subscribe" in src
        assert 'target="popupwindow"' not in src

    def test_inline_keyframes_removed(self):
        src = _read("templates/network_page.html.j2")
        assert "@keyframes cardFloat" not in src
        assert "@keyframes ctaPulse" not in src

    def test_hero_eager_images_capped(self):
        src = _read("templates/network_page.html.j2")
        assert "{% if loop.index0 < 7 %} loading=\"eager\" fetchpriority=\"high\"" in src

    def test_most_played_capped_per_show(self):
        import generate_html as g
        assert 1 <= g.POPULAR_EPISODES_MAX_PER_SHOW <= 3
        assert "_per_show.get(_slug, 0) >= POPULAR_EPISODES_MAX_PER_SHOW" in _read("generate_html.py")

    def test_scaffolded_shows_have_real_display_order(self):
        import yaml
        meta = yaml.safe_load(_read("shows/network_meta.yaml"))
        for slug in ("spacex", "dp_pod", "age_of_ai", "offshore_north", "nerra_daily"):
            assert meta[slug]["display_order"] < 99, slug
        orders = [meta[s]["display_order"] for s in meta]
        assert len(orders) == len(set(orders)), "display_order ties fall back to insertion order"


# ---------------------------------------------------------------------------
# Show / info page messaging
# ---------------------------------------------------------------------------

class TestShowAndInfoPages:
    def test_env_intel_has_no_borrowed_x_handle(self):
        import generate_html as g
        assert g.NETWORK_SHOWS["env_intel"]["x_account"] is None

    def test_hero_description_is_not_the_about_text(self):
        src = _read("generate_html.py")
        assert '"show_description": cfg.get("about_text", cfg["description"])' not in src

    def test_every_show_has_an_inbound_recommendation(self):
        import generate_html as g
        import yaml
        inbound = {cfg["related_show"] for cfg in g.NETWORK_SHOWS.values() if cfg.get("related_show")}
        meta = yaml.safe_load(_read("shows/network_meta.yaml"))
        inbound |= {v.get("related_show") for v in meta.values() if v.get("related_show")}
        for slug in ("spacex", "nerra_daily", "offshore_north", "first_principles", "unintended_consequences"):
            assert slug in inbound, f"{slug} is recommended by no show"

    def test_summaries_page_is_honest_and_reads_age_of_ai_shape(self):
        gen = _read("generate_html.py")
        assert "Complete archive of" not in gen
        tpl = (_T / "summaries_page.html.j2").read_text(encoding="utf-8")
        assert "data.summaries || data.episodes || []" in tpl
        assert "allorigins" not in tpl
        assert "<h1>${linkify" not in tpl

    def test_start_here_lists_every_show(self):
        src = (_T / "start_here.html.j2").read_text(encoding="utf-8")
        import generate_html as g
        listed = set(re.findall(r"'([a-z_]+)'", "".join(re.findall(r"s\.slug in \[(.*?)\]", src))))
        missing = set(g.NETWORK_SHOWS) - listed
        assert not missing, f"Start Here hides: {sorted(missing)}"

    def test_faq_covers_cost_mira_languages_and_correct_cadence(self):
        src = (_T / "faq.html.j2").read_text(encoding="utf-8")
        for q in ("What does it cost?", "Who is Mira?", "What languages can I listen in?"):
            assert src.count(q) == 2, f"{q!r} must be in the JSON-LD and the visible FAQ"
        assert "Offshore North is weekly on Mondays" in src
        assert "Modern Investing and Unintended Consequences are weekdays" not in src

    def test_no_seventeen_daily_shows_claim(self):
        for rel in ("templates/support_page.html.j2", "templates/join_page.html.j2",
                    "templates/press.html.j2", "generate_html.py"):
            src = _read(rel)
            assert "Seventeen daily shows" not in src, rel
            assert "Seventeen shows publish every day" not in src, rel

    def test_how_to_listen_does_not_advertise_spanish(self):
        assert "Espa&ntilde;ol" not in (_T / "how_to_listen.html.j2").read_text(encoding="utf-8")

    def test_ru_landing_has_no_nested_main(self):
        src = (_T / "ru_landing.html.j2").read_text(encoding="utf-8")
        assert not re.search(r"^\s*<main\b", src, re.M), "base.html.j2 already provides <main>"

    def test_account_page_is_noindexed(self):
        assert 'content="noindex,follow"' in (_T / "account_page.html.j2").read_text(encoding="utf-8")

    def test_blog_index_rss_button_gated_on_posts(self):
        src = (_T / "blog_index.html.j2").read_text(encoding="utf-8")
        assert src.index("{% if posts %}") < src.index('class="blog-rss-btn"')


# ---------------------------------------------------------------------------
# Mission Control
# ---------------------------------------------------------------------------

class TestMissionControl:
    def test_guarded_reads(self):
        src = _read("management.html")
        assert "money((data.network || {}).total_cost_last_7_days_usd)" in src
        assert "((data.voice_config || {}).shows || [])" in src
        assert "(mit.trades || []).forEach" in src
        assert "(rss.feeds || []).length" in src
        assert 'window.addEventListener("error"' in src

    def test_null_is_not_zero_on_show_cards(self):
        src = _read("management.html")
        assert 'addStat(fmtOrDash(dl.downloads_7d), "RSS · 7d");' in src
        assert 'fmt(dl.downloads_7d || 0)' not in src

    def test_data_age_visible_in_every_view(self):
        src = _read("management.html")
        assert 'id="data-age"' in src
        assert 'ageEl.className = "pill " + ageClass;' in src

    def test_nav_has_way_back_and_growth_anchor(self):
        src = _read("management.html")
        assert '<a href="index.html">← nerranetwork.com</a>' in src
        assert '<a href="#growth-levers" data-ops>Growth</a>' in src

    def test_phone_layout_and_ops_only_notes(self):
        src = _read("management.html")
        assert "minmax(min(340px, 100%), 1fr)" in src
        assert '"data-ops": ""' in src
