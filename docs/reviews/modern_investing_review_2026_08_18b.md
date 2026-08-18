# Modern Investing Techniques — rules-based restart

**Date:** 2026-08-18
**Scope:** operator-directed — "start fresh alpha tracking to beat NASDAQ
from today's show; clear and reproducible entry and exit decisions,
recursive learning loop, continuous improvement for the show and the
audience."

---

## The problem this solves

The show has produced 140 episodes and, after three passes of measurement
repair, still could not answer its own question. The reason was not the
estimator. It was that **the exit was never a decision.**

Weekly holds closed on whichever bar the Friday pre-market run happened to
price — which is Thursday's. A Monday pick therefore got five sessions, a
Wednesday pick got one, and both were called a "Weekly Hold" written to a
five-day thesis. Across the ten trades with trustworthy data, holds ran
0–6 sessions, median 3.

Per-trade alpha was measuring two things at once: whether the pick was
good, and which weekday it was announced on. No quantity of additional
trades separates those afterwards. That is why the record needed to
restart rather than merely accumulate.

## What shipped

### 1. A rulebook, in a file the code reads

[`shows/_trading_policy.yaml`](../../shows/_trading_policy.yaml) is now
the rules, and `load_policy()` / `horizon_sessions()` / `era_inception()`
read them:

- **Position:** $1,000, one at a time.
- **Entry:** open of the first session on/after the pick. Never earlier.
- **Exit:** the narrated stop (gap-aware) or a **fixed 5-session horizon**
  (flash: 1), whichever comes first. **No discretionary exit.**
- **Benchmark:** index bought and sold on the same sessions.

`_pick_weekly_bars` returns `window[horizon - 1]` instead of
`window[-1]`, so the exit index is fixed when the trade opens and does not
depend on when the sim next looks. `_evaluate_open_trade` counts printed
sessions instead of asking "is today Friday". Verified: a Monday, Tuesday
and Wednesday pick now all get exactly 5 sessions.

Two failure modes were closed while doing it. A fetch failure returns 0
sessions, which reads as *not due* — a bad network day can no longer close
every open position at whatever price came back. And `_close_trade` now
accepts the caller's bars, so the exit decision and the exit pricing read
the same snapshot.

`execution/shadow.py` derives its exit calendar from the same policy. If
those two ever drift, the shadow ledger stops being a check on the sim and
becomes a second opinion about the calendar.

### 2. A fresh era, and the old record kept as history

`era_*` fields in the summary score only trades picked on/after
2026-08-18. The show speaks that record. Earlier trades stay published —
nothing was deleted — but they are never blended into an on-air figure,
and while the era is empty the lifetime totals are explicitly labelled
`HISTORY ONLY` in the prompt so the model cannot reach for the nearest
impressive number.

Today the show will say: *the rules-based record starts now, and the first
result arrives when the first hold completes its five sessions.* That is a
stronger thing to say than a flattering number nobody can reproduce.

**`_alpha_scope()` is the single selector** both prompt blocks use — era →
verified → blended, each carrying its own label and trade count. This is
the direct fix for the August 15 failure where two blocks chose
independently and the model fused a value from one with a label from the
other.

### 3. Decisions that can be checked

Every pick now records, and the show states on air:

- **Invalidation** — the specific, observable thing that would prove the
  thesis wrong, named before the money is at risk. Not "if it drops": a
  level, a data release, a guidance number. The stop is derived from it.
- **Confidence** — now a *graded forecast*, not a formality.
- **policy_version** and **horizon_sessions** — stamped on the trade, so a
  future reader knows which rules produced it.

### 4. The learning loop actually closes

Confidence was a dead field: of 50 closed trades, 48 "Medium", 2 "Low",
**zero "High"** — a rating that never varied while feeding the show's own
analysis as if it did.

`get_mit_confidence_calibration` (the existing function — a second one was
written during this pass and **deleted before commit**, because shipping
two calibration sources would have repeated the exact mistake this pass
was fixing) is now era-scoped and carries the rubric: High means the
catalyst is confirmed, Medium means it is pending, Low means smaller size.
It reports realized hit-rate per bucket back into each episode and warns
on air if High-confidence picks stop outperforming Low ones.

### 5. Audience-facing

[`docs/mit_trading_method.md`](../mit_trading_method.md) publishes the
rules, the reasoning, why the record restarted, and a checklist for
auditing *any* track record. The podcast prompt requires the show to
explain the rules and to speak the invalidation line every episode, framed
as the habit to copy.

Six segments were added to the existing evergreen library — invalidation,
fixed horizons, what alpha actually measures, sample size, calibration,
and auditing someone else's record. They use the library's existing
rotation and cooldown machinery rather than a parallel system.

## What this costs, honestly

- **The show's headline number goes to zero for about a week**, then to a
  small sample that cannot support a claim of edge. The prompts require it
  to say so.
- **A fixed horizon will sometimes exit a position that would have kept
  running.** That is the price of a measurable process, and the show now
  teaches why it is worth paying.
- **The pre-era record still has 8 trades that reconcile to no price bar**
  — including its best, second-best and worst. That remains an operator
  item; it no longer contaminates the on-air number.

## Predictions for the next review

Recorded in the ledger: every era trade holds exactly 5 sessions (or exits
on a stop); zero blended figures reach air; confidence ratings vary; every
pick carries an invalidation.
