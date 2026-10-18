"""One public show count on home, join and show pages (Oct 18 2026).

Show pages used to say "See all 29 shows" (all_shows minus RU), while the
homepage and join page said 26 (public / Personal roster). Both numbers
were honest for their filter; visitors saw three pages disagree. The show
page now reads ``public_show_count()`` — the same source as the homepage.
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


@pytest.fixture(scope="module")
def expected_n() -> int:
    n = len(G._public_shows())
    assert n == G._public_show_count_cached()
    assert n > 0
    return n


@pytest.fixture(scope="module")
def home_html(tmp_path_factory) -> str:
    out = tmp_path_factory.mktemp("home")
    return G.generate_network_page(output_dir=out, now=NOW).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def join_html(tmp_path_factory) -> str:
    out = tmp_path_factory.mktemp("join")
    path = G.generate_join_page(output_dir=out)
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def tesla_html(tmp_path_factory) -> str:
    out = tmp_path_factory.mktemp("tesla")
    path = G.generate_show_page("tesla", output_dir=out)
    return Path(path).read_text(encoding="utf-8")


class TestPublicShowCountAcrossSurfaces:
    def test_jinja_global_is_the_cached_counter(self):
        env = G._get_jinja_env()
        assert env.globals["public_show_count"] is G._public_show_count_cached
        assert env.globals["public_show_count"]() == len(G._public_shows())

    def test_show_page_see_all_matches_public_count(self, tesla_html, expected_n):
        m = re.search(r"See all (\d+) shows", tesla_html)
        assert m, "tesla show page missing 'See all N shows' link"
        assert int(m.group(1)) == expected_n

    def test_homepage_and_join_and_show_page_agree(
        self, home_html, join_html, tesla_html, expected_n,
    ):
        home_n = re.search(
            r"News and ideas from (\d+) free shows", home_html,
        )
        assert home_n, "homepage missing network_promise show count"
        assert int(home_n.group(1)) == expected_n

        join_n = re.search(
            r"<strong>(\d+)</strong><span>shows to pick from</span>", join_html,
        )
        assert join_n, "join page missing shows-to-pick-from stat"
        assert int(join_n.group(1)) == expected_n

        see_all = re.search(r"See all (\d+) shows", tesla_html)
        assert see_all
        assert int(see_all.group(1)) == expected_n

        assert int(home_n.group(1)) == int(join_n.group(1)) == int(see_all.group(1))

    def test_template_no_longer_counts_network_shows_for_see_all(self):
        src = (ROOT / "templates" / "show_page.html.j2").read_text(encoding="utf-8")
        assert "public_show_count()" in src
        assert "See all {{ _network_shows | length }} shows" not in src
