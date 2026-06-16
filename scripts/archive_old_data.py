#!/usr/bin/env python3
"""Archive and prune old per-episode data files.

Tars credit_usage_*.json and metrics_ep*.json files older than
``--keep-days`` (default 180), writes the archive to
``data/archives/<slug>_<year>_<month>.tar.gz``, then deletes the
archived originals.

Run monthly from a cron workflow.

Usage::

    python scripts/archive_old_data.py                       # 180-day retention
    python scripts/archive_old_data.py --keep-days 90        # 90-day retention
    python scripts/archive_old_data.py --dry-run             # preview only
    python scripts/archive_old_data.py --show tesla          # single show
"""

from __future__ import annotations

import argparse
import datetime
import logging
import re
import sys
import tarfile
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

ARCHIVE_DIR = ROOT / "data" / "archives"

# Map show slug → on-disk subdirectory name
_SHOW_DIR_OVERRIDES = {
    "tesla": "tesla_shorts_time",
}

_NON_SHOW_YAMLS = {"_defaults", "_blocked_sources", "pronunciation_map",
                   "translation_overrides"}


def _discover_shows() -> List[str]:
    shows_dir = ROOT / "shows"
    return sorted(
        p.stem for p in shows_dir.glob("*.yaml")
        if not p.stem.startswith("_") and p.stem not in _NON_SHOW_YAMLS
    )


def _digests_dir(slug: str) -> Path:
    sub = _SHOW_DIR_OVERRIDES.get(slug, slug)
    return ROOT / "digests" / sub


def _extract_date(filename: str) -> Optional[datetime.date]:
    """Best-effort date extraction from metric/credit filenames."""
    m = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    if m:
        try:
            return datetime.date.fromisoformat(m.group(1))
        except ValueError:
            pass
    m = re.search(r"ep(\d{3,})", filename)
    if m:
        return None
    return None


def _file_age_date(path: Path) -> Optional[datetime.date]:
    """File date from name, falling back to mtime."""
    d = _extract_date(path.name)
    if d:
        return d
    try:
        return datetime.date.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return None


def archive_show(
    slug: str,
    *,
    cutoff: datetime.date,
    dry_run: bool = False,
) -> int:
    """Archive old data files for a single show.

    Returns the number of files archived (or would archive in dry-run).
    """
    ddir = _digests_dir(slug)
    if not ddir.exists():
        return 0

    patterns = ["credit_usage_*.json", "metrics_ep*.json"]
    candidates: List[Path] = []
    for pattern in patterns:
        for f in ddir.glob(pattern):
            age = _file_age_date(f)
            if age and age < cutoff:
                candidates.append(f)

    if not candidates:
        return 0

    candidates.sort(key=lambda p: p.name)
    month_str = cutoff.strftime("%Y_%m")
    archive_name = f"{slug}_{month_str}.tar.gz"
    archive_path = ARCHIVE_DIR / archive_name

    if dry_run:
        logger.info(
            "[dry-run] %s: would archive %d file(s) → %s",
            slug, len(candidates), archive_path.relative_to(ROOT),
        )
        for f in candidates:
            logger.info("  %s", f.name)
        return len(candidates)

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    mode = "w:gz" if not archive_path.exists() else "a:gz"
    if archive_path.exists():
        mode = "w:gz"

    with tarfile.open(archive_path, mode) as tar:
        for f in candidates:
            tar.add(f, arcname=f"{slug}/{f.name}")
    logger.info(
        "%s: archived %d file(s) → %s",
        slug, len(candidates), archive_path.relative_to(ROOT),
    )

    for f in candidates:
        f.unlink()
        logger.info("  deleted %s", f.name)

    return len(candidates)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Archive old per-episode data files")
    parser.add_argument("--keep-days", type=int, default=180,
                        help="Files older than this many days get archived (default: 180)")
    parser.add_argument("--show", help="Archive a single show only")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    cutoff = datetime.date.today() - datetime.timedelta(days=args.keep_days)
    logger.info(
        "Archiving data files older than %s (%d days)%s",
        cutoff, args.keep_days, " [DRY RUN]" if args.dry_run else "",
    )

    shows = [args.show] if args.show else _discover_shows()
    total = 0
    for slug in shows:
        count = archive_show(slug, cutoff=cutoff, dry_run=args.dry_run)
        total += count

    verb = "Would archive" if args.dry_run else "Archived"
    logger.info("%s %d file(s) total across %d show(s)", verb, total, len(shows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
