"""Drift guards for the June 10 2026 YouTube pipeline quality pass
(docs/youtube_review_2026_06_10.md)."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.config import NewsletterConfig, YouTubeConfig, load_config  # noqa: E402


class TestSilentConfigDropClass:
    """The bug class behind this pass: YAML keys not declared on a
    dataclass were silently dropped by _build_nested."""

    def test_every_youtube_yaml_key_is_declared(self):
        known = set(YouTubeConfig.__dataclass_fields__)
        for f in sorted((_ROOT / "shows").glob("*.yaml")):
            if f.stem.startswith("_") or f.stem in (
                "network_meta", "pronunciation_map", "scaffold_pending",
            ):
                continue
            yt = (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("youtube") or {}
            unknown = set(yt) - known
            assert not unknown, f"{f.name}: undeclared youtube keys {sorted(unknown)}"

    def test_unknown_keys_warn_loudly(self):
        src = (_ROOT / "engine" / "config.py").read_text(encoding="utf-8")
        assert "ignoring unknown config key(s)" in src

    def test_tesla_threshold_resolves(self):
        cfg = load_config(str(_ROOT / "shows" / "tesla.yaml"))
        assert cfg.youtube.shorts_min_score_threshold == 3.5

    def test_newsletter_fields_declared(self):
        fields = set(NewsletterConfig.__dataclass_fields__)
        for f in ("requires_financial_disclaimer", "emoji", "short_label",
                  "length_target_words", "newsletter_start_date"):
            assert f in fields
        fp = load_config(str(_ROOT / "shows" / "finansy_prosto.yaml"))
        assert fp.newsletter.requires_financial_disclaimer is True

    def test_min_audio_duration_network_default_live(self):
        ov = load_config(str(_ROOT / "shows" / "omni_view.yaml"))
        assert ov.min_audio_duration == 180  # was dead inside the audio: block


class TestShortsSelectorThresholdWired:
    def test_single_short_path_passes_threshold(self):
        src = (_ROOT / "engine" / "youtube_shorts.py").read_text(encoding="utf-8")
        assert "shorts_min_score_threshold" in src
        assert "min_score_threshold=threshold" in src


class TestSlideshowSceneCycling:
    def test_scene_hold_cap_present(self):
        src = (_ROOT / "engine" / "video.py").read_text(encoding="utf-8")
        assert "_MAX_SCENE_HOLD_S = 15.0" in src
        assert "slideshow_scenes" in src

    def test_slideshow_slot_cap_shared_with_scheduler(self):
        """Ep537 timeout class: long episodes must clamp ffmpeg inputs via
        the shared _MAX_SLIDESHOW_SLOTS (not unbounded 15 s cycling)."""
        from engine.scene_scheduler import _MAX_SLIDESHOW_SLOTS
        video_src = (_ROOT / "engine" / "video.py").read_text(encoding="utf-8")
        sched_src = (_ROOT / "engine" / "scene_scheduler.py").read_text(
            encoding="utf-8")
        assert "_MAX_SLIDESHOW_SLOTS" in video_src
        # Aug 2026: cap raised 24 -> 36 after the command builders began
        # deduping ffmpeg inputs (one -i per unique image + split) — the
        # Ep537 blowup was 74 DEMUXERS, not 74 zoompan stages, and input
        # count no longer scales with slots.
        assert "_MAX_SLIDESHOW_SLOTS = 36" in sched_src
        assert _MAX_SLIDESHOW_SLOTS == 36
        assert "_dedupe_scene_inputs" in video_src
        assert "PIPELINE_TIMEOUT_SECONDS: '3000'" in (
            _ROOT / ".github" / "workflows" / "run-show.yml"
        ).read_text(encoding="utf-8")


class TestObservability:
    def test_missing_channel_token_warning(self):
        # July 18 2026 (lang_dub generalization): the RU-specific warning
        # became channel-generic — any non-EN channel with a missing token
        # warns loudly instead of silently no-oping.
        src = (_ROOT / "engine" / "youtube.py").read_text(encoding="utf-8")
        assert "YOUTUBE_REFRESH_TOKEN_%s is not set" in src
        assert 'suffix != "EN"' in src

    def test_shorts_caption_mode_metric(self):
        # Key must match what engine/pipeline.record_youtube_outcomes
        # reads (shorts_caption_mode) — the old shorts_captions_path key
        # was recorded by nothing, so the ASS-vs-SRT-fallback rate never
        # reached metrics.
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'result["shorts_caption_mode"]' in src
        assert 'result["shorts_captions_path"]' not in src
        pipeline_src = (_ROOT / "engine" / "pipeline.py").read_text(
            encoding="utf-8")
        assert '"shorts_caption_mode"' in pipeline_src

    def test_grok_degraded_slideshow_is_loud(self):
        """June 14 2026: with six shows on Grok Imagine, a silent outage that
        drops the slideshow to the static cover must surface as a GitHub
        annotation + metric, not hide in the per-episode JSON."""
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "grok_slideshow_degraded" in src
        assert "::warning::Grok Imagine produced only" in src
