"""Tests for YouTube preflight validation."""

from pathlib import Path
from types import SimpleNamespace

from engine.youtube_preflight import validate_youtube_show_ready


def test_enabled_show_requires_cover_and_queries(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / "shows").mkdir(parents=True)
    cfg = SimpleNamespace(
        slug="tesla",
        youtube=SimpleNamespace(
            enabled=True,
            channel="en",
            privacy_status="public",
            image_provider="pexels",
            image_queries=["tesla car"],
        ),
    )
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "id")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN_EN", "token")
    monkeypatch.setenv("PEXELS_API_KEY", "pex")
    issues = validate_youtube_show_ready(cfg, root)
    assert any("cover" in i.lower() for i in issues)
