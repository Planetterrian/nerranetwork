"""YouTube Data API v3 quota estimation for rollout planning."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import yaml

# Documented costs (units per call) — keep in sync with engine/youtube.py.
QUOTA_VIDEO_INSERT = 1600
QUOTA_THUMBNAIL_SET = 50
QUOTA_PLAYLIST_INSERT = 50
QUOTA_CAPTION_INSERT = 400
DEFAULT_DAILY_QUOTA = 10_000


@dataclass
class QuotaEstimate:
    """Estimated quota for one show on one day."""
    long_form: bool
    shorts: bool
    caption_track: bool
    units: int

    @property
    def uploads(self) -> int:
        n = 0
        if self.long_form:
            n += 1
        if self.shorts:
            n += 1
        return n


def estimate_episode_units(
    *,
    publish_long_form: bool = True,
    publish_shorts: bool = True,
    with_thumbnail: bool = True,
    with_playlist: bool = True,
    with_caption_track: bool = True,
) -> QuotaEstimate:
    """Return per-episode quota breakdown."""
    units = 0
    if publish_long_form:
        units += QUOTA_VIDEO_INSERT
        if with_thumbnail:
            units += QUOTA_THUMBNAIL_SET
        if with_playlist:
            units += QUOTA_PLAYLIST_INSERT
        if with_caption_track:
            units += QUOTA_CAPTION_INSERT
    if publish_shorts:
        units += QUOTA_VIDEO_INSERT
        if with_thumbnail:
            units += QUOTA_THUMBNAIL_SET
        if with_playlist:
            units += QUOTA_PLAYLIST_INSERT
    return QuotaEstimate(
        long_form=publish_long_form,
        shorts=publish_shorts,
        caption_track=publish_long_form and with_caption_track,
        units=units,
    )


def list_youtube_enabled_slugs(shows_dir: Path) -> List[str]:
    """Return slugs with ``youtube.enabled: true``."""
    enabled: List[str] = []
    for path in sorted(shows_dir.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        slug = raw.get("slug") or path.stem
        yt = raw.get("youtube") or {}
        if yt.get("enabled") is True:
            enabled.append(slug)
    return enabled


def estimate_network_daily_units(
    shows_dir: Path,
    *,
    daily_quota: int = DEFAULT_DAILY_QUOTA,
) -> dict:
    """Sum quota for all enabled shows (reads show YAML only)."""
    total = 0
    per_show: dict[str, int] = {}
    for path in sorted(shows_dir.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        slug = raw.get("slug") or path.stem
        yt = raw.get("youtube") or {}
        if yt.get("enabled") is not True:
            continue
        est = estimate_episode_units(
            publish_long_form=bool(yt.get("publish_long_form", True)),
            publish_shorts=bool(yt.get("publish_shorts", True)),
        )
        per_show[slug] = est.units
        total += est.units
    return {
        "enabled_slugs": list(per_show.keys()),
        "per_show_units": per_show,
        "total_units": total,
        "daily_quota": daily_quota,
        "over_quota": total > daily_quota,
        "headroom_units": daily_quota - total,
    }


def format_quota_warning(summary: dict) -> Optional[str]:
    """Human-readable warning when enabled shows exceed default quota."""
    if not summary.get("over_quota"):
        return None
    slugs = ", ".join(summary.get("enabled_slugs") or [])
    return (
        f"YouTube quota: estimated {summary['total_units']} units/day for "
        f"enabled shows ({slugs}) exceeds default {summary['daily_quota']} "
        f"(~{summary['daily_quota'] // QUOTA_VIDEO_INSERT} video inserts). "
        "Request a quota increase or set youtube.shorts_upload_schedule: "
        "alternate_episodes on some shows."
    )
