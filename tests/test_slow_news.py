"""Tests for engine.slow_news module — Slow News Day handling."""

import json
import datetime
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Minimal config stubs for testing (avoid importing the real ShowConfig which
# pulls in YAML and other dependencies we don't need here).
# ---------------------------------------------------------------------------

@dataclass
class _SlowNewsConfig:
    enabled: bool = False
    library_file: str = ""
    max_segments: int = 2
    cooldown_days: int = 30
    selection_mode: str = "round_robin"


@dataclass
class _FakeConfig:
    min_articles_skip: int = 3
    slow_news: _SlowNewsConfig = field(default_factory=_SlowNewsConfig)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_library(tmp_path):
    """Create a sample segment library JSON and return its path."""
    data = {
        "show": "Test Show",
        "segments": [
            {
                "id": "seg_alpha",
                "type": "deep_dive",
                "title": "Alpha Topic",
                "prompt_template": "Write about alpha for {today_str}.",
                "estimated_words": 500,
                "tags": ["test"],
            },
            {
                "id": "seg_beta",
                "type": "profile",
                "title": "Beta Profile",
                "prompt_template": "Write a profile about beta.",
                "estimated_words": 400,
                "tags": ["test"],
            },
            {
                "id": "seg_gamma",
                "type": "historical",
                "title": "Gamma History",
                "prompt_template": "Write about the history of gamma.",
                "estimated_words": 600,
                "tags": ["test"],
            },
            {
                "id": "seg_delta",
                "type": "utility",
                "title": "Delta How-To",
                "prompt_template": "Write a how-to guide for delta.",
                "estimated_words": 500,
                "tags": ["test"],
            },
        ],
    }
    lib_path = tmp_path / "test_segments.json"
    lib_path.write_text(json.dumps(data), encoding="utf-8")
    return str(lib_path)


# ---------------------------------------------------------------------------
# is_slow_news_day
# ---------------------------------------------------------------------------

class TestIsSlowNewsDay:
    def test_enabled_below_threshold(self):
        from engine.slow_news import is_slow_news_day

        config = _FakeConfig(
            min_articles_skip=3,
            slow_news=_SlowNewsConfig(enabled=True),
        )
        assert is_slow_news_day(2, config) is True

    def test_enabled_at_threshold(self):
        from engine.slow_news import is_slow_news_day

        config = _FakeConfig(
            min_articles_skip=3,
            slow_news=_SlowNewsConfig(enabled=True),
        )
        # At threshold = not below, so False
        assert is_slow_news_day(3, config) is False

    def test_disabled(self):
        from engine.slow_news import is_slow_news_day

        config = _FakeConfig(
            min_articles_skip=3,
            slow_news=_SlowNewsConfig(enabled=False),
        )
        assert is_slow_news_day(1, config) is False

    def test_zero_articles(self):
        from engine.slow_news import is_slow_news_day

        config = _FakeConfig(
            min_articles_skip=3,
            slow_news=_SlowNewsConfig(enabled=True),
        )
        # Zero articles should still skip entirely
        assert is_slow_news_day(0, config) is False

    def test_above_threshold(self):
        from engine.slow_news import is_slow_news_day

        config = _FakeConfig(
            min_articles_skip=3,
            slow_news=_SlowNewsConfig(enabled=True),
        )
        assert is_slow_news_day(5, config) is False


# ---------------------------------------------------------------------------
# load_segment_library
# ---------------------------------------------------------------------------

class TestLoadSegmentLibrary:
    def test_loads_valid_library(self, sample_library):
        from engine.slow_news import load_segment_library

        segments = load_segment_library(sample_library)
        assert len(segments) == 4
        assert segments[0]["id"] == "seg_alpha"

    def test_missing_file(self, tmp_path):
        from engine.slow_news import load_segment_library

        with pytest.raises(FileNotFoundError):
            load_segment_library(str(tmp_path / "nonexistent.json"))

    def test_missing_required_key(self, tmp_path):
        from engine.slow_news import load_segment_library

        bad_data = {
            "segments": [
                {"id": "seg_bad", "type": "deep_dive"},  # missing title, prompt_template, estimated_words
            ]
        }
        bad_path = tmp_path / "bad.json"
        bad_path.write_text(json.dumps(bad_data), encoding="utf-8")
        with pytest.raises(ValueError, match="missing required keys"):
            load_segment_library(str(bad_path))

    def test_no_segments_key(self, tmp_path):
        from engine.slow_news import load_segment_library

        bad_data = {"show": "Test"}
        bad_path = tmp_path / "no_segs.json"
        bad_path.write_text(json.dumps(bad_data), encoding="utf-8")
        with pytest.raises(ValueError, match="segments"):
            load_segment_library(str(bad_path))

    def test_empty_segments_list(self, tmp_path):
        from engine.slow_news import load_segment_library

        bad_data = {"segments": []}
        bad_path = tmp_path / "empty.json"
        bad_path.write_text(json.dumps(bad_data), encoding="utf-8")
        with pytest.raises(ValueError, match="non-empty"):
            load_segment_library(str(bad_path))

    def test_empty_path_raises_clear_error(self):
        # July 21 2026 (SpaceX ep039): slow_news.enabled with the empty
        # library_file default resolved Path("") to the project root and
        # crashed the fallback with IsADirectoryError. Must fail with an
        # actionable message instead.
        from engine.slow_news import load_segment_library

        with pytest.raises(FileNotFoundError, match="library_file is empty"):
            load_segment_library("")
        with pytest.raises(FileNotFoundError, match="library_file is empty"):
            load_segment_library("   ")

    def test_directory_path_raises_clear_error(self, tmp_path):
        from engine.slow_news import load_segment_library

        with pytest.raises(FileNotFoundError, match="directory"):
            load_segment_library(str(tmp_path))


# ---------------------------------------------------------------------------
# Drift guard: every show that enables slow_news must ship a valid library
# (SpaceX launched June 13 2026 with enabled: true and no library_file —
# the misconfiguration sat dormant until the first day the fallback fired,
# then killed the episode instead of rescuing it)
# ---------------------------------------------------------------------------

_SHOWS_DIR = Path(__file__).resolve().parent.parent / "shows"


class TestSlowNewsConfigDriftGuard:
    def _show_yamls(self):
        return sorted(
            p for p in _SHOWS_DIR.glob("*.yaml")
            if not p.name.startswith("_")
        )

    def test_every_enabled_show_has_loadable_library(self):
        from engine.config import load_config
        from engine.slow_news import load_segment_library

        checked = 0
        for yaml_path in self._show_yamls():
            cfg = load_config(str(yaml_path))
            if not cfg.slow_news.enabled:
                continue
            checked += 1
            lib = cfg.slow_news.library_file
            assert str(lib).strip(), (
                f"{yaml_path.name}: slow_news.enabled without library_file "
                "(the SpaceX July 21 2026 abort class)"
            )
            lib_path = Path(lib)
            if not lib_path.is_absolute():
                lib_path = _SHOWS_DIR.parent / lib
            segments = load_segment_library(str(lib_path))
            assert segments, (
                f"{yaml_path.name}: slow_news library "
                f"{cfg.slow_news.library_file} loaded but is empty"
            )
        # Sanity: the guard is actually exercising shows (11 enabled today).
        assert checked >= 5

    def test_spacex_has_slow_news_library(self):
        from engine.config import load_config
        from engine.slow_news import load_segment_library

        cfg = load_config(str(_SHOWS_DIR / "spacex.yaml"))
        assert cfg.slow_news.enabled
        assert cfg.slow_news.library_file == "shows/segments/spacex.json"
        segments = load_segment_library(
            str(_SHOWS_DIR.parent / cfg.slow_news.library_file)
        )
        assert len(segments) >= 10
        ids = [s["id"] for s in segments]
        assert len(ids) == len(set(ids)), "duplicate segment ids"


# ---------------------------------------------------------------------------
# select_segments
# ---------------------------------------------------------------------------

class TestSelectSegments:
    def test_round_robin_skips_recent(self, sample_library):
        from engine.slow_news import load_segment_library, select_segments

        library = load_segment_library(sample_library)
        selected = select_segments(
            library,
            recently_used_ids=["seg_alpha", "seg_beta"],
            max_segments=2,
        )
        ids = [s["id"] for s in selected]
        assert "seg_alpha" not in ids
        assert "seg_beta" not in ids
        assert len(selected) == 2
        assert ids == ["seg_gamma", "seg_delta"]

    def test_respects_max_segments(self, sample_library):
        from engine.slow_news import load_segment_library, select_segments

        library = load_segment_library(sample_library)
        selected = select_segments(
            library,
            recently_used_ids=[],
            max_segments=1,
        )
        assert len(selected) == 1

    def test_all_on_cooldown_falls_back(self, sample_library):
        from engine.slow_news import load_segment_library, select_segments

        library = load_segment_library(sample_library)
        # All 4 segment IDs are "recently used"
        selected = select_segments(
            library,
            recently_used_ids=["seg_alpha", "seg_beta", "seg_gamma", "seg_delta"],
            max_segments=2,
        )
        # Should still return 2 segments (least-recently-used fallback)
        assert len(selected) == 2
        # First in recently_used_ids = oldest = should be picked first
        assert selected[0]["id"] == "seg_alpha"
        assert selected[1]["id"] == "seg_beta"

    def test_empty_library(self):
        from engine.slow_news import select_segments

        assert select_segments([], [], max_segments=2) == []

    def test_no_recently_used(self, sample_library):
        from engine.slow_news import load_segment_library, select_segments

        library = load_segment_library(sample_library)
        selected = select_segments(library, recently_used_ids=[], max_segments=2)
        assert len(selected) == 2
        assert selected[0]["id"] == "seg_alpha"
        assert selected[1]["id"] == "seg_beta"


# ---------------------------------------------------------------------------
# build_slow_news_prompt_context
# ---------------------------------------------------------------------------

class TestBuildSlowNewsPromptContext:
    def test_generates_context_with_articles_and_segments(self, sample_library):
        from engine.slow_news import load_segment_library, build_slow_news_prompt_context

        library = load_segment_library(sample_library)
        segments = library[:2]
        articles = [
            {"title": "Breaking News A", "source": "Reuters", "summary": "Something happened."},
            {"title": "Update B", "source": "AP", "description": "Another thing."},
        ]
        config = _FakeConfig(slow_news=_SlowNewsConfig(enabled=True))
        template_vars = {"today_str": "2026-03-25", "date": "2026-03-25"}

        result = build_slow_news_prompt_context(
            articles, segments, config, template_vars,
        )

        assert "SUPPLEMENTAL CONTENT" in result
        assert "NEWS" in result
        assert "Breaking News A" in result
        assert "EVERGREEN SEGMENT" in result
        assert "ALPHA TOPIC" in result  # title is uppercased in the section header
        assert "VARIATION DIRECTION" in result

    def test_includes_previous_angles(self, sample_library):
        from engine.slow_news import load_segment_library, build_slow_news_prompt_context

        library = load_segment_library(sample_library)
        segments = [library[0]]
        articles = [{"title": "News", "source": "Test"}]
        config = _FakeConfig(slow_news=_SlowNewsConfig(enabled=True))
        template_vars = {"today_str": "2026-03-25", "date": "2026-03-25"}

        previous_angles = {
            "seg_alpha": [
                "Previously covered the basics of alpha technology.",
                "Focused on alpha in the European market.",
            ],
        }

        result = build_slow_news_prompt_context(
            articles, segments, config, template_vars, previous_angles,
        )

        assert "PREVIOUS ANGLES" in result
        assert "basics of alpha technology" in result
        assert "European market" in result
        assert "DIFFERENT angle" in result

    def test_empty_segments_returns_empty(self):
        from engine.slow_news import build_slow_news_prompt_context

        config = _FakeConfig(slow_news=_SlowNewsConfig(enabled=True))
        result = build_slow_news_prompt_context([], [], config, {})
        assert result == ""

    def test_template_vars_injected(self, sample_library):
        from engine.slow_news import load_segment_library, build_slow_news_prompt_context

        library = load_segment_library(sample_library)
        segments = [library[0]]  # prompt_template has {today_str}
        articles = [{"title": "News", "source": "Test"}]
        config = _FakeConfig(slow_news=_SlowNewsConfig(enabled=True))
        template_vars = {"today_str": "2026-03-25", "date": "2026-03-25"}

        result = build_slow_news_prompt_context(
            articles, segments, config, template_vars,
        )
        assert "2026-03-25" in result


# ---------------------------------------------------------------------------
# Config integration
# ---------------------------------------------------------------------------

class TestSlowNewsConfig:
    def test_config_loads_slow_news_block(self, tmp_path):
        from engine.config import load_config

        yaml_content = """
name: Test Show
slug: test
slow_news:
  enabled: true
  library_file: shows/segments/test.json
  max_segments: 3
  cooldown_days: 14
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content, encoding="utf-8")
        config = load_config(str(yaml_file))
        assert config.slow_news.enabled is True
        assert config.slow_news.library_file == "shows/segments/test.json"
        assert config.slow_news.max_segments == 3
        assert config.slow_news.cooldown_days == 14

    def test_config_defaults_slow_news_disabled(self, tmp_path):
        from engine.config import load_config

        yaml_content = """
name: Minimal Show
slug: minimal
"""
        yaml_file = tmp_path / "minimal.yaml"
        yaml_file.write_text(yaml_content, encoding="utf-8")
        config = load_config(str(yaml_file))
        assert config.slow_news.enabled is False
        assert config.slow_news.library_file == ""
        assert config.slow_news.max_segments == 2


# ---------------------------------------------------------------------------
# ContentTracker segment methods
# ---------------------------------------------------------------------------

class TestContentTrackerSegments:
    def test_get_recent_segment_ids(self, tmp_path):
        from engine.content_tracker import ContentTracker

        tracker = ContentTracker("test_show", tmp_path, max_days=30)
        today = datetime.date.today().isoformat()
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

        tracker.data["episodes"] = [
            {
                "date": yesterday,
                "headlines": [],
                "slow_news_segments": ["seg_alpha", "seg_beta"],
            },
            {
                "date": today,
                "headlines": [],
                "slow_news_segments": ["seg_gamma"],
            },
        ]

        ids = tracker.get_recent_segment_ids(days=7)
        assert ids == ["seg_alpha", "seg_beta", "seg_gamma"]

    def test_get_recent_segment_ids_respects_cutoff(self, tmp_path):
        from engine.content_tracker import ContentTracker

        tracker = ContentTracker("test_show", tmp_path, max_days=30)
        old_date = (datetime.date.today() - datetime.timedelta(days=60)).isoformat()

        tracker.data["episodes"] = [
            {
                "date": old_date,
                "headlines": [],
                "slow_news_segments": ["seg_old"],
            },
        ]

        ids = tracker.get_recent_segment_ids(days=30)
        assert ids == []

    def test_get_segment_history(self, tmp_path):
        from engine.content_tracker import ContentTracker

        tracker = ContentTracker("test_show", tmp_path, max_days=30)
        today = datetime.date.today().isoformat()
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

        tracker.data["episodes"] = [
            {
                "date": yesterday,
                "headlines": [],
                "slow_news_segments": ["seg_alpha"],
                "slow_news_segment_summaries": {
                    "seg_alpha": "Covered the European angle on alpha.",
                },
            },
            {
                "date": today,
                "headlines": [],
                "slow_news_segments": ["seg_alpha"],
                "slow_news_segment_summaries": {
                    "seg_alpha": "Covered the Asian angle on alpha.",
                },
            },
        ]

        history = tracker.get_segment_history("seg_alpha", limit=3)
        assert len(history) == 2
        # Most recent first
        assert history[0]["date"] == today
        assert "Asian" in history[0]["summary"]
        assert history[1]["date"] == yesterday

    def test_get_segment_history_no_matches(self, tmp_path):
        from engine.content_tracker import ContentTracker

        tracker = ContentTracker("test_show", tmp_path, max_days=30)
        tracker.data["episodes"] = []
        assert tracker.get_segment_history("nonexistent") == []


# ---------------------------------------------------------------------------
# Segment library file validation (actual shipped files)
# ---------------------------------------------------------------------------

class TestShippedSegmentLibraries:
    """Validate the segment library JSON files shipped with the project."""

    @pytest.mark.parametrize("lib_file", [
        "shows/segments/tesla.json",
        "shows/segments/models_agents.json",
        "shows/segments/env_intel.json",
    ])
    def test_shipped_library_is_valid(self, lib_file):
        from engine.slow_news import load_segment_library

        path = Path(__file__).parent.parent / lib_file
        if not path.exists():
            pytest.skip(f"{lib_file} not found")
        segments = load_segment_library(str(path))
        assert len(segments) >= 10, f"Expected at least 10 segments in {lib_file}"

        # All IDs should be unique
        ids = [s["id"] for s in segments]
        assert len(ids) == len(set(ids)), f"Duplicate segment IDs in {lib_file}"

        # All types should be from the allowed set
        allowed_types = {"deep_dive", "profile", "historical", "contrarian", "utility", "listener_guide"}
        for seg in segments:
            assert seg["type"] in allowed_types, f"Unknown type '{seg['type']}' in {lib_file}"
