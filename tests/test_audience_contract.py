"""Drift guards for the audience contract (api/audience_contract.json).

Mission Control pins to this shape. A silent field rename or a missing
source that becomes ``0`` instead of ``null`` would look like a real
audience collapse. These tests pin the documented v1 contract against
fixture inputs and against the builder's exported key set.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_audience_contract as ac  # noqa: E402


DOCUMENTED_TOP_LEVEL = {
    "schema_version",
    "generated_at",
    "op3",
    "youtube",
    "spotify",
    "apple",
    "site",
    "newsletter",
}

FIXED_NOW = dt.datetime(2026, 10, 28, 16, 0, 0, tzinfo=dt.timezone.utc)


def _full_dashboard() -> dict:
    return {
        "generated_at": "2026-10-27T21:08:00+00:00",
        "network": {"shows_count": 30},
        "audience": {
            "op3": {
                "configured": True,
                "fetched_at": "2026-10-27T21:02:50+00:00",
                "network_downloads_7d": 4093,
                "network_downloads_30d": 15200,
                "unindexed": [
                    "nerra_voices",
                    "offshore_north",
                    "omni_view_north_america",
                ],
            },
            "youtube": {
                "configured": True,
                "generated": "2026-10-27T21:06:02+00:00",
                "channels": {
                    "en": {
                        "subscribers": 540,
                        "subscribers_delta_7d": 10,
                    },
                    "ru": {
                        "subscribers": 257,
                        "subscribers_delta_7d": 8,
                    },
                    "fr": {
                        "subscribers": 79,
                        "subscribers_delta_7d": 6,
                    },
                },
            },
            "spotify": {
                "configured": True,
                "fetched_at": "2026-10-27T21:03:29+00:00",
                "window_days": 30,
                "totals": {"streams": 1429, "listeners": 331},
            },
            "apple": {
                "configured": True,
                "fetched_at": "2026-10-27T21:03:41+00:00",
                "first_date": "2026-07-27",
                "last_date": "2026-10-26",
                "days_retained": 92,
                "shows_reporting": 5,
                "totals": {
                    "plays": 7344,
                    "listeners": 2218,
                    "listening_hours": 333.71,
                },
            },
            "site": {
                "configured": True,
                "fetched_at": "2026-10-27T21:02:57+00:00",
                "days": 28,
                "totals": {"active_users": 766, "sessions": 840},
            },
            "newsletter": {
                "configured": True,
                "fetched_at": "2026-10-27T21:02:50+00:00",
                "subscriber_count": 14,
            },
        },
        "growth": {
            "channel_scorecard": {
                "configured": True,
                "as_of": "2026-10-27T21:06:02+00:00",
                "channels": {
                    "en": {
                        "subscribers": 540,
                        "views_7d": 6407,
                        "subs_net_7d": 10,
                    },
                    "ru": {
                        "subscribers": 257,
                        "views_7d": 8252,
                        "subs_net_7d": 8,
                    },
                    "fr": {
                        "subscribers": 79,
                        "views_7d": 3244,
                        "subs_net_7d": 5,
                    },
                },
            }
        },
    }


def _full_headline() -> dict:
    return {
        "generated_at": "2026-10-27T21:08:01+00:00",
        "sources": {
            "op3_fetched_at": "2026-10-27T21:02:50+00:00",
            "buttondown_fetched_at": "2026-10-27T21:02:50+00:00",
        },
        "network": {
            "downloads_7d": 4093,
            "downloads_30d": 15200,
            "last_week": 3367,
            "prior_week": 4329,
            "wow_pct": -22.2,
            "shows_measured": 28,
            "shows_unindexed": [
                "nerra_voices",
                "offshore_north",
                "omni_view_north_america",
            ],
            "newsletter_subscribers": 14,
        },
    }


class TestAudienceContractShape:
    def test_schema_version_and_generated_at(self):
        doc = ac.build_contract(_full_dashboard(), _full_headline(), now=FIXED_NOW)
        assert doc["schema_version"] == 1
        parsed = dt.datetime.fromisoformat(doc["generated_at"])
        assert parsed == FIXED_NOW

    def test_top_level_keys_match_documented_set(self):
        """Drift guard: a future shape change must fail here, not silently
        break Mission Control."""
        assert set(ac.TOP_LEVEL_KEYS) == DOCUMENTED_TOP_LEVEL
        doc = ac.build_contract(_full_dashboard(), _full_headline(), now=FIXED_NOW)
        assert set(doc.keys()) == DOCUMENTED_TOP_LEVEL

    def test_every_documented_field_present_on_fixture(self):
        doc = ac.build_contract(_full_dashboard(), _full_headline(), now=FIXED_NOW)

        op3 = doc["op3"]
        assert op3["network_downloads_7d"] == 4093
        assert op3["network_downloads_30d"] == 15200
        assert op3["last_week"] == 3367
        assert op3["prior_week"] == 4329
        assert op3["wow_pct"] == -22.2
        assert op3["shows_measured"] == 28
        assert op3["fetched_at"] == "2026-10-27T21:02:50+00:00"
        assert op3["unindexed_shows"] == [
            "nerra_voices",
            "offshore_north",
            "omni_view_north_america",
        ]

        yt = doc["youtube"]
        assert yt["network_views_7d"] == 6407 + 8252 + 3244
        assert yt["channels"]["en"]["subscribers"] == 540
        assert yt["channels"]["en"]["subs_net_7d"] == 10
        assert yt["channels"]["en"]["views_7d"] == 6407
        assert yt["channels"]["fr"]["subs_net_7d"] == 5
        assert yt["generated_at"] == "2026-10-27T21:06:02+00:00"

        sp = doc["spotify"]
        assert sp["streams"] == 1429
        assert sp["listeners"] == 331
        assert sp["window_days"] == 30

        ap = doc["apple"]
        assert ap["plays"] == 7344
        assert ap["listeners"] == 2218
        assert ap["listening_hours"] == 333.71
        assert ap["shows_reporting"] == 5
        assert ap["shows_in_network"] == 30
        assert ap["window_start"] == "2026-07-27"
        assert ap["window_end"] == "2026-10-26"
        assert ap["days_retained"] == 92

        site = doc["site"]
        assert site["days"] == 28
        assert site["totals"]["active_users"] == 766
        assert site["totals"]["sessions"] == 840

        assert doc["newsletter"]["subscriber_count"] == 14


class TestAudienceContractHonesty:
    def test_missing_sources_are_null_not_zero(self):
        doc = ac.build_contract({}, {}, now=FIXED_NOW)
        assert doc["schema_version"] == 1
        for key in ("op3", "youtube", "spotify", "apple", "site", "newsletter"):
            assert doc[key] is None, f"{key} must be null when unmeasured, not 0"

    def test_unconfigured_audience_blocks_are_null(self):
        dashboard = {
            "network": {"shows_count": 30},
            "audience": {
                "op3": {"configured": False},
                "youtube": {"configured": False},
                "spotify": {"configured": False},
                "apple": {"configured": False},
                "site": {"configured": False},
                "newsletter": {"configured": False},
            },
        }
        doc = ac.build_contract(dashboard, {}, now=FIXED_NOW)
        assert doc["spotify"] is None
        assert doc["apple"] is None
        assert doc["site"] is None
        assert doc["newsletter"] is None
        assert doc["youtube"] is None

    def test_partial_op3_does_not_invent_wow_zeros(self):
        dashboard = {
            "audience": {
                "op3": {
                    "configured": True,
                    "fetched_at": "t",
                    "network_downloads_7d": 100,
                    "network_downloads_30d": 400,
                    "unindexed": [],
                }
            }
        }
        # Headline missing → WoW fields null, not 0.
        doc = ac.build_contract(dashboard, {}, now=FIXED_NOW)
        op3 = doc["op3"]
        assert op3["network_downloads_7d"] == 100
        assert op3["last_week"] is None
        assert op3["prior_week"] is None
        assert op3["wow_pct"] is None
        assert op3["shows_measured"] is None
        assert op3["unindexed_shows"] == []

    def test_unindexed_shows_carried_as_list(self):
        doc = ac.build_contract(_full_dashboard(), _full_headline(), now=FIXED_NOW)
        assert isinstance(doc["op3"]["unindexed_shows"], list)
        assert "nerra_voices" in doc["op3"]["unindexed_shows"]

        # Headline-only fallback still carries the list.
        headline_only = ac.build_contract(
            {},
            {
                "network": {
                    "shows_unindexed": ["offshore_north"],
                    "shows_measured": 1,
                    "last_week": 10,
                    "prior_week": 5,
                    "wow_pct": 100.0,
                }
            },
            now=FIXED_NOW,
        )
        assert headline_only["op3"]["unindexed_shows"] == ["offshore_north"]

    def test_apple_totals_carry_retained_window_not_weekly(self):
        """Apple totals are cumulative over days_retained — the window
        fields must sit beside the totals so a consumer cannot mistake
        plays for a weekly figure."""
        doc = ac.build_contract(_full_dashboard(), _full_headline(), now=FIXED_NOW)
        ap = doc["apple"]
        assert ap["days_retained"] == 92
        assert ap["window_start"] and ap["window_end"]
        assert ap["shows_reporting"] == 5
        assert ap["shows_in_network"] == 30
        # No weekly Apple field exists on the contract.
        assert "plays_7d" not in ap
        assert "weekly_plays" not in ap


class TestAudienceContractCli:
    def test_main_writes_out(self, tmp_path: Path):
        api = tmp_path / "api"
        api.mkdir()
        (api / "dashboard.json").write_text(
            json.dumps(_full_dashboard()), encoding="utf-8"
        )
        (api / "audience_headline.json").write_text(
            json.dumps(_full_headline()), encoding="utf-8"
        )
        out = tmp_path / "audience_contract.json"
        rc = ac.main(["--root", str(tmp_path), "--out", str(out)])
        assert rc == 0
        doc = json.loads(out.read_text(encoding="utf-8"))
        assert doc["schema_version"] == 1
        assert set(doc.keys()) == DOCUMENTED_TOP_LEVEL
        assert doc["op3"]["network_downloads_7d"] == 4093

    def test_nightly_wires_builder_after_dashboard(self):
        wf = (ROOT / ".github/workflows/nightly-maintenance.yml").read_text(
            encoding="utf-8"
        )
        assert "python scripts/build_audience_contract.py" in wf
        assert wf.index("scripts/generate_dashboard.py --out") < wf.index(
            "scripts/build_audience_contract.py"
        )
        assert "            api/audience_contract.json\n" in wf
