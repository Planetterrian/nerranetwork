"""One public show count where a live number is still shown (Oct 18 2026).

Show pages used to say "See all 29 shows" (all_shows minus RU), while the
homepage and join page said 26 (public / Personal roster). The Oct 18
follow-up made homepage + show-page CTAs count-free; join still derives
its "shows to pick from" from the Personal roster at build time — never
a typed integer. Explore / how-to-listen keep ``public_show_count()``.
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

    def test_show_page_see_all_is_count_free(self, tesla_html):
        assert "See all shows" in tesla_html
        assert not re.search(r"See all \d+ shows", tesla_html)

    def test_join_stat_matches_personal_roster(self, join_html):
        join_n = re.search(
            r"<strong>(\d+)</strong><span>shows to pick from</span>", join_html,
        )
        assert join_n, "join page missing shows-to-pick-from stat"
        assert int(join_n.group(1)) == len(G._personal_shows_list())

    def test_template_no_longer_counts_network_shows_for_see_all(self):
        src = (ROOT / "templates" / "show_page.html.j2").read_text(encoding="utf-8")
        assert "See all shows" in src
        assert "See all {{ public_show_count() }} shows" not in src
        assert "See all {{ _network_shows | length }} shows" not in src
