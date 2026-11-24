"""The YouTube growth readout and the reach instrument's status (Nov 24 2026)."""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_youtube_growth as g  # noqa: E402
import fetch_youtube_reach as reach  # noqa: E402


def _history(channel="en", start=dt.date(2026, 9, 1), days=64, subs=100, per_day=2,
             views_per_day=1000):
    return {"rows": [{"date": (start + dt.timedelta(days=i)).isoformat(),
                      "channel": channel, "subscribers": subs + per_day * i,
                      "total_views": views_per_day * i} for i in range(days)]}


class TestWeeks:
    def test_a_week_is_two_snapshots_seven_days_apart(self):
        weeks = g.weekly_series(_history())["en"]
        assert len(weeks) == 9  # 63 days of differences
        assert all(w["net_subscribers"] == 14 and w["views"] == 7000 for w in weeks)
        assert weeks[-1]["week_ending"] == "2026-11-03"

    def test_a_missing_snapshot_drops_its_week_never_guesses(self):
        hist = _history()
        hist["rows"] = [r for r in hist["rows"] if r["date"] != "2026-10-27"]
        ends = [w["week_ending"] for w in g.weekly_series(hist)["en"]]
        assert "2026-11-03" not in ends and "2026-10-27" not in ends

    def test_summary_is_null_without_four_whole_weeks(self):
        weeks = g.weekly_series(_history(days=30))["en"]
        s = g.growth_summary(weeks)
        assert s["net_subscribers_4w"] == 56 and s["net_subscribers_prior_4w"] is None


def _short(channel, show, views, published="2026-11-20", window="hook_open"):
    return {"kind": "short", "channel": channel, "show": show, "window": window,
            "published": published, "views_by_age": {"3": views}}


class TestSameEpisode:
    TODAY = dt.date(2026, 11, 24)

    def test_median_per_channel_and_the_ratio_to_en(self):
        vids = {}
        for i in range(6):
            vids[f"e{i}"] = _short("en", "ff", 10)
            vids[f"r{i}"] = _short("ru", "ff", 250)
        out = g.same_episode({"videos": vids}, self.TODAY)
        assert out["ff"]["en"] == {"n": 6, "median_views": 10.0, "times_en": None}
        assert out["ff"]["ru"]["times_en"] == 25.0

    def test_under_five_videos_is_null_and_one_channel_is_no_row(self):
        vids = {f"e{i}": _short("en", "ff", 10) for i in range(6)}
        vids.update({f"r{i}": _short("ru", "ff", 250) for i in range(3)})
        vids.update({f"x{i}": _short("en", "solo", 10) for i in range(6)})
        out = g.same_episode({"videos": vids}, self.TODAY)
        assert out["ff"]["ru"]["median_views"] is None and out["ff"]["ru"]["times_en"] is None
        assert "solo" not in out

    def test_only_the_hook_short_inside_the_window_at_the_fixed_age(self):
        vids = {f"e{i}": _short("en", "ff", 10) for i in range(6)}
        vids.update({f"r{i}": _short("ru", "ff", 250, window="filled") for i in range(6)})
        vids.update({f"o{i}": _short("ru", "ff", 250, published="2026-09-01") for i in range(6)})
        vids["young"] = {"kind": "short", "channel": "ru", "show": "ff",
                         "window": "hook_open", "published": "2026-11-23",
                         "views_by_age": {"1": 999}}
        assert g.same_episode({"videos": vids}, self.TODAY) == {}


def _long(arm, views=100, avd=80, subs=0):
    return {"kind": "long", "channel": "en", "variant": arm, "show": "spacex",
            "views_by_age": {"7": views}, "avd_by_age": {"7": avd},
            "avp_by_age": {"7": 14.0}, "subs_by_age": {"7": subs}}


def _curve(vid, at30):
    # A 600 s video: t=0.05 is 30 s, t=0.10 is 60 s.
    return {"video_id": vid, "average_view_duration_s": 60.0, "average_view_percentage": 10.0,
            "retention_curve": [{"t": 0.01, "ratio": 1.0}, {"t": 0.05, "ratio": at30},
                                {"t": 0.10, "ratio": at30 - 0.15}]}


class TestMapAB:
    def _data(self, n, cut30, kept30):
        reach_file = {"videos": {}}
        rows = []
        for i in range(n):
            reach_file["videos"][f"c{i}"] = _long("map_cut", subs=1)
            reach_file["videos"][f"k{i}"] = _long("map_kept")
            rows += [_curve(f"c{i}", cut30), _curve(f"k{i}", kept30)]
        return reach_file, {"shows": {"spacex": {"videos": rows}}}

    def test_no_verdict_under_twenty_curves_an_arm(self):
        out = g.map_ab(*self._data(19, 0.60, 0.47))
        assert out["verdict"] is None
        assert out["arms"]["map_cut"]["retention_30s"] == 0.6
        assert out["arms"]["map_cut"]["subs_per_1000_views"] == 10.0

    def test_the_three_verdicts(self):
        assert g.map_ab(*self._data(20, 0.55, 0.47))["verdict"] == "cut_ahead"
        assert g.map_ab(*self._data(20, 0.40, 0.47))["verdict"] == "kept_ahead"
        assert g.map_ab(*self._data(20, 0.49, 0.47))["verdict"] == "no_difference"

    def test_unenrolled_longs_and_other_channels_are_in_no_arm(self):
        reach_file = {"videos": {"a": _long(""), "b": {**_long("map_cut"), "channel": "ru"},
                                 "c": {**_long("map_cut"), "views_by_age": {"3": 5}}}}
        out = g.map_ab(reach_file, {})
        assert out["arms"]["map_cut"]["n"] == 0 and out["arms"]["map_kept"]["n"] == 0
        assert out["arms"]["map_cut"]["median_views"] is None


class TestReachStatus:
    RAW = ('<HttpError 403 when requesting https://youtubereporting.googleapis.com/v1/jobs'
           '?alt=json returned "YouTube Reporting API has not been used in project '
           '141610975484 before or it is disabled. Enable it by')

    def test_a_disabled_api_names_the_operators_step(self):
        status, error = reach.classify_failure(self.RAW)
        assert status == "api_disabled"
        assert "youtubereporting.googleapis.com?project=141610975484" in error

    def test_anything_else_stays_an_error(self):
        assert reach.classify_failure("quota exceeded") == ("error", "quota exceeded")

    def test_the_readout_says_blocked_from_the_old_file_too(self):
        out = g.reach_instrument({"channels": {
            "en": {"status": "error", "error": self.RAW},
            "ru": {"status": "api_disabled"}}, "videos": {}})
        assert out == {"channels": {"en": "api_disabled", "ru": "api_disabled"},
                       "videos_with_data": 0, "blocked": True}
        assert g.reach_instrument({"channels": {"en": {"status": "ok"}},
                                   "videos": {"v": {}}})["blocked"] is False


class TestWiring:
    def test_the_nightly_writes_and_commits_the_readout(self):
        wf = (ROOT / ".github" / "workflows" / "nightly-maintenance.yml").read_text(encoding="utf-8")
        assert wf.index("scripts/track_early_reach.py") < wf.index("scripts/build_youtube_growth.py")
        assert "            api/youtube_growth.json" in wf

    def test_the_committed_file_builds_from_the_committed_inputs(self):
        data = g.build(ROOT, today=dt.date(2026, 11, 24))
        assert set(data) == {"schema_version", "generated", "channels",
                             "same_episode_hook_short", "long_form_map_ab", "reach_instrument"}
        assert data["long_form_map_ab"]["min_n_per_arm"] == g.AB_MIN_N
