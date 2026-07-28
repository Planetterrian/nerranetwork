"""Drift guards for the June 2026 YouTube visual-reuse composition layer.

Pins: the new ``youtube:`` config knobs exist on the dataclass AND in
``shows/_defaults.yaml`` (the silent-config-drop landmine), the
``engine.visual_reuse`` flag gating + never-raise contract, the recap /
fallback pools, the new observability keys in ``record_youtube_outcomes``,
the gallery↔retention join script, and the nightly-workflow wiring. All
gallery/network access is stubbed via monkeypatch — no R2, no manifest.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.config import YouTubeConfig  # noqa: E402
from engine import visual_reuse as vr  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_NEW_KNOBS = {
    "gallery_blend_enabled": True,
    # July 2026: 8 -> 16 and 4 -> 6. Only 4 fresh images are
    # generated per episode against up to 24 scheduler slots, so
    # the old pool repeated every image several times per episode.
    # Library scenes are already generated and already paid for.
    "gallery_blend_max_long": 16,
    "gallery_blend_max_short": 6,
    "chapter_aligned_scenes": True,
    "long_form_thumbnail_from_scene": True,
    "thumbnail_variants": 2,
    "recap_reuse_scenes": True,
    "gallery_fallback_enabled": True,
    "shorts_sentence_cuts": True,
    "evergreen_broll": True,
}


def _config(**overrides):
    return SimpleNamespace(youtube=YouTubeConfig(**overrides))


def _chapters_file(tmp_path, n=3):
    chapters = [
        {"startTime": float(i * 60), "title": f"Chapter {i}"} for i in range(n)
    ]
    p = tmp_path / "chapters_ep001.json"
    p.write_text(json.dumps({"version": "1.2.0", "chapters": chapters}),
                 encoding="utf-8")
    return p


def _scenes(prefix, n):
    return [Path(f"/scenes/{prefix}{i}.jpeg") for i in range(n)]


def _stub_library(monkeypatch, *, scenes=(), broll=(), raise_on=None):
    """Stub every gallery_library entry point visual_reuse touches."""
    import engine.gallery_library as gl

    def _select(*a, **k):
        if raise_on == "select":
            raise RuntimeError("boom")
        return list(scenes)

    def _week(*a, **k):
        if raise_on == "week":
            raise RuntimeError("boom")
        return list(scenes)

    def _broll(*a, **k):
        return list(broll)

    def _manifest(*a, **k):
        if raise_on == "manifest":
            raise RuntimeError("boom")
        return {"images": []}

    monkeypatch.setattr(gl, "select_library_scenes", _select)
    monkeypatch.setattr(gl, "collect_week_scenes", _week)
    monkeypatch.setattr(gl, "select_broll_clips", _broll)
    monkeypatch.setattr(gl, "load_manifest", _manifest)
    monkeypatch.setattr(gl, "scene_context_map",
                        lambda manifest, paths: {p: "" for p in paths})


# ---------------------------------------------------------------------------
# Config knobs — dataclass + _defaults.yaml (silent-config-drop landmine)
# ---------------------------------------------------------------------------

class TestConfigKnobs:
    def test_dataclass_declares_all_knobs_with_defaults(self):
        fields = YouTubeConfig.__dataclass_fields__
        cfg = YouTubeConfig()
        for name, expected in _NEW_KNOBS.items():
            assert name in fields, f"YouTubeConfig missing {name}"
            assert getattr(cfg, name) == expected, (
                f"{name} default is {getattr(cfg, name)!r}, want {expected!r}"
            )

    def test_defaults_yaml_documents_all_knobs(self):
        data = yaml.safe_load(
            (_ROOT / "shows" / "_defaults.yaml").read_text(encoding="utf-8")
        )
        yt = data.get("youtube") or {}
        for name, expected in _NEW_KNOBS.items():
            assert name in yt, f"_defaults.yaml youtube: missing {name}"
            assert yt[name] == expected


# ---------------------------------------------------------------------------
# long_form_visual_plan
# ---------------------------------------------------------------------------

class TestLongFormVisualPlan:
    def _plan(self, config, tmp_path, *, fresh=4, chapters=3, **kwargs):
        return vr.long_form_visual_plan(
            config,
            show_slug="tesla",
            episode_id="ep001",
            hook="Cybercab production begins",
            fresh_scenes=_scenes("fresh", fresh),
            chapters_path=_chapters_file(tmp_path, chapters) if chapters else None,
            audio_duration_s=600.0,
            digests_dir=tmp_path,
            **kwargs,
        )

    def test_happy_path_chapter_schedule(self, monkeypatch, tmp_path):
        _stub_library(monkeypatch, scenes=_scenes("lib", 3))
        out = self._plan(_config(), tmp_path)
        assert out["mode"] == "chapter_schedule"
        assert out["scene_schedule"] and len(out["scene_schedule"]) >= 2
        assert out["fresh_count"] == 4
        assert out["library_count"] == 3
        # Blended pool = fresh + library, fresh first.
        assert out["scene_paths"][:4] == _scenes("fresh", 4)
        assert abs(sum(d for _, d in out["scene_schedule"]) - 600.0) < 1.0

    def test_chapter_alignment_disabled_gives_no_schedule(
        self, monkeypatch, tmp_path,
    ):
        _stub_library(monkeypatch, scenes=_scenes("lib", 3))
        out = self._plan(_config(chapter_aligned_scenes=False), tmp_path)
        assert out["scene_schedule"] is None
        assert out["mode"] == "uniform"
        assert out["scene_paths"]  # blending still applies

    def test_blend_disabled_uses_only_fresh(self, monkeypatch, tmp_path):
        _stub_library(monkeypatch, scenes=_scenes("lib", 3))
        out = self._plan(_config(gallery_blend_enabled=False), tmp_path)
        assert out["library_count"] == 0
        assert out["scene_paths"] == _scenes("fresh", 4)

    def test_fewer_than_two_chapters_falls_back_to_uniform_mode(
        self, monkeypatch, tmp_path,
    ):
        _stub_library(monkeypatch, scenes=[])
        out = self._plan(_config(), tmp_path, chapters=1)
        assert out["scene_schedule"] is None
        assert out["mode"] == "uniform"

    def test_no_fresh_scenes_is_library_fallback_mode(
        self, monkeypatch, tmp_path,
    ):
        _stub_library(monkeypatch, scenes=_scenes("lib", 4))
        out = self._plan(_config(), tmp_path, fresh=0)
        assert out["mode"] == "library_fallback"
        assert out["scene_paths"] == _scenes("lib", 4)

    def test_empty_pool_is_cover_mode(self, monkeypatch, tmp_path):
        _stub_library(monkeypatch, scenes=[])
        out = self._plan(_config(), tmp_path, fresh=0)
        assert out["mode"] == "cover"
        assert out["scene_paths"] is None
        assert out["scene_schedule"] is None

    def test_broll_gating(self, monkeypatch, tmp_path):
        clips = [Path("/broll/clip1.mp4")]
        _stub_library(monkeypatch, scenes=[], broll=clips)
        assert self._plan(_config(), tmp_path)["broll_clips"] == clips
        assert self._plan(
            _config(evergreen_broll=False), tmp_path,
        )["broll_clips"] is None

    def test_internal_failure_never_raises_and_returns_legacy(
        self, monkeypatch, tmp_path,
    ):
        _stub_library(monkeypatch, raise_on="manifest")
        out = self._plan(_config(), tmp_path)
        assert out["scene_schedule"] is None
        assert out["scene_paths"] is None
        assert out["broll_clips"] is None
        assert out["mode"] == "uniform"  # ≥2 fresh scenes → legacy uniform

    def test_scheduler_failure_never_raises(self, monkeypatch, tmp_path):
        _stub_library(monkeypatch, scenes=_scenes("lib", 2))
        import engine.scene_scheduler as ss

        def _boom(*a, **k):
            raise RuntimeError("scheduler exploded")

        monkeypatch.setattr(ss, "plan_chapter_schedule", _boom)
        out = self._plan(_config(), tmp_path)
        assert out["scene_schedule"] is None
        assert out["mode"] == "uniform"


# ---------------------------------------------------------------------------
# short_visual_extras
# ---------------------------------------------------------------------------

_WORDS = [
    {"word": " Hello", "start": 10.0, "end": 10.4},
    {"word": " world.", "start": 10.5, "end": 11.0},
    {"word": " Next", "start": 16.0, "end": 16.3},
    {"word": " sentence.", "start": 16.4, "end": 17.0},
    {"word": " More.", "start": 24.0, "end": 24.5},
]


class TestShortVisualExtras:
    def _extras(self, config, **kwargs):
        defaults = dict(
            show_slug="tesla",
            episode_id="ep001",
            fresh_short_scenes=_scenes("vert", 4),
            transcript_words=_WORDS,
            window_start_s=5.0,
            clip_duration_s=55.0,
            context_text="cybercab",
        )
        defaults.update(kwargs)
        return vr.short_visual_extras(config, **defaults)

    def test_blends_library_and_produces_cuts(self, monkeypatch):
        _stub_library(monkeypatch, scenes=_scenes("libv", 2))
        out = self._extras(_config())
        assert out["scene_paths"][:4] == _scenes("vert", 4)
        assert out["library_count"] == 2
        assert out["scene_change_times"], "expected sentence cuts"

    def test_sentence_cuts_disabled(self, monkeypatch):
        _stub_library(monkeypatch, scenes=[])
        out = self._extras(_config(shorts_sentence_cuts=False))
        assert out["scene_change_times"] is None

    def test_no_word_data_means_no_cuts(self, monkeypatch):
        _stub_library(monkeypatch, scenes=[])
        out = self._extras(_config(), transcript_words=[])
        assert out["scene_change_times"] is None

    def test_blend_disabled_and_thin_fresh_gives_no_scene_paths(
        self, monkeypatch,
    ):
        _stub_library(monkeypatch, scenes=_scenes("libv", 4))
        out = self._extras(
            _config(gallery_blend_enabled=False),
            fresh_short_scenes=_scenes("vert", 1),
        )
        assert out["scene_paths"] is None  # legacy handling takes over

    def test_failure_never_raises(self, monkeypatch):
        _stub_library(monkeypatch, raise_on="select")
        out = self._extras(_config())
        assert out["scene_paths"] is None
        assert out["scene_change_times"] is None


# ---------------------------------------------------------------------------
# recap_scene_pool / fallback_scene_pool
# ---------------------------------------------------------------------------

class TestRecapAndFallbackPools:
    def test_recap_pool_returns_both_aspects(self, monkeypatch):
        _stub_library(monkeypatch, scenes=_scenes("wk", 5))
        out = vr.recap_scene_pool(
            _config(), show_slug="tesla", episode_id="ep001",
            end_date="2026-06-28",
        )
        assert out["enabled"] is True
        assert len(out["long"]) == 5 and len(out["short"]) == 5

    def test_recap_pool_disabled_flag(self, monkeypatch):
        _stub_library(monkeypatch, scenes=_scenes("wk", 5))
        out = vr.recap_scene_pool(
            _config(recap_reuse_scenes=False), show_slug="tesla",
            episode_id="ep001", end_date="2026-06-28",
        )
        assert out == {"long": [], "short": [], "enabled": False}

    def test_recap_pool_failure_never_raises(self, monkeypatch):
        _stub_library(monkeypatch, raise_on="week")
        out = vr.recap_scene_pool(
            _config(), show_slug="tesla", episode_id="ep001",
            end_date="2026-06-28",
        )
        assert out["long"] == [] and out["short"] == []

    def test_run_show_gates_recap_on_two_per_aspect(self):
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'len(_recap_pool.get("long") or []) >= 2' in src
        assert 'len(_recap_pool.get("short") or []) >= 2' in src

    def test_fallback_pool(self, monkeypatch):
        _stub_library(monkeypatch, scenes=_scenes("fb", 3))
        got = vr.fallback_scene_pool(
            _config(), show_slug="tesla", episode_id="ep001",
        )
        assert got == _scenes("fb", 3)

    def test_fallback_pool_disabled_flag(self, monkeypatch):
        _stub_library(monkeypatch, scenes=_scenes("fb", 3))
        assert vr.fallback_scene_pool(
            _config(gallery_fallback_enabled=False),
            show_slug="tesla", episode_id="ep001",
        ) == []

    def test_fallback_pool_failure_never_raises(self, monkeypatch):
        _stub_library(monkeypatch, raise_on="select")
        assert vr.fallback_scene_pool(
            _config(), show_slug="tesla", episode_id="ep001",
        ) == []


class TestLoadTranscriptWords:
    def test_flattens_segments(self, tmp_path):
        p = tmp_path / "t.json"
        p.write_text(json.dumps({"segments": [
            {"start": 0, "end": 1, "text": "a", "words": _WORDS[:2]},
            {"start": 1, "end": 2, "text": "b", "words": _WORDS[2:]},
        ]}), encoding="utf-8")
        assert vr.load_transcript_words(p) == _WORDS

    def test_missing_or_wordless_is_empty(self, tmp_path):
        assert vr.load_transcript_words(tmp_path / "nope.json") == []
        p = tmp_path / "old.json"
        p.write_text(json.dumps({"segments": [{"start": 0, "end": 1,
                                               "text": "a"}]}),
                     encoding="utf-8")
        assert vr.load_transcript_words(p) == []


# ---------------------------------------------------------------------------
# Metrics — record_youtube_outcomes carries the new observability keys
# ---------------------------------------------------------------------------

class _FakeMetrics:
    def __init__(self):
        self.data = {}

    def record(self, key, value):
        self.data[key] = value


class TestVisualMetricsRecorded:
    def test_new_keys_recorded(self):
        from engine.pipeline import record_youtube_outcomes
        metrics = _FakeMetrics()
        record_youtube_outcomes(
            metrics,
            {
                "visual_mode": "chapter_schedule",
                "scene_fresh_count": 4,
                "scene_library_count": 6,
                "broll_clips_used": 2,
                "thumbnail_base": "scene",
                "thumbnail_variant_urls": ["https://g/x.jpg"],
            },
            1.0,
            config=_config(),
        )
        assert metrics.data["visual_mode"] == "chapter_schedule"
        assert metrics.data["scene_fresh_count"] == 4
        assert metrics.data["scene_library_count"] == 6
        assert metrics.data["broll_clips_used"] == 2
        assert metrics.data["thumbnail_base"] == "scene"
        assert metrics.data["thumbnail_variant_urls"] == ["https://g/x.jpg"]

    def test_absent_keys_not_recorded(self):
        from engine.pipeline import record_youtube_outcomes
        metrics = _FakeMetrics()
        record_youtube_outcomes(metrics, {}, 1.0, config=_config())
        for key in ("visual_mode", "scene_fresh_count", "scene_library_count",
                    "broll_clips_used", "thumbnail_base",
                    "thumbnail_variant_urls"):
            assert key not in metrics.data


# ---------------------------------------------------------------------------
# run_show wiring drift guards (source-level, matching repo convention)
# ---------------------------------------------------------------------------

class TestRunShowWiring:
    def test_wiring_present(self):
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        # Long-form: plan feeds the renderer.
        assert 'scene_schedule=_visual_plan.get("scene_schedule")' in src
        assert 'broll_clips=_visual_plan.get("broll_clips")' in src
        # Shorts: extras feed the renderer.
        assert "scene_change_times=_short_visuals.get(" in src
        # Degraded fallback pool wired. (The recap-scene-reuse pool is a
        # dormant capability inside _publish_youtube since the full Sunday
        # weekly-recap mode was retired in July 2026 — its is_weekly_recap
        # param now defaults False and the caller no longer passes it.)
        assert "recap_scene_pool" in src
        assert "fallback_scene_pool" in src
        # Scene-based thumbnail + variants.
        assert "long_form_thumbnail_from_scene" in src
        assert "generate_thumbnail_variants" in src

    def test_publisher_variant_helper_exists(self):
        from engine.publisher import generate_thumbnail_variants
        assert callable(generate_thumbnail_variants)


# ---------------------------------------------------------------------------
# Gallery ↔ retention join script
# ---------------------------------------------------------------------------

def _load_retention_module():
    spec = importlib.util.spec_from_file_location(
        "build_gallery_retention",
        _ROOT / "scripts" / "build_gallery_retention.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _stats_fixture():
    return {"schema_version": 1, "shows": {"tesla_shorts_time": {"videos": [
        {"video_id": "vidLONG", "show_slug": "tesla", "episode": 520,
         "kind": "long", "channel": "en", "average_view_percentage": 41.5},
        {"video_id": "vidSHORT", "show_slug": "tesla", "episode": 520,
         "kind": "short", "channel": "en", "average_view_percentage": 62.0},
        {"video_id": "vidOTHER", "show_slug": "tesla", "episode": 521,
         "kind": "long", "channel": "en", "average_view_percentage": 30.0},
    ]}}}


def _manifest_fixture():
    def img(image_id, ep, use, tags, video_id=""):
        return {"image_id": image_id, "show_slug": "tesla",
                "episode_id": ep, "intended_use": use,
                "tags": ["tesla"] + tags, "youtube_video_id": video_id}
    return {"images": [
        img("aaa", "ep520", "segment_card", ["factory"]),
        img("bbb", "ep520", "social", ["factory"]),
        img("ccc", "ep521", "segment_card", ["factory"], video_id="vidOTHER"),
        img("ddd", "ep999", "segment_card", ["orphan"]),  # no video → dropped
        img("eee", "ep520", "thumbnail_variant", ["x"]),  # not rendered use
    ]}


class TestGalleryRetentionJoin:
    def test_join_by_episode_and_video_id(self):
        mod = _load_retention_module()
        out = mod.build(_manifest_fixture(), _stats_fixture(), min_videos=1)
        tesla = out["shows"]["tesla"]
        assert tesla["images"]["aaa"]["video_id"] == "vidLONG"
        assert tesla["images"]["aaa"]["averageViewPercentage"] == 41.5
        assert tesla["images"]["bbb"]["video_id"] == "vidSHORT"
        assert tesla["images"]["ccc"]["video_id"] == "vidOTHER"
        assert "ddd" not in tesla["images"]
        assert "eee" not in tesla["images"]
        # Summary: 'factory' spans 3 distinct videos → mean of 41.5/62/30.
        factory = [t for t in tesla["summary"]["top_tags"]
                   if t["tag"] == "factory"][0]
        assert factory["videos"] == 3
        assert abs(factory["mean_retention"] - 44.5) < 0.01

    def test_min_videos_threshold_prunes_summary(self):
        mod = _load_retention_module()
        out = mod.build(_manifest_fixture(), _stats_fixture(), min_videos=4)
        assert out["shows"]["tesla"]["summary"]["top_tags"] == []

    def test_absent_data_is_clean_empty_payload(self):
        mod = _load_retention_module()
        for manifest, stats in ((None, _stats_fixture()),
                                (_manifest_fixture(), None), (None, None)):
            out = mod.build(manifest, stats)
            assert out["shows"] == {}
            assert out["schema_version"] == 1


# ---------------------------------------------------------------------------
# Nightly workflow wiring
# ---------------------------------------------------------------------------

class TestNightlyWiring:
    def test_retention_step_and_commit_path(self):
        text = (_ROOT / ".github" / "workflows"
                / "nightly-maintenance.yml").read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        steps = data["jobs"]["generate-artifacts"]["steps"]
        runs = " ".join(s.get("run", "") or "" for s in steps)
        assert "scripts/build_gallery_retention.py" in runs
        commit = [s for s in steps
                  if (s.get("uses") or "").endswith("safe-commit-push")]
        assert commit, "safe-commit-push step missing"
        assert "api/gallery_retention.json" in commit[0]["with"]["add-paths"]
        # Ordering: the join must run AFTER the analytics fetch and AFTER
        # the manifest rebuild (it joins both files fresh).
        names = [s.get("name", "") for s in steps]
        join_idx = next(i for i, s in enumerate(steps)
                        if "build_gallery_retention" in (s.get("run") or ""))
        analytics_idx = next(i for i, n in enumerate(names)
                             if "YouTube analytics" in n)
        manifest_idx = next(i for i, s in enumerate(steps)
                            if "build_gallery_manifest" in (s.get("run") or ""))
        assert join_idx > analytics_idx
        assert join_idx > manifest_idx
