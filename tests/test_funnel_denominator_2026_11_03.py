"""The site's number becomes a number of readers (Nov 3 2026).

``api/ga4_stats.json`` read 999 sessions in 28 days, 898 of them Direct; 492
landed on ``/personal-interest.html`` at a 98.8% bounce, one session per
user, 0.6-9.4 s a visit, in eight spikes — the Google Ads campaign that
targets the page, untagged, arriving as Direct under denied ``ad_storage``.
Every site decision since Sep 25 was read through that denominator. Four
things bind now:

* paid links are tagged through the one owner (``engine.funnel`` ``ad``
  kind, ``cpc`` medium, ``google_ads`` source, ``ad_link``, the CLI);
* landing anomalies are named, excluded from the readers' count and PRINTED
  beside the raw total — a judgement rule, never silent, never hidden;
* the email has a funnel row (``by_kind`` / ``stages.click.email``) and an
  ad or an email click never counts as a subscriber;
* real-user vitals are GA4 events the fetcher asks for.
"""

from __future__ import annotations

import importlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from engine import funnel as F  # noqa: E402


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _campaign_in(url: str) -> str:
    m = re.search(r"utm_campaign=([^&\s]+)", url)
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# 1. Paid links have one owner
# ---------------------------------------------------------------------------

class TestPaidLinksHaveOneOwner:
    def test_the_ad_kind_round_trips_with_the_fixed_product_slot(self):
        cid = F.campaign_id("personal", 1, kind="ad", variant="personal-tips")
        assert cid == "nn-personal-en-ad-ep001-personal_tips"
        parsed = F.parse_campaign_id(cid)
        assert parsed is not None
        assert (parsed.show, parsed.channel, parsed.kind, parsed.episode) == \
            ("personal", "en", "ad", 1)
        # An ad-group slug is normalised like every variant.
        assert parsed.variant == F._norm("personal-tips") == "personal_tips"

    def test_ad_link_carries_source_medium_campaign_and_placement(self):
        url = F.ad_link("personal-interest.html", 1, "personal-tips")
        assert url.startswith("https://nerranetwork.com/personal-interest.html?")
        assert "utm_source=google_ads" in url
        assert "utm_medium=cpc" in url
        assert "utm_content=body" in url
        parsed = F.parse_campaign_id(_campaign_in(url))
        assert parsed is not None and parsed.kind == F.KIND_AD
        assert parsed.show == F.AD_PRODUCT_PERSONAL and parsed.episode == 1

    def test_ad_link_accepts_a_full_url_and_the_network_product(self):
        url = F.ad_link("https://nerranetwork.com/", 7, product="network")
        parsed = F.parse_campaign_id(_campaign_in(url))
        assert parsed.show == F.AD_PRODUCT_NETWORK and parsed.episode == 7
        assert url.startswith("https://nerranetwork.com/?utm_source=")

    def test_an_unknown_product_is_coerced_loudly_never_unparseable(self, caplog):
        with caplog.at_level("WARNING"):
            url = F.ad_link("join.html", 3, product="gallery")
        parsed = F.parse_campaign_id(_campaign_in(url))
        assert parsed is not None and parsed.show == F.AD_PRODUCT_NETWORK
        assert any("ad product" in rec.message for rec in caplog.records)

    def test_empty_destination_stays_empty(self):
        assert F.ad_link("", 1) == ""

    def test_the_vocabularies_carry_the_paid_values(self):
        assert F.KIND_AD in F.KINDS
        assert F.MEDIUM_CPC in F.MEDIUMS
        assert F.SOURCE_GOOGLE_ADS in F.SOURCES
        assert F.source_tag(F.SOURCE_GOOGLE_ADS) == "src-google-ads"
        assert F.source_from_tag("src-google-ads") == F.SOURCE_GOOGLE_ADS

    def test_episode_link_resolves_the_ad_medium(self):
        url = F.episode_link("https://nerranetwork.com/join.html", "personal", 2,
                             kind="ad", source=F.SOURCE_GOOGLE_ADS)
        assert "utm_medium=cpc" in url

    def test_the_worker_and_the_client_map_allow_every_funnel_source(self):
        handlers = _read("workers/gallery/src/handlers.ts")
        client = _read("assets/js/footer-subscribe.js")
        utm_map = client.split("var UTM_SOURCE_TAGS = {", 1)[1].split("};", 1)[0]
        for source in sorted(F.SOURCES):
            tag = F.source_tag(source)
            assert f'"{tag}"' in handlers, tag
            assert f"'{tag}'" in utm_map, (
                f"{source} is a funnel source but footer-subscribe.js would "
                "not map utm_source={source} to its tag")
        assert "src-google-ads" in handlers

    def test_the_cli_prints_a_url_whose_campaign_parses_to_kind_ad(self):
        out = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "funnel_link.py"), "ad",
             "--campaign", "1", "--variant", "personal-tips",
             "--to", "personal-interest.html"],
            cwd=ROOT, capture_output=True, text=True, timeout=120, check=True,
        ).stdout.strip()
        assert out.startswith("https://nerranetwork.com/personal-interest.html?")
        parsed = F.parse_campaign_id(_campaign_in(out))
        assert parsed is not None and parsed.kind == "ad"
        assert parsed.show == "personal" and parsed.episode == 1
        assert parsed.variant == "personal_tips"

    def test_the_cli_post_command_tags_an_episode_post(self):
        import funnel_link as cli

        url = cli.post_url("spacex", 150, "x")
        assert url.startswith("https://nerranetwork.com/spacex.html?")
        assert "utm_source=x" in url and "utm_medium=social" in url
        parsed = F.parse_campaign_id(_campaign_in(url))
        assert (parsed.show, parsed.kind, parsed.episode) == ("spacex", "post", 150)
        assert cli.parse_url(url) == parsed
        assert cli.parse_url("https://nerranetwork.com/?utm_campaign=spring") is None

    def test_the_cli_never_hand_rolls_a_query_string(self):
        src = _read("scripts/funnel_link.py")
        assert "utm_" not in src.split("from engine import funnel", 1)[1].replace(
            'query.get("utm_campaign")', "")


# ---------------------------------------------------------------------------
# 2. Landing anomalies — named, excluded, printed
# ---------------------------------------------------------------------------

def _ga4_module():
    import fetch_ga4_stats as mod
    return importlib.reload(mod)


BREAKDOWN = [
    {"landingPagePlusQueryString": "/personal-interest.html",
     "sessionDefaultChannelGroup": "Direct", "deviceCategory": "mobile",
     "country": "United States", "sessions": 480, "engagedSessions": 5,
     "averageSessionDuration": 2.1},
    {"landingPagePlusQueryString": "/personal-interest.html?utm_source=x",
     "sessionDefaultChannelGroup": "Organic Social", "deviceCategory": "desktop",
     "country": "Canada", "sessions": 12, "engagedSessions": 1,
     "averageSessionDuration": 4.0},
    # A healthy page above the floor: never flagged.
    {"landingPagePlusQueryString": "/", "sessionDefaultChannelGroup": "Direct",
     "deviceCategory": "desktop", "country": "Canada", "sessions": 69,
     "engagedSessions": 47, "averageSessionDuration": 120.0},
    # A page that bounces but is under the 50-session floor: never flagged.
    {"landingPagePlusQueryString": "/blog/spacex/ep100.html",
     "sessionDefaultChannelGroup": "Organic Search", "deviceCategory": "mobile",
     "country": "India", "sessions": 20, "engagedSessions": 0,
     "averageSessionDuration": 1.0},
]


class TestLandingAnomalies:
    def test_the_fetcher_asks_for_the_breakdown_with_the_mix_dimensions(self):
        src = _read("scripts/fetch_ga4_stats.py")
        block = src.split("landing_breakdown = _rows(", 1)[1].split("}))", 1)[0]
        for dim in ("landingPagePlusQueryString", "sessionDefaultChannelGroup",
                    "deviceCategory", "country"):
            assert f'"{dim}"' in block, dim
        for met in ("sessions", "engagedSessions", "averageSessionDuration"):
            assert f'"{met}"' in block, met
        assert '"limit": 300' in block

    def test_the_492_session_landing_is_one_anomaly_row_with_its_mix(self):
        mod = _ga4_module()
        rows = mod.landing_anomalies(BREAKDOWN)
        assert isinstance(rows, list) and len(rows) == 1
        a = rows[0]
        assert a["path"] == "/personal-interest.html"
        assert a["sessions"] == 492 and a["engaged_sessions"] == 6
        assert a["bounce_rate"] == pytest.approx(0.9878, abs=1e-3)
        assert a["mean_engagement_s"] == pytest.approx(2.1, abs=0.1)
        assert any(r.startswith("bounce 99%") for r in a["reasons"])
        assert a["channels"][0]["label"] == "Direct"
        assert a["channels"][0]["share_pct"] == pytest.approx(97.6, abs=0.1)
        assert a["devices"][0]["label"] == "mobile"
        assert a["countries"][0]["label"] == "United States"

    def test_engagement_alone_flags_a_page_that_does_not_bounce(self):
        mod = _ga4_module()
        rows = mod.landing_anomalies([
            {"landingPagePlusQueryString": "/x.html", "sessions": 60,
             "engagedSessions": 40, "averageSessionDuration": 1.5},
        ])
        assert len(rows) == 1 and rows[0]["reasons"] == [
            "mean engagement 1.5 s (under 3 s)"]

    def test_unread_is_none_and_clean_is_an_empty_list(self):
        mod = _ga4_module()
        assert mod.landing_anomalies(None) is None
        assert mod.landing_anomalies([]) == []
        assert mod.exclusion_sentence(None) is None
        assert mod.exclusion_sentence([]) == "no anomalous landing pages in the window"
        assert mod.exclusion_sentence(mod.landing_anomalies(BREAKDOWN)) == \
            "492 sessions on 1 anomalous landing excluded"

    def test_the_fetcher_totals_carry_the_readers_count_beside_the_raw(self):
        src = _read("scripts/fetch_ga4_stats.py")
        tail = src.split("totals = {", 1)[1]
        for key in ("anomalous_landing_sessions", "sessions_excluding_anomalies",
                    "anomaly_exclusion"):
            assert f'totals["{key}"]' in tail, key
        assert '"landing_anomalies": anomalies' in src
        assert '"landing_breakdown": landing_breakdown' in src


# ---------------------------------------------------------------------------
# 3. The funnel report: exclusion printed, email row, no ad is a subscriber
# ---------------------------------------------------------------------------

GA4_FIXTURE = {
    "fetched_at": "2026-11-03T00:00:00Z",
    "days": 28,
    "totals": {"active_users": 923, "sessions": 999, "engaged_sessions": 266,
               "page_views": 1241, "anomalous_landing_sessions": 492,
               "sessions_excluding_anomalies": 507,
               "anomaly_exclusion": "492 sessions on 1 anomalous landing excluded"},
    "campaigns": [
        {"sessionSource": "newsletter", "sessionMedium": "email",
         "sessionCampaignName": "nn-tesla-en-email-ep640-nerra_daily",
         "sessions": 9, "engagedSessions": 6},
        {"sessionSource": "newsletter", "sessionMedium": "email",
         "sessionCampaignName": "nn-nerra_daily-en-email-ep075-personal",
         "sessions": 3, "engagedSessions": 3},
        {"sessionSource": "x", "sessionMedium": "social",
         "sessionCampaignName": "nn-tesla-en-post-ep640-gallery",
         "sessions": 4, "engagedSessions": 2},
        {"sessionSource": "google_ads", "sessionMedium": "cpc",
         "sessionCampaignName": "nn-personal-en-ad-ep001-personal_tips",
         "sessions": 300, "engagedSessions": 3},
        {"sessionSource": "(direct)", "sessionMedium": "(none)",
         "sessionCampaignName": "(direct)", "sessions": 500,
         "engagedSessions": 80},
    ],
    "landing_pages": [
        {"landingPagePlusQueryString": "/personal-interest.html",
         "sessions": 492, "activeUsers": 493, "bounceRate": 0.9878},
        {"landingPagePlusQueryString": "/spacex.html",
         "sessions": 7, "activeUsers": 5, "bounceRate": 0.3},
    ],
    "landing_anomalies": [
        {"path": "/personal-interest.html", "sessions": 492,
         "engaged_sessions": 6, "bounce_rate": 0.9878,
         "mean_engagement_s": 2.1, "reasons": ["bounce 99% (floor 95%)"],
         "channels": [{"label": "Direct", "sessions": 480, "share_pct": 97.6}],
         "devices": [], "countries": []},
    ],
    "conversions": [],
    "site_events": [],
}


def _build(tmp_path, ga4):
    api = tmp_path / "api"
    api.mkdir(parents=True, exist_ok=True)
    (api / "ga4_stats.json").write_text(json.dumps(ga4))
    module = importlib.import_module("scripts.build_funnel")
    original = module._API
    module._API = api
    try:
        return module.build()
    finally:
        module._API = original


class TestTheFunnelReport:
    def test_the_visit_stage_prints_the_exclusion_and_keeps_the_raw_total(self, tmp_path):
        data = _build(tmp_path, GA4_FIXTURE)
        site = data["stages"]["visit"]["site"]
        assert site["configured"] is True
        assert site["sessions_raw"] == 999
        assert site["anomalous_sessions"] == 492
        assert site["anomalous_landings"] == 1
        assert site["sessions"] == 507
        assert site["exclusion"] == "492 sessions on 1 anomalous landing excluded"
        assert site["anomalies"][0]["path"] == "/personal-interest.html"
        # The page is not a configured funnel destination, so the funnel's
        # own landing total is untouched and says so.
        totals = data["stages"]["visit"]["totals"]
        assert totals["sessions"] == 7 and totals["sessions_raw"] == 7
        assert totals["excluded_sessions"] == 0
        assert totals["exclusion"] == "no anomalous funnel landings"

    def test_an_anomalous_funnel_destination_is_flagged_and_kept_out_of_the_count(
            self, tmp_path, monkeypatch):
        module = importlib.import_module("scripts.build_funnel")
        ga4 = json.loads(json.dumps(GA4_FIXTURE))
        ga4["landing_pages"].append(
            {"landingPagePlusQueryString": "/ru/spacex.html", "sessions": 80,
             "activeUsers": 80, "bounceRate": 0.99})
        ga4["landing_anomalies"].append(
            {"path": "/ru/spacex.html", "sessions": 80, "engaged_sessions": 1,
             "bounce_rate": 0.99, "mean_engagement_s": 1.0,
             "reasons": ["bounce 99% (floor 95%)"], "channels": [],
             "devices": [], "countries": []})
        out = module._visits(ga4, {"spacex-ru": "https://nerranetwork.com/ru/spacex.html",
                                   "spacex-default": "https://nerranetwork.com/spacex.html"})
        ru = out["by_destination"]["spacex-ru"]
        assert ru["anomalous"] is True
        assert ru["sessions_raw"] == 80 and ru["sessions"] == 0
        assert out["totals"] == {
            "sessions": 7, "sessions_raw": 87, "excluded_sessions": 80,
            "exclusion": "80 sessions on 1 anomalous funnel landing excluded"}

    def test_unread_anomalies_leave_the_readers_count_null_never_zero(self, tmp_path):
        ga4 = json.loads(json.dumps(GA4_FIXTURE))
        ga4["landing_anomalies"] = None
        for key in ("anomalous_landing_sessions", "sessions_excluding_anomalies",
                    "anomaly_exclusion"):
            ga4["totals"][key] = None
        data = _build(tmp_path, ga4)
        site = data["stages"]["visit"]["site"]
        assert site["sessions_raw"] == 999
        assert site["sessions"] is None and site["exclusion"] is None
        assert site["anomalous_sessions"] is None
        totals = data["stages"]["visit"]["totals"]
        assert totals["excluded_sessions"] is None and totals["exclusion"] is None
        assert totals["sessions"] == 7

    def test_by_kind_counts_the_email_and_not_the_post(self, tmp_path):
        data = _build(tmp_path, GA4_FIXTURE)
        click = data["stages"]["click"]
        assert click["by_kind"]["email"] == {
            "sessions": 12, "engaged_sessions": 9, "campaigns": 2}
        assert click["by_kind"]["post"] == {
            "sessions": 4, "engaged_sessions": 2, "campaigns": 1}
        assert click["email"] == {"sessions_28d": 12, "engaged_sessions_28d": 9,
                                  "campaigns": 2, "window_days": 28}

    def test_a_google_ads_campaign_parses_like_any_other(self, tmp_path):
        data = _build(tmp_path, GA4_FIXTURE)
        click = data["stages"]["click"]
        assert click["by_kind"]["ad"] == {
            "sessions": 300, "engaged_sessions": 3, "campaigns": 1}
        assert click["by_show"]["personal"]["sessions"] == 300
        row = click["by_campaign"]["nn-personal-en-ad-ep001-personal_tips"]
        assert row["kind"] == "ad" and row["variant"] == "personal_tips"
        assert click["unattributed"]["sessions"] == 500

    def test_an_ad_click_never_counts_as_a_subscriber(self, tmp_path):
        data = _build(tmp_path, GA4_FIXTURE)
        capture = data["stages"]["capture"]
        # The conversions report was read and is empty: a measured zero,
        # with 300 paid sessions and 12 email sessions in the window.
        assert capture["signup_events_total"] == 0
        assert capture["signup_events_by_campaign"] == {}
        src = _read("scripts/build_funnel.py")
        body = src.split("def _captures(", 1)[1].split("\ndef ", 1)[0]
        assert '"conversions"' in body and "campaigns" not in body.replace(
            "signup_events_by_campaign", "")

    def test_the_click_stage_is_null_before_it_is_measured(self, tmp_path):
        data = _build(tmp_path, {"fetched_at": "x", "days": 28, "totals": {}})
        click = data["stages"]["click"]
        assert click["configured"] is False
        assert click["by_kind"] == {} and click["email"] is None
        assert data["stages"]["visit"]["site"]["configured"] is False


# ---------------------------------------------------------------------------
# 4. The dashboard shows the excluded figure and the anomaly row
# ---------------------------------------------------------------------------

class TestTheDashboardPrintsTheExclusion:
    def test_the_site_section_carries_the_anomalies_and_the_readers_count(self, tmp_path):
        import generate_dashboard as gd

        (tmp_path / "api").mkdir()
        (tmp_path / "api" / "ga4_stats.json").write_text(json.dumps(GA4_FIXTURE))
        site = gd.build_audience_section(tmp_path)["site"]
        assert site["configured"] is True
        assert site["totals"]["sessions_excluding_anomalies"] == 507
        assert site["totals"]["anomaly_exclusion"].startswith("492 sessions on 1")
        assert site["landing_anomalies"][0]["path"] == "/personal-interest.html"

    def test_unread_anomalies_reach_the_dashboard_as_none(self, tmp_path):
        import generate_dashboard as gd

        ga4 = json.loads(json.dumps(GA4_FIXTURE))
        ga4["landing_anomalies"] = None
        (tmp_path / "api").mkdir()
        (tmp_path / "api" / "ga4_stats.json").write_text(json.dumps(ga4))
        assert gd.build_audience_section(tmp_path)["site"]["landing_anomalies"] is None

    def test_the_funnel_section_carries_the_site_block_and_the_email_row(self, tmp_path):
        import generate_dashboard as gd

        data = _build(tmp_path, GA4_FIXTURE)
        (tmp_path / "api" / "funnel.json").write_text(json.dumps(data))
        section = gd.build_funnel_section(tmp_path)
        assert section["visit_site"]["exclusion"].startswith("492 sessions")
        assert section["click_email"]["sessions_28d"] == 12
        visit = [s for s in section["stages"] if s["key"] == "visit"][0]
        assert visit["secondary_unit"] == "excluded as anomalous landings"

    def test_management_html_prints_both_numbers_and_the_row(self):
        html = _read("management.html")
        assert "sessions_excluding_anomalies" in html
        assert "anomaly_exclusion" in html
        assert "landing_anomalies" in html
        assert "visit_site" in html and "click_email" in html
        # The Nov 3 engaged-sessions print survives beside it.
        assert html.count("engaged_sessions != null") >= 2


# ---------------------------------------------------------------------------
# 5. Real-user vitals are events the fetcher asks for
# ---------------------------------------------------------------------------

class TestRealUserVitalsAreEvents:
    def test_web_vital_is_an_engagement_event_never_a_conversion(self):
        mod = _ga4_module()
        assert "web_vital" in mod.ENGAGEMENT_EVENTS
        assert "web_vital" not in mod.CONVERSION_EVENTS

    def test_tracking_js_observes_and_sends_web_vital(self):
        js = _read("assets/js/tracking.js")
        assert "PerformanceObserver" in js
        assert "track('web_vital'" in js
        block = js.split("function attachWebVitals", 1)[1].split("// ----- Init", 1)[0]
        for entry in ("largest-contentful-paint", "layout-shift", "'event'"):
            assert entry in block, entry
        for param in ("name: name", "rating:", "page_type:"):
            assert param in block, param
        for rating in ("'good'", "'needs-improvement'", "'poor'"):
            assert rating in block, rating
        assert "attachWebVitals();" in js.split("function init()", 1)[1]
        # ~1 KB, no library.
        assert len(block.encode("utf-8")) < 3000
        assert "web-vitals" not in js

    def test_the_fetcher_reads_the_vitals_report_and_summarises_the_good_share(self):
        mod = _ga4_module()
        src = _read("scripts/fetch_ga4_stats.py")
        assert "customEvent:name" in src and "customEvent:rating" in src
        assert '"web_vitals": web_vitals' in src
        summary = mod.web_vitals_summary([
            {"customEvent:name": "LCP", "customEvent:rating": "good", "eventCount": 40},
            {"customEvent:name": "LCP", "customEvent:rating": "poor", "eventCount": 10},
            {"customEvent:name": "CLS", "customEvent:rating": "good", "eventCount": 5},
            {"customEvent:name": "FID", "customEvent:rating": "good", "eventCount": 99},
        ])
        assert summary["LCP"]["good_share_pct"] == 80.0
        assert summary["LCP"]["total"] == 50
        # Under the 30-sample floor the share is null, never a percentage.
        assert summary["CLS"]["good_share_pct"] is None and summary["CLS"]["total"] == 5
        assert "FID" not in summary
        assert mod.web_vitals_summary(None) is None
