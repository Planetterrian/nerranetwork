"""Guards for the Nov 11 2026 Mission Control redesign.

The page was 34,000 px tall, opened on six full-width alert banners, and
gave a sponsor one week's week-over-week change as the headline "growth"
figure while twenty weeks of history sat in the repo uncharted. Now every
view opens on a growth panel built from that history, the operator opens on
what needs attention and what moved, and the detail collapses.

Under guard: the growth reading (complete weeks only, a comparison that is
None until the history can make it, never a forecast), and the page wiring
that keeps the three audiences' views honest.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "management.html"


def _gen():
    name = "generate_dashboard_mc_2026_11_11"
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / "generate_dashboard.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _root(tmp_path, weeks, updated="2026-11-10T22:00:00+00:00", yt_rows=None):
    (tmp_path / "api").mkdir()
    (tmp_path / "api" / "op3_history.json").write_text(json.dumps(
        {"updated_at": updated, "weeks": {wk: {"a": n} for wk, n in weeks}}))
    if yt_rows is not None:
        (tmp_path / "api" / "youtube_channel_history.json").write_text(json.dumps({"rows": yt_rows}))
    return tmp_path


def _mondays(n, end="2026-11-09"):
    import datetime as dt
    last = dt.date.fromisoformat(end)
    return [(last - dt.timedelta(weeks=n - 1 - i)).isoformat() for i in range(n)]


class TestGrowthStoryDownloads:
    def test_newest_bucket_is_never_charted(self, tmp_path):
        weeks = list(zip(_mondays(10), [100] * 9 + [9999]))
        out = _gen().build_growth_story(_root(tmp_path, weeks))
        charted = [w["week"] for w in out["downloads"]["weeks"]]
        assert "2026-11-09" not in charted and len(charted) == 9
        assert all(w["value"] == 100 for w in out["downloads"]["weeks"])

    def test_four_week_average_against_a_quarter_earlier(self, tmp_path):
        # 18 complete weeks + the newest bucket: the last four average 400,
        # the four ending 13 weeks earlier average 100.
        values = [100] * 5 + [200] * 9 + [400] * 4 + [1]
        out = _gen().build_growth_story(_root(tmp_path, list(zip(_mondays(19), values))))
        d = out["downloads"]
        assert d["avg_4w"] == 400 and d["avg_4w_then"] == 100
        assert d["weeks_apart"] == 13 and d["multiple"] == 4.0 and d["change_pct"] == 300.0

    def test_short_history_compares_nothing(self, tmp_path):
        out = _gen().build_growth_story(_root(tmp_path, list(zip(_mondays(7), [100] * 7))))
        d = out["downloads"]
        assert d["avg_4w"] == 100
        assert d["multiple"] is None and d["avg_4w_then"] is None and d["change_pct"] is None

    def test_history_under_a_quarter_uses_the_first_four_weeks(self, tmp_path):
        values = [100] * 4 + [300] * 5 + [1]
        d = _gen().build_growth_story(_root(tmp_path, list(zip(_mondays(10), values))))["downloads"]
        assert d["weeks_apart"] == 5 and d["avg_4w_then"] == 100 and d["multiple"] == 3.0

    def test_no_multiple_against_a_base_under_the_floor(self, tmp_path):
        values = [5] * 5 + [50] * 9 + [400] * 4 + [1]
        d = _gen().build_growth_story(_root(tmp_path, list(zip(_mondays(19), values))))["downloads"]
        assert d["avg_4w"] == 400 and d["multiple"] is None

    def test_missing_files_are_unconfigured_not_zero(self, tmp_path):
        (tmp_path / "api").mkdir()
        out = _gen().build_growth_story(tmp_path)
        assert out["configured"] is False
        assert out["downloads"]["avg_4w"] is None and out["youtube"]["subscribers_now"] is None


class TestGrowthStoryYouTube:
    def test_a_missed_night_carries_the_channel_forward(self, tmp_path):
        rows = [
            {"date": "2026-10-01", "channel": "en", "subscribers": 100, "total_views": 1000},
            {"date": "2026-10-01", "channel": "ru", "subscribers": 50, "total_views": 500},
            # ru missed the night of the 15th: its 50 carries, never drops to 0
            {"date": "2026-10-15", "channel": "en", "subscribers": 130, "total_views": 1500},
        ]
        y = _gen().build_growth_story(_root(tmp_path, [], yt_rows=rows))["youtube"]
        assert y["subscribers_first"] == 150 and y["subscribers_now"] == 180
        assert y["views_now"] == 2000
        assert y["points"][-1]["by_channel"] == {"en": 130, "ru": 50}
        assert [p["date"] for p in y["points"]] == ["2026-10-01", "2026-10-01", "2026-10-15"][-len(y["points"]):]

    def test_one_point_a_week(self, tmp_path):
        import datetime as dt
        rows = [{"date": (dt.date(2026, 9, 1) + dt.timedelta(days=i)).isoformat(), "channel": "en",
                 "subscribers": 100 + i, "total_views": 10 * i} for i in range(29)]
        y = _gen().build_growth_story(_root(tmp_path, [], yt_rows=rows))["youtube"]
        dates = [dt.date.fromisoformat(p["date"]) for p in y["points"]]
        assert len(dates) == 5 and all((b - a).days == 7 for a, b in zip(dates, dates[1:]))
        assert y["points"][-1]["subscribers"] == 128


class TestCommittedDashboard:
    def test_generator_ships_the_section(self):
        src = (ROOT / "scripts" / "generate_dashboard.py").read_text(encoding="utf-8")
        assert '"growth_story": build_growth_story(root),' in src

    def test_committed_growth_story_is_complete_weeks(self):
        data = json.loads((ROOT / "api" / "dashboard.json").read_text(encoding="utf-8"))
        gs = data.get("growth_story")
        if not gs or not gs.get("configured"):
            return  # a dashboard.json from before the section is a legitimate state
        hist = json.loads((ROOT / "api" / "op3_history.json").read_text(encoding="utf-8"))
        newest = max(hist["weeks"])
        weeks = [w["week"] for w in gs["downloads"]["weeks"]]
        assert weeks == sorted(weeks)
        if str(hist.get("updated_at", ""))[:10] < _plus_days(newest, 7):
            assert newest not in weeks


def _plus_days(iso, n):
    import datetime as dt
    return (dt.date.fromisoformat(iso) + dt.timedelta(days=n)).isoformat()


def _page() -> str:
    return PAGE.read_text(encoding="utf-8")


def _block(src: str, start: str) -> str:
    body = src[src.index(start):]
    return body[:body.index("\n  })();")]


class TestPageWiring:
    def test_every_view_opens_on_the_growth_panel(self):
        src = _page()
        assert '<section class="growth-story" id="growth-story"' in src
        section = src[src.index('<section class="growth-story" id="growth-story"'):]
        assert "data-ops" not in section[:section.index(">")]
        assert "data.growth_story" in _block(src, "function renderGrowthStory")

    def test_growth_panel_adds_no_platforms_together(self):
        """A download, a subscriber and a view are different events."""
        body = _block(_page(), "function renderGrowthStory")
        assert "never added together" in body
        assert not re.search(r"avg_4w\s*\+\s*\w*\.?(subscribers|views)", body)

    def test_growth_panel_is_labelled_history_not_forecast(self):
        assert "not a forecast" in _block(_page(), "function renderGrowthStory")

    def test_no_weekly_change_as_the_sponsor_headline(self):
        src = _page()
        assert 'l: "Week-over-week growth"' not in src
        panel = _block(src, "function renderSponsorPanel")
        # The weekly change stays in the hero, as the complete-week figure.
        assert "ahNet.wow_pct" in panel and "last complete week" in panel

    def test_sponsor_brief_types_no_price_and_no_gender(self):
        """engine.brand owns the rate card; YouTube age bands only."""
        src = _page()
        brief = _block(src, "function renderSponsorBrief")
        assert not re.search(r"\$\s?\d|USD|money\(|rateUsd\(", brief) and "CPM" not in brief
        assert "by_gender" not in src
        markup = src[src.index('id="sponsor-brief"'):src.index('id="tile-row"')]
        assert 'href="sponsor.html"' in markup and 'href="press.html"' in markup
        assert "$" not in markup

    def test_sponsor_brief_is_sponsor_only(self):
        assert '<section class="brief" data-sponsor id="sponsor-brief"' in _page()

    def test_operator_brief_is_internal(self):
        src = _page()
        assert '<section class="ops-brief" data-ops id="ops-brief"' in src
        # The alert band lives inside it and keeps its own tag.
        brief = src[src.index('id="ops-brief"'):src.index('id="sponsor-hero"')]
        assert '<div class="alert-band" id="alert-band" data-ops>' in brief

    def test_alerts_are_written_as_text(self):
        """Titles and details come from the generator; they are set with
        textContent, never concatenated into innerHTML."""
        src = _page()
        row = src[src.index("const alertRow = "):]
        row = row[:row.index("\n  };")]
        assert "html:" not in row and "innerHTML" not in row

    def test_detail_collapses_per_view_and_a_link_opens_it(self):
        src = _page()
        defaults = src[src.index("const SECTION_DEFAULTS = {"):]
        defaults = defaults[:defaults.index("};")]
        for view in ("operator", "sponsor", "investor"):
            assert view + ":" in defaults
        assert '"investor", "benchmarks"' in defaults
        assert "applySectionDefaults(view);" in src[src.index("function viewSwitch"):]
        assert 'window.addEventListener("hashchange"' in src

    def test_sponsor_only_tiles_stay_hidden_elsewhere(self):
        """The tile rule sets display; without this pair the sponsor-only
        tiles showed in the operator and investor views."""
        src = _page()
        assert ".tile[data-sponsor] { display: none; }" in src
        assert "body.view-sponsor .tile[data-sponsor] { display: flex; }" in src
