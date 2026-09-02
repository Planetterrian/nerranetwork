"""Drift guards for story-driven scene briefs (Sep 2026).

The fix for "the pictures don't match what's being said": prompts LEAD
with a concrete per-story scene instead of a static show keyword, the
library blend only pads with ON-TOPIC images, and every episode gets
one fresh scene per story instead of a fixed four.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine import scene_briefs as sb  # noqa: E402
from engine.grok_imagine import build_image_prompts  # noqa: E402


STORIES = [
    "Starship Flight 14 stacks at Starbase as FAA clears the pad",
    "Tesla FSD v14.1 Lite rolls out to HW3 cars in Texas",
    "Gemini 3.7 Flash beats GPT on the agent benchmark",
]


class TestDeterministicBriefs:
    def test_one_subject_per_story_in_order(self):
        out = sb.deterministic_briefs(STORIES)
        assert len(out) == 3
        assert out[0].lower().startswith("starship flight 14")
        assert "gemini" in out[2].lower()

    def test_dedups_and_caps(self):
        out = sb.deterministic_briefs(STORIES + STORIES, max_n=2)
        assert len(out) == 2


class TestModelBriefs:
    def _fake(self, text):
        return lambda prompt, **kw: (text, {})

    def test_uses_model_output_in_story_order(self, monkeypatch):
        arr = ('["Starship upper stage lowered onto its booster by the launch tower arms at dawn, wide shot",'
               ' "A Model 3 interior at night with the center screen glowing during a highway drive",'
               ' "A rack of humming AI accelerator servers in a dim data center, telephoto"]')
        monkeypatch.setattr("engine.generator._call_grok", self._fake(arr))
        out = sb.generate_scene_briefs(STORIES, show_name="SpaceX Daily")
        assert len(out) == 3
        assert out[0].startswith("Starship upper stage lowered")
        assert out[2].startswith("A rack of humming")

    def test_texty_brief_falls_back_per_slot(self, monkeypatch):
        arr = ('["A headline banner reading Flight 14 over the launch pad text overlay",'
               ' "A Model 3 interior at night with the center screen glowing during a highway drive",'
               ' "A rack of humming AI accelerator servers in a dim data center, telephoto"]')
        monkeypatch.setattr("engine.generator._call_grok", self._fake(arr))
        out = sb.generate_scene_briefs(STORIES)
        # Slot 0 rejected (caption-shaped) -> deterministic brief for story 0,
        # order preserved.
        assert out[0].lower().startswith("starship flight 14")
        assert out[1].startswith("A Model 3 interior")

    def test_garbage_response_falls_back_entirely(self, monkeypatch):
        monkeypatch.setattr("engine.generator._call_grok", self._fake("no json here"))
        out = sb.generate_scene_briefs(STORIES)
        assert out == sb.deterministic_briefs(STORIES, max_n=3)

    def test_disabled_skips_the_model(self, monkeypatch):
        def boom(*a, **k):
            raise AssertionError("model must not be called when disabled")
        monkeypatch.setattr("engine.generator._call_grok", boom)
        out = sb.generate_scene_briefs(STORIES, enabled=False)
        assert len(out) == 3

    def test_hook_is_story_zero(self, monkeypatch):
        monkeypatch.setattr("engine.generator._call_grok", self._fake("[]"))
        out = sb.generate_scene_briefs(STORIES, hook="Raptor 3 hits full thrust on the stand")
        assert out[0].lower().startswith("raptor 3")


class TestBriefFirstPrompts:
    BRIEFS = ["Starship upper stage lowered onto its booster at dawn, wide shot",
              "A Model 3 interior at night with the center screen glowing"]

    def test_briefs_lead_the_prompt(self):
        prompts = build_image_prompts(
            hook="h", image_queries=["cybertruck", "supercharger"],
            count=2, scene_briefs=self.BRIEFS,
            show_descriptor="high-energy Tesla news photo")
        assert len(prompts) == 2
        assert prompts[0].startswith("Starship upper stage lowered")
        assert "cybertruck" not in prompts[0]
        assert "ZERO text" in prompts[0]

    def test_queries_fill_only_the_remainder(self):
        prompts = build_image_prompts(
            hook="h", image_queries=["cybertruck"], count=3,
            scene_briefs=self.BRIEFS)
        assert len(prompts) == 3
        assert prompts[2].startswith("cybertruck")

    def test_briefs_work_without_any_queries(self):
        prompts = build_image_prompts(hook="h", image_queries=[], count=2,
                                      scene_briefs=self.BRIEFS)
        assert len(prompts) == 2

    def test_legacy_shape_unchanged_without_briefs(self):
        a = build_image_prompts(hook="h", image_queries=["cybertruck"], count=1)
        b = build_image_prompts(hook="h", image_queries=["cybertruck"], count=1,
                                scene_briefs=None)
        assert a == b and a[0].startswith("cybertruck")


class TestOnTopicLibraryBlend:
    def test_min_overlap_drops_off_topic_entries(self, tmp_path, monkeypatch):
        from engine import gallery_library as gl
        entries = [
            {"image_id": "a", "original_url": "https://x/a.jpg", "prompt": "starship booster catch at the tower", "episode_date": "2026-08-01"},
            {"image_id": "b", "original_url": "https://x/b.jpg", "prompt": "generic city skyline at night", "episode_date": "2026-08-02"},
        ]
        monkeypatch.setattr(gl, "_candidate_entries", lambda *a, **k: entries)
        monkeypatch.setattr(gl, "load_manifest", lambda: {})
        downloaded = []
        def fake_dl(entry, cdir, failures=None):
            p = tmp_path / f"{entry['image_id']}.jpg"; p.write_bytes(b"x"); downloaded.append(entry["image_id"]); return p
        monkeypatch.setattr(gl, "_download_entry", fake_dl)
        out = gl.select_library_scenes("spacex", aspect="16:9",
                                       context_text="Starship booster catch attempt",
                                       limit=8, cache_dir=tmp_path, min_overlap=1)
        assert [p.stem for p in out] == ["a"]
        # Legacy (min_overlap=0) still returns both, ranked.
        out2 = gl.select_library_scenes("spacex", aspect="16:9",
                                        context_text="Starship booster catch attempt",
                                        limit=8, cache_dir=tmp_path, min_overlap=0)
        assert len(out2) == 2


class TestConfigContract:
    def test_defaults_wire_the_story_driven_pipeline(self):
        from engine.config import YouTubeConfig
        c = YouTubeConfig()
        assert c.scene_briefs_enabled is True
        assert c.scenes_per_episode >= 8
        assert c.short_scenes_per_episode >= 4
        assert c.gallery_blend_min_overlap >= 1

    def test_run_show_generates_briefs_once_and_passes_them(self):
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert src.count("generate_scene_briefs(") == 1
        assert "scene_briefs=_scene_briefs or None" in src
        assert "_fresh_short_scene_count" in src
