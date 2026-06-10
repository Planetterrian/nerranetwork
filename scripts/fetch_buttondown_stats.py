#!/usr/bin/env python3
"""Fetch the Buttondown newsletter subscriber count.

Writes ``api/buttondown_stats.json`` for the operator dashboard and the
homepage "Join N readers" social proof. Clean no-op when
``BUTTONDOWN_API_KEY`` is unset (logs one line, exits 0, leaves any
previously committed output untouched) — same convention as every other
optional integration in this repo.

Buttondown API: ``GET /v1/subscribers?page_size=1`` returns a paginated
envelope whose ``count`` field is the total number of subscribers. If the
field is ever missing we skip rather than guess (no page-walking — a
wrong number shown publicly is worse than none).

Usage::

    python scripts/fetch_buttondown_stats.py                 # write api/buttondown_stats.json
    python scripts/fetch_buttondown_stats.py --dry-run       # print, write nothing
    python scripts/fetch_buttondown_stats.py --out /tmp/b.json
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

_SCRIPT_DIR = Path(__file__).resolve().parent
_ROOT = _SCRIPT_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import requests  # noqa: E402  (after sys.path fix)

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
log = logging.getLogger("buttondown_stats")

BUTTONDOWN_API_BASE = "https://api.buttondown.com/v1"
HTTP_TIMEOUT = 15


def fetch_subscriber_count(api_key: str) -> Optional[int]:
    """Return the total subscriber count, or None on any failure."""
    try:
        resp = requests.get(
            f"{BUTTONDOWN_API_BASE}/subscribers",
            headers={"Authorization": f"Token {api_key}"},
            params={"page_size": "1", "type": "regular"},
            timeout=HTTP_TIMEOUT,
        )
        if resp.status_code != 200:
            log.warning("buttondown: HTTP %s from /subscribers", resp.status_code)
            return None
        data = resp.json() or {}
        count = data.get("count")
        if isinstance(count, int) and count >= 0:
            return count
        log.warning("buttondown: no usable 'count' field in response "
                    "(keys: %s)", sorted(data.keys()))
        return None
    except Exception as exc:  # noqa: BLE001 — never break the nightly job
        log.warning("buttondown: fetch failed: %s", exc)
        return None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="api/buttondown_stats.json")
    parser.add_argument("--dry-run", action="store_true",
                        help="print JSON to stdout, write nothing")
    args = parser.parse_args(argv)

    api_key = (os.getenv("BUTTONDOWN_API_KEY") or "").strip()
    if not api_key:
        log.info("buttondown: BUTTONDOWN_API_KEY unset — skipping (clean no-op)")
        return 0

    count = fetch_subscriber_count(api_key)
    if count is None:
        log.warning("buttondown: leaving existing stats untouched")
        return 0

    stats = {
        "fetched_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "subscriber_count": count,
    }

    if args.dry_run:
        print(json.dumps(stats, indent=2))
        return 0

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    log.info("buttondown: wrote %s (%d subscribers)", out_path, count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
