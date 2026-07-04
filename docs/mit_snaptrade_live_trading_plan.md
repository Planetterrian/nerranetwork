# MIT → SnapTrade live-trading plan (Wealthsimple + Webull)

**Date:** 2026-07-03 · **Status:** design + Phase-1 bridge shipped (trade
signal artifact). Follows the July 3 benchmark-integrity pass
([`docs/reviews/modern_investing_review_2026_07_03.md`](reviews/modern_investing_review_2026_07_03.md))
whose verdict — accumulate 2–3 months of clean simulated record first —
still gates real-dollar orders. This plan builds the execution layer *in
parallel* with that clock so nothing blocks when the record earns it.

---

## 1. SnapTrade review — what it is and what matters for us

SnapTrade (docs.snaptrade.com) is a brokerage-connectivity API: one
interface for account data + order placement across ~35 institutions. It
is the **only sanctioned API route into Wealthsimple** (Wealthsimple has
no developer API; SnapTrade is its integration partner) and it added
**Webull (US and Canada as separate integrations) with real-time trading
in December 2025**. That makes it exactly the right choice for the
operator's two accounts.

### Auth model (three tiers)
1. **Partner keys** — `clientId` + `consumerKey` from the SnapTrade
   dashboard. Every server-side call signs with these.
2. **User registration** — register one SnapTrade user (the operator) →
   `userId` + `userSecret`. The secret is shown once; store alongside the
   other pipeline secrets.
3. **Connection Portal** — generate a redirect URI; the operator logs in
   to Wealthsimple and Webull once through SnapTrade's hosted portal
   (credentials + MFA go to SnapTrade, never to us; we hold scoped
   tokens). Each brokerage = one "connection" containing its accounts.

### Trading API surface (what the executor will call)
- `POST /trade/place` (**place equity order**): `account_id`, `action`
  (BUY/SELL), `symbol` **or** `universal_symbol_id`, `order_type`
  (`Market` | `Limit` | `Stop` | `StopLimit`), `time_in_force` (`Day` |
  `GTC` | `FOK` | `IOC` | `GTD`), `units` (fractional supported) or
  `notional_value` (Market+Day only, select brokerages), `price` /
  `stop` as required, and — critically for a cron-driven system —
  **`client_order_id` for idempotent placement** (a retried job cannot
  double-buy).
- **Checked-order flow**: `check order impact` → returns buying-power /
  commission impact + a `tradeId` → `place checked order`. SnapTrade
  recommends the direct flow, but the impact check is a free extra
  guardrail; we'll use it when available and fall through with a log.
- **Cancel order** (all asset types) + **get order detail** for status
  (`PENDING/ACCEPTED/EXECUTED/PARTIAL/REJECTED/EXPIRED…`).
- Post-order: trigger a **manual account refresh** (docs recommend it;
  default sync is only guaranteed once/day).
- Rate guidance: **≤1 trade/sec/account** (we do ~1 trade/day — a
  non-issue).

### Symbology — a happy accident
SnapTrade's canonical symbols follow the **Yahoo Finance ticker format**
(`SHOP.TO` for TSX, bare for US listings), with distinct
universal-symbol IDs per venue. The July 3 pass already made the MIT
tracker resolve picks to exactly this format (`resolved_symbol`), so the
sim and the executor speak the same language with zero mapping code. For
belt-and-braces, the executor should cache each account's
`listAllBrokerageInstruments` (tradeable flags, fractionability,
exchange MIC) and refuse any symbol not present.

### Webhooks (wire to the existing `NOTIFICATION_WEBHOOK_URL` plumbing)
HMAC-SHA256-signed (consumer key), 3 retries w/ backoff. The ones we
want: `CONNECTION_BROKEN` / `CONNECTION_FIXED` (Wealthsimple
credential-based connections can and do break — **trading must
fail-closed on a broken connection**), `TRADE_UPDATE` (status changes
for SnapTrade-placed orders), `TRADE_DETECTION` (executions detected —
catches manual trades too), `ACCOUNT_HOLDINGS_UPDATED`.

### Environments, SDK, pricing
- **The sandbox is READ-ONLY** — simulated connections/holdings/orders
  but **no order placement, no simulated fills**. Consequence: *paper
  trading cannot be delegated to SnapTrade*; our own shadow mode (§3
  Phase 2) is the paper-trading layer, and first live orders must be
  real-but-tiny.
- Python SDK: `snaptrade-python-sdk` (PyPI); TypeScript etc. also exist.
- Pricing: free tier ≈ 5 connections; pay-as-you-go ~$1.50/connected
  user/month. We are 1 user + 2 connections → **effectively free**.

### Open items to verify in the SnapTrade dashboard (operator, ~30 min)
The per-broker capability matrix is a Notion page that couldn't be read
programmatically, and some brokers gate *trading* (vs read) behind
partner enablement. Before writing executor code against assumptions:
1. Confirm **trade access is enabled** for Wealthsimple and Webull on
   your key (message SnapTrade support if the connection portal shows
   read-only).
2. Confirm per-broker support for: `Limit` orders (must-have), `Day`
   TIF (must-have), fractional units, `notional_value`, `Stop`/
   `StopLimit` (nice-to-have — see §4 stops), extended hours.
3. Confirm which **Webull entity** your account is (Webull US vs Webull
   Canada — separate integrations) and which Wealthsimple account types
   surface (TFSA/RRSP/non-registered; business accounts have limited
   support).
4. Ask about order limits/velocity checks on the Wealthsimple side.

## 2. Target architecture

```
run_show.py (08:16 UTC, unchanged)
  └─ shows/hooks/modern_investing.py post_generate
       ├─ investment_tracker.json          (sim record — unchanged)
       └─ trade_signal_ep{N}.json + trade_signal_latest.json   ← SHIPPED
                                                (schema v1, see §5)
execution/ (NEW — isolated package, never imported by the podcast path)
  ├─ snaptrade_client.py    thin wrapper over snaptrade-python-sdk
  ├─ risk.py                hard caps + kill switch (deterministic)
  ├─ executor.py            signal → validated order → ledger
  ├─ reconcile.py           order status / holdings / sim-vs-live report
  └─ live_ledger.json       every order ever sent, with full audit trail
.github/workflows/execute-trade.yml (NEW — 13:50 UTC ≈ 9:50 ET)
```

Design rules (non-negotiable):
- **The LLM never touches the order path.** It produces the pick; the
  signal artifact is deterministic parsed data; `execution/` is plain
  code with hard caps. No prompt output is ever interpolated into an
  order.
- **Fail closed.** No signal file → no trade. Stale signal (>1 day) →
  no trade. Broken connection → no trade. Any validation failure → no
  trade + loud notification. There is no retry-until-it-works.
- **Separate schedule.** MIT generates at 08:16 UTC = 4:16 a.m. ET,
  pre-market. Orders placed then would sit in a queue or be rejected.
  The executor runs in its own workflow at ~9:50 ET (after the opening
  auction volatility), consuming the morning's signal. This also means a
  podcast failure and a trading failure can never entangle.
- **Idempotent.** `client_order_id` = uuid5(episode, symbol, date) —
  already in the signal. A re-run workflow re-sends the same id;
  SnapTrade dedupes.

### Account routing
| Pick market | Currency | Account | Why |
|---|---|---|---|
| TSX / TSX-V | CAD | Wealthsimple (non-registered or TFSA) | native CAD; avoids Wealthsimple's ~1.5% FX on USD trades |
| NYSE / NASDAQ | USD | Webull US | $0 commission USD-native; better order-type coverage |

### Order policy (v1)
- **Marketable limit, never market**: buy limit = min(quote ask,
  reference × (1 + `max_slippage_pct` 0.5%)), TIF `Day`. Unfilled after
  30 min → cancel; one requote attempt; then give up and record
  `unfilled` (the sim's "you always fill at the open" optimism is
  measured, not replicated).
- **Exits on the sim's calendar**: flash → sell next trading day;
  weekly → sell Friday ~15:45 ET (a second executor slot), so live
  windows track the (fixed) sim windows as closely as reality allows.
- **Position size**: start at $150–250/trade (Phase 3), not the sim's
  $1,000, until slippage data exists.

## 3. Rollout phases

**Phase 0 — account facts (operator, this week).** Dashboard signup,
verify §1 open items, create sandbox + production keys, connect both
brokerages via the portal, set `SNAPTRADE_CLIENT_ID` /
`SNAPTRADE_CONSUMER_KEY` / `SNAPTRADE_USER_ID` / `SNAPTRADE_USER_SECRET`
secrets.

**Phase 1 — read-only mirror (SHIPPED, same PR).** `execution/` package
(`snaptrade_client.py` lazy-SDK wrapper + `mirror.py`),
`scripts/snaptrade_setup.py` (one-time local: `--register` mints the
user secret, `--connect` prints the Connection Portal URL per broker,
`--status` verifies), `scripts/snaptrade_mirror.py` +
`.github/workflows/snaptrade-mirror.yml` (weekdays 13:40 UTC): pulls
accounts/balances/positions daily, one-line summary to
`NOTIFICATION_WEBHOOK_URL`, **mirror JSON gitignored + uploaded as a
14-day CI artifact — never committed (public repo)**. Zero orders
possible (no `place` call in the package; pinned by
`tests/test_snaptrade_execution.py`, along with the
podcast-never-imports-execution isolation contract). Proves connection
stability with Wealthsimple/Webull for a few weeks — the thing we
genuinely don't know. Webhook registration (CONNECTION_BROKEN → push)
is a dashboard setting (Webhooks tab → point at the existing
notification endpoint); a dedicated receiver Worker is Phase-2 scope if
signature verification is wanted.

**Phase 2 — shadow mode (SHIPPED July 4; run ≥4 weeks).**
`execution/risk.py` (env-tunable hard gates: kill switch off by default,
$250 cap, 0.5% slippage collar, $2 price floor, 1-day signal freshness,
duplicate-order rejection — all pure/unit-tested) +
`execution/shadow.py` (full pipeline: signal → gates → decision-time
yfinance quote → marketable-limit price + sizing → committed
`digests/modern_investing/shadow_ledger.json`; idempotent by
`client_order_id`; hypothetical orders only, safe to commit) +
`.github/workflows/mit-shadow-executor.yml` (weekdays 13:50 UTC ≈ 9:50
ET — **live now, needs no secrets**). `scripts/mit_shadow_report.py`
compares shadow decision-time quotes against the sim's entry-bar opens —
the first real **slippage model**, feeding the sim's cost assumptions
once ~20 trades accumulate. This IS the paper-trading layer, since
SnapTrade's sandbox can't fill orders. **Phase 2.5 (shadow exits) also
shipped**: each open shadow position gets a paired, idempotent
`would_sell` on the sim's exit calendar (flash → next weekday, weekly →
Friday; no-quote days retry), carrying the round-trip
`shadow_return_pct`, and the report now shows the per-trade
shadow-vs-sim P&L gap. Entry timing note: the sim enters at the
pick-date OPEN; shadow quotes at ~9:50 ET — the measured gap between
them is exactly the execution cost the sim currently ignores.

**Phase 3 — micro-live (operator flips `LIVE_TRADING_ENABLED=1`).**
Real orders at $150–250, Webull US only at first (single account, USD,
simplest), 20–30 trades. Every order → notification with fill vs sim
delta. Halt automatically on: 2 consecutive rejected orders, daily loss
> cap, connection broken, or sim-vs-live divergence > threshold.

**Phase 4 — scale decision (operator).** Add Wealthsimple/TSX routing,
raise size toward $1,000 — only if Phase 3's matched-window alpha net of
measured costs is still positive AND the sim's clean 2–3-month record
holds. Then, optionally: enforceable stops (see §4), TFSA
considerations (frequent trading inside a TFSA can be deemed business
income by the CRA — talk to an accountant before running this strategy
in a registered account).

## 4. Risk controls (`execution/risk.py`, all hard-coded, env-tunable)

| Control | Default | Note |
|---|---|---|
| `LIVE_TRADING_ENABLED` | unset (off) | global kill switch; shadow mode ignores it |
| `MAX_POSITION_USD` | 250 | Phase-3 cap |
| `MAX_OPEN_POSITIONS` | 1 | matches the sim's model |
| `MAX_DAILY_ORDERS` | 2 | 1 entry + 1 exit |
| `MAX_DAILY_LOSS_USD` | 100 | realized, from ledger; halts entries |
| `MAX_SLIPPAGE_PCT` | 0.5 | limit-price collar vs reference |
| Symbol gates | — | must be in brokerage instrument cache; price ≥ $2; no OTC (blocks the SSNLF/BTC/ION pick classes); reject if `pick_validated: false` |
| Confidence gate | optional | skip `Low`-confidence picks once calibration data exists |
| PDT guard | — | flash trades buy day-D / sell day-D+1 (not day trades), but track the 5-day window anyway on Webull margin < $25k; prefer a cash account |
| Stops | software | if the broker matrix confirms native `StopLimit`, attach one at Phase 4; until then a 15-min position monitor sells on breach (gaps are NOT protected — stated honestly in the ledger) |

## 5. Trade-signal schema v1 (shipped this PR)

Written by `post_generate` to `digests/modern_investing/`
(`trade_signal_latest.json` + `trade_signal_ep{N}.json`); read-only runs
write nothing. `action: "new_trade" | "no_trade"` with an explicit
`reason` (`explicit_no_trade` vs `no_pick_extracted`) so the executor
can fail closed on drift. Trade block carries `snaptrade_symbol`
(Yahoo/SnapTrade format), `currency` + `suggested_account` routing,
`pick_reference_price` + `pick_validated` (from the July-3 probe), and
the deterministic `client_order_id`. Drift guards:
`tests/test_mit_benchmark_integrity.py::TestTradeSignal`.

## 6. What this does NOT change

The podcast remains a simulation on air — the $1,000 sim tracker stays
the show's record and the disclaimers stay exactly as they are. Live
execution is the operator's private layer; if it ever becomes content
("we put real money on the line"), that's an editorial decision with
its own compliance review, out of scope here.

## Sources
- https://docs.snaptrade.com/docs/getting-started
- https://docs.snaptrade.com/docs/trading-with-snaptrade
- https://docs.snaptrade.com/reference/Trading/Trading_placeForceOrder
- https://docs.snaptrade.com/docs/symbology.md
- https://docs.snaptrade.com/docs/webhooks
- https://docs.snaptrade.com/docs/sandbox.md (read-only sandbox)
- https://docs.snaptrade.com/docs/faq
- https://snaptrade.com/brokerage-integrations/wealthsimple-api
- https://snaptrade.com/brokerage-integrations/webull-api ·
  https://snaptrade.com/brokerage-integrations/webull-ca-api
- https://snaptrade.com/pricing
- Webull partnership (Dec 2025): https://finance.yahoo.com/news/snaptrade-partners-webull-140000135.html
