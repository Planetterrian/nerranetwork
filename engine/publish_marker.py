"""Publish-complete markers for pipeline checkpoint/resume."""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def publish_marker_path(digests_dir: Path, day: datetime.date) -> Path:
    return digests_dir / f".published_{day:%Y%m%d}.json"


def is_publish_complete(marker_path: Path) -> bool:
    if not marker_path.exists():
        return False
    try:
        data = json.loads(marker_path.read_text(encoding="utf-8"))
        return bool(data.get("complete"))
    except (OSError, json.JSONDecodeError, TypeError):
        return False


def write_publish_complete_marker(
    marker_path: Path,
    *,
    show_slug: str,
    episode_num: int,
    date_iso: str,
) -> None:
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(
        json.dumps(
            {
                "complete": True,
                "show": show_slug,
                "episode_num": episode_num,
                "date": date_iso,
                "timestamp": datetime.datetime.now(
                    datetime.timezone.utc,
                ).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.info("Publish marker written: %s", marker_path.name)
