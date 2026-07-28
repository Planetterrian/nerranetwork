"""Drift guards for per-episode cost completeness (July 28 2026, P0-3).

The credit summary reported roughly half of real spend. Three separate
holes, all fixed together because a partial fix still produces a number
nobody can budget with:

  1. ``save_usage`` summed only ``x_thread_generation`` and
     ``podcast_script_generation``. Every retry and the outline call
     were recorded in the JSON and then dropped from the total — 47% of
     LLM spend on the SpaceX Ep047 file this suite pins.
  2. Grok Imagine cost was computed and logged by ``grok_imagine.py``
     but never reached the tracker, so images contributed $0.00.
  3. The digest bucket was logged as "X Thread" on shows that post
     nothing to X.

The headline assertion is the invariant: the reported total equals the
sum of everything logged.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.tracking import (  # noqa: E402
    _STEP_LABELS,
    create_tracker,
    record_image_usage,
    record_llm_usage,
    record_render_seconds,
    record_tts_usage,
    save_usage,
)


@pytest.fixture()
def ep047(tmp_path):
    """A tracker loaded with the real SpaceX Ep047 usage figures."""
    tracker = create_tracker("SpaceX Daily", 47)
    record_llm_usage(tracker, "x_thread_generation", 15531, 3116,
                     model="grok-4.3", cached_tokens=15488)
    record_llm_usage(tracker, "podcast_script_generation", 9659, 1630,
                     model="grok-4.3", cached_tokens=192)
    record_llm_usage(tracker, "x_thread_generation_expansion", 18905, 3551,
                     model="grok-4.3", cached_tokens=15488)
    record_llm_usage(tracker, "podcast_outline_generation", 4450, 703,
                     model="grok-4.3", cached_tokens=192)
    record_tts_usage(tracker, 8944, provider="grok")
    record_image_usage(tracker, 8, 0.16, model="grok-imagine-image")
    path = save_usage(tracker, tmp_path)
    return json.loads(Path(path).read_text(encoding="utf-8"))


class TestTotalIsComplete:
    def test_total_equals_sum_of_every_logged_cost(self, ep047):
        services = ep047["services"]
        parts = (
            services["grok_api"]["total_cost_usd"]
            + services["tts_api"]["estimated_cost_usd"]
            + services["image_api"]["estimated_cost_usd"]
        )
        assert ep047["total_estimated_cost_usd"] == pytest.approx(parts)

    def test_retries_and_outline_are_counted(self, ep047):
        """The regression that hid 47% of Ep047's LLM spend."""
        grok = ep047["services"]["grok_api"]
        per_step = sum(
            v["estimated_cost_usd"] for v in grok.values()
            if isinstance(v, dict) and "estimated_cost_usd" in v
        )
        assert grok["total_cost_usd"] == pytest.approx(per_step)
        # The two originally-summed buckets alone must NOT equal the
        # total, or this test would pass vacuously.
        originals = (
            grok["x_thread_generation"]["estimated_cost_usd"]
            + grok["podcast_script_generation"]["estimated_cost_usd"]
        )
        assert originals < grok["total_cost_usd"]

    def test_images_reach_the_total(self, ep047):
        assert ep047["services"]["image_api"]["estimated_cost_usd"] == pytest.approx(0.16)
        assert ep047["total_estimated_cost_usd"] > 0.16

    def test_token_total_covers_every_step(self, ep047):
        grok = ep047["services"]["grok_api"]
        per_step = sum(
            v["total_tokens"] for v in grok.values()
            if isinstance(v, dict) and "total_tokens" in v
        )
        assert grok["total_tokens"] == per_step

    def test_reported_total_is_no_longer_the_understated_figure(self, ep047):
        """Ep047 shipped reporting $0.1610; the true figure is ~$0.34."""
        assert ep047["total_estimated_cost_usd"] > 0.30


class TestBackwardCompatibility:
    """The dashboard reads these keys — they must survive."""

    def test_dashboard_keys_still_present(self, ep047):
        services = ep047["services"]
        assert "total_cost_usd" in services["grok_api"]
        assert "estimated_cost_usd" in services["tts_api"]
        assert "total_estimated_cost_usd" in ep047
        # Legacy mirror the dashboard historically read.
        assert "elevenlabs_api" in services

    def test_original_step_keys_are_unchanged(self, ep047):
        grok = ep047["services"]["grok_api"]
        assert "x_thread_generation" in grok
        assert "podcast_script_generation" in grok

    def test_zero_usage_run_totals_zero(self, tmp_path):
        tracker = create_tracker("Quiet Show", 1)
        data = json.loads(
            Path(save_usage(tracker, tmp_path)).read_text(encoding="utf-8")
        )
        assert data["total_estimated_cost_usd"] == 0.0

    def test_tracker_without_image_block_still_saves(self, tmp_path):
        """Old in-flight trackers (no image_api key) must not crash."""
        tracker = create_tracker("Legacy Show", 2)
        del tracker["services"]["image_api"]
        record_llm_usage(tracker, "x_thread_generation", 100, 50, model="grok-4.3")
        data = json.loads(
            Path(save_usage(tracker, tmp_path)).read_text(encoding="utf-8")
        )
        assert data["total_estimated_cost_usd"] > 0


class TestStepLabels:
    def test_digest_bucket_is_not_labelled_x_thread(self):
        """It is written on every run, including shows with X disabled."""
        assert _STEP_LABELS["x_thread_generation"] == "Digest"
        assert "X Thread" not in _STEP_LABELS.values()

    def test_every_recorded_step_name_has_a_label(self):
        """A new step should be labelled, not fall back to the raw key."""
        source = (
            Path(__file__).resolve().parent.parent / "engine" / "generator.py"
        ).read_text(encoding="utf-8")
        used = {
            line.split('"')[1]
            for line in source.split("\n")
            if "record_llm_usage(" not in line
            and line.strip().startswith('"')
            and line.strip().rstrip(",").endswith('"')
            and ("_generation" in line or "_retry" in line or "_model" in line)
        }
        unlabelled = {s for s in used if s and s not in _STEP_LABELS}
        assert not unlabelled, f"unlabelled tracking steps: {unlabelled}"


class TestImageAccounting:
    def test_multiple_passes_accumulate(self):
        tracker = create_tracker("Show", 1)
        record_image_usage(tracker, 4, 0.08, model="grok-imagine-image")
        record_image_usage(tracker, 4, 0.08, model="grok-imagine-image")
        images = tracker["services"]["image_api"]
        assert images["images_generated"] == 8
        assert images["estimated_cost_usd"] == pytest.approx(0.16)

    def test_model_is_recorded(self):
        tracker = create_tracker("Show", 1)
        record_image_usage(tracker, 1, 0.05, model="grok-imagine-image-quality")
        assert tracker["services"]["image_api"]["model"] == "grok-imagine-image-quality"


class TestRenderMinutes:
    def test_render_seconds_accumulate_and_are_not_priced(self, tmp_path):
        tracker = create_tracker("Show", 1)
        record_render_seconds(tracker, 207)
        record_render_seconds(tracker, 320)
        data = json.loads(
            Path(save_usage(tracker, tmp_path)).read_text(encoding="utf-8")
        )
        assert data["render"]["video_seconds"] == pytest.approx(527.0)
        # Compute time is informational — it must never inflate dollars.
        assert data["total_estimated_cost_usd"] == 0.0


class TestRunShowWiring:
    """The tracker wire must actually exist in the pipeline."""

    def test_run_show_records_image_cost(self):
        source = (
            Path(__file__).resolve().parent.parent / "run_show.py"
        ).read_text(encoding="utf-8")
        assert "record_image_usage(" in source
        assert "grok_image_cost_usd" in source
