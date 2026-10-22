"""Oct 22 2026 crawl / indexing pass — pagination noindex, sitemap order,
same-show related links.

Google indexes ~1.7K pages here and sends ~14 organic sessions/month; the
guards pin the rules that concentrate crawl budget on show hubs and fresh
episodes without noindexing published episode content.
"""

from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

import generate_html as G
from engine.blog import generate_blog_index_html

ROOT = Path(__file__).resolve().parent.parent
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def _locs(xml: str) -> list[str]:
    root = ET.fromstring(xml)
    return [el.text for el in root.findall("sm:url/sm:loc", NS)]


class TestBlogArchiveNoindex:
    def test_threshold_constant(self):
        assert G.BLOG_ARCHIVE_NOINDEX_FROM_PAGE == 3

    def test_page_number_helper(self):
        assert G.blog_archive_page_number("page3.html") == 3
        assert G.blog_archive_page_number("index.html") is None
        assert G.sitemap_should_include_blog_archive_page("page2.html")
        assert not G.sitemap_should_include_blog_archive_page("page3.html")

    def test_template_emits_noindex_from_page_three(self, tmp_path):
        cfg = G.NETWORK_SHOWS["tesla"]
        env = G._get_jinja_env()
        posts = [{"episode_num": i, "title": f"T{i}", "hook": "", "date": "2026-01-01",
                  "reading_time_min": 3, "filename": f"x{i}.md"} for i in range(1, 4)]
        html3 = generate_blog_index_html(
            posts, cfg, env, page=3, total_pages=5)
        html1 = generate_blog_index_html(
            posts, cfg, env, page=1, total_pages=5)
        html2 = generate_blog_index_html(
            posts, cfg, env, page=2, total_pages=5)
        assert 'name="robots" content="noindex, follow"' in html3
        assert 'name="robots" content="noindex' not in html1.split("</head>")[0]
        assert 'name="robots" content="noindex' not in html2.split("</head>")[0]

    def test_self_canonical_and_absolute_rel_links(self):
        cfg = G.NETWORK_SHOWS["tesla"]
        env = G._get_jinja_env()
        posts = [{"episode_num": 1, "title": "T", "hook": "", "date": "2026-01-01",
                  "reading_time_min": 3, "filename": "x.md"}]
        html = generate_blog_index_html(
            posts, cfg, env, page=2, total_pages=4)
        assert 'rel="canonical" href="https://nerranetwork.com/blog/tesla/page2.html"' in html
        assert 'rel="prev" href="https://nerranetwork.com/blog/tesla/index.html"' in html
        assert 'rel="next" href="https://nerranetwork.com/blog/tesla/page3.html"' in html

    def test_blog_index_links_show_hub(self):
        cfg = G.NETWORK_SHOWS["tesla"]
        env = G._get_jinja_env()
        html = generate_blog_index_html([], cfg, env, page=1, total_pages=1)
        assert f'href="' in html
        assert cfg["show_page"] in html
        assert "Listen to Tesla Shorts Time" in html


class TestMoreFromShow:
    def test_neighbours_exclude_self_and_prefer_nearby(self):
        # SpaceX has a dense early archive on disk.
        rows = G.more_from_show_episodes("spacex", 5, limit=5)
        assert rows
        assert all(r["episode_num"] != 5 for r in rows)
        assert all(r["url"] == f"ep{r['episode_num']:03d}.html" for r in rows)
        # Closest episode numbers first.
        deltas = [abs(r["episode_num"] - 5) for r in rows]
        assert deltas == sorted(deltas)

    def test_template_block_renders(self):
        src = (ROOT / "templates" / "blog_post.html.j2").read_text(encoding="utf-8")
        assert 'id="more-from-show"' in src
        assert "More from {{ show_name }}" in src
        assert "more_from_show_episodes" in src


@pytest.fixture(scope="module")
def _sitemap_xml(tmp_path_factory):
    out = tmp_path_factory.mktemp("sm") / "sitemap.xml"
    G.generate_sitemap(out=out)
    return out.read_text(encoding="utf-8")


class TestSitemapCrawlPass:
    @pytest.fixture(scope="module")
    def sitemap_xml(self, _sitemap_xml):
        return _sitemap_xml

    def test_no_deep_archive_pages(self, sitemap_xml):
        locs = _locs(sitemap_xml)
        deep = [u for u in locs if re.search(r"/blog/[^/]+/page([3-9]|[1-9]\d+)\.html$", u)]
        assert deep == []

    def test_page_two_still_listed_when_present(self, sitemap_xml):
        locs = _locs(sitemap_xml)
        # Tesla has many pages; page2 must remain discoverable.
        assert any(u.endswith("/blog/tesla/page2.html") for u in locs)

    def test_utilities_excluded(self, sitemap_xml):
        locs = _locs(sitemap_xml)
        for name in G.SITEMAP_EXCLUDE_UTILITIES:
            assert not any(u.endswith("/" + name) for u in locs), name
        # Funnel landers stay indexed (explicitly NOT in the exclude set).
        assert "join.html" not in G.SITEMAP_EXCLUDE_UTILITIES
        assert "personal-interest.html" not in G.SITEMAP_EXCLUDE_UTILITIES
        assert any(u.endswith("/join.html") for u in locs)
        assert any(u.endswith("/personal-interest.html") for u in locs)

    def test_show_hubs_before_episodes(self, sitemap_xml):
        locs = _locs(sitemap_xml)
        # First URL is the homepage; a show hub appears before any /blog/.../ep.
        first_ep = next(i for i, u in enumerate(locs) if re.search(r"/blog/[^/]+/ep\d+\.html$", u))
        first_hub = next(i for i, u in enumerate(locs)
                         if u.endswith("/tesla.html") or u.endswith("/spacex.html"))
        assert first_hub < first_ep

    def test_episodes_newest_first(self, sitemap_xml):
        root = ET.fromstring(sitemap_xml)
        ep_dates = []
        for url in root.findall("sm:url", NS):
            loc = url.findtext("sm:loc", default="", namespaces=NS)
            if not re.search(r"/blog/[^/]+/ep\d+\.html$", loc):
                continue
            lastmod = url.findtext("sm:lastmod", default="", namespaces=NS)
            ep_dates.append(lastmod)
        assert ep_dates
        assert ep_dates == sorted(ep_dates, reverse=True)

    def test_player_listed_in_source_but_filtered(self):
        """The extras loop still names player.html; the skip set drops it."""
        import inspect
        src = inspect.getsource(G.generate_sitemap)
        assert '"player.html"' in src
        assert "SITEMAP_EXCLUDE_UTILITIES" in src
