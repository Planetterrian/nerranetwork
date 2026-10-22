"""Guards for ``landing-test.html`` v2 — the whole site on the front page (Oct 17 2026).

The second pass put the rest of the site on the test front page: the
interviews (Conversations), Watch, Most read, the network's numbers and its
claims record, the live dashboards and Story Trackers, the topic hubs, Nerra
Personal, the books, the image gallery, every way to listen, partners — and
a real signup form. What these pin, section by section:

* every value comes from committed data, and a missing value renders
  NOTHING (never a 0, never an empty band);
* the Mira claim renders whole from engine.brand (claim + basis + correction
  invitation), never retyped; nothing says Mira phones guests;
* the private studio join link is never linked, retired books never appear,
  members-only shows never appear;
* the signup form is the site's own: it posts through footer-subscribe.js to
  the Worker with a source and show tags the Worker's allow-lists accept,
  and it is the page's ONLY email form;
* the trust strip prints exactly what claims.html counts;
* the JSON-LD is valid and lists the page's stories;
* every image has alt text and dimensions; every internal link resolves.

Every render goes to ``tmp_path``: never read a committed generated page.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import generate_html as G  # noqa: E402
from engine import brand  # noqa: E402
from engine import funnel as F  # noqa: E402
from engine import landing_test as LT  # noqa: E402

_HREF_RE = re.compile(r'href="([^"]*)"')
_IMG_RE = re.compile(r"<img\b[^>]*>", re.S)
_HANDLERS = (ROOT / "workers" / "gallery" / "src" / "handlers.ts").read_text(encoding="utf-8")


def _ts_set(name: str) -> set:
    block = _HANDLERS.split(f"const {name} = new Set([", 1)[1].split("]);", 1)[0]
    block = re.sub(r"//[^\n]*", "", block)
    return set(re.findall(r'"([^"]+)"', block))


@pytest.fixture(scope="module")
def rendered(tmp_path_factory) -> str:
    out = tmp_path_factory.mktemp("landing_v2")
    path = G.generate_network_page(output_dir=out)
    return Path(path).read_text(encoding="utf-8")


def _body(html: str) -> str:
    start = html.index('<div class="lt-page">')
    end = html.index('<footer class="nn-footer">')
    return html[start:end]


def _section(html: str, section_id: str) -> str:
    """The markup of one ``<section id=…>`` (or ``<nav>``) of the page."""
    match = re.search(rf'<(section|nav)[^>]*\bid="{section_id}"', html)
    assert match, f"section #{section_id} not rendered"
    tag = match.group(1)
    end = html.index(f"</{tag}>", match.end())
    return html[match.start():end]


def _public_shows():
    return [s for s in G._build_all_shows_list()
            if s.get("access", "public") in LT.PUBLIC_ACCESS_MODES and s.get("has_feed", True)]


def _internal(href: str) -> bool:
    return not href.startswith(("http://", "https://", "#", "mailto:", "data:"))


# --------------------------------------------------------------------------
# Whole page
# --------------------------------------------------------------------------

class TestWholePage:
    def test_every_internal_link_resolves_and_none_is_a_stub(self, rendered):
        stubs = G.redirect_stub_paths()
        missing = []
        for href in _HREF_RE.findall(_body(rendered)):
            if not _internal(href):
                continue
            rel = href.split("#")[0].split("?")[0]
            if rel and (not (ROOT / rel).is_file() or rel in stubs):
                missing.append(href)
        assert not missing, missing

    def test_no_internal_link_carries_utm(self, rendered):
        from urllib.parse import urlparse
        for href in _HREF_RE.findall(rendered):
            ours = _internal(href) or (urlparse(href).hostname or "").endswith("nerranetwork.com")
            assert not (ours and "utm_" in href), href

    def test_never_links_the_private_studio(self, rendered):
        assert "age-of-ai-studio" not in rendered

    def test_images_have_alt_and_dimensions(self, rendered):
        for tag in _IMG_RE.findall(_body(rendered)):
            alt = re.search(r'alt="([^"]*)"', tag)
            assert alt, tag
            # Oct 18 2026: the homepage's show grid is the shared show_card,
            # whose cover is alt="" on purpose (the show's name is the
            # heading beside it — tests/test_site_review_2026_10_07_chrome).
            assert alt.group(1).strip() or 'class="show-card-image"' in tag, tag
            assert re.search(r'width="\d+"', tag) and re.search(r'height="\d+"', tag), tag

    def test_below_the_fold_images_are_lazy(self, rendered):
        imgs = _IMG_RE.findall(_body(rendered))
        eager = [t for t in imgs if 'loading="lazy"' not in t]
        # Only the lead picture loads eagerly (fetchpriority=high).
        assert len(eager) <= 1, eager
        assert all("fetchpriority" in t for t in eager)

    def test_no_members_only_show_in_any_v2_section(self, rendered):
        body = _body(rendered)
        gated = [s for s in G._build_all_shows_list() if s["access"] == "members_only"]
        assert gated
        for show in gated:
            assert show["name"] not in body, show["slug"]
            narrative = show["show_page"].replace(".html", "-narrative.html")
            assert f'href="{narrative}"' not in body, show["slug"]

    def test_indexable_and_never_links_the_retired_test_url(self, rendered):
        # Oct 18 2026: the page is the homepage now (was: noindex test page).
        assert not re.search(r'<meta name="robots" content="noindex', rendered.split("</head>")[0])
        assert "landing-test" not in rendered

    def test_page_weight_is_reasonable(self, rendered):
        # Oct 18 2026: the homepage added the show grid, the subscribe list
        # and the about block to the test page's sections.
        assert len(rendered.encode("utf-8")) < 450_000

    def test_no_new_external_scripts(self, rendered):
        srcs = re.findall(r'<script[^>]+src="([^"]+)"', _body(rendered))
        assert not [s for s in srcs if s.startswith("http")], srcs


# --------------------------------------------------------------------------
# Growth details: OG, JSON-LD, share
# --------------------------------------------------------------------------

class TestGrowthDetails:
    def test_json_ld_item_list_parses_and_lists_the_stories(self, rendered):
        head = rendered.split("</head>")[0]
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', head, re.S)
        lists = [json.loads(b) for b in blocks if '"ItemList"' in b]
        assert len(lists) == 1
        data = lists[0]
        assert data["@context"] == "https://schema.org" and data["@type"] == "ItemList"
        items = data["itemListElement"]
        assert items and data["numberOfItems"] == len(items)
        assert [i["position"] for i in items] == list(range(1, len(items) + 1))
        for item in items:
            assert item["url"].startswith("https://nerranetwork.com/")
            rel = item["url"].removeprefix("https://nerranetwork.com/")
            assert (ROOT / rel).is_file(), rel
            assert item["name"] and "utm_" not in item["url"]

    def test_og_image_is_the_network_card(self, rendered):
        """Oct 18 2026: the front page shares as the network card
        (engine/share_cards.py); each story's post carries its own card."""
        head = rendered.split("</head>")[0]
        og = re.search(r'<meta property="og:image" content="([^"]+)"', head).group(1)
        assert og == "https://nerranetwork.com/assets/share/network.jpg"
        assert '<meta property="og:image:width" content="1200">' in head
        assert head.count('property="og:image:alt"') == 1

    def test_lead_share_links_carry_a_parseable_share_campaign(self, rendered):
        from urllib.parse import parse_qs, unquote, urlparse
        share = re.search(r'<div class="lt-share".*?</div>', rendered, re.S)
        assert share, "lead has an article, so it must offer a share row"
        x = re.search(r'href="(https://twitter\.com/intent/tweet\?url=[^"&]+)', share.group(0)).group(1)
        target = unquote(x.split("url=", 1)[1])
        assert urlparse(target).hostname == "nerranetwork.com"
        campaign = parse_qs(urlparse(target).query)["utm_campaign"][0]
        parsed = F.parse_campaign_id(campaign)
        assert parsed is not None and parsed.variant == "share"


# --------------------------------------------------------------------------
# Conversations
# --------------------------------------------------------------------------

class TestConversations:
    def test_the_interviews_lead_the_page_after_the_lead_story(self, rendered):
        body = _body(rendered)
        assert body.index('id="conversations"') < body.index('id="top-stories"')

    def test_interview_shows_are_not_also_news_stories(self, rendered):
        body = _body(rendered)
        for slug in LT.CONVERSATION_SLUGS:
            show = G.NETWORK_SHOWS[slug]
            for cls in ("lt-lead", "lt-card", "lt-feature", "lt-row"):
                assert not re.search(
                    rf'class="{cls}"[^>]*>(?:(?!</article>|</li>).)*?href="{re.escape(show["show_page"])}"',
                    body, re.S), (slug, cls)

    def test_cards_are_real_episodes_with_articles(self, rendered):
        sec = _section(rendered, "conversations")
        cards = [c for slug in LT.CONVERSATION_SLUGS
                 for c in G._interview_episode_cards(slug, G.NETWORK_SHOWS[slug])
                 if c.get("post_url") and c.get("guest")]
        assert cards
        linked = set(re.findall(r'href="(blog/(?:age_of_ai|nerra_voices)/ep\d{3}\.html)"', sec))
        assert linked and linked <= {c["post_url"] for c in cards}
        # Age of AI Ep001 is a redirect stub, never an article.
        assert "blog/age_of_ai/ep001.html" not in sec

    def test_the_mira_claim_renders_whole_from_engine_brand(self, rendered):
        sec = _section(rendered, "conversations")
        assert brand.MIRA_FIRST_CLAIM in sec
        assert brand.MIRA_FIRST_CLAIM_BASIS in sec
        assert brand.MIRA_FIRST_CLAIM_FOOTNOTE in sec

    def test_the_claim_is_never_retyped_in_the_template(self):
        tpl = (ROOT / "templates" / "network_page.html.j2").read_text(encoding="utf-8")
        assert "first interview shows of their kind" not in tpl
        assert "{{ mira_claim() }}" in tpl

    def test_nothing_says_mira_phones_guests(self, rendered):
        sec = _section(rendered, "conversations").lower()
        for phrase in ("phones guests", "phone call", "calls guests", "on the phone"):
            assert phrase not in sec, phrase
        assert "nothing publishes until" not in sec

    def test_apply_links_are_each_shows_own_form(self, rendered):
        sec = _section(rendered, "conversations")
        for slug in LT.CONVERSATION_SLUGS:
            apply_page = G.NETWORK_SHOWS[slug].get("apply_page")
            if apply_page:
                assert f'href="{apply_page}"' in sec, slug

    def test_cohost_comes_from_the_transcript(self, rendered):
        sec = _section(rendered, "conversations")
        feature = sec.split('class="lt-convo-feature"', 1)[1].split("</article>", 1)[0]
        cards = sorted(
            (c for slug in LT.CONVERSATION_SLUGS
             for c in G._interview_episode_cards(slug, G.NETWORK_SHOWS[slug])
             if c.get("post_url") and c.get("guest")),
            key=lambda c: (G.datetime.strptime(c["date"], "%b %d, %Y").date(), c["episode"]),
            reverse=True)
        top = cards[0]
        assert top["guest"] in feature
        assert ("with Patrick Novak" in feature) == (top["cohost"] == "Patrick Novak")


# --------------------------------------------------------------------------
# Signup
# --------------------------------------------------------------------------

class TestSignup:
    """Oct 18 2026: the v2 test page's inline per-show newsletter form did not
    come with the promotion. The homepage is Soft-only (Oct 9 2026,
    tests/test_homepage_soft_only_2026_10_09.py): its one email ask is the
    Soft Personal band, and the footer form is suppressed. These guard the
    same properties the v2 form guards did — one ask, posting through the
    shared handler with engine.funnel's source — on the form the page has."""

    def _forms(self, html):
        return re.findall(r"<form\b[^>]*data-nn-subscribe[^>]*>.*?</form>", html, re.S)

    def test_one_email_ask_and_it_is_soft_personal(self, rendered):
        forms = self._forms(rendered)
        assert len(forms) == 1, "the Soft Personal band is the homepage's ONLY email form"
        assert 'data-nn-subscribe="soft-personal"' in forms[0]
        assert 'data-nn-subscribe="landing"' not in rendered
        assert 'name="tag"' not in rendered

    def test_posts_through_the_shared_handler_with_the_above_fold_source(self, rendered):
        # Oct 22 2026: Soft above-fold placement posts src-above_fold so
        # capture.by_source / GA4 can tell it from mid-page Soft asks. Still
        # goes through footer-subscribe.js; Worker SOURCE_TAGS allow-lists it.
        form = self._forms(rendered)[0]
        assert 'type="email"' in form and 'name="email"' in form
        assert "assets/js/footer-subscribe.js" in rendered
        js = (ROOT / "assets" / "js" / "footer-subscribe.js").read_text(encoding="utf-8")
        assert "https://api.nerranetwork.com/api/subscribe" in js
        source = re.search(r'data-source="([^"]+)"', form).group(1)
        assert source == "src-above_fold"
        assert source in _ts_set("SOURCE_TAGS")
        assert F.source_tag(F.SOURCE_SITE) == "src-nerranetwork"  # site tag unchanged

    def test_no_subscriber_count_below_the_social_proof_floor(self, rendered):
        stats = json.loads((ROOT / "api" / "buttondown_stats.json").read_text(encoding="utf-8"))
        count = stats.get("subscriber_count")
        if not (isinstance(count, int) and count >= G.MIN_SOCIAL_PROOF_SUBSCRIBERS):
            assert not re.search(r"Join \d+", _body(rendered))


# --------------------------------------------------------------------------
# Numbers + trust
# --------------------------------------------------------------------------

class TestNumbersAndTrust:
    def test_trust_strip_prints_exactly_what_claims_html_counts(self, rendered):
        totals = G._claims_network_ledger(G._build_all_shows_list())["totals"]
        sec = _section(rendered, "numbers")
        assert f"{totals['claims']:,}" in sec
        assert f"{totals['verified_share_pct']}%" in sec
        assert f"claims on the ledger across {totals['episodes']} episodes" in sec

    def test_claims_page_and_landing_share_one_ledger_function(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        claims = src.split("def generate_claims_pages(")[1].split("\ndef ")[0]
        assert "_claims_network_ledger(" in claims
        assert "network_ledger(" not in claims.replace("_claims_network_ledger(", "")

    def test_trust_links_include_corrections_and_disclosure(self, rendered):
        sec = _section(rendered, "numbers")
        for href in ("claims.html", "editorial.html#corrections", "ai-disclosure.html"):
            assert f'href="{href}"' in sec, href
        assert 'id="corrections"' in (ROOT / "templates" / "editorial.html.j2").read_text(encoding="utf-8")

    def test_glance_hides_what_is_not_measured(self):
        tiles = LT.glance_numbers({"network": {"downloads_30d": None, "youtube": {"views": 0}}},
                                  shows_publishing=5, episodes_this_week=None, languages=1)
        labels = " ".join(t["label"] for t in tiles)
        assert "downloads" not in labels and "YouTube" not in labels
        assert "episodes" not in labels and "languages" not in labels
        assert [t["value"] for t in tiles] == ["5"]
        assert LT.glance_numbers(None, shows_publishing=0, episodes_this_week=0, languages=0) == []

    def test_glance_week_over_week_only_when_up(self):
        up = LT.glance_numbers({"network": {"downloads_30d": 100, "wow_pct": 12.4}},
                               shows_publishing=1, episodes_this_week=None, languages=1)
        down = LT.glance_numbers({"network": {"downloads_30d": 100, "wow_pct": -40.0}},
                                 shows_publishing=1, episodes_this_week=None, languages=1)
        assert "up 12%" in up[-1]["label"] and "up" not in down[-1]["label"]

    def test_unmeasured_audience_renders_no_audience_tile(self, tmp_path, monkeypatch):
        fake = tmp_path / "audience_headline.json"
        fake.write_text(json.dumps({"network": {"downloads_30d": None, "youtube": None}, "shows": {}}))
        monkeypatch.setattr(G, "AUDIENCE_HEADLINE_PATH", fake)
        path = G.generate_network_page(output_dir=tmp_path)
        sec = _section(Path(path).read_text(encoding="utf-8"), "numbers")
        assert "podcast downloads" not in sec and "YouTube views" not in sec
        assert ">0<" not in sec


# --------------------------------------------------------------------------
# Watch
# --------------------------------------------------------------------------

def _video(slug, kind, published, **kw):
    return {"show_slug": slug, "kind": kind, "published": published, "episode": kw.pop("episode", 1),
            "title": kw.pop("title", f"{slug} {kind} title #Shorts"), "channel": kw.pop("channel", "en"),
            "watch_url": kw.pop("watch_url", f"https://www.youtube.com/watch?v={slug}{kind}{published}"), **kw}


class TestWatch:
    def test_one_per_show_newest_first_public_and_english_only(self):
        rows = [
            _video("a", "long", "2026-10-15"), _video("a", "long", "2026-10-17"),
            _video("b", "long", "2026-10-16"),
            _video("c", "long", "2026-10-17", channel="ru"),
            _video("desk", "long", "2026-10-17"),
            _video("d", "long", "2026-10-17", watch_url="http://example.com/x"),
        ]
        out = LT.pick_videos(rows, kind="long", public_slugs=["a", "b", "c", "d"], limit=4)
        assert [(v["show_slug"], v["date_raw"]) for v in out] == [("a", "2026-10-17"), ("b", "2026-10-16")]

    def test_the_hook_short_wins_and_hashtags_drop(self):
        rows = [_video("a", "short", "2026-10-17", window="qualified", title="Second window #Shorts"),
                _video("a", "short", "2026-10-17", window="hook_open", title="The hook short #Shorts")]
        out = LT.pick_videos(rows, kind="short", public_slugs=["a"], limit=6)
        assert out[0]["display_title"] == "The hook short"

    def test_stale_videos_drop_off(self):
        rows = [_video("a", "long", "2026-10-17"), _video("b", "long", "2026-08-01")]
        out = LT.pick_videos(rows, kind="long", public_slugs=["a", "b"], limit=4)
        assert [v["show_slug"] for v in out] == ["a"]

    def test_watch_cards_link_youtube_and_channels_subscribe(self, rendered):
        sec = _section(rendered, "watch")
        assert re.search(r'href="https://www\.youtube\.com/watch\?v=[\w-]+"', sec)
        from engine.video_metadata import channel_subscribe_url
        for code in ("en", "ru", "fr"):
            assert f'href="{channel_subscribe_url(code)}"' in sec, code
        assert "utm_" not in sec

    def test_no_youtube_hosted_thumbnails(self, rendered):
        assert "ytimg.com" not in rendered and "img.youtube.com" not in rendered


# --------------------------------------------------------------------------
# Gallery, books, dashboards, topics, personal, listen
# --------------------------------------------------------------------------

def _gallery_index(rows):
    return {
        "base_url": "https://gallery.example.com",
        "license": "CC BY-SA 4.0",
        "episode_fields": ["show_slug", "episode_date", "episode_id", "episode_title"],
        "image_fields": ["image_id", "episode", "format", "caption", "intended_use"],
        "episodes": [r[0] for r in rows],
        "images": [[f"img{n}", n, "png", "", r[1]] for n, r in enumerate(rows)],
        "overrides": {},
    }


class TestGalleryStrip:
    def test_one_per_show_public_scenes_only(self):
        idx = _gallery_index([
            (["a", "2026-10-17", "ep010", ""], "segment_card"),
            (["a", "2026-10-17", "ep010", ""], "segment_card"),
            (["b", "2026-10-16", "ep004", ""], "book_cover"),
            (["b", "2026-10-15", "ep003", ""], "social"),
            (["desk", "2026-10-17", "ep001", ""], "segment_card"),
            (["c", "2026-10-14", "ep002", ""], "segment_card"),
        ])
        out = LT.gallery_strip(idx, public_slugs=["a", "b", "c"],
                               exclude_urls=["https://gallery.example.com/a/2026-10-17/ep010/img1.thumb.webp"])
        assert [(g["show_slug"], g["url"].rsplit("/", 1)[1]) for g in out] == [
            ("a", "img0.thumb.webp"), ("c", "img5.thumb.webp")]

    def test_missing_index_is_empty(self):
        assert LT.gallery_strip(None, public_slugs=["a"]) == []

    def test_strip_reads_the_slim_index_never_the_manifest(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        v2 = src.split("def _front_page_sections(")[1].split("\ndef ")[0]
        assert "gallery-manifest" not in v2 and '"_network"' in v2

    def test_no_gallery_data_renders_no_strip_and_no_scenes(self, tmp_path):
        empty = tmp_path / "gallery"
        empty.mkdir()
        path = G.generate_network_page(output_dir=tmp_path, gallery_dir=empty)
        html = Path(path).read_text(encoding="utf-8")
        assert "lt-gallery-grid" not in _body(html)
        assert "gallery.nerranetwork.com" not in _body(html)


class TestBooks:
    def test_only_live_volumes_render(self, rendered):
        sec = _section(rendered, "shelf")
        live = G.books_page_volumes(ROOT / "books" / "catalog.json", ROOT / "books" / "volumes")
        catalog = json.loads((ROOT / "books" / "catalog.json").read_text(encoding="utf-8"))["volumes"]
        retired_only = {v["full_title"] for v in catalog if v.get("retired")} - {v["full_title"] for v in live}
        assert retired_only, "expected retired volumes in the catalog"
        for title in retired_only:
            assert title not in sec, title
        for v in live:
            assert v["full_title"] in sec


class TestDashboardsAndTopics:
    def test_dashboard_links_exist_and_carry_dated_facts(self, rendered):
        sec = _section(rendered, "dashboards")
        for href in re.findall(r'class="lt-dash" href="([^"]+)"', sec):
            assert (ROOT / href).is_file(), href
        for fact in re.findall(r'<span class="lt-dash-fact">([^<]+)</span>', sec):
            # A live fact always says when (a month abbreviation and a day).
            assert re.search(r"\b[A-Z][a-z]{2} \d{1,2}\b", fact) or "terms" in fact, fact

    def test_only_built_topic_hubs_are_linked(self, rendered):
        sec = _section(rendered, "discover")
        for href in re.findall(r'href="(topics/[^"]+)"', sec):
            assert (ROOT / href).is_file(), href


class TestPersonal:
    def test_launching_soon_without_a_payment_link(self, rendered):
        import os
        if os.environ.get("STRIPE_LINK_PERSONAL"):
            pytest.skip("a live Payment Link is configured in this environment")
        sec = _section(rendered, "personal-promo")
        assert "Launching soon" in sec
        assert "$" not in sec, "prices are not stated from config, so none are printed"

    def test_cta_is_measured_as_an_engagement_event(self, rendered):
        sec = _section(rendered, "personal-promo")
        assert "select_personal_upsell" in sec
        src = (ROOT / "scripts" / "fetch_ga4_stats.py").read_text(encoding="utf-8")
        assert re.search(r"ENGAGEMENT_EVENTS = \[[^\]]*\"select_personal_upsell\"", src)


class TestListenEverywhere:
    def test_languages_are_only_ones_still_produced(self, rendered):
        sec = _section(rendered, "subscribe")
        producing = set(G._listening_languages())
        from engine.language_feeds import LANGUAGE_META
        for lang, (autonym, _locale) in LANGUAGE_META.items():
            if lang not in producing:
                assert f'lang="{lang}">{autonym}' not in sec, lang


class TestMostRead:
    def test_articles_only_public_only(self):
        ga4 = {"top_pages": [
            {"pagePath": "/age-of-ai.html"},
            {"pagePath": "/blog/age_of_ai/ep005.html"},
            {"pagePath": "/blog/omni_view_europe/ep010.html"},
            {"pagePath": "/blog/spacex/ep120.html"},
            {"pagePath": "/blog/spacex/ep120.html"},
        ]}
        assert LT.most_read_pages(ga4, public_slugs=["age_of_ai", "spacex"]) == [
            ("age_of_ai", 5), ("spacex", 120)]
        assert LT.most_read_pages(None, public_slugs=["spacex"]) == []

    def test_no_view_counts_are_printed(self, rendered):
        if 'id="popular"' not in rendered:
            pytest.skip("no fresh popularity data in this checkout")
        sec = _section(rendered, "popular")
        assert "views" not in re.sub(r"Article views, last \d+ days", "", sec)


class TestEmptyState:
    def test_no_public_shows_renders_no_v2_show_sections(self, tmp_path):
        path = G.generate_network_page(output_dir=tmp_path, all_shows=[])
        body = _body(Path(path).read_text(encoding="utf-8"))
        for section_id in ("conversations", "watch", "dashboards", "numbers", "shelf"):
            assert f'id="{section_id}"' not in body, section_id
        assert "lt-video" not in body and "lt-convo" not in body


def test_episode_scene_avoids_a_used_picture_but_never_borrows_another_episodes():
    idx = {
        "base_url": "https://g.example.com",
        "episode_fields": ["show_slug", "episode_date", "episode_id", "episode_title"],
        "image_fields": ["image_id", "episode", "format", "caption", "intended_use"],
        "episodes": [["s", "2026-10-17", "ep001", ""], ["s", "2026-10-16", "ep000", ""]],
        "images": [["one", 0, "png", "", "segment_card"], ["two", 0, "png", "", "segment_card"],
                   ["old", 1, "png", "", "segment_card"]],
        "overrides": {},
    }
    first = "https://g.example.com/s/2026-10-17/ep001/one.thumb.webp"
    hit = LT.episode_scene(idx, "s", 1, "2026-10-17", avoid_urls=[first])
    assert hit["url"].endswith("/two.thumb.webp")
    both = [first, "https://g.example.com/s/2026-10-17/ep001/two.thumb.webp"]
    # Every scene used: the episode's own picture again, never ep000's.
    assert "/ep001/" in LT.episode_scene(idx, "s", 1, "2026-10-17", avoid_urls=both)["url"]
