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


def test_estimate_counts_multiple_shorts():
    one = estimate_episode_units(publish_long_form=True, publish_shorts=True,
                                 shorts_count=1)
    two = estimate_episode_units(publish_long_form=True, publish_shorts=True,
                                 shorts_count=2)
    assert two.units > one.units
    assert two.uploads == 3  # long + 2 shorts
    # The delta is exactly one more Short's worth of calls.
    assert two.units - one.units == one.units - estimate_episode_units(
        publish_long_form=True, publish_shorts=False).units


def test_network_estimate_splits_channels(tmp_path):
    shows = tmp_path / "shows"
    shows.mkdir()
    (shows / "en_show.yaml").write_text(
        "name: X\nslug: en_show\nyoutube:\n  enabled: true\n  channel: en\n",
        encoding="utf-8",
    )
    (shows / "ru_show.yaml").write_text(
        "name: Y\nslug: ru_show\nyoutube:\n  enabled: true\n  channel: ru\n",
        encoding="utf-8",
    )
    summary = estimate_network_daily_units(shows)
    per_channel = summary["per_channel"]
    assert set(per_channel) == {"en", "ru"}
    assert per_channel["en"]["enabled_slugs"] == ["en_show"]
    assert per_channel["ru"]["enabled_slugs"] == ["ru_show"]
    # A RU show must never count against the EN channel's budget.
    assert per_channel["en"]["total_units"] < summary["total_units"]


def test_over_quota_is_per_channel(tmp_path):
    shows = tmp_path / "shows"
    shows.mkdir()
    # Three full-format EN shows (~2100+1700 each) bust a 6000 budget;
    # one RU show alone does not.
    for i in range(3):
        (shows / f"en{i}.yaml").write_text(
            f"name: E{i}\nslug: en{i}\nyoutube:\n  enabled: true\n  channel: en\n",
            encoding="utf-8",
        )
    (shows / "ru0.yaml").write_text(
        "name: R\nslug: ru0\nyoutube:\n  enabled: true\n  channel: ru\n",
        encoding="utf-8",
    )
    summary = estimate_network_daily_units(shows, daily_quota=6000)
    assert summary["per_channel"]["en"]["over_quota"] is True
    assert summary["per_channel"]["ru"]["over_quota"] is False
    assert summary["over_quota"] is True
    msg = format_quota_warning(summary)
    assert "channel 'en'" in msg
    assert "channel 'ru'" not in msg
