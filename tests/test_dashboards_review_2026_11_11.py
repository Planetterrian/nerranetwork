"""Guards for the Nov 11 2026 dashboard review.

The Tesla dashboard's quarterly series had stopped at 2025 Q1 and the
Starship tracker at IFT-9 while both pages read "Live". Now the curated
files are current, the launch record extends the SpaceX series every night,
Mission Control warns when a curated series falls behind, and the home page's
dashboard cards carry each dashboard's headline numbers from the same reading
the dashboard prints (engine.public_dashboards).
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
from pathlib import Path

from engine import public_dashboards as pd

ROOT = Path(__file__).resolve().parent.parent


def _fetcher():
    spec = importlib.util.spec_from_file_location(
        "fetch_spacex_launches", ROOT / "scripts" / "fetch_spacex_launches.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class TestTeslaCuratedData:
    def test_quarters_have_energy_and_reconcile(self):
        d = json.loads((ROOT / "site/data/tesla_metrics.json").read_text(encoding="utf-8"))
        q = {r["quarter"]: r for r in d["deliveries_quarterly"]}
        annual = {r["year"]: r["vehicles"] for r in d["deliveries_annual"]}
        for year in ("2023", "2024", "2025"):
            assert sum(q[f"{year} Q{i}"]["delivered"] for i in range(1, 5)) == annual[year]
        for r in d["deliveries_quarterly"]:
            assert isinstance(r.get("energy_gwh"), (int, float)), r["quarter"]

    def test_latest_quarter_scoreboard(self):
        lq = pd.tesla_latest_quarter({"deliveries_quarterly": [
            {"quarter": "2025 Q3", "produced": 447450, "delivered": 497099, "energy_gwh": 12.5},
            {"quarter": "2026 Q3", "produced": 464391, "delivered": 486532, "energy_gwh": 13.7},
        ]})
        assert lq["label"] == "Q3 2026"
        assert lq["delivered_yoy_pct"] == -2.1 and lq["energy_yoy_pct"] == 9.6
        assert lq["inventory_change"] == -22141
        assert lq["next_label"] == "Q4 2026"

    def test_missing_year_ago_is_none_never_zero(self):
        lq = pd.tesla_latest_quarter({"deliveries_quarterly": [
            {"quarter": "2026 Q3", "produced": 1, "delivered": 2}]})
        assert lq["delivered_yoy_pct"] is None and lq["energy_yoy_pct"] is None


class TestFreshness:
    def _root(self, tmp_path, quarter="2026 Q3", flights=None, recent=None):
        (tmp_path / "site/data").mkdir(parents=True)
        (tmp_path / "api").mkdir()
        (tmp_path / "site/data/tesla_metrics.json").write_text(json.dumps({
            "deliveries_quarterly": [{"quarter": quarter, "produced": 1, "delivered": 1}],
            "deliveries_annual": [{"year": "2025", "vehicles": 1}]}))
        (tmp_path / "site/data/spacex_metrics.json").write_text(json.dumps({
            "annual_launches": {"years": [{"year": "2025", "launches": 165}]},
            "starship_flights": {"flights": flights or [{"flight": "IFT-14", "date": "2026-09-28"}]}}))
        (tmp_path / "api/spacex_launches.json").write_text(json.dumps({"recent": recent or []}))
        return tmp_path

    def test_current_files_are_clean(self, tmp_path):
        assert pd.curated_freshness(self._root(tmp_path), dt.date(2026, 11, 11)) == []

    def test_the_q1_2025_state_is_flagged(self, tmp_path):
        out = pd.curated_freshness(self._root(tmp_path, quarter="2025 Q1"), dt.date(2026, 11, 11))
        assert any("Tesla quarterly" in f["series"] and f["latest"] == "2025 Q1" for f in out)

    def test_a_flight_newer_than_the_tracker_is_flagged(self, tmp_path):
        root = self._root(tmp_path, flights=[{"flight": "IFT-9", "date": "2025-05-27"}],
                          recent=[{"rocket": "Starship", "name": "Starship | Flight 14",
                                   "net": "2026-09-28T13:49:00Z"}])
        out = pd.curated_freshness(root, dt.date(2026, 11, 11))
        assert any("Starship" in f["series"] for f in out)

    def test_mission_control_runs_the_check(self):
        src = (ROOT / "scripts/generate_dashboard.py").read_text(encoding="utf-8")
        assert "item_23_public_dashboard_data(root)" in src


class TestSpaceXFromTheRecord:
    def test_starship_flights_are_appended_never_duplicated(self):
        m = _fetcher()
        curated = {"flights": [{"flight": "IFT-9", "date": "2025-05-27", "outcome": "partial",
                                "milestone": "curated text"}]}
        launches = [
            {"rocket": "Starship", "name": "Starship | Flight 10", "net": "2025-08-26T23:30:00Z",
             "status": "Success", "mission_description": "Tenth flight. More text."},
            {"rocket": "Starship", "name": "Starship | Flight 9", "net": "2025-05-27T23:36:00Z",
             "status": "Partial Failure"},
            {"rocket": "Starship", "name": "Starship | Flight 15", "net": "2026-11-13T00:00:00Z",
             "status": "Go"},
            {"rocket": "Falcon 9", "name": "Falcon 9 | Starlink", "net": "2025-08-27T00:00:00Z",
             "status": "Success"},
        ]
        out = m.merge_starship_record(curated, launches)
        names = [f["flight"] for f in out["flights"]]
        assert names == ["IFT-9", "IFT-10"]
        assert out["flights"][0]["milestone"] == "curated text"
        assert out["flights"][1]["source"] == "launch_record"
        assert out["flights"][1]["milestone"] == "Tenth flight."

    def test_annual_counts_only_years_the_record_reaches(self):
        m = _fetcher()
        now = dt.datetime(2026, 11, 11, tzinfo=dt.timezone.utc)
        launches = ([{"rocket": "Falcon 9", "net": "2024-12-30T00:00:00Z", "status": "Success"}]
                    + [{"rocket": "Falcon 9", "net": f"2025-0{i}-01T00:00:00Z", "status": "Success"}
                       for i in range(1, 4)]
                    + [{"rocket": "Falcon 9", "net": "2026-03-01T00:00:00Z", "status": "Success"},
                       {"rocket": "Starship", "name": "Starship | Flight 12", "orbit": "Suborbital",
                        "net": "2026-05-22T00:00:00Z", "status": "Partial Failure"}])
        out = m.merge_annual_launches({"years": [{"year": "2024", "launches": 134}]}, launches, now)
        years = {y["year"]: y for y in out["years"]}
        assert years["2024"]["launches"] == 134  # a curated year is never rewritten
        assert years["2025"]["launches"] == 3 and not years["2025"].get("ytd")
        assert years["2026"]["launches"] == 1 and years["2026"]["ytd"] is True  # suborbital excluded

    def test_committed_tracker_reaches_flight_14(self):
        d = json.loads((ROOT / "site/data/spacex_metrics.json").read_text(encoding="utf-8"))
        flights = d["starship_flights"]["flights"]
        assert flights[-1]["flight"] == "IFT-14" and flights[-1]["date"] == "2026-09-28"
        years = {y["year"] for y in d["annual_launches"]["years"]}
        assert "2025" in years


class TestHomepageNumbers:
    def test_facts_come_from_the_dashboards_reading(self):
        facts = pd.homepage_facts(ROOT)
        lq = pd.tesla_latest_quarter(json.loads(
            (ROOT / "site/data/tesla_metrics.json").read_text(encoding="utf-8")))
        assert facts["tesla"][0]["value"] == f"{lq['delivered']:,}"
        assert lq["label"] in facts["tesla"][0]["label"]

    def test_mit_headline_is_the_era_record_only(self):
        facts = pd.homepage_facts(ROOT).get("modern_investing") or []
        if facts:
            assert "vs the NASDAQ" in facts[0]["label"]
            assert all("blended" not in f["label"] and "compounded" not in f["label"] for f in facts)

    def test_template_renders_the_stats(self):
        t = (ROOT / "templates/network_page.html.j2").read_text(encoding="utf-8")
        assert "lt-dash-stats" in t and "d.stats" in t
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        assert "_public_dashboards.homepage_facts(ROOT)" in src
        assert '"latest_quarter": _public_dashboards.tesla_latest_quarter(metrics)' in src


class TestMitPagePhoneWidth:
    def test_two_column_row_cannot_overflow(self):
        t = (ROOT / "templates/mit_performance_page.html.j2").read_text(encoding="utf-8")
        assert "grid-template-columns:1fr 1fr" not in t
        assert "repeat(2,minmax(0,1fr))" in t
