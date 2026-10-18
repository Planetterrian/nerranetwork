"""Visitor-facing copy drops hard-coded show counts (Oct 18 2026 follow-up).

Homepage hero / about / og alt, show-page "See all", and the join Soft
Personal tip line. Counts that remain (explore, how-to-listen, join stats)
must come from the live public/Personal roster — never a typed integer.
"""
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import generate_html as G  # noqa: E402

NOW = dt.datetime(2026, 10, 18, 13, 30, tzinfo=dt.timezone.utc)

PROMISE_NO_COUNT = (
    "Free news and ideas on space, AI, markets, world news, science and more. "
    "Every story is sourced, every claim is checked against its source, "
    "and you can read the article or hear the episode it came from.")
TIPS_LINE = "Get Personal tips by email — no charge, no card →"
OLD_TIPS = "Not ready yet? Get Personal tips by email — no charge, no card →"


@pytest.fixture(scope="module")
def home_html(tmp_path_factory) -> str:
    out = tmp_path_factory.mktemp("home")
    return G.generate_network_page(output_dir=out, now=NOW).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def join_html(tmp_path_factory) -> str:
    out = tmp_path_factory.mktemp("join")
    return G.generate_join_page(output_dir=out).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def tesla_html(tmp_path_factory) -> str:
    out = tmp_path_factory.mktemp("tesla")
    return Path(G.generate_show_page("tesla", output_dir=out)).read_text(encoding="utf-8")


class TestHomepageCountFreeCopy:
    def test_stories_header_is_fixed(self, home_html):
        assert "Stories from across the network" in home_html
        assert not re.search(r"Stories from \d+ shows", home_html)

    def test_all_shows_header_has_no_number(self, home_html):
        assert ">All shows<" in home_html
        assert not re.search(r">All \d+ shows<", home_html)

    def test_hero_and_about_use_count_free_promise(self, home_html):
        assert PROMISE_NO_COUNT in home_html
        assert "News and ideas from" not in home_html
        assert "network of free shows covering" in home_html
        assert not re.search(r"network of \d+ free shows", home_html)

    def test_og_and_twitter_alt_are_count_free(self, home_html):
        for prop in ("og:image:alt", "twitter:image:alt"):
            if prop.startswith("og"):
                m = re.search(rf'<meta property="{prop}" content="([^"]*)"', home_html)
            else:
                m = re.search(rf'<meta name="{prop}" content="([^"]*)"', home_html)
            assert m, prop
            alt = m.group(1)
            assert "Free news and ideas on space, AI" in alt
            assert not re.search(r"\d+ free shows", alt)


class TestShowPageAndJoin:
    def test_see_all_shows_has_no_number(self, tesla_html):
        assert "See all shows" in tesla_html
        assert not re.search(r"See all \d+ shows", tesla_html)

    def test_join_tips_line_drops_not_ready_yet(self, join_html):
        assert TIPS_LINE in join_html
        assert OLD_TIPS not in join_html

    def test_join_show_stat_is_live_derived(self, join_html):
        """Join may still name a count, but only from the Personal roster."""
        m = re.search(
            r"<strong>(\d+)</strong><span>shows to pick from</span>", join_html,
        )
        assert m
        assert int(m.group(1)) == len(G._personal_shows_list())


class TestTemplatesNeverTypeAShowCount:
    def test_homepage_and_show_templates(self):
        net = (ROOT / "templates" / "network_page.html.j2").read_text(encoding="utf-8")
        show = (ROOT / "templates" / "show_page.html.j2").read_text(encoding="utf-8")
        join = (ROOT / "templates" / "join_page.html.j2").read_text(encoding="utf-8")
        assert "Stories from across the network" in net
        assert "All shows" in net
        assert "network of free shows covering" in net
        assert "See all shows" in show
        assert "See all {{" not in show
        assert TIPS_LINE in join
        assert OLD_TIPS not in join
