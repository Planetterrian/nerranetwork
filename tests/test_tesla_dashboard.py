"""Drift guards for the Tesla data dashboard + SpaceX real-Starlink count
(June 13 2026 dashboard expansion)."""
from __future__ import annotations
import json, sys
from pathlib import Path
import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


class TestTeslaMetricsDataset:
    def test_dataset_valid_and_populated(self):
        d = json.loads((_ROOT / "site/data/tesla_metrics.json").read_text(encoding="utf-8"))
        assert d["deliveries_annual"] and d["energy_storage_annual_gwh"]
        for row in d["deliveries_annual"]:
            assert "year" in row and isinstance(row["vehicles"], int)
        for row in d["energy_storage_annual_gwh"]:
            assert "year" in row and isinstance(row["gwh"], (int, float))

    def test_quarterly_deliveries_reconcile_to_annual(self):
        d = json.loads((_ROOT / "site/data/tesla_metrics.json").read_text(encoding="utf-8"))
        q = d.get("deliveries_quarterly") or []
        assert len(q) >= 8, "quarterly P&D series should be seeded"
        for row in q:
            assert isinstance(row["produced"], int) and isinstance(row["delivered"], int)
            assert "Q" in row["quarter"]
        # The curated quarterly delivered totals must sum to the annual figures
        # (the integrity check that keeps the dataset honest).
        annual = {r["year"]: r["vehicles"] for r in d["deliveries_annual"]}
        from collections import defaultdict
        by_year = defaultdict(int)
        for row in q:
            by_year[row["quarter"].split()[0]] += row["delivered"]
        for yr in ("2023", "2024"):
            full = [k for k in by_year if k == yr]
            if full and yr in annual:
                assert by_year[yr] == annual[yr], f"{yr}: {by_year[yr]} != {annual[yr]}"

    def test_supercharger_series_monotonic(self):
        d = json.loads((_ROOT / "site/data/tesla_metrics.json").read_text(encoding="utf-8"))
        sc = d.get("supercharger_connectors_annual") or []
        assert len(sc) >= 5
        vals = [r["connectors"] for r in sc]
        assert all(isinstance(v, int) for v in vals)
        # The network only grows — a decreasing year signals a data-entry error.
        assert vals == sorted(vals), "connector counts should be non-decreasing"


class TestTeslaFetcher:
    def _mod(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "fetch_tesla_dashboard", _ROOT / "scripts" / "fetch_tesla_dashboard.py")
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        return m

    def test_helpers(self):
        m = self._mod()
        assert m._f(1.23456) == 1.23
        assert m._f(None) is None
        assert m._i("5") == 5
        assert m._i(None) is None
        # sanity band constants present
        assert m._PRICE_MIN < m._PRICE_MAX


class TestTeslaDashboardPage:
    def test_template_and_generator(self):
        import generate_html as g
        g.generate_tesla_dashboard(dry_run=True)  # smoke, no exception
        t = (_ROOT / "templates/tesla_dashboard.html.j2").read_text(encoding="utf-8")
        for needle in ('id="tslArea"', 'id="tslDeliveries"', 'id="tslEnergy"',
                       'id="tslPrice"', "function renderArea", "function countUp",
                       'id="tslQuarterly"', "tsl-qbar", "deliveries_quarterly",
                       'id="tslSupercharger"', "supercharger_connectors_annual"):
            assert needle in t, needle

    def test_show_page_links_dashboard(self):
        sp = (_ROOT / "templates/show_page.html.j2").read_text(encoding="utf-8")
        assert "tesla-dashboard.html" in sp
        assert "Tesla Dashboard" in sp

    def test_in_sitemap_list(self):
        gh = (_ROOT / "generate_html.py").read_text(encoding="utf-8")
        assert '"tesla-dashboard.html"' in gh


class TestSpacexStarlinkCount:
    def _mod(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "fetch_spacex_launches", _ROOT / "scripts" / "fetch_spacex_launches.py")
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        return m

    def test_starlink_count_function_exists(self):
        m = self._mod()
        assert hasattr(m, "_starlink_active_count")
        # dashboard shows the live active count
        dash = (_ROOT / "templates/spacex_dashboard.html.j2").read_text(encoding="utf-8")
        assert "flStarlinkActive" in dash and "Active Starlink" in dash

    def test_satellite_counts_single_fetch_derives_both(self, monkeypatch):
        m = self._mod()
        # One catalogue download yields total + the Starlink subset.
        fake = [{"OBJECT_NAME": "STARLINK-1"}, {"OBJECT_NAME": "STARLINK-2"},
                {"OBJECT_NAME": "ISS (ZARYA)"}, {"OBJECT_NAME": "ONEWEB-9"}] * 2000
        import io, json as _json

        class _Resp(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): return False
        monkeypatch.setattr(m.urllib.request, "urlopen",
                            lambda *a, **k: _Resp(_json.dumps(fake).encode()))
        c = m._satellite_counts()
        assert c["total"] == 8000 and c["starlink"] == 4000
        assert m._starlink_active_count() == 4000  # back-compat wrapper

    def test_satellite_counts_rejects_junk(self, monkeypatch):
        m = self._mod()
        import io, json as _json

        class _Resp(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): return False
        monkeypatch.setattr(m.urllib.request, "urlopen",
                            lambda *a, **k: _Resp(_json.dumps([]).encode()))
        c = m._satellite_counts()  # empty list → below sanity band
        assert c["total"] is None and c["starlink"] is None

    def test_aged_out_month_does_not_overwrite_locked_value(self, tmp_path):
        # As the date advances the oldest month ages out of the LL2 window and
        # returns 0 launches — that zero must NOT clobber a locked non-zero month.
        m = self._mod()
        import json as _json, datetime as dt
        p = tmp_path / "spacex_metrics.json"
        p.write_text(_json.dumps({"months": {"2025-07": {
            "launches": 13, "mass_t": 181, "satellites": 184, "vehicles": {"Falcon 9": 13}}}}))
        # New breakdown reports 2025-07 with 0 (aged out) + a fresh real month.
        monthly = [
            {"month": "2025-07", "launches": 0, "mass_t": 0, "satellites": 0, "vehicles": {}},
            {"month": "2026-06", "launches": 6, "mass_t": 90, "satellites": 130, "vehicles": {"Falcon 9": 6}},
        ]
        m._update_metrics_timeseries(monthly, dt.datetime(2026, 6, 14, tzinfo=dt.timezone.utc), path=p)
        saved = _json.loads(p.read_text())["months"]
        assert saved["2025-07"]["launches"] == 13  # locked value preserved
        assert saved["2026-06"]["launches"] == 6   # fresh month written

    def test_dashboard_shows_active_satellite_share(self):
        dash = (_ROOT / "templates/spacex_dashboard.html.j2").read_text(encoding="utf-8")
        assert "flActiveSats" in dash and "flStarlinkOfActive" in dash
        assert "total_active_satellites" in dash
        # build_payload sets the new field + keep-last-good covers it.
        m = self._mod()
        import inspect
        assert 'fleet["total_active_satellites"]' in inspect.getsource(m.build_payload)
        assert "total_active_satellites" in inspect.getsource(m.main)


class TestMitPerformanceCharts:
    def test_chart_data_is_finite_safe(self):
        import generate_html as g
        # NaN P&L (the yfinance-NaN class) must never reach the baked JSON.
        tracker = {
            "summary": {"wins": 2, "losses": 1, "breakeven": 0, "cumulative_pnl": 50.0,
                        "best_trade_pct": float("nan"), "win_rate_pct": 66.6,
                        "longest_win_streak": 2, "worst_trade_pct": -5.0},
            "sectors": {"tech": {"trade_count": 2, "cumulative_pnl": float("inf")},
                        "consumer": {"trade_count": 1, "cumulative_pnl": 9.0}},
            "trades": [
                {"date": "2026-01-01", "symbol": "A", "pnl_pct": 3.0, "strategy": "x"},
                {"date": "2026-01-02", "symbol": "B", "pnl_pct": float("nan"), "strategy": "y"},
                {"date": "2026-01-03", "symbol": "C", "pnl_pct": -1.0, "strategy": "z"},
            ],
        }
        c = g._mit_chart_data(tracker)
        import json, math
        blob = json.dumps(c)  # default allow_nan=True would still emit NaN; assert none
        assert "NaN" not in blob and "Infinity" not in blob
        # NaN trade dropped from the curve (2 finite trades remain)
        assert len(c["equity_curve"]) == 2
        assert c["headline"]["best"] is None  # NaN coerced to None
        # Monthly P&L buckets the same finite trades; NaN excluded, no NaN leak.
        mp = c["monthly_pnl"]
        assert mp == [{"month": "2026-01", "pnl": 2.0}]  # 3.0 + (-1.0), NaN dropped

    def test_mit_template_has_charts(self):
        t = (_ROOT / "templates/mit_performance_page.html.j2").read_text(encoding="utf-8")
        for needle in ('id="mitEquity"', 'id="mitSectors"', 'id="mitWL"', "mit-chart-data",
                       "Cumulative return", "Simulated P&amp;L",
                       'id="mitMonthly"', "Monthly P&amp;L", "D.monthly_pnl"):
            assert needle in t, needle


class TestPadBreakdown:
    def _mod(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "fetch_spacex_launches", _ROOT / "scripts" / "fetch_spacex_launches.py")
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        return m

    def test_pad_label_friendly_names(self):
        m = self._mod()
        assert m._pad_label("Space Launch Complex 40", "Cape Canaveral SFS") == "Cape Canaveral SLC-40"
        assert m._pad_label("Launch Complex 39A", "Kennedy Space Center") == "Kennedy LC-39A"
        assert m._pad_label("Space Launch Complex 4E", "Vandenberg SFB") == "Vandenberg SLC-4E"
        assert m._pad_label("Orbital Launch Mount A", "SpaceX Starbase") == "Starbase, TX"
        # Unknown pad falls back to its raw name, never crashes.
        assert m._pad_label(None, "Somewhere") == "Somewhere"

    def test_pad_breakdown_counts_and_sorts(self):
        import datetime as dt
        m = self._mod()
        now = dt.datetime(2026, 6, 14, tzinfo=dt.timezone.utc)
        prev = [
            {"net": "2026-06-01T00:00:00Z", "pad": "Space Launch Complex 40", "location": "Cape"},
            {"net": "2026-05-01T00:00:00Z", "pad": "Space Launch Complex 40", "location": "Cape"},
            {"net": "2026-04-01T00:00:00Z", "pad": "Space Launch Complex 4E", "location": "Vandenberg"},
            {"net": "2020-01-01T00:00:00Z", "pad": "Launch Complex 39A", "location": "KSC"},  # >365d, excluded
        ]
        out = m._pad_breakdown(prev, now)
        assert out[0] == {"site": "Cape Canaveral SLC-40", "count": 2}  # most, sorted first
        sites = {r["site"]: r["count"] for r in out}
        assert sites.get("Vandenberg SLC-4E") == 1
        assert "Kennedy LC-39A" not in sites  # outside the 365d window

    def test_dashboard_renders_pads_and_hub_link(self):
        m = self._mod()
        import inspect
        assert '"pads": _pad_breakdown(slim_prev, now)' in inspect.getsource(m.build_payload)
        t = (_ROOT / "templates/spacex_dashboard.html.j2").read_text(encoding="utf-8")
        assert 'id="spxPads"' in t and "renderPads" in t and "data.pads" in t
        assert 'data.html' in t  # back-link to the hub


class TestDashboardHubBackLinks:
    def test_each_dashboard_links_to_hub(self):
        for tpl in ("spacex_dashboard.html.j2", "tesla_dashboard.html.j2",
                    "mit_performance_page.html.j2"):
            t = (_ROOT / "templates" / tpl).read_text(encoding="utf-8")
            assert "data.html" in t, tpl


class TestDataHubPage:
    def test_generator_and_links(self):
        import generate_html as g
        g.generate_data_hub_page(dry_run=True)  # smoke, no exception
        t = (_ROOT / "templates/data_hub.html.j2").read_text(encoding="utf-8")
        for href in ("spacex-dashboard.html", "tesla-dashboard.html",
                     "modern-investing-performance.html", "gallery.html"):
            assert href in t, href

    def test_wired_into_build_and_sitemap_and_footer(self):
        gh = (_ROOT / "generate_html.py").read_text(encoding="utf-8")
        # rendered in both --all and --network, and listed in the sitemap
        assert gh.count("generate_data_hub_page(dry_run=args.dry_run)") >= 2
        assert '"data.html"' in gh
        base = (_ROOT / "templates/base.html.j2").read_text(encoding="utf-8")
        assert "data.html" in base  # footer discovery link on every page


class TestWatchLinksAndRangeBar:
    def test_spacex_dashboard_has_watch_links(self):
        t = (_ROOT / "templates/spacex_dashboard.html.j2").read_text(encoding="utf-8")
        # per-upcoming watch link + official-stream how-to-watch note
        assert "spx-watch" in t
        assert "Watch live on" in t and "x.com/SpaceX" in t and "youtube.com/@SpaceX" in t
        assert "Where to watch" in t  # hero fallback when no webcast yet

    def test_tesla_dashboard_has_range_bar(self):
        t = (_ROOT / "templates/tesla_dashboard.html.j2").read_text(encoding="utf-8")
        assert "tslRangeWrap" in t and "52-week range" in t
        assert "tslRangeMarker" in t


class TestBoosterReuseStats:
    def _mod(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "fetch_spacex_launches", _ROOT / "scripts" / "fetch_spacex_launches.py")
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        return m

    def test_booster_stats_from_detailed_records(self):
        m = self._mod()
        raw = [
            {"rocket": {"launcher_stage": [{"launcher": {"serial_number": "B1067", "flights": 35},
                                            "launcher_flight_number": 35, "landing": {"success": True}}]}},
            {"rocket": {"launcher_stage": [{"launcher": {"serial_number": "B1071", "flights": 34},
                                            "launcher_flight_number": 34, "landing": {"success": True}}]}},
            {"rocket": {"launcher_stage": [{"launcher": {"serial_number": "B1067", "flights": 33},
                                            "launcher_flight_number": 33, "landing": {"success": False}}]}},
        ]
        b = m._booster_stats(raw)
        assert b["most_flown"] == {"serial": "B1067", "flights": 35}
        assert b["fleet_leaders"][0]["serial"] == "B1067"
        assert b["active_boosters_window"] == 2
        assert b["landing_success_pct"] == 66.7  # 2 of 3

    def test_slim_launch_extracts_booster(self):
        m = self._mod()
        s = m._slim_launch({"name": "X", "rocket": {"launcher_stage": [
            {"launcher": {"serial_number": "B1093"}, "launcher_flight_number": 14}]}})
        assert s["booster"] == {"serial": "B1093", "flight_number": 14}

    def test_dashboard_has_booster_panel(self):
        t = (_ROOT / "templates/spacex_dashboard.html.j2").read_text(encoding="utf-8")
        assert "record watch" in t and "brRecordN" in t and "brLeaders" in t
        assert "spxBooster" in t  # per-launch booster line on the hero


class TestStarshipTracker:
    def _mod(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "fetch_spacex_launches", _ROOT / "scripts" / "fetch_spacex_launches.py")
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        return m

    def test_metrics_has_curated_starship_record(self):
        data = json.loads((_ROOT / "site/data/spacex_metrics.json").read_text(encoding="utf-8"))
        sf = data.get("starship_flights") or {}
        flights = sf.get("flights") or []
        assert len(flights) >= 9, "Starship IFT record should be seeded"
        # Schema + value sanity on every curated entry.
        valid_outcomes = {"success", "partial", "failure"}
        seen = set()
        for f in flights:
            assert f.get("flight") and f.get("date") and f.get("milestone")
            assert f["outcome"] in valid_outcomes, f["outcome"]
            assert f["flight"] not in seen, f"duplicate {f['flight']}"
            seen.add(f["flight"])
        # The three confirmed tower catches carry the explicit, non-prose flag.
        caught = {f["flight"] for f in flights if f.get("booster_caught") is True}
        assert {"IFT-5", "IFT-7", "IFT-8"}.issubset(caught), caught

    def test_fetcher_reads_and_preserves_starship(self):
        m = self._mod()
        sf = m._starship_flights()
        assert isinstance(sf, dict) and len(sf.get("flights", [])) >= 9
        # The fetcher must carry it into the launches payload (so the dashboard
        # — which only fetches api/spacex_launches.json — can read it).
        import inspect
        src = inspect.getsource(m.build_payload)
        assert '"starship": _starship_flights()' in src
        # And the metrics-rewrite must preserve it across runs (not wipe it).
        rewrite = inspect.getsource(m._update_metrics_timeseries)
        assert 'existing.get("starship_flights"' in rewrite

    def test_main_keeps_last_good_starlink_count(self):
        # A transient CelesTrak rate-limit (None) must not wipe a real count.
        m = self._mod()
        import inspect
        src = inspect.getsource(m.main)
        # keep-last-good loop covers both CelesTrak-derived counts
        assert '"starlink_active"' in src and "is None" in src
        assert "Kept last-good" in src

    def test_dashboard_has_starship_panel(self):
        t = (_ROOT / "templates/spacex_dashboard.html.j2").read_text(encoding="utf-8")
        assert "Starship flight-test tracker" in t
        assert "ssTimeline" in t and "renderStarship" in t
        assert "data.starship" in t  # wired into applyLaunches
        # Catch count must be the deterministic flag, not prose-matching.
        assert "f.booster_caught===true" in t

    def test_annual_launches_growth_series(self):
        data = json.loads((_ROOT / "site/data/spacex_metrics.json").read_text(encoding="utf-8"))
        al = data.get("annual_launches") or {}
        years = al.get("years") or []
        assert len(years) >= 5
        for y in years:
            assert y.get("year") and isinstance(y["launches"], int)
        # Fetcher reads it + carries it into the payload + preserves across runs.
        m = self._mod()
        assert len(m._annual_launches().get("years", [])) >= 5
        import inspect
        assert '"annual_launches": _annual_launches()' in inspect.getsource(m.build_payload)
        assert 'existing.get("annual_launches"' in inspect.getsource(m._update_metrics_timeseries)
        # Dashboard renders it.
        t = (_ROOT / "templates/spacex_dashboard.html.j2").read_text(encoding="utf-8")
        assert "spxAnnual" in t and "renderAnnual" in t and "data.annual_launches" in t

    def test_grid_uses_minmax_zero_for_mobile_safety(self):
        # minmax(0,1fr) prevents grid items overflowing on narrow viewports.
        t = (_ROOT / "templates/spacex_dashboard.html.j2").read_text(encoding="utf-8")
        assert "minmax(0,1fr)" in t
        assert "grid-template-columns: 1fr 1fr;" not in t  # legacy overflow shape
