"""The tagline and the promise lead every surface (Oct 18 2026, operator).

"Feed your curiosity, not your anxiety." and the visitor-facing promise —
"Free news and ideas on space, AI, …" (count-free as of the Oct 18
follow-up) — instead of a front page and a share card that led on SpaceX
and Tesla. ``engine/brand.py`` still owns the tagline and the counted
``network_promise(n)`` used by share-card art; generate_html's Jinja
global serves the count-free visitor wording.
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
        assert f'<p class="lt-tagline">{B.NETWORK_TAGLINE}</p>' in home
        visitor = G._get_jinja_env().globals["network_promise"]()
        assert visitor in home
        assert "Free news and ideas on" in visitor
        assert not re.search(r"\d+ free shows", visitor)

    def test_title_and_description_lead_with_the_tagline(self, home):
        title = re.search(r"<title>([^<]*)</title>", home).group(1)
        assert title.lower().endswith("feed your curiosity, not your anxiety")
        desc = re.search(r'<meta name="description" content="([^"]*)"', home).group(1)
        # The flagships are named first; the rest of the promise follows.
        assert desc.index("SpaceX") < desc.index("Tesla") < desc.index("AI")

    def test_flagship_band_comes_before_every_other_block(self, home):
        band = home.index('id="flagships"')
        assert home.index('class="lt-lead"') < band
        for later in ('id="developing"', 'id="top-stories"', 'id="today"'):
            if later in home:
                assert band < home.index(later), later
        cards = re.findall(r'<article class="lt-flag"', home)
        assert len(cards) == len(B.FLAGSHIP_SHOW_SLUGS)
        sec = home[band:home.index("</section>", band)]
        assert sec.index("SpaceX Daily") < sec.index("Tesla Shorts Time")
        assert 'href="#flagships"' in home

    def test_masthead_actions_link_to_pages_that_exist(self, home):
        block = home[home.index('class="lt-masthead-actions"'):]
        block = block[:block.index("</p>")]
        hrefs = re.findall(r'href="([^"#]+)"', block)
        # "Find your show" goes where the nav's "Find your show" goes.
        assert "explore.html" in hrefs and "how-to-listen.html" in hrefs
        assert "start-here.html" not in hrefs
        for h in hrefs:
            assert (ROOT / h).is_file(), h

    def test_markets_strip_leads_with_the_flagship_ticker(self, home):
        strip = home[home.index('id="markets"'):]
        assert strip.index(">TSLA<") < strip.index(">NVDA<")

    def test_footer_signs_with_the_tagline(self, home):
        assert f"{B.NETWORK_TAGLINE} Independent news and podcasts" in home
        assert "Zero fluff" not in home


class TestLeadRotation:
    """The lead rotates by subject; the flagships have their own band and are
    never the lead or a top story (they stay in the chronological Latest)."""

    def _story(self, slug, d, hub, img="u"):
        return {"slug": slug, "date_obj": date.fromisoformat(d), "image_url": img,
                "image_orientation": "landscape" if img else "", "hub_id": hub}

    def _day(self, d):
        return [self._story("spacex", d, "space"), self._story("tesla", d, "tesla"),
                self._story("fascinating_frontiers", d, "space"),
                self._story("models_agents", d, "ai"),
                self._story("omni_view_world", d, "world-news"),
                self._story("planetterrian", d, "science"),
                self._story("modern_investing", d, "markets"),
                self._story("unintended_consequences", d, "history-and-consequences")]

    AUDIENCE = ["tesla", "spacex", "models_agents", "omni_view_world",
                "planetterrian", "modern_investing", "unintended_consequences",
                "fascinating_frontiers"]

    def _page(self, d, stories=None):
        return LT.assemble(stories or self._day(d), audience_order=self.AUDIENCE,
                           flagships=B.FLAGSHIP_SHOW_SLUGS)

    def test_flagships_have_their_own_band_every_day(self):
        for k in range(7):
            d = (date(2026, 10, 18) + dt.timedelta(days=k)).isoformat()
            page = self._page(d)
            assert [s["slug"] for s in page["flagships"]] == list(B.FLAGSHIP_SHOW_SLUGS)
            placed = [page["lead"], *page["top"], *page["more"],
                      *(s for sec in page["sections"] for s in sec["stories"])]
            assert not {s["slug"] for s in placed} & set(B.FLAGSHIP_SHOW_SLUGS)
            assert {"spacex", "tesla"} <= {s["slug"] for s in page["latest"]}

    def test_the_lead_subject_changes_daily_and_covers_the_promise(self):
        leads = []
        for k in range(len(LT.LEAD_ROTATION)):
            d = (date(2026, 10, 18) + dt.timedelta(days=k)).isoformat()
            leads.append(self._page(d)["lead"]["hub_id"])
        assert sorted(leads) == sorted(LT.LEAD_ROTATION)

    def test_a_missing_subject_falls_through_to_the_next(self):
        d = "2026-10-18"
        hub = LT.LEAD_ROTATION[date.fromisoformat(d).toordinal() % len(LT.LEAD_ROTATION)]
        stories = [s for s in self._day(d) if s["hub_id"] != hub]
        lead = self._page(d, stories)["lead"]
        assert lead["hub_id"] != hub and lead["hub_id"] in LT.LEAD_ROTATION

    def test_only_flagships_published_means_they_lead_as_before(self):
        d = "2026-10-18"
        page = self._page(d, [self._story("spacex", d, "space"),
                              self._story("tesla", d, "tesla")])
        assert page["flagships"] == [] and page["lead"]["slug"] in {"spacex", "tesla"}

    def test_top_stories_show_range_before_repeating_a_beat(self):
        d = "2026-10-18"
        stories = self._day(d) + [self._story("ai_chips", d, "ai")]
        page = self._page(d, stories)
        beats = [LT._beat(s) for s in [page["lead"], *page["top"]]]
        assert len(beats) == len(set(beats)), beats


class TestNetworkCard:
    def test_card_art_leads_with_the_flagships_then_the_breadth(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_share_cards as BSC
        assert B.FLAGSHIP_SHOW_SLUGS == ("spacex", "tesla")
        # The breadth row never repeats a flagship tile.
        assert not set(BSC.NETWORK_COVER_SLUGS) & set(B.FLAGSHIP_SHOW_SLUGS)
        src = (ROOT / "scripts" / "build_share_cards.py").read_text(encoding="utf-8")
        assert "flagship_covers=_covers(shows, FLAGSHIP_SHOW_SLUGS)" in src

    def test_flagship_layout_draws_large_tiles(self):
        from PIL import Image
        tile = lambda c: Image.new("RGB", (400, 400), c)  # noqa: E731
        card = S.render_network_card(show_count=26,
                                     flagship_covers=[tile("red"), tile("blue")],
                                     covers=[tile("green")] * 6)
        assert card.size == (S.WIDTH, S.HEIGHT)
        # The first flagship tile's centre is the flagship's own colour.
        r, g, b = card.convert("RGB").getpixel((840, 140))
        assert r > 150 and g < 90 and b < 90

    def test_alt_text_is_the_tagline_and_promise(self):
        import json
        alts = json.loads(S.MANIFEST_PATH.read_text(encoding="utf-8"))["alt"]
        alt = alts["assets/share/network.jpg"]
        assert alt.startswith(f"{S.NETWORK_NAME}: {B.NETWORK_TAGLINE}")
        assert "every claim is checked against its source" in alt
        assert alt.endswith("Featuring SpaceX Daily and Tesla Shorts Time.")
