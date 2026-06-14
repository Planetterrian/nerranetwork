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
        assert "_MAX_SCENE_HOLD_S = 25.0" in src
        assert "slideshow_scenes" in src


class TestObservability:
    def test_ru_token_warning(self):
        src = (_ROOT / "engine" / "youtube.py").read_text(encoding="utf-8")
        assert "YOUTUBE_REFRESH_TOKEN_RU is not set" in src

    def test_shorts_captions_path_metric(self):
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'result["shorts_captions_path"]' in src

    def test_grok_degraded_slideshow_is_loud(self):
        """June 14 2026: with six shows on Grok Imagine, a silent outage that
        drops the slideshow to the static cover must surface as a GitHub
        annotation + metric, not hide in the per-episode JSON."""
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "grok_slideshow_degraded" in src
        assert "::warning::Grok Imagine produced only" in src
