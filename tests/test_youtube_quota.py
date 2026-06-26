"""Tests for YouTube quota estimation."""

from engine.youtube_quota import (
    DEFAULT_DAILY_QUOTA,
    estimate_episode_units,
    estimate_network_daily_units,
    format_quota_warning,
    resolve_daily_quota,
)


def test_default_daily_quota_reflects_200k_grant():
    # Operator raised the quota 10k -> 200k (June 2026).
    assert DEFAULT_DAILY_QUOTA == 200_000


def test_resolve_daily_quota_precedence(monkeypatch):
    monkeypatch.delenv("YOUTUBE_DAILY_QUOTA", raising=False)
    monkeypatch.delenv("YOUTUBE_DAILY_QUOTA_EN", raising=False)
    # Default when nothing set.
    assert resolve_daily_quota("en") == DEFAULT_DAILY_QUOTA
    # Explicit override always wins.
    assert resolve_daily_quota("en", override=5000) == 5000
    # Global env beats default.
    monkeypatch.setenv("YOUTUBE_DAILY_QUOTA", "150000")
    assert resolve_daily_quota("ru") == 150000
    # Per-channel env beats global.
    monkeypatch.setenv("YOUTUBE_DAILY_QUOTA_EN", "300000")
    assert resolve_daily_quota("en") == 300000
    assert resolve_daily_quota("ru") == 150000  # ru still on global


def test_network_estimate_resolves_env_budget(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUTUBE_DAILY_QUOTA_EN", "9000")
    shows = tmp_path / "shows"
    shows.mkdir()
    # Two full-format EN shows (~3800 each = 7600) under a 9000 budget.
    for i in range(2):
        (shows / f"en{i}.yaml").write_text(
            f"name: E{i}\nslug: en{i}\nyoutube:\n  enabled: true\n  channel: en\n",
            encoding="utf-8",
        )
    summary = estimate_network_daily_units(shows)
    assert summary["per_channel"]["en"]["daily_quota"] == 9000
    assert summary["per_channel"]["en"]["over_quota"] is False
    # A third show would bust the env budget.
    (shows / "en2.yaml").write_text(
        "name: E2\nslug: en2\nyoutube:\n  enabled: true\n  channel: en\n",
        encoding="utf-8",
    )
    summary = estimate_network_daily_units(shows)
    assert summary["per_channel"]["en"]["over_quota"] is True


def test_network_estimate_tracks_uploads_and_cadence(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUTUBE_SAFE_DAILY_UPLOADS", "12")
    # The cadence flag is read at import time, so the threshold for the flag
    # itself comes from the module constant; this test only pins the uploads
    # accounting and the flag wiring at a low manual count.
    shows = tmp_path / "shows"
    shows.mkdir()
    (shows / "en0.yaml").write_text(
        "name: E0\nslug: en0\nyoutube:\n  enabled: true\n  channel: en\n"
        "  shorts_per_episode: 2\n",
        encoding="utf-8",
    )
    summary = estimate_network_daily_units(shows)
    # long-form + 2 shorts = 3 uploads.
    assert summary["per_channel"]["en"]["uploads"] == 3
    assert summary["per_channel"]["en"]["over_safe_cadence"] is False


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
