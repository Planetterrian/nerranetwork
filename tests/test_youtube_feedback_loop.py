"""Drift guards for the recursive YouTube-feedback loop (June 2026).

Pieces under test:
  * engine.youtube_index.record_video — per-show video→episode index
    (per-show, NOT a shared file, to avoid concurrent push-contention).
  * engine.youtube.YOUTUBE_SCOPES carries yt-analytics.readonly.
  * engine.youtube_titles._performance_hint reads the per-show signal
    file and is a clean no-op when absent.
  * scripts/fetch_youtube_analytics.py + update_youtube_performance.py
    are clean no-ops with no data (the loop ships dormant).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine import youtube_index
from engine.youtube import YOUTUBE_SCOPES


def _load_script(name: str):
    path = _ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestNightlyPersistsLoopOutputs:
    """The nightly job PRODUCES api/youtube_stats.json + per-show
    youtube_performance.json but commits via an explicit add-paths allowlist.
    If the loop outputs aren't in that list they're generated then discarded —
    the loop can never persist (the bug found 2026-07-01)."""

    def test_add_paths_includes_loop_outputs(self):
        wf = (_ROOT / ".github" / "workflows" / "nightly-maintenance.yml").read_text(
            encoding="utf-8")
        # Both must appear in the workflow's commit allowlist.
        assert "api/youtube_stats.json" in wf
        assert "digests/**/youtube_performance.json" in wf


class TestScope:
    def test_analytics_scope_present(self):
        assert any("yt-analytics.readonly" in s for s in YOUTUBE_SCOPES), (
            "the feedback loop needs the analytics read scope"
        )

    def test_upload_scopes_still_present(self):
        # Re-auth must not drop the upload/publish scopes.
        joined = " ".join(YOUTUBE_SCOPES)
        assert "youtube.upload" in joined
        assert "youtube.force-ssl" in joined


class TestVideoIndex:
    def test_per_show_path_not_shared(self):
        p = youtube_index.index_path_for("tesla")
        assert p == Path("digests/tesla/youtube_videos.json")
        # Two shows must resolve to different files (no shared aggregate).
        assert youtube_index.index_path_for("spacex") != p

    def test_record_and_upsert(self, tmp_path):
        idx = tmp_path / "tesla" / "youtube_videos.json"
        assert youtube_index.record_video(
            video_id="v1", show_slug="tesla", episode=526, kind="long",
            title="A", index_path=idx)
        assert youtube_index.record_video(
            video_id="v1", show_slug="tesla", episode=526, kind="long",
            title="B", index_path=idx)  # upsert, no dup
        assert youtube_index.record_video(
            video_id="v2", show_slug="tesla", episode=526, kind="short",
            index_path=idx)
        data = json.loads(idx.read_text())
        ids = [v["video_id"] for v in data["videos"]]
        assert ids == ["v1", "v2"]
        assert data["videos"][0]["title"] == "B"  # upserted in place

    def test_empty_video_id_is_noop(self, tmp_path):
        idx = tmp_path / "x" / "youtube_videos.json"
        assert youtube_index.record_video(
            video_id="", show_slug="x", episode=1, kind="long",
            index_path=idx) is False
        assert not idx.exists()

    def test_corrupt_index_does_not_lose_new_row(self, tmp_path):
        idx = tmp_path / "x" / "youtube_videos.json"
        idx.parent.mkdir(parents=True)
        idx.write_text("{not json", encoding="utf-8")
        assert youtube_index.record_video(
            video_id="v9", show_slug="x", episode=1, kind="long", index_path=idx)
        data = json.loads(idx.read_text())
        assert [v["video_id"] for v in data["videos"]] == ["v9"]


class TestPerformanceHint:
    def test_no_file_is_empty(self, tmp_path):
        from engine.youtube_titles import _performance_hint
        assert _performance_hint(tmp_path) == ""  # dir exists, no perf file

    def test_none_dir_is_empty(self):
        from engine.youtube_titles import _performance_hint
        assert _performance_hint(None) == ""

    def test_reads_title_hint(self, tmp_path):
        import json
        from engine.youtube_titles import _performance_hint
        (tmp_path / "youtube_performance.json").write_text(
            json.dumps({"title_hint": "robotaxi retains best"}), encoding="utf-8")
        out = _performance_hint(tmp_path)
        assert "robotaxi retains best" in out
        assert "WHAT'S WORKING" in out


class TestUpdaterHint:
    def test_build_hint_needs_minimum_videos(self):
        uyp = _load_script("update_youtube_performance.py")
        vids = [{"title": "t", "hook": "h", "average_view_percentage": 50}] * 2
        assert uyp._build_hint(vids) == ""

    def test_build_hint_surfaces_keywords_and_median(self):
        uyp = _load_script("update_youtube_performance.py")
        vids = [
            {"title": "Tesla Robotaxi Launch Texas", "hook": "robotaxi",
             "average_view_percentage": 62},
            {"title": "Tesla Robotaxi Expands Cities", "hook": "robotaxi",
             "average_view_percentage": 58},
            {"title": "Tesla Semi Battery", "hook": "semi",
             "average_view_percentage": 40},
            {"title": "Tesla Earnings", "hook": "earnings",
             "average_view_percentage": 30},
            {"title": "Tesla FSD", "hook": "fsd",
             "average_view_percentage": 25},
        ]
        hint = uyp._build_hint(vids)
        assert "robotaxi" in hint.lower()
        assert "Median retention" in hint


class TestScriptsAreCleanNoOps:
    def test_fetch_no_data(self, tmp_path):
        fya = _load_script("fetch_youtube_analytics.py")
        # No per-show indexes under an empty digests dir → None (no-op).
        assert fya.fetch(tmp_path, days=90) is None
