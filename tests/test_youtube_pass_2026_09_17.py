"""Drift guards for the Sep 17 2026 YouTube pass.

* **A partial analytics fetch never replaces a healthy snapshot.** On
  09-16 the Analytics API answered HTTP 500 to most queries; every
  failure was swallowed as an empty result and a file with a third of
  the videos and no day series overwrote the good one. The policy,
  scorecard, early-reach card and register metrics all read zeros.
* **5xx is retried, 403 is not.**
* **The early-reach tracker skips a degraded snapshot** (first
  observation wins, so a bad one would freeze).
* **A trimmed digest keeps its combined script.** M&A's script was
  discarded every day because the forward line share fell under 0.6
  after run_show's trims; the reverse share is what a trim preserves.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

fya = importlib.import_module("scripts.fetch_youtube_analytics")
ter = importlib.import_module("scripts.track_early_reach")


def _snapshot(n_videos: int, day_series: bool = True, degraded=None):
    vids = [{"video_id": f"v{i}", "show_slug": "tesla", "kind": "short",
             "channel": "en", "published": "2026-09-10", "views": 5,
             "subscribers_gained": 0} for i in range(n_videos)]
    snap = {
        "schema_version": 2, "generated": "2026-09-16T19:48:00+00:00",
        "channels": {"en": {"subscribers": 437,
                            "day_series": ([{"day": "2026-09-14", "views": 100,
                                             "subscribersGained": 1,
                                             "subscribersLost": 0}]
                                           if day_series else [])}},
        "shows": {"tesla_shorts_time": {"videos": vids}},
    }
    if degraded:
        snap["degraded"] = {"failed_queries": degraded}
    return snap


class TestSnapshotRegression:
    def test_failed_queries_refuse_over_a_clean_file(self):
        reason = fya.snapshot_regression(
            _snapshot(2700, degraded=["video batch (200 ids)"] * 13 + ["channel day series"]),
            _snapshot(2753))
        assert reason and "14 analytics quer" in reason

    def test_a_third_of_the_videos_is_refused(self):
        reason = fya.snapshot_regression(_snapshot(927), _snapshot(2753))
        assert reason and "927 videos against 2753" in reason

    def test_a_lost_day_series_is_refused(self):
        reason = fya.snapshot_regression(_snapshot(2760, day_series=False), _snapshot(2753))
        assert reason and "day series" in reason

    def test_healthy_over_healthy_and_anything_over_nothing_pass(self):
        assert fya.snapshot_regression(_snapshot(2760), _snapshot(2753)) is None
        assert fya.snapshot_regression(_snapshot(2000), _snapshot(2753)) is None  # 73%
        assert fya.snapshot_regression(_snapshot(10), None) is None
        assert fya.snapshot_regression(_snapshot(10, day_series=False), {}) is None

    def test_degraded_over_degraded_is_allowed_to_recover(self):
        """A second partial fetch may still be better than the first."""
        assert fya.snapshot_regression(
            _snapshot(1500, degraded=["x"]), _snapshot(927, degraded=["y"])) is None


class TestTrafficDaySeries:
    """Sep 22 2026: the per-day traffic-source series is informational —
    losing it never refuses a snapshot, and its query failing never marks
    the snapshot degraded."""

    def test_lost_traffic_day_series_never_refuses(self):
        old = _snapshot(2753)
        old["channels"]["en"]["traffic_day_series"] = [
            {"day": "2026-09-14", "SHORTS": 50, "SUBSCRIBER": 30, "YT_SEARCH": 10,
             "RELATED_VIDEO": 5, "other": 5, "total": 100}]
        new = _snapshot(2760)
        assert fya.snapshot_regression(new, old) is None
        notes = fya.snapshot_notes(new, old)
        assert notes and "traffic-source day series" in notes[0]
        assert fya.snapshot_notes(old, old) == []

    def test_query_failure_is_not_a_degraded_marker(self, monkeypatch):
        class _Boom:
            def reports(self):
                return self
            def query(self, **kw):
                raise RuntimeError("HttpError 500")
        monkeypatch.setattr(fya, "_RETRY_SLEEPS_S", ())
        monkeypatch.setattr(fya, "_FAILED_QUERIES", [])
        assert fya._traffic_source_day_series(_Boom()) == []
        assert fya._FAILED_QUERIES == []

    def test_pivot_shape(self):
        class _Svc:
            def reports(self):
                return self
            def query(self, **kw):
                assert kw["dimensions"] == "day,insightTrafficSourceType"
                return self
            def execute(self):
                return {"columnHeaders": [{"name": "day"}, {"name": "insightTrafficSourceType"}, {"name": "views"}],
                        "rows": [["2026-09-20", "SHORTS", 40], ["2026-09-20", "SUBSCRIBER", 30],
                                 ["2026-09-20", "EXT_URL", 5], ["2026-09-21", "YT_SEARCH", 7]]}
        rows = fya._traffic_source_day_series(_Svc())
        assert rows == [
            {"day": "2026-09-20", "SHORTS": 40, "SUBSCRIBER": 30, "YT_SEARCH": 0,
             "RELATED_VIDEO": 0, "other": 5, "total": 75},
            {"day": "2026-09-21", "SHORTS": 0, "SUBSCRIBER": 0, "YT_SEARCH": 7,
             "RELATED_VIDEO": 0, "other": 0, "total": 7}]


class TestMainRefusesToOverwrite:
    def test_degraded_payload_leaves_the_committed_file_alone(self, tmp_path, monkeypatch, capsys):
        out = tmp_path / "youtube_stats.json"
        good = _snapshot(2753)
        out.write_text(json.dumps(good), encoding="utf-8")
        monkeypatch.setattr(fya, "fetch", lambda *a, **k: _snapshot(927, day_series=False,
                                                                     degraded=["video batch"]))
        monkeypatch.setattr(fya, "_ROOT", tmp_path)
        monkeypatch.setattr(sys, "argv", ["fetch", "--out", "youtube_stats.json"])
        assert fya.main() == 0
        assert json.loads(out.read_text(encoding="utf-8")) == good
        assert "::error::YouTube analytics snapshot REFUSED" in capsys.readouterr().out

    def test_healthy_payload_is_written(self, tmp_path, monkeypatch):
        out = tmp_path / "youtube_stats.json"
        out.write_text(json.dumps(_snapshot(2753)), encoding="utf-8")
        monkeypatch.setattr(fya, "fetch", lambda *a, **k: _snapshot(2790))
        monkeypatch.setattr(fya, "_ROOT", tmp_path)
        monkeypatch.setattr(fya, "_CHANNEL_HISTORY_PATH", "history.json")
        monkeypatch.setattr(sys, "argv", ["fetch", "--out", "youtube_stats.json"])
        assert fya.main() == 0
        n = sum(len(s["videos"]) for s in json.loads(out.read_text())["shows"].values())
        assert n == 2790


class _Req:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)

    def execute(self):
        o = self.outcomes.pop(0)
        if isinstance(o, Exception):
            raise o
        return o


class TestServerErrorRetry:
    def test_500_twice_then_success(self, monkeypatch):
        sleeps = []
        monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))
        req = _Req([Exception('<HttpError 500 when requesting x returned "An internal error has occurred.">'),
                    Exception("HttpError 503 backend error"), {"rows": []}])
        assert fya._execute_with_retry(lambda: req, "t") == {"rows": []}
        assert sleeps == list(fya._RETRY_SLEEPS_S)

    def test_403_is_not_retried(self, monkeypatch):
        sleeps = []
        monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))
        req = _Req([Exception("<HttpError 403 insufficient scope>")])
        with pytest.raises(Exception):
            fya._execute_with_retry(lambda: req, "t")
        assert sleeps == []

    def test_batch_failure_is_recorded_for_the_degraded_marker(self):
        class _Svc:
            def reports(self):
                return self

            def query(self, **kw):
                return _Req([Exception("<HttpError 403 insufficient scope>")])
        del fya._FAILED_QUERIES[:]
        assert fya._query_batch(_Svc(), ["a", "b"], "2026-09-01", "2026-09-16") == {}
        assert fya._FAILED_QUERIES == ["video batch (2 ids)"]
        del fya._FAILED_QUERIES[:]


class TestTrackerSkipsDegraded:
    def test_reasons(self):
        assert ter.snapshot_unusable(_snapshot(5)) is None
        assert "quer" in ter.snapshot_unusable(_snapshot(5, degraded=["x"]))
        assert "day series" in ter.snapshot_unusable(_snapshot(5, day_series=False))
        assert ter.snapshot_unusable({"generated": "2026-09-16", "shows": {}}) is None  # no channels block

    def test_main_does_not_write_on_a_degraded_snapshot(self, tmp_path, capsys):
        stats = tmp_path / "stats.json"
        stats.write_text(json.dumps(_snapshot(5, day_series=False, degraded=["x"])), encoding="utf-8")
        out = tmp_path / "reach.json"
        assert ter.main(["--stats", str(stats), "--out", str(out)]) == 0
        assert not out.exists()
        assert "snapshot skipped" in capsys.readouterr().out


class TestTrimmedDigestKeepsItsScript:
    STASH = "\n".join(
        f"{i}. **Item {i}**\n   A long enough sentence number {i} about Tesla energy storage deals in Nevada."
        for i in range(1, 11))

    def test_a_heavy_trim_still_matches(self):
        from engine.generator import combined_script_matches_digest, combined_digest_line_shares
        trimmed = "\n".join(self.STASH.splitlines()[:8])  # 4 of 10 items survive
        fwd, back = combined_digest_line_shares(self.STASH, trimmed)
        assert fwd < 0.6 and back == 1.0
        assert combined_script_matches_digest(self.STASH, trimmed)

    def test_a_replacement_fails_both_ways(self):
        from engine.generator import combined_script_matches_digest
        other = "\n".join(
            f"{i}. **Story {i}**\n   Entirely different SpaceX Starship sentences about the {i}th static fire."
            for i in range(1, 11))
        assert not combined_script_matches_digest(self.STASH, other)
        assert not combined_script_matches_digest("", other)
        assert not combined_script_matches_digest(self.STASH, "")

    def test_pipeline_logs_the_shares(self):
        src = (ROOT / "engine" / "pipeline.py").read_text(encoding="utf-8")
        assert "combined_digest_line_shares" in src
