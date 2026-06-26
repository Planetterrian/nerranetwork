"""Tests for LLM-optimized YouTube titles (engine.youtube_titles) and the
optimized_title wiring in engine.video_metadata."""

import types

import engine.youtube_titles as yt
from engine.youtube_titles import (
    YOUTUBE_TITLE_HARD_MAX,
    _clean_title,
    generate_youtube_titles,
)


def test_clean_title_strips_noise():
    assert _clean_title('1. "Tesla Robotaxi Goes Live"') == "Tesla Robotaxi Goes Live"
    assert _clean_title("- Why SpaceX Just Changed Orbit") == "Why SpaceX Just Changed Orbit"
    assert _clean_title("Title: **Big AI News** #ai") == "Big AI News ai"
    # Angle brackets (YouTube rejects them) are removed.
    assert "<" not in _clean_title("A < B drop") and ">" not in _clean_title("A > B")


def _fake_grok(text):
    def _call(prompt, **kwargs):
        return text, {"model": "grok-4.3"}
    return _call


def test_generate_titles_parses_and_dedupes(monkeypatch):
    out = "Tesla FSD v14 Ships\nTesla FSD v14 Ships\nThe Robotaxi Math Nobody Ran\n"
    monkeypatch.setattr("engine.generator._call_grok", _fake_grok(out))
    titles = generate_youtube_titles(
        hook="Tesla ships FSD", digest_text="body", show_name="Tesla Shorts Time",
        episode_num=42, keywords=["tesla"], n=3,
    )
    assert titles == ["Tesla FSD v14 Ships", "The Robotaxi Math Nobody Ran"]


def test_generate_titles_drops_overlong(monkeypatch):
    long_line = "X" * (YOUTUBE_TITLE_HARD_MAX + 5)
    monkeypatch.setattr("engine.generator._call_grok",
                        _fake_grok(f"{long_line}\nShort Good Title\n"))
    titles = generate_youtube_titles(
        hook="h", digest_text="d", show_name="S", episode_num=1, n=3,
    )
    assert titles == ["Short Good Title"]


def test_generate_titles_returns_empty_on_failure(monkeypatch):
    def _boom(prompt, **kwargs):
        raise RuntimeError("no api key")
    monkeypatch.setattr("engine.generator._call_grok", _boom)
    assert generate_youtube_titles(
        hook="h", digest_text="d", show_name="S", episode_num=1) == []


def _fake_config():
    pub = types.SimpleNamespace(rss_title="Tesla Shorts Time", base_url="https://x.com",
                                rss_link="https://x.com/tesla")
    ytc = types.SimpleNamespace(synthetic_disclosure="", pinned_comment_template="",
                                category_id=28, default_language="en", tags=[])
    return types.SimpleNamespace(publishing=pub, youtube=ytc, name="Tesla Shorts Time",
                                 keywords=["tesla"])


def test_long_form_metadata_prefers_optimized_title():
    from engine.video_metadata import build_long_form_metadata
    meta = build_long_form_metadata(
        _fake_config(), episode_num=42, today_str="2026-06-26",
        hook="Tesla ships something", digest_text="Body text here.",
        audio_url="https://x.com/a.mp3", optimized_title="Robotaxi Goes Driverless Today",
    )
    assert meta["title"] == "Robotaxi Goes Driverless Today"


def test_long_form_metadata_falls_back_to_hook():
    from engine.video_metadata import build_long_form_metadata
    meta = build_long_form_metadata(
        _fake_config(), episode_num=42, today_str="2026-06-26",
        hook="Tesla ships something big", digest_text="Body.",
        audio_url="", optimized_title="",
    )
    assert meta["title"].startswith("Tesla ships something big")
