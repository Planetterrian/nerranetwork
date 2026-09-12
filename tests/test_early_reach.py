"""Age-matched early reach (Sep 12 2026) — scripts/track_early_reach.py +
the dashboard card. A rolling channel total compared against a breakout
peak reads as a drop; views at a fixed snapshot age per publish day is
the comparison that cannot be fooled by that."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _stats(generated, rows):
    return {"generated": generated + "T19:00:00+00:00",
            "shows": {"x": {"videos": rows}}}


def _row(vid, published, views, ch="en", kind="short", subs=0):
    return {"video_id": vid, "published": published, "views": views,
            "channel": ch, "kind": kind, "show_slug": "tesla",
            "window": "hook_open", "subscribers_gained": subs}


class TestTracker:
    def test_records_views_at_snapshot_age_and_is_idempotent(self):
        tr = _load("ter", "scripts/track_early_reach.py")
        reach = tr.load_reach(Path("/nonexistent/x.json"))
        snap = _stats("2026-09-10", [_row("a", "2026-09-07", 40), _row("b", "2026-09-09", 5)])
        assert tr.merge_snapshot(reach, snap) == 2
        assert reach["videos"]["a"]["views_by_age"] == {"3": 40}
        assert reach["videos"]["b"]["views_by_age"] == {"1": 5}
        # Same snapshot again: nothing changes.
        assert tr.merge_snapshot(reach, snap) == 0
        # Next night: age advances, the earlier observation is kept.
        nxt = _stats("2026-09-11", [_row("a", "2026-09-07", 55), _row("b", "2026-09-09", 12)])
        assert tr.merge_snapshot(reach, nxt) == 2
        assert reach["videos"]["a"]["views_by_age"] == {"3": 40, "4": 55}
        assert reach["updated"] == "2026-09-11"

    def test_ignores_out_of_range_ages_and_prunes_old_videos(self):
        tr = _load("ter2", "scripts/track_early_reach.py")
        reach = {"schema_version": 1, "updated": None,
                 "videos": {"old": {"published": "2026-06-01", "views_by_age": {"3": 1},
                                    "subs_by_age": {}, "channel": "en", "kind": "short",
                                    "show": "t", "window": ""}}}
        snap = _stats("2026-09-10", [_row("same_day", "2026-09-10", 1),
                                     _row("too_old", "2026-08-01", 900)])
        assert tr.merge_snapshot(reach, snap) == 0
        assert "old" not in reach["videos"]
        assert "same_day" not in reach["videos"] and "too_old" not in reach["videos"]

    def test_main_writes_file_and_never_raises_on_missing_stats(self, tmp_path):
        tr = _load("ter3", "scripts/track_early_reach.py")
        stats = tmp_path / "stats.json"
        stats.write_text(json.dumps(_stats("2026-09-10", [_row("a", "2026-09-07", 40)])))
        out = tmp_path / "reach.json"
        assert tr.main(["--stats", str(stats), "--out", str(out)]) == 0
        assert json.loads(out.read_text())["videos"]["a"]["views_by_age"] == {"3": 40}
        assert tr.main(["--stats", str(tmp_path / "missing.json"), "--out", str(out)]) == 0


class TestDashboardSection:
    def _gd(self):
        return _load("gd_er", "scripts/generate_dashboard.py")

    def test_unconfigured_without_file(self, tmp_path):
        gd = self._gd()
        (tmp_path / "api").mkdir()
        sec = gd.build_early_reach_section(tmp_path)
        assert sec["configured"] is False and "note" in sec

    def test_medians_per_publish_day_with_honest_nulls(self, tmp_path):
        gd = self._gd()
        (tmp_path / "api").mkdir()
        videos = {}
        for i in range(4):
            videos[f"s{i}"] = {"published": "2026-09-08", "channel": "en", "kind": "short",
                               "show": "t", "window": "hook_open",
                               "views_by_age": {"3": 10 + i}, "subs_by_age": {}}
        videos["l0"] = {"published": "2026-09-08", "channel": "en", "kind": "long", "show": "t",
                        "window": "", "views_by_age": {"3": 99}, "subs_by_age": {}}
        videos["no_d3"] = {"published": "2026-09-09", "channel": "en", "kind": "short", "show": "t",
                           "window": "", "views_by_age": {"1": 3}, "subs_by_age": {}}
        (tmp_path / "api" / "youtube_early_reach.json").write_text(json.dumps(
            {"schema_version": 1, "updated": "2026-09-11", "videos": videos}))
        sec = gd.build_early_reach_section(tmp_path)
        assert sec["configured"] is True and sec["age_days"] == 3
        day = sec["channels"]["en"]["days"][0]
        assert day["published"] == "2026-09-08" and day["weekday"] == "Tue"
        assert day["short_median"] == 12 and day["short_n"] == 4
        assert day["long_median"] is None and day["long_n"] == 1  # under the floor
        assert sec["channels"]["en"]["short_median_7d"] is None  # under 10 videos

    def test_metric_registered_and_nightly_wired(self):
        gd = self._gd()
        assert "short_reach_d3_median_en_7d" in gd._experiment_live_metrics(ROOT)
        wf = (ROOT / ".github/workflows/nightly-maintenance.yml").read_text(encoding="utf-8")
        assert "scripts/track_early_reach.py" in wf
        assert "api/youtube_early_reach.json" in wf  # add-paths whitelist (silent-drop class)
        html = (ROOT / "management.html").read_text(encoding="utf-8")
        assert "growth.early_reach" in html
