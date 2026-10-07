"""Oct 7 2026 site review — shared chrome, homepage and show pages.

The review rendered every page family at 1440 and 390 px and measured it.
The guards below pin what it fixed:

* One stray ``}`` in styles/main.css closed the phone media query early, so
  the phone-only rules (one-column footer and grids, hidden speed control)
  applied at every width and the 640–1023px tablet block was dropped — no
  hamburger at tablet width, the nav ran off-screen.
* Brand colours were used raw as TEXT on the dark surfaces (Tesla red
  4.06:1, Offshore North 1.66:1, the network purple 3.6:1).
* Show pages: the summaries page printed its own link markup as text, the
  "Recommended for you" copy named a different show from its card, the
  Story Tracker said "Not yet deeply covered" after 122 episodes, the DP Pod
  page still described a daily pre-launch show, and Nerra Voices advertised
  an empty episode rail.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "styles" / "main.css").read_text(encoding="utf-8")


def _strip_css_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _strip_jinja_comments(text: str) -> str:
    return re.sub(r"\{#.*?#\}", "", text, flags=re.S)


class TestStylesheetBraces:
    def test_braces_balance_and_never_close_below_zero(self):
        depth = 0
        for i, ch in enumerate(_strip_css_comments(CSS)):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                assert depth >= 0, f"unmatched '}}' at char {i} of main.css"
        assert depth == 0

    def test_phone_only_rules_stay_inside_the_phone_query(self):
        # The footer, speed control and episode grid rules the stray brace
        # leaked must sit inside a max-width block, not at the top level.
        css = _strip_css_comments(CSS)
        for rule in (".nn-speed-control { display: none; }",
                     ".episodes-grid { grid-template-columns: 1fr; }"):
            idx = css.index(rule)
            depth = css[:idx].count("{") - css[:idx].count("}")
            assert depth >= 1, f"{rule} is at the top level"


class TestTextSafeBrandColours:
    def test_every_element_derives_the_text_tint(self):
        css = _strip_css_comments(CSS)
        assert re.search(r"\*,\s*\*::before,\s*\*::after\s*\{[^}]*--show-color-text:\s*color-mix",
                         css)

    def test_no_rule_uses_a_raw_show_colour_as_text(self):
        css = _strip_css_comments(CSS)
        raw = re.findall(r"(?<![-\w])color:\s*var\(--show-color(?:,[^)]*\))?\)", css)
        assert raw == [], raw
        assert not re.search(r"(?<![-\w])color:\s*var\(--nn-purple\)", css)
        assert not re.search(r"(?<![-\w])color:\s*var\(--card-accent\)", css)

    def test_purple_text_token_passes_aa_on_the_page_background(self):
        m = re.search(r"--nn-purple-text:\s*(#[0-9A-Fa-f]{6})", CSS)
        assert m

        def lum(hex_):
            r, g, b = (int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5))
            f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
            return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

        fg, bg = lum(m.group(1)), lum("#0B0F1A")
        assert (fg + 0.05) / (bg + 0.05) >= 4.5

    def test_hidden_attribute_wins_over_component_display(self):
        assert re.search(r"\[hidden\]\s*\{\s*display:\s*none\s*!important", CSS)


class TestHomepageAndStartHere:
    def test_homepage_nav_matches_every_other_page(self):
        src = _strip_jinja_comments(
            (ROOT / "templates" / "network_page.html.j2").read_text(encoding="utf-8"))
        block = src.split("{% block nav_links %}", 1)[1].split("{% endblock %}", 1)[0]
        # The two in-page anchors pushed "Subscribe"/"Join" off-screen at
        # 1024-1186px.
        assert 'href="#latest"' not in block and 'href="#subscribe"' not in block

    def test_made_in_canada_card_uses_the_canada_flag(self):
        src = (ROOT / "templates" / "network_page.html.j2").read_text(encoding="utf-8")
        assert "&#127463;&#127464;" not in src  # regional letters B, C
        assert "&#127464;&#127462;" in src

    def test_explore_and_start_here_copy_is_not_stale(self):
        explore = (ROOT / "templates" / "explore_page.html.j2").read_text(encoding="utf-8")
        start = (ROOT / "templates" / "start_here.html.j2").read_text(encoding="utf-8")
        assert "Eighteen shows" not in explore
        assert "alternating days" not in start

    def test_start_here_guest_card_has_no_nested_link(self):
        src = _strip_jinja_comments(
            (ROOT / "templates" / "start_here.html.j2").read_text(encoding="utf-8"))
        card = src.split('href="{{ path_prefix }}age-of-ai-apply.html" class="start-show-card"', 1)[1]
        card = card.split("</a>", 1)[0]
        assert "<a " not in card


class TestShowRegistryCopy:
    def test_recommendation_names_the_show_it_recommends(self):
        import generate_html as gh

        names = {k: v.get("name", "") for k, v in gh.NETWORK_SHOWS.items()}
        bad = []
        for slug, cfg in gh.NETWORK_SHOWS.items():
            rel, reason = cfg.get("related_show"), cfg.get("related_reason")
            if rel and reason and names.get(rel):
                if names[rel].split(":")[0].lower() not in reason.lower():
                    bad.append((slug, rel))
        assert bad == []

    def test_referrals_disclose_that_the_show_may_be_rewarded(self):
        import generate_html as gh

        for slug, cfg in gh.NETWORK_SHOWS.items():
            ref = cfg.get("referral")
            if ref:
                assert ref.get("disclosure"), slug
                assert "referral" in ref["disclosure"].lower()

    def test_modern_investing_card_does_not_promise_picks_that_beat_the_index(self):
        import generate_html as gh

        text = gh.NETWORK_SHOWS["modern_investing"]["description_long"]
        assert "actionable picks" not in text
        assert "outperform index funds" not in text


class TestShowPageRender:
    @pytest.fixture(scope="class")
    def rendered(self, tmp_path_factory):
        import generate_html as gh

        out = tmp_path_factory.mktemp("shows")
        pages = {}
        for slug in ("modern_investing", "nerra_voices", "tesla", "dp_pod"):
            if slug not in gh.NETWORK_SHOWS:
                continue
            path = gh.generate_show_page(slug, output_dir=str(out))
            pages[slug] = Path(path).read_text(encoding="utf-8")
        return pages

    def test_wealthsimple_referral_is_not_headed_vehicle_benefits(self, rendered):
        html = rendered["modern_investing"]
        assert "Vehicle Benefits" not in html
        assert "nn-referral-disclosure" in html

    def test_show_page_lists_ten_trades_not_the_whole_ledger(self, rendered):
        html = rendered["modern_investing"]
        assert html.count('href="blog/modern_investing/ep') <= 40
        assert "modern-investing-performance.html" in html

    def test_listen_now_goes_to_the_latest_player(self, rendered):
        html = rendered["tesla"]
        assert re.search(r'href="#latest-player" class="nn-btn nn-btn-primary"', html)

    def test_latest_player_is_counted_by_op3(self, rendered):
        m = re.search(r'<audio id="latest-audio"[^>]*src="([^"]+)"', rendered["tesla"])
        assert m and m.group(1).startswith("https://op3.dev/e/"), m and m.group(1)

    def test_show_without_a_feed_has_no_episode_rail(self, rendered):
        if "nerra_voices" not in rendered:
            pytest.skip("nerra_voices not in registry")
        html = rendered["nerra_voices"]
        assert 'id="episodes"' not in html

    def test_mobile_menu_links_carry_no_inline_close_handler(self, rendered):
        menu = rendered["tesla"].split('id="mobileMenu"', 1)[1].split("</div>", 1)[0]
        assert "onclick" not in menu

    def test_dp_pod_page_reads_as_the_weekly_show_it_is(self, rendered):
        html = rendered["dp_pod"]
        for stale in ("ten minutes a day", "One mental rep a day",
                      "The next lever is tomorrow", "Patron doors open with Episode 1"):
            assert stale not in html, stale


class TestSummariesPage:
    def test_linkify_is_one_pass(self):
        src = (ROOT / "templates" / "summaries_page.html.j2").read_text(encoding="utf-8")
        body = src.split("function linkify(text)", 1)[1].split("\n        }", 1)[0]
        assert body.count(".replace(") == 1

    @pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
    def test_linkify_never_links_inside_its_own_href(self):
        src = (ROOT / "templates" / "summaries_page.html.j2").read_text(encoding="utf-8")
        fn = "function linkify(text)" + src.split("function linkify(text)", 1)[1].split("\n        }", 1)[0] + "\n}"
        script = fn + "\nprocess.stdout.write(linkify('[x.com](https://x.com/a/1) and https://kedglobal.com/x?y=1.'));"
        out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
        assert 'rel="noopener">x.com</a>' in out
        assert '" target="_blank" rel="noopener">x.com' not in out.replace(
            '<a href="https://x.com/a/1" target="_blank" rel="noopener">x.com</a>', "")
        assert 'https://kedglobal.com/x?y=1</a>.' in out

    def test_long_summaries_are_clamped_not_printed_in_full(self):
        src = (ROOT / "templates" / "summaries_page.html.j2").read_text(encoding="utf-8")
        assert "function clampSummaries" in src
        assert ".nn-summary-content.is-clamped" in CSS


class TestStoryTracker:
    def _render(self, template, programs):
        import generate_html as gh

        env = gh._get_jinja_env()
        return env.get_template(template).render(
            narrative={"programs": programs, "last_updated": "2026-10-06T08:00:00"},
            show_name="SpaceX Daily", path_prefix="", all_shows=[], t={},
            source_path="digests/x.json", page_title="t", meta_description="d",
        )

    @pytest.mark.parametrize("template", ["narrative_page.html.j2", "tesla_narrative_page.html.j2"])
    def test_last_on_air_reads_the_field_the_hook_writes(self, template):
        html = self._render(template, {"starship": {
            "display_name": "Starship", "status": "Flight tests continue.",
            "last_major_update_episode": None, "last_major_update_date": "",
            "last_mentioned_episode": 122, "last_mentioned_date": "2026-10-06",
        }})
        assert "Last on air: <strong>Ep 122</strong>" in html
        assert "Not yet deeply covered" not in html
        assert "digests/" not in html.split("<main", 1)[-1]


class TestDesignPassShowCard:
    """Design pass (Oct 7 2026): the show card leads with the tagline,
    clamps the long description, drops the sources list, and the homepage
    stops repeating the Latest rail as a blog section."""

    def _card(self):
        macros = (ROOT / "templates" / "_macros.html.j2").read_text(encoding="utf-8")
        start = macros.index("macro show_card(")
        return macros[start:macros.index("endmacro", start)]

    def test_card_heading_and_tagline(self):
        card = _strip_jinja_comments(self._card())
        assert '<h3 class="show-card-name">' in card
        assert 'class="show-card-hook"' in card
        assert "show-card-sources" not in card
        assert 'alt=""' in card

    def test_long_description_is_clamped(self):
        block = CSS.split(".show-card-tagline {")[-1].split("}", 1)[0]
        assert "-webkit-line-clamp: 3" in block

    def test_homepage_has_one_latest_list(self):
        src = _strip_jinja_comments(
            (ROOT / "templates" / "network_page.html.j2").read_text(encoding="utf-8"))
        assert "Latest from the Blog" not in src
        assert 'class="subscribe-all"' in src


class TestMobileMenuIsShort:
    def test_show_groups_collapse_and_blogs_are_two_links(self):
        base = _strip_jinja_comments(
            (ROOT / "templates" / "base.html.j2").read_text(encoding="utf-8"))
        menu = base.split('<div id="mobileMenu"', 1)[1].split("</main>", 1)[0]
        assert '<details class="nn-mobile-shows nn-mobile-group"' in menu
        # No per-show blog loop: the blog section is the hub + topics map.
        assert "s.blog_page" not in menu
        assert 'alt="{{ s.name }} cover art"' not in menu


class TestFooterIsCompact:
    """The footer was ~2,400 px tall on a desktop: 31 show checkboxes printed
    open under the newsletter form and an 18-show list in one column."""

    def _base(self):
        return _strip_jinja_comments(
            (ROOT / "templates" / "base.html.j2").read_text(encoding="utf-8"))

    def test_newsletter_show_picker_is_collapsed(self):
        base = self._base()
        assert '<details class="nn-subscribe-pick">' in base
        pick = base.split('<details class="nn-subscribe-pick">', 1)[1].split("</details>", 1)[0]
        # The tag checkboxes still render (the Worker reads them); they sit
        # behind the summary instead of printing open on every page.
        assert "nn-subscribe-tags" in pick

    def test_show_list_runs_in_two_columns_on_desktop(self):
        css = _strip_css_comments(CSS)
        assert "nn-footer-col nn-footer-col--shows" in self._base()
        assert re.search(r"\.nn-footer-col--shows ul\.nn-footer-showlist\s*\{\s*columns:\s*2", css)


class TestShowPageIsShorter:
    """Tesla's page was 25k px on a phone: all thirty shows in the
    'More from' grid and twelve open archive players."""

    TPL = _strip_jinja_comments(
        (ROOT / "templates" / "show_page.html.j2").read_text(encoding="utf-8"))

    def test_cross_network_grid_is_capped_and_links_explore(self):
        assert "{% for s in _pool[:8] %}" in self.TPL
        assert 'explore.html">See all' in self.TPL
        # One link per tile; the separate per-show blog row is gone.
        grid = self.TPL.split('<div class="cross-network-grid">', 1)[1].split("</section>", 1)[0]
        assert "s.blog_page" not in grid

    def test_empty_pool_renders_no_section(self):
        # A Russian show's only sibling already has the related-show card.
        assert "{%- if _pool %}\n    <section class=\"cross-network nn-section\">" in self.TPL

    def test_archive_folds_after_six_on_both_render_paths(self):
        assert "const ARCHIVE_VISIBLE = 6;" in self.TPL
        assert self.TPL.count("foldArchive(grid);") == 2

    def test_resource_groups_collapse_with_the_first_open(self):
        assert '<details class="resource-category"{% if loop.first %} open{% endif %}>' in self.TPL
        assert '<summary class="resource-category-title">' in self.TPL
        # The card names the host; the full URL is the link.
        assert "r.url | replace('https://', '')" not in self.TPL


class TestMitTablesSayWhatTheyHold:
    """tracker['sectors'] is the last-ten-trades concentration window in
    DOLLARS with no win counts; monthly snapshots are running totals with
    the three % columns null by construction. The page had printed 0% wins
    on every sector, a dollar average with a % sign, a claim about alpha
    the block never measures, and three columns of dashes."""

    TPL = _strip_jinja_comments(
        (ROOT / "templates" / "show_page.html.j2").read_text(encoding="utf-8"))

    def test_sector_table_is_the_concentration_window_in_dollars(self):
        assert "which approaches are generating alpha" not in self.TPL
        assert "sec_data.get('wins'" not in self.TPL
        assert "Sector mix, last {{ _sec_total }} trades" in self.TPL
        assert "sec_data.cumulative_pnl / sec_data.trade_count" not in self.TPL

    def test_monthly_table_is_labelled_running_totals(self):
        assert "running totals, not per-month results" in self.TPL
        assert "Trades to date" in self.TPL
        # The always-null comparison columns render only when a row has them.
        assert "selectattr('alpha_pct', 'number')" in self.TPL

    def test_sector_writer_still_matches_the_label(self):
        hook = (ROOT / "shows" / "hooks" / "modern_investing.py").read_text(encoding="utf-8")
        body = hook.split("def _compute_sector_exposure", 1)[1].split("\ndef ", 1)[0]
        assert "_CONCENTRATION_WINDOW" in body and "pnl_dollars" in body
        assert "wins" not in body


class TestHomepageLeadsWithTopShows:
    """The hero icons and the show grid followed display_order alone, which
    put Tesla 21st and SpaceX 22nd of 31 while the two carry most of the
    network's downloads. The homepage now ranks by 30-day RSS downloads."""

    def _shows(self, *slugs):
        return [{"slug": s} for s in slugs]

    def test_ranked_by_downloads_then_display_order(self, tmp_path):
        import json as _json
        import generate_html as g
        f = tmp_path / "audience.json"
        f.write_text(_json.dumps({"shows": {
            "a": {"downloads_30d": 5}, "b": {"downloads_30d": 50},
            "c": {"downloads_30d": 0}, "d": {"downloads_30d": None},
            "e": {"downloads_30d": 5},
        }}))
        order = [s["slug"] for s in g._rank_shows_by_audience(
            self._shows("a", "c", "d", "b", "e", "f"), path=f)]
        # Measured shows by downloads (a tie keeps display order), then the
        # unmeasured or zero ones in their original order.
        assert order == ["b", "a", "e", "c", "d", "f"]

    def test_missing_or_broken_file_keeps_display_order(self, tmp_path):
        import generate_html as g
        shows = self._shows("x", "y")
        assert g._rank_shows_by_audience(shows, path=tmp_path / "nope.json") == shows
        bad = tmp_path / "bad.json"
        bad.write_text("{not json")
        assert g._rank_shows_by_audience(shows, path=bad) == shows

    def test_committed_data_puts_the_flagships_first(self):
        import generate_html as g
        if not g.AUDIENCE_HEADLINE_PATH.exists():
            pytest.skip("no committed audience headline")
        ranked = [s["slug"] for s in g._rank_shows_by_audience(g._build_all_shows_list())]
        assert len(ranked) == len(g._build_all_shows_list())
        # Today's file: SpaceX and Tesla lead; a desk with no audience never
        # outranks them. Judged on order, not on exact counts.
        assert ranked.index("spacex") < ranked.index("omni_view_world")
        assert ranked.index("tesla") < ranked.index("omni_view_world")

    def test_hero_icons_and_grid_read_the_ranked_list(self):
        tpl = _strip_jinja_comments(
            (ROOT / "templates" / "network_page.html.j2").read_text(encoding="utf-8"))
        orbit = tpl.split('<div class="hero-show-orbit">', 1)[1].split("</div>", 1)[0]
        assert "{% for s in _ranked %}" in orbit
        assert "{%- set _ranked = ranked_shows | default(all_shows) -%}" in tpl
        grid = tpl.split('id="show-showcase-grid">', 1)[1].split("</div>", 1)[0]
        assert "ranked_shows" in grid
        gen = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        assert '"ranked_shows": _rank_shows_by_audience(_build_all_shows_list())' in gen
