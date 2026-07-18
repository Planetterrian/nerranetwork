# Modern Investing Techniques — two-week scoring review (2026-07-18)

**Question asked:** after the July 3–4 overhaul (benchmark integrity,
learning-loop self-audit, stop enforcement, shadow mode, dormant live
executor), is the system working as intended — and what makes it a
better product for listeners? Evidence: Ep096–Ep110 (14 episodes),
15 trade signals, the shadow ledger, the tracker, transcripts, and the
snapshot tool.

## Scorecard — every pending ledger prediction, now scored

| Prediction (July 3–4) | Verdict | Evidence |
|---|---|---|
| "closing-price confirmation" tic ≤2/10 (was 9/10) | **HIT** | 0/10 in the last-10 transcript snapshot; the lessons dedup held (ledger stable at 65 total / 11 active, no echo regrowth). |
| No new flash trade with a zero benchmark window | **HIT (thin n)** | No flash trades occurred; both new closes carry real windows. |
| No new trade with entry before pick date | **HIT** | Ep101 COST entry bar = pick date (Jul 9); Ep102 DAL = Jul 10. |
| TSX picks priced on `.TO`/`.V` | **PENDING** | No TSX picks in the window; both US picks carry `resolved_symbol`. |
| Shadow ledger ≥8 entries, zero duplicate ids, green with no secrets | **HIT** | 12 entries, every weekday covered, entries+paired exits, idempotent. |
| New closes carry all-3-index returns | **HIT** | Both trades have nasdaq/sp500/tsx matched returns. |
| New picks stamped with `rules_in_effect` | **HIT** | Both stamped with the exact 5 rule IDs shown on pick day. |
| ≥70% of picks carry a parsed stop | **HIT** | 2/2 picks carry `{"pct": 6.0}`; none above entry. |
| Outperformance claims hedged while t<2 | **MISS** | Alpha quoted in most episodes ("the portfolio holds a 7.0% alpha…"), the hedge spoken in **zero**. Root cause: the caveat lived in a separate instruction line — models echo data lines and drop instructions. **Fixed this pass**: the caveat is now embedded in the same sentence as the alpha number. |
| Live workflow green no-op while dormant | **HIT** | No `live_execution_state.json` exists — the layer has never touched anything. |

Also verified working: matched-window labeling reached air (6/10
episodes say "matched-window"), review-once guard, voided-trade
exclusions, cost ~$0.10/episode, chapters clean (one recap exception).

## What is NOT working as intended (found + fixed this pass)

### P0 (product): the regime brake deadlocked the show's signature segment
The Practice Investment made **2 picks in 14 episodes**, and both
scheduled Monday weekly picks were suppressed. Cause: the cold-streak
trigger used the **mean** of the last 10 alphas (poisoned indefinitely by
Ep81 MDA's −11.8% outlier: mean −0.98) OR **drawdown > $100** (standing
drawdown was $164 — permanently tripped for a strategy whose single
trades swing ±$120). Worse, cold suppresses new trades, new trades are
the only thing that refreshes the window → a self-reinforcing lockup.
Fixed (`shows/hooks/modern_investing.py`): **median** instead of mean
(−0.94 vs −1.0 threshold — today's record is borderline, not locked),
drawdown threshold raised to a full position ($250), and an **escape
valve**: when cold coincides with a >7-day pick drought, the guidance
becomes a "SELECTIVE RESET" that *expects* the next Monday pick with
honest moderate-conviction framing — because an extended pick drought
teaches listeners nothing. The fresh-cold text now also instructs the
show to SAY it's in capital-preservation mode and what re-opens trading
— dead air becomes a narrative.

### P0 (integrity): the one-bar "Weekly Hold"
Ep101 COST was picked Thursday and closed on Friday's pre-market run
with **entry and exit on the same Thursday bar** (−2.35% in a
zero-day "weekly hold") — a degenerate artifact of the July-3 pick-date
entry fix meeting the close-every-Friday rule. Fixed: a weekly hold now
closes on a Friday run only when ≥2 calendar days have elapsed since the
pick (Thu/Fri picks roll to the next Friday); the shadow executor's exit
calendar matches (`_exit_due_date`: Thursday → +8 days). Notably, the
shadow layer held COST Thu→Fri and made **+0.26% while the sim booked
−2.35%** on the same pick — the divergence that proves the fix matters.

### P1 (honesty): the index sweep compared a 37-trade score to 2-trade scores
`benchmark_scores` showed "beating 1 of 3 major indices" with S&P/TSX
samples of n=2 (history isn't backfilled until the operator's recompute
runs). Never actually spoken, but it was live prompt context. Fixed: the
sweep line only includes indices with ≥5 matched trades and needs 2+
qualifying indices to appear at all.

### P2: no-trade signals mislabeled as extraction drift
5 of 12 no-trade signals said `no_pick_extracted` (the drift alarm), but
the digests actually said "**Today's Pick:** None" / "**Trade Type:** No
new trade" — deliberate no-trade days in phrasings the regex missed, so
the drift alarm meant nothing. Fixed: broadened explicit-no-trade
detection (None/No Trade/No new trade/Mid-Week Update) + a new
`no_practice_section` reason for recap/weekend episodes.
`no_pick_extracted` now genuinely means drift.

## Watch list (no action yet)
- **"volume above the 20-day average" spoken in 8/10 episodes** — the
  LL-017 rule (reinforced ×23 pre-dedup) echoing on air. The rule
  scoreboard will adjudicate LL-017 once ~5 stamped trades close
  (currently 2); if it shows no edge it becomes a retirement candidate.
- Chronic under-length (all 10 recent episodes below the 1800w floor) —
  unchanged, still the network digest-ceiling deferral.
- Shadow executor runs land 15:04–16:48 UTC vs the 13:50 cron (GitHub
  delay, landmine #24) — quotes are mid-day rather than 9:50 ET.
  Acceptable for now; the Cloudflare exact-time dispatcher could add
  these slots if precision starts mattering.

## Product recommendations (for listeners/users — not yet implemented)
1. **Make the discipline visible** (shipped in part via the cold-streak
   transparency line): no-trade stretches should be a story listeners
   follow, not silence.
2. **"Execution reality" section on the performance page** once ~20
   shadow round trips exist: sim vs would-have-been-real, per trade —
   no other investing podcast shows its slippage honestly.
3. **Weekly scoreboard ritual**: the Sunday recap could own the weekly
   numbers (matched-window alpha, indices sweep once qualified, rule
   scoreboard movements) as a signature segment.
4. Operator items still open: **run `scripts/recompute_mit_benchmarks.py
   --apply`** (the current +6.59% matched alpha still contains
   old-window inflation; the sweep stays suppressed until backfill),
   SnapTrade Phase-0 status unknown from the repo (mirror artifacts
   aren't committed — check the Actions runs), and the closing-price
   lesson-family retirement (LL-054/005/013) remains a one-line flip.

## Shipped this pass
Regime v2 (median + $250 drawdown + drought escape valve + on-air
transparency), weekly min-hold rule (sim + shadow calendars), sweep
sample-gating, inline significance caveat, no-trade reason taxonomy.
Drift guards: `TestRegimeDeadlockFix`, `TestWeeklyMinHold`,
`TestSweepGating`, `TestNoTradeReasonTaxonomy` (+3 updated pins). 229
tests green. ⚠️ A/B-listen (landmine #17): regime text, inline caveat,
and cold-streak transparency are new/changed prompt context.
