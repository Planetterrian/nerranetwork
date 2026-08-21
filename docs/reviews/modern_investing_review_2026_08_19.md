# Modern Investing — learning loop, options, and transparency audit

**Date:** 2026-08-19
**Scope:** operator questions — is MIT actually learning from its lessons
and set up to keep improving; is it trading the strategies it teaches
(options in particular); is it maximally transparent about the tactics it
uses so the audience can learn from them.

Answers first, evidence under each.

---

## 1. Learning loop: it records, but its verdicts were artifacts

**The machinery ran. Its output was not evidence.**

`_build_rule_scoreboard` was emitting five findings:

```
[LL-015] in effect for 10 closed trades: avg alpha -0.17% (without: +0.43%) → RETIREMENT CANDIDATE
[LL-017] in effect for 10 closed trades: avg alpha -0.17% (without: +0.43%) → RETIREMENT CANDIDATE
[LL-028] in effect for 10 closed trades: avg alpha -0.17% (without: +0.43%) → RETIREMENT CANDIDATE
[LL-041] in effect for 10 closed trades: avg alpha -0.17% (without: +0.43%) → RETIREMENT CANDIDATE
[LL-054] in effect for 10 closed trades: avg alpha -0.17% (without: +0.43%) → RETIREMENT CANDIDATE
```

Five identical numbers, because all five rules were stamped on **exactly
the same 10 trades**. They are perfectly collinear: no design can
attribute an effect to any one of them. One undivided sample was being
reported as five findings, and the prompt was telling the model to
"weight proven rules more heavily" on the strength of it.

Worse, the control group — "trades without the rule" — was the 35 pre-era
trades whose benchmark windows the integrity passes had already disowned.
So the comparison was **new trades versus old trades**, confounded by the
exact measurement bug the era boundary exists to remove.

Three further problems in the same loop:

- **Six of thirteen "recursive improvement rules" are production hygiene,
  not investing skill**: re-teach cooldowns, "every episode must state the
  NASDAQ level", "every Quick Hit ends with an Action line", and three
  variants of "verify price data from multiple providers" — which are the
  pipeline's *own historical data-fetch bugs*, written up as investing
  wisdom and fed back into the pick prompt. (LL-054, the "closing-price
  confirmation" rule, has been carried as an open retirement item since
  July 2.)
- **Three of the remaining rules are the same rule.** LL-017, LL-041 and
  LL-067 all say "require volume above the 20-day average", differing only
  in scope clause, and scored 0.51–0.61 against a 0.62 dedup threshold —
  so all three reached the prompt and all three got stamped.
- **No rule has ever been scored** (`effectiveness` is unset on every
  entry) and none has been retired.

**Fixed.** The scoreboard is era-scoped; it refuses to produce a verdict
when every stamped trade carried the same rule set, flags collinear rules
as one piece of evidence rather than several, requires a real control
group (≥5 on both arms, the repo's existing `_MIN_SAMPLE_TRADES`
standard), and says "not measurable yet" instead of going silent —
silence is how the bogus verdicts rode for weeks. Pipeline rules are
classified out of the trading rule set (`_is_trading_rule`), and dedup now
compares the rule's **constraint** with its scope clause stripped
(`_rule_core`), which collapses LL-017 into LL-067 at 0.796 and lets a
genuinely distinct rule — the sector cap — into the set instead.

**Honest status:** the loop is now built to close. It has not closed yet,
and it cannot until the rule set varies between picks and the era
accumulates trades. What changed is that it will no longer manufacture
confidence in the meantime.

## 2. Options: it taught them constantly and had never traded one

| | |
|---|---:|
| Recent episodes discussing options/derivatives | **32 of 40** |
| Times `covered_call` has been taught | **33** |
| Simulated trades using any options structure | **0 of 61** |

Every one of the 61 trades was a long equity or ETF position. The show
has an options-flow source account (`unusual_whales`), an options-strategy
account (`OptionsPlay`), and "options strategy" and "covered call" among
its keywords — and its track record contains no evidence about any of it.

**Built:** covered calls and cash-secured puts, held to expiry.

The design constraint is that an option premium **cannot be reconstructed
after the fact** from free data. So the contract is quoted live at pick
time — real listed strike, real expiry, real bid/ask mid — and recorded;
the payoff at expiry is then arithmetic on the underlying's close with no
free parameters:

- covered call: `min(close, strike) × 100 + premium × 100 − capital`
- cash-secured put: `premium × 100 − max(0, strike − close) × 100`

Both were verified against hand calculations. Strike and expiry are chosen
by rule (nearest listed expiry 21–45 days out; listed strike closest to 4%
OTM), so selection is reproducible rather than taste. Returns are computed
on the capital the structure actually commits, which is what makes an
options position comparable with a $1,000 share position.

Two limits, both stated on air by prompt requirement:

1. **If the chain cannot be quoted, there is no option trade** — the pick
   degrades to shares and records `option_quote_failed`. A premium is
   never estimated.
2. **Early assignment is not modelled.** This flatters short-option
   positions slightly and the show has to keep saying so.

A test caught a real bug during this build: with no post-expiry bar,
settlement matched "the last bar on or before expiry" — which is just the
most recent bar — and closed a fresh position against its own entry day.
Settlement now requires evidence the market has traded on or after the
expiry date.

## 3. Transparency: good aggregates, no audit trail

What was already public: track record vs NASDAQ, cumulative return,
monthly P&L, win/loss split, P&L by sector, active lessons, and a
by-sector/approach table.

What was not: **the trades themselves.** The performance page showed five
recent rows. Nothing published carried entry or exit bar dates, the stop,
the horizon, the invalidation, the rules in effect, or the confidence
rating — i.e. none of what a listener would need to check the record or to
learn the process from it. The methodology page written on 2026-08-18 sat
in `docs/`, unlinked from the site.

**Built:** `scripts/build_mit_ledger.py` → `api/mit_trade_ledger.json` +
`.csv`, published nightly. Every trade, with the full decision record:

```json
{"episode_num": 141, "symbol": "NFI.TO", "confidence": "Medium",
 "invalidation": "If Canadian transit orders in the next quarterly fall
   below the prior-year level, the demand thesis is dead.",
 "horizon_sessions": 5, "policy_version": 2,
 "rules_in_effect": "LL-066|LL-054|LL-041|LL-028|LL-017",
 "in_current_era": true}
```

It deliberately includes the failures: the 7 voided picks with their
reasons, and the pre-era trades flagged `in_current_era: false`. A ledger
that quietly dropped its embarrassments would be marketing.

Current contents: 61 trades — 50 closed, 4 open, 7 voided, 2 in the new
era, 0 options (the first will appear when the show next picks one).

---

## What is still not true

- **The learning loop has not yet produced a single scored rule.** It is
  now capable of it and refuses to fake it. First real verdict needs the
  rule set to vary across a dozen or so era trades.
- **Confidence still reads "Medium" on both era picks.** The calibration
  rubric shipped yesterday; whether the model actually varies the rating
  is the open question, and it is a recorded prediction.
- **The options record is empty until the show picks one.** The prompt
  permits a structure but does not force one, deliberately — a covered
  call caps exactly the upside a momentum thesis wants, and picking one to
  look sophisticated would be worse than not trading options at all.
- **Per-strategy performance is still reported by sector, not by
  strategy family.** The strategy strings are 61 unique free-text
  descriptions, so there is nothing to group on yet. Tagging them is the
  next tractable step.
