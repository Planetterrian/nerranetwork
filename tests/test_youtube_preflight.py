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


def _full_creds(monkeypatch):
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "id")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN_EN", "token")
    monkeypatch.setenv("PEXELS_API_KEY", "pex")
    monkeypatch.setenv("GROK_API_KEY", "grok")


def test_cover_accepts_rss_image_basename(tmp_path, monkeypatch):
    """A YouTube-enabled show whose cover is named after the title (not the
    slug) must still pass — the validator accepts the basename referenced in
    publishing.rss_image. Regression guard for the Jun 15 2026 first_principles
    outage (cover was first-principles-daily.jpg; slug-derived check failed)."""
    root = tmp_path / "repo"
    (root / "assets" / "covers").mkdir(parents=True)
    # Only the title-named cover exists — NOT the slug-derived name.
    (root / "assets" / "covers" / "first-principles-daily.jpg").write_bytes(b"\xff\xd8\xff")
    cfg = SimpleNamespace(
        slug="first_principles",
        publishing=SimpleNamespace(
            rss_image="https://nerranetwork.com/assets/covers/first-principles-daily.jpg",
        ),
        youtube=SimpleNamespace(
            enabled=True, channel="en", privacy_status="public",
            image_provider="grok", image_queries=["rocket engine factory"],
        ),
    )
    _full_creds(monkeypatch)
    issues = validate_youtube_show_ready(cfg, root)
    assert not any("cover" in i.lower() for i in issues), issues


def test_cover_still_fails_when_no_cover_anywhere(tmp_path, monkeypatch):
    """Sanity: with neither a slug-derived nor an rss_image cover present, the
    cover check still fails (the fallback is additive, not a bypass)."""
    root = tmp_path / "repo"
    (root / "assets" / "covers").mkdir(parents=True)
    cfg = SimpleNamespace(
        slug="ghost_show",
        publishing=SimpleNamespace(rss_image=""),
        youtube=SimpleNamespace(
            enabled=True, channel="en", privacy_status="public",
            image_provider="grok", image_queries=["x"],
        ),
    )
    _full_creds(monkeypatch)
    issues = validate_youtube_show_ready(cfg, root)
    assert any("cover" in i.lower() for i in issues)
