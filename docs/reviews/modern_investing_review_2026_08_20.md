# Modern Investing — making the learning loop able to learn

**Date:** 2026-08-20
**Scope:** operator question — are there further improvements to the show
or the recursively-improving investing system.

Four candidates were found by audit; three were chosen and are shipped
here. The fourth (a listener feedback loop) is recorded as the biggest
remaining gap.

---

## 1. The loop was honest but could never produce a verdict

The 2026-08-19 pass stopped the rule scoreboard inventing findings. It did
not give it the ability to produce real ones.

Across the first 15 stamped trades, **only two rule sets have ever
existed**:

```
13 trades: LL-015, LL-017, LL-028, LL-041, LL-054
 2 trades: LL-017, LL-028, LL-041, LL-054, LL-066
```

They differ by one rule, and that difference arose because the lesson
ledger happened to change — not by design. Four of five rules are common
to both sets, so those four can never be told apart from each other, and
neither arm of the one that varies clears the 5-trade minimum. **The
experiment had no variation, so it had no power.** It would have stayed
silent indefinitely while looking like a working feedback loop.

**Shipped: deterministic rule rotation.** Each pick is shown a rotating
subset of the unproven rules (4 slots from a pool of ~6, cycling by
episode number). Over ten episodes that produces five distinct rule sets
and gives **every rule both a with-rule and a without-rule arm**, which is
the precondition for attribution. Because the rotation is a pure function
of the episode number, a reader auditing the ledger can recompute which
rules were in effect on any pick.

Two safeguards, because this is an intervention on the product and not
just on the measurement:

- **A rule that demonstrates an edge is pinned** and stops rotating. The
  point is to find out which heuristics work, not to withhold ones already
  known to.
- **Anything can be pinned by hand** with `always_on: true` — intended for
  safety-shaped rules, never for a hunch.

Honest expectation: with a pool of 6 and 4 slots each rule sits out about
a third of picks, so both arms reach the 5-trade minimum in roughly 20-25
era trades. That is about five weeks at the current cadence. It is slow
because the sample is small, not because the design is lazy — and it is
the first time the number is reachable at all.

## 2. The show could say which sectors worked, never which approaches

61 trades produced **61 unique free-text strategy strings**. "Momentum
play on earnings beat", "Earnings-surprise entry after reported beat",
"AI momentum entry on earnings-revision catalyst" — three descriptions of
what is arguably one method, with nothing to group them by. So
"are our momentum entries better than our valuation screens?" was
unanswerable, for the operator and for the audience, while the
performance page happily reported alpha by sector.

**Shipped: a closed strategy-family vocabulary** (momentum,
mean_reversion, valuation, catalyst_event, earnings_surprise,
dividend_income, macro_rotation, technical_breakout, merger_arb, other),
required on every new pick *and derived from the existing free text* so
the 61 historic trades are groupable immediately rather than starting the
count from zero. Derivation is deterministic regex over the strategy
string; an unmatched strategy becomes `other` rather than being forced
into a wrong bucket.

The resulting block feeds the pick prompt, and it inherits the same window
discipline as every other number the show speaks: computed over
verified-window trades when there are enough, otherwise labelled
*"indicative only, do NOT quote these as measured results on air"*.

## 3. The quality reviewer was skipping episodes silently

The daily audit runs on a fixed cron at 16:15 UTC. Shows finish at wildly
different times — MIT's last three episodes landed at 14:29, 19:41 and
09:32 UTC. Anything finishing after the audit window was recorded as
**"critical: Missed episode"**, and the next day an auto-close routine
resolved the issue by confirming *the file now exists*.

So a late episode got a false critical, a tidy auto-close, and **no
content review at all** — its digest length, required sections,
repetition, TTS artifacts and hallucination checks were never run. On
2026-08-19 that happened to four shows at once: modern_investing,
fascinating_frontiers, models_agents, models_agents_beginners.

**Shipped: a catch-up pass.** The audit now also reviews episodes from the
previous three days that carry no coverage mark, recording what it has
reviewed in `api/review_coverage.json` (pruned to 14 days) so the pass is
idempotent and the file persists across CI runs.

The first run found a **32-episode network-wide backlog** and immediately
surfaced real findings that had been invisible — including high
cross-episode repetition on MIT Ep139 and Ep140 (23 and 21 already-covered
stories). Catch-up is capped at 10 episodes per run, oldest first, because
the AI review calls Grok once per episode and a 42-episode run would spike
cost; the backlog drains over a few days at the same total cost.

This one is network-wide, not MIT-specific.

---

## The gap that remains: nothing learns from listeners

The system improves from its trades, its rules, YouTube retention, and an
LLM judge scoring its own scripts. It has **no path for a listener's
experience to enter the loop at all** — zero mentions of reply, email or
question in the podcast prompt, despite the show running a newsletter that
could carry one.

For a show whose stated purpose is teaching people to invest better, the
one signal it never collects is whether anyone learned anything. DP Pod
already solved the mechanics of this (email replies as a submission
channel, named on air). Deferred pending an operator decision, since it
needs an inbox and a triage path rather than just code.

## Also noted, not acted on

- **Long-form YouTube retention is 10% against 33% on Shorts** (169
  videos). Long-form is where subscribers convert, so the gap matters —
  but it is a network-wide video problem, not a MIT one.
- **Audience is flat**: 221 downloads/30d, weekly 52/44/61/50.
- **Listener-value scores stepped from ~3.9 to ~7.3** around Ep128 and
  have held, which is a real quality improvement showing up in an
  independent gauge.
