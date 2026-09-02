"""Drift guards for the July 29 2026 cost-efficiency pass.

Five changes, each measured before it shipped rather than argued from
first principles:

* per-language OP3 measurement (multilingual is ~1/3 of network spend and
  its audience was measured nowhere) — guarded in test_op3_stats.py;
* 16:9 scene generation scoped to days a long-form video is produced;
* xAI search-tool spend finally reaching the episode's credit file;
* single-pass render on by default after an output-equivalence A/B —
  guarded in test_single_pass_render.py;
* the podcast-side expansion retry switched off wherever the sanctioned
  digest-side lever exists.

The last one is the load-bearing measurement: across 901 committed
episodes, 81% shipped BELOW target WITH the retry running (Tesla 96.7%,
Models & Agents 95.2%). The ceiling is the digest, not the script, so the
retry paid on nearly every episode and almost never reached its goal —
and it pads by paraphrase-duplication, which is why the July 28 pass had
to add ``_dedup_expansion_sentences`` to clean up after it. The July 18
playbook had already banned podcast-side length levers network-wide; this
makes the config match the policy.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _show_yamls():
    for p in sorted((REPO_ROOT / "shows").glob("*.yaml")):
        if p.stem.startswith("_") or p.stem in {
            "pronunciation_map", "network_meta", "scaffold_pending",
            "translation_overrides",
        }:
            continue
        yield p, (yaml.safe_load(p.read_text(encoding="utf-8")) or {})


class TestLengthLeverPolicy:
    def test_no_show_runs_both_expansion_retries(self):
        """Paying twice for the same miss. The digest lever is the
        sanctioned substrate; the podcast one is banned by the playbook."""
        both = [
            p.stem for p, d in _show_yamls()
            if (d.get("llm") or {}).get("podcast_expand_below_target")
            and (d.get("llm") or {}).get("digest_expand_below_target")
        ]
        assert both == [], f"shows running both length retries: {both}"

    def test_shows_with_the_digest_lever_disabled_the_podcast_one(self):
        offenders = [
            p.stem for p, d in _show_yamls()
            if (d.get("llm") or {}).get("digest_expand_below_target")
            and (d.get("llm") or {}).get("podcast_expand_below_target")
        ]
        assert not offenders, offenders

    def test_env_intel_switched_to_the_digest_lever(self):
        """July 31 2026: env_intel gained digest_expand_below_target
        (digests measured 563-891 words — the real ceiling), so its
        banned podcast-side retry is now off per the network policy."""
        data = yaml.safe_load(
            (REPO_ROOT / "shows" / "env_intel.yaml").read_text(
                encoding="utf-8")) or {}
        llm = data.get("llm") or {}
        assert llm.get("digest_expand_below_target") is True
        assert llm.get("min_digest_words", 0) > 0
        assert not llm.get("podcast_expand_below_target")

    def test_the_show_without_a_digest_lever_keeps_theirs(self):
        """finansy_prosto still has no digest-side lever (its digest .md
        is a ~200-word structured brief — a words floor needs its own
        design), so switching the podcast retry off would leave it no
        length mechanism at all. Deliberately untouched — revisit only by
        giving it the digest lever first."""
        for slug in ("finansy_prosto",):
            data = yaml.safe_load(
                (REPO_ROOT / "shows" / f"{slug}.yaml").read_text(
                    encoding="utf-8")) or {}
            llm = data.get("llm") or {}
            assert llm.get("podcast_expand_below_target") is True, slug
            assert not llm.get("digest_expand_below_target"), (
                f"{slug} gained a digest lever — now switch its podcast "
                "retry off and move it to the guarded set above"
            )


class TestSceneGenerationFollowsTheRender:
    """16:9 scenes feed only the long-form video, its thumbnail, and the
    gallery. Shorts use their own 9:16 set, so on a shorts-only policy day
    for a show with no video-podcast feed, three of four paid images were
    generated and never seen."""

    def test_run_show_scopes_fresh_16x9_to_long_form_days(self):
        src = (REPO_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "_fresh_long_scene_count" in src
        assert "_long_form_produced = bool(" in src
        # The saving must not apply when a video-podcast feed still needs
        # the render — those shows render long-form regardless of tier.
        idx = src.index("_long_form_produced = bool(")
        window = src[idx:idx + 200]
        assert "config.video_podcast.enabled" in window
        assert "_policy_publish_long" in window

    def test_the_shorts_aspect_is_never_reduced(self):
        """Shorts publish on every tier — their scenes are not optional.

        Sep 2026: the 9:16 count is config-driven
        (youtube.short_scenes_per_episode, default 5 >= the old fixed 4)
        and, unlike the 16:9 count, must NOT be gated on whether a
        long-form is produced today."""
        src = (REPO_ROOT / "run_show.py").read_text(encoding="utf-8")
        idx = src.index('aspect="9:16", label_suffix="_short"')
        assert "count=_fresh_short_scene_count" in src[idx:idx + 160]
        line = [l for l in src.splitlines()
                if "_fresh_short_scene_count = " in l][0]
        assert "_long_form_produced" not in line
        from engine.config import YouTubeConfig
        assert YouTubeConfig().short_scenes_per_episode >= 4

    def test_saving_is_measured_not_assumed(self):
        from engine.pipeline import record_youtube_outcomes  # noqa: F401

        src = (REPO_ROOT / "engine" / "pipeline.py").read_text(encoding="utf-8")
        assert "scene_long_form_produced" in src
        assert "scene_fresh_long_requested" in src


class TestSearchSpendIsCounted:
    """xAI bills server-side search per tool CALL ($5/1k, 2026 pricing) on
    top of tokens; the launch-era per-SOURCE fee ($25/1k) only applies if
    the usage object ever reports source counts again. The 2026-08-18 LLM
    usage review found EVERY credit file since the July 29 accounting
    shipped had ``sources: 0`` — the per-source term multiplied by zero
    while the real per-call fee went untracked."""

    def test_tracker_has_a_search_section(self):
        from engine.tracking import create_tracker

        t = create_tracker("Test Show", 1)
        assert "search_api" in t["services"]

    def test_cost_is_calls_plus_sources_plus_tokens(self):
        from engine.tracking import (
            SEARCH_COST_PER_CALL, SEARCH_COST_PER_SOURCE,
            create_tracker, record_search_usage,
        )

        t = create_tracker("Test Show", 1)
        record_search_usage(t, calls=2, sources=10,
                            prompt_tokens=1000, completion_tokens=500,
                            model="grok-4.3")
        got = t["services"]["search_api"]["estimated_cost_usd"]
        expected = 2 * SEARCH_COST_PER_CALL + 10 * SEARCH_COST_PER_SOURCE + (
            1000 * 1.25 + 500 * 2.50) / 1_000_000
        assert got == pytest.approx(expected)

    def test_calls_bill_even_with_zero_sources(self):
        """The live 2026 shape: xAI reports no source count, bills per
        call. sources=0 must not zero the search cost."""
        from engine.tracking import (
            SEARCH_COST_PER_CALL, create_tracker, record_search_usage,
        )

        t = create_tracker("Test Show", 1)
        record_search_usage(t, calls=6, sources=0)
        assert t["services"]["search_api"]["estimated_cost_usd"] == pytest.approx(
            6 * SEARCH_COST_PER_CALL)

    def test_rates_are_env_overridable(self, monkeypatch):
        from engine.tracking import create_tracker, record_search_usage

        monkeypatch.setenv("XAI_SEARCH_COST_PER_SOURCE", "0.01")
        monkeypatch.setenv("XAI_SEARCH_COST_PER_CALL", "0.002")
        t = create_tracker("Test Show", 1)
        record_search_usage(t, calls=1, sources=10)
        assert t["services"]["search_api"]["estimated_cost_usd"] == pytest.approx(
            1 * 0.002 + 10 * 0.01)

    def test_search_cost_reaches_the_episode_total(self, tmp_path):
        from engine.tracking import create_tracker, record_search_usage, save_usage

        t = create_tracker("Test Show", 7)
        record_search_usage(t, calls=1, sources=4)
        save_usage(t, tmp_path)
        written = next(tmp_path.glob("credit_usage_*.json"))
        import json
        data = json.loads(written.read_text(encoding="utf-8"))
        assert data["total_estimated_cost_usd"] >= 4 * 0.025

    def test_accumulator_drains_so_shows_do_not_bill_each_other(self):
        """The daily-audit retry path runs several shows in one process."""
        from digests.xai_grok import drain_search_usage

        drain_search_usage()  # start clean
        assert drain_search_usage() == {
            "calls": 0, "sources": 0, "input_tokens": 0, "output_tokens": 0,
        }

    def test_usage_extraction_survives_unknown_response_shapes(self):
        from digests.xai_grok import _record_search_usage, drain_search_usage

        drain_search_usage()

        class _Root:
            usage = type("U", (), {
                "input_tokens": 10, "output_tokens": 2,
                "num_sources_used": 5})()

        class _Nested:
            usage = type("U", (), {
                "input_tokens": 1, "output_tokens": 1,
                "server_side_tool_use": type("S", (), {"sources_used": 3})()})()

        class _Bare:  # no usage attribute at all
            pass

        for resp in (_Root(), _Nested(), _Bare()):
            _record_search_usage(resp, 1)
        drained = drain_search_usage()
        assert drained["calls"] == 3
        assert drained["sources"] == 8


class TestRenderSecondsHaveACaller:
    """The July 28 cost pass shipped record_render_seconds with no caller,
    so `render.video_seconds` was always 0.0 and its log line was dead."""

    def test_run_show_records_render_seconds(self):
        src = (REPO_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "record_render_seconds(tracker" in src
