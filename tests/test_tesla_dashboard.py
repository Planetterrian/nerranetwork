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
                       'id="tslPrice"', "function renderArea", "function countUp"):
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
