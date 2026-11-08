"""Nov 8 2026: the Nerra Daily email looks like the front page.

Patrick asked for an email that looks more like the landing page and reads
like a news update, with links to the shows and to the articles behind
them. This adds the landing page's masthead, one lead story with its
picture, cards with a kicker and a serif headline, each hook story's own
sources, and "More in this episode" lines that link to the articles the
episode reported from. The links come from the digest's own Source lines
(``engine.landing_test.story_links``). Nothing is looked up, and nothing
calls a model. The cards' article links are the only part that gives way
to Gmail's clipping point.
"""

from __future__ import annotations

import datetime as dt
import re

import pytest

from engine import landing_test as lt
from engine import nerra_daily_email as nde

from tests.test_nerra_daily_email_2026_11_03 import DIGEST, HOOK, NOW, _front  # noqa: E402

DAY = dt.date(2026, 11, 2)
IMAGE = "https://gallery.nerranetwork.com/{slug}/2026-11-02/ep100/abc.thumb.webp"


def _rich_front(day=DAY):
    """The Nov 3 fixture, with pictures, sources and article links."""
    front = _front(day)
    for slug, show in front["shows"].items():
        if slug == "nerra_daily":
            continue
        story = show["stories"][0]
        story["image_url"] = IMAGE.format(slug=slug)
        story["sources"] = [{"outlet": "reuters.com", "url": f"https://www.reuters.com/{slug}?utm_source=rss"}]
        story["reads"] = [{"title": f"{show['name']} read {n}", "url": f"https://example.org/{slug}/{n}",
                           "outlet": "example.org"} for n in (1, 2, 3)]
    return front


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(nde, "already_sent", lambda day, root=None, **k: {})
    monkeypatch.setattr(nde, "video_links", lambda *a: {})
    monkeypatch.setattr(nde, "week_records", lambda slug, day, root=None: [])
    return monkeypatch


@pytest.fixture
def composed(patched):
    return nde.compose(DAY, now=NOW, front=_rich_front(), trial_days=7)


def _lead(composed):
    return nde.choose_lead(nde.pick_stories(nde.eligible_shows(_rich_front()), DAY, {}), DAY)


# ---------------------------------------------------------------------------
# The links, from the digest's own Source lines
# ---------------------------------------------------------------------------


class TestStoryLinks:
    def test_sources_are_the_hook_storys_links_one_per_outlet(self):
        row = lt.story_json({"slug": "tesla", "hook": HOOK}, record={"content": DIGEST, "episode_num": "653"})
        assert row["sources"] == [
            {"outlet": "finance.biggo.com", "url": "https://finance.biggo.com/news/1"},
            {"outlet": "reuters.com", "url": "https://www.reuters.com/x"},
        ]

    def test_reads_pair_each_headline_with_its_own_items_link(self):
        row = lt.story_json({"slug": "tesla", "hook": HOOK}, record={"content": DIGEST, "episode_num": "653"})
        assert row["reads"] == [
            {"title": "Tesla Norway sales hit 130.7% YoY growth and best October ever",
             "url": "https://x.com/tslaming/status/1", "outlet": "x.com"},
            {"title": "Texas family finds missing cat inside their own Tesla",
             "url": "https://khou.com/x", "outlet": "khou.com"},
        ]

    def test_a_story_with_no_link_gets_none(self):
        bare = DIGEST.replace(" Source: [khou.com](https://khou.com/x)", "")
        _, reads = lt.story_links(bare, HOOK, ["Texas family finds missing cat inside their own Tesla"])
        assert reads == []

    def test_a_read_never_repeats_a_source(self):
        sources, reads = lt.story_links(DIGEST, HOOK, ["Tesla's October registrations surge in Northern Europe"])
        assert {s["url"] for s in sources}.isdisjoint({r["url"] for r in reads})

    def test_outlet_is_the_address(self):
        assert lt.outlet_name("https://www.theverge.com/x") == "theverge.com"
        assert lt.outlet_name("https://news.mit.edu:443/a") == "news.mit.edu"
        assert lt.outlet_name("") == ""

    def test_feed_tracking_parameters_are_dropped(self):
        assert nde._clean_url("https://a.com/x?utm_source=rss&id=7") == "https://a.com/x?id=7"
        assert nde._clean_url("https://a.com/x?traffic_source=rss") == "https://a.com/x"
        assert nde._clean_url("https://a.com/x") == "https://a.com/x"


# ---------------------------------------------------------------------------
# The front page in an email
# ---------------------------------------------------------------------------


class TestTheLead:
    def test_the_lead_rotates_by_date_among_stories_with_a_picture_and_a_deck(self):
        picks = nde.pick_stories(nde.eligible_shows(_rich_front()), DAY, {})
        leads = {nde.choose_lead(picks, DAY + dt.timedelta(days=n)).show.slug for n in range(6)}
        assert leads == {"omni_view_world", "models_agents", "omni_view", "mag7"}
        assert nde.choose_lead(picks, DAY) is nde.choose_lead(picks, DAY)

    def test_a_flagship_never_leads(self):
        assert not set(nde.LEAD_POOL) & {"spacex", "tesla"}

    def test_no_picture_no_lead(self):
        picks = nde.pick_stories(nde.eligible_shows(_front()), DAY, {})
        assert nde.choose_lead(picks, DAY) is None

    def test_every_copy_opens_on_the_lead_and_its_show_is_not_repeated(self, composed):
        lead = _lead(composed)
        name = lead.show.name
        for tags, subscriber in ((["nerra-member"], True), ([lead.show.tag], True),
                                 ([s.tag for s in nde.eligible_shows(_rich_front())], True), ([], False)):
            copy = nde.render_for(composed.body, tags, subscriber=subscriber)
            body = copy.split("padding:16px 24px 24px;", 1)[1]
            # Before the first section rule ("Your shows today", "Today on Nerra").
            assert body.index(f"{name} lead story") < body.index("border-top:3px solid")
            assert body.count(f"{name} lead story") == 1, tags
            assert f"{name} read 3" in body  # the lead keeps three article links

    def test_the_lead_picture_spans_the_column_and_links_the_episode(self, composed):
        lead = _lead(composed)
        src = composed.body
        img = re.search(r'<a href="([^"]+)"><img src="' + re.escape(IMAGE.format(slug=lead.show.slug)), src)
        assert img and "utm_source=newsletter" in img.group(1)
        assert f'width="{nde.LEAD_IMAGE_PX}"' in src


class TestTheCards:
    def test_a_card_has_kicker_headline_deck_sources_and_reads(self, composed):
        copy = nde.render_for(composed.body, ["nerra-member", "Tesla Shorts Time"])
        card = copy.split("Your shows today", 1)[1].split("▶ Listen", 1)[0]
        assert "Tesla</span>" not in card or "Tesla &nbsp;/&nbsp; </span>" in card
        assert "Tesla Shorts Time</span>" in card
        assert "card-title" in card and "Georgia" in card
        assert "Tesla Shorts Time deck sentence one." in card
        assert 'Sources: <a href="https://www.reuters.com/tesla"' in card  # rss tag dropped
        assert "More in this episode" in card
        assert "Tesla Shorts Time read 1" in card and "Tesla Shorts Time read 2" in card
        assert "Tesla Shorts Time read 3" not in card

    def test_article_links_carry_no_utm_and_our_links_always_do(self, composed):
        copy = nde.render_for(composed.body, [s.tag for s in nde.eligible_shows(_rich_front())])
        for href in re.findall(r'href="([^"]+)"', copy):
            if "nerranetwork.com" in href and "/unsubscribe" not in href and "{{" not in href:
                assert "utm_source=newsletter" in href or "utm_" not in href, href
            elif href.startswith(("https://example.org", "https://www.reuters.com")):
                assert "utm_" not in href, href

    def test_the_thumbnail_is_not_a_second_link(self, composed):
        thumb = IMAGE.format(slug="tesla")
        assert not re.search(r'<a [^>]*><img src="' + re.escape(thumb), composed.body)
        assert f'<img src="{thumb}" width="{nde.THUMB_PX}"' in composed.body


class TestTheMasthead:
    def test_it_is_the_landing_pages(self):
        from engine.brand import NETWORK_TAGLINE
        html = nde.masthead_html(dt.date(2026, 11, 8), shows_today=15,
                                 listen_url="https://nerranetwork.com/x", duration="2 h 5 min")
        assert "Sunday, November 8, 2026" in html
        assert "15 shows published this morning" in html
        assert "Nerra <span" in html and ">Daily</span>" in html
        assert NETWORK_TAGLINE in html
        assert "▶ Hear all of it · 2 h 5 min" in html
        assert "<img" not in html and "<h1" not in html

    def test_no_listen_url_no_button(self):
        html = nde.masthead_html(dt.date(2026, 11, 8), shows_today=1)
        assert "Hear all of it" not in html and "Stories from across the network" in html


# ---------------------------------------------------------------------------
# Gmail's clipping point
# ---------------------------------------------------------------------------


class TestTheReadsGiveWay:
    def test_the_cards_drop_their_article_links_before_the_copy_clips(self, patched):
        front = _rich_front()
        full = nde._compose(DAY, now=NOW, front=front, trial_days=7, card_reads=nde.READS_PER_CARD)
        none = nde._compose(DAY, now=NOW, front=front, trial_days=7, card_reads=0)
        patched.setattr(nde, "size_warning_bytes", lambda: nde.largest_copy_bytes(none, front) + 1)
        tight = nde.compose(DAY, now=NOW, front=front, trial_days=7)
        assert nde.largest_copy_bytes(tight, front) <= nde.largest_copy_bytes(none, front) + 1
        assert nde.largest_copy_bytes(full, front) > nde.largest_copy_bytes(tight, front)
        copy = nde.render_for(tight.body, ["nerra-member", "Tesla Shorts Time"])
        lead = _lead(tight)
        assert f"{lead.show.name} read 3" in copy  # the lead keeps its links
        assert "Tesla Shorts Time read 1" not in copy
        assert "Tesla Shorts Time deck sentence one." in copy and "Sources:" in copy

    def test_a_roomy_budget_keeps_every_link(self, composed):
        copy = nde.render_for(composed.body, ["nerra-member", "Tesla Shorts Time"])
        assert "Tesla Shorts Time read 2" in copy

    def test_your_week_leaves_out_todays_episode(self, patched):
        rows = [{"episode_num": 100, "date": DAY, "hook": "Today's tesla hook"},
                {"episode_num": 99, "date": DAY - dt.timedelta(days=1), "hook": "Yesterday's tesla hook"}]
        patched.setattr(nde, "week_records", lambda slug, day, root=None: rows if slug == "tesla" else [])
        sunday = dt.date(2026, 11, 8)
        front = _rich_front(sunday)
        rows[0]["date"], rows[1]["date"] = sunday, sunday - dt.timedelta(days=1)
        composed = nde.compose(sunday, now=NOW + dt.timedelta(days=6), front=front, trial_days=7)
        copy = nde.render_for(composed.body, ["nerra-member", "Tesla Shorts Time"])
        week = copy.split("Your week", 1)[1]
        assert "Yesterday&#x27;s tesla hook" in week and "Today&#x27;s tesla hook" not in week

    def test_contrast_holds_on_every_copy(self, composed):
        from engine.contrast_validator import assert_contrast_ok
        tags = [s.tag for s in nde.eligible_shows(_rich_front())]
        for sample in (["nerra-member"], ["Tesla Shorts Time"], tags + [nde.PAID_TAG], []):
            assert_contrast_ok(nde.render_for(composed.body, sample, subscriber=bool(sample)))
