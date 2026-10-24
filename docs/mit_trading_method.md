# Modern Investing Techniques — the method, in full

*Published 2026-08-18, corrected 2026-10-24. The machine-readable version
the code actually reads is
[`shows/_trading_policy.yaml`](../shows/_trading_policy.yaml); this page is
the same rules in prose, plus a plain account of where the record has fallen
short of them.*

Every episode of Modern Investing Techniques makes one simulated
investment and reports how the previous ones turned out. This page exists
so that a listener can **check the show's homework** — take any pick, the
date it was announced, and daily price data, and arrive at the same
numbers the show reports. A track record nobody can reproduce is a story,
not a record.

## The rules

**Position size.** $1,000 per trade, one new position per episode. Because
a weekly hold lasts five sessions and the show publishes daily, several
positions are open at once (five is normal, seven has happened), each
scored on its own. The record is therefore the **average trade** against
the index over its own sessions — never a compounded chain, which would
describe a portfolio that reinvested each trade's proceeds in the next and
which these rules never held. Simulated — no real money is involved, and
this is not financial advice.

**Entry.** The pick is announced pre-market. The trade enters at the
**open of the first trading session on or after the announcement**. Never
earlier. If no session prints within 10 days, the trade is voided rather
than priced on a guess.

**Exit.** Whichever of these comes first:

1. **The stop is hit.** Every pick states a stop-loss as a price or a
   percent below entry. If any session's low after the entry session
   reaches it, the trade exits there (the entry session itself is not
   judged, because a daily bar cannot show whether its low came before or
   after the open). A gap straight through the stop fills at the open, not
   at the stop — because that is what would actually happen to you.

   *What actually happened, through 2026-10-24:* the sim enforces only a
   stop it can read from the published pick, and it could read one on
   **9 of the 41** rules-based picks. The others stated a "maximum
   acceptable loss" the parser did not recognise, or no level at all; the
   worst trade of the era (XNDU, −27.1%) ran to its horizon with no stop on
   record. No stop was ever reached on the nine that had one. Since
   2026-10-24 a maximum-loss sentence counts as the stop, every pick carries
   a required `Stop-Loss:` line, and a pick without a readable stop is
   regenerated before it ships. The ledger's `stop_stated` column says, per
   trade, whether a stop was in force.
2. **The horizon is reached.** A weekly hold is exactly **five sessions**:
   in at the first session's open, out at the fifth session's close. A
   flash trade is one session, open to close.

**There is no discretionary exit.** The show does not let winners run, and
it does not give a loser "a bit more time". That freedom is precisely what
makes most published track records unfalsifiable.

**Benchmark.** The comparison index is bought and sold on the *same
sessions* as the trade. So "alpha" here answers exactly one question: did
this pick beat the index over the time it was actually held? Not over the
year, not since inception — over its own holding window.

## Why the record restarted on 2026-08-18

For the show's first five months the exit was not a decision, it was a
side effect. Weekly holds were closed by whichever run happened to
evaluate them, and that run priced the previous session — so a Monday pick
got five sessions and a Wednesday pick got one, from the same rule.
Measured across the trades with trustworthy data, holds ran from 0 to 6
sessions, median 3, against picks written to a five-day thesis.

That makes the resulting alpha uninterpretable. It blends *was the pick
good* with *which weekday was it announced*, and no amount of extra data
separates them afterwards.

So the record was restarted, not erased. Every trade before 2026-08-18
remains published as the show's history. None of them are quoted as
evidence about the current method, because they cannot be.

**The show will report a small, honest number for a while.** That is the
intended outcome. Five trades is a scoreboard, not evidence, and the show
says so on air rather than implying an edge it has not earned.

## Options positions

The show teaches covered calls and cash-secured puts constantly — and for
its first 61 simulated trades it never placed one. The mechanism to close that
gap exists, in a way that keeps the record reproducible — but as of
2026-10-24 **no options position has been placed in 103 simulated trades**.
From that date, when ten picks run without one, the next pick must use a
covered call or cash-secured put on a US-listed name whose chain can be
quoted.

An option's premium cannot be reconstructed after the fact from free data.
So the contract is **quoted live when the pick is made** — a real listed
strike, a real expiry, a real bid/ask — and recorded. The position is then
**held to expiry**, where the payoff is arithmetic on the underlying's
closing price with no free parameters:

- **Covered call** — own 100 shares, sell one out-of-the-money call. At
  expiry the shares are worth `min(close, strike) × 100`, plus the premium
  kept. Gains are capped at the strike; that cap is the trade.
- **Cash-secured put** — set aside `strike × 100` in cash, sell one
  out-of-the-money put. At expiry you keep the premium, less
  `(strike − close) × 100` if the stock finished below the strike.

Strike and expiry are chosen by rule, not by taste: the nearest listed
expiry 21–45 days out, and the listed strike closest to 4% out of the
money. Returns are reported on the capital the structure actually
commits, which is what makes them comparable with a $1,000 share position.

Two honesty limits, stated on air whenever an options trade is discussed:

1. **If the chain cannot be quoted, no option trade happens.** The pick
   degrades to plain shares. A premium is never estimated — an
   unverifiable number is exactly what this record exists not to contain.
2. **Early assignment is not modelled.** American options can be assigned
   before expiry. This simulation holds to expiry, which slightly
   flatters short-option positions in a way the show should keep saying
   out loud.

## What gets recorded on every pick

| Field | Why it exists |
|---|---|
| Symbol, market, sector | What was bought, on which listing |
| Strategy | The approach being demonstrated |
| **Confidence** (High/Medium/Low) | A **graded forecast**. The show's realized hit-rate per bucket is fed back into the next episode. |
| **Invalidation** | The specific, observable thing that would prove the thesis wrong — named *before* the money is at risk |
| Stop-loss | Where the trade is wrong in price terms, derived from the invalidation |
| Horizon | Sessions to be held, fixed at entry |
| **Structure** | Shares, covered call, or cash-secured put |
| **Rules in effect** | Which of the show's own learned rules it was obeying |
| **Stop stated** | Whether the pick carried a stop the record could enforce |
| **Sessions held**, **entry factors** | How long it was actually held; the entry day's volume and trend condition, measured from the bars |

## Check the homework

The complete ledger — every trade, including the voided ones and the ones
that reconcile to no market bar — is published as
[`api/mit_trade_ledger.json`](https://nerranetwork.com/api/mit_trade_ledger.json)
and as CSV. It carries the entry and exit bar dates, the stop, the
horizon, the option contract, the stated invalidation, and the rules in
effect on the day of the pick: everything needed to recompute the numbers
without taking the show's word for anything.

A ledger that omitted its failures would be marketing, so the failures are
in there and labelled.

The **invalidation** line is the habit worth stealing. "I'll sell if it
drops" is not a plan. "If Q3 guidance comes in below $4.10 on the November
2 call, the re-rating thesis is dead" is one — it is checkable, it is
dated, and it tells you what you were wrong about, not merely that you
lost money.

## How confidence is kept honest

Across the 51 trades closed before the restart, 49 were rated "Medium",
2 "Low" and none "High". A rating that never varies carries no
information, and it was feeding the show's own analysis as though it did.

The rating is meant to be scored: each episode is shown its realized
outcome per confidence bucket, and if High-confidence picks stop
outperforming Low-confidence ones, the show is required to say so on air
and tighten what earns a High.

*What actually happened, through 2026-10-24:* **all 44 rules-based picks
were rated Medium.** The grade has had nothing to grade, and the warning
above has never been able to fire. Since 2026-10-24 a run of five Medium
picks makes the next rating High or Low by the rubric's factor count; the
ledger's `confidence` column shows whether that has worked.

## What the market said at each entry

The show's most repeated rule is "require volume above the 20-day average
before entering". Whether the rule was *shown to the writer* on pick day is
recorded on every trade; since 2026-10-24 the record also measures whether
the condition *held*: the entry day's volume against its 20-session
average, and the entry open against the 50-session average close, computed
from the same daily bars anyone can download (`entry_volume_ratio_20d`,
`entry_vs_50dma_pct` in the ledger). The show reports alpha with and
without each condition, calls a gap a finding only at ten trades a side
with the mean and the median agreeing, and says so on air when a pick leans
on a factor the record shows is not paying. On the first 36 rules-based
trades the volume condition was *not* paying: entries on above-average
volume averaged −2.9% against the index (5 of 14 beat it), entries below it
+0.6% (12 of 22).

## What "beating the NASDAQ" would actually take

The goal is real, and so is the bar. With one $1,000 position at a time
and roughly weekly turnover, beating the index is not about being right
more often — it is about the size of the wins relative to the losses, and
about not giving back edge through undisciplined exits.

Two honesty rules bound what the show may claim:

- **Sample size travels with every number.** An alpha figure is always
  spoken with the count of trades behind it.
- **No edge is claimed while it is statistically indistinguishable from
  luck.** The t-statistic is computed on the show's own per-trade alpha,
  and while it is below 2 the show says the result is early.

If the method does not beat the index, the show will report that it does
not. That is the only version of this worth listening to.
