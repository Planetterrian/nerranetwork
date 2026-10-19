#!/usr/bin/env python3
"""Start a show's follow-up workflows only when there is work (Oct 19 2026).

Until today the multilingual sweep and the Nerra Daily ready gate were
``workflow_run`` triggers on every "Run Podcast Show" completion: ~46 runs
a day each, every one checking out the repo and installing Python to decide
that there was nothing to do (the show was not multilingual, the edition
was not due yet, the video was still rendering). Measured Oct 16-18: about
110 runner-minutes a day of deciding. The show run already knows the
answer, so it decides here and dispatches only the workflow that has work:

  multilingual --show X [--after-video]
      dispatch multilingual.yml for X when X published today, is public
      today, opts into automatic translation, and its video is not still
      rendering in its own job (render-video.yml dispatches with
      --after-video once the scenes are on main). The two cron passes of
      multilingual.yml remain the catch-all.

  nerra-daily --show X
      dispatch nerra-daily.yml when X is on today's edition roster, the
      edition has not been built, and the clock is past the release
      (engine.daily_edition.RELEASE_EASTERN). Before the release nothing
      wakes the gate: the scheduler Worker dispatches it at the release
      and at the end of the hold, so only a straggler landing inside the
      hold (or a late re-run after a failed morning) has to wake it.

Both need GH_TOKEN (actions: write) and GITHUB_REPOSITORY; without them the
decision is printed and nothing is dispatched (a local run).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

API = "https://api.github.com"
MULTILINGUAL_WORKFLOW = "multilingual.yml"
EDITION_WORKFLOW = "nerra-daily.yml"
VIDEO_PENDING_PREFIX = ".video_pending_"
VIDEO_DONE_PREFIX = ".video_done_"


# ---------------------------------------------------------------------------
# Decisions (pure — tested without a network)
# ---------------------------------------------------------------------------

def multilingual_decision(config, out_dir: Path, today: dt.date, *,
                          after_video: bool = False) -> Tuple[bool, str]:
    """``(dispatch, why)`` for one show's multilingual sweep."""
    ml = getattr(config, "multilingual", None)
    if not (ml and getattr(ml, "enabled", False) and getattr(ml, "auto", False)):
        return False, "multilingual is not automatic on this show"
    try:
        from engine.access import is_public_on
        if not is_public_on(config, today):
            return False, "no public episode today (members-only)"
    except Exception:  # noqa: BLE001 — an unreadable access block is public
        pass
    stamp = today.strftime("%Y%m%d")
    if not any(out_dir.glob(f"*_{stamp}.md")):
        return False, "no episode dated today (skipped or not yet written)"
    pending = out_dir / f"{VIDEO_PENDING_PREFIX}{stamp}.json"
    done = out_dir / f"{VIDEO_DONE_PREFIX}{stamp}.json"
    if not after_video and pending.exists() and not done.exists():
        return False, "the video job is still rendering; it dispatches the sweep when done"
    return True, "published today with automatic translation"


def edition_decision(spec, root: Path, show: str, now_utc: dt.datetime,
                     target_date: Optional[dt.date] = None) -> Tuple[bool, str]:
    """``(dispatch, why)`` for waking the Nerra Daily ready gate."""
    from engine.daily_edition import expected_slugs, release_window

    target_date = target_date or now_utc.date()
    if show not in expected_slugs(spec, target_date):
        return False, f"{show} is not on the {target_date} edition roster"
    if edition_published(spec, root, target_date):
        return False, f"the {target_date} edition is already published"
    release, _hold = release_window(target_date)
    if now_utc < release:
        return False, ("before the release — the scheduler Worker dispatches the "
                       "gate at the release and at the end of the hold")
    return True, "a roster show landed after the release with no edition built"


def edition_published(spec, root: Path, target_date: dt.date) -> bool:
    path = root / spec.digest_dir / f"summaries_{spec.slug}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return False
    return any(e.get("date") == target_date.isoformat()
               for e in data.get("summaries", []) if isinstance(e, dict))


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def _session():
    import requests

    token = (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
    s = requests.Session()
    s.headers.update({"Accept": "application/vnd.github+json",
                      "X-GitHub-Api-Version": "2022-11-28"})
    if token:
        s.headers["Authorization"] = f"Bearer {token}"
    return s, bool(token)


def dispatch_workflow(workflow: str, inputs: dict, *, attempts: int = 3) -> bool:
    """POST a workflow_dispatch; False when it never got a 2xx."""
    import requests

    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    session, has_token = _session()
    if not repo or not has_token:
        print(f"(no GITHUB_REPOSITORY/GH_TOKEN — would dispatch {workflow} {inputs})")
        return True
    url = f"{API}/repos/{repo}/actions/workflows/{workflow}/dispatches"
    body = {"ref": "main", "inputs": {k: str(v) for k, v in inputs.items()}}
    for attempt in range(1, attempts + 1):
        try:
            r = session.post(url, json=body, timeout=30)
            if r.status_code in (201, 204):
                print(f"Dispatched {workflow} {inputs}")
                return True
            print(f"::warning::{workflow} dispatch answered {r.status_code}: {r.text[:200]}")
        except requests.RequestException as exc:
            print(f"::warning::{workflow} dispatch failed: {exc}")
        time.sleep(5 * attempt)
    return False


def _show_config(show: str):
    from engine.config import load_config

    return load_config(ROOT / "shows" / f"{show}.yaml")


def cmd_multilingual(args) -> int:
    today = dt.datetime.now(dt.timezone.utc).date()
    config = _show_config(args.show)
    out_dir = ROOT / config.episode.output_dir
    go, why = multilingual_decision(config, out_dir, today, after_video=args.after_video)
    print(f"multilingual {args.show}: {'dispatch' if go else 'skip'} — {why}")
    if not go:
        return 0
    return 0 if dispatch_workflow(MULTILINGUAL_WORKFLOW, {"show": args.show}) else 1


def cmd_nerra_daily(args) -> int:
    from engine.daily_edition import EDITIONS

    now = dt.datetime.now(dt.timezone.utc)
    go, why = edition_decision(EDITIONS["en"], ROOT, args.show, now)
    print(f"nerra-daily after {args.show}: {'dispatch' if go else 'skip'} — {why}")
    if not go:
        return 0
    # A failed dispatch is not the show's failure: the Worker's hold-end
    # dispatch and the GitHub fallback crons still build the edition.
    dispatch_workflow(EDITION_WORKFLOW, {})
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("multilingual", help="start the multilingual sweep for one show")
    m.add_argument("--show", required=True)
    m.add_argument("--after-video", action="store_true",
                   help="called by the video job: the scenes are on main")
    n = sub.add_parser("nerra-daily", help="wake the Nerra Daily ready gate")
    n.add_argument("--show", required=True)
    args = parser.parse_args(argv)
    return cmd_multilingual(args) if args.cmd == "multilingual" else cmd_nerra_daily(args)


if __name__ == "__main__":
    sys.exit(main())
