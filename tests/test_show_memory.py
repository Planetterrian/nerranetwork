"""Safety-net coverage for the narrative-memory subsystem.

Today this lives in ``engine.tesla_memory`` and powers Tesla Shorts Time's
recursive "program narrative" continuity.  Phase 3 of the network roadmap
generalizes it to Models & Agents, Fascinating Frontiers, Planetterrian, and
Modern Investing.  These tests pin the load/save/build contract *before* that
refactor so the generalization can't silently change behavior — and they cover
the first-run (no file yet) path that a brand-new show hits, which is exactly
where copy-isolation bugs bite.
"""

from __future__ import annotations

import json

import pytest

from engine import tesla_memory as tm


# ---------------------------------------------------------------------------
# Round-trip load/save
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_narrative_round_trip(self, tmp_path):
        tracker = tm.load_narrative_tracker(tmp_path)
        assert "programs" in tracker
        tm.save_narrative_tracker(tracker, tmp_path)
        assert (tmp_path / tm.NARRATIVE_TRACKER_FILENAME).exists()
        reloaded = tm.load_narrative_tracker(tmp_path)
        assert "programs" in reloaded
        assert "last_updated" in reloaded  # save stamps it

    def test_performance_round_trip(self, tmp_path):
        perf = tm.load_performance_tracker(tmp_path)
        assert "recent_signals" in perf
        tm.save_performance_tracker(perf, tmp_path)
        assert (tmp_path / tm.PERFORMANCE_TRACKER_FILENAME).exists()

    def test_theme_round_trip(self, tmp_path):
        themes = tm.load_theme_history(tmp_path)
        assert "recurring_themes" in themes
        tm.save_theme_history(themes, tmp_path)
        assert (tmp_path / tm.THEME_HISTORY_FILENAME).exists()


# ---------------------------------------------------------------------------
# Default isolation — the first-run path for a brand-new show
# ---------------------------------------------------------------------------

class TestDefaultIsolation:
    def test_loading_defaults_does_not_mutate_module_default(self, tmp_path):
        """A fresh load (no file on disk) must return an INDEPENDENT copy.

        If the loader returned a reference into the module-level default dict,
        a new show recording its first narrative update would corrupt the
        default for every other consumer in the same process.
        """
        first = tm.load_narrative_tracker(tmp_path)
        first["programs"]["__test_injected__"] = {"status": "x"}

        # A second load from a *different* empty dir must not see the injection.
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        second = tm.load_narrative_tracker(other_dir)
        assert "__test_injected__" not in second["programs"]

    def test_performance_default_isolation(self, tmp_path):
        first = tm.load_performance_tracker(tmp_path)
        first["recent_signals"]["__injected__"] = ["x"]
        other = tmp_path / "p2"
        other.mkdir()
        second = tm.load_performance_tracker(other)
        assert "__injected__" not in second["recent_signals"]


# ---------------------------------------------------------------------------
# Prompt-block builders
# ---------------------------------------------------------------------------

class TestBlockBuilders:
    def test_empty_programs_yields_empty_block(self):
        assert tm.build_narrative_status_block({"programs": {}}) == ""

    def test_populated_programs_yields_text(self):
        tracker = {
            "programs": {
                "optimus": {
                    "display_name": "Optimus",
                    "status": "Gen 3 hands in testing.",
                    "key_open_questions": ["When does volume production start?"],
                    "last_major_update_episode": 42,
                    "last_major_update_date": "2026-05-01",
                }
            }
        }
        block = tm.build_narrative_status_block(tracker)
        assert "Optimus" in block
        assert "Gen 3 hands in testing." in block
        assert "Ep42" in block

    def test_empty_performance_signals_yields_empty(self):
        assert tm.build_performance_signals_block({"recent_signals": {}}) == ""

    def test_empty_theme_history_yields_empty(self):
        assert tm.build_theme_context_block({"recurring_themes": {}}) == ""

    def test_get_memory_context_returns_three_blocks(self, tmp_path):
        ctx = tm.get_tesla_memory_context(tmp_path)
        assert set(ctx) == {
            "tesla_narrative_status_block",
            "tesla_performance_signals_block",
            "tesla_theme_context_block",
        }
        assert all(isinstance(v, str) for v in ctx.values())


# ---------------------------------------------------------------------------
# Update helpers
# ---------------------------------------------------------------------------

class TestUpdateHelpers:
    def test_record_performance_signal_persists(self, tmp_path):
        tm.record_performance_signal(tmp_path, "strong_topic", "Robotaxi launch")
        perf = tm.load_performance_tracker(tmp_path)
        assert "Robotaxi launch" in perf["recent_signals"]["strong_topics_last_30d"]

    def test_update_theme_history_counts_keywords(self, tmp_path):
        tm.update_theme_history_from_digest(
            tmp_path, "Today the robotaxi and FSD updates dominated.", episode_num=1
        )
        themes = tm.load_theme_history(tmp_path)["recurring_themes"]
        assert themes.get("robotaxi", 0) >= 1
        assert themes.get("fsd", 0) >= 1

    def test_record_unknown_program_is_noop(self, tmp_path):
        # Unknown key logs a warning and does not raise.
        tm.record_narrative_update(tmp_path, "__nonexistent__", "x", 1, "2026-05-01")


# ---------------------------------------------------------------------------
# Corruption tolerance
# ---------------------------------------------------------------------------

class TestCorruptionTolerance:
    def test_corrupt_json_falls_back_to_default(self, tmp_path):
        (tmp_path / tm.NARRATIVE_TRACKER_FILENAME).write_text("{ not valid json", encoding="utf-8")
        tracker = tm.load_narrative_tracker(tmp_path)
        assert "programs" in tracker  # graceful fallback, no exception
