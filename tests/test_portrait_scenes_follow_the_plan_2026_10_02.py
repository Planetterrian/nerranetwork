"""Oct 2 2026 (cost pass) — the fresh 9:16 Grok Imagine set follows its
consumers. The count was a fixed ``short_scenes_per_episode`` (5) on every
YouTube-enabled run, including the dead-Shorts probe-tier days on which the
policy ships ZERO Shorts: six shows paid for five portrait images a day that
nothing rendered (~$10–15/month). A 9:16 scene has three consumers — this
channel's Shorts, a dub channel's Shorts (which reuse the gallery scenes)
and the multi-platform cuts — and with none of them in play the count is 0.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.youtube_policy import portrait_scene_count  # noqa: E402


def _yt(**kw):
    base = dict(short_scenes_per_episode=5, ru_dub_enabled=False,
                dub_languages=[], multi_platform_enabled=False)
    base.update(kw)
    return SimpleNamespace(**base)


class TestPortraitSceneCount:
    def test_a_planned_short_keeps_the_yaml_count(self):
        assert portrait_scene_count(_yt(), shorts_planned=1) == 5
        assert portrait_scene_count(_yt(short_scenes_per_episode=3), shorts_planned=2) == 3

    def test_a_probe_day_with_no_consumer_generates_nothing(self):
        assert portrait_scene_count(_yt(), shorts_planned=0) == 0

    def test_a_dub_channel_is_a_consumer_even_on_an_en_probe_day(self):
        assert portrait_scene_count(_yt(ru_dub_enabled=True), shorts_planned=0) == 5
        assert portrait_scene_count(_yt(dub_languages=["fr"]), shorts_planned=0) == 5

    def test_multi_platform_is_a_consumer(self):
        assert portrait_scene_count(_yt(multi_platform_enabled=True), shorts_planned=0) == 5

    def test_the_yaml_count_is_never_raised(self):
        assert portrait_scene_count(_yt(short_scenes_per_episode=2), shorts_planned=1) == 2

    def test_the_real_dubbed_shows_keep_their_scenes(self):
        from engine.config import load_config
        for slug in ("tesla", "spacex", "fascinating_frontiers"):
            cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
            assert portrait_scene_count(cfg.youtube, shorts_planned=0) > 0, slug

    def test_the_probe_tier_shows_generate_nothing_on_a_zero_short_day(self):
        from engine.config import load_config
        for slug in ("omni_view", "modern_investing", "planetterrian"):
            cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
            assert portrait_scene_count(cfg.youtube, shorts_planned=0) == 0, slug


class TestRunShowWiring:
    def test_the_scene_stage_reads_the_plan_and_skips_the_9x16_call(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        i = src.index("_fresh_short_scene_count = portrait_scene_count(")
        block = src[i:i + 2200]
        assert "shorts_planned=_policy_shorts_count" in block
        # Both Grok 9:16 call sites are gated on a consumer existing.
        assert block.count("if _portrait_consumers:") == 2
        assert 'result["short_scenes_skipped_no_consumer"] = True' in block

    def test_an_empty_9x16_set_is_not_a_degraded_one(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert re.search(r"if len\(short_scene_paths\) < 2 and _portrait_consumers:", src)

    def test_the_skip_is_a_metric(self):
        src = (ROOT / "engine" / "pipeline.py").read_text(encoding="utf-8")
        assert 'metrics.record("short_scenes_skipped_no_consumer", True)' in src
