"""OP3: an unindexed feed is written, not skipped (Oct 1 2026).

The thirteen September launch-cohort shows were absent from
``api/op3_stats.json`` because OP3 answers 404 for a feed it has not
indexed and ``fetch_op3_stats`` wrote NOTHING for a ``None`` result —
"not indexed" was indistinguishable from "never fetched", and Mission
Control rendered them with the same "—" as a show that has no feed. The
language-feed loop had carried an explicit ``resolved: false`` marker
since Aug 15 2026; the show loop now mirrors it. Contract pinned here:

* the unresolved marker is written for a show OP3 cannot resolve, and a
  previously-resolved show that fails this run keeps its previous entry
  tagged ``not_refreshed_this_run``;
* every consumer of ``op3_stats["shows"]`` tolerates the marker — never
  a fabricated zero, never a crash: the dashboard audience section (and
  the benchmark / unit-economics joins built on it), the audience
  headline, the popular-episodes rail, the funnel's reach stage, the
  performance trackers, the review snapshot;
* the headline keeps ``shows_measured`` to resolved shows and names the
  rest in ``shows_unindexed``; the page renders "not indexed".

No network call is made anywhere in this file.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts import build_audience_headline as ah  # noqa: E402
from scripts import fetch_op3_stats as mod  # noqa: E402
from scripts import generate_dashboard as gd  # noqa: E402

_RESOLVED = {
    "show_uuid": "u-tesla", "feed_url": "https://nerranetwork.com/podcast.rss",
    "asof": "2026-10-01", "downloads_7d": 149, "downloads_30d": 616,
    "weekly_avg": 150, "weekly_downloads": [120, 140, 150, 60],
    "episodes": [{"title": "Tesla Shorts Time Ep 620: Big ep", "item_guid": "g",
                  "pubdate": "2026-09-20T08:00:00.000Z", "downloads_3d": 5,
                  "downloads_7d": 12, "downloads_30d": 20, "downloads_all_time": 20}],
}
_UNINDEXED = mod.unresolved_show_entry(
    "ai_chips_podcast.rss", "https://nerranetwork.com/ai_chips_podcast.rss")
# The shape the task describes — a marker with NO download keys at all.
_BARE_MARKER = {"resolved": False, "note": "OP3 has no record of this feed yet",
                "rss_file": "mag7_podcast.rss"}


def _fixture() -> dict:
    return {
        "fetched_at": "2026-10-01T16:45:00+00:00",
        "shows": {"tesla": dict(_RESOLVED), "ai_chips": dict(_UNINDEXED),
                  "mag7": dict(_BARE_MARKER)},
        "language_feeds": {},
    }


def _seed(tmp_path: Path) -> Path:
    (tmp_path / "api").mkdir(exist_ok=True)
    (tmp_path / "api" / "op3_stats.json").write_text(
        json.dumps(_fixture()), encoding="utf-8")
    return tmp_path


class TestMarkerIsWritten:
    def test_unresolved_entry_shape(self):
        assert _UNINDEXED["resolved"] is False
        assert _UNINDEXED["downloads_7d"] is None and _UNINDEXED["downloads_30d"] is None
        assert "not indexed via Podcast Index" in _UNINDEXED["note"]
        assert _UNINDEXED["rss_file"] == "ai_chips_podcast.rss"
        assert mod.is_resolved_show_entry(_UNINDEXED) is False
        assert mod.is_resolved_show_entry(_BARE_MARKER) is False
        assert mod.is_resolved_show_entry(_RESOLVED) is True
        assert mod.is_resolved_show_entry(None) is False

    def test_main_writes_marker_and_keeps_previous_on_failure(self, tmp_path, monkeypatch):
        """Every real show YAML is iterated; the fake fetch resolves only
        tesla. A show that resolved LAST run but fails this run keeps its
        reading (flagged); one that never resolved gets the marker."""
        out = tmp_path / "op3.json"
        out.write_text(json.dumps({
            "shows": {"spacex": {**_RESOLVED, "show_uuid": "u-spacex", "downloads_30d": 42}},
            "language_feeds": {},
        }), encoding="utf-8")
        monkeypatch.setenv("OP3_API_TOKEN", "t")
        monkeypatch.setattr(mod.time, "sleep", lambda *_: None)
        monkeypatch.setattr(mod, "_language_feed_targets", lambda root: [])

        def _fake(slug, feed_url, token, cached):
            if slug == "tesla":
                return {**_RESOLVED, "feed_url": feed_url}
            return None  # 404 / transport failure — OP3 could not resolve it
        monkeypatch.setattr(mod, "_fetch_show_stats", _fake)

        assert mod.main(["--out", str(out),
                         "--popular-out", str(tmp_path / "pop.json")]) == 0
        shows = json.loads(out.read_text())["shows"]
        assert shows["tesla"]["downloads_30d"] == 616
        assert "not_refreshed_this_run" not in shows["tesla"]
        # Previously resolved, failed now: kept and flagged, NOT a marker.
        assert shows["spacex"]["downloads_30d"] == 42
        assert shows["spacex"]["not_refreshed_this_run"] is True
        assert shows["spacex"].get("resolved") is not False
        # Every cohort show is now PRESENT, as the unresolved marker.
        for slug in ("ai_chips", "mag7", "peptides", "longevity", "vancouver",
                     "collingwood", "prediction_markets", "omni_view_world",
                     "omni_view_north_america", "omni_view_europe",
                     "omni_view_asia_pacific", "omni_view_africa_mideast",
                     "omni_view_latam"):
            assert slug in shows, slug
            assert shows[slug]["resolved"] is False, slug
            assert shows[slug]["downloads_7d"] is None, slug
            assert shows[slug]["note"] == mod.UNINDEXED_NOTE
            assert shows[slug]["rss_file"].endswith(".rss")
        # A marker from the previous run is re-emitted fresh, never flagged stale.
        out.write_text(json.dumps({"shows": {"ai_chips": dict(_UNINDEXED)}}), encoding="utf-8")
        assert mod.main(["--out", str(out),
                         "--popular-out", str(tmp_path / "pop.json")]) == 0
        entry = json.loads(out.read_text())["shows"]["ai_chips"]
        assert entry["resolved"] is False and "not_refreshed_this_run" not in entry
        # The popular rail ignores markers.
        pop = json.loads((tmp_path / "pop.json").read_text())
        assert all(p["show_slug"] != "ai_chips" for p in pop)


class TestConsumersTolerateTheMarker:
    def test_popular_episodes_skip_markers(self, tmp_path):
        popular = mod.build_popular_episodes(_fixture(), tmp_path)
        assert {p["show_slug"] for p in popular} == {"tesla"}

    def test_dashboard_audience_section(self, tmp_path):
        sec = gd.build_audience_section(_seed(tmp_path))["op3"]
        assert sec["configured"] is True
        # Not a fabricated zero-download show: excluded from per_show...
        assert set(sec["per_show"]) == {"tesla"}
        assert sec["network_downloads_30d"] == 616
        assert sec["network_downloads_7d"] == 149
        # ...and NAMED, so the page can say "not indexed".
        assert sec["unindexed"] == ["ai_chips", "mag7"]
        assert sec["not_refreshed"] == []
        # The history ledger never saw the marker.
        hist = json.loads((tmp_path / "api" / "op3_history.json").read_text())
        assert all(set(row) == {"tesla"} for row in hist["weeks"].values())

    def test_dashboard_names_not_refreshed_shows(self, tmp_path):
        root = _seed(tmp_path)
        data = _fixture()
        data["shows"]["tesla"]["not_refreshed_this_run"] = True
        (root / "api" / "op3_stats.json").write_text(json.dumps(data), encoding="utf-8")
        sec = gd.build_audience_section(root)["op3"]
        assert sec["not_refreshed"] == ["tesla"]
        assert sec["per_show"]["tesla"]["downloads_30d"] == 616

    def test_downstream_dashboard_joins_still_build(self, tmp_path):
        """Benchmarks and unit economics join on op3.per_show — a marker
        there would have produced a 0-download placement and a null
        cost-per-download that LOOKS measured."""
        root = _seed(tmp_path)
        audience = gd.build_audience_section(root)
        costs = {"network_last_7_days": {"total": 10.0, "episodes": 7},
                 "per_show": {"tesla": {"last_7_days": {"total": 5.0}},
                              "ai_chips": {"last_7_days": {"total": 2.0}}}}
        eff = gd.build_efficiency_section(costs, audience)
        assert eff["per_show"]["tesla"]["op3_downloads_7d"] == 149
        assert eff["per_show"]["ai_chips"]["op3_downloads_7d"] == 0
        assert eff["per_show"]["ai_chips"]["usd_per_op3_download"] is None
        bm = gd.build_benchmarks_section(root, audience=audience, costs=costs,
                                         network={"shows": []})
        assert "ai_chips" not in (bm.get("per_show") or {}), (
            "an unindexed feed has no percentile placement")

    def test_audience_headline(self, tmp_path):
        doc = ah.build_headline(_seed(tmp_path), today=_dt.date(2026, 10, 1))
        n = doc["network"]
        assert n["shows_measured"] == 1
        assert n["shows_unindexed"] == ["ai_chips", "mag7"]
        assert n["downloads_30d"] == 616 and n["downloads_7d"] == 149
        for slug in ("ai_chips", "mag7"):
            e = doc["shows"][slug]
            assert e["downloads_7d"] is None and e["downloads_30d"] is None
            assert e["op3_unindexed"] is True
            assert e["first_week"] == {"median": None, "episodes": 0}
        assert "op3_unindexed" not in doc["shows"]["tesla"]
        assert "2 feed(s) not yet indexed by OP3" in ah.headline_line(doc)

    def test_headline_without_markers_has_empty_list(self, tmp_path):
        data = _fixture()
        data["shows"] = {"tesla": dict(_RESOLVED)}
        (tmp_path / "api").mkdir()
        (tmp_path / "api" / "op3_stats.json").write_text(json.dumps(data), encoding="utf-8")
        doc = ah.build_headline(tmp_path, today=_dt.date(2026, 10, 1))
        assert doc["network"]["shows_unindexed"] == []
        assert "not yet indexed" not in ah.headline_line(doc)

    def test_funnel_reach_leaves_downloads_null(self):
        from scripts.build_funnel import _reach
        reach = _reach(None, _fixture(), 30)
        assert reach["by_show"]["ai_chips"]["podcast_downloads_30d"] is None
        assert reach["by_show"]["mag7"]["podcast_downloads_30d"] is None
        assert reach["totals"]["podcast_downloads"] == 616

    def test_performance_trackers_are_a_no_op_on_a_marker(self, tmp_path):
        """update_performance_trackers passes shows[slug] straight through;
        a marker carries no episodes, so the tracker is left untouched."""
        from engine import show_memory, tesla_memory
        assert tesla_memory.update_performance_from_op3(tmp_path, dict(_UNINDEXED)) == 0
        assert tesla_memory.update_performance_from_op3(tmp_path, dict(_BARE_MARKER)) == 0
        cfg = show_memory.SHOW_MEMORY_CONFIGS["models_agents"]
        assert show_memory.update_performance_from_op3(tmp_path, cfg, dict(_UNINDEXED)) == 0
        assert not list(tmp_path.iterdir()), "nothing written for an unindexed feed"

    def test_review_snapshot_never_prints_a_zero(self):
        """review_snapshot renders shows[slug] keys verbatim — on a marker
        every download key is None (or absent), never 0."""
        src = (_ROOT / "scripts" / "review_snapshot.py").read_text(encoding="utf-8")
        assert "stats.get('downloads_7d')" in src
        assert _UNINDEXED.get("downloads_7d") is None
        assert _BARE_MARKER.get("downloads_7d") is None


class TestPageRendersNotIndexed:
    def test_show_card_and_rss_card(self):
        html = (_ROOT / "management.html").read_text(encoding="utf-8")
        assert "op3.unindexed" in html
        assert "not indexed" in html
        assert "Not yet indexed by OP3" in html
        # The show card's RSS stat branches on the marker before fmtOrDash,
        # so an unindexed show never reads "—" (that is "no feed").
        i = html.index("const unindexedRss")
        assert html.index("fmtOrDash(dl.downloads_7d)", i) > i

    def test_documented(self):
        doc = (_ROOT / "docs" / "analytics.md").read_text(encoding="utf-8")
        assert '"resolved": false' in doc
        assert "shows_unindexed" in doc
