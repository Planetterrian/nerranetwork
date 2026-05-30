"""Tests for the multi-platform (Instagram Reels / TikTok) Shorts distribution.

Covers: per-platform metadata, the safe-zone Short filter graph, the
credential-gated publisher (no-op without creds), and the distribute_short
orchestrator (no-op unless opted in; renders variant + sidecar when on).
ffmpeg / R2 / platform APIs are mocked — none run here.
"""

from __future__ import annotations

import json
import os
import types
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Per-platform metadata
# ---------------------------------------------------------------------------

class TestSocialMetadata:
    def _build(self, **kw):
        from engine.social_metadata import build_social_metadata
        base = dict(
            hook="Tesla Cybercab hits 500k preorders in 48 hours",
            show_name="Tesla Shorts Time",
            show_url="https://nerranetwork.com",
            long_form_url="https://youtu.be/abc",
            short_youtube_url="https://youtube.com/shorts/xyz",
            show_keywords=["tesla", "ev"],
        )
        base.update(kw)
        return build_social_metadata(**base)

    def test_has_all_platforms(self):
        m = self._build()
        for key in ("youtube", "instagram_reels", "tiktok"):
            assert key in m

    def test_captions_lead_with_hook(self):
        m = self._build()
        assert m["instagram_reels"]["caption"].startswith("Tesla Cybercab")
        assert m["tiktok"]["caption"].startswith("Tesla Cybercab")

    def test_hashtags_present_and_formatted(self):
        m = self._build()
        assert m["instagram_reels"]["hashtags"], "expected IG hashtags"
        assert "#" in m["instagram_reels"]["caption"]
        # TikTok adds discovery tags
        assert any(t.lower() == "fyp" for t in m["tiktok"]["hashtags"])
        # IG adds Reels tag
        assert any(t.lower() == "reels" for t in m["instagram_reels"]["hashtags"])

    def test_youtube_title_capped(self):
        m = self._build(hook="X" * 300)
        assert len(m["youtube"]["title"]) <= 100

    def test_caption_capped(self):
        m = self._build(hook="word " * 1000)
        assert len(m["instagram_reels"]["caption"]) <= 2000
        assert len(m["tiktok"]["caption"]) <= 2000

    def test_russian_localised_cta(self):
        m = self._build(is_ru=True)
        assert "Полный выпуск" in m["instagram_reels"]["caption"]


# ---------------------------------------------------------------------------
# Safe-zone Short filter graph
# ---------------------------------------------------------------------------

class TestSafeZoneFilterGraph:
    def test_default_youtube_unchanged(self):
        from engine.video import _short_form_filter_graph
        g = _short_form_filter_graph(subtitles_path="x.srt", with_url_pill=True)
        assert "MarginV=340" in g
        assert "urlpill" in g

    def test_safe_zone_lifts_captions_and_drops_url_pill(self):
        from engine.video import _short_form_filter_graph
        g = _short_form_filter_graph(
            subtitles_path="x.srt", with_url_pill=False, caption_margin_v=480,
        )
        assert "MarginV=480" in g
        assert "MarginV=340" not in g
        assert "urlpill" not in g

    def test_style_helper(self):
        from engine.video import _shorts_subtitle_style
        assert _shorts_subtitle_style().endswith("MarginV=340")
        assert _shorts_subtitle_style(480).endswith("MarginV=480")


# ---------------------------------------------------------------------------
# Credential-gated publisher
# ---------------------------------------------------------------------------

class TestPublisherGating:
    def _clear_creds(self, monkeypatch):
        for k in ("IG_ACCESS_TOKEN", "IG_USER_ID", "TIKTOK_ACCESS_TOKEN"):
            monkeypatch.delenv(k, raising=False)

    def test_instagram_skips_without_creds(self, monkeypatch):
        self._clear_creds(monkeypatch)
        from engine.social_publisher import publish_to_instagram
        r = publish_to_instagram(video_public_url="https://x/v.mp4", caption="hi")
        assert r["status"] == "skipped"

    def test_tiktok_skips_without_creds(self, monkeypatch):
        self._clear_creds(monkeypatch)
        from engine.social_publisher import publish_to_tiktok
        r = publish_to_tiktok(video_path=Path("/tmp/none.mp4"), caption="hi")
        assert r["status"] == "skipped"

    def test_instagram_skips_without_public_url(self, monkeypatch):
        monkeypatch.setenv("IG_ACCESS_TOKEN", "t")
        monkeypatch.setenv("IG_USER_ID", "1")
        from engine.social_publisher import publish_to_instagram
        r = publish_to_instagram(video_public_url="", caption="hi")
        assert r["status"] == "skipped"

    def test_dispatcher_only_requested_platforms(self, monkeypatch):
        self._clear_creds(monkeypatch)
        from engine.social_publisher import publish_short
        r = publish_short(video_path=Path("/tmp/x.mp4"), metadata={}, instagram=True, tiktok=False)
        assert set(r) == {"instagram_reels"}
        assert r["instagram_reels"]["status"] == "skipped"

    def test_dispatcher_never_raises(self, monkeypatch):
        self._clear_creds(monkeypatch)
        from engine.social_publisher import publish_short
        # metadata missing keys must not crash
        assert publish_short(video_path=Path("/tmp/x.mp4"), metadata={}, tiktok=True)


# ---------------------------------------------------------------------------
# distribute_short orchestrator
# ---------------------------------------------------------------------------

def _fake_config(enabled: bool):
    yt = types.SimpleNamespace(
        multi_platform_enabled=enabled,
        social_drop_url_pill=True,
        social_caption_margin_v=480,
        social_r2_prefix="",
        instagram_enabled=False,
        tiktok_enabled=False,
    )
    return types.SimpleNamespace(youtube=yt, name="Tesla Shorts Time", slug="tesla", keywords=["tesla"])


class TestDistributeShort:
    def test_noop_when_disabled(self, tmp_path):
        from engine.social_distribution import distribute_short
        out = distribute_short(
            _fake_config(False),
            audio_path=tmp_path / "a.mp3", cover_path=tmp_path / "c.jpg",
            work_dir=tmp_path, base_name="Ep1", hook="A hook", show_name="Tesla",
            show_url="https://nerranetwork.com",
        )
        assert out == {}

    def test_enabled_renders_variant_and_sidecar(self, tmp_path, monkeypatch):
        # Mock the ffmpeg render to just create the file.
        import engine.video as video

        def _fake_build(audio_path, cover_path, output_path, **kw):
            Path(output_path).write_bytes(b"\x00")
            # safe-zone kwargs must be passed through
            assert kw.get("end_card") is False
            assert kw.get("drop_url_pill") is True
            assert kw.get("caption_margin_v") == 480
            return output_path

        monkeypatch.setattr(video, "build_short_video", _fake_build)

        from engine.social_distribution import distribute_short
        out = distribute_short(
            _fake_config(True),
            audio_path=tmp_path / "a.mp3", cover_path=tmp_path / "c.jpg",
            work_dir=tmp_path, base_name="Ep1", short_suffix="_1",
            hook="A unique hook line", show_name="Tesla Shorts Time",
            show_url="https://nerranetwork.com", show_keywords=["tesla"],
        )
        assert out.get("video", "").endswith("Ep1_short_1_social.mp4")
        sidecar = Path(out["sidecar"])
        assert sidecar.exists()
        meta = json.loads(sidecar.read_text())
        assert "instagram_reels" in meta and "tiktok" in meta
        # Posting was attempted but skipped (no creds / flags off).
        assert out.get("posted") == {} or all(
            v["status"] == "skipped" for v in out.get("posted", {}).values()
        )
