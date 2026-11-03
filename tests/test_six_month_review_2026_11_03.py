"""Guards from the six-month network review (Nov 3 2026).

Each class pins one rule the review found broken on main. See
``docs/reviews/network_review_2026_11_03.md`` for the evidence.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _tracked(*patterns: str) -> list[str]:
    out = subprocess.run(["git", "ls-files", "--", *patterns], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line.strip()]


class TestNoEpisodeAudioIsTracked:
    """Landmine #1, third recurrence: the hook Short's spliced FLAC source
    (``engine/short_furniture.py``, Oct 30) was written into
    ``digests/<dir>/youtube_tmp/`` and the video job's ``git add -A digests/``
    committed thirteen of them (571 MB) in three days."""

    def test_no_audio_or_video_file_under_digests_is_tracked(self):
        media = _tracked("digests/**/*.flac", "digests/*.flac", "digests/**/*.wav",
                         "digests/**/*.mp3", "digests/**/*.mp4", "digests/**/*.m4a",
                         "digests/**/*.ogg", "digests/**/*.aac")
        assert media == [], f"episode media is tracked at HEAD: {media[:5]}"

    def test_the_short_source_intermediates_are_ignored(self):
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        assert "digests/*/youtube_tmp/*_short_source.flac" in ignore
        assert "digests/*/youtube_tmp/*_short_source.json" in ignore
        assert "digests/**/*.flac" in ignore

    def test_the_word_json_beside_the_flac_is_not_tracked_either(self):
        assert _tracked("digests/*/youtube_tmp/*_short_source.json") == []


class TestMonthAbbreviationsNeedADate:
    """``replace_dates`` expanded every bare ``Mar``/``Jan`` token: Nerra
    Daily aired "March-a-Lago" and "January Ferrigan" (a hyphen and a
    space are both word boundaries). A month abbreviation is a month only
    when a day or a year follows it."""

    @pytest.mark.parametrize("text", ["Mar-a-Lago", "Jan Ferrigan", "Oct-Dec quarter",
                                      "in Mar", "Dec Jones said", "Aug Wilson"])
    def test_names_and_ranges_are_untouched(self, text):
        from assets.pronunciation import replace_dates
        assert replace_dates(text) == text

    @pytest.mark.parametrize("text, spoken", [
        ("Feb 15, 2026", "February fifteenth"),
        ("Jan. 5, 2026", "January fifth"),
        ("Sept 9, 2026", "September ninth"),
        ("the Mar 3 hearing", "March 3"),
        ("Dec 2025", "December 2025"),
    ])
    def test_dates_still_expand(self, text, spoken):
        from assets.pronunciation import replace_dates
        assert spoken in replace_dates(text)


class TestDubViewersLandOnTheirLanguage:
    """``engine.funnel.destination_for`` sent every @NerraRU / @NerraFR Short
    of a show with no per-channel destination to the ENGLISH show page
    (Fascinating Frontiers and Modern Investing on both channels; Tesla and
    SpaceX on French). The language's front page is the fallback; a
    language the site does not publish in keeps the show page."""

    @pytest.fixture
    def load(self):
        from engine.config import load_config
        return lambda slug: load_config(ROOT / "shows" / f"{slug}.yaml")

    @pytest.mark.parametrize("slug", ["fascinating_frontiers", "modern_investing"])
    def test_ru_and_fr_dubs_point_at_the_language_hub(self, load, slug):
        from engine import funnel
        cfg = load(slug)
        assert funnel.destination_for(cfg, channel="ru") == "https://nerranetwork.com/ru/index.html"
        assert funnel.destination_for(cfg, channel="fr") == "https://nerranetwork.com/fr/index.html"

    def test_a_configured_destination_still_wins(self, load):
        from engine import funnel
        assert funnel.destination_for(load("spacex"), channel="ru") == \
            "https://nerranetwork.com/ru/spacex.html"
        assert funnel.destination_for(load("spacex"), channel="fr") == \
            "https://nerranetwork.com/fr/index.html"

    def test_english_and_unpublished_languages_are_unchanged(self, load):
        from engine import funnel
        cfg = load("fascinating_frontiers")
        assert funnel.destination_for(cfg, channel="en") == cfg.publishing.rss_link
        assert funnel.destination_for(cfg, channel="zh") == cfg.publishing.rss_link

    def test_the_hubs_the_fallback_names_are_generated(self):
        from engine import funnel
        for lang in funnel._hub_languages():
            assert (ROOT / lang / "index.html").exists(), f"{lang}/index.html is linked but not generated"


class TestButtondownEmailReadFollowsPagesAndRecords:
    """``fetch_recent_emails`` read ONE unordered page of 50 from ``/emails``
    and filtered it to the window — the night after the first Nerra Daily
    send it returned ``[]`` (the page held older emails). The committed send
    record (``digests/nerra_daily/email/<date>.json``) is the primary read
    and the list is followed through ``next``."""

    @staticmethod
    def _resp(status=200, body=None):
        from unittest.mock import MagicMock
        resp = MagicMock()
        resp.status_code = status
        resp.json.return_value = body if body is not None else {}
        return resp

    def _now(self):
        import datetime as dt
        return dt.datetime.now(dt.timezone.utc)

    def test_the_list_is_followed_past_a_page_of_old_emails(self, tmp_path):
        from unittest.mock import patch
        import scripts.fetch_buttondown_stats as F
        import datetime as dt
        old = (self._now() - dt.timedelta(days=200)).strftime("%Y-%m-%dT%H:%M:%SZ")
        new = (self._now() - dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        page1 = {"results": [{"id": f"em_old{i}", "status": "sent", "publish_date": old,
                              "slug": f"tesla-ep{i}"} for i in range(50)],
                 "next": "https://api.buttondown.com/v1/emails?page=2"}
        page2 = {"results": [{"id": "em_new", "status": "sent", "publish_date": new,
                              "slug": "nerra-daily-2026-11-02", "subject": "Nerra Daily"}],
                 "next": None}
        with patch.object(F.requests, "get", side_effect=[self._resp(body=page1), self._resp(body=page2)]), \
             patch("engine.newsletter.email_analytics", return_value={"recipients": 14, "opens": 7}):
            rows = F.fetch_recent_emails("key", records_dir=tmp_path)
        assert [r["id"] for r in rows] == ["em_new"]
        assert rows[0]["kind"] == "nerra_daily" and rows[0]["recipients"] == 14

    def test_a_committed_send_is_read_even_when_the_list_fails(self, tmp_path):
        from unittest.mock import patch
        import scripts.fetch_buttondown_stats as F
        import json
        created = (self._now()).strftime("%Y-%m-%dT%H:%M:%SZ")
        (tmp_path / "2026-11-02.json").write_text(json.dumps({
            "date": "2026-11-02", "email_id": "em_rec", "created_at": created,
            "subject": "Nerra Daily — Nov 2"}), encoding="utf-8")
        with patch.object(F.requests, "get", return_value=self._resp(status=500)), \
             patch("engine.newsletter.email_analytics", return_value={"recipients": 14, "opens": 5, "clicks": 1}):
            rows = F.fetch_recent_emails("key", records_dir=tmp_path)
        assert rows and rows[0]["id"] == "em_rec" and rows[0]["kind"] == "nerra_daily"
        assert rows[0]["slug"] == "nerra-daily-2026-11-02"
        assert F.summarize_nerra_daily(rows)["sends"] == 1

    def test_nothing_readable_is_none_not_empty(self, tmp_path):
        from unittest.mock import patch
        import scripts.fetch_buttondown_stats as F
        with patch.object(F.requests, "get", return_value=self._resp(status=500)):
            assert F.fetch_recent_emails("key", records_dir=tmp_path) is None

    def test_the_real_records_dir_is_the_committed_one(self):
        import scripts.fetch_buttondown_stats as F
        assert F.SEND_RECORDS_DIR == ROOT / "digests" / "nerra_daily" / "email"


class TestHandoffRevisionJudgesAlignedHandoffs:
    """Nerra Daily's handoff-variety revision measured the DRAFT before
    ``realign_handoffs`` moved its handoffs onto the segments they introduce,
    so a shifted draft was judged (and revised) against the wrong segments
    and the realigned text shipped unrevised. The order is realign, then
    revise, and the revision is realigned before it is adopted."""

    def test_realign_runs_before_the_variety_revision(self):
        src = (ROOT / "scripts" / "build_daily_edition.py").read_text(encoding="utf-8")
        body = src.split("def _generate_links(", 1)[1].split("\ndef ", 1)[0]
        assert "links = realign_handoffs(links, segments)" in body
        assert body.index("realign_handoffs(links, segments)") < body.index("_enforce_handoff_variety(")

    def test_the_revised_draft_is_realigned_before_adoption(self):
        src = (ROOT / "scripts" / "build_daily_edition.py").read_text(encoding="utf-8")
        body = src.split("def _enforce_handoff_variety(", 1)[1].split("\ndef ", 1)[0]
        assert "realign_handoffs(revised, segments)" in body
        assert body.index("realign_handoffs(revised, segments)") < body.index("return adopt_revised_handoffs(links, revised, segments)")


class TestFeedTitlesHaveOneOwner:
    """Two feed-title writers had grown outside ``engine/titles.py``: a
    correction with ``amend_headline`` wrote the headline raw into the RSS
    ``<title>`` and the per-language feeds wrote the translated title raw."""

    def test_an_amended_rss_title_is_clipped_through_titles(self, tmp_path):
        from engine import corrections as C
        from engine.titles import PODCAST_EPISODE_TITLE_MAX
        headline = "Corrected: " + " ".join(["word"] * 40)
        rss = tmp_path / "f.rss"
        rss.write_text("<rss><channel><item><title>Ep 1: Old hook</title>"
                       "<itunes:title>Ep 1: Old hook</itunes:title>"
                       "<itunes:episode>1</itunes:episode>"
                       "<description><![CDATA[<b>Old hook</b> body]]></description></item>"
                       "</channel></rss>", encoding="utf-8")
        n = C.amend_rss_feed(rss, 1, {"headline": headline, "replacements": []}, dry_run=False)
        assert n >= 1
        out = rss.read_text(encoding="utf-8")
        import re
        titles = re.findall(r"<(?:itunes:)?title>(.*?)</(?:itunes:)?title>", out)
        assert titles and all(t.startswith("Ep 1: ") for t in titles)
        assert all(len(t) <= PODCAST_EPISODE_TITLE_MAX for t in titles), [len(t) for t in titles]

    def test_the_language_feed_clips_the_translated_title(self, tmp_path):
        import json
        import xml.etree.ElementTree as ET
        pytest.importorskip("feedgen")
        from engine import language_feeds
        from engine.titles import PODCAST_EPISODE_TITLE_MAX
        long_title = "Ép 4 : " + " ".join(["mot"] * 60)
        summaries = tmp_path / "summaries_demo.json"
        summaries.write_text(json.dumps({"podcast": "demo", "summaries": [{
            "date": "2026-06-15", "episode_num": 4, "episode_title": "Ep 4: English title",
            "audio_url": "https://audio.nerranetwork.com/demo/Ep004.mp3",
            "translations": {"fr": {
                "audio_url": "https://audio.nerranetwork.com/demo/Ep004.fr.mp3",
                "title": long_title, "description": "description française",
                "duration_sec": 347.7}}}]}, ensure_ascii=False), encoding="utf-8")
        out = tmp_path / language_feeds.feed_filename("demo_podcast.rss", "fr")
        result = language_feeds.build_language_feed(
            slug="demo", lang="fr", summaries_path=summaries, out_path=out,
            guid_prefix="demo", channel_title="Demo (Français)", channel_description="d",
            channel_link="https://nerranetwork.com/demo.html", channel_author="Patrick",
            channel_email="x@example.com", channel_image="https://nerranetwork.com/c.jpg")
        assert result is not None
        titles = [it.find("title").text for it in ET.parse(out).getroot().find("channel").findall("item")]
        assert titles and all(len(t) <= PODCAST_EPISODE_TITLE_MAX for t in titles), titles
        assert titles[0].startswith("Ép 4 :")


class TestStripModeLedgersAreNotAllMalformed:
    """Peptides Weekly and Longevity Weekly were still on ``on_failure:
    strip``; the strip path writes a policy-2 sidecar with no per-entry
    status, and ``claims.html`` read every one of their claims as
    "malformed" (138 of 138 on the last six episodes each). The pages now
    read a status-less entry from the gate's own lists, and no show pins
    strip any more — flag has been the network policy since Oct 1 2026."""

    def test_no_show_still_pins_strip_mode(self):
        import yaml
        pinned = []
        for path in sorted((ROOT / "shows").glob("*.yaml")):
            if path.stem.startswith("_"):
                continue
            cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            mode = ((cfg.get("source_integrity") or {}).get("on_failure") or "").lower()
            if mode == "strip":
                pinned.append(path.stem)
        assert pinned == [], f"strip mode is no longer the network policy: {pinned}"

    def test_a_status_less_policy_2_entry_takes_the_gate_verdict(self, tmp_path):
        import json
        from engine.claims_ledger import read_sidecar
        side = tmp_path / "x_claims.json"
        side.write_text(json.dumps({
            "version": 1,
            "gate": {"policy_version": 2, "passed": True,
                     "verified_claims": [{"id": "c1"}],
                     "failed_verifications": [{"id": "c2", "passed": False, "resolved": True,
                                               "unreachable": False}],
                     "shape_errors": ["c3: missing quote"]},
            "claims": [
                {"id": "c1", "claim": "A verified sentence.", "source_url": "https://a.example/1"},
                {"id": "c2", "claim": "A quote that did not match.", "source_url": "https://a.example/2"},
                {"id": "c3", "claim": "A malformed entry.", "source_url": "https://a.example/3"},
                {"id": "c4", "claim": "Anchored, never checked.", "source_url": "https://a.example/4"},
            ]}), encoding="utf-8")
        out = read_sidecar(side)
        by_id = {c["id"]: c["status"] for c in out["claims"]}
        assert by_id == {"c1": "verified", "c2": "unverified_quote_mismatch",
                         "c3": "malformed", "c4": "verified"}

    def test_an_entry_with_a_status_is_left_alone(self, tmp_path):
        import json
        from engine.claims_ledger import read_sidecar
        side = tmp_path / "y_claims.json"
        side.write_text(json.dumps({"gate": {"policy_version": 2, "verified_claims": [{"id": "c1"}]},
                                    "claims": [{"id": "c1", "claim": "Flagged on purpose.",
                                                "status": "unverified_unreachable"}]}), encoding="utf-8")
        assert read_sidecar(side)["claims"][0]["status"] == "unverified_unreachable"

    def test_the_committed_health_ledgers_now_read_as_checked(self):
        from engine.claims_ledger import read_sidecar
        for slug in ("peptides", "longevity"):
            paths = sorted((ROOT / "digests" / slug).glob("*_claims.json"))[-3:]
            for path in paths:
                out = read_sidecar(path)
                statuses = [c["status"] for c in out["claims"]]
                assert statuses and "malformed" not in statuses, (path.name, statuses[:5])


class TestSiteHeadlineCarriesEngagedSessions:
    """733 of the 999 sessions in the 28 days to Nov 2 were eight spike days
    of 0.6-9 s visits to one page (98.8% bounce, one session per user); the
    dashboard repeated 999. GA4's engaged session is the human floor and is
    fetched, totalled (null, never 0, when the column is absent) and printed."""

    def test_the_fetcher_requests_and_totals_engaged_sessions(self):
        src = (ROOT / "scripts" / "fetch_ga4_stats.py").read_text(encoding="utf-8")
        core = src.split("core_metrics = [", 1)[1].split("]", 1)[0]
        assert '"engagedSessions"' in core
        assert '"engaged_sessions"' in src.split("totals = {", 1)[1].split("}", 1)[0]

    def test_totals_are_null_without_the_column(self):
        # The committed day_series predates the column: the total must read
        # None rather than a zero that looks like nobody stayed.
        rows = [{"date": "20261102", "sessions": 5, "activeUsers": 5, "screenPageViews": 5}]
        engaged = (sum(int(r.get("engagedSessions", 0)) for r in rows)
                   if any("engagedSessions" in r for r in rows) else None)
        assert engaged is None

    def test_the_dashboard_prints_engaged_beside_sessions(self):
        html = (ROOT / "management.html").read_text(encoding="utf-8")
        assert "engaged_sessions" in html
        assert html.count("engaged_sessions != null") >= 2


class TestTheLeadPictureIsThisStorysScene:
    """The Nov 2 front page led with a coral reef under "AI cloud lab uses
    robots and models to compress protein engineering": the chooser compared
    exact words ("robots" vs "Robotic", "models" vs "molecular models" scored
    one each, under the floor of two) and fell back to the first scene in
    slice order. Tokens are stemmed now, one unique match is enough, and when
    the episode's prompts are known and none depicts the headline the story
    gets no scene (the template shows the show's cover) rather than another
    story's picture."""

    @staticmethod
    def _index():
        base = "https://g.example"
        ef = ["show_slug", "episode_date", "episode_id"]
        imf = ["image_id", "episode", "intended_use"]
        from engine.landing_test import LANDSCAPE_USE
        return {"base_url": base, "episode_fields": ef, "image_fields": imf,
                "episodes": [["pt", "2026-11-02", "ep232"]],
                "images": [["coral", 0, LANDSCAPE_USE], ["robotic", 0, LANDSCAPE_USE],
                           ["pipette", 0, LANDSCAPE_USE]]}

    PROMPTS = {
        "coral": "Sparse crown-of-thorns starfish on diverse coral formations in sunlit clear ocean water",
        "robotic": "Robotic machinery handling molecular models in a high-tech facility during nighttime",
        "pipette": "Robotic arms pipetting protein samples into microplates inside an automated lab at dusk",
    }
    HOOK = "AI cloud lab uses robots and models to compress protein engineering from years to weeks"

    def test_stems_match_the_lab_scene_not_the_first_scene(self):
        from engine.landing_test import episode_scene
        out = episode_scene(self._index(), "pt", 232, "2026-11-02", hook=self.HOOK, prompts=self.PROMPTS)
        assert out and out["matched"] is True
        assert "/coral." not in out["url"] and ("/robotic." in out["url"] or "/pipette." in out["url"])

    def test_a_headline_no_scene_depicts_gets_no_scene(self):
        from engine.landing_test import episode_scene
        out = episode_scene(self._index(), "pt", 232, "2026-11-02",
                            hook="Treasury auction yields climb as dealers absorb record supply",
                            prompts=self.PROMPTS)
        assert out is None

    def test_without_prompts_the_first_scene_still_stands_in(self):
        from engine.landing_test import episode_scene
        out = episode_scene(self._index(), "pt", 232, "2026-11-02", hook=self.HOOK, prompts={})
        assert out and out["matched"] is False and "/coral." in out["url"]

    def test_a_single_shared_word_wins_only_when_unique(self):
        from engine.landing_test import episode_scene
        prompts = {"coral": "Coral reef under sunlight", "robotic": "Protein folding diagram on a screen",
                   "pipette": "A quiet harbour at dawn"}
        out = episode_scene(self._index(), "pt", 232, "2026-11-02", hook="New protein map", prompts=prompts)
        assert out and out["matched"] and "/robotic." in out["url"]
        prompts["pipette"] = "A protein sample in a vial"  # two scenes tie at one word: not unique
        assert episode_scene(self._index(), "pt", 232, "2026-11-02", hook="New protein map", prompts=prompts) is None

    def test_stemming_folds_plurals_and_adjectives(self):
        from engine.landing_test import _stems
        assert _stems("robots models engineering") & _stems("Robotic machinery handling molecular models") >= {"robot", "model"}


class TestRegistryOnlyShowsCreditTheirHost:
    """Every Nerra Daily post said "By Patrick": the byline read
    ``publishing.host_name`` from a show YAML Nerra Daily does not have (it is
    registry-only by design). The registry's ``host`` is read for those."""

    def test_nerra_daily_is_mira_and_an_ai_host(self):
        from engine.blog import _show_host_kind, _show_host_name
        assert _show_host_name("nerra_daily") == "Mira"
        assert _show_host_kind("nerra_daily") == "ai"

    def test_yaml_shows_are_unchanged(self):
        from engine.blog import _show_host_kind, _show_host_name
        assert _show_host_name("offshore_north") == "Dan"
        assert _show_host_name("tesla") == "Patrick" and _show_host_kind("tesla") == "human"


class TestImageryCreditNamesItsSource:
    """Every YouTube description credited "Photos via Pexels:" over two
    identical Grok lines (run_show appends the credit at two sites; no show
    has used Pexels since June)."""

    def test_grok_credits_are_labelled_imagery_and_said_once(self):
        from engine.config import load_config
        from engine.video_metadata import build_long_form_metadata
        cfg = load_config(ROOT / "shows" / "tesla.yaml")
        meta = build_long_form_metadata(
            cfg, episode_num=999, today_str="2026-11-03", hook="A hook for the test",
            digest_text="# Tesla Shorts Time\n\nA hook for the test\n\n### Top News\n\n1. **Item: Outlet** body.",
            audio_url="https://audio.nerranetwork.com/x.mp3",
            photo_attribution=["Imagery generated by Grok Imagine (xAI).",
                               "Imagery generated by Grok Imagine (xAI)."])
        text = meta["description"]
        assert text.count("Imagery generated by Grok Imagine (xAI).") == 1
        assert "Imagery:" in text and "Photos via Pexels" not in text

    def test_a_pexels_credit_keeps_its_own_label(self):
        from engine.config import load_config
        from engine.video_metadata import build_long_form_metadata
        cfg = load_config(ROOT / "shows" / "tesla.yaml")
        text = build_long_form_metadata(
            cfg, episode_num=999, today_str="2026-11-03", hook="A hook for the test",
            digest_text="# Tesla Shorts Time\n\nA hook for the test",
            audio_url="https://audio.nerranetwork.com/x.mp3",
            photo_attribution=["Photo by A. Person on Pexels",
                               "Imagery generated by Grok Imagine (xAI)."])["description"]
        assert "Photos via Pexels:\nPhoto by A. Person on Pexels" in text
        assert "Imagery:\nImagery generated by Grok Imagine (xAI)." in text


class TestSmallPageDefects:
    def test_the_explore_page_does_not_nest_a_second_main(self):
        src = (ROOT / "templates" / "explore_page.html.j2").read_text(encoding="utf-8")
        assert "<main" not in src and 'id="main-content"' not in src

    def test_the_dead_buttondown_embed_tracker_is_gone(self):
        js = (ROOT / "assets" / "js" / "tracking.js").read_text(encoding="utf-8")
        assert "embed-subscribe" not in js and "attachNewsletterTracking" not in js


class TestSpaceXSaysClosedFridayBeforeMondaysOpen:
    """Ep149 (Monday Nov 2, run at 03:30 New York) spoke Friday's close as
    "closed at" beside a hook about pre-market trading. Before Monday's
    09:30 open the last bar is Friday's and the sentence says so; a weekday
    after the close is still "closed at"."""

    def _ny(self, weekday_date: str, hhmm: str):
        import datetime as dt
        from zoneinfo import ZoneInfo
        h, m = (int(x) for x in hhmm.split(":"))
        y, mo, d = (int(x) for x in weekday_date.split("-"))
        return dt.datetime(y, mo, d, h, m, tzinfo=ZoneInfo("America/New_York"))

    def test_monday_before_the_open_is_fridays_close(self):
        from shows.hooks.spacex import _price_sentence
        out = _price_sentence(134.72, "-6.4%", "yfinance_history", now=self._ny("2026-11-02", "03:30"))
        assert "closed Friday at" in out

    def test_sunday_is_fridays_close_too(self):
        from shows.hooks.spacex import _price_sentence
        assert "closed Friday at" in _price_sentence(134.72, "-6.4%", "yfinance_history",
                                                     now=self._ny("2026-11-01", "08:00"))

    def test_a_weekday_evening_is_plain_closed_at(self):
        from shows.hooks.spacex import _price_sentence
        out = _price_sentence(134.72, "-6.4%", "yfinance_history", now=self._ny("2026-11-03", "21:30"))
        assert "closed at" in out and "Friday" not in out

    def test_monday_pre_market_live_quote_is_trading_at(self):
        from shows.hooks.spacex import _price_sentence
        out = _price_sentence(136.1, "+1.0%", "yfinance_fast_info", now=self._ny("2026-11-02", "07:30"))
        assert "is trading at" in out


class TestShowPagesAskOurOwnMarketsRoute:
    """tesla.html and spacex.html sent every visitor's browser to
    api.allorigins.win and corsproxy.io with a Yahoo Finance URL (a free
    proxy sees the IP, can inject content, fails unpredictably) although the
    network has had its own markets route since Oct 29. The templates and
    the generator name no proxy; the widget asks the route."""

    PROXIES = ("allorigins", "corsproxy", "query1.finance.yahoo", "query2.finance.yahoo")

    def test_no_template_or_generator_names_a_cors_proxy(self):
        for rel in ("templates/show_page.html.j2", "templates/spacex_dashboard.html.j2",
                    "generate_html.py", "templates/base.html.j2"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            for host in self.PROXIES:
                assert host not in text, f"{rel} still names {host}"

    def test_the_widget_reads_the_markets_route(self):
        src = (ROOT / "templates" / "show_page.html.j2").read_text(encoding="utf-8")
        assert "stock_widget.markets_api" in src and "prev_close" in src
        import generate_html as G
        from engine.newsroom import LIVE_MARKETS_API
        assert all("yahoo_symbol" not in w for w in G._STOCK_WIDGETS.values())
        assert LIVE_MARKETS_API.startswith("https://api.nerranetwork.com/")


class TestTopWorldNamesTheDesksItRead:
    """Four of the five desks are members-only by design (Oct 15), so the
    public WYNTK line "This edition draws on 1 of the 5 Omni View regional
    desks" read as a daily defect, and the registry promised five desks
    "which publish earlier each morning". A partial intake names the desks
    read; the registry promises no cadence."""

    def test_a_partial_intake_names_the_desks(self):
        from shows.hooks.omni_view_world import intake_line
        assert intake_line(1, 5, ["North America"]) == \
            "This edition also draws on the Omni View North America desk."
        assert "Europe and North America desks" in intake_line(2, 5, ["Europe", "North America"])
        assert "all 5" in intake_line(5, 5, ["a", "b", "c", "d", "e"])
        assert intake_line(0, 5, []) == ""

    def test_the_hook_passes_the_names(self):
        src = (ROOT / "shows" / "hooks" / "omni_view_world.py").read_text(encoding="utf-8")
        assert "intake_line(desks_live, len(DESKS), desk_names)" in src

    def test_the_registry_promises_no_desk_cadence(self):
        import yaml
        meta = yaml.safe_load((ROOT / "shows" / "network_meta.yaml").read_text(encoding="utf-8"))
        shows = meta.get("shows", meta)
        tw = shows["omni_view_world"] if isinstance(shows, dict) else next(s for s in shows if s["slug"] == "omni_view_world")
        blob = " ".join(str(v) for v in tw.values() if isinstance(v, str)).lower()
        assert "publish earlier each morning" not in blob
        assert "five regional desks" not in blob


class TestTheConsentBarIsCompact:
    """The cookie banner was 147 px on a phone — a third of the first
    screen — over the lead picture: heading, a three-line paragraph, three
    stacked buttons. Heading and text share one two-line block and the
    equal-weight actions sit in one row."""

    def test_the_copy_block_exists_and_clamps(self):
        base = (ROOT / "templates" / "base.html.j2").read_text(encoding="utf-8")
        assert '<div class="nn-consent-copy">' in base
        import re
        css = (ROOT / "styles" / "main.css").read_text(encoding="utf-8")
        assert re.search(r"#nn-consent-banner \.nn-consent-copy \{[^}]*-webkit-line-clamp: 2", css)

    def test_accept_and_reject_keep_equal_metrics(self):
        css = (ROOT / "styles" / "main.css").read_text(encoding="utf-8")
        assert 'data-nn-consent="accept-all"]' not in css and 'data-nn-consent="reject-all"]' not in css

    def test_the_phone_actions_sit_in_one_row(self):
        css = (ROOT / "styles" / "main.css").read_text(encoding="utf-8")
        phone = css.split("@media (max-width: 480px) {\n  #nn-consent-banner", 1)[1].split("}\n}", 1)[0]
        assert "flex-wrap: nowrap" in phone
