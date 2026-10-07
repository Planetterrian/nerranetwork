"""Drift guards for the Oct 7 2026 dashboard review.

Mission Control (management.html, hand-written), scripts/generate_dashboard.py,
the Tesla / SpaceX / Offshore North dashboards and the MIT performance and
resources pages. Every item here was a number or label that read as
something the data does not say:

* the sponsor view compared the current PARTIAL OP3 week ("+62%") beside
  the tile's last-complete-week "+7.8% WoW";
* episodes/week came from credit files (dub tracks included: 176) while
  the investor view counted RSS pubDates (144); a typed "5 languages"
  sat beside a computed 4;
* an alert object printed "[object Object]";
* a show with UNTRACKED spend ranked cheapest at "$0.000 per download";
* the MIT sector table printed 0% win rate / +0.00% alpha in green for
  fields its data never carried;
* the Offshore North calendar said Canada Ocean Racing was "on the list"
  against the Oct 4 "aiming to start" rule;
* curated blocks on "Live" dashboards carried no date.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MC = ROOT / "management.html"


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "generate_dashboard_review_1007", ROOT / "scripts" / "generate_dashboard.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["generate_dashboard_review_1007"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gd():
    return _load_generator()


def _mc() -> str:
    return MC.read_text(encoding="utf-8")


def _strip_js_comments(src: str) -> str:
    """Drop whole-line // comments so prose describing a bug cannot
    satisfy (or trip) a source assertion. (Block comments are left alone:
    the page's prose carries globs like digests/**/*_claims.json.)"""
    return re.sub(r"(?m)^\s*//.*$", "", src)


def _jinja_env():
    import generate_html as g
    return g._get_jinja_env()


# ---------------------------------------------------------------------------
# Generator: null is never 0, languages are counted
# ---------------------------------------------------------------------------

class TestUntrackedSpendIsNull:
    def _audience(self):
        return {
            "op3": {"network_downloads_7d": 200, "network_downloads_30d": 800,
                    "per_show": {"age_of_ai": {"downloads_7d": 77},
                                 "tesla": {"downloads_7d": 100}}},
            "youtube": {"per_show": {"tesla": {"views": 1000}}},
            "spotify": {}, "apple": {},
        }

    def test_slug_without_credit_files_has_null_cost(self, gd):
        costs = {
            "network_last_7_days": {"total": 10.0, "episodes": 5},
            "per_show": {
                # Present in the rollup but no credit file in the window —
                # the Voices pipeline writes none.
                "age_of_ai": {"last_7_days": {"total": 0.0, "episodes": 0, "files": 0}},
                "tesla": {"last_7_days": {"total": 4.0, "episodes": 2, "files": 2}},
            },
        }
        eff = gd.build_efficiency_section(costs, self._audience())
        aoai = eff["per_show"]["age_of_ai"]
        assert aoai["cost_7d_usd"] is None
        assert aoai["usd_per_op3_download"] is None
        assert aoai["op3_downloads_7d"] == 77
        assert eff["per_show"]["tesla"]["usd_per_op3_download"] == pytest.approx(0.04)
        assert eff["per_show"]["tesla"]["usd_per_yt_view"] == pytest.approx(0.004)

    def test_slug_absent_from_costs_has_null_cost(self, gd):
        costs = {"network_last_7_days": {"total": 4.0},
                 "per_show": {"tesla": {"last_7_days": {"total": 4.0}}}}
        eff = gd.build_efficiency_section(costs, self._audience())
        assert eff["per_show"]["age_of_ai"]["cost_7d_usd"] is None
        assert eff["per_show"]["age_of_ai"]["usd_per_op3_download"] is None

    def test_ranking_and_cells_render_null_as_dash(self):
        src = _mc()
        assert "spend untracked" in src
        # The ranking sorts null rates last (unchanged contract).
        assert "if (ua == null) return 1;" in src
        # Unit rates print with adaptive precision, never a fixed 3 dp.
        code = _strip_js_comments(src)
        assert ".toFixed(3)) : \"—\"" not in code
        assert "const rateUsd" in code


class TestLanguagesCounted:
    def _root(self, tmp_path):
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "industry_benchmarks.yaml").write_text(
            (ROOT / "docs" / "industry_benchmarks.yaml").read_text(encoding="utf-8"),
            encoding="utf-8")
        return tmp_path

    def test_framing_uses_computed_language_count(self, gd, tmp_path):
        root = self._root(tmp_path)
        audience = {"op3": {"configured": True, "network_downloads_30d": 4000,
                            "network_downloads_7d": 1000, "per_show": {},
                            "network_weekly_history": []},
                    "youtube": {}, "newsletter": {}}
        bm = gd.build_benchmarks_section(root, audience=audience, costs={},
                                         network={"shows": []})
        ml = {"per_show": {"tesla": {"languages": ["fr", "ru"]},
                           "spacex": {"languages": ["fr", "zh"]}}}
        inv = gd.build_investor_section(
            root, audience=audience, costs={},
            catalog={"network_episodes_to_date": 10, "shows_count": 3},
            lake={}, gallery={}, network={"shows": []}, benchmarks=bm,
            multilingual=ml)
        assert inv["thesis"]["languages"] == 4
        engine = next(a for a in inv["assets"] if a["label"] == "Production engine")
        assert "in 4 languages" in engine["framing"]
        assert "5 languages" not in engine["framing"]

    def test_no_typed_language_count_in_framing(self):
        src = (ROOT / "scripts" / "generate_dashboard.py").read_text(encoding="utf-8")
        assert "self-review, in 5 languages" not in src


# ---------------------------------------------------------------------------
# Mission Control page
# ---------------------------------------------------------------------------

class TestMissionControlNumbers:
    def test_sponsor_wow_is_last_complete_week(self):
        code = _strip_js_comments(_mc())
        panel = code[code.index("function renderSponsorPanel"):]
        panel = panel[:panel.index("})();")]
        assert "audience_headline" in panel
        assert "wow_pct" in panel
        # The partial-week comparison is gone.
        assert "weeks[weeks.length - 1]" not in panel

    def test_episodes_per_week_from_rss_count(self):
        code = _strip_js_comments(_mc())
        assert "benchmarks || {}).network) || {}).episodes_7d" in code
        assert "(cost.network_last_7_days || {}).episodes" not in code

    def test_alert_band_never_prints_object(self):
        code = _strip_js_comments(_mc())
        assert "String(a.message || a)" not in code
        assert 'a.type === "landmine"' in code

    def test_levers_text_is_escaped(self):
        code = _strip_js_comments(_mc())
        block = code[code.index('sectionCard("Levers in flight"'):]
        block = block[:block.index("grid.appendChild(card);")]
        assert "esc(r.title)" in block and "esc(v)" in block
        assert '"<strong>" + r.title' not in block
        assert "<details" in block or 'h("details"' in block
        assert "mc-card-wide" in block

    def test_operator_plumbing_hidden_outside_operator_view(self):
        code = _strip_js_comments(_mc())
        for marker in ("Not yet indexed by OP3", "Connect scrape",
                       "Not refreshed this run"):
            i = code.index(marker)
            assert '"data-ops": ""' in code[max(0, i - 400):i], marker
        # Per-show claim rows sit in the operator-only wrapper.
        assert 'const ops = h("div", { "data-ops": "" })' in code
        assert "ops.appendChild(barRow(slug, v.claims_total" in code

    def test_show_slugs_render_as_display_names(self):
        code = _strip_js_comments(_mc())
        assert "const shown = showName(label);" in code
        assert "SHOW_NAMES[r.slug] = r.name" in code


def _hex_lum(h: str) -> float:
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def _contrast(a: str, b: str) -> float:
    la, lb = sorted((_hex_lum(a), _hex_lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


class TestMissionControlLayoutAndContrast:
    def test_bar_value_can_shrink(self):
        css = _mc()
        rule = re.search(r"\.bar-row \.value \{([^}]*)\}", css).group(1)
        assert "flex: 0 0 auto; font-size" not in rule
        assert "max-width" in rule and "overflow-wrap" in rule
        label = re.search(r"\.bar-row \.label \{([^}]*)\}", css).group(1)
        assert "flex: 0 1" in label

    def test_faint_ink_passes_aa(self):
        css = _mc()
        ink4 = re.search(r"--ink-4:\s*(#[0-9a-fA-F]{6})", css).group(1)
        surface = re.search(r"--surface-1:\s*(#[0-9a-fA-F]{6})", css).group(1)
        assert _contrast(ink4, surface) >= 4.5

    def test_active_view_button_passes_aa(self):
        css = _mc()
        rule = re.search(r'\.view-switch button\[aria-pressed="true"\] \{([^}]*)\}', css).group(1)
        color = re.search(r"color:\s*(#[0-9a-fA-F]{3,6})", rule).group(1)
        color = "#ffffff" if color.lower() in ("#fff", "#ffffff") else color
        assert _contrast(color, "#6B47FF") >= 4.5


# ---------------------------------------------------------------------------
# MIT performance page
# ---------------------------------------------------------------------------

class TestMitPerformance:
    def _render(self):
        tpl = _jinja_env().get_template("mit_performance_page.html.j2")
        perf = {
            "available": True,
            "summary": {"total_trades": 69, "wins": 36, "losses": 32,
                        "breakeven": 1, "win_rate_pct": 52.2},
            "alpha": {}, "benchmark": {}, "last_updated": "2026-10-06",
            "sectors": {
                "other": {"trade_count": 7, "exposure_pct": 70.0, "cumulative_pnl": 21.71},
                "tech": {"trade_count": 1, "exposure_pct": 10.0, "cumulative_pnl": -22.25},
                "energy": {"trade_count": 1, "exposure_pct": 10.0, "cumulative_pnl": 0.0},
                "metals": {"trade_count": 1, "exposure_pct": 10.0, "cumulative_pnl": -66.27},
            },
        }
        charts = {"equity_curve": [{"date": "2026-05-01", "cum": 1.0},
                                   {"date": "2026-05-02", "cum": 2.0}],
                  "monthly_pnl": [], "winloss": {}, "recent_trades": [],
                  "sector_pnl": [{"sector": "other", "pnl": 21.71, "trades": 7},
                                 {"sector": "tech", "pnl": -22.25, "trades": 1},
                                 {"sector": "energy", "pnl": 0.0, "trades": 1},
                                 {"sector": "metals", "pnl": -66.27, "trades": 1}],
                  "headline": {}}
        return tpl.render(performance_data=perf, tracker=None, mit_charts=charts,
                          path_prefix="", show={}, t={}, all_shows=[])

    def _sector_table(self, html):
        i = html.index("What the Data Says About Different Approaches")
        return html[i:html.index("</table>", i)]

    def test_missing_fields_are_not_zero(self):
        table = self._sector_table(self._render())
        assert "+0.00%" not in table
        assert ">0%<" not in table
        # Columns the data never carries are not drawn at all.
        assert "Win Rate" not in table and "Avg Alpha" not in table
        assert "+$22" in table and "-$66" in table

    def test_table_names_its_window(self):
        table = self._sector_table(self._render())
        assert "last 10 positions" in table
        assert "69-trade record" in table

    def test_zero_pnl_is_neutral(self):
        table = self._sector_table(self._render())
        row = table[table.index(">energy<"):]
        row = row[:row.index("</tr>")]
        assert "#10b981" not in row and "#ef4444" not in row

    def test_chart_labels_are_honest(self):
        src = (ROOT / "templates" / "mit_performance_page.html.j2").read_text(encoding="utf-8")
        assert "Sum of trade returns (pts)" in src
        assert "s[i].date.slice(2,7)" not in src
        assert "trade #" in src
        assert "P&amp;L by sector ($)" in src
        assert "Monthly P&amp;L (percentage points)" in src
        assert "not a compounded portfolio return" in src


# ---------------------------------------------------------------------------
# Live dashboards: curated blocks carry their date
# ---------------------------------------------------------------------------

class TestCuratedBlocksDated:
    def test_tesla_quarterly_shows_operator_date(self):
        tpl = _jinja_env().get_template("tesla_dashboard.html.j2")
        html = tpl.render(path_prefix="", t={}, all_shows=[],
                          deliveries_quarterly=[{"quarter": "2025 Q1", "produced": 1,
                                                 "delivered": 1}],
                          deliveries_annual=[], energy_storage_annual_gwh=[],
                          supercharger_connectors_annual=[], highlights=[],
                          metrics_updated_at="2026-06-13")
        assert "Operator data as of 2026-06-13" in html
        assert "latest quarter on record: 2025 Q1" in html
        # Quarter labels split onto two lines so they hold 11px on a phone.
        assert '<div class="tsl-qlab">Q1<br>2025</div>' in html

    def test_tesla_generator_passes_metrics_date(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        assert '"metrics_updated_at": metrics.get("updated_at")' in src

    def test_bar_labels_have_headroom(self):
        for name, cls in (("tesla_dashboard.html.j2", ".tsl-bars"),
                          ("tesla_dashboard.html.j2", ".tsl-qbars"),
                          ("spacex_dashboard.html.j2", ".spx-cadence")):
            src = (ROOT / "templates" / name).read_text(encoding="utf-8")
            rule = re.search(re.escape(cls) + r" \{([^}]*)\}", src).group(1)
            pad = int(re.search(r"padding-top:(\d+)px", rule).group(1))
            assert pad >= 20, (name, cls)

    def test_spacex_starship_prefers_live_record(self):
        src = (ROOT / "templates" / "spacex_dashboard.html.j2").read_text(encoding="utf-8")
        assert "function newestLiveStarship" in src
        assert "renderStarship(data.starship, data)" in src
        assert 'id="ssLiveNote"' in src and 'id="ssAsOf"' in src
        assert ">Integrated flights<" not in src

    def test_offshore_fleet_stale_names_its_date(self):
        src = (ROOT / "templates" / "offshore_north_dashboard.html.j2").read_text(encoding="utf-8")
        assert "last good read ' + esc(b.fetched" in src


class TestOffshoreNorthRecord:
    def test_calendar_agrees_with_aiming_to_start_rule(self):
        data = json.loads((ROOT / "site" / "data" / "offshore_north_dashboard.json")
                          .read_text(encoding="utf-8"))
        for row in data.get("calendar") or []:
            label = row.get("label", "")
            if "Route du Rhum" in label and ("Canada Ocean Racing" in label
                                             or "Shawyer" in label):
                assert "on the list" not in label, label
                assert "entered" not in label.lower(), label


# ---------------------------------------------------------------------------
# Modern Investing resources (hand-written)
# ---------------------------------------------------------------------------

class TestMitResourcesPage:
    def _src(self):
        return (ROOT / "modern-investing-resources.html").read_text(encoding="utf-8")

    def test_phone_query_beats_inline_columns(self):
        src = self._src()
        assert "#calcCard > div:first-child { grid-template-columns:1fr !important; }" in src
        assert "#calcResults > div:first-child { grid-template-columns:1fr !important; }" in src

    def test_show_colour_text_uses_a_passing_tint(self):
        src = self._src()
        tint = re.search(r"--show-color-text:\s*(#[0-9a-fA-F]{6})", src).group(1)
        # Darkest page surface the text sits on.
        assert _contrast(tint, "#161a24") >= 4.5
        assert ".resource-card-url" in src and ".milestone-badge" in src
