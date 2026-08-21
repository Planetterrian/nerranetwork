# Modern Investing Techniques — the method, in full

*Published 2026-08-18. The machine-readable version the code actually
reads is [`shows/_trading_policy.yaml`](../shows/_trading_policy.yaml); this
page is the same rules in prose.*

Every episode of Modern Investing Techniques makes one simulated
investment and reports how the previous ones turned out. This page exists
so that a listener can **check the show's homework** — take any pick, the
date it was announced, and daily price data, and arrive at the same
numbers the show reports. A track record nobody can reproduce is a story,
not a record.

## The rules

**Position size.** $1,000 per trade, one position at a time. Simulated —
no real money is involved, and this is not financial advice.

**Entry.** The pick is announced pre-market. The trade enters at the
**open of the first trading session on or after the announcement**. Never
earlier. If no session prints within 10 days, the trade is voided rather
than priced on a guess.

**Exit.** Whichever of these comes first:

1. **The stop is hit.** Every pick states a stop-loss on air. If any
   session's low reaches it, the trade exits there. A gap straight through
   the stop fills at the open, not at the stop — because that is what
   would actually happen to you.
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
its first 61 simulated trades it never placed one. That gap is closed, but
only in a way that keeps the record reproducible.

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

Across the 50 trades closed before the restart, 48 were rated "Medium",
2 "Low" and none "High". A rating that never varies carries no
information, and it was feeding the show's own analysis as though it did.

Now the rating is scored. Each episode is shown its realized outcome per
confidence bucket, and if High-confidence picks stop outperforming
Low-confidence ones, the show is required to say so on air and tighten
what earns a High.

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
