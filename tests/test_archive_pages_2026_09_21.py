"""Two archives that a browser with no JavaScript could not read.

**The summaries pages were 100% client-rendered.** The committed HTML held a
``<div id="summaries-container">`` containing the words *"Loading … summaries
…"* and a script that fetched the JSON and wrote the list. With JavaScript
off, before the fetch resolved, or to a crawler that does not execute
scripts, the page WAS that sentence — including
``nerra-daily-summaries.html``, the archive of the network's most-visited
show. Deferred twice as "search engines run JavaScript now". They do,
sometimes, on a delay, with no guarantee, and none of that helps a reader on
a train.

**The per-show blog indexes were complete lists.** Tesla's was 217 cards and
232 KB, growing by one a day forever. The Sep 3 pass capped the network hub
for exactly this reason and deliberately left the per-show ones complete;
completeness is pages now, which is the same promise with a bounded first
byte.

Every render here goes into ``tmp_path`` via ``output_dir=``. Generated HTML
is refreshed by the pipeline, not committed from a working tree, so a guard
that reads a committed page is asserting against the previous chrome.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import generate_html as G
from engine.blog import (
    BLOG_INDEX_POSTS_PER_PAGE,
    blog_index_page_count,
    blog_index_page_path,
)
from engine.summaries_ssr import SSR_CARD_LIMIT, summary_cards, summary_to_html

ROOT = Path(__file__).resolve().parent.parent


def _markup_only(html: str) -> str:
    """Drop ``<script>`` and ``<style>`` blocks.

    The card markup also exists as a JavaScript template literal inside the
    page's own script, so counting class names across the whole document
    measures the script, not what a browser renders before it runs.
    """
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.S)
    return re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.S)


# ---------------------------------------------------------------------------
# The markdown subset
# ---------------------------------------------------------------------------

class TestSummaryMarkdown:
    def test_it_escapes_before_it_renders(self):
        """The escaping IS the safety property — nothing may inject markup."""
        out = summary_to_html('<script>alert(1)</script> & "quoted"')
        assert "<script>" not in out
        assert "&lt;script&gt;" in out

    def test_bold_bullets_headings_and_rules(self):
        out = summary_to_html(
            "### Section\n\n- a point with **bold**\n- another\n\nA para.\n---\n")
        assert "<h3>Section</h3>" in out
        assert "<ul>" in out and "</ul>" in out
        assert "<strong>bold</strong>" in out
        assert "<p>A para.</p>" in out
        assert "<hr" in out

    def test_the_hook_blockquote_keeps_its_rule(self):
        out = summary_to_html("> **The hook sentence.**")
        assert "border-left" in out
        assert "The hook sentence." in out
        # The bold markers inside a hook are consumed, not printed.
        assert "**" not in out

    def test_a_list_is_closed_before_a_following_paragraph(self):
        out = summary_to_html("- one\n- two\n\nAfter the list.")
        assert out.index("</ul>") < out.index("After the list.")

    def test_empty_input_is_empty_output(self):
        assert summary_to_html("") == ""
        assert summary_to_html(None) == ""


# ---------------------------------------------------------------------------
# The cards
# ---------------------------------------------------------------------------

class TestSummaryCards:
    def test_a_missing_or_broken_file_yields_nothing(self, tmp_path):
        assert summary_cards(tmp_path / "nope.json", "x") == []
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        assert summary_cards(bad, "x") == []

    def test_both_committed_shapes_are_read(self):
        """``{"summaries": [...]}`` and ``{"episodes": [...]}``."""
        daily = summary_cards(
            ROOT / "digests" / "nerra_daily" / "summaries_nerra_daily.json",
            "nerra_daily")
        interviews = summary_cards(
            ROOT / "digests" / "age_of_ai" / "summaries_age_of_ai.json",
            "age_of_ai")
        assert daily and interviews

    def test_newest_first(self):
        cards = summary_cards(
            ROOT / "digests" / "nerra_daily" / "summaries_nerra_daily.json",
            "nerra_daily")
        numbers = [c["episode_num"] for c in cards if c["episode_num"]]
        assert numbers == sorted(numbers, reverse=True)

    def test_it_never_exceeds_the_limit(self):
        cards = summary_cards(
            ROOT / "digests" / "tesla_shorts_time" / "summaries_tesla.json",
            "tesla")
        assert 0 < len(cards) <= SSR_CARD_LIMIT

    def test_the_transcript_link_matches_the_post_path(self):
        """A card that links a page the blog generator never writes is a 404."""
        cards = summary_cards(
            ROOT / "digests" / "age_of_ai" / "summaries_age_of_ai.json",
            "age_of_ai")
        for card in cards:
            if not card["blog_url"]:
                continue
            assert re.fullmatch(r"blog/age_of_ai/ep\d{3}\.html",
                                card["blog_url"]), card["blog_url"]


class TestRenderedSummariesPage:
    @pytest.fixture(scope="module")
    def daily_page(self, tmp_path_factory):
        out = tmp_path_factory.mktemp("summaries")
        return G.generate_summaries_page(
            "nerra_daily", output_dir=out).read_text(encoding="utf-8")

    def test_the_page_is_readable_without_javascript(self, daily_page):
        body = _markup_only(daily_page)
        assert body.count('class="nn-summary-item"') == SSR_CARD_LIMIT
        assert "Loading Nerra Daily summaries" not in body, (
            "the container still ships only the loading sentence")

    def test_it_can_be_listened_to_without_javascript(self, daily_page):
        assert _markup_only(daily_page).count("<audio") >= SSR_CARD_LIMIT

    def test_it_says_what_needs_javascript(self, daily_page):
        """An honest partial beats a silent one."""
        assert "<noscript>" in daily_page
        noscript = re.search(r"<noscript>(.*?)</noscript>", daily_page, re.S)
        assert "archive" in noscript.group(1).lower()

    def test_a_show_with_no_episodes_keeps_its_empty_state(self, tmp_path):
        """Never render an empty rail where a message belongs."""
        html = G.generate_summaries_page(
            "nerra_voices", output_dir=tmp_path).read_text(encoding="utf-8")
        body = _markup_only(html)
        assert body.count('class="nn-summary-item"') == 0
        assert "Loading" in body

    def test_every_show_still_renders(self, tmp_path):
        for slug in G.NETWORK_SHOWS:
            assert G.generate_summaries_page(
                slug, output_dir=tmp_path) is not None


# ---------------------------------------------------------------------------
# Blog pagination
# ---------------------------------------------------------------------------

class TestBlogPagination:
    @pytest.mark.parametrize("total,expected", [
        (0, 1), (1, 1), (BLOG_INDEX_POSTS_PER_PAGE, 1),
        (BLOG_INDEX_POSTS_PER_PAGE + 1, 2),
        (BLOG_INDEX_POSTS_PER_PAGE * 3, 3),
    ])
    def test_page_count(self, total, expected):
        assert blog_index_page_count(total) == expected

    def test_page_one_keeps_the_live_url(self):
        """Every feed, nav item and crawler already points at index.html."""
        assert blog_index_page_path("tesla", 1) == "blog/tesla/index.html"
        assert blog_index_page_path("tesla", 2) == "blog/tesla/page2.html"

    @pytest.fixture(scope="module")
    def tesla_blog(self, tmp_path_factory):
        out = tmp_path_factory.mktemp("blogidx")
        G.generate_blog_index("tesla", output_dir=out)
        return out / "blog" / "tesla"

    def test_the_first_page_is_bounded(self, tesla_blog):
        html = (tesla_blog / "index.html").read_text(encoding="utf-8")
        assert html.count('class="blog-idx-card"') == BLOG_INDEX_POSTS_PER_PAGE

    def test_every_post_is_still_reachable(self, tesla_blog):
        """Pagination must not lose an episode from the archive."""
        seen = set()
        for page in sorted(tesla_blog.glob("*.html")):
            for match in re.finditer(r'href="(ep\d{3}\.html)"',
                                     page.read_text(encoding="utf-8")):
                seen.add(match.group(1))
        from engine.blog import extract_blog_metadata

        digest_dir = ROOT / "digests" / "tesla_shorts_time"
        episodes = set()
        for md in digest_dir.glob("*.md"):
            meta = extract_blog_metadata(
                md.read_text(encoding="utf-8"), "tesla", md.name, file_path=md)
            episodes.add(f"ep{meta['episode_num']:03d}.html")
        missing = episodes - seen
        assert not missing, f"{len(missing)} episodes fell off the archive"

    def test_the_pages_chain_in_both_directions(self, tesla_blog):
        first = (tesla_blog / "index.html").read_text(encoding="utf-8")
        second = (tesla_blog / "page2.html").read_text(encoding="utf-8")
        assert 'rel="next"' in first and 'rel="prev"' not in first
        assert 'rel="prev"' in second and 'rel="next"' in second

    def test_each_page_is_its_own_canonical(self, tesla_blog):
        """Pointing them all at page 1 tells a crawler the archive is a
        duplicate of its own first screen."""
        second = (tesla_blog / "page2.html").read_text(encoding="utf-8")
        canonical = re.search(r'rel="canonical" href="([^"]*)"', second)
        assert canonical and canonical.group(1).endswith("page2.html")

    def test_each_page_has_its_own_title(self, tesla_blog):
        second = (tesla_blog / "page2.html").read_text(encoding="utf-8")
        title = re.search(r"<title>(.*?)</title>", second, re.S).group(1)
        assert "page 2" in title

    def test_a_short_archive_renders_no_pager(self, tmp_path):
        """A show under one page is unchanged, pager and all absent."""
        G.generate_blog_index("age_of_ai", output_dir=tmp_path)
        blog_dir = tmp_path / "blog" / "age_of_ai"
        assert not list(blog_dir.glob("page*.html"))
        html = (blog_dir / "index.html").read_text(encoding="utf-8")
        assert "blog-idx-pager" not in html

    def test_a_shrunk_catalogue_drops_its_stale_pages(self, tmp_path):
        """The DP Pod prune removed 19 episodes in one day.

        A page left behind would stay live, stay in the sitemap, and list
        posts that had moved to another page.
        """
        blog_dir = tmp_path / "blog" / "age_of_ai"
        blog_dir.mkdir(parents=True)
        stale = blog_dir / "page7.html"
        stale.write_text("old", encoding="utf-8")
        G.generate_blog_index("age_of_ai", output_dir=tmp_path)
        assert not stale.exists()

    def test_every_show_still_builds_an_index(self, tmp_path):
        for slug in G.NETWORK_SHOWS:
            G.generate_blog_index(slug, output_dir=tmp_path)
            index = tmp_path / "blog" / slug / "index.html"
            assert index.exists(), f"{slug} produced no blog index"
