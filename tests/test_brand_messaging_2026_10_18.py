"""The tagline and the promise lead every surface (Oct 18 2026, operator).

"Feed your curiosity, not your anxiety." and "News and ideas from N free shows
on space, AI, markets, world news, science and more. Every story is sourced,
every claim is checked against its source, and you can read the article or
hear the episode it came from." — instead of a front page and a share card
that led on SpaceX and Tesla. ``engine/brand.py`` owns both sentences; every
page, card and meta description reads them from there.
"""
from __future__ import annotations

import datetime as dt
import re
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import generate_html as G  # noqa: E402
from engine import brand as B  # noqa: E402
from engine import landing_test as LT  # noqa: E402
from engine import share_cards as S  # noqa: E402

NOW = dt.datetime(2026, 10, 17, 13, 30, tzinfo=dt.timezone.utc)


def _strip_jinja_comments(text: str) -> str:
    return re.sub(r"\{#.*?#\}", "", text, flags=re.S)


class TestOneOwner:
    def test_the_operators_sentence_exactly(self):
        assert B.NETWORK_TAGLINE == "Feed your curiosity, not your anxiety."
        assert B.network_promise(26) == (
            "News and ideas from 26 free shows on space, AI, markets, world news, "
            "science and more. Every story is sourced, every claim is checked against "
            "its source, and you can read the article or hear the episode it came from.")

    def test_no_template_types_the_tagline(self):
        hits = []
        for path in (ROOT / "templates").glob("*.j2"):
            text = _strip_jinja_comments(path.read_text(encoding="utf-8"))
            if re.search(r"feed your curiosity|not your anxiety", text, re.I):
                hits.append(path.name)
        assert not hits, f"tagline typed in a template (use network_tagline): {hits}"

    def test_cards_use_the_brand_tagline(self):
        assert S.NETWORK_TAGLINE is B.NETWORK_TAGLINE
        src = (ROOT / "engine" / "share_cards.py").read_text(encoding="utf-8")
        assert "Feed your curiosity" not in src

    def test_the_count_is_the_free_shows(self):
        n = G._public_show_count_cached()
        assert n == len(G._public_shows())
        assert n < len(G.NETWORK_SHOWS)  # members-only and feedless shows excluded


@pytest.fixture(scope="module")
def home(tmp_path_factory) -> str:
    out = tmp_path_factory.mktemp("home")
    return G.generate_network_page(output_dir=out, now=NOW).read_text(encoding="utf-8")


class TestHomepage:
    def test_masthead_carries_tagline_and_promise(self, home):
        n = len(G._public_shows())
        assert f'<p class="lt-tagline">{B.NETWORK_TAGLINE}</p>' in home
        assert B.network_promise(n) in home

    def test_title_and_description_lead_with_the_tagline(self, home):
        title = re.search(r"<title>([^<]*)</title>", home).group(1)
        assert title.lower().endswith("feed your curiosity, not your anxiety")
        desc = re.search(r'<meta name="description" content="([^"]*)"', home).group(1)
        assert "Tesla" not in desc and "SpaceX" not in desc

    def test_footer_signs_with_the_tagline(self, home):
        assert f"{B.NETWORK_TAGLINE} Independent news and podcasts" in home
        assert "Zero fluff" not in home


class TestLeadRotation:
    def _story(self, slug, d, hub, img="u"):
        return {"slug": slug, "date_obj": date.fromisoformat(d), "image_url": img,
                "image_orientation": "landscape" if img else "", "hub_id": hub}

    def _day(self, d):
        return [self._story("spacex", d, "space"), self._story("tesla", d, "tesla"),
                self._story("models_agents", d, "ai"),
                self._story("omni_view_world", d, "world-news"),
                self._story("planetterrian", d, "science"),
                self._story("modern_investing", d, "markets"),
                self._story("unintended_consequences", d, "history-and-consequences")]

    def test_the_lead_subject_changes_daily_and_covers_the_promise(self):
        audience = ["tesla", "spacex", "models_agents", "omni_view_world",
                    "planetterrian", "modern_investing", "unintended_consequences"]
        leads = []
        for k in range(len(LT.LEAD_ROTATION)):
            d = (date(2026, 10, 18) + dt.timedelta(days=k)).isoformat()
            leads.append(LT.assemble(self._day(d), audience_order=audience)["lead"]["hub_id"])
        assert sorted(leads) == sorted(LT.LEAD_ROTATION)
        assert "tesla" not in leads

    def test_a_missing_subject_falls_through_to_the_next(self):
        d = "2026-10-18"
        hub = LT.LEAD_ROTATION[date.fromisoformat(d).toordinal() % len(LT.LEAD_ROTATION)]
        stories = [s for s in self._day(d) if s["hub_id"] != hub]
        lead = LT.assemble(stories)["lead"]
        assert lead["hub_id"] != hub and lead["hub_id"] in LT.LEAD_ROTATION

    def test_top_stories_show_range_before_repeating_a_beat(self):
        d = "2026-10-18"
        stories = self._day(d) + [self._story("ai_chips", d, "ai"),
                                  self._story("fascinating_frontiers", d, "space")]
        page = LT.assemble(stories, audience_order=["tesla", "spacex", "fascinating_frontiers",
                                                    "ai_chips"])
        beats = [LT._beat(s) for s in [page["lead"], *page["top"]]]
        assert len(beats) == len(set(beats)), beats  # SpaceX and Tesla are one beat


class TestNetworkCard:
    def test_card_art_is_the_networks_breadth(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_share_cards as BSC
        grid = BSC.NETWORK_COVER_SLUGS[:9]
        assert "tesla" not in grid and "spacex" not in grid

    def test_alt_text_is_the_tagline_and_promise(self):
        import json
        alts = json.loads(S.MANIFEST_PATH.read_text(encoding="utf-8"))["alt"]
        alt = alts["assets/share/network.jpg"]
        assert alt.startswith(f"{S.NETWORK_NAME}: {B.NETWORK_TAGLINE}")
        assert "every claim is checked against its source" in alt
