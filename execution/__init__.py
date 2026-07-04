"""Live-account execution layer (SnapTrade) — ISOLATED from the podcast path.

Contract (see docs/mit_snaptrade_live_trading_plan.md):

- Nothing in ``engine/``, ``run_show.py``, or ``shows/hooks/`` may import
  this package. The podcast pipeline's only interface to execution is the
  ``trade_signal_*.json`` artifact it writes; this package's only
  interface back is its own ledger/mirror files.
- The LLM never touches the order path: this package consumes the
  deterministic signal artifact, never digest prose.
- Fail closed: unconfigured environment, missing/stale signal, or a
  broken brokerage connection means NO action, loudly.
- Phase 1 (current) is READ-ONLY: there is deliberately no order-placing
  code in this package yet. Phases in the plan doc gate what gets added.
- Privacy: the repo is public. Balances/positions are written only to
  gitignored local files or CI artifacts — never committed.
"""
