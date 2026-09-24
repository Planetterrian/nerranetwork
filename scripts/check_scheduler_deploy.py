#!/usr/bin/env python3
"""Compare the deployed scheduler Worker's slot table with the committed one.

The Worker fires whatever was last deployed. On 2026-09-24 a redeploy from a
stale checkout left nine newly scheduled shows off the live table; the deploy
output looked healthy, the old slots fired on the minute, and the new shows
simply never ran until GitHub's hours-late cron fallback picked them up. Nothing
watched for it, because every guard compared two files in the repo.

This reads the Worker's ``GET /`` (set the repo variable ``SCHEDULER_STATUS_URL``
to its ``*.workers.dev`` URL; see ``workers/scheduler/README.md``) and diffs its
``slots`` against ``workers/scheduler/src/index.ts``. Loud but non-blocking:
a drift prints a ``::warning::`` annotation naming each missing / extra /
changed slot and says how to fix it (``git pull && npx wrangler deploy`` in
``workers/scheduler``). ``--strict`` exits non-zero instead. An unset variable
is a one-line no-op, never a failure.

    python scripts/check_scheduler_deploy.py
    SCHEDULER_STATUS_URL=https://nerra-scheduler.<acct>.workers.dev python scripts/check_scheduler_deploy.py --strict
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.scheduler_slots import (  # noqa: E402
    has_drift, slot_drift, slots_from_status, worker_slots,
)

ENV_VAR = "SCHEDULER_STATUS_URL"
FIX = "cd workers/scheduler && git pull && npx wrangler deploy"


def fetch_status(url: str, timeout: float = 20.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "nerra-deploy-check"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def _fmt(slot) -> str:
    h, m, f = slot
    return f"{h:02d}:{m:02d}Z" + (f" ({f})" if f else "")


def check(payload: dict, committed: Optional[dict] = None) -> tuple[bool, list[str]]:
    """``(ok, lines)`` — pure; the tests drive this with a fake payload."""
    committed = committed if committed is not None else worker_slots()
    live = slots_from_status(payload)
    lines: list[str] = []
    if not live:
        lines.append("deployed Worker returned no slot table (old build, or not the status page)")
        return False, lines
    drift = slot_drift(committed, live)
    for show, slot in sorted(drift["missing_live"].items()):
        lines.append(f"missing on the live Worker: {show} @ {_fmt(slot)}")
    for show, slot in sorted(drift["extra_live"].items()):
        lines.append(f"live but not committed: {show} @ {_fmt(slot)}")
    for show, both in sorted(drift["changed"].items()):
        lines.append(f"changed: {show} committed {_fmt(both['committed'])} live {_fmt(both['live'])}")
    if not has_drift(drift):
        lines.append(f"deployed slot table matches the source ({len(live)} slots)")
        return True, lines
    return False, lines


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strict", action="store_true", help="exit 1 on drift or an unreachable Worker")
    ap.add_argument("--url", default=None, help=f"override ${ENV_VAR}")
    args = ap.parse_args(argv)
    url = (args.url or os.environ.get(ENV_VAR, "")).strip()
    if not url:
        print(f"{ENV_VAR} is not set — scheduler deploy check skipped (set the repo "
              "variable to the Worker's *.workers.dev URL to enable it)")
        return 0
    try:
        payload = fetch_status(url)
    except Exception as exc:  # noqa: BLE001 — network trouble is a warning, not a failure
        msg = f"scheduler Worker status unreachable at {url}: {exc}"
        print(f"::warning::{msg}")
        return 1 if args.strict else 0
    ok, lines = check(payload)
    for line in lines:
        print(line)
    if ok:
        return 0
    print(f"::warning::scheduler Worker deploy drift — the live slot table does not match "
          f"workers/scheduler/src/index.ts ({len(lines)} difference(s)); fix: {FIX}")
    return 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
