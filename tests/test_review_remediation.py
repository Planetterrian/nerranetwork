"""Regression tests for May 2026 network review remediation."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from engine.blog import (
    blog_rss_item_title,
    collect_blog_posts_from_digests,
    regenerate_show_blog_rss,
)
from engine.config import load_config

REPO = Path(__file__).resolve().parent.parent


class TestMinAudioDurationConfig:
    def test_defaults_audio_block_resolves_min_duration(self):
        cfg = load_config(REPO / "shows" / "omni_view.yaml")
        assert cfg.min_audio_duration == 180

    def test_tesla_override_wins(self):
        cfg = load_config(REPO / "shows" / "tesla.yaml")
        assert cfg.min_audio_duration == 300


class TestBlogRssTitle:
    def test_prefers_hook_over_show_name(self):
        meta = {"title": "Tesla Shorts Time", "hook": "Cybertruck hits new record"}
        assert blog_rss_item_title(meta, "Tesla Shorts Time") == "Cybertruck hits new record"


class TestPublishMarker:
    def test_marker_helpers(self, tmp_path):
        from engine.publish_marker import (
            is_publish_complete,
            publish_marker_path,
            write_publish_complete_marker,
        )

        marker = publish_marker_path(tmp_path, date(2026, 5, 20))
        assert not is_publish_complete(marker)
        write_publish_complete_marker(
            marker, show_slug="tesla", episode_num=1, date_iso="2026-05-20",
        )
        assert is_publish_complete(marker)
        data = json.loads(marker.read_text())
        assert data["complete"] is True


class TestTeslaScrub:
    def test_scrubs_unavailable_price_line(self):
        from shows.hooks.tesla import scrub_unavailable_tsla_from_digest

        text = (
            "# Tesla Shorts Time\n"
            "**REAL-TIME TSLA price:** $0.00 (price unavailable)\n"
            "**HOOK:** Record deal\n"
        )
        out = scrub_unavailable_tsla_from_digest(text)
        assert "unavailable" not in out
        assert "Record deal" in out


class TestResumePublish:
    def test_should_resume_when_mp3_without_marker(self, tmp_path):
        from engine.pipeline_resume import should_resume_publish
        from engine.publish_marker import publish_marker_path

        mp3 = tmp_path / "ep.mp3"
        mp3.write_bytes(b"x" * 1000)
        marker = publish_marker_path(tmp_path, date(2026, 5, 20))
        assert should_resume_publish(mp3, marker, test_mode=False, dry_run=False)

    def test_should_not_resume_when_marker_complete(self, tmp_path):
        from engine.pipeline_resume import should_resume_publish
        from engine.publish_marker import (
            publish_marker_path,
            write_publish_complete_marker,
        )

        mp3 = tmp_path / "ep.mp3"
        mp3.write_bytes(b"x" * 1000)
        marker = publish_marker_path(tmp_path, date(2026, 5, 20))
        write_publish_complete_marker(
            marker, show_slug="tesla", episode_num=1, date_iso="2026-05-20",
        )
        assert not should_resume_publish(mp3, marker, test_mode=False, dry_run=False)


class TestShowPageSchemaUrls:
    def test_schema_urls_are_absolute(self):
        from generate_html import GITHUB_RAW, NETWORK_SHOWS

        cfg = NETWORK_SHOWS["tesla"]
        feed = f"{GITHUB_RAW}/{cfg['rss_file']}"
        img = f"{GITHUB_RAW}/{cfg['podcast_image'].lstrip('/')}"
        assert feed == "https://nerranetwork.com/podcast.rss"
        assert feed.startswith("https://")
        assert img.startswith("https://nerranetwork.com/assets/")


class TestBlogRssRegeneration:
    def test_collect_posts_from_tesla_digests(self):
        digest_dir = REPO / "digests" / "tesla_shorts_time"
        if not digest_dir.is_dir():
            pytest.skip("tesla digest dir missing")
        posts = collect_blog_posts_from_digests(
            "tesla", "Tesla Shorts Time", digest_dir, max_files=5,
        )
        assert posts
        assert posts[0].get("episode_num", 0) > 0

    def test_regenerate_uc_blog_rss_file(self, tmp_path):
        digest_dir = tmp_path / "digests" / "unintended_consequences"
        digest_dir.mkdir(parents=True)
        digest_dir.joinpath("UC_Ep001_20260501.md").write_text(
            "# Unintended Consequences\n**HOOK:** Test hook\n**Date:** May 1, 2026\n\nBody.",
            encoding="utf-8",
        )
        out = regenerate_show_blog_rss(
            "unintended_consequences",
            "Unintended Consequences",
            tmp_path,
        )
        assert out is not None
        assert out.name == "blog_unintended_consequences.rss"
        assert "Test hook" in out.read_text(encoding="utf-8")
