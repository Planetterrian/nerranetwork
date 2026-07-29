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


class TestTitleVariantsRecorded:
    """run_show stashes the optimized title + its A/B candidates on the
    publish result; record_youtube_outcomes must persist them to metrics —
    otherwise the Studio 'Test & Compare' variants exist only in the
    Actions log (the gap found 2026-07-01)."""

    def _record(self, youtube_urls):
        from types import SimpleNamespace
        from engine.pipeline import record_youtube_outcomes
        recorded = {}
        metrics = SimpleNamespace(record=lambda k, v: recorded.__setitem__(k, v))
        cfg = SimpleNamespace(youtube=SimpleNamespace(enabled=True))
        record_youtube_outcomes(metrics, youtube_urls, 1.0, config=cfg)
        return recorded

    def test_title_and_variants_persisted(self):
        recorded = self._record({
            "long_url": "https://youtu.be/x",
            "youtube_title": "Tesla's Wireless BMS Explained",
            "youtube_title_variants": ["Tesla's Wireless BMS Explained",
                                       "Variant B", "Variant C"],
        })
        assert recorded["youtube_title"] == "Tesla's Wireless BMS Explained"
        assert recorded["youtube_title_variants"] == [
            "Tesla's Wireless BMS Explained", "Variant B", "Variant C"]

    def test_absent_title_records_nothing(self):
        recorded = self._record({"long_url": "https://youtu.be/x"})
        assert "youtube_title" not in recorded
        assert "youtube_title_variants" not in recorded

    def test_growth_pass_keys_persisted(self):
        # July 22 2026: fill/punch/comment layers had shipped invisibly —
        # the recorder dropped these three result keys.
        recorded = self._record({
            "long_url": "https://youtu.be/x",
            "shorts_fill_modes": ["qualified", "filled"],
            "thumbnail_punch_text": "FSD PROBE",
            "yt_comments_posted": 3,
        })
        assert recorded["shorts_fill_modes"] == ["qualified", "filled"]
        assert recorded["thumbnail_punch_text"] == "FSD PROBE"
        assert recorded["yt_comments_posted"] == 3

    def test_absent_growth_pass_keys_record_nothing(self):
        recorded = self._record({"long_url": "https://youtu.be/x"})
        for key in ("shorts_fill_modes", "thumbnail_punch_text",
                    "yt_comments_posted"):
            assert key not in recorded


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

    def test_build_hint_ignores_ru_channel_rows(self):
        # RU-dub retention must not skew the EN title hints or quote Russian
        # titles as exemplars in English prompts (the gap found 2026-07-01).
        uyp = _load_script("update_youtube_performance.py")
        en = [
            {"title": "Tesla Robotaxi Launch Texas", "hook": "robotaxi",
             "average_view_percentage": 62, "channel": "en"},
            {"title": "Tesla Robotaxi Expands Cities", "hook": "robotaxi",
             "average_view_percentage": 58},  # legacy row, no channel → en
            {"title": "Tesla Semi Battery", "hook": "semi",
             "average_view_percentage": 40, "channel": "en"},
            {"title": "Tesla Earnings", "hook": "earnings",
             "average_view_percentage": 30, "channel": "en"},
            {"title": "Tesla FSD", "hook": "fsd",
             "average_view_percentage": 25, "channel": "en"},
        ]
        ru = [{"title": "Робота́кси Теслы в Техасе", "hook": "роботакси",
               "average_view_percentage": 95, "channel": "ru"}] * 4
        hint = uyp._build_hint(en + ru)
        assert hint  # EN rows alone clear the minimum
        assert "Робота́кси" not in hint  # no Russian exemplar
        assert "роботакси" not in hint

    def test_build_hint_ru_only_is_empty(self):
        uyp = _load_script("update_youtube_performance.py")
        ru = [{"title": "Русский заголовок", "hook": "х",
               "average_view_percentage": 90, "channel": "ru"}] * 6
        assert uyp._build_hint(ru) == ""


class TestBothChannelsCovered:
    """The analytics loop must read BOTH the EN index (youtube_videos.json)
    and the @NerraRU dubs (youtube_videos.ru.json) — otherwise the RU channel
    is invisible to the loop (the gap found 2026-07-01)."""

    def test_load_index_includes_ru_dubs(self, tmp_path):
        fya = _load_script("fetch_youtube_analytics.py")
        show = tmp_path / "tesla_shorts_time"
        show.mkdir()
        (show / "youtube_videos.json").write_text(json.dumps({"videos": [
            {"video_id": "en1", "channel": "en"}]}), encoding="utf-8")
        (show / "youtube_videos.ru.json").write_text(json.dumps({"videos": [
            {"video_id": "ru1", "channel": "ru"}]}), encoding="utf-8")
        rows = fya._load_index(tmp_path)
        channels = {r.get("channel") for r in rows}
        assert channels == {"en", "ru"}, channels
        assert {r["video_id"] for r in rows} == {"en1", "ru1"}

    def test_fetch_propagates_channel_into_stats_rows(self, tmp_path, monkeypatch):
        # The assembled per-show stats rows must carry `channel` so the
        # performance updater can keep RU-dub retention out of EN hints.
        fya = _load_script("fetch_youtube_analytics.py")
        show = tmp_path / "tesla_shorts_time"
        show.mkdir()
        (show / "youtube_videos.json").write_text(json.dumps({"videos": [
            {"video_id": "en1"}]}), encoding="utf-8")  # legacy row, no channel
        (show / "youtube_videos.ru.json").write_text(json.dumps({"videos": [
            {"video_id": "ru1", "channel": "ru"}]}), encoding="utf-8")

        import engine.youtube as ey
        monkeypatch.setattr(ey, "get_channel_credentials_from_env",
                            lambda channel: object())
        monkeypatch.setattr(fya, "_analytics_service", lambda creds: object())
        monkeypatch.setattr(fya, "_query_batch", lambda svc, ids, s, e: {
            vid: {"views": 5, "estimatedMinutesWatched": 1.0,
                  "averageViewDuration": 30.0, "averageViewPercentage": 40.0}
            for vid in ids})
        payload = fya.fetch(tmp_path, days=30)
        rows = payload["shows"]["tesla_shorts_time"]["videos"]
        by_id = {r["video_id"]: r["channel"] for r in rows}
        assert by_id == {"en1": "en", "ru1": "ru"}  # missing channel → en


class TestScriptsAreCleanNoOps:
    def test_fetch_no_data(self, tmp_path):
        fya = _load_script("fetch_youtube_analytics.py")
        # No per-show indexes under an empty digests dir → None (no-op).
        assert fya.fetch(tmp_path, days=90) is None


class TestAnalytics403Classification:
    """July 2026: nightly 403 was 'API disabled', not missing scope —
    the warning must tell the operator which fix to apply."""

    def test_disabled_api_message(self, caplog):
        import logging
        from unittest.mock import MagicMock

        fya = _load_script("fetch_youtube_analytics.py")
        svc = MagicMock()
        svc.reports.return_value.query.return_value.execute.side_effect = (
            RuntimeError(
                "HttpError 403 … YouTube Analytics API has not been used "
                "in project 141610975484 before or it is disabled"
            )
        )
        with caplog.at_level(logging.WARNING):
            assert fya._query_batch(svc, ["vid1"], "2026-01-01", "2026-07-09") == {}
        joined = " ".join(r.message for r in caplog.records)
        assert "Enable" in joined or "enable" in joined
        assert "YouTube Analytics API" in joined
        assert "re-run scripts/youtube_oauth_bootstrap" not in joined

    def test_missing_scope_message(self, caplog):
        import logging
        from unittest.mock import MagicMock

        fya = _load_script("fetch_youtube_analytics.py")
        svc = MagicMock()
        svc.reports.return_value.query.return_value.execute.side_effect = (
            RuntimeError("HttpError 403 insufficient authentication scopes")
        )
        with caplog.at_level(logging.WARNING):
            assert fya._query_batch(svc, ["vid1"], "2026-01-01", "2026-07-09") == {}
        joined = " ".join(r.message for r in caplog.records)
        assert "yt-analytics.readonly" in joined
        assert "youtube_oauth_bootstrap" in joined


class TestEveryDubChannelEntersTheLoop:
    """@NerraFR went live 2026-07-23 and published 39 videos that the
    analytics fetch never saw: only ``.ru.json`` had been added beside
    the base index, so the glob missed ``.fr.json`` entirely.

    The blind spot was not cosmetic. The adaptive policy computed
    ``video_count_14d = 0`` for all four FR shows and held them at their
    seed tier — a channel that could never earn a promotion however well
    it performed — and the title hints, subscriber attribution and
    gallery-retention join were blind for the same reason. Matching the
    language indexes by pattern means the next channel is covered on the
    day it launches."""

    def test_language_indexes_are_globbed_not_listed(self):
        src = (_ROOT / "scripts" / "fetch_youtube_analytics.py").read_text(
            encoding="utf-8")
        assert 'digests_dir.glob("*/youtube_videos.*.json")' in src
        # A hardcoded per-language line is what caused the miss.
        assert 'glob("*/youtube_videos.ru.json")' not in src

    def test_the_two_patterns_do_not_overlap(self):
        """The base index must be collected exactly once — a double read
        would duplicate every EN row and inflate its view totals."""
        import fnmatch

        assert not fnmatch.fnmatch("youtube_videos.json", "youtube_videos.*.json")
        assert fnmatch.fnmatch("youtube_videos.fr.json", "youtube_videos.*.json")
        assert fnmatch.fnmatch("youtube_videos.ru.json", "youtube_videos.*.json")

    def test_live_fr_rows_are_picked_up(self):
        """Guards the real repo state, not just the pattern."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "_fya", _ROOT / "scripts" / "fetch_youtube_analytics.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        rows = mod._load_index(_ROOT / "digests")
        channels = {r.get("channel") or "en" for r in rows}
        if (_ROOT / "digests").glob("*/youtube_videos.fr.json"):
            assert "fr" in channels or not any(
                (_ROOT / "digests").glob("*/youtube_videos.fr.json"))
