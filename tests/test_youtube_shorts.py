"""Tests for Shorts timing and quota-stagger helpers."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from engine.youtube_shorts import (
    resolve_shorts_start_offset,
    should_upload_shorts_today,
)


def _config(*, voice_delay=10.0, intro_duration=10.0, **yt_kw):
    return SimpleNamespace(
        audio=SimpleNamespace(
            voice_intro_delay=voice_delay,
            intro_duration=intro_duration,
        ),
        youtube=SimpleNamespace(
            shorts_start_offset=yt_kw.pop("shorts_start_offset", None),
            shorts_start_mode=yt_kw.pop("shorts_start_mode", "voice"),
            shorts_duration_seconds=55.0,
            short_duration_seconds=55.0,
            publish_shorts=True,
            shorts_upload_schedule=yt_kw.pop(
                "shorts_upload_schedule", "always",
            ),
            **yt_kw,
        ),
    )


def test_voice_mode_uses_voice_intro_delay_only():
    cfg = _config(voice_delay=10.0, intro_duration=10.0)
    assert resolve_shorts_start_offset(cfg, None) == 10.0


def test_explicit_offset_wins():
    cfg = _config(shorts_start_offset=42.0)
    assert resolve_shorts_start_offset(cfg, None) == 42.0


def test_first_chapter_mode_uses_second_marker(tmp_path):
    chapters = tmp_path / "chapters_ep001.json"
    chapters.write_text(
        json.dumps({
            "chapters": [
                {"title": "Intro", "startTime": 0},
                {"title": "Story A", "startTime": 120},
                {"title": "Story B", "startTime": 300},
            ],
        }),
        encoding="utf-8",
    )
    cfg = _config(shorts_start_mode="first_chapter")
    assert resolve_shorts_start_offset(cfg, chapters) == 120.0


def test_alternate_episodes_schedule():
    cfg = _config(shorts_upload_schedule="alternate_episodes")
    assert should_upload_shorts_today(cfg, episode_num=2) is True
    assert should_upload_shorts_today(cfg, episode_num=3) is False
