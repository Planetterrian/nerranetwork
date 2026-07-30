"""Drift guards for the funnel instrumentation (July 2026).

The failure this whole layer exists to prevent is silent: if a campaign
id stops round-tripping, or a publishing surface stops tagging its
links, nothing breaks — ``api/funnel.json`` simply reports zeros, and the
network goes back to being unable to tell which surface produces
subscribers without anyone noticing. So the tests here pin the two
halves of the contract against each other and assert that each real
publishing surface actually emits a parseable campaign.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import funnel  # noqa: E402
from engine.config import load_config  # noqa: E402


# ---------------------------------------------------------------------------
# The build/parse contract
# ---------------------------------------------------------------------------

class TestCampaignRoundTrip:
    """``parse_campaign_id`` must be the exact inverse of ``campaign_id``."""

    @pytest.mark.parametrize("show", [
        "spacex", "tesla", "fascinating_frontiers", "models_agents_beginners",
        "privet_russian", "dp_pod",
    ])
    @pytest.mark.parametrize("channel", ["en", "ru", "fr", "zh"])
    @pytest.mark.parametrize("kind", ["short", "long", "episode", "email"])
    @pytest.mark.parametrize("episode", [1, 45, 573, 1204])
    @pytest.mark.parametrize("variant", ["", "stills", "grok_video"])
    def test_round_trip(self, show, channel, kind, episode, variant):
        cid = funnel.campaign_id(show, episode, channel=channel, kind=kind,
                                 variant=variant)
        parsed = funnel.parse_campaign_id(cid)
        assert parsed is not None, f"{cid} did not parse"
        assert parsed.show == show
        assert parsed.channel == channel
        assert parsed.kind == kind
        assert parsed.episode == episode
        assert parsed.variant == variant

    def test_hyphenated_show_cannot_collide_with_its_squashed_form(self):
        # `-` is the separator, so a hyphen inside a component has to be
        # translated rather than dropped: dropping it would make
        # "models-agents" and "modelsagents" the same campaign row.
        a = funnel.campaign_id("models-agents", 1)
        b = funnel.campaign_id("modelsagents", 1)
        assert a != b
        assert funnel.parse_campaign_id(a).show == "models_agents"

    def test_episode_is_zero_padded_so_ids_sort(self):
        assert "ep007" in funnel.campaign_id("spacex", 7)

    @pytest.mark.parametrize("junk", [
        "", "  ", "(organic)", "spring_sale", "nn-spacex-ru-short",
        "nn-spacex-ru-banner-ep001",   # 'banner' is not a known kind
        "nn-spacex-ru-short-epXYZ",
    ])
    def test_foreign_campaigns_return_none_rather_than_guessing(self, junk):
        # GA4 reports organic and third-party campaigns too. Guessing an
        # attribution for those would quietly inflate a show's numbers.
        assert funnel.parse_campaign_id(junk) is None


class TestFunnelLink:
    def test_appends_all_four_parameters(self):
        url = funnel.funnel_link(
            "https://nerranetwork.com/ru/spacex.html",
            source=funnel.SOURCE_YOUTUBE_RU, medium=funnel.MEDIUM_SHORT,
            campaign="nn-spacex-ru-short-ep045",
            placement=funnel.PLACEMENT_COMMENT)
        for part in ("utm_source=youtube_ru", "utm_medium=short",
                     "utm_campaign=nn-spacex-ru-short-ep045",
                     "utm_content=comment"):
            assert part in url

    def test_preserves_an_existing_query_string(self):
        url = funnel.funnel_link("https://x.test/p?ref=a", source="podcast",
                                 medium="episode")
        assert "ref=a" in url and "utm_source=podcast" in url

    def test_is_idempotent(self):
        once = funnel.funnel_link("https://x.test/p", source="podcast",
                                  medium="episode")
        twice = funnel.funnel_link(once, source="x", medium="social")
        assert once == twice

    def test_empty_destination_stays_empty(self):
        # Callers append the line only when truthy — a show with no
        # destination should ship one fewer line, not a bare "?utm_…".
        assert funnel.funnel_link("", source="podcast", medium="episode") == ""


class TestSourceTags:
    def test_round_trip(self):
        for source in sorted(funnel.SOURCES):
            tag = funnel.source_tag(source)
            assert tag.startswith(funnel.SOURCE_TAG_PREFIX)
            assert funnel.source_from_tag(tag) == source

    def test_non_source_tag_is_not_mistaken_for_one(self):
        assert funnel.source_from_tag("ru-spacex") == ""
        assert funnel.source_from_tag("SpaceX Daily") == ""

    def test_channel_source_mapping(self):
        assert funnel.channel_source("en") == funnel.SOURCE_YOUTUBE
        assert funnel.channel_source("ru") == funnel.SOURCE_YOUTUBE_RU
        assert funnel.channel_source("fr") == funnel.SOURCE_YOUTUBE_FR
        # A channel that launches before this map is updated must still be
        # attributable rather than silently becoming "youtube".
        assert funnel.channel_source("de") == "youtube_de"


# ---------------------------------------------------------------------------
# Destinations
# ---------------------------------------------------------------------------

class TestDestinations:
    def test_spacex_ru_points_at_the_russian_landing_page(self):
        cfg = load_config(ROOT / "shows" / "spacex.yaml")
        assert funnel.destination_for(cfg, channel="ru") == \
            "https://nerranetwork.com/ru/spacex.html"

    def test_spacex_en_is_unchanged(self):
        cfg = load_config(ROOT / "shows" / "spacex.yaml")
        assert funnel.destination_for(cfg, channel="en") == \
            "https://nerranetwork.com/spacex.html"

    def test_a_show_without_a_funnel_block_falls_back_to_its_show_page(self):
        cfg = load_config(ROOT / "shows" / "omni_view.yaml")
        assert funnel.destination_for(cfg, channel="ru") == cfg.publishing.rss_link

    def test_the_ru_landing_page_exists_at_the_configured_url(self):
        # The slug/filename landmine, applied to the funnel: nothing in
        # the pipeline fetches its own destination URL, so a mismatch
        # between the configured link and the generated page would 404
        # the network's highest-reach surface indefinitely.
        cfg = load_config(ROOT / "shows" / "spacex.yaml")
        dest = funnel.destination_for(cfg, channel="ru")
        rel = dest.split("nerranetwork.com/", 1)[1]
        assert (ROOT / rel).exists(), f"{rel} is linked but not generated"

    def test_capture_tags_carry_list_and_source(self):
        cfg = load_config(ROOT / "shows" / "spacex.yaml")
        tags = funnel.capture_tags(cfg, channel="ru")
        assert "ru-spacex" in tags
        assert "src-youtube-ru" in tags


# ---------------------------------------------------------------------------
# Publishing surfaces actually emit campaigns
# ---------------------------------------------------------------------------

class TestSurfacesAreInstrumented:
    """Each surface that ships a link must ship a PARSEABLE one.

    Before July 2026 the Shorts description hand-rolled
    ``utm_campaign=ep45`` (no show slug — every show's episode 45 landed
    in one GA4 row) and the RU dub linked the bare homepage with no UTM
    at all. Both are now required to round-trip.
    """

    @staticmethod
    def _campaign_in(text: str) -> str:
        import re
        m = re.search(r"utm_campaign=([^&\s]+)", text)
        return m.group(1) if m else ""

    def test_short_description_carries_a_parseable_campaign(self):
        from engine.video_metadata import build_short_metadata

        cfg = load_config(ROOT / "shows" / "spacex.yaml")
        meta = build_short_metadata(cfg, episode_num=45,
                                    today_str="2026-07-30", hook="A hook")
        parsed = funnel.parse_campaign_id(
            self._campaign_in(meta["description"]))
        assert parsed is not None
        assert (parsed.show, parsed.kind, parsed.episode) == ("spacex", "short", 45)

    def test_short_description_carries_the_experiment_arm(self):
        from engine.video_metadata import build_short_metadata

        cfg = load_config(ROOT / "shows" / "spacex.yaml")
        meta = build_short_metadata(cfg, episode_num=45,
                                    today_str="2026-07-30", hook="A hook",
                                    variant="grok_video")
        parsed = funnel.parse_campaign_id(
            self._campaign_in(meta["description"]))
        assert parsed.variant == "grok_video"

    def test_long_form_description_carries_a_parseable_campaign(self):
        from engine.video_metadata import build_long_form_metadata

        cfg = load_config(ROOT / "shows" / "spacex.yaml")
        meta = build_long_form_metadata(
            cfg, episode_num=45, today_str="2026-07-30", hook="A hook",
            digest_text="Body.", audio_url="")
        parsed = funnel.parse_campaign_id(
            self._campaign_in(meta["description"]))
        assert parsed is not None
        assert parsed.kind == "long"

    def test_ru_dub_description_sends_russian_viewers_to_the_russian_page(self):
        from engine.ru_dub import _ru_long_description

        cfg = load_config(ROOT / "shows" / "spacex.yaml")
        desc = _ru_long_description(cfg, "Описание", episode_num=45,
                                    kind="short")
        assert "nerranetwork.com/ru/spacex.html" in desc
        parsed = funnel.parse_campaign_id(self._campaign_in(desc))
        assert parsed is not None
        assert parsed.channel == "ru"
        # The bare English homepage was the pre-pilot destination and is
        # the regression to guard against.
        assert "🎧 https://nerranetwork.com\n" not in desc

    def test_lang_dub_description_is_tagged(self):
        from engine.lang_dub import DUB_LANGUAGES, _long_description

        cfg = load_config(ROOT / "shows" / "spacex.yaml")
        desc = _long_description(cfg, "Description", DUB_LANGUAGES["fr"],
                                 episode_num=45, kind="short")
        parsed = funnel.parse_campaign_id(self._campaign_in(desc))
        assert parsed is not None and parsed.channel == "fr"


# ---------------------------------------------------------------------------
# The report itself
# ---------------------------------------------------------------------------

class TestFunnelReport:
    def _build(self, tmp_path, **files):
        """Run build_funnel against a synthetic api/ directory."""
        import importlib

        api = tmp_path / "api"
        api.mkdir(parents=True)
        for name, payload in files.items():
            (api / f"{name}.json").write_text(json.dumps(payload))
        module = importlib.import_module("scripts.build_funnel")
        original = module._API
        module._API = api
        try:
            return module.build()
        finally:
            module._API = original

    def test_a_missing_source_reports_null_not_zero(self, tmp_path):
        data = self._build(tmp_path)
        stages = data["stages"]
        assert stages["click"]["configured"] is False
        assert stages["capture"]["configured"] is False
        assert data["network_rates"]["reach_to_click_pct"] is None

    def test_small_denominators_report_null_rather_than_a_percentage(self):
        from scripts.build_funnel import MIN_DENOMINATOR, _rate

        assert _rate(1, 2) is None
        assert _rate(1, MIN_DENOMINATOR - 1) is None
        assert _rate(15, 30) == 50.0

    def test_unparseable_campaigns_are_counted_not_dropped(self, tmp_path):
        data = self._build(tmp_path, ga4_stats={
            "fetched_at": "2026-07-30T00:00:00Z",
            "days": 30,
            "campaigns": [
                {"sessionSource": "youtube_ru", "sessionMedium": "short",
                 "sessionCampaignName": "nn-spacex-ru-short-ep045",
                 "sessions": 40, "engagedSessions": 30},
                {"sessionSource": "google", "sessionMedium": "organic",
                 "sessionCampaignName": "(organic)",
                 "sessions": 60, "engagedSessions": 10},
            ],
            "landing_pages": [],
        })
        click = data["stages"]["click"]
        assert click["totals"]["sessions"] == 100
        assert click["unattributed"]["sessions"] == 60
        assert click["by_show"]["spacex"]["sessions"] == 40
        # 40 of 100 sessions are ours — the report must say so rather
        # than imply it can see everything.
        assert data["network_rates"]["attribution_coverage_pct"] == 40.0

    def test_variant_sessions_are_split_for_the_ab(self, tmp_path):
        data = self._build(tmp_path, ga4_stats={
            "days": 30,
            "campaigns": [
                {"sessionCampaignName": "nn-spacex-en-short-ep045-grok_video",
                 "sessions": 12, "engagedSessions": 9},
                {"sessionCampaignName": "nn-spacex-en-short-ep045-stills",
                 "sessions": 7, "engagedSessions": 4},
            ],
            "landing_pages": [],
        })
        by_variant = data["stages"]["click"]["by_variant"]
        assert by_variant["grok_video"]["sessions"] == 12
        assert by_variant["stills"]["sessions"] == 7

    def test_the_ru_pilot_appears_with_its_own_stages(self, tmp_path):
        data = self._build(tmp_path, youtube_stats={
            "shows": {"spacex": {"videos": [
                {"show_slug": "spacex", "channel": "ru", "kind": "short",
                 "published": "2999-01-01", "views": 5000,
                 "subscribers_gained": 4},
            ]}},
        })
        pilot = data["pilots"]["spacex-ru"]
        assert pilot["destination"] == "https://nerranetwork.com/ru/spacex.html"
        assert pilot["capture_tag"] == "ru-spacex"
        assert pilot["stages"]["reach_views"] == 5000
