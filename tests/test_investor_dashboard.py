"""Drift guards for the industry-benchmarks + investor dashboard sections
(Aug 2026).

The dashboard now compares the network against published industry
figures and renders an investor view with value scenarios. Under guard:

* ``docs/industry_benchmarks.yaml`` — the ONE place external market
  numbers live; schema pinned so the generator can rely on it.
* ``build_benchmarks_section`` — percentile placement, feed-based
  episode counting (credit files include dub tracks and must not be the
  denominator), WoW-median pairing, null-honesty.
* ``build_investor_section`` — asset inventory + now/1y/5y scenarios
  with serialized assumptions; scenarios never render without a
  measured download base.
* ``management.html`` — three-view switch + the new sections' wiring.
"""
from __future__ import annotations

import datetime as _dt
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "generate_dashboard_test", PROJECT_ROOT / "scripts" / "generate_dashboard.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["generate_dashboard_test"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gd():
    return _load_generator()


# ---------------------------------------------------------------------------
# Benchmarks file schema
# ---------------------------------------------------------------------------

class TestBenchmarksFile:
    def test_schema(self):
        data = yaml.safe_load(
            (PROJECT_ROOT / "docs" / "industry_benchmarks.yaml").read_text(
                encoding="utf-8"))
        assert data.get("as_of"), "benchmarks need an as_of date"
        assert data.get("sources"), "benchmarks must cite sources"
        ladder = data["podcast_episode_downloads_7d_percentiles"]
        # The ladder must be strictly increasing — a mis-edit here would
        # silently misplace every show.
        rungs = [ladder["median"], ladder["top_25pct"], ladder["top_10pct"],
                 ladder["top_5pct"], ladder["top_1pct"]]
        assert rungs == sorted(rungs) and len(set(rungs)) == 5
        for key in ("podcast_cpm_usd", "production_cost_per_episode_usd",
                    "valuation", "industry_structure", "youtube"):
            assert key in data, key
        for name, rng in data["podcast_cpm_usd"].items():
            assert len(rng) == 2 and rng[0] < rng[1], name


# ---------------------------------------------------------------------------
# Percentile mapping + WoW median
# ---------------------------------------------------------------------------

class TestBenchmarksSection:
    LADDER = {"median": 28, "top_25pct": 119, "top_10pct": 434,
              "top_5pct": 1029, "top_1pct": 4615}

    def test_percentile_band_mapping(self, gd):
        f = gd._percentile_band
        assert f(10, self.LADDER) == "below median"
        assert f(28, self.LADDER) == "top 50%"
        assert f(120, self.LADDER) == "top 25%"
        assert f(500, self.LADDER) == "top 10%"
        assert f(2000, self.LADDER) == "top 5%"
        assert f(9999, self.LADDER) == "top 1%"

    def test_wow_median_short_history_not_zero(self, gd, tmp_path, monkeypatch):
        """Regression: with <9 weeks of history the old slice logic paired
        each week with itself and reported 0% growth."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "industry_benchmarks.yaml").write_text(
            (PROJECT_ROOT / "docs" / "industry_benchmarks.yaml").read_text(
                encoding="utf-8"), encoding="utf-8")
        audience = {"op3": {
            "configured": True,
            "network_downloads_7d": 700,
            "network_downloads_30d": 2800,
            "per_show": {},
            "network_weekly_history": [
                ["2026-07-06", 500], ["2026-07-13", 550],
                ["2026-07-20", 605], ["2026-07-27", 700],
            ],
        }, "youtube": {}}
        out = gd.build_benchmarks_section(
            tmp_path, audience=audience, costs={}, network={"shows": []})
        wow = out["network"]["wow_growth_median_pct"]
        assert wow is not None and wow == pytest.approx(10.0, abs=0.5)

    def test_unconfigured_without_file(self, gd, tmp_path):
        out = gd.build_benchmarks_section(
            tmp_path, audience={}, costs={}, network={})
        assert out == {"configured": False}

    def test_feed_episode_denominator(self, gd, tmp_path):
        """Episodes come from RSS pubDates, not credit files."""
        now = _dt.datetime.now(_dt.timezone.utc)
        recent = (now - _dt.timedelta(days=2)).strftime(
            "%a, %d %b %Y %H:%M:%S +0000")
        old = (now - _dt.timedelta(days=30)).strftime(
            "%a, %d %b %Y %H:%M:%S +0000")
        (tmp_path / "feed.rss").write_text(
            f"<rss><channel><item><pubDate>{recent}</pubDate></item>"
            f"<item><pubDate>{recent}</pubDate></item>"
            f"<item><pubDate>{old}</pubDate></item></channel></rss>",
            encoding="utf-8")
        counts = gd._feed_episodes_last_7d(
            tmp_path, {"shows": [{"slug": "x", "rss_file": "feed.rss"}]})
        assert counts == {"x": 2}

    def test_monetization_null_without_op3(self, gd, tmp_path):
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "industry_benchmarks.yaml").write_text(
            (PROJECT_ROOT / "docs" / "industry_benchmarks.yaml").read_text(
                encoding="utf-8"), encoding="utf-8")
        out = gd.build_benchmarks_section(
            tmp_path, audience={"op3": {"configured": False}, "youtube": {}},
            costs={}, network={"shows": []})
        mc = out["monetization_capacity"]
        assert mc["monthly_downloads"] is None
        assert mc["podcast_ads_annual_usd"] is None


# ---------------------------------------------------------------------------
# Investor section
# ---------------------------------------------------------------------------

class TestInvestorSection:
    def _fixture_root(self, tmp_path):
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "industry_benchmarks.yaml").write_text(
            (PROJECT_ROOT / "docs" / "industry_benchmarks.yaml").read_text(
                encoding="utf-8"), encoding="utf-8")
        return tmp_path

    def _audience(self):
        return {
            "op3": {"configured": True, "network_downloads_30d": 4000,
                    "network_downloads_7d": 1000, "per_show": {},
                    "network_weekly_history": []},
            "youtube": {"configured": True, "channels": {
                "en": {"subscribers": 100, "total_views": 50000}}},
            "newsletter": {"configured": True, "subscriber_count": 5},
        }

    def test_scenarios_shape(self, gd, tmp_path):
        root = self._fixture_root(tmp_path)
        bm = gd.build_benchmarks_section(
            root, audience=self._audience(),
            costs={"network_last_7_days": {"total": 30.0}},
            network={"shows": []})
        inv = gd.build_investor_section(
            root, audience=self._audience(),
            costs={"network_last_7_days": {"total": 30.0}},
            catalog={"network_episodes_to_date": 1000, "shows_count": 16},
            lake={"stats": {"total_words": 900000}},
            gallery={"image_count": 4000},
            network={"shows": []}, benchmarks=bm)
        assert inv["configured"] is True
        sc = inv["scenarios"]
        assert sc["configured"] is True
        names = [r["name"] for r in sc["rows"]]
        assert names == ["hold", "base", "upside"]
        for r in sc["rows"]:
            # hold never grows; growth is monotone across scenarios.
            assert r["downloads_month"]["y5"] >= r["downloads_month"]["now"]
            for k in ("now", "y1", "y5"):
                lo, hi = r["implied_ev_usd"][k]
                assert 0 <= lo <= hi
        assert sc["rows"][0]["downloads_month"]["y5"] == \
            sc["rows"][0]["downloads_month"]["now"]
        # Assumptions must ship WITH the numbers — scenarios without
        # their assumptions are how dishonest decks are made.
        assert len(sc["assumptions"]) >= 4
        assert any("not forecasts" in a for a in sc["assumptions"])

    def test_scenarios_need_measured_base(self, gd, tmp_path):
        root = self._fixture_root(tmp_path)
        audience = {"op3": {"configured": False}, "youtube": {},
                    "newsletter": {}}
        bm = gd.build_benchmarks_section(
            root, audience=audience, costs={}, network={"shows": []})
        inv = gd.build_investor_section(
            root, audience=audience, costs={},
            catalog={"network_episodes_to_date": 100, "shows_count": 16},
            lake={}, gallery={}, network={"shows": []}, benchmarks=bm)
        assert inv["scenarios"]["configured"] is False

    def test_asset_inventory_labels(self, gd, tmp_path):
        root = self._fixture_root(tmp_path)
        bm = gd.build_benchmarks_section(
            root, audience=self._audience(), costs={}, network={"shows": []})
        inv = gd.build_investor_section(
            root, audience=self._audience(), costs={},
            catalog={"network_episodes_to_date": 1000, "shows_count": 16},
            lake={}, gallery={}, network={"shows": []}, benchmarks=bm)
        labels = [a["label"] for a in inv["assets"]]
        assert "Content library" in labels
        assert "Production engine" in labels
        lib = next(a for a in inv["assets"] if a["label"] == "Content library")
        assert lib["usd_range"][0] < lib["usd_range"][1]


# ---------------------------------------------------------------------------
# Dashboard JSON + page wiring
# ---------------------------------------------------------------------------

class TestWiring:
    def test_dashboard_json_carries_sections(self):
        d = json.loads((PROJECT_ROOT / "api" / "dashboard.json").read_text(
            encoding="utf-8"))
        assert d.get("benchmarks", {}).get("configured") is True
        assert d.get("investor", {}).get("configured") is True

    def test_management_html_three_views(self):
        src = (PROJECT_ROOT / "management.html").read_text(encoding="utf-8")
        for needle in (
            'id="view-investor"', 'id="benchmarks-grid"', 'id="investor-grid"',
            'id="investor-hero"', "view-investor",
            "data.benchmarks", "data.investor",
            # Honesty labels must survive future edits.
            "scenarios, not forecasts", "ZERO ads",
        ):
            assert needle in src, needle

    def test_sponsor_hides_econ_css(self):
        src = (PROJECT_ROOT / "management.html").read_text(encoding="utf-8")
        assert "body.view-sponsor [data-econ]" in src
        assert "body.view-investor [data-ops]" in src
