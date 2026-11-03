"""Nov 3 2026 — the channel the repo can see, and a measurement that can read
the levers (youtube-1 + youtube-5 of the six-month review).

What binds:
  - **The uploads playlist is reconciled nightly.** ``_channel_uploads`` pages
    the channel's uploads back ``UPLOADS_SINCE_DAYS``; ``attribute_rss_copies``
    diffs them against the per-show indexes and attributes an
    "Ep N: <hook prefix>" twin to its show as ``kind: rss_copy``. The copies
    JOIN the metrics batch (their views are read) and the shows block, and
    every instrument that reads the indexed kinds is unchanged:
    ``collect_velocities`` returns the same velocities, ``merge_snapshot``
    writes no ``rss_copy`` row, ``snapshot_regression`` counts indexed kinds
    only. A failed uploads read leaves the keys ABSENT (null, never 0) and
    never marks the snapshot degraded.
  - **A retention curve for EVERY long** of the last ``RETENTION_CURVE_DAYS``
    (newest first in ONE order across the channels, ``RETENTION_CURVE_MAX``
    a night) and the top Shorts; a
    failed curve never joins ``_FAILED_QUERIES``; ``curve_fetched_at`` says
    when, so a carried-forward curve is never read as fresh.
  - **The reach file carries ``hold5_by_age`` / ``hold25_by_age``** for longs
    only, from tonight's curve only, first observation wins.
  - **The five dashboard keys** (``long_hold5_age7_median_en``,
    ``long_d3_median_en_7d``, ``short_reach_d3_median_ru_7d``,
    ``short_reach_d3_median_fr_7d``, ``youtube_rss_copies_14d_<ch>``) are
    computable and null where unmeasured; the open-cliff card groups by show;
    the scorecard's analytics rows exclude the copies.
  - **The Short's job is written per channel** in ``engine/release_schedule.py``
    and the two docs; the nightly warns for a show that renders its own long
    and still carries RSS copies.
"""

from __future__ import annotations

import datetime as _dt
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
uyp = importlib.import_module("scripts.update_youtube_policy")
gd = importlib.import_module("scripts.generate_dashboard")

TODAY = _dt.date(2026, 11, 3)
HOOK = "Tesla registrations in Sweden rose 248 percent in October while Norway climbed 131 percent."


class _Exec:
    def __init__(self, payload):
        self._payload = payload

    def execute(self):
        return self._payload


class _FakeDataApi:
    """``channels().list(part="contentDetails", mine=True)`` then paged
    ``playlistItems().list``; records every call."""

    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def channels(self):
        return self

    def playlistItems(self):
        return self

    def list(self, **kw):
        self.calls.append(kw)
        if kw.get("part") == "contentDetails" and kw.get("mine"):
            return _Exec({"items": [{"contentDetails": {
                "relatedPlaylists": {"uploads": "UUnerra"}}}]})
        idx = int((kw.get("pageToken") or "p0")[1:])
        return _Exec(self.pages[idx])


def _item(vid, title, published):
    return {"snippet": {"title": title, "resourceId": {"videoId": vid}},
            "contentDetails": {"videoId": vid, "videoPublishedAt": published + "T11:00:00Z"}}


def _index_rows():
    return [
        {"video_id": "long653", "show_slug": "tesla", "episode": 653, "kind": "long",
         "channel": "en", "title": "Tesla Sales Jump 248% in Sweden", "hook": HOOK,
         "published": "2026-11-02", "_dir": "tesla_shorts_time"},
        {"video_id": "short653", "show_slug": "tesla", "episode": 653, "kind": "short",
         "channel": "en", "title": "Tesla Sweden Jumps 248% #Shorts", "hook": HOOK,
         "published": "2026-11-02", "_dir": "tesla_shorts_time", "window": "hook_open"},
        {"video_id": "long600", "show_slug": "tesla", "episode": 600, "kind": "long",
         "channel": "en", "title": "An older long", "hook": "An older hook about batteries.",
         "published": "2026-10-01", "_dir": "tesla_shorts_time"},
        {"video_id": "short652", "show_slug": "tesla", "episode": 652, "kind": "short",
         "channel": "en", "title": "Supercharger #Shorts", "hook": "California's 164-stall site.",
         "published": "2026-11-01", "_dir": "tesla_shorts_time", "window": "hook_open"},
    ]


def _uploads():
    # Two ids outside the index: the RSS copy of Ep 653 (attributable) and a
    # stray upload with a title shape the pipeline never writes.
    return [
        {"video_id": "long653", "title": "Tesla Sales Jump 248% in Sweden", "published": "2026-11-02"},
        {"video_id": "copy653", "title": "Ep 653: Tesla registrations in Sweden rose 248 percent in October while Norway…",
         "published": "2026-11-02"},
        {"video_id": "short653", "title": "Tesla Sweden Jumps 248% #Shorts", "published": "2026-11-02"},
        {"video_id": "stray1", "title": "Studio-only upload", "published": "2026-10-30"},
    ]


def _wire_fetch(monkeypatch, *, uploads, curves_log=None, data_service=None):
    """Make ``fetch`` run offline: index rows, credentials, one metrics row
    per queried id, a fake uploads read, every optional query empty."""
    import engine.youtube as yt
    monkeypatch.setattr(fya, "_load_index", lambda d: _index_rows())
    monkeypatch.setattr(yt, "get_channel_credentials_from_env", lambda ch: object())
    monkeypatch.setattr(fya, "_analytics_service", lambda creds: object())
    monkeypatch.setattr(fya, "_query_batch", lambda svc, ids, s, e: {
        vid: {"views": 10 if vid.startswith("long") else 100, "estimatedMinutesWatched": 1.0,
              "averageViewDuration": 30.0, "averageViewPercentage": 5.0,
              "subscribersGained": 1, "subscribersLost": 0} for vid in ids})
    monkeypatch.setattr(fya, "_channel_snapshot", lambda creds: {"subscribers": 1})
    monkeypatch.setattr(fya, "_channel_day_series", lambda svc, days=30: [
        {"day": "2026-11-01", "views": 100, "subscribersGained": 1, "subscribersLost": 0}])
    for name in ("_viewer_percentages", "_geography", "_traffic_sources",
                 "_traffic_source_day_series", "_search_terms"):
        monkeypatch.setattr(fya, name, lambda *a, **k: [])
    if data_service is not None:
        monkeypatch.setattr(fya, "_data_service", lambda creds: data_service)
    else:
        monkeypatch.setattr(fya, "_channel_uploads", lambda creds, **k: uploads)
    log = curves_log if curves_log is not None else []

    def _curve(service, video_id, start, end):
        log.append(video_id)
        return [{"t": 0.0, "ratio": 1.0}, {"t": 0.05, "ratio": 0.6}, {"t": 0.25, "ratio": 0.3}]
    monkeypatch.setattr(fya, "_retention_curve", _curve)
    monkeypatch.setattr(fya, "_FAILED_QUERIES", [])

    class _Date(_dt.date):
        @classmethod
        def today(cls):
            return TODAY
    monkeypatch.setattr(fya._dt, "date", _Date)
    return log


class TestChannelUploadsAreReconciled:
    def test_uploads_playlist_is_paged_until_the_window_closes(self):
        pages = [
            {"items": [_item("a", "Ep 1: x", "2026-11-02"), _item("b", "Ep 2: y", "2026-10-20")],
             "nextPageToken": "p1"},
            {"items": [_item("c", "Ep 3: z", "2026-10-05"), _item("d", "old", "2026-09-01"),
                       _item("e", "older", "2026-08-01")],
             "nextPageToken": "p2"},
            {"items": [_item("f", "never read", "2026-07-01")]},
        ]
        svc = _FakeDataApi(pages)
        rows = fya._channel_uploads(None, service=svc, today=TODAY, since_days=35)
        assert [r["video_id"] for r in rows] == ["a", "b", "c"]
        assert rows[0] == {"video_id": "a", "title": "Ep 1: x", "published": "2026-11-02"}
        # The first call named the uploads playlist; the third page was never asked for.
        assert svc.calls[0] == {"part": "contentDetails", "mine": True}
        assert [c.get("pageToken") for c in svc.calls[1:]] == [None, "p1"]
        assert all(c["playlistId"] == "UUnerra" for c in svc.calls[1:])

    def test_attribution_by_episode_number_and_hook_prefix(self):
        out = fya.attribute_rss_copies(_uploads(), _index_rows())
        assert [e["video_id"] for e in out] == ["copy653", "stray1"]
        copy = out[0]
        assert copy["kind"] == "rss_copy" and copy["show_slug"] == "tesla"
        assert copy["episode"] == 653 and copy["_dir"] == "tesla_shorts_time"
        assert "kind" not in out[1] and "show_slug" not in out[1]

    def test_a_matching_number_with_another_hook_is_not_attributed(self):
        ups = [{"video_id": "x", "title": "Ep 653: Rocket Lab launches its 99th mission today",
                "published": "2026-11-02"}]
        out = fya.attribute_rss_copies(ups, _index_rows())
        assert len(out) == 1 and "kind" not in out[0]

    def test_russian_feed_prefix_is_the_same_shape(self):
        rows = [{"video_id": "r1", "show_slug": "privet_russian", "episode": 41, "kind": "long",
                 "channel": "ru", "hook": "Сегодня разбираем слова про погоду и зиму.",
                 "published": "2026-11-02", "_dir": "privet_russian"}]
        ups = [{"video_id": "rc", "title": "Выпуск 41: Сегодня разбираем слова про погоду…",
                "published": "2026-11-02"}]
        out = fya.attribute_rss_copies(ups, rows)
        assert out[0]["kind"] == "rss_copy" and out[0]["show_slug"] == "privet_russian"

    def test_fetch_counts_two_unindexed_and_joins_one_copy(self, monkeypatch, tmp_path):
        _wire_fetch(monkeypatch, uploads=_uploads())
        payload = fya.fetch(tmp_path, 90, out_path=tmp_path / "none.json")
        en = payload["channels"]["en"]
        assert en["unindexed_recent_count"] == 2
        assert en["unindexed_since_days"] == fya.UPLOADS_SINCE_DAYS
        kinds = {e["video_id"]: e.get("kind") for e in en["unindexed_recent"]}
        assert kinds == {"copy653": "rss_copy", "stray1": None}
        assert all("_dir" not in e for e in en["unindexed_recent"])
        vids = payload["shows"]["tesla_shorts_time"]["videos"]
        copies = [v for v in vids if v["kind"] == "rss_copy"]
        assert len(copies) == 1
        assert copies[0]["video_id"] == "copy653" and copies[0]["views"] == 100
        assert copies[0]["show_slug"] == "tesla" and copies[0]["episode"] == 653
        assert "degraded" not in payload

    def test_collect_velocities_and_merge_snapshot_ignore_the_copy(self, monkeypatch, tmp_path):
        _wire_fetch(monkeypatch, uploads=_uploads())
        payload = fya.fetch(tmp_path, 90, out_path=tmp_path / "none.json")
        payload["generated"] = "2026-11-03T23:48:00+00:00"
        without = json.loads(json.dumps(payload))
        for sh in without["shows"].values():
            sh["videos"] = [v for v in sh["videos"] if v["kind"] != "rss_copy"]
        assert uyp.collect_velocities(payload) == uyp.collect_velocities(without)
        reach = ter.load_reach(tmp_path / "nonexistent.json")
        ter.merge_snapshot(reach, payload)
        assert "copy653" in {v["video_id"] for sh in payload["shows"].values()
                             for v in sh["videos"]}
        assert "copy653" not in reach["videos"]
        assert all(r["kind"] != "rss_copy" for r in reach["videos"].values())

    def test_failed_uploads_read_leaves_keys_absent_and_never_degraded(self, monkeypatch, tmp_path):
        class _Boom:
            def channels(self):
                raise RuntimeError("HttpError 403")
        assert fya._channel_uploads(None, service=_Boom(), today=TODAY) is None
        _wire_fetch(monkeypatch, uploads=None, data_service=_Boom())
        payload = fya.fetch(tmp_path, 90, out_path=tmp_path / "none.json")
        en = payload["channels"]["en"]
        assert "unindexed_recent" not in en and "unindexed_recent_count" not in en
        assert "degraded" not in payload
        assert not any(v["kind"] == "rss_copy"
                       for sh in payload["shows"].values() for v in sh["videos"])

    def test_snapshot_regression_counts_indexed_kinds_only(self):
        def _snap(n_indexed, n_copies):
            vids = [{"video_id": f"v{i}", "kind": "short", "channel": "en",
                     "published": "2026-11-01", "views": 1} for i in range(n_indexed)]
            vids += [{"video_id": f"c{i}", "kind": "rss_copy", "channel": "en",
                      "published": "2026-11-01", "views": 1} for i in range(n_copies)]
            return {"generated": "2026-11-03T00:00:00+00:00",
                    "channels": {"en": {"day_series": [{"day": "2026-11-01", "views": 1}],
                                        "unindexed_recent": [], "unindexed_recent_count": 0}},
                    "shows": {"x": {"videos": vids}}}
        # Unindexed rows beside a full index: nothing trips.
        assert fya.snapshot_regression(_snap(10, 10), _snap(10, 0)) is None
        # Copies never pad a thin fetch over the 60% line.
        reason = fya.snapshot_regression(_snap(5, 10), _snap(10, 0))
        assert reason and "5 videos against 10" in reason


class TestEveryLongGetsACurve:
    def test_one_curve_query_per_recent_long_and_none_for_older(self, monkeypatch, tmp_path):
        log = _wire_fetch(monkeypatch, uploads=None)
        payload = fya.fetch(tmp_path, 90, out_path=tmp_path / "none.json")
        assert log.count("long653") == 1 and "long600" not in log
        # The top Shorts by views are read too (hook-Short readouts).
        assert "short653" in log and "short652" in log
        rows = {v["video_id"]: v for v in payload["shows"]["tesla_shorts_time"]["videos"]}
        assert rows["long653"]["retention_curve"] and rows["long653"]["curve_fetched_at"] == TODAY.isoformat()
        assert "retention_curve" not in rows["long600"]
        assert payload.get("degraded") is None

    def test_budget_caps_the_night_newest_first(self, monkeypatch, tmp_path):
        monkeypatch.setattr(fya, "RETENTION_CURVE_MAX", 1)
        log = _wire_fetch(monkeypatch, uploads=None)
        fya.fetch(tmp_path, 90, out_path=tmp_path / "none.json")
        assert log == ["long653"]

    def test_the_budget_is_spent_newest_first_across_channels(self, monkeypatch, tmp_path):
        # Spent channel by channel, the EN longs alone (118 in the 14 days
        # to Nov 3) emptied the budget before RU or FR was asked for a
        # curve. The order is ONE list across the channels, newest first.
        rows = _index_rows() + [
            {"video_id": "frlong9", "show_slug": "tesla", "episode": 9, "kind": "long",
             "channel": "fr", "title": "Un long d'hier", "hook": "Une accroche.",
             "published": "2026-11-03", "_dir": "tesla_shorts_time"},
            {"video_id": "frlong8", "show_slug": "tesla", "episode": 8, "kind": "long",
             "channel": "fr", "title": "Un long plus vieux", "hook": "Une autre accroche.",
             "published": "2026-10-25", "_dir": "tesla_shorts_time"},
        ]
        monkeypatch.setattr(fya, "RETENTION_CURVE_MAX", 2)
        log = _wire_fetch(monkeypatch, uploads=None)
        monkeypatch.setattr(fya, "_load_index", lambda d: rows)
        payload = fya.fetch(tmp_path, 90, out_path=tmp_path / "none.json")
        assert log == ["frlong9", "long653"]
        fr = {v["video_id"]: v for v in payload["shows"]["tesla_shorts_time"]["videos"]
              if v["channel"] == "fr"}
        assert fr["frlong9"]["curve_fetched_at"] == TODAY.isoformat()
        assert "retention_curve" not in fr["frlong8"]

    def test_carried_forward_curve_keeps_its_old_date(self, monkeypatch, tmp_path):
        prev = tmp_path / "youtube_stats.json"
        prev.write_text(json.dumps({"shows": {"tesla_shorts_time": {"videos": [
            {"video_id": "long600", "retention_curve": [{"t": 0.05, "ratio": 0.5}],
             "curve_fetched_at": "2026-10-03"},
            {"video_id": "short652", "retention_curve": [{"t": 0.05, "ratio": 0.9}]},
        ]}}}), encoding="utf-8")
        monkeypatch.setattr(fya, "RETENTION_CURVE_MAX", 1)   # only long653 is fetched tonight
        _wire_fetch(monkeypatch, uploads=None)
        payload = fya.fetch(tmp_path, 90, out_path=prev)
        rows = {v["video_id"]: v for v in payload["shows"]["tesla_shorts_time"]["videos"]}
        assert rows["long600"]["retention_curve"] == [{"t": 0.05, "ratio": 0.5}]
        assert rows["long600"]["curve_fetched_at"] == "2026-10-03"
        # An old file that never stamped a date carries None — never today's.
        assert rows["short652"]["curve_fetched_at"] is None
        assert rows["long653"]["curve_fetched_at"] == TODAY.isoformat()

    def test_a_failed_curve_never_joins_failed_queries(self, monkeypatch):
        class _Boom:
            def reports(self):
                return self

            def query(self, **kw):
                raise RuntimeError("HttpError 500")
        monkeypatch.setattr(fya, "_FAILED_QUERIES", [])
        assert fya._retention_curve(_Boom(), "v1", "2026-10-01", "2026-11-03") == []
        assert fya._FAILED_QUERIES == []


class TestReachFileCarriesHold5ByAge:
    CURVE = [{"t": 0.0, "ratio": 1.0}, {"t": 0.05, "ratio": 0.62}, {"t": 0.1, "ratio": 0.5},
             {"t": 0.25, "ratio": 0.31}, {"t": 0.5, "ratio": 0.2}]

    def _snap(self, generated, rows):
        return {"generated": generated + "T19:00:00+00:00",
                "channels": {"en": {"day_series": [{"day": generated, "views": 1}]}},
                "shows": {"x": {"videos": rows}}}

    def _row(self, vid, kind, fetched_at, views=10):
        return {"video_id": vid, "published": "2026-10-31", "views": views, "channel": "en",
                "kind": kind, "show_slug": "tesla", "subscribers_gained": 0,
                "average_view_percentage": 5.0, "average_view_duration_s": 40,
                "retention_curve": self.CURVE, "curve_fetched_at": fetched_at}

    def test_long_gets_hold_at_age_short_never(self):
        reach = ter.load_reach(Path("/nonexistent/reach.json"))
        snap = self._snap("2026-11-03", [self._row("L", "long", "2026-11-03"),
                                         self._row("S", "short", "2026-11-03")])
        ter.merge_snapshot(reach, snap)
        assert reach["videos"]["L"]["hold5_by_age"] == {"3": 0.62}
        assert reach["videos"]["L"]["hold25_by_age"] == {"3": 0.31}
        assert "hold5_by_age" not in reach["videos"]["S"]
        assert "hold25_by_age" not in reach["videos"]["S"]

    def test_a_carried_forward_curve_is_never_read_as_fresh(self):
        reach = ter.load_reach(Path("/nonexistent/reach.json"))
        snap = self._snap("2026-11-03", [self._row("L", "long", "2026-11-01"),
                                         self._row("M", "long", None)])
        ter.merge_snapshot(reach, snap)
        assert reach["videos"]["L"]["views_by_age"] == {"3": 10}
        assert "hold5_by_age" not in reach["videos"]["L"]
        assert "hold5_by_age" not in reach["videos"]["M"]

    def test_first_observation_wins(self):
        reach = ter.load_reach(Path("/nonexistent/reach.json"))
        ter.merge_snapshot(reach, self._snap("2026-11-03", [self._row("L", "long", "2026-11-03")]))
        later = self._row("L", "long", "2026-11-03")
        later["retention_curve"] = [{"t": 0.05, "ratio": 0.1}, {"t": 0.25, "ratio": 0.05}]
        ter.merge_snapshot(reach, self._snap("2026-11-03", [later]))
        assert reach["videos"]["L"]["hold5_by_age"] == {"3": 0.62}
        nxt = self._row("L", "long", "2026-11-04")
        ter.merge_snapshot(reach, self._snap("2026-11-04", [nxt]))
        assert set(reach["videos"]["L"]["hold5_by_age"]) == {"3", "4"}


class TestDashboardReadsTheNewKeys:
    GEN = "2026-11-03T23:48:00+00:00"

    def _root(self, tmp_path, *, stats_channels=None, shows=None, reach=None, policy=None):
        (tmp_path / "api").mkdir()
        (tmp_path / "digests").mkdir()
        (tmp_path / "api" / "youtube_stats.json").write_text(json.dumps({
            "generated": self.GEN,
            "channels": stats_channels if stats_channels is not None else {"en": {"day_series": []}},
            "shows": shows or {}}), encoding="utf-8")
        if reach is not None:
            (tmp_path / "api" / "youtube_early_reach.json").write_text(
                json.dumps({"schema_version": 1, "updated": "2026-11-03", "videos": reach}),
                encoding="utf-8")
        if policy is not None:
            (tmp_path / "api" / "youtube_policy.json").write_text(json.dumps(policy), encoding="utf-8")
        return tmp_path

    def test_rss_copies_count_is_null_when_the_read_is_absent(self, tmp_path):
        m = gd._experiment_live_metrics(self._root(tmp_path))
        for ch in ("en", "ru", "fr"):
            assert m[f"youtube_rss_copies_14d_{ch}"] is None

    def test_rss_copies_count_reads_the_window(self, tmp_path):
        ch = {"en": {"day_series": [], "unindexed_recent_count": 4, "unindexed_recent": [
            {"video_id": "a", "kind": "rss_copy", "published": "2026-11-01", "show_slug": "tesla"},
            {"video_id": "b", "kind": "rss_copy", "published": "2026-10-01", "show_slug": "tesla"},
            {"video_id": "c", "published": "2026-11-01"},
            {"video_id": "d", "kind": "rss_copy", "published": "2026-10-25", "show_slug": "spacex"},
        ]}, "ru": {"day_series": [], "unindexed_recent": [], "unindexed_recent_count": 0}}
        m = gd._experiment_live_metrics(self._root(tmp_path, stats_channels=ch))
        assert m["youtube_rss_copies_14d_en"] == 2
        assert m["youtube_rss_copies_14d_ru"] == 0
        assert m["youtube_rss_copies_14d_fr"] is None

    def test_hold5_at_age7_and_d3_medians_per_channel(self, tmp_path):
        reach = {}
        for i in range(10):
            reach[f"L{i}"] = {"published": "2026-10-20", "channel": "en", "kind": "long",
                              "show": "tesla", "window": "", "variant": "",
                              "views_by_age": {"7": 20 + i}, "subs_by_age": {},
                              "hold5_by_age": {"7": 0.40 + i / 100}}
        for ch in ("ru", "fr"):
            for i in range(10):
                reach[f"{ch}S{i}"] = {"published": "2026-11-01", "channel": ch, "kind": "short",
                                      "show": "tesla", "window": "hook_open", "variant": "",
                                      "views_by_age": {"3": 100 + i}, "subs_by_age": {}}
        for i in range(10):
            reach[f"enL{i}"] = {"published": "2026-11-01", "channel": "en", "kind": "long",
                                "show": "tesla", "window": "", "variant": "",
                                "views_by_age": {"3": 7 + i}, "subs_by_age": {}}
        m = gd._experiment_live_metrics(self._root(tmp_path, reach=reach))
        assert m["long_hold5_age7_median_en"] == 0.45
        assert m["long_d3_median_en_7d"] == 12
        assert m["short_reach_d3_median_ru_7d"] == 105
        assert m["short_reach_d3_median_fr_7d"] == 105

    def test_keys_are_null_without_data_never_zero(self, tmp_path):
        m = gd._experiment_live_metrics(self._root(tmp_path))
        for k in ("long_hold5_age7_median_en", "long_d3_median_en_7d",
                  "short_reach_d3_median_ru_7d", "short_reach_d3_median_fr_7d"):
            assert m[k] is None

    def test_open_cliff_card_groups_longs_by_show_and_keeps_shorts_out(self, tmp_path):
        curve = [{"t": 0.05, "ratio": 0.6}, {"t": 0.1, "ratio": 0.5},
                 {"t": 0.25, "ratio": 0.3}, {"t": 0.5, "ratio": 0.2}]
        shows = {"tesla_shorts_time": {"videos": [
            {"video_id": "a", "kind": "long", "channel": "en", "episode": 1, "views": 5,
             "published": "2026-11-01", "retention_curve": curve},
            {"video_id": "b", "kind": "long", "channel": "en", "episode": 2, "views": 9,
             "published": "2026-10-30", "retention_curve": curve},
            {"video_id": "old", "kind": "long", "channel": "en", "episode": 3, "views": 90,
             "published": "2026-09-01", "retention_curve": curve},
            {"video_id": "s", "kind": "short", "channel": "en", "episode": 2, "views": 900,
             "published": "2026-11-01", "retention_curve": [{"t": 0.05, "ratio": 0.99}]},
        ]}}
        sec = gd.build_retention_curves_section(self._root(tmp_path, shows=shows))
        assert sec["configured"] is True and sec["window_days"] == 14
        assert sec["by_show"] == [{"show": "tesla_shorts_time", "channel": "en", "n": 2,
                                   "hold5_median": 0.6, "hold25_median": 0.3}]
        assert {r["episode"] for r in sec["videos"]} == {1, 2, 3}
        assert sec["mean_hold_5pct_by_channel"] == {"en": 0.6}
        m = gd._experiment_live_metrics(tmp_path)
        assert m["long_open_hold_5pct_en"] == 0.6   # the Short's 0.99 never pools

    def test_scorecard_analytics_rows_exclude_the_copies(self, tmp_path):
        shows = {"tesla_shorts_time": {"videos": [
            {"video_id": "a", "kind": "long", "channel": "en", "published": "2026-10-28", "views": 5},
            {"video_id": "c", "kind": "rss_copy", "channel": "en", "published": "2026-10-28", "views": 50},
        ]}}
        root = self._root(tmp_path, shows=shows,
                          stats_channels={"en": {"subscribers": 1, "day_series": []}})
        (root / "digests" / "tesla_shorts_time").mkdir()
        (root / "digests" / "tesla_shorts_time" / "youtube_videos.json").write_text(json.dumps({
            "videos": [{"video_id": "a", "kind": "long", "channel": "en", "published": "2026-10-28"}]}),
            encoding="utf-8")
        sc = gd.build_channel_scorecard(root)
        en = sc["channels"]["en"]
        assert en["uploads_14d"] == 1 and en["analytics_rows_14d"] == 1
        assert en["views_per_video_14d"] == {"long": {"n": 1, "views_per_video": 5.0}}


class TestNightlyWarnsOnCopiesBesideARender:
    def _payload(self):
        return {"channels": {"en": {"unindexed_recent_count": 3, "unindexed_recent": [
            {"video_id": "a", "kind": "rss_copy", "show_slug": "tesla", "published": "2026-11-01"},
            {"video_id": "b", "kind": "rss_copy", "show_slug": "planetterrian", "published": "2026-11-01"},
            {"video_id": "c", "published": "2026-11-01"}]},
            "ru": {"unindexed_recent": [], "unindexed_recent_count": 0},
            "fr": {}}}

    def test_warning_only_for_a_show_whose_long_form_is_on(self):
        policy = {"channels": {"en": {"tesla": {"publish_long_form": True},
                                      "planetterrian": {"publish_long_form": False}}}}
        lines = fya.rss_copy_warnings(self._payload(), policy)
        warns = [l for l in lines if l.startswith("::warning::")]
        assert len(warns) == 1 and "tesla on en: 1 RSS-ingested copy" in warns[0]
        notices = [l for l in lines if l.startswith("::notice::")]
        assert len(notices) == 1 and "channel en: 3 upload(s)" in notices[0]
        assert "2 attributed" in notices[0]

    def test_no_policy_and_no_read_are_quiet(self):
        lines = fya.rss_copy_warnings(self._payload(), None)
        assert not any(l.startswith("::warning::") for l in lines)
        assert fya.rss_copy_warnings({"channels": {"en": {}}}, {"channels": {}}) == []

    def test_main_prints_the_warning(self, tmp_path, monkeypatch, capsys):
        out = tmp_path / "youtube_stats.json"
        payload = {"schema_version": 2, "generated": "2026-11-03T23:00:00+00:00",
                   "channels": {"en": {"subscribers": 1, "day_series": [{"day": "2026-11-01", "views": 1}],
                                       **self._payload()["channels"]["en"]}},
                   "shows": {"x": {"videos": [{"video_id": "v", "kind": "short", "channel": "en",
                                               "published": "2026-11-01", "views": 1}]}}}
        (tmp_path / "api").mkdir()
        (tmp_path / "api" / "youtube_policy.json").write_text(json.dumps(
            {"channels": {"en": {"tesla": {"publish_long_form": True}}}}), encoding="utf-8")
        monkeypatch.setattr(fya, "fetch", lambda *a, **k: payload)
        monkeypatch.setattr(fya, "_ROOT", tmp_path)
        monkeypatch.setattr(fya, "_CHANNEL_HISTORY_PATH", "history.json")
        monkeypatch.setattr(sys, "argv", ["fetch", "--out", "youtube_stats.json"])
        assert fya.main() == 0
        text = capsys.readouterr().out
        assert "::warning::YouTube RSS copies — tesla on en" in text
        assert json.loads(out.read_text(encoding="utf-8"))["channels"]["en"]["unindexed_recent_count"] == 3


class TestShortJobIsWrittenPerChannel:
    def test_release_schedule_docstring_names_the_keys(self):
        import engine.release_schedule as rs
        doc = " ".join((rs.__doc__ or "").split())
        assert "What each surface is for" in doc
        for key in ("short_subs_per_1k_views_14d_en", "long_d3_median_en_7d",
                    "short_reach_d3_median_<ch>_7d", "short_reach_d3_median_ru_7d",
                    "short_reach_d3_median_fr_7d"):
            assert key in doc, key
        assert "never on site sessions" in doc

    @pytest.mark.parametrize("rel", ["docs/youtube_feedback_loop.md", "docs/funnel.md"])
    def test_the_docs_carry_the_same_paragraph(self, rel):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "not a funnel stage for video" in text
        for key in ("short_subs_per_1k_views_14d_en", "long_d3_median_en_7d",
                    "short_reach_d3_median_<ch>_7d"):
            assert key in text, (rel, key)

    def test_podcast_directories_notes_the_ingestion(self):
        text = (ROOT / "docs" / "podcast_directories.md").read_text(encoding="utf-8")
        assert "rss_copy" in text and "YouTube Music: RSS synced" in text

    def test_the_new_keys_are_computable_live_metrics(self):
        computable = set(gd._experiment_live_metrics(ROOT).keys())
        for key in ("long_hold5_age7_median_en", "long_d3_median_en_7d",
                    "short_reach_d3_median_ru_7d", "short_reach_d3_median_fr_7d",
                    "youtube_rss_copies_14d_en", "youtube_rss_copies_14d_ru",
                    "youtube_rss_copies_14d_fr"):
            assert key in computable, key


class TestTheSnapshotAndItsCurvesShareOneDate:
    """Nov 3 2026: ``generated`` carries the date the fetch started on — the
    date every ``curve_fetched_at`` is stamped with — whatever the clock says
    at assembly. The reach file records a hold only from a curve fetched on
    the snapshot's own date, so a fetch that crossed UTC midnight had
    stamped two dates and lost every age-7 hold for the night. The fixture's
    frozen date is not the real clock's, which is exactly the crossing."""

    def test_generated_date_is_the_fetch_date(self, monkeypatch, tmp_path):
        _wire_fetch(monkeypatch, uploads=_uploads())
        payload = fya.fetch(tmp_path, 90, out_path=tmp_path / "none.json")
        assert payload["generated"][:10] == TODAY.isoformat()
        stamped = {v.get("curve_fetched_at") for sh in payload["shows"].values()
                   for v in sh["videos"] if v.get("retention_curve")}
        assert stamped == {TODAY.isoformat()}
        # The stamp still carries a clock time (freshness reads it).
        assert "T" in payload["generated"] and payload["generated"].endswith("+00:00")

