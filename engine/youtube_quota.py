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
    shorts_count: int = 1

    @property
    def uploads(self) -> int:
        n = 0
        if self.long_form:
            n += 1
        if self.shorts:
            n += self.shorts_count
        return n


def estimate_episode_units(
    *,
    publish_long_form: bool = True,
    publish_shorts: bool = True,
    shorts_count: int = 1,
    with_thumbnail: bool = True,
    with_playlist: bool = True,
    with_caption_track: bool = True,
) -> QuotaEstimate:
    """Return per-episode quota breakdown.

    *shorts_count* mirrors ``youtube.shorts_per_episode`` — each Short is
    its own ``videos.insert`` (June 2026 fix: the estimator previously
    counted one Short regardless, undercounting multi-Shorts shows).
    """
    units = 0
    if publish_long_form:
        units += QUOTA_VIDEO_INSERT
        if with_thumbnail:
            units += QUOTA_THUMBNAIL_SET
        if with_playlist:
            units += QUOTA_PLAYLIST_INSERT
        if with_caption_track:
            units += QUOTA_CAPTION_INSERT
    shorts_count = max(1, int(shorts_count or 1))
    if publish_shorts:
        per_short = QUOTA_VIDEO_INSERT
        if with_thumbnail:
            per_short += QUOTA_THUMBNAIL_SET
        if with_playlist:
            per_short += QUOTA_PLAYLIST_INSERT
        units += per_short * shorts_count
    return QuotaEstimate(
        long_form=publish_long_form,
        shorts=publish_shorts,
        caption_track=publish_long_form and with_caption_track,
        units=units,
        shorts_count=shorts_count if publish_shorts else 0,
    )


def list_youtube_enabled_slugs(shows_dir: Path) -> List[str]:
    """Return slugs with ``youtube.enabled: true``."""
    from engine.config import discover_show_slugs, load_config

    enabled: List[str] = []
    for slug in discover_show_slugs(shows_dir):
        yaml_path = shows_dir / f"{slug}.yaml"
        try:
            cfg = load_config(yaml_path)
            if getattr(getattr(cfg, "youtube", None), "enabled", False):
                enabled.append(slug)
        except Exception:
            # Fall back to raw parse if config load fails
            raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            yt = raw.get("youtube") or {}
            if yt.get("enabled") is True:
                enabled.append(slug)
    return enabled


def estimate_network_daily_units(
    shows_dir: Path,
    *,
    daily_quota: int = DEFAULT_DAILY_QUOTA,
) -> dict:
    """Sum quota for all enabled shows (reads show YAML only).

    June 2026: quota is **per channel** — @NerraNetwork (``channel: en``)
    and @NerraRU (``channel: ru``) each get their own daily budget, so
    shows are grouped by channel and ``over_quota`` means "at least one
    channel exceeds its own quota". Top-level ``total_units`` keeps the
    legacy all-shows-summed meaning for dashboards; per-channel detail
    lives under ``per_channel``.
    """
    from engine.config import discover_show_slugs, load_config

    per_show: dict[str, int] = {}
    show_channel: dict[str, str] = {}
    for slug in discover_show_slugs(shows_dir):
        yaml_path = shows_dir / f"{slug}.yaml"
        try:
            cfg = load_config(yaml_path)
            yt = getattr(cfg, "youtube", None)
            if not getattr(yt, "enabled", False):
                continue
            est = estimate_episode_units(
                publish_long_form=getattr(yt, "publish_long_form", True),
                publish_shorts=getattr(yt, "publish_shorts", True),
                shorts_count=getattr(yt, "shorts_per_episode", 1),
            )
            per_show[slug] = est.units
            show_channel[slug] = (getattr(yt, "channel", "en") or "en").lower()
        except Exception:
            # Fallback to raw parse
            raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            yt = raw.get("youtube") or {}
            if yt.get("enabled") is not True:
                continue
            est = estimate_episode_units(
                publish_long_form=bool(yt.get("publish_long_form", True)),
                publish_shorts=bool(yt.get("publish_shorts", True)),
                shorts_count=int(yt.get("shorts_per_episode", 1) or 1),
            )
            per_show[slug] = est.units
            show_channel[slug] = str(yt.get("channel", "en") or "en").lower()

    per_channel: dict[str, dict] = {}
    for slug, units in per_show.items():
        ch = show_channel[slug]
        entry = per_channel.setdefault(ch, {
            "enabled_slugs": [],
            "total_units": 0,
            "daily_quota": daily_quota,
        })
        entry["enabled_slugs"].append(slug)
        entry["total_units"] += units
    for entry in per_channel.values():
        entry["over_quota"] = entry["total_units"] > entry["daily_quota"]
        entry["headroom_units"] = entry["daily_quota"] - entry["total_units"]

    total = sum(per_show.values())
    over = any(e["over_quota"] for e in per_channel.values())
    min_headroom = min(
        (e["headroom_units"] for e in per_channel.values()),
        default=daily_quota,
    )

    return {
        "enabled_slugs": list(per_show.keys()),
        "per_show_units": per_show,
        "per_channel": per_channel,
        "total_units": total,
        "daily_quota": daily_quota,
        "over_quota": over,
        # Tightest channel's headroom — the number that matters for
        # "can I enable one more upload anywhere".
        "headroom_units": min_headroom,
    }


def format_quota_warning(summary: dict) -> Optional[str]:
    """Human-readable warning when an enabled channel exceeds its quota."""
    if not summary.get("over_quota"):
        return None
    per_channel = summary.get("per_channel") or {}
    over_channels = {
        ch: e for ch, e in per_channel.items() if e.get("over_quota")
    }
    if over_channels:
        parts = []
        for ch, e in sorted(over_channels.items()):
            slugs = ", ".join(e.get("enabled_slugs") or [])
            parts.append(
                f"channel '{ch}' projected {e['total_units']} units/day "
                f"({slugs}) vs quota {e['daily_quota']}"
            )
        detail = "; ".join(parts)
    else:  # legacy summaries without per_channel
        slugs = ", ".join(summary.get("enabled_slugs") or [])
        detail = (
            f"estimated {summary['total_units']} units/day for enabled "
            f"shows ({slugs}) exceeds {summary['daily_quota']}"
        )
    return (
        f"YouTube quota: {detail} "
        f"(~{summary['daily_quota'] // QUOTA_VIDEO_INSERT} video inserts/channel). "
        "Request a quota increase, drop shorts_per_episode, set "
        "publish_long_form: false, or use shorts_upload_schedule: "
        "alternate_episodes."
    )
