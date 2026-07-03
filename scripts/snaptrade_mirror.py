#!/usr/bin/env python3
"""Daily read-only SnapTrade account mirror (Phase 1).

Fetches connected accounts/balances/positions and writes
``digests/modern_investing/live_account_mirror.json`` (GITIGNORED — the
repo is public and balances must never be committed; in CI the file is
uploaded as a workflow artifact instead). Prints a one-line summary and
POSTs it to ``NOTIFICATION_WEBHOOK_URL`` when set.

Exit codes: 0 on success OR when SnapTrade env vars are unset (clean
no-op, so the workflow can run before setup is done); 1 on a real
fetch/serialization failure.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from execution import mirror as mirror_mod  # noqa: E402
from execution import snaptrade_client as st  # noqa: E402

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
logger = logging.getLogger("snaptrade_mirror")

DEFAULT_OUT = ROOT / "digests" / "modern_investing" / "live_account_mirror.json"


def _notify(line: str) -> None:
    url = os.environ.get("NOTIFICATION_WEBHOOK_URL", "").strip()
    if not url:
        return
    try:
        import requests
        requests.post(url, json={"text": line}, timeout=10)
    except Exception as exc:  # noqa: BLE001
        logger.warning("notification failed (non-fatal): %s", exc)


def main() -> int:
    out_path = Path(sys.argv[sys.argv.index("--out") + 1]) \
        if "--out" in sys.argv else DEFAULT_OUT

    if not st.is_configured():
        logger.info(
            "SnapTrade env vars not set (%s) — mirror is a clean no-op. "
            "Run scripts/snaptrade_setup.py first.",
            ", ".join(st.missing_config()),
        )
        return 0

    try:
        mirror = mirror_mod.fetch_mirror()
    except Exception as exc:  # noqa: BLE001
        logger.error("Mirror fetch FAILED: %s", exc)
        _notify(f"SnapTrade mirror FAILED: {exc}")
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(mirror, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    line = mirror_mod.mirror_summary_line(mirror)
    logger.info("%s → %s", line, out_path)
    if mirror["account_count"] == 0:
        logger.warning(
            "No accounts returned — connections may be broken or not yet "
            "created (scripts/snaptrade_setup.py --status).")
        _notify("SnapTrade mirror: 0 accounts returned — check connections.")
    else:
        _notify(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
