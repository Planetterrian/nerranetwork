"""Tests for engine.grok_imagine — Grok Imagine API wrapper.

Three layers:
  1. Prompt construction — deterministic, no network. Pins how the
     hook + show image_queries get woven into a generation prompt
     so a future tweak doesn't silently regress prompt quality.
  2. Cost-table sanity — pin the May 2026 published prices so a
     copy-paste typo in MODEL_COST_USD trips a test instead of
     billing the operator at the wrong rate.
  3. Fallback behaviour — when the API returns an error or no API
     key is set, the helper returns a SceneSet containing the show
     cover, never crashes the pipeline.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import List
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

class TestBuildImagePrompts:

    def test_returns_count_prompts_when_queries_match(self):
        from engine.grok_imagine import build_image_prompts
        prompts = build_image_prompts(
            hook="Tesla unveils Cybertruck price drop",
            image_queries=["tesla car", "tesla factory", "cybertruck"],
            count=3,
            aspect="16:9",
        )
        assert len(prompts) == 3
        # Hook is woven in to every prompt so episodes get unique imagery.
        for p in prompts:
            assert "Tesla unveils Cybertruck price drop" in p

    def test_recycles_queries_when_count_exceeds_query_list(self):
        """If the operator's image_queries list has 3 entries but we
        want 8 prompts, the extra prompts cycle through the queries
        with a ``variant`` marker so the model sees distinct strings."""
        from engine.grok_imagine import build_image_prompts
        prompts = build_image_prompts(
            hook="Big news",
            image_queries=["a", "b", "c"],
            count=8,
        )
        assert len(prompts) == 8
        # Distinct prompts even though queries recycle.
        assert len(set(prompts)) == 8

    def test_vertical_aspect_includes_9_16_framing_hint(self):
        from engine.grok_imagine import build_image_prompts
        v = build_image_prompts(
            hook="x", image_queries=["q"], count=1, aspect="9:16",
        )
        assert "9:16" in v[0] or "vertical" in v[0].lower()
        h = build_image_prompts(
            hook="x", image_queries=["q"], count=1, aspect="16:9",
        )
        assert "16:9" in h[0] or "cinematic" in h[0].lower()

    def test_show_descriptor_is_injected(self):
        """``grok_image_descriptor`` is the per-show tone cue (e.g.
        ``high-energy Tesla news photo``). Must appear in every prompt
        so the model picks up the show's voice."""
        from engine.grok_imagine import build_image_prompts
        prompts = build_image_prompts(
            hook="x",
            image_queries=["a", "b"],
            count=2,
            show_descriptor="high-energy Tesla news photo",
        )
        for p in prompts:
            assert "high-energy Tesla news photo" in p

    def test_empty_queries_returns_empty_list(self):
        from engine.grok_imagine import build_image_prompts
        assert build_image_prompts(hook="x", image_queries=[], count=8) == []

    def test_no_hook_still_yields_prompts(self):
        """The pipeline runs even when the hook is empty (e.g. early
        in fetch). The prompt builder shouldn't crash, and prompts
        should still be deterministic."""
        from engine.grok_imagine import build_image_prompts
        prompts = build_image_prompts(
            hook="", image_queries=["tesla car"], count=1,
        )
        assert prompts and "tesla car" in prompts[0]


# ---------------------------------------------------------------------------
# Cost table — pin the May 2026 published prices
# ---------------------------------------------------------------------------

class TestCostTable:

    def test_standard_price_is_two_cents(self):
        from engine.grok_imagine import MODEL_COST_USD
        assert MODEL_COST_USD["grok-imagine-image"] == 0.02

    def test_pro_price_is_seven_cents(self):
        from engine.grok_imagine import MODEL_COST_USD
        assert MODEL_COST_USD["grok-imagine-image-pro"] == 0.07

    def test_aliases_map_to_same_prices(self):
        """Operators sometimes type ``grok-imagine-standard`` /
        ``grok-imagine-pro`` instead of the API IDs. The cost table
        recognises both spellings so cost tracking stays accurate
        regardless."""
        from engine.grok_imagine import MODEL_COST_USD
        assert MODEL_COST_USD["grok-imagine-standard"] == MODEL_COST_USD["grok-imagine-image"]
        assert MODEL_COST_USD["grok-imagine-pro"] == MODEL_COST_USD["grok-imagine-image-pro"]


# ---------------------------------------------------------------------------
# Fallback behaviour — never crash the pipeline
# ---------------------------------------------------------------------------

class TestFetchSceneImagesGrokFallbacks:

    def test_no_api_key_returns_fallback_scene_set(self, tmp_path: Path, monkeypatch):
        from engine.grok_imagine import fetch_scene_images_grok
        # Both env vars empty — the wrapper should fall back gracefully.
        monkeypatch.delenv("GROK_API_KEY", raising=False)
        monkeypatch.delenv("XAI_API_KEY", raising=False)
        cover = tmp_path / "cover.jpg"
        cover.write_bytes(b"\xff\xd8\xff\xd9")  # tiny valid-ish JPEG
        result = fetch_scene_images_grok(
            work_dir=tmp_path,
            episode_num=1,
            prompts=["tesla supercharger"],
            fallback_cover=cover,
        )
        assert result.scene_set.is_fallback is True
        assert len(result.scene_set) == 1
        assert result.scene_set.scenes[0].path == cover
        assert result.cost_usd == 0.0

    def test_empty_prompts_returns_fallback(self, tmp_path: Path, monkeypatch):
        from engine.grok_imagine import fetch_scene_images_grok
        monkeypatch.setenv("GROK_API_KEY", "sk-test")
        cover = tmp_path / "cover.jpg"
        cover.write_bytes(b"\xff\xd8\xff\xd9")
        result = fetch_scene_images_grok(
            work_dir=tmp_path,
            episode_num=1,
            prompts=[],
            fallback_cover=cover,
        )
        assert result.scene_set.is_fallback is True

    def test_api_error_falls_back_to_cover(self, tmp_path: Path, monkeypatch):
        """The API endpoint returning a 500 should not blow up the
        pipeline — every prompt fails, the wrapper returns the cover
        as a single scene with cost 0 and the failures listed."""
        from engine import grok_imagine

        monkeypatch.setenv("GROK_API_KEY", "sk-test")
        cover = tmp_path / "cover.jpg"
        cover.write_bytes(b"\xff\xd8\xff\xd9")

        def _fake_request(*a, **kw):
            raise grok_imagine.GrokImagineError("HTTP 500: server error")

        monkeypatch.setattr(grok_imagine, "_request_one_image", _fake_request)

        result = grok_imagine.fetch_scene_images_grok(
            work_dir=tmp_path,
            episode_num=42,
            prompts=["a", "b"],
            fallback_cover=cover,
        )
        assert result.scene_set.is_fallback is True
        assert result.images_generated == 0
        assert len(result.failures) == 2
        assert result.cost_usd == 0.0

    def test_partial_success_still_returns_real_scenes(
        self, tmp_path: Path, monkeypatch,
    ):
        """If 6 of 8 prompts succeed and 2 fail, the result has 6 real
        scenes (not the fallback cover). Cost reflects only the
        successful generations."""
        from engine import grok_imagine

        monkeypatch.setenv("GROK_API_KEY", "sk-test")
        cover = tmp_path / "cover.jpg"
        cover.write_bytes(b"\xff\xd8\xff\xd9")

        # Make the 4th call fail; the rest succeed with a tiny PNG.
        tiny_png = base64.b64decode(
            b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgAAIAAAUAAeImBZsAAAAASUVORK5CYII="
        )
        call_count = {"n": 0}

        def _fake_request(prompt, *, api_key, model, size, **_kw):
            call_count["n"] += 1
            if call_count["n"] == 4:
                raise grok_imagine.GrokImagineError("HTTP 400: prompt rejected")
            return tiny_png

        monkeypatch.setattr(grok_imagine, "_request_one_image", _fake_request)

        result = grok_imagine.fetch_scene_images_grok(
            work_dir=tmp_path,
            episode_num=10,
            prompts=[f"q{i}" for i in range(8)],
            fallback_cover=cover,
            model="grok-imagine-image",
        )
        assert result.scene_set.is_fallback is False
        assert result.images_generated == 7
        assert len(result.failures) == 1
        # 7 successes × $0.02
        assert result.cost_usd == pytest.approx(0.14, rel=1e-3)


# ---------------------------------------------------------------------------
# Aspect → API size mapping
# ---------------------------------------------------------------------------

class TestApiSizeForAspect:

    def test_horizontal_returns_landscape_size(self):
        from engine.grok_imagine import _api_size_for_aspect
        assert _api_size_for_aspect("16:9") == "1792x1024"

    def test_vertical_returns_portrait_size(self):
        from engine.grok_imagine import _api_size_for_aspect
        out = _api_size_for_aspect("9:16")
        # Portrait — height > width.
        w, h = (int(x) for x in out.split("x"))
        assert h > w

    def test_square_returns_square(self):
        from engine.grok_imagine import _api_size_for_aspect
        assert _api_size_for_aspect("1:1") == "1024x1024"
