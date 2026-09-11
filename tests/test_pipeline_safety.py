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


# ---------------------------------------------------------------------------
# Timeout envelope (2026-08-18 grok-4.6 outage post-mortem)
# ---------------------------------------------------------------------------
#
# The outage's amplifier was a mis-ordered timeout stack: the in-process
# SIGALRM watchdog (PIPELINE_TIMEOUT_SECONDS) sat ABOVE the CI step's
# hard-kill, so it could never fire — jobs died mid-write with commit
# steps skipped, and unintended_consequences Ep093 was orphaned (published
# everywhere, committed nowhere) when the kill landed 0.35 s after the
# pipeline finished. These guards pin the ordering and the retry contract.

class TestTimeoutEnvelope:
    WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "run-show.yml"

    def _run_show_job(self):
        import yaml
        wf = yaml.safe_load(self.WORKFLOW.read_text(encoding="utf-8"))
        return wf["jobs"]["run"]

    def _pipeline_step(self):
        job = self._run_show_job()
        for step in job["steps"]:
            if step.get("name") == "Run show pipeline":
                return step
        raise AssertionError("'Run show pipeline' step not found")

    def test_watchdog_fires_before_ci_hard_kill(self):
        """PIPELINE_TIMEOUT_SECONDS (SIGALRM, clean abort with a reason)
        must sit at least 5 minutes BELOW the step's timeout-minutes
        (hard kill, skipped commit steps). At 45/3000 the watchdog was
        unreachable in CI."""
        step = self._pipeline_step()
        step_limit_s = int(step["timeout-minutes"]) * 60
        watchdog_s = int(step["env"]["PIPELINE_TIMEOUT_SECONDS"])
        assert watchdog_s + 300 <= step_limit_s, (
            f"PIPELINE_TIMEOUT_SECONDS={watchdog_s} must be >=300s below "
            f"the step hard-kill ({step_limit_s}s) or it can never fire"
        )

    def test_setup_steps_carry_a_hang_guard(self):
        """2026-08-19: a GitHub-side stall froze the setup-python step for
        SIX HOURS on four shows' scheduled runs (killed only by the 6h job
        limit — four missed episodes, recovered by the audit's retry path
        at 16:52). Every setup step in this workflow must carry its own
        timeout so a hung dependency install fails fast and loud instead
        of silently eating the day's slot."""
        import yaml
        wf = yaml.safe_load(self.WORKFLOW.read_text(encoding="utf-8"))
        for job_name in ("run", "finalize"):
            for step in wf["jobs"][job_name]["steps"]:
                if str(step.get("uses", "")).endswith("actions/setup-python"):
                    assert step.get("timeout-minutes"), (
                        f"{job_name}: setup-python step needs timeout-minutes"
                    )
                    assert int(step["timeout-minutes"]) <= 60

    def test_llm_client_owns_no_retries(self):
        """_call_grok must create its OpenAI client with max_retries=0.

        The SDK's default internal retry (2) sat UNDER the tenacity
        wrappers, so one hanging upstream became 3 SDK requests x 3
        tenacity attempts = nine 5-minute stalls (grok-4.6, 2026-08-18).
        Retries belong to exactly one layer: tenacity."""
        src = (PROJECT_ROOT / "engine" / "generator.py").read_text(
            encoding="utf-8")
        assert "max_retries=0" in src

    def test_llm_timeout_is_env_tunable(self):
        """A slower model must be accommodated by raising
        NERRA_LLM_TIMEOUT_SECONDS, never by letting requests hang."""
        src = (PROJECT_ROOT / "engine" / "generator.py").read_text(
            encoding="utf-8")
        assert "NERRA_LLM_TIMEOUT_SECONDS" in src


# ---------------------------------------------------------------------------
# Long-form render budget (Tesla Ep602, 2026-09-11)
# ---------------------------------------------------------------------------
#
# The commit reserve has guarded the Grok Video CLIPS path since June 2026 so
# a slow optional stage "can never trip the SIGALRM and skip the episode's git
# commit". That path is disabled network-wide (`video_clips_enabled: false`),
# while the long-form slideshow render — the 27-minute stage on every episode
# (Ep601: youtube_publish_duration_s 1619.65) — was not budgeted at all.
# Ep602 reached it 2,186 s into a 3,000 s budget after a 17-minute script
# stage, rendered for 13 minutes, died on the alarm, and was orphaned: audio
# already on R2, nothing committed, no RSS item.

class TestLongFormRenderBudget:
    SRC = (PROJECT_ROOT / "run_show.py")

    def _src(self):
        return self.SRC.read_text(encoding="utf-8")

    def test_render_budget_constant_is_env_tunable(self):
        """The floor must be tunable without touching the timeout envelope:
        raising PIPELINE_TIMEOUT_SECONDS past the job's timeout-minutes is
        the mis-ordering TestTimeoutEnvelope exists to forbid."""
        src = self._src()
        assert "_LONG_FORM_RENDER_BUDGET_S" in src
        assert "LONG_FORM_RENDER_BUDGET_SECONDS" in src

    def test_long_form_render_is_budgeted_against_the_commit_reserve(self):
        """The render must consult the SAME budget-minus-reserve expression
        the clips path uses, and must turn the render off rather than
        continue into a SIGALRM."""
        src = self._src()
        guard = src.split("_render_long = _policy_publish_long", 1)[1][:3000]
        assert "_pipeline_budget_remaining() - _PIPELINE_COMMIT_RESERVE_S" in guard
        assert "_LONG_FORM_RENDER_BUDGET_S" in guard
        assert "_render_long = False" in guard
        # The YouTube upload must be disarmed too — uploading a long-form
        # that was never rendered is a guaranteed error path.
        assert "_policy_publish_long = False" in guard

    def test_skip_keeps_shorts_and_records_the_decision(self):
        """Skipping the long-form must stay observable: a silent skip is the
        silent-number class the Sep 2026 passes kept paying for."""
        src = self._src()
        assert 'result["long_form_skipped_budget"] = True' in src
        assert 'result["long_form_render_budget_s"]' in src
        assert 'result["long_form_render_duration_s"]' in src

    def test_render_metrics_are_on_the_allowlist(self):
        """`record_youtube_outcomes` is the only way a result key reaches the
        metrics file (grok_image_px_max shipped 09-03 and recorded nothing
        for six days)."""
        src = (PROJECT_ROOT / "engine" / "pipeline.py").read_text(
            encoding="utf-8")
        for key in ("long_form_render_duration_s", "long_form_skipped_budget",
                    "long_form_render_budget_s"):
            assert f'"{key}"' in src, f"{key} never reaches the metrics file"
