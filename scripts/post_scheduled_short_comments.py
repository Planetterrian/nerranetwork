#!/usr/bin/env python3
"""Post queued funnel comments on Shorts that have gone public.

Staggered Shorts publishing (engine/shorts_stagger.py) uploads an
episode's 2nd/3rd Shorts private with ``status.publishAt``. A comment
cannot be posted on a private video, so the publish paths queue each
Short's funnel comment ("▶ Full episode: …" — the strongest Shorts→long
placement after the description) to
``digests/<slug>/scheduled_comments.json``. This sweep posts every queued
comment whose publish time has passed, using the channel's own
credentials, and removes it from the sidecar.

Wired into the multilingual sweep (14:07 / 18:07 UTC — right after the EN
17:00 and RU 15:00/18:00 slots... the next run always covers a slot) and
nightly maintenance (catches the late-evening slots). Safe to run any
time: not-yet-due entries are kept, entries whose channel has no token in
this environment are kept for the next sweep, and entries > 7 days
overdue are dropped loudly. Always exits 0 — a comment is never worth
failing a workflow over.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("post_scheduled_short_comments")


def main() -> int:
    from engine.shorts_stagger import post_due_comments

    stats = post_due_comments(PROJECT_ROOT)
    logger.info(
        "Scheduled-Short comments: %d posted, %d kept for a later sweep, "
        "%d dropped.", stats["posted"], stats["kept"], stats["dropped"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
