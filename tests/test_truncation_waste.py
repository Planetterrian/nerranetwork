"""Drift guards for wasted truncation retries (July 28 2026, P1-1).

When a generation call hits ``max_tokens`` the code retries at 1.5x and
replaces ``text``/``meta`` wholesale. The first call's tokens were
therefore billed by xAI and recorded nowhere — the waste was invisible
in every credit file.

That mattered more than the accounting: the improvement plan had to
infer the problem from run logs and named the wrong show. Measured
across the committed credit files, SpaceX has hit the digest truncation
retry in **0 of 45** recorded runs (largest completion 3,870 against a
4,000 cap). The real offenders are Omni View (21/117, 17%) and
Fascinating Frontiers (7/107, 6%), whose caps are raised here.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.config import load_config  # noqa: E402
from engine.tracking import (  # noqa: E402
    _STEP_LABELS,
    create_tracker,
    save_usage,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestDiscardedCallIsRecorded:
    def test_helper_records_under_its_own_step(self):
        from engine.generator import _record_discarded_call

        class _Cfg:
            class llm:
                model = "grok-4.3"

        tracker = create_tracker("Show", 1)
        meta = {"usage": {"prompt_tokens": 8000, "completion_tokens": 10000,
                          "cached_tokens": 0}}
        _record_discarded_call(tracker, "x_thread_generation_truncated", meta, _Cfg)

        bucket = tracker["services"]["grok_api"]["x_thread_generation_truncated"]
        assert bucket["completion_tokens"] == 10000
        # Must not be folded into the successful call's bucket, or the
        # waste becomes indistinguishable from useful output.
        assert "x_thread_generation" in tracker["services"]["grok_api"]
        assert (
            tracker["services"]["grok_api"]["x_thread_generation"]["completion_tokens"]
            == 0
        )

    def test_discarded_cost_reaches_the_episode_total(self, tmp_path):
        """P0-3 sums every bucket, so the waste now shows up in dollars."""
        from engine.generator import _record_discarded_call

        class _Cfg:
            class llm:
                model = "grok-4.3"

        tracker = create_tracker("Show", 1)
        _record_discarded_call(
            tracker, "x_thread_generation_truncated",
            {"usage": {"prompt_tokens": 8000, "completion_tokens": 10000}}, _Cfg,
        )
        import json
        data = json.loads(
            Path(save_usage(tracker, tmp_path)).read_text(encoding="utf-8")
        )
        assert data["total_estimated_cost_usd"] > 0

    def test_missing_usage_is_a_noop(self):
        from engine.generator import _record_discarded_call

        class _Cfg:
            class llm:
                model = "grok-4.3"

        tracker = create_tracker("Show", 1)
        _record_discarded_call(tracker, "x_thread_generation_truncated", {}, _Cfg)
        assert "x_thread_generation_truncated" not in tracker["services"]["grok_api"]

    def test_no_tracker_is_a_noop(self):
        from engine.generator import _record_discarded_call

        class _Cfg:
            class llm:
                model = "grok-4.3"

        # Must not raise — generation runs without a tracker in --test mode.
        _record_discarded_call(None, "step", {"usage": {}}, _Cfg)

    @pytest.mark.parametrize(
        "step",
        ["x_thread_generation_truncated", "podcast_script_generation_truncated"],
    )
    def test_discarded_steps_are_labelled(self, step):
        assert step in _STEP_LABELS
        assert "discarded" in _STEP_LABELS[step].lower()


class TestBothRetryPathsRecord:
    """Digest and podcast both throw away a call; both must account for it."""

    def test_wired_into_both_truncation_retries(self):
        source = (REPO_ROOT / "engine" / "generator.py").read_text(encoding="utf-8")
        assert source.count("_record_discarded_call(") >= 3  # def + 2 call sites
        assert "x_thread_generation_truncated" in source
        assert "podcast_script_generation_truncated" in source

    def test_recorded_before_meta_is_overwritten(self):
        """Order matters: after the retry, the first call's usage is gone."""
        source = (REPO_ROOT / "engine" / "generator.py").read_text(encoding="utf-8")
        block = source.split('"x_thread_generation_truncated", meta, config)')[1]
        # The very next _call_grok is the retry that replaces meta.
        assert block.lstrip().startswith("text, meta = _call_grok(")


class TestRaisedCaps:
    """The caps raised on measured evidence, pinned so they don't drift back."""

    @pytest.mark.parametrize(
        "slug,minimum",
        [
            # 17% retry rate at 10,000; largest kept digest 12,000 tokens.
            ("omni_view", 13000),
            # 6% retry rate at 5,000; largest kept digest 7,287 tokens.
            ("fascinating_frontiers", 7500),
        ],
    )
    def test_cap_clears_the_largest_observed_digest(self, slug, minimum):
        config = load_config(REPO_ROOT / "shows" / f"{slug}.yaml")
        assert config.llm.max_tokens >= minimum

    def test_spacex_cap_left_alone(self):
        """The plan named SpaceX; the data says it has never truncated.

        Raising a cap that is never reached would be a no-op change to a
        live show's config, so it is deliberately not made.
        """
        config = load_config(REPO_ROOT / "shows" / "spacex.yaml")
        assert config.llm.max_tokens == 4000

    def test_raised_caps_carry_their_evidence(self):
        """A future reader must be able to see why the number is what it is."""
        for slug in ("omni_view", "fascinating_frontiers"):
            raw = (REPO_ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8")
            head = raw.split("max_tokens:")[0]
            assert "truncation retry" in head, f"{slug} cap lacks a rationale comment"

    def test_every_show_still_loads(self):
        """A malformed YAML comment would break the whole network."""
        for path in sorted((REPO_ROOT / "shows").glob("*.yaml")):
            if path.name.startswith("_"):
                continue
            assert yaml.safe_load(path.read_text(encoding="utf-8")) is not None
