"""Drift guards for the Apple Podcasts Connect scalar extractor.

The July 2026 failure this pins: every headline scalar was derived from the
``trends()`` payloads by walking for dicts carrying ``value``/``count``/
``total``. Those payloads put their data in ``content`` as a list of lists
of scalars, so nothing ever matched, every metric returned ``None``, and
the dashboard summed them into a confident ``0`` — while 4,486 real plays
across 14 shows sat in ``overview.showPlayCount.latestValue``, a field the
fetcher retrieved and then threw away.

It went undetected because a parse miss records no ``errors`` entry, so the
"cookies expired" hint could never fire for it, and ``feeds_reporting``
keys off ``plays is not None`` — making a parser bug and a genuine auth
failure look identical.

These tests use the real payload shape, so a future shape change fails here
rather than silently in production.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def fas():
    spec = importlib.util.spec_from_file_location(
        "fetch_apple_stats", ROOT / "scripts" / "fetch_apple_stats.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["fetch_apple_stats"] = mod
    spec.loader.exec_module(mod)
    return mod


def _overview(plays=2041.0, listeners=164.0, engaged=94.0,
              time_listened=445323.0, followers=23.0):
    """The real shape, as returned by Connect for Tesla on 2026-07-25."""
    ov = {
        "content": {"1855142939": {"id": "1855142939", "name": "Tesla Shorts Time"}},
        "showPlayCount": {"latestValue": {
            "followstate": "*",
            "playscount": plays,
            "podcastid": "1855142939",
            "totaltimelistened": time_listened,
            "uniqueengagedlistenerscount": engaged,
            "uniquelistenerscount": listeners,
        }},
        "followerCount": {},
        "showPlayCountTrends": [[20260701.0, 45.0, 29.0, 567.0]],
        "followerGrowthTrends": [[20260701.0, 0.0, 0.0]],
    }
    if followers is not None:
        ov["followerAllTimeTrends"] = [[20260701.0, followers, 5.0]]
    else:
        ov["followerAllTimeTrends"] = []
    return ov


class TestOverviewScalars:
    def test_reads_the_headline_metrics(self, fas):
        s = fas._overview_scalars(_overview())
        assert s["plays"] == 2041
        assert s["listeners"] == 164
        assert s["engaged_listeners"] == 94
        assert s["time_listened"] == 445323
        assert s["followers"] == 23

    def test_missing_metric_is_absent_not_zero(self, fas):
        """A false zero is worse than a gap — the dashboard renders an
        absent metric as '—' but treats 0 as a real measurement."""
        ov = _overview()
        del ov["showPlayCount"]["latestValue"]["uniquelistenerscount"]
        s = fas._overview_scalars(ov)
        assert "listeners" not in s
        assert s["plays"] == 2041

    def test_empty_follower_trends_is_not_zero_followers(self, fas):
        s = fas._overview_scalars(_overview(followers=None))
        assert "followers" not in s

    def test_garbage_overview_degrades_quietly(self, fas):
        for bad in (None, [], "nope", {}, {"showPlayCount": None}):
            assert fas._overview_scalars(bad) == {}

    def test_booleans_are_not_counted_as_numbers(self, fas):
        ov = _overview()
        ov["showPlayCount"]["latestValue"]["playscount"] = True
        assert "plays" not in fas._overview_scalars(ov)


class TestTrendsFallbackNoLongerOwnsTheHeadline:
    def test_the_real_trends_shape_yields_nothing(self, fas):
        """This is the exact payload that produced the silent zero: content
        is a list of lists of scalars, so the dict-walking extractor finds
        no keys. Pinned so nobody restores it as the primary source."""
        real = {
            "measure": "PLAYS",
            "dimension": "BY_COUNTRY",
            "content": [["1000778313593", "Ep 552: ...", "2026-07-25", -1.0, 1.0]],
        }
        assert fas._totals_from_trends(real) is None

    def test_overview_wins_over_trends(self, fas):
        """Even when a trends payload happens to parse, the overview is
        authoritative — it is what Connect's own dashboard renders."""
        s = fas._overview_scalars(_overview(plays=2041.0))
        assert s["plays"] == 2041
        assert fas._totals_from_trends({"value": 7}) == 7  # fallback still works


class TestAgainstTheLiveFile:
    """Runs against the committed api/apple_stats.json — the file that was
    on disk while the dashboard displayed zero."""

    def test_live_payload_yields_real_numbers(self, fas):
        import json

        path = ROOT / "api" / "apple_stats.json"
        if not path.exists():
            pytest.skip("no apple_stats.json committed")
        data = json.loads(path.read_text(encoding="utf-8"))
        shows = data.get("shows") or {}
        if not shows:
            pytest.skip("apple_stats.json has no shows")

        total = sum(fas._overview_scalars(v.get("overview")).get("plays", 0)
                    for v in shows.values())
        reporting = sum(
            1 for v in shows.values()
            if fas._overview_scalars(v.get("overview")).get("plays"))

        # The whole point: this file is not empty, and never was.
        assert total > 0, "extractor found no plays in a file that has them"
        assert reporting >= 1
