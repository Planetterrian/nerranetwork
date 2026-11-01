#!/usr/bin/env python3
"""Ask the account Worker to reconcile the Nerra Daily email's tags (Nov 2026).

``POST /api/admin/sync-email-tags`` sets ``personal-paid`` on every active
Nerra Personal member's Buttondown record and clears it from everyone else,
so the email's Personal pitch is never shown to someone already paying.
``--lineups`` (once, after the first deploy) also adds each member's lineup
shows to their email. The Worker answers with counts only.

Clean no-op without ``PERSONAL_ADMIN_TOKEN``. Never fails the caller: a
Worker that predates the endpoint answers 404, which is reported.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import requests

DEFAULT_BASE = "https://api.nerranetwork.com"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--lineups", action="store_true",
                    help="also add each member's lineup shows to their email (one-time backfill)")
    ap.add_argument("--base", default=os.environ.get("PERSONAL_API_BASE", DEFAULT_BASE))
    args = ap.parse_args(argv)
    token = (os.environ.get("PERSONAL_ADMIN_TOKEN") or "").strip()
    if not token:
        print("PERSONAL_ADMIN_TOKEN not set; email tags not reconciled (clean no-op).")
        return 0
    url = f"{args.base.rstrip('/')}/api/admin/sync-email-tags" + ("?lineups=1" if args.lineups else "")
    try:
        resp = requests.post(url, headers={"Authorization": f"Bearer {token}"}, timeout=120)
    except requests.RequestException as exc:
        print(f"::warning::email tag sync could not reach the Worker: {type(exc).__name__}")
        return 0
    if resp.status_code == 404:
        print("::warning::the account Worker has no /api/admin/sync-email-tags yet "
              "(run `wrangler deploy` in workers/gallery)")
        return 0
    if resp.status_code != 200:
        print(f"::warning::email tag sync answered HTTP {resp.status_code}")
        return 0
    try:
        body = resp.json()
    except ValueError:
        body = {}
    print("email tag sync:", json.dumps({k: body.get(k) for k in
                                          ("members", "paid", "updated", "not_on_list")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
