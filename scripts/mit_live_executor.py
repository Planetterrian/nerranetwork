#!/usr/bin/env python3
"""Run one live-executor pass (Phase 3 — DORMANT until armed).

Modes (schedule slots pass one; dispatch may pass both):
  --entries   morning slot (~9:52 ET): today's signal → at most one BUY
  --exits     afternoon slot (~15:45 ET): due positions → SELLs

Fail-closed everywhere: LIVE_TRADING_ENABLED unset, missing SnapTrade
config, missing/stale signal, halted state, no matching account, or no
quote all mean NO order, with the reason logged (and notified for
anything surprising). Exit code is 0 for every no-op path so the
workflow stays green while dormant.

State files: live_execution_state.json (committed — halt flag + id-only
order index) and live_ledger.json (gitignored full audit; CI artifact).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from execution import live  # noqa: E402
from execution.risk import RiskConfig  # noqa: E402

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
logger = logging.getLogger("mit_live_executor")

MIT_DIR = ROOT / "digests" / "modern_investing"
SIGNAL_PATH = MIT_DIR / "trade_signal_latest.json"
STATE_PATH = MIT_DIR / "live_execution_state.json"
LEDGER_PATH = MIT_DIR / "live_ledger.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entries", action="store_true")
    parser.add_argument("--exits", action="store_true")
    args = parser.parse_args()
    if not (args.entries or args.exits):
        args.entries = args.exits = True

    config = RiskConfig.from_env()
    if not config.live_trading_enabled:
        logger.info("LIVE_TRADING_ENABLED is not 1 — live layer dormant "
                    "(clean no-op).")
        return 0

    state = live.load_state(STATE_PATH)
    ledger = live.load_ledger(LEDGER_PATH)

    if args.entries:
        if SIGNAL_PATH.exists():
            try:
                signal = json.loads(SIGNAL_PATH.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.error("Unreadable trade signal: %s", exc)
                signal = None
            if signal is not None:
                decision = live.run_live_entry(signal, state, ledger, config)
                logger.info("Live entry decision: %s%s",
                            decision.get("decision"),
                            f" — {'; '.join(decision.get('skip_reasons', []))}"
                            if decision.get("skip_reasons") else "")
        else:
            logger.info("No trade signal — no entry (fail-closed).")

    if args.exits:
        exits = live.run_live_exits(state, ledger, config)
        for x in exits:
            logger.info("Live exit: %s %s", x.get("symbol"), x.get("status"))

    live.save_state(state, STATE_PATH)
    live.save_ledger(ledger, LEDGER_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
