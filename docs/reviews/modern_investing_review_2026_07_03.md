# Modern Investing Techniques — benchmark-integrity & live-trading readiness review (2026-07-03)

**Focus (operator request):** the recursive learning loop, trade
extraction/tracking integrity, NASDAQ-alpha measurement, and overall
pipeline robustness — because the operator wants to connect the show's
strategy to a **live brokerage account** and beat the NASDAQ benchmark
regularly. That intent reframes the bar: the simulated track record is no
longer just content, it is the *evidence* a real-money decision would rest
on. This pass audited the measurement layer accordingly.

Method: full read of `shows/hooks/modern_investing.py` (the entire trading
system, 1,916 lines), the committed `investment_tracker.json` (46 trades),
`taught_lessons.json` / `lessons_learned.json`, all 7 prompts, the last 10
episodes' digests + transcripts, `scripts/review_snapshot.py
modern_investing`, and the July 2 network-pass ledger entry.

---

## Scoring the previous review's predictions (ledger, 2026-07-02)

| Prediction | Verdict | Evidence |
|---|---|---|
| Spoken record excludes voided trades; no data-failure close ever narrated as a market outcome | **partial** | The 4 null-price trades (XLF/KO/ROKU/ION) are voided and excluded — but the two **NaN-exit** closes (DELL Ep57, HIMS Ep63) stayed `status: closed` with `pnl_pct: NaN`. `_finite()` coerced them to 0.0 in every aggregate, so **2 of the 3 spoken "breakeven" trades were still data failures**. Fixed this pass (see P0-1). |
| Each closed trade reviewed exactly once | **hit** | Ep94 reviewed the MU flash once (`reviewed_in_episode: 94`), Ep95 reviewed GIS once (`95`); no re-narration in Ep94/95 transcripts. |

---

## P0 — the track record was not measuring what it claims (all fixed)

### P0-1. NaN-closed trades still narrated as breakeven outcomes
DELL (Ep57) and HIMS (Ep63) closed with `exit_price: NaN` before the June
NaN guard landed and were **missed by the July 2 voiding migration** (it
caught null prices, not NaN). They sat in the spoken record as 2 of the 3
"breakeven" trades. Fixed with a **self-healing migration**
(`_void_nonfinite_closed_trades`, run on every tracker load —
`shows/hooks/modern_investing.py`) + one-time application to the committed
tracker: **40 honest closed trades, 6 voided, breakeven 3→1, win rate
54.8%→57.5%**. The brittle drift guard that pinned `total_trades == 37`
(red on main since trades resumed closing) was rewritten as invariants
that hold for any healthy tracker (`tests/test_mit_quality_pass.py::
TestVoidedTradesExcluded::test_committed_tracker_invariants`).

### P0-2. Flash-trade "alpha" was just the raw return — the benchmark was never applied
`_annotate_trade_with_nasdaq` computed the NASDAQ window as
close(trade date) → close(trade date): **the same number twice**. Every
flash trade in the tracker has `nasdaq_return_pct: 0.0` and
`alpha_pct == pnl_pct` (verified: CLDX, EXE, BTC, PYPL, IBM, TSM, SNOW,
MU). Weekly holds had a related corruption: stock entry at Monday's OPEN
was compared to the index's **previous-Friday CLOSE** (weekend gap
contamination), and weekly picks made on Fridays got a zero-length index
window. **The headline "cumulative alpha vs NASDAQ +15.17%" is built on
these windows and is not trustworthy.** Fixed: the benchmark now uses the
index **OPEN on the trade's entry bar → CLOSE on its exit bar** — the
exact window the trade's own P&L measures (`_matched_nasdaq_window`).
Historical realignment ships as `scripts/recompute_mit_benchmarks.py`
(needs market-data access; this environment's proxy blocks Yahoo) — run it
once, review its wrong-instrument report, `--apply`.

### P0-3. Weekly holds picked mid-week were backdated to Monday's open (hindsight gain)
`_fetch_weekly_prices` always took "this week's first trading day" — so a
weekly hold picked on Wednesday was credited from **Monday's open**, two
days of price action the pick was made *knowing about*. Ep35 AMD (picked
Wed 2026-05-06, +13.36% "alpha +13.49%") is the flagship example; 15 of
the 34 weekly trades were picked Tue–Sun. For a record meant to justify
live trading this is look-ahead bias, the classic sim-inflation failure.
Fixed: entry is now the first bar **on/after the pick date**
(`_pick_weekly_bars`); flash trades similarly must price the **pick-date
bar**, never "the most recent day" (`_pick_flash_bar` — this also kills
the wrong-day pricing that a 1–6 h delayed GitHub cron caused, landmine
#24 class). If no bar exists yet the trade stays open (weekend picks
enter Monday); a pick with no trading data for 10+ days voids as
`no_trading_data_after_pick`.

### P0-4. TSX picks were priced as the wrong US company
Ep50's digest picked **"CNR — Canadian National Railway (TSX:CNR)"**; the
bare symbol went to yfinance, which resolves "CNR" to **Core Natural
Resources (NYSE)**. The tracker booked +8.66% (entry $86.46) on a company
the show never picked — CN Rail trades ~C$130+. Every TSX pick had this
exposure (SSRM/TECK/KGEI/MDA were priced via US listings or unknown
matches). Fixed three ways:
- `_yf_symbol_candidates`: `market: TSX` → try `SYM.TO` first, `TSX-V` →
  `SYM.V` (fall back to bare for dual-listed lookups that fail);
- **pick-time validation probe** (`_probe_pick`, run in `post_generate`):
  resolves the symbol on pick day, stamps `resolved_symbol` +
  `pick_reference_price`, and logs `PICK VALIDATION FAILED` loudly for
  bogus tickers (Ep79 "ION" would have been caught the same morning
  instead of voiding four days later);
- **price-discontinuity tripwire** at close: entry >50% away from the
  pick-time reference → `price_discontinuity: true` + loud warning
  (flagged for the operator, never auto-voided — a genuine halving is a
  real, instructive outcome).

### P0-5. `--test` runs mutate the live track record
`post_generate` runs **before** run_show's test-mode early exit, so a
`--test` invocation (the exact command the review playbook tells agents
to run) appended a REAL trade to the tracker, and `pre_fetch` closed and
stamped open trades on any invocation. Fixed: `run_show.py` sets
`NERRA_HOOKS_READONLY=1` for `--test`/`--rehearse`; the MIT hook builds
all its prompt blocks read-only under it and `post_generate` no-ops.
(Other hook-owning shows — Tesla memory etc. — have the same class of
exposure; recommended below.)

## P1 — the "recursive learning loop" was an echo chamber (fixed)

### P1-1. lessons_learned.json: 65 "active" rules, ~47 of them copies of two rules
The loop's mechanics guaranteed convergence-to-noise: the digest prompt
shows the 5 **most recent** active rules → the LLM's `**Lesson Learned:**`
block paraphrases what it was just shown → `_extract_lesson_learned_from_
digest` appends the paraphrase as a **new** entry → tomorrow's window is
yesterday's echo. Result: LL-017…LL-053 are ~35 near-copies of "require
volume confirmation above the 20-day average", LL-054…LL-065 are 12
copies of "require closing-price confirmation" — which is also the
9-of-10-episodes spoken tic in the snapshot, and is the pipeline
narrating **its own former price-fetch bug** as an investing lesson.
Fixed: **dedup-on-append** (`_find_similar_active_lesson` via the shared
`engine.utils.calculate_similarity`; a near-duplicate now *reinforces* the
existing rule — `reinforced_count`/`last_reinforced` — instead of
multiplying it), **diversity selection** in the 5-rule prompt block, and a
one-time collapse of the committed ledger: **65 → 11 distinct active
rules** (duplicates marked `merged_duplicate` with `merged_into`;
reinforcement counts preserved: the volume rule x23, closing-price x12).
The prompt block now shows five *different* rules. Retiring the
closing-price rule outright remains the operator's July-2 A/B call — the
data now makes it a one-line status flip on LL-054/LL-005/LL-013 (all
three describe pipeline data-fetch failures, not market behavior).

### P1-2. Two irreconcilable "alphas", now three honest, labeled ones
Episodes have spoken "+11% alpha" one day and "−13.1%" the Sunday recap
(July 2 finding, deferred as a prompt-label A/B). This pass fixed it at
the **data layer** instead: `_recompute_summary` now computes a
**matched-window compounded score** — Π(1+trade) vs Π(1+NASDAQ) over each
trade's own bar window — which is the honest answer to "do the picks beat
the index?", and `_build_benchmark_block` / `_build_portfolio_summary`
now label every number (`MATCHED-WINDOW SCORE` vs `BUY-AND-HOLD GAP
(NOT capital-matched)`) with an explicit never-mix-in-one-sentence rule.
⚠️ Changes spoken output — A/B-listen (landmine #17).

### P1-3. "Friday close" was Thursday's bar
MIT runs at 08:16 UTC (4:16 a.m. ET, pre-market), so the Friday run
closes weekly holds on **Thursday's** completed bar while the hardcoded
review label said "Friday close" (and Saturday scripts then said
"Friday's close" about a Thursday price — the July-2 labeling item).
Closes now record `entry_bar_date`/`exit_bar_date` and the review block
derives its labels from them ("Monday open → Thursday close"). The
cadence question — close on Saturday's run to capture the true Friday
close — is an operator decision (recommended below).

### P1-4. Confidence calibration never engaged — every pick is "Medium"
All 46 recorded trades declare `confidence: Medium`, so the High-only
calibration report returned "data still limited" forever.
`get_mit_confidence_calibration` now reports **every bucket** and calls
out a >90%-single-bucket distribution as uninformative, instructing the
model to commit to High/Low when the rubric supports it.

### P1-5. Small dead ends
- `_maybe_record_monthly_snapshot` read `alpha["ytd_vs_nasdaq"]` — a key
  that never existed — recording 0.0 in every snapshot; now reads
  `ytd_pct`.
- The committed drift guard pinning `total_trades == 37` was already red
  on main (42 at review time) — a drift guard that drifts; replaced with
  invariants + a summary-equals-recompute check.

## Live-trading readiness assessment (the operator's actual question)

**Verdict: do not connect real money yet.** Three independent reasons:

**1. The evidence doesn't support the claim yet.** The honest record
after this pass's migration: 40 closed trades over ~3.5 months,
cumulative P&L **+$304.47 on sequential $1,000 positions** (+0.76%
avg/trade, 57.5% win rate). Meanwhile the NASDAQ is +15.46% since
inception — capital parked in QQQ would have made ~30× more dollars than
the sim's single rotating $1k position. The pre-realignment
"matched-window alpha +11.17%" and "per-trade alpha sum +15.17%" are both
**inflated by the window bugs fixed above** (flash benchmark = 0,
backdated weekly entries): run `scripts/recompute_mit_benchmarks.py` and
treat ITS output as the first trustworthy baseline, then let the fixed
pipeline accumulate **2–3 months of clean, bias-free record** before any
live decision.

**2. The sim doesn't model execution.** Fills at the exact open/close
with zero spread, slippage, commissions, or FX (TSX picks in CAD vs USD
accounting is currently ignored); stop-losses are *narrated* in the
digest but never enforced in evaluation; a $1k position sidesteps all
sizing/risk questions a real account faces; PDT rules apply to real flash
trades under US$25k equity. Ironically the show *teaches*
bid_ask_spread/order_flow_slippage while its own record assumes both are
zero. Minimum before live: subtract a per-side cost assumption (e.g.
0.1–0.2% + spread by liquidity tier), enforce the stated stop in
evaluation, and model weekend-pick entry realistically (now done).

**3. There is no execution layer, by design — keep it that way for now.**
If/when the record earns it, the safe path is a *paper-trading API first*
(IBKR paper account or Alpaca paper are the practical options; canadian
retail brokers like Wealthsimple have no public trading API), driven by a
new, isolated module that reads the tracker's open pick and places
bracket orders (entry + stop + target) with hard caps: max position size,
max daily loss, a kill-switch env var, and *no LLM in the order path* —
the LLM picks, deterministic code trades. That is a separate project and
should not live inside the podcast hook.

**What "beating the Nasdaq regularly" should mean going forward:** the
matched-window compounded score (now in `summary.matched_window_alpha_pct`)
is the defensible metric — same dollars, same windows, compounded. The
buy-and-hold gap stays on air for honesty (it is the number a listener
holding an index fund cares about), always labeled.

## P2 / deferred (carried forward)

- **Chronic under-length** — 8/10 recent episodes below the 1,800-word
  floor (snapshot). Same digest-ceiling root cause as FF/UC/PT; stays
  deferred behind the operator's four-show length A/B.
- **Retire the closing-price-confirmation "lesson"** (LL-054 + the
  LL-005/LL-013 data-availability family) — operator A/B call from July
  2, now a one-line status flip after the dedup.
- **investing.com promo-headline demotion** (Ep093 "Qualys surged 65%") —
  operator item from July 2, unchanged.
- **Saturday/Sunday-recap trade picks** — recap/weekend episodes create
  real trades from synthesized/stale news (Ep38 HMN on a Sunday, Ep44/89
  Saturdays). With pick-date entry (this pass) the pricing is now fair
  (they enter Monday's open), but consider whether recap episodes should
  pick at all.
- **Close weekly holds on Saturday's run** to capture the true Friday
  close (today: Thursday's bar, honestly labeled now). Cadence/content
  decision.
- **Network-wide: extend `NERRA_HOOKS_READONLY` honoring** to the other
  state-mutating hooks (tesla/spacex/FF/PT memory, PR vocab) — same
  `--test` pollution class, lower stakes.
- **Prompt-vs-code drift:** the digest prompt says weekly holds are
  Monday-only + max 1 flash/week; the LLM declares "Weekly Hold" on any
  day and the code accepts it. Now harmless for integrity (pick-date
  entry), but the hybrid-model prompt language could be simplified to
  match reality.

## ⚠️ A/B-listen required (landmine #17)

No prompt files were edited. These **data/hook-block changes alter
generated (spoken) output** and should be listened to on the next 1–2
episodes:
1. Relabeled scoreboard blocks (`MATCHED-WINDOW SCORE` / `BUY-AND-HOLD
   GAP` phrasing will appear in Market Pulse / Portfolio Performance).
2. Lessons-learned block now shows 5 *distinct* rules (the
   closing-price tic should drop from ~9/10 episodes to ≤1 mention).
3. Trade-review labels now name real bar days ("Thursday close").
4. Migration deltas: win rate 57.5%, breakeven 1, 40 trades.

## Shipped (all code/data, drift-guarded)

`shows/hooks/modern_investing.py` (window alignment, symbol resolution,
probe, readonly guard, dedup, calibration, labels, migrations),
`run_show.py` (readonly env), committed tracker + lessons migrations,
`scripts/recompute_mit_benchmarks.py`, `tests/test_mit_benchmark_integrity.py`
(37 new tests), updates to `tests/test_mit_quality_pass.py` +
`tests/test_modern_investing_hooks.py`. Full suites green (508 tests
across the touched areas).
