#!/usr/bin/env python3
"""Run one shadow-executor pass over today's MIT trade signal (Phase 2).

Scheduled at ~9:50 ET (13:50 UTC) — after the opening auction, on the
signal the 08:16 UTC episode wrote. Fail-closed by design:

- no signal file → clean no-op (exit 0, logged);
- stale / no-trade / unvalidated signal → 'skipped' ledger entry with
  explicit reasons;
- duplicate client_order_id → nothing logged twice.

The shadow ledger (``digests/modern_investing/shadow_ledger.json``) is
committed by the workflow — it contains only hypothetical orders on
public symbols. Compare against the sim with scripts/mit_shadow_report.py.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from execution import shadow  # noqa: E402
from execution.risk import RiskConfig  # noqa: E402

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
logger = logging.getLogger("mit_shadow_executor")

SIGNAL_PATH = ROOT / "digests" / "modern_investing" / "trade_signal_latest.json"
LEDGER_PATH = ROOT / "digests" / "modern_investing" / "shadow_ledger.json"


def main() -> int:
    if not SIGNAL_PATH.exists():
        logger.info("No trade signal at %s — nothing to do (fail-closed).",
                    SIGNAL_PATH)
        return 0
    try:
        signal = json.loads(SIGNAL_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Unreadable trade signal: %s", exc)
        return 1

    ledger = shadow.load_ledger(LEDGER_PATH)
    config = RiskConfig.from_env()
    entry = shadow.run_shadow(signal, ledger, config)
    shadow.save_ledger(ledger, LEDGER_PATH)

    logger.info("Shadow decision: %s%s", entry.get("decision"),
                f" — {'; '.join(entry.get('skip_reasons', []))}"
                if entry.get("skip_reasons") else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
