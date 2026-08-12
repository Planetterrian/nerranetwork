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
    import argparse

    from engine.shorts_stagger import post_due_comments

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--show", default="",
        help="Sweep only this show's digests/<dir> sidecar. REQUIRED when "
             "run inside a parallel per-show matrix (multilingual.yml) — "
             "concurrent global sweeps each posted the same pending "
             "comments, shipping 2-3 identical bot comments per Short.")
    args = ap.parse_args()

    show_dir = None
    slug = args.show.strip()
    if slug:
        # The sidecar lives under the show's OUTPUT dir, which is not
        # always the slug (tesla -> digests/tesla_shorts_time). Resolve
        # via the show config; fall back to the literal value.
        show_dir = slug
        try:
            from engine.config import load_config

            cfg = load_config(f"shows/{slug}.yaml")
            out_dir = Path(getattr(cfg.episode, "output_dir", "") or "")
            if out_dir.name and out_dir.name != "digests":
                show_dir = out_dir.name
        except Exception as exc:  # noqa: BLE001 — literal fallback is fine
            logger.info("--show %s: config resolve failed (%s) — using the "
                        "value as a directory name", slug, exc)

    stats = post_due_comments(PROJECT_ROOT, show_dir=show_dir)
    logger.info(
        "Scheduled-Short comments: %d posted, %d kept for a later sweep, "
        "%d dropped.", stats["posted"], stats["kept"], stats["dropped"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
