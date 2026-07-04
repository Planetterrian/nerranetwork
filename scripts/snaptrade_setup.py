#!/usr/bin/env python3
"""One-time SnapTrade setup for the MIT execution layer (Phase 1).

Run this LOCALLY (it prints a secret once and opens browser URLs — never
run it in CI). Prerequisites: ``pip install snaptrade-python-sdk`` and
the two API-key env vars from the dashboard (API Keys tab):

    export SNAPTRADE_CLIENT_ID=...
    export SNAPTRADE_CONSUMER_KEY=...

Steps it performs:

1. ``--register`` — registers the SnapTrade user (default userId
   ``nerra-mit-operator``) and prints the ``userSecret``. SnapTrade
   returns the secret ONCE; copy both values into your local ``.env``
   AND the GitHub Actions secrets:
       SNAPTRADE_USER_ID / SNAPTRADE_USER_SECRET
2. ``--connect`` — prints a Connection Portal URL (optionally
   ``--broker WEALTHSIMPLETRADE`` / ``--broker WEBULL``). Open it in a
   browser and log in to the brokerage; repeat per brokerage.
3. ``--status`` — lists connections + accounts so you can confirm both
   brokerages are linked and whether the connection is read-only or
   trade-enabled.

Usage:
    python scripts/snaptrade_setup.py --register
    python scripts/snaptrade_setup.py --connect --broker WEALTHSIMPLETRADE
    python scripts/snaptrade_setup.py --connect --broker WEBULL
    python scripts/snaptrade_setup.py --status
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from execution import snaptrade_client as st  # noqa: E402

DEFAULT_USER_ID = "nerra-mit-operator"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register", action="store_true",
                        help="register the SnapTrade user (one-time)")
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    parser.add_argument("--connect", action="store_true",
                        help="print a Connection Portal URL")
    parser.add_argument("--broker", default=None,
                        help="preselect an institution (e.g. "
                             "WEALTHSIMPLETRADE, WEBULL)")
    parser.add_argument("--connection-type", default="trade",
                        choices=("read", "trade"),
                        help="scope to request in the portal (default: trade)")
    parser.add_argument("--status", action="store_true",
                        help="list connections and accounts")
    args = parser.parse_args()

    if not (os.environ.get("SNAPTRADE_CLIENT_ID")
            and os.environ.get("SNAPTRADE_CONSUMER_KEY")):
        print("Set SNAPTRADE_CLIENT_ID and SNAPTRADE_CONSUMER_KEY first "
              "(dashboard → API Keys).")
        return 1

    if args.register:
        result = st.register_user(args.user_id)
        secret = result.get("userSecret")
        print("Registered SnapTrade user.")
        print(f"  SNAPTRADE_USER_ID={result.get('userId', args.user_id)}")
        print(f"  SNAPTRADE_USER_SECRET={secret}")
        print("\nStore BOTH in your local .env and in GitHub Actions "
              "secrets NOW — the secret is not shown again.")
        return 0

    if args.connect:
        if st.missing_config():
            print(f"Missing env vars: {', '.join(st.missing_config())} "
                  "(run --register first).")
            return 1
        url = st.connection_portal_url(
            broker=args.broker, connection_type=args.connection_type)
        print("Open this URL in a browser and log in to the brokerage:\n")
        print(f"  {url}\n")
        print("Then re-run with --status to confirm the connection.")
        return 0

    if args.status:
        if st.missing_config():
            print(f"Missing env vars: {', '.join(st.missing_config())}.")
            return 1
        connections = st.list_connections()
        print(f"{len(connections)} connection(s):")
        for c in connections:
            broker = (c.get("brokerage") or {}).get("name") or c.get("name")
            print(f"  - {broker}: disabled={c.get('disabled')} "
                  f"type={c.get('type')} id={c.get('id')}")
        accounts = st.list_accounts()
        print(f"{len(accounts)} account(s):")
        for a in accounts:
            print(f"  - {a.get('institution_name')} {a.get('name')} "
                  f"(id={a.get('id')})")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
