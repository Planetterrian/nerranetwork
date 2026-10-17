#!/usr/bin/env python3
"""Post the @nerranetwork X posts that are due (Oct 11 2026).

Run every half hour by .github/workflows/x-queue.yml, which the scheduler
Worker dispatches on Pacific time between 6:31 AM and 7:31 PM. The queue,
its slots and the retry rules live in engine/x_queue.py. Exit code 1 only
when a post failed for good, so the workflow run shows red for it.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import x_queue  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("post_x_queue")


def main() -> int:
    url, key = x_queue._db()
    if not (url and key):
        logger.warning("X queue not configured (X_QUEUE_SUPABASE_URL/KEY); nothing to do")
        return 0
    results = x_queue.post_due()
    if not results:
        logger.info("Nothing due")
    for r in results:
        if r["status"] == "posted":
            logger.info("Posted %s: %s", r["show"], r["url"])
        elif r["status"] == "retry":
            logger.warning("%s did not post (%s); retrying in 30 minutes", r["show"], r["error"])
        else:
            print(f"::error::X post for {r['show']} failed for good ({r['error']})")
    # Oct 17 2026: full episodes, as replies under posts that are up. The
    # x_post_replies table may not exist yet; that is a warning, never red.
    try:
        replies = x_queue.post_due_replies()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Full-episode replies skipped: %s", exc)
        replies = []
    for r in replies:
        if r["status"] == "posted":
            logger.info("Posted the full episode under %s: %s", r["show"], r["url"])
        elif r["status"] in ("retry", "cancelled"):
            logger.warning("Full-episode reply %s: %s (%s)", r["show"], r["status"], r["error"])
        else:
            print(f"::warning::Full-episode reply for {r['show']} failed ({r['error']})")
    return 1 if any(r["status"] == "failed" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
