"""Guards for the homepage as a news front page (Oct 18 2026).

Operator direction: "make the landing page test the new landing page … with
timely news information and updates as any successful news and information
site would be expected to have." The Oct 17 landing test (landing-test.html)
became ``index.html``; ``engine/newsroom.py`` added what a credible news front
shows. What these pin:

* the promotion: index.html renders the front-page design, indexable, bare
  canonical, the approved SEO copy, the Organization / WebSite JSON-LD, the
  site's real nav; landing-test.html is a redirect stub and no generator
  writes it;
* every story says when it went out (the summary record's time, Eastern),
  never the feed pubDate; a "Today" marker only on today's stories; the
  masthead carries the build date and an "Updated" stamp;
* Developing stories are found from the digests' own headlines, need two or
  more days and a recent update, and never treat a recurring segment label as
  a story — on fixtures AND on the committed digests;
* markets and launches: every value has its as-of date; a stale value, or a
  launch whose time has passed, renders nothing;
* corrections come from engine.corrections, newest first, each linking the
  corrected article;
* freshness wiring: the finalize job and the Nerra Daily workflow re-render
  and commit index.html.

Every render goes to ``tmp_path``: never read a committed generated page.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import generate_html as G  # noqa: E402
from engine import newsroom as N  # noqa: E402

UTC = dt.timezone.utc
# 2026-10-17 09:30 ET — the morning after the committed slate's shows ran.
NOW = dt.datetime(2026, 10, 17, 13, 30, tzinfo=UTC)


@pytest.fixture(scope="module")
def home(tmp_path_factory) -> str:
    out = tmp_path_factory.mktemp("home")
    return G.generate_network_page(output_dir=out, now=NOW).read_text(encoding="utf-8")


def _section(html: str, section_id: str) -> str:
    match = re.search(rf'<(section|aside|div)[^>]*\bid="{section_id}"', html)
    assert match, f"#{section_id} not rendered"
    tag = match.group(1)
    return html[match.start():html.index(f"</{tag}>", match.end())]


def _public():
    from engine import landing_test as LT
    return [s for s in G._build_all_shows_list()
            if s.get("access", "public") in LT.PUBLIC_ACCESS_MODES and s.get("has_feed", True)]


# --------------------------------------------------------------------------
# Part A — the promotion
# --------------------------------------------------------------------------

class TestPromotion:
    def test_index_html_is_the_front_page(self, home):
        assert '<div class="lt-page">' in home
        assert 'class="lt-lead"' in home and 'id="latest"' in home

    def test_indexable_with_the_bare_origin_canonical(self, home):
        head = home.split("</head>")[0]
        assert 'name="robots" content="noindex' not in head
        assert '<link rel="canonical" href="https://nerranetwork.com/">' in head
        assert 'hreflang="ru" href="https://nerranetwork.com/ru/index.html"' in head

    def test_seo_copy_is_the_approved_one(self, home):
        import html as _h
        title, meta = G.SEO_PAGE_COPY["index.html"]
        head = _h.unescape(home.split("</head>")[0])
        assert f"<title>{title}</title>" in head
        assert f'name="description" content="{meta}"' in head

    def test_organization_and_website_json_ld(self, home):
        head = home.split("</head>")[0]
        blocks = [json.loads(b) for b in re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', head, re.S)]
        types = {b.get("@type") for b in blocks}
        assert {"Organization", "WebSite"} <= types
        org = next(b for b in blocks if b["@type"] == "Organization")
        names = {p["name"] for p in org["hasPart"]}
        assert {s["name"] for s in _public()} == names
        gated = {s["name"] for s in G._build_all_shows_list() if s.get("access") == "members_only"}
        assert not names & gated

    def test_real_nav_and_soft_only_capture(self, home):
        assert 'class="nn-nav-logo"' in home and 'id="mobileMenu"' in home
        kinds = re.findall(r'data-nn-subscribe="([^"]+)"', home)
        assert kinds == ["soft-personal"]
        assert 'id="home-soft-personal"' in home

    def test_homepage_features_carried_over(self, home):
        for anchor in ("shows", "subscribe", "about", "personal-promo", "latest"):
            assert f'id="{anchor}"' in home, anchor
        grid = _section(home, "shows")
        for show in _public():
            assert f'href="{show["show_page"]}" class="show-card' in grid, show["slug"]
        assert 'class="subscribe-all"' in home
        assert "personal-interest.html" in _section(home, "personal-promo")

    def test_landing_test_is_retired_cleanly(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        assert "generate_landing_test_page" not in src
        assert not (ROOT / "templates" / "landing_test.html.j2").exists()
        stub = ROOT / "landing-test.html"
        assert stub.exists() and G._is_redirect_stub(stub)
        assert "index.html" in stub.read_text(encoding="utf-8")

    def test_homepage_flag_writes_only_the_homepage(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        assert '"--homepage"' in src
        assert "if args.homepage and not args.network:\n        generate_network_page(" in src

    def test_no_internal_link_carries_utm(self, home):
        from urllib.parse import urlparse
        for href in re.findall(r'href="([^"]*)"', home):
            internal = not href.startswith(("http", "#", "mailto:")) or \
                (urlparse(href).hostname or "").endswith("nerranetwork.com")
            assert not (internal and "utm_" in href), href


# --------------------------------------------------------------------------
# Part B — timestamps
# --------------------------------------------------------------------------

class TestTimestamps:
    def test_published_at_reads_the_record_time_as_utc(self):
        rec = {"date": "2026-10-17", "datetime": "2026-10-17T09:47:40.043275"}
        when = N.published_at(rec)
        assert when == dt.datetime(2026, 10, 17, 9, 47, 40, 43275, tzinfo=UTC)
        assert N.eastern_label(when) == "Oct 17, 5:47 AM ET"

    def test_no_time_means_a_date_only_stamp(self):
        st = N.stamp("2026-10-14", N.published_at({"date": "2026-10-14"}), NOW)
        assert st["label"] == "Oct 14" and not st["has_time"] and st["iso"] == "2026-10-14"

    def test_a_time_that_contradicts_its_date_is_dropped(self):
        assert N.published_at({"date": "2026-10-17", "datetime": "2026-09-01T10:00:00"}) is None

    def test_today_is_the_eastern_date(self):
        # 03:30 UTC on the 17th is still the 16th in New York.
        late = dt.datetime(2026, 10, 17, 3, 30, tzinfo=UTC)
        st = N.stamp("2026-10-17", late, NOW)
        assert st["day"] == "2026-10-16" and not st["is_today"]
        st = N.stamp("2026-10-17", dt.datetime(2026, 10, 17, 9, 0, tzinfo=UTC), NOW)
        assert st["is_today"]

    def test_eastern_handles_daylight_saving(self):
        winter = dt.datetime(2026, 12, 1, 12, 0, tzinfo=UTC)
        assert N.eastern_label(winter) == "Dec 1, 7:00 AM ET"

    def test_masthead(self):
        m = N.masthead(NOW)
        assert m["date"] == "Saturday, October 17, 2026" and m["updated"] == "9:30 AM ET"

    def test_every_story_card_carries_a_time(self, home):
        lead = home.split('class="lt-lead"', 1)[1].split("</article>", 1)[0]
        assert re.search(r'<time datetime="[^"]+" data-rel title="[^"]+">', lead)
        latest = _section(home, "latest")
        assert latest.count("data-rel") >= 3

    def test_story_time_is_never_the_feed_pubdate(self, home):
        # Every feed item carries 08:00:00 UTC; 4:00 AM ET would be that.
        assert not re.search(r'<time datetime="\d{4}-\d\d-\d\dT08:00:00Z"', home)

    def test_today_marker_only_on_todays_stories(self, home):
        for m in re.finditer(r'data-today="([\d-]+)"', home):
            assert m.group(1) == "2026-10-17"

    def test_masthead_date_and_updated_stamp(self, home):
        assert "Saturday, October 17, 2026" in home
        assert 'Updated <time datetime="2026-10-17T13:30:00Z">9:30 AM ET</time>' in home

    def test_relative_time_script_is_inline_and_fetches_nothing(self, home):
        script = home.split("time[data-rel]", 1)[0].rsplit("<script>", 1)[1] + \
            home.split("time[data-rel]", 1)[1].split("</script>", 1)[0]
        assert "America/New_York" in script
        assert "fetch(" not in script and "XMLHttpRequest" not in script


# --------------------------------------------------------------------------
# Part B — developing stories
# --------------------------------------------------------------------------

def _ep(slug, day, headlines, hour=10):
    d = dt.date.fromisoformat(day)
    when = dt.datetime(d.year, d.month, d.day, hour, tzinfo=UTC)
    return {"slug": slug, "show_name": slug.title(), "show_page": f"{slug}.html",
            "brand_color": "#123456", "day": d, "stamp": N.stamp(day, when, NOW),
            "post_url": f"blog/{slug}/ep{d.day:03d}.html", "headlines": headlines}


FILLER = [_ep(f"s{n}", "2026-10-1" + str(n % 7), [f"Unrelated filler headline number {n} about item{n} widget{n}"])
          for n in range(40)]


class TestDevelopingStories:
    def test_a_story_on_two_days_is_a_thread(self):
        eps = [_ep("spacex", "2026-10-13", ["Super Heavy Booster 23 moved to Massey for cryogenic proof testing"]),
               _ep("spacex", "2026-10-17", ["Super Heavy Booster 23 completed cryogenic proof testing at Starbase"])]
        threads = N.developing_stories(eps + FILLER, NOW)
        assert len(threads) == 1
        t = threads[0]
        assert t["days"] == 2 and t["latest"]["headline"].endswith("at Starbase")
        assert t["latest"]["url"] == "blog/spacex/ep017.html"
        assert [e["headline"] for e in t["earlier"]] == [
            "Super Heavy Booster 23 moved to Massey for cryogenic proof testing"]

    def test_one_day_is_not_a_thread(self):
        eps = [_ep("a", "2026-10-17", ["Kenya confirms second Ebola case inside quarantine"]),
               _ep("b", "2026-10-17", ["Kenya confirms Ebola case inside quarantine zone"])]
        assert N.developing_stories(eps + FILLER, NOW) == []

    def test_a_stale_thread_is_not_developing(self):
        eps = [_ep("a", "2026-10-11", ["Pope Leo to have surgery after lump found on lung"]),
               _ep("a", "2026-10-12", ["Pope diagnosed with lung cancer after lump surgery"])]
        assert N.developing_stories(eps + FILLER, NOW) == []

    def test_a_recurring_segment_label_is_furniture(self):
        eps = [_ep("mit", "2026-10-15", ["Unusual Whales Options Flow"]),
               _ep("mit", "2026-10-16", ["Unusual Whales Options Flow API"]),
               _ep("mit", "2026-10-17", ["Unusual Whales Options Flow"])]
        assert N.developing_stories(eps + FILLER, NOW) == []

    def test_shared_beat_words_never_make_a_match(self):
        eps = [_ep("v", "2026-10-15", ["Canucks visit the Hurricanes tonight"]),
               _ep("v", "2026-10-16", ["Canucks visit the Islanders tonight"])]
        assert N.developing_stories(eps + FILLER, NOW) == []

    def test_committed_digests_find_real_threads_only(self):
        """Calibration replay on the committed digests (window ending Oct 17
        2026, docs/landing_test.md v3): three threads, each a real one."""
        now = dt.datetime(2026, 10, 17, 22, 0, tzinfo=UTC)
        threads = N.developing_stories(G._newsroom_episodes(_public(), now), now)
        if not threads:
            pytest.skip("the committed digests have moved past the calibration window")
        assert len(threads) <= N.DEVELOPING_LIMIT
        for t in threads:
            assert t["days"] >= 2
            days = {e["stamp"]["day"] for e in [t["latest"], *t["earlier"]]}
            assert len(days) >= 2
            # Every thread links real articles, never a redirect stub.
            for e in [t["latest"], *t["earlier"]]:
                if e["url"]:
                    assert (ROOT / e["url"]).is_file() and e["url"] not in G.redirect_stub_paths()
        heads = " ".join(t["latest"]["headline"] for t in threads)
        assert "Booster 23" in heads

    def test_never_reads_members_or_the_edition(self):
        from engine import landing_test as LT
        eps = G._newsroom_episodes(_public(), NOW)
        gated = {s["slug"] for s in G._build_all_shows_list() if s.get("access") == "members_only"}
        slugs = {e["slug"] for e in eps}
        assert not slugs & gated
        assert LT.EDITION_SLUG not in slugs and not slugs & set(LT.CONVERSATION_SLUGS)
        src = (ROOT / "engine" / "newsroom.py").read_text(encoding="utf-8")
        assert "members/" not in src

    def test_rendered_section(self, home):
        if 'id="developing"' not in home:
            pytest.skip("no developing threads at the fixed clock")
        sec = _section(home, "developing")
        assert "Covered on" in sec and "Latest update" in sec


# --------------------------------------------------------------------------
# Part B — markets & launches
# --------------------------------------------------------------------------

MAG7 = {"quotes": [{"ticker": "TSLA", "close": 354.72, "change_pct": -2.1, "bar_date": "2026-10-16"},
                   {"ticker": "NVDA", "close": 214.13, "change_pct": -1.4, "bar_date": "2026-10-16"}]}
SPCX = {"price": 146.03, "prev_close": 148.21, "updated_at": "2026-10-17T09:19:19+00:00"}
LAUNCHES = {"updated_at": "2026-10-17T18:59:55+00:00",
            "next": {"mission": "Bandwagon 5", "rocket": "Falcon 9", "net": "2026-10-19T10:30:00Z",
                     "status_name": "Go for Launch"}}


class TestMarkets:
    def test_every_value_carries_its_as_of_date(self):
        m = N.market_strip(mag7=MAG7, spcx=SPCX, tsla=None, launches=LAUNCHES, now=NOW)
        syms = [q["symbol"] for q in m["quotes"]]
        assert syms == ["TSLA", "NVDA", "SPCX"]  # the flagship ticker leads
        for q in m["quotes"]:
            assert q["as_of"] and q["as_of_iso"]
        tsla = next(q for q in m["quotes"] if q["symbol"] == "TSLA")
        assert tsla["basis"] == "close" and tsla["as_of"] == "Oct 16" and tsla["change"] == "−2.1%"
        assert m["quotes"][-1]["basis"] == "last quote"
        assert m["groups"][0]["label"] == "Closes" and m["groups"][0]["as_of"] == "Oct 16"
        assert m["launch"]["net"] == "Oct 19, 6:30 AM ET"

    def test_stale_values_render_nothing(self):
        later = NOW + dt.timedelta(days=N.MARKET_MAX_AGE_DAYS + 2)
        m = N.market_strip(mag7=MAG7, spcx=SPCX, tsla=None, launches=LAUNCHES, now=later)
        assert m["quotes"] == [] and m["launch"] is None

    def test_a_launch_whose_time_has_passed_renders_nothing(self):
        after = dt.datetime(2026, 10, 19, 11, 0, tzinfo=UTC)
        assert N.market_strip(mag7=None, spcx=None, tsla=None, launches=LAUNCHES,
                              now=after)["launch"] is None

    def test_missing_or_undated_values_render_nothing(self):
        m = N.market_strip(mag7={"quotes": [{"ticker": "TSLA", "close": 1.0}]},
                           spcx={"price": 10.0}, tsla={"price": 0}, launches={"next": {}}, now=NOW)
        assert m == {"quotes": [], "groups": [], "launch": None}

    def test_tsla_falls_back_to_the_quote_file_labelled_as_a_quote(self):
        tsla = {"price": 354.72, "prev_close": 362.44, "fetched_at": "2026-10-17T08:50:32Z"}
        m = N.market_strip(mag7=None, spcx=None, tsla=tsla, launches=None, now=NOW)
        q = m["quotes"][0]
        assert q["symbol"] == "TSLA" and q["basis"] == "last quote"
        assert q["as_of"] == "Oct 17, 4:50 AM ET"

    def test_rendered_strip_dates_every_value(self, home):
        if 'id="markets"' not in home:
            pytest.skip("no fresh market data at the fixed clock")
        strip = _section(home, "markets")
        for group in re.findall(r'<li class="lt-mk-group[^"]*".*?</li>', strip, re.S):
            assert "<time datetime=" in group


# --------------------------------------------------------------------------
# Part B — corrections, claims, schedule
# --------------------------------------------------------------------------

class TestCorrectionsAndRecord:
    def test_newest_first_and_never_shortened(self):
        rows = [{"date": "2026-10-08", "episode": 627, "text": "Old."},
                {"date": "2026-10-16", "episode": 634, "text": "A long correction " * 20},
                {"date": "2026-10-11", "episode": 139, "text": "Middle."},
                {"date": "2026-10-01", "episode": 1, "text": "Oldest."}]
        out = N.recent_corrections(rows)
        assert [r["episode"] for r in out] == [634, 139, 627]
        assert out[0]["text"] == "A long correction " * 20 and out[0]["date_label"] == "Oct 16"

    def test_none_renders_nothing(self):
        assert N.recent_corrections([]) == []

    def test_rendered_corrections_link_the_corrected_article(self, home):
        filed = N.recent_corrections(G._newsroom_corrections(_public()))
        if not filed:
            assert 'id="latest-corrections"' not in home
            return
        sec = _section(home, "latest-corrections")
        for c in filed:
            assert f"Correction to episode {c['episode']}" in sec
            assert f'href="{c["post_url"]}"' in sec
            assert (ROOT / c["post_url"]).is_file()

    def test_record_numbers_are_the_claims_page_numbers(self, home):
        totals = G._claims_network_ledger(G._build_all_shows_list())["totals"]
        sec = _section(home, "numbers")
        assert f"{totals['claims']:,}" in sec
        assert f"claims on the ledger across {totals['episodes']} episodes" in sec

    def test_schedule_comes_from_the_constants(self):
        from engine import daily_edition as E
        from engine import release_schedule as RS
        rows = N.todays_schedule(NOW)
        assert N.schedule_is_clean(rows)
        hh, mm = E.RELEASE_EASTERN
        assert rows[0]["label"] == "Nerra Daily" and rows[0]["time"] == f"{hh % 12 or 12}:{mm:02d} AM ET"
        assert any(r["time"] == "7:00 AM ET" for r in rows) and RS.SHORT_FIRST == dt.time(7, 0)
        tpl = (ROOT / "templates" / "network_page.html.j2").read_text(encoding="utf-8")
        assert "6:35" not in tpl and "12:00 PM" not in tpl


# --------------------------------------------------------------------------
# Freshness wiring
# --------------------------------------------------------------------------

class TestFreshness:
    def test_finalize_rerenders_and_commits_the_homepage(self):
        wf = (ROOT / ".github" / "workflows" / "run-show.yml").read_text(encoding="utf-8")
        finalize = wf.split("  finalize:", 1)[1]
        assert "python generate_html.py --network --blogs --sitemap" in finalize
        gallery = finalize.index("build_gallery_manifest.py")
        assert finalize.index("python generate_html.py --homepage") > gallery
        assert "git add index.html" in finalize

    def test_nerra_daily_refreshes_and_commits_the_homepage(self):
        wf = (ROOT / ".github" / "workflows" / "nerra-daily.yml").read_text(encoding="utf-8")
        build = wf.index("python scripts/build_daily_edition.py")
        refresh = wf.index("python generate_html.py --homepage")
        commit = wf.index("name: Commit edition artifacts")
        assert build < refresh < commit
        add_paths = wf[commit:].split("commit-message:", 1)[0]
        assert re.search(r"^\s+index\.html$", add_paths, re.M)
        # Only the homepage: --network would rewrite pages this workflow
        # does not commit.
        assert "generate_html.py --network" not in wf

    def test_all_renders_the_homepage_after_the_pages_it_links(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        block = src.split("    if args.all:", 1)[1].split("        return\n", 1)[0]
        assert block.index("generate_all_blogs(") < block.index("generate_network_page(")
        assert block.index("generate_topic_hub_pages(") < block.index("generate_network_page(")


class TestMobileAndChrome:
    def test_no_fixed_widths_wider_than_a_phone(self):
        tpl = (ROOT / "templates" / "network_page.html.j2").read_text(encoding="utf-8")
        style = tpl.split("<style>", 1)[1].split("</style>", 1)[0]
        assert style.count("{") == style.count("}")
        for px in re.findall(r"(?<![-\w])(?:min-)?width:\s*(\d+)px", style):
            assert int(px) <= 360, px

    def test_brand_colour_is_never_raw_text(self):
        tpl = (ROOT / "templates" / "network_page.html.j2").read_text(encoding="utf-8")
        style = tpl.split("<style>", 1)[1].split("</style>", 1)[0]
        assert not re.search(r"(?<!-)color:\s*var\(--show-color\)", style)

    def test_members_only_never_in_the_body(self, home):
        body = home.split('<div class="lt-page">', 1)[1].split('<footer class="nn-footer">', 1)[0]
        for s in G._build_all_shows_list():
            if s.get("access") == "members_only":
                assert s["name"] not in body, s["slug"]
