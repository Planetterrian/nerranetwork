"""Tests for YouTube quota estimation."""

from engine.youtube_quota import (
    DEFAULT_DAILY_QUOTA,
    estimate_episode_units,
    estimate_network_daily_units,
    format_quota_warning,
)


def test_estimate_episode_units_long_and_short():
    est = estimate_episode_units(
        publish_long_form=True,
        publish_shorts=True,
        with_caption_track=True,
    )
    assert est.uploads == 2
    assert est.units > 3000


def test_format_quota_warning_when_over():
    summary = {
        "over_quota": True,
        "total_units": 12000,
        "daily_quota": DEFAULT_DAILY_QUOTA,
        "enabled_slugs": ["tesla", "models_agents_beginners"],
    }
    msg = format_quota_warning(summary)
    assert msg is not None
    assert "tesla" in msg


def test_network_estimate_two_enabled_shows(tmp_path):
    shows = tmp_path / "shows"
    shows.mkdir()
    for slug, enabled in (("tesla", True), ("omni_view", False)):
        (shows / f"{slug}.yaml").write_text(
            f"name: X\nslug: {slug}\nyoutube:\n  enabled: {enabled}\n",
            encoding="utf-8",
        )
    summary = estimate_network_daily_units(shows)
    assert summary["enabled_slugs"] == ["tesla"]
    assert summary["total_units"] > 0
