"""Drift guards for the Phase 1 pipeline safety nets.

Three additive guardrails:
  * content-lake backfill fail-loud evaluation,
  * YouTube quota preflight,
  * daily health-summary text builder.

None of these change show output; they make silent failures loud.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import post_run_summary as prs  # noqa: E402
from scripts import youtube_quota_preflight as yqp  # noqa: E402


# ---------------------------------------------------------------------------
# Content-lake backfill fail-loud evaluation
# ---------------------------------------------------------------------------

class TestBackfillEvaluation:
    def _ev(self):
        from scripts.backfill_content_lake import evaluate_backfill
        return evaluate_backfill

    def test_empty_lake_is_error(self):
        level, msg = self._ev()(0)
        assert level == "error"
        assert "EMPTY" in msg

    def test_thin_lake_is_warning(self):
        level, _ = self._ev()(3, warn_below=7)
        assert level == "warning"

    def test_healthy_lake_is_ok(self):
        level, _ = self._ev()(50, warn_below=7)
        assert level == "ok"

    def test_exactly_at_threshold_is_ok(self):
        level, _ = self._ev()(7, warn_below=7)
        assert level == "ok"


# ---------------------------------------------------------------------------
# YouTube quota preflight
# ---------------------------------------------------------------------------

class TestQuotaPreflight:
    def test_current_network_is_under_quota(self):
        # Tesla + MAB only (landmine #20) — must stay under the 10k default.
        assert yqp.main([]) == 0

    def test_over_quota_with_tiny_budget_warns_but_does_not_block_by_default(self):
        # Non-strict: loud annotation, but exit 0 so an episode still ships.
        assert yqp.main(["--daily-quota", "100"]) == 0

    def test_over_quota_with_strict_fails(self):
        assert yqp.main(["--daily-quota", "100", "--strict"]) == 1


# ---------------------------------------------------------------------------
# Daily health-summary builder
# ---------------------------------------------------------------------------

class TestSummaryBuilder:
    def test_healthy_summary(self):
        dash = {
            "generated_at": "2026-05-29T00:00:00Z",
            "network": {"shows_count": 11, "total_cost_last_7_days_usd": 4.5, "stale_shows": 0},
            "alerts": [],
            "rss_audit": {"offline": False, "raw_github_hits": []},
        }
        text = prs.build_summary_text(dash)
        assert text.startswith("✅")
        assert "Shows tracked: 11" in text
        assert "7-day spend: $4.50" in text
        assert "All feeds fresh" in text

    def test_unhealthy_summary_flags_problems(self):
        dash = {
            "generated_at": "t",
            "network": {"shows_count": 11, "stale_shows": 2},
            "alerts": ["x"],
            "rss_audit": {"offline": ["feed_a"], "raw_github_hits": ["b", "c"]},
        }
        text = prs.build_summary_text(dash)
        assert text.startswith("⚠️")
        assert "Stale shows: 2" in text
        assert "Offline RSS feeds: 1" in text
        assert "Alerts: 1" in text

    def test_count_helper_handles_mixed_shapes(self):
        assert prs._count(None) == 0
        assert prs._count(False) == 0
        assert prs._count(True) == 1
        assert prs._count(3) == 3
        assert prs._count(["a", "b"]) == 2
        assert prs._count({"k": 1}) == 1

    def test_quota_over_marker(self):
        dash = {"generated_at": "t", "network": {"shows_count": 1}, "alerts": [], "rss_audit": {}}
        quota = {"total_units": 12000, "daily_quota": 10000, "headroom_units": -2000, "over_quota": True}
        text = prs.build_summary_text(dash, quota)
        assert "OVER QUOTA" in text

    def test_builder_tolerates_empty_dashboard(self):
        text = prs.build_summary_text({})
        assert "Nerra Network daily summary" in text
