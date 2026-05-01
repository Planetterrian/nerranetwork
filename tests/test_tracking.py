"""
Tests for engine/tracking.py — cost and usage tracking for the podcast pipeline.

Covers:
  - create_tracker(): structure, defaults, field types
  - record_llm_usage(): token accumulation, known and custom steps, auto-cost
  - record_tts_usage(): character accumulation, multi-provider support
  - record_x_post(): post counter increment
  - save_usage(): cost calculations, JSON output, file naming
"""

import datetime
import json
from pathlib import Path

import pytest

from engine.tracking import (
    ELEVENLABS_COST_PER_1K_CHARS,
    GROK_PRICING,
    create_tracker,
    record_llm_usage,
    record_tts_usage,
    record_x_post,
    save_usage,
)


# ===================================================================
# TEST: create_tracker
# ===================================================================

class TestCreateTracker:

    def test_returns_dict(self):
        tracker = create_tracker("Test Show", 1)
        assert isinstance(tracker, dict)

    def test_has_date(self):
        tracker = create_tracker("Test Show", 1)
        assert tracker["date"] == datetime.date.today().isoformat()

    def test_has_show_name(self):
        tracker = create_tracker("Tesla Shorts Time", 42)
        assert tracker["show"] == "Tesla Shorts Time"

    def test_has_episode_number(self):
        tracker = create_tracker("Test", 99)
        assert tracker["episode_number"] == 99

    def test_has_services_key(self):
        tracker = create_tracker("Test", 1)
        assert "services" in tracker
        assert "grok_api" in tracker["services"]
        assert "tts_api" in tracker["services"]
        assert "x_api" in tracker["services"]

    def test_grok_api_structure(self):
        tracker = create_tracker("Test", 1)
        grok = tracker["services"]["grok_api"]
        assert "x_thread_generation" in grok
        assert "podcast_script_generation" in grok
        assert grok["total_tokens"] == 0
        assert grok["total_cost_usd"] == 0.0

    def test_grok_step_defaults(self):
        tracker = create_tracker("Test", 1)
        for step in ("x_thread_generation", "podcast_script_generation"):
            s = tracker["services"]["grok_api"][step]
            assert s["prompt_tokens"] == 0
            assert s["completion_tokens"] == 0
            assert s["total_tokens"] == 0
            assert s["estimated_cost_usd"] == 0.0

    def test_tts_defaults(self):
        tracker = create_tracker("Test", 1)
        tts = tracker["services"]["tts_api"]
        assert tts["provider"] == "elevenlabs"
        assert tts["characters"] == 0
        assert tts["estimated_cost_usd"] == 0.0

    def test_x_api_defaults(self):
        tracker = create_tracker("Test", 1)
        x = tracker["services"]["x_api"]
        assert x["search_calls"] == 0
        assert x["post_calls"] == 0
        assert x["total_calls"] == 0

    def test_total_cost_starts_at_zero(self):
        tracker = create_tracker("Test", 1)
        assert tracker["total_estimated_cost_usd"] == 0.0


# ===================================================================
# TEST: record_llm_usage
# ===================================================================

class TestRecordLlmUsage:

    def test_record_x_thread_generation(self):
        tracker = create_tracker("Test", 1)
        record_llm_usage(tracker, "x_thread_generation", 500, 200, 0.05)
        step = tracker["services"]["grok_api"]["x_thread_generation"]
        assert step["prompt_tokens"] == 500
        assert step["completion_tokens"] == 200
        assert step["total_tokens"] == 700
        assert step["estimated_cost_usd"] == 0.05

    def test_record_podcast_script_generation(self):
        tracker = create_tracker("Test", 1)
        record_llm_usage(tracker, "podcast_script_generation", 1000, 800, 0.10)
        step = tracker["services"]["grok_api"]["podcast_script_generation"]
        assert step["prompt_tokens"] == 1000
        assert step["completion_tokens"] == 800
        assert step["total_tokens"] == 1800
        assert step["estimated_cost_usd"] == 0.10

    def test_accumulates_multiple_calls(self):
        tracker = create_tracker("Test", 1)
        record_llm_usage(tracker, "x_thread_generation", 100, 50, 0.01)
        record_llm_usage(tracker, "x_thread_generation", 200, 100, 0.02)
        step = tracker["services"]["grok_api"]["x_thread_generation"]
        assert step["prompt_tokens"] == 300
        assert step["completion_tokens"] == 150
        assert step["total_tokens"] == 450
        assert step["estimated_cost_usd"] == pytest.approx(0.03)

    def test_custom_step_created_if_missing(self):
        tracker = create_tracker("Test", 1)
        record_llm_usage(tracker, "custom_step", 10, 5, 0.001)
        assert "custom_step" in tracker["services"]["grok_api"]
        assert tracker["services"]["grok_api"]["custom_step"]["total_tokens"] == 15

    def test_zero_cost_default(self):
        tracker = create_tracker("Test", 1)
        record_llm_usage(tracker, "x_thread_generation", 100, 50)
        step = tracker["services"]["grok_api"]["x_thread_generation"]
        assert step["estimated_cost_usd"] == 0.0

    def test_auto_cost_with_model(self):
        """When model is provided and cost is 0, cost is auto-estimated."""
        tracker = create_tracker("Test", 1)
        record_llm_usage(tracker, "x_thread_generation", 1_000_000, 500_000, model="grok-4.20-non-reasoning")
        step = tracker["services"]["grok_api"]["x_thread_generation"]
        pricing = GROK_PRICING["grok-4.20-non-reasoning"]
        expected = (1_000_000 / 1e6) * pricing["input_per_1m"] + (500_000 / 1e6) * pricing["output_per_1m"]
        assert step["estimated_cost_usd"] == pytest.approx(expected)

    def test_model_recorded(self):
        tracker = create_tracker("Test", 1)
        record_llm_usage(tracker, "x_thread_generation", 100, 50, model="grok-4.20-non-reasoning")
        assert tracker["services"]["grok_api"]["model"] == "grok-4.20-non-reasoning"

    def test_unknown_model_zero_cost(self):
        tracker = create_tracker("Test", 1)
        record_llm_usage(tracker, "x_thread_generation", 100, 50, model="unknown-model")
        step = tracker["services"]["grok_api"]["x_thread_generation"]
        assert step["estimated_cost_usd"] == 0.0


# ===================================================================
# TEST: record_tts_usage
# ===================================================================

class TestRecordTtsUsage:

    def test_records_characters(self):
        tracker = create_tracker("Test", 1)
        record_tts_usage(tracker, 5000)
        assert tracker["services"]["tts_api"]["characters"] == 5000

    def test_accumulates_characters(self):
        tracker = create_tracker("Test", 1)
        record_tts_usage(tracker, 3000)
        record_tts_usage(tracker, 2000)
        assert tracker["services"]["tts_api"]["characters"] == 5000

    def test_zero_characters(self):
        tracker = create_tracker("Test", 1)
        record_tts_usage(tracker, 0)
        assert tracker["services"]["tts_api"]["characters"] == 0

    def test_fish_provider(self):
        tracker = create_tracker("Test", 1)
        record_tts_usage(tracker, 5000, provider="fish")
        assert tracker["services"]["tts_api"]["provider"] == "fish"
        assert tracker["services"]["tts_api"]["characters"] == 5000

    def test_elevenlabs_provider_default(self):
        tracker = create_tracker("Test", 1)
        record_tts_usage(tracker, 5000)
        assert tracker["services"]["tts_api"]["provider"] == "elevenlabs"


# ===================================================================
# TEST: record_x_post
# ===================================================================

class TestRecordXPost:

    def test_increments_post_calls(self):
        tracker = create_tracker("Test", 1)
        record_x_post(tracker)
        assert tracker["services"]["x_api"]["post_calls"] == 1

    def test_multiple_posts(self):
        tracker = create_tracker("Test", 1)
        record_x_post(tracker)
        record_x_post(tracker)
        record_x_post(tracker)
        assert tracker["services"]["x_api"]["post_calls"] == 3

    def test_does_not_affect_search_calls(self):
        tracker = create_tracker("Test", 1)
        record_x_post(tracker)
        assert tracker["services"]["x_api"]["search_calls"] == 0


# ===================================================================
# TEST: save_usage
# ===================================================================

class TestSaveUsage:

    def test_writes_json_file(self, tmp_path):
        tracker = create_tracker("Test Show", 42)
        result = save_usage(tracker, tmp_path)
        assert result is not None
        assert result.exists()
        assert result.suffix == ".json"

    def test_filename_format(self, tmp_path):
        tracker = create_tracker("Test Show", 7)
        result = save_usage(tracker, tmp_path)
        expected = f"credit_usage_{datetime.date.today().isoformat()}_ep007.json"
        assert result.name == expected

    def test_json_is_valid(self, tmp_path):
        tracker = create_tracker("Test", 1)
        result = save_usage(tracker, tmp_path)
        data = json.loads(result.read_text())
        assert data["show"] == "Test"
        assert data["episode_number"] == 1

    def test_calculates_grok_totals(self, tmp_path):
        tracker = create_tracker("Test", 1)
        record_llm_usage(tracker, "x_thread_generation", 500, 200, 0.05)
        record_llm_usage(tracker, "podcast_script_generation", 1000, 800, 0.10)
        save_usage(tracker, tmp_path)
        grok = tracker["services"]["grok_api"]
        assert grok["total_tokens"] == 500 + 200 + 1000 + 800
        assert grok["total_cost_usd"] == pytest.approx(0.15)

    def test_calculates_elevenlabs_cost(self, tmp_path):
        tracker = create_tracker("Test", 1)
        record_tts_usage(tracker, 10000, provider="elevenlabs")
        save_usage(tracker, tmp_path)
        tts = tracker["services"]["tts_api"]
        expected_cost = (10000 / 1000) * ELEVENLABS_COST_PER_1K_CHARS
        assert tts["estimated_cost_usd"] == pytest.approx(expected_cost)

    def test_calculates_x_api_totals(self, tmp_path):
        tracker = create_tracker("Test", 1)
        record_x_post(tracker)
        record_x_post(tracker)
        save_usage(tracker, tmp_path)
        x = tracker["services"]["x_api"]
        assert x["total_calls"] == 2

    def test_calculates_total_cost(self, tmp_path):
        tracker = create_tracker("Test", 1)
        record_llm_usage(tracker, "x_thread_generation", 500, 200, 0.05)
        record_tts_usage(tracker, 5000)
        save_usage(tracker, tmp_path)
        el_cost = (5000 / 1000) * ELEVENLABS_COST_PER_1K_CHARS
        assert tracker["total_estimated_cost_usd"] == pytest.approx(0.05 + el_cost)

    def test_returns_none_on_invalid_dir(self):
        tracker = create_tracker("Test", 1)
        result = save_usage(tracker, Path("/nonexistent/dir/that/does/not/exist"))
        assert result is None

    def test_json_contains_all_keys(self, tmp_path):
        tracker = create_tracker("My Show", 10)
        record_llm_usage(tracker, "x_thread_generation", 100, 50, 0.01)
        record_tts_usage(tracker, 2000)
        record_x_post(tracker)
        result = save_usage(tracker, tmp_path)
        data = json.loads(result.read_text())
        assert "date" in data
        assert "show" in data
        assert "episode_number" in data
        assert "services" in data
        assert "total_estimated_cost_usd" in data

    def test_elevenlabs_cost_per_1k_constant(self):
        """Verify the pricing constant matches the documented rate (Flash v2.5)."""
        assert ELEVENLABS_COST_PER_1K_CHARS == 0.15

    def test_cost_precision(self, tmp_path):
        """Costs should not have floating point drift issues."""
        tracker = create_tracker("Test", 1)
        record_tts_usage(tracker, 3333)
        save_usage(tracker, tmp_path)
        tts = tracker["services"]["tts_api"]
        expected = (3333 / 1000) * 0.15
        assert abs(tts["estimated_cost_usd"] - expected) < 1e-10


# ===================================================================
# TEST: Grok pricing
# ===================================================================

class TestGrokPricing:

    def test_grok4_pricing_exists(self):
        """grok-4 is retained for historical credit_usage JSON re-scoring."""
        assert "grok-4" in GROK_PRICING
        assert "input_per_1m" in GROK_PRICING["grok-4"]
        assert "output_per_1m" in GROK_PRICING["grok-4"]

    def test_grok420_pricing_exists(self):
        assert "grok-4.20-non-reasoning" in GROK_PRICING
        assert "grok-4.20-reasoning" in GROK_PRICING

    def test_grok43_pricing_exists(self):
        """grok-4.3 is the current network default (since 2026-05-01)."""
        assert "grok-4.3" in GROK_PRICING
        assert GROK_PRICING["grok-4.3"]["input_per_1m"] == 1.25
        assert GROK_PRICING["grok-4.3"]["output_per_1m"] == 2.50

    def test_grok43_cheaper_than_grok420(self):
        """The whole point of switching to grok-4.3 is cost savings."""
        assert (
            GROK_PRICING["grok-4.3"]["input_per_1m"]
            < GROK_PRICING["grok-4.20-non-reasoning"]["input_per_1m"]
        )
        assert (
            GROK_PRICING["grok-4.3"]["output_per_1m"]
            < GROK_PRICING["grok-4.20-non-reasoning"]["output_per_1m"]
        )

    def test_reviewer_model_priced(self):
        """Reviewer model must have pricing so its cost is attributed."""
        assert "grok-4-1-fast-non-reasoning" in GROK_PRICING

    def test_pruned_models_removed(self):
        """Legacy ids that no live call site targets should be pruned."""
        for pruned in ("grok-2", "grok-3", "grok-3-mini",
                       "grok-4.20-0309-non-reasoning"):
            assert pruned not in GROK_PRICING, (
                f"{pruned} was pruned in the April 2026 audit — re-adding it "
                "invites accidental cost attribution drift"
            )
