"""What an OP3 "week" is, and the one reading every surface uses (Nov 12 2026).

OP3's ``weeklyDownloads`` are four back-to-back TRAILING seven-day windows
ending on ``asof``, every one complete. The network had read them as
calendar weeks whose newest entry was the week in progress, so:

* the audience headline, the media kit and Mission Control skipped the
  newest window as "partial" and reported the week before last (on Nov 10
  2026 the headline read -16.9% while the latest seven days were up on the
  seven before);
* the ledger (``api/op3_history.json``) wrote all four windows every night
  under the Monday of the fetch date, so its newest four "weeks" changed
  value nightly, overlapped the frozen week before them by up to six days,
  and the all-time total double-counted those days.

Under guard: the evidence itself (the shift the nightly files show), week
over week as the newest window against the one before, a ledger that takes
windows only on the night they are whole Sunday to Saturday weeks, readers
that share one reading, and committed files that agree with it.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import op3_weeks  # noqa: E402
from scripts import build_audience_headline as ah  # noqa: E402

# Network sums of the committed api/op3_stats.json on three nights a week
# apart (git history; asof is the day before each fetch).
NIGHTS = [
    ("2026-10-21", [1942, 3013, 4651, 3881]),
    ("2026-10-28", [3013, 4651, 3861, 2977]),
    ("2026-11-04", [4651, 3861, 2977, 3685]),
]


def _gen():
    name = "generate_dashboard_op3_weeks_2026_11_12"
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / "generate_dashboard.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _ledger(root):
    return json.loads((root / "api" / "op3_history.json").read_text(encoding="utf-8"))


class TestTheEvidence:
    def test_each_night_reappears_a_week_later_shifted_one_place(self):
        """A calendar week would stand still for seven nights. These move
        one place to the left: the same seven days, named one window older
        (OP3 revises a window by a fraction of a percent as late requests
        arrive, hence the tolerance)."""
        for (_a1, earlier), (_a2, later) in zip(NIGHTS, NIGHTS[1:]):
            for was, now in zip(earlier[1:], later[:3]):
                assert abs(was - now) <= max(25, was * 0.01), (earlier, later)

    def test_a_window_is_seven_days_ending_on_asof(self):
        assert op3_weeks.window_bounds("2026-11-11") == (dt.date(2026, 11, 5), dt.date(2026, 11, 11))
        assert op3_weeks.window_bounds("2026-11-11", back=1) == (dt.date(2026, 10, 29), dt.date(2026, 11, 4))
        assert op3_weeks.window_bounds(None) is None and op3_weeks.window_bounds("soon") is None


class TestWeekOverWeek:
    def test_the_newest_window_against_the_one_before(self):
        assert op3_weeks.latest_and_prior([3861, 2977, 3687, 4160]) == (4160, 3687)
        assert ah.weekly_wow([3861, 2977, 3687, 4160]) == {
            "last_week": 4160, "prior_week": 3687, "wow_pct": 12.8}

    def test_the_week_before_last_is_never_the_figure(self):
        """The Nov 10 reading: 3595 -> 2989 printed as -16.9% while the
        latest seven days were 4678."""
        out = ah.weekly_wow([3367, 3595, 2989, 4678])
        assert out["last_week"] == 4678 and out["prior_week"] == 2989
        assert out["wow_pct"] > 0

    def test_unmeasured_is_none_never_zero(self):
        assert op3_weeks.latest_and_prior([]) == (None, None)
        assert op3_weeks.latest_and_prior([7]) == (None, None)
        assert ah.weekly_wow([7]) == {"last_week": None, "prior_week": None, "wow_pct": None}
        assert ah.weekly_wow([0, 0, 0, 9])["wow_pct"] is None   # nothing to divide by

    def test_the_headline_says_which_days(self, tmp_path):
        (tmp_path / "api").mkdir()
        (tmp_path / "api" / "op3_stats.json").write_text(json.dumps({
            "fetched_at": "2026-11-12T22:30:00+00:00",
            "shows": {"a": {"asof": "2026-11-11", "downloads_7d": 40, "downloads_30d": 100,
                            "weekly_downloads": [10, 20, 30, 40], "episodes": []}}}))
        net = ah.build_headline(tmp_path)["network"]
        assert net["week_ending"] == "2026-11-11"
        assert (net["last_week"], net["prior_week"], net["wow_pct"]) == (40, 30, 33.3)
        assert net["last_week"] == net["downloads_7d"]

    def test_no_reader_skips_the_newest_window(self):
        src = (ROOT / "scripts" / "build_audience_headline.py").read_text(encoding="utf-8")
        assert "series[-2], series[-3]" not in src
        assert "op3_weeks.latest_and_prior" in src


class TestTheLedgerTakesWholeWeeksOnly:
    def test_a_weeknight_writes_nothing(self, tmp_path):
        (tmp_path / "api").mkdir()
        per_show = {"a": {"weekly_downloads": [10, 20, 30, 40]}}
        for asof in ("2026-11-08", "2026-11-09", "2026-11-10", "2026-11-11",
                     "2026-11-12", "2026-11-13"):                      # Sun .. Fri
            out = _gen()._merge_op3_history(tmp_path, None, per_show, {"a": asof})
            assert out["network_total"] == 0 and out["through"] is None
        assert not (tmp_path / "api" / "op3_history.json").exists()

    def test_a_saturday_asof_writes_four_sunday_to_saturday_weeks(self, tmp_path):
        (tmp_path / "api").mkdir()
        out = _gen()._merge_op3_history(
            tmp_path, None, {"a": {"weekly_downloads": [10, 20, 30, 40]}}, {"a": "2026-11-07"})
        weeks = _ledger(tmp_path)["weeks"]
        assert {k: v["a"] for k, v in weeks.items()} == {
            "2026-10-12": 10, "2026-10-19": 20, "2026-10-26": 30, "2026-11-02": 40}
        for key in weeks:
            sunday, saturday = op3_weeks.ledger_week_bounds(key)
            assert dt.date.fromisoformat(key).weekday() == 0
            assert sunday.weekday() == 6 and saturday.weekday() == 5
        assert out["since"] == "2026-10-12" and out["through"] == "2026-11-07"
        assert out["network_total"] == 100

    def test_the_week_does_not_move_between_saturdays(self, tmp_path):
        """The old writer rewrote the newest four weeks every night."""
        (tmp_path / "api").mkdir()
        gen = _gen()
        gen._merge_op3_history(
            tmp_path, None, {"a": {"weekly_downloads": [10, 20, 30, 40]}}, {"a": "2026-11-07"})
        before = (tmp_path / "api" / "op3_history.json").read_bytes()
        for asof, series in (("2026-11-08", [11, 22, 33, 44]), ("2026-11-11", [15, 25, 35, 99])):
            gen._merge_op3_history(tmp_path, None, {"a": {"weekly_downloads": series}}, {"a": asof})
            assert (tmp_path / "api" / "op3_history.json").read_bytes() == before
        # The next Saturday slides the window: the oldest week is frozen,
        # three carry OP3's revisions, one is new.
        out = gen._merge_op3_history(
            tmp_path, None, {"a": {"weekly_downloads": [21, 31, 41, 50]}}, {"a": "2026-11-14"})
        assert {k: v["a"] for k, v in _ledger(tmp_path)["weeks"].items()} == {
            "2026-10-12": 10, "2026-10-19": 21, "2026-10-26": 31, "2026-11-02": 41,
            "2026-11-09": 50}
        assert out["network_total"] == 153 and out["through"] == "2026-11-14"

    def test_a_show_without_a_date_is_never_placed_by_guessing(self, tmp_path):
        (tmp_path / "api").mkdir()
        gen = _gen()
        per_show = {"a": {"weekly_downloads": [1, 2, 3, 4]}, "b": {"weekly_downloads": [5, 6, 7, 8]}}
        gen._merge_op3_history(tmp_path, "2026-11-08T20:00:00+00:00", per_show, {"a": "2026-11-07"})
        assert all(set(row) == {"a"} for row in _ledger(tmp_path)["weeks"].values())
        # ...and the fetch time alone places nothing.
        other = tmp_path / "other"
        (other / "api").mkdir(parents=True)
        gen._merge_op3_history(other, "2026-11-08T20:00:00+00:00", per_show)
        assert not (other / "api" / "op3_history.json").exists()

    def test_the_dashboard_passes_each_shows_own_asof(self):
        src = (ROOT / "scripts" / "generate_dashboard.py").read_text(encoding="utf-8")
        assert '{slug: s.get("asof") for slug, s in shows.items()}' in src
        assert '"all_time_through": history.get("through"),' in src
        # The fetch date no longer places a window.
        merge = src[src.index("def _merge_op3_history"):src.index("#: A 7-day ratings delta")]
        assert "monday_w0" not in merge and "weekday()" not in merge


class TestOneReading:
    def test_every_week_on_file_is_read_once_it_has_ended(self):
        hist = {"updated_at": "2026-11-15T21:00:00+00:00",
                "weeks": {"2026-11-02": {"a": 5}, "2026-11-09": {"a": 7}}}
        assert [(m.isoformat(), r["a"]) for m, r in op3_weeks.complete_ledger_weeks(hist)] == [
            ("2026-11-02", 5), ("2026-11-09", 7)]

    def test_a_week_ahead_of_its_own_file_is_not_read(self):
        """A file from before this pass: key Nov 9 written on Nov 10."""
        hist = {"updated_at": "2026-11-10T22:00:00+00:00",
                "weeks": {"2026-11-02": {"a": 5}, "2026-11-09": {"a": 7}}}
        assert [m.isoformat() for m, _r in op3_weeks.complete_ledger_weeks(hist)] == ["2026-11-02"]
        assert op3_weeks.complete_ledger_weeks({"weeks": {"2026-11-02": {"a": 5}}}) == []
        assert op3_weeks.complete_ledger_weeks(None) == []

    def test_the_media_kit_and_the_growth_panel_share_the_reader(self):
        kit = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        kit = kit[kit.index("def _media_kit_growth"):kit.index("# YouTube subscribers: nightly snapshots per channel")]
        panel = (ROOT / "scripts" / "generate_dashboard.py").read_text(encoding="utf-8")
        panel = panel[panel.index("def build_growth_story"):panel.index("# ---- YouTube")] \
            if "# ---- YouTube" in panel else panel[panel.index("def build_growth_story"):]
        for src in (kit, panel):
            assert "complete_ledger_weeks(hist)" in src
            assert "timedelta(days=7) > updated" not in src

    def test_no_page_calls_the_newest_window_partial(self):
        page = (ROOT / "management.html").read_text(encoding="utf-8")
        assert "current partial week" not in page
        assert "last full week" not in page
        press = (ROOT / "templates" / "press.html.j2").read_text(encoding="utf-8")
        assert "latest seven days" in press and "last complete week" not in press
        for name in ("press.html.j2", "sponsor_page.html.j2"):
            assert "Weeks run Sunday to Saturday" in (ROOT / "templates" / name).read_text(encoding="utf-8")


class TestCommittedFiles:
    """These read today's committed data, so each holds on any night."""

    def test_every_ledger_key_is_a_monday_whose_week_has_ended(self):
        hist = _ledger(ROOT)
        updated = dt.date.fromisoformat(str(hist["updated_at"])[:10])
        for key in hist["weeks"]:
            assert dt.date.fromisoformat(key).weekday() == 0, key
            assert op3_weeks.ledger_week_bounds(key)[1] < updated, key
        assert len(op3_weeks.complete_ledger_weeks(hist)) == len(hist["weeks"])

    def test_the_ledger_has_no_gap(self):
        keys = sorted(_ledger(ROOT)["weeks"])
        days = [dt.date.fromisoformat(k) for k in keys]
        assert all((b - a).days == 7 for a, b in zip(days, days[1:])), keys

    def test_the_repaired_weeks_are_the_sunday_fetch(self):
        """The four weeks the old writer had overwritten with mid-week
        windows, restored from the Sunday Nov 8 fetch (asof Saturday Nov 7):
        network sums 4078, 3808, 2969, 4260. Frozen since, apart from
        OP3's own revisions on the following three Saturdays."""
        weeks = _ledger(ROOT)["weeks"]
        assert sum(weeks["2026-10-12"].values()) == 4078
        for key, was in (("2026-10-19", 3808), ("2026-10-26", 2969), ("2026-11-02", 4260)):
            assert abs(sum(weeks[key].values()) - was) <= was * 0.02, key

    def test_the_committed_headline_compares_the_newest_window(self):
        net = json.loads((ROOT / "api" / "audience_headline.json").read_text(encoding="utf-8"))["network"]
        series = net.get("weekly_downloads") or []
        if len(series) < 2:
            return  # an unmeasured night is a legitimate state
        assert net["last_week"] == series[-1] and net["prior_week"] == series[-2]

    def test_the_ledger_is_still_committed_by_the_nightly(self):
        wf = (ROOT / ".github" / "workflows" / "nightly-maintenance.yml").read_text(encoding="utf-8")
        assert "api/op3_history.json" in wf
