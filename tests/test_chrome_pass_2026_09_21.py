"""Guards for the chrome + browse pass (C2, 2026-09-21).

Three changes, all of them deliberately visible:

* the footer's show-derived links dropped from 53 per page to 20 — the show list
  is grouped by ``strand``, the eighteen per-show blog links became the hub and
  the topics map, and the seventeen per-show RSS links became one link to
  ``how-to-listen.html#feeds``, a page that already lists every feed;
* the strand grouping is computed ONCE (``show_groups``) and reused by the
  desktop Shows dropdown, the mobile menu, the footer and the Blog dropdown;
* ``/explore.html`` browses the catalogue by subject and language.

The load-bearing assertion here is the footer accordion one. On a phone the
column collapses via::

    .nn-footer-col > a,
    .nn-footer-col > ul { display: none; }

so a direct-child ``<ul>`` collapses correctly — but an element that is neither
an ``a`` nor a ``ul`` does NOT, which means a group label written as a
direct-child heading would sit visible above a collapsed column with nothing
under it. The labels therefore live inside the ``<ul>``, and this pins it.
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
sys.path.insert(0, str(ROOT))


def _fresh_chrome(tmp_path) -> str:
    """A page rendered NOW, for asserting on the chrome.

    Deliberately not the committed ``index.html``: generated HTML is refreshed
    by the pipeline rather than committed from a working tree, so on any
    checkout — including CI — the committed copy still carries the PREVIOUS
    footer. Two of these tests failed that way and a third passed vacuously
    (its loop found no group label to check) before this. ``explore.html`` is
    cheap to render and carries the same ``base.html.j2`` footer.
    """
    import generate_html as G
    out = G.generate_explore_page(output_dir=str(tmp_path))
    assert out is not None
    return Path(out).read_text(encoding="utf-8")


class _FooterColumns(HTMLParser):
    """Collect the direct-child tag names of every ``.nn-footer-col``."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.columns: list[list[str]] = []
        self._depth = None

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        classes = (d.get("class") or "").split()
        if self._depth is None:
            if "nn-footer-col" in classes:
                self._depth = 0
                self.columns.append([])
            return
        if self._depth == 0:
            self.columns[-1].append(tag)
        if tag not in ("img", "br", "source", "input", "meta", "hr"):
            self._depth += 1

    def handle_endtag(self, tag):
        if self._depth is None:
            return
        self._depth -= 1
        if self._depth < 0:
            self._depth = None


class TestTheFooterStillCollapsesOnAPhone:
    """The trap this pass found, stated as a test.

    The Sep 20 guard asserted the footer show list must "stay flat", on the
    premise that any nesting breaks the accordion. That premise was incomplete:
    the CSS hides ``.nn-footer-col > ul`` as well as ``> a``, so a direct-child
    list is fine. What is NOT fine is a direct child of any other kind.
    """

    ALLOWED = {"h4", "a", "ul", "p", "form", "div", "span", "svg", "script"}
    COLLAPSIBLE = {"a", "ul"}

    def test_the_accordion_css_hides_lists_as_well_as_links(self):
        base = (TEMPLATES / "base.html.j2").read_text(encoding="utf-8")
        assert ".nn-footer-col > ul { display: none; }" in base
        assert ".nn-footer-col.expanded > ul { display: block; }" in base

    def test_no_group_label_sits_outside_a_collapsible_child(self, tmp_path):
        """A label as a direct child would stay visible when collapsed."""
        home = _fresh_chrome(tmp_path)
        i = home.find('<h4>Shows</h4>')
        assert i != -1, "footer Shows column not found"
        column = home[i:home.find("</div>", i + 200)]
        for match in re.finditer(r'class="[^"]*nn-footer-grouplabel[^"]*"', column):
            before = column[:match.start()]
            assert before.rfind("<ul") > before.rfind("</ul>"), (
                "a group label is outside the <ul>; on a phone it would stay "
                "visible with every link beneath it collapsed away"
            )

    def test_the_show_column_children_are_all_collapsible(self, tmp_path):
        parser = _FooterColumns()
        parser.feed(_fresh_chrome(tmp_path))
        shows_col = next(
            (c for c in parser.columns if "ul" in c and c[:1] == ["h4"]), None)
        assert shows_col, "no footer column with a grouped list"
        for tag in shows_col[1:]:
            assert tag in self.COLLAPSIBLE, (
                f"<{tag}> is a direct child of the column and the accordion "
                "hides only 'a' and 'ul', so it would not collapse"
            )


class TestTheFooterRepeatsLessOnEveryPage:
    def test_per_show_rss_links_are_one_link_now(self):
        base = (TEMPLATES / "base.html.j2").read_text(encoding="utf-8")
        assert "{{ s.rss_file }}" not in base, (
            "the footer still repeats a per-show RSS link on every page"
        )
        assert "how-to-listen.html#feeds" in base

    def test_the_feeds_anchor_exists_on_the_page_it_points_at(self):
        """A link to an anchor nobody added just lands at the top of the page —
        the "advertises something that does not exist" class. The anchor must be
        on the section that lists the feeds, not merely present."""
        htl = (TEMPLATES / "how_to_listen.html.j2").read_text(encoding="utf-8")
        assert '<section class="htl-shows-section" id="feeds">' in htl
        base = (TEMPLATES / "base.html.j2").read_text(encoding="utf-8")
        assert "how-to-listen.html#feeds" in base, "nothing links the anchor"

    def test_per_show_blog_links_left_the_footer(self):
        base = (TEMPLATES / "base.html.j2").read_text(encoding="utf-8")
        footer = base.split("<h4>{{ t.footer_blog }}</h4>")[1][:900]
        assert "{{ s.blog_page }}" not in footer
        assert "blog/index.html" in footer

    def test_the_footer_carries_far_fewer_show_links(self, tmp_path):
        home = _fresh_chrome(tmp_path)
        i = home.find('class="nn-footer-grid"')
        j = home.find("nn-footer-bottom", i)
        footer = home[i:j]
        rss = len(re.findall(r'href="[^"]+\.rss"', footer))
        assert rss <= 3, f"{rss} RSS links in the footer; it was 19"


class TestTheStrandGroupingHasOneSource:
    def test_only_one_selectattr_computes_the_groups(self):
        base = (TEMPLATES / "base.html.j2").read_text(encoding="utf-8")
        assert base.count("selectattr('strand'") == 1, (
            "the grouping is copied again; a copied selector is how the footer "
            "drifts away from the nav"
        )

    def test_every_surface_uses_it(self):
        base = (TEMPLATES / "base.html.j2").read_text(encoding="utf-8")
        assert base.count("in show_groups") >= 4, (
            "expected the desktop Shows dropdown, the mobile menu, the footer "
            "and the Blog dropdown to share one grouping"
        )

    def test_both_navs_still_show_the_group_to_a_reader(self, tmp_path):
        """The property the old count-the-literal guard was reaching for."""
        home = _fresh_chrome(tmp_path)
        assert home.count("nn-nav-group-label") >= 2
        assert "Hosted by Mira" in home
        assert "nn-mobile-shows-title" in home


class TestExplorePage:
    def test_it_is_generated_registered_and_in_the_sitemap(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        assert "def generate_explore_page(" in src
        import inspect

        import generate_html as G
        assert "generate_explore_page" in inspect.getsource(G.generate_static_pages)
        sitemap_src = inspect.getsource(G.generate_sitemap)
        assert '"explore.html"' in sitemap_src

    def test_the_page_is_committed_so_the_site_has_it_now(self):
        """The nav links it from every page, so it cannot wait for a nightly.
        New generated pages are committed once when introduced — mira.html and
        topics/*.html set that precedent; what is never committed is a full
        regen from a working tree."""
        assert (ROOT / "explore.html").is_file()

    def test_the_nav_links_it(self):
        base = (TEMPLATES / "base.html.j2").read_text(encoding="utf-8")
        assert base.count("explore.html") >= 2, "desktop and mobile both link it"

    def test_the_grid_is_server_rendered(self, tmp_path):
        """With JS off the page must be the catalogue, not an empty shell."""
        html = _fresh_chrome(tmp_path)
        import generate_html as G
        assert len(re.findall(r'<div class="show-card-wrap"', html)) == len(
            G._build_all_shows_list())

    def test_the_filter_only_dims_and_never_fetches(self):
        """Checked on the TEMPLATE: the rendered page also carries the footer's
        newsletter form, which fetches legitimately and is not this page."""
        tpl = (TEMPLATES / "explore_page.html.j2").read_text(encoding="utf-8")
        assert "fetch(" not in tpl, "the filter must not fetch its own content"
        assert "is-dimmed" in tpl, "the filter should dim, not remove"
        assert ".remove()" not in tpl and "display='none'" not in tpl

    def test_subjects_come_from_the_curated_vocabulary(self, tmp_path):
        """Not the union of registry picker_tags.topics: that is 42 values with
        28 singletons and both `tech` and `technology`."""
        import generate_html as G
        from engine import topic_hubs as H

        html = _fresh_chrome(tmp_path)
        chips = set(re.findall(r'data-facet="hub" data-value="([^"]+)"', html))
        shows = G._build_all_shows_list()
        expected = {h["id"] for h in H.TOPIC_HUBS if H.hub_shows(h, shows)}
        assert chips == expected
        assert "technology" not in chips, (
            "a raw registry topic leaked into the chip vocabulary"
        )

    def test_the_filter_reads_attributes_the_card_actually_emits(self):
        """The JS and the macro have to agree, and nothing renders them
        together at build time."""
        html = (ROOT / "explore.html").read_text(encoding="utf-8")
        for attr in ("data-slug", "data-language"):
            assert f'{attr}="' in html, f"cards do not emit {attr}"
            assert f"getAttribute('{attr}')" in html, f"JS never reads {attr}"
        assert "is-dimmed" in html

    def test_the_dim_class_is_styled_where_both_pages_can_see_it(self):
        css = (ROOT / "styles" / "main.css").read_text(encoding="utf-8")
        assert ".show-card-wrap.is-dimmed" in css, (
            "the rule lived in the homepage's inline style; explore.html "
            "renders the same card and would dim nothing"
        )
        home_tpl = (TEMPLATES / "network_page.html.j2").read_text(encoding="utf-8")
        assert ".show-card-wrap.is-dimmed" not in home_tpl, "duplicated rule"


class TestTheCardIsOneMacro:
    def test_both_pages_render_the_same_macro(self):
        macros = (TEMPLATES / "_macros.html.j2").read_text(encoding="utf-8")
        assert "macro show_card(" in macros
        for name in ("network_page.html.j2", "explore_page.html.j2"):
            tpl = (TEMPLATES / name).read_text(encoding="utf-8")
            assert "import show_card" in tpl, f"{name} does not import it"
            assert "show_card(s, path_prefix)" in tpl

    def test_the_card_is_not_hand_copied_anywhere(self):
        for name in ("network_page.html.j2", "explore_page.html.j2"):
            tpl = (TEMPLATES / name).read_text(encoding="utf-8")
            assert 'class="show-card-wrap"' not in tpl, (
                f"{name} carries an inline copy of the card"
            )
