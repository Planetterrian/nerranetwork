"""Tests for skip marker logic in run_show.py and review_episodes.py."""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest

from review_episodes import (
    Issue,
    EpisodeReview,
    SHOW_REGISTRY,
    _read_skip_marker,
    _should_run_on,
    check_missed_episodes,
)


# ---------------------------------------------------------------------------
# _should_run_on
# ---------------------------------------------------------------------------


class TestShouldRunOn:
    def test_daily_always(self):
        assert _should_run_on("daily", datetime.date(2026, 4, 13)) is True
        assert _should_run_on("daily", datetime.date(2026, 4, 14)) is True

    def test_odd_day(self):
        assert _should_run_on("odd", datetime.date(2026, 4, 13)) is True  # day=13
        assert _should_run_on("odd", datetime.date(2026, 4, 14)) is False  # day=14

    def test_even_day(self):
        assert _should_run_on("even", datetime.date(2026, 4, 14)) is True  # day=14
        assert _should_run_on("even", datetime.date(2026, 4, 13)) is False  # day=13

    def test_weekday(self):
        # 2026-04-13 is Monday
        assert _should_run_on("weekday", datetime.date(2026, 4, 13)) is True
        # 2026-04-12 is Sunday
        assert _should_run_on("weekday", datetime.date(2026, 4, 12)) is False

    def test_odd_weekday(self):
        # 2026-04-13: day=13 (odd), Monday (weekday) → True
        assert _should_run_on("odd_weekday", datetime.date(2026, 4, 13)) is True
        # 2026-04-14: day=14 (even), Tuesday → False
        assert _should_run_on("odd_weekday", datetime.date(2026, 4, 14)) is False
        # 2026-04-11: day=11 (odd), Saturday → False
        assert _should_run_on("odd_weekday", datetime.date(2026, 4, 11)) is False


# ---------------------------------------------------------------------------
# _read_skip_marker
# ---------------------------------------------------------------------------


class TestReadSkipMarker:
    def test_reads_valid_marker(self, tmp_path):
        marker_data = {
            "date": "2026-04-13",
            "show": "tesla",
            "show_name": "Tesla Shorts Time",
            "reason": "insufficient_articles",
            "detail": "Only 2 articles found.",
        }
        marker_file = tmp_path / ".skip_20260413.json"
        marker_file.write_text(json.dumps(marker_data))

        # _read_skip_marker expects output_dir relative to PROJECT_ROOT,
        # so we monkeypatch PROJECT_ROOT for testing
        import review_episodes
        orig = review_episodes.PROJECT_ROOT
        try:
            review_episodes.PROJECT_ROOT = tmp_path.parent
            result = _read_skip_marker(tmp_path.name, datetime.date(2026, 4, 13))
        finally:
            review_episodes.PROJECT_ROOT = orig

        assert result is not None
        assert result["reason"] == "insufficient_articles"
        assert result["show"] == "tesla"

    def test_returns_none_when_missing(self, tmp_path):
        import review_episodes
        orig = review_episodes.PROJECT_ROOT
        try:
            review_episodes.PROJECT_ROOT = tmp_path.parent
            result = _read_skip_marker(tmp_path.name, datetime.date(2026, 4, 13))
        finally:
            review_episodes.PROJECT_ROOT = orig

        assert result is None

    def test_returns_none_on_invalid_json(self, tmp_path):
        marker_file = tmp_path / ".skip_20260413.json"
        marker_file.write_text("not valid json{{{")

        import review_episodes
        orig = review_episodes.PROJECT_ROOT
        try:
            review_episodes.PROJECT_ROOT = tmp_path.parent
            result = _read_skip_marker(tmp_path.name, datetime.date(2026, 4, 13))
        finally:
            review_episodes.PROJECT_ROOT = orig

        assert result is None


# ---------------------------------------------------------------------------
# check_missed_episodes — with and without skip markers
# ---------------------------------------------------------------------------


class TestCheckMissedEpisodes:
    def test_no_missed_when_episode_exists(self):
        """A show with output should not be flagged."""
        target = datetime.date(2026, 4, 13)
        found = [
            EpisodeReview(
                show_slug="tesla",
                show_name="Tesla Shorts Time",
                episode_num=435,
                date="2026-04-13",
            )
        ]
        issues = check_missed_episodes(target, found, show_filter="tesla")
        assert len(issues) == 0

    def test_critical_when_no_output_and_no_marker(self, tmp_path):
        """A missed show with no skip marker → critical."""
        target = datetime.date(2026, 4, 13)
        found: list[EpisodeReview] = []

        # Point to tmp_path so no marker file exists
        import review_episodes
        orig = review_episodes.PROJECT_ROOT
        orig_registry = review_episodes.SHOW_REGISTRY.copy()
        try:
            review_episodes.PROJECT_ROOT = tmp_path
            # Create a minimal test registry
            review_episodes.SHOW_REGISTRY = {
                "tesla": {
                    "name": "Tesla Shorts Time",
                    "output_dir": "digests/tesla_shorts_time",
                    "prefix": "Tesla_Shorts_Time_Pod",
                    "schedule": "daily",
                    "min_digest_chars": 3000,
                    "max_digest_chars": 20000,
                    "min_tts_words": 2200,
                    "min_audio_s": 300,
                    "max_audio_s": 1800,
                    "required_sections": [],
                },
            }
            issues = check_missed_episodes(target, found, show_filter="tesla")
        finally:
            review_episodes.PROJECT_ROOT = orig
            review_episodes.SHOW_REGISTRY = orig_registry

        assert len(issues) == 1
        assert issues[0].severity == "critical"
        assert "Missed episode" in issues[0].title

    def test_warning_when_skip_marker_exists(self, tmp_path):
        """A skipped show with a marker → warning (not critical)."""
        target = datetime.date(2026, 4, 13)
        found: list[EpisodeReview] = []

        # Create the output dir with a skip marker
        output_dir = tmp_path / "digests" / "tesla_shorts_time"
        output_dir.mkdir(parents=True)
        marker = {
            "date": "2026-04-13",
            "show": "tesla",
            "show_name": "Tesla Shorts Time",
            "reason": "insufficient_articles",
            "detail": "Only 2 articles found — below minimum threshold (6).",
        }
        (output_dir / ".skip_20260413.json").write_text(json.dumps(marker))

        import review_episodes
        orig = review_episodes.PROJECT_ROOT
        orig_registry = review_episodes.SHOW_REGISTRY.copy()
        try:
            review_episodes.PROJECT_ROOT = tmp_path
            review_episodes.SHOW_REGISTRY = {
                "tesla": {
                    "name": "Tesla Shorts Time",
                    "output_dir": "digests/tesla_shorts_time",
                    "prefix": "Tesla_Shorts_Time_Pod",
                    "schedule": "daily",
                    "min_digest_chars": 3000,
                    "max_digest_chars": 20000,
                    "min_tts_words": 2200,
                    "min_audio_s": 300,
                    "max_audio_s": 1800,
                    "required_sections": [],
                },
            }
            issues = check_missed_episodes(target, found, show_filter="tesla")
        finally:
            review_episodes.PROJECT_ROOT = orig
            review_episodes.SHOW_REGISTRY = orig_registry

        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert "Skipped episode" in issues[0].title
        assert "insufficient_articles" in issues[0].title
        assert "intentionally skipped" in issues[0].detail

    def test_skip_marker_reason_in_detail(self, tmp_path):
        """Skip marker detail text should appear in the issue detail."""
        target = datetime.date(2026, 4, 13)
        found: list[EpisodeReview] = []

        output_dir = tmp_path / "digests" / "tesla_shorts_time"
        output_dir.mkdir(parents=True)
        marker = {
            "date": "2026-04-13",
            "show": "tesla",
            "show_name": "Tesla Shorts Time",
            "reason": "audio_too_short",
            "detail": "Audio too short (180s < 300s minimum).",
        }
        (output_dir / ".skip_20260413.json").write_text(json.dumps(marker))

        import review_episodes
        orig = review_episodes.PROJECT_ROOT
        orig_registry = review_episodes.SHOW_REGISTRY.copy()
        try:
            review_episodes.PROJECT_ROOT = tmp_path
            review_episodes.SHOW_REGISTRY = {
                "tesla": {
                    "name": "Tesla Shorts Time",
                    "output_dir": "digests/tesla_shorts_time",
                    "prefix": "Tesla_Shorts_Time_Pod",
                    "schedule": "daily",
                    "min_digest_chars": 3000,
                    "max_digest_chars": 20000,
                    "min_tts_words": 2200,
                    "min_audio_s": 300,
                    "max_audio_s": 1800,
                    "required_sections": [],
                },
            }
            issues = check_missed_episodes(target, found, show_filter="tesla")
        finally:
            review_episodes.PROJECT_ROOT = orig
            review_episodes.SHOW_REGISTRY = orig_registry

        assert len(issues) == 1
        assert "Audio too short" in issues[0].detail

    def test_not_scheduled_not_flagged(self):
        """A show not scheduled for the target date should not be flagged."""
        # Day 13 is odd — finansy_prosto (even schedule) should not be flagged
        target = datetime.date(2026, 4, 13)
        found: list[EpisodeReview] = []
        issues = check_missed_episodes(target, found, show_filter="finansy_prosto")
        assert len(issues) == 0
