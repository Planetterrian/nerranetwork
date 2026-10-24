# Modern Investing Techniques — deep review (2026-10-24)

Operator brief: the show should be a great guide to investing techniques,
demonstrate them with live simulated trades that are transparent, and
recursively improve toward beating the NASDAQ. This pass read the record
(the tracker, the public ledger, 36 closed rules-based trades), the hook
that runs the simulation, the three prompts, the public pages and the last
twelve episodes as spoken (Ep199–210), and measured each claim the show
makes about itself against the data. Everything below that says "fixed" is
in this PR; guards are in `tests/test_mit_review_2026_10_24.py`.

## 1. The record as it stands

Era 2 (rules-based, since 2026-08-18): **36 closed trades, average alpha
−0.76% per trade against the NASDAQ over the same sessions, 17 of 36 beat
the index, −$311.40 across 36 parallel $1,000 positions, t = −0.74** (not
distinguishable from luck). Lifetime, every trade since March: 87 closed,
52% win rate, −$14.73. Five positions open (GM, CM.TO, MU, AAPL, COIN).

The mechanics reconcile: every closed era weekly hold ran exactly five
sessions from its entry bar, every flash trade one, no entry predates its
pick, and the era average recomputes to the cent. The record is honest in
construction. What it is not, yet, is a test of the method — because the
rules it publishes were only partly in force, and the loop that is meant
to improve the picks has been measuring the wrong thing.

## 2. What the data showed

**The stop was a rule on paper.** The policy says exit at the stated stop or
the fifth close. The sim enforces only a stop it can parse from the pick,
and it had one on **9 of 41** rules-based picks (`stopped_out` is true on
none). Of the 18 era digests whose stop went unread, 15 stated one as
"maximum acceptable loss 8 percent" or "max loss capped at 6%", shapes the
parser did not know; Ep210 (COIN) dropped the Risk Assessment line
entirely and is running with no stop after the script spoke "limits dollar
risk to eighty dollars". The worst trade of the era, XNDU at −27.1%, ran to
its horizon. A second parser fault was live: the price form won over the
percent form, so GM's "stop-loss set 6 percent below entry to limit loss
to roughly $60" was recorded as a **$60 stop on an $82.75 stock** and
published in the ledger as a 27% stop; "maximum loss capped at position
size of $1,000" parsed as a $1,000 stop, which `_close_trade` discarded
but the pre-check did not — it would have closed the trade on session two
through the horizon path with no flag.

**Every one of 44 era picks was rated Medium.** The rubric, the per-bucket
calibration read-back and September's "do not repeat that" all asked the
model to vary it; nothing did. Eleven of twelve recent episodes gave the
same reason ("sector rotation not yet confirmed by volume") and entered
anyway. The grade the method page promises to score has had nothing to
score, and the High-vs-Low warning requires both buckets, which have never
existed.

**No options position in 103 trades**, across two readouts that predicted
at least one in ten, while covered calls were taught or re-explained in 6
of the last 12 episodes and the identical "parking spot" analogy — a
specimen sentence in the system prompt — aired verbatim in five of nine.

**The learning loop scored exposure, not conditions.** `rules_in_effect`
records which rule TEXT was shown on pick day. The four active rules are
one constraint in four scopes ("volume above the 20-day average before
entering…"), each on ~29 of 36 trades by rotation, so every with/without
comparison was two readings of one sample — and the "Lesson Learned" the
review asked for came back as the rule copied from the ledger (7 of 8
reviews ended on LL-066 or LL-067 verbatim; TD.TO, a Canadian bank that
beat the index by 5.4 points, got "single-name fintech exposure can lag
broader tech rotation").

Measured on the market's own record instead — the entry day's volume
against its 20-session average and the entry open against the 50-session
average close, from the daily bars the sim already fetches — the show's
favourite rule is **not paying**: entries on above-average volume averaged
−2.86% alpha over 14 trades (median −2.30%, 5 beat the index); entries
below it +0.57% over 22 (median +0.25%, 12 beat). The trend condition
reads +0.54% over 18 against −2.06% over 18, but the medians disagree
(−1.33% vs −0.67%): one −26% trade moves the mean, so it is noise for now.

**The lifetime blend rode inside the trade review.** The block the model
received for yesterday's trade carried "Running Total: $-14.73 across 87
trades · Win Rate 45/87 (52%)", and Portfolio Performance led with
"Lifetime totals" and put the era alpha fourth — so Ep200–210 all spoke the
87-trade figures as the scoreboard beside the era alpha, the blend the
Aug 18 restart exists to prevent.

**The alpha line in the trade review was written from nothing.** The block
gave entry, exit and P&L and not the tracker's `nasdaq_return_pct` or
`alpha_pct`. Six of eight spoken verdicts in Ep199–210 were wrong: ATZ.TO
"+3.1% alpha" against a recorded +7.51%; the day's −0.10% NASDAQ move
pasted onto two different six-day windows (Ep209, Ep210); EDV "lagged
broader rotation" while beating the index by 3.8 points.

**The headline changed basis with nothing said.** Ep208 aired "minus
thirty-three point one percent across thirty-four rules-based trades"
(the compounded chain); Ep209 "minus zero point eight percent across
thirty-six" (the average trade, after the Oct 22 change). Two closes
cannot move a figure 32 points.

**Smaller, each verified:** the public method page said "one position at a
time" (five are open; seven have been); the show page's "How the Practice
Investment Model Works" still described the pre-Aug-18 Monday-pick/Friday-
close model, as did both prompts' hybrid-model text (Ep204 followed it,
wrote a "Mid-Week Update" and spent the no-trade budget); the performance
page showed the era record nowhere and led with the blended compounded
−27.3%; 27 of 44 era picks were sector "other" because the extractor never
read the digest's required `**Sector:**` line; Ep205's pick "TSX:H — Hydro
One" was lost as `no_pick_extracted`; the narrative callback recalled the
same trade on consecutive days (IAG 199/200, AVGO 208/209) because it never
stamped; "Actual hold: 6 calendar day(s)" aired beside "a fixed five-session
hold"; Ep208 shipped with no Investor Education (the section was never
validated); invalidations are routinely dated outside the five-session
window (a November call cannot fire in an October hold).

## 3. Fixed in this PR

Code (`shows/hooks/modern_investing.py` unless noted):

1. **Stops.** A stated maximum loss is the stop; whichever form the
   sentence states first wins (GM reads 6%); the position size is never a
   stop; `_stop_already_breached` has `_close_trade`'s sanity guard; open
   trades' stops are re-read from their committed digests every run with
   the current parser (`_refresh_open_stops` — GM corrects itself, AAPL
   gains its 8%); the digest carries a required `**Stop-Loss:**` line and a
   new lint `pick_stop_loss` (`engine/digest_lint.py`) regenerates a pick
   without a readable stop.
2. **Measured entry factors.** `_bars_from_history` carries volume;
   `_close_trade` records `entry_volume_ratio_20d`, `entry_vs_50dma_pct`
   and `sessions_held`; `_backfill_entry_factors` stamps eight older era
   trades a run; `_build_factor_scoreboard` reports alpha with and without
   each condition, "not measurable yet" under five a side, a finding only
   at ten a side with mean and median agreeing. It rides beside the rule
   scoreboard in the digest prompt and the ledger carries the columns.
3. **The trade review** drops the lifetime figures, hands over the stated
   confidence, invalidation and stop (so the review grades the forecast),
   states the hold in sessions, and carries the tracker's own NASDAQ
   window return and alpha with the instruction to use them.
4. **Portfolio Performance** leads with the era record (alpha, n, beat
   count, dollars, t-stat), labels the lifetime block HISTORY ONLY
   whenever the era has trades, drops best/worst, and carries a one-time
   note (two airings, stamped) explaining the compounded-to-average basis
   change.
5. **Confidence budget** (five Mediums → the next pick is High or Low by
   factor count) and **options cadence** (ten share picks → the next is a
   covered call or cash-secured put on a US-listed name), both counted
   from the recorded picks like the no-trade budget that worked.
6. The extractor reads `**Sector:**` and accepts an exchange prefix; the
   callback stamps each trade once; the sector block is era-scoped once the
   era has ten closes; the signal carries `structure` and `invalidation`;
   the validator requires Investor Education and Portfolio Performance;
   the ledger emits `stopped_out: false` on closed trades, `stop_stated`,
   `window_verified` and the factor columns; the dashboard reads
   `mit_stop_stated_share_10ep` and `mit_non_medium_share_10ep`.

Prompts (⚠️ AUDIO — A/B-listen the first two episodes): the hybrid-model
text in the digest, podcast and system prompts now states the rulebook (one
pick every episode, enters next open, five sessions or the stop, parallel
positions); the Strategy Spotlight teaches one technique with a worked
example and the pick demonstrates it; the Invalidation must be observable
inside the five sessions; the Lesson Learned grades the forecast and writes
a Rule only for something the rules and the measured factors do not already
say; Portfolio Performance speaks the record first and the history in one
sentence; weekend episodes call the levels Friday's closes; the "parking
spot" specimen, the "habit the listener should copy" frame and the per-tool
"no financial relationship" repeat are de-seeded by shape; the system
prompt's sporting-event framing reports the record plainly.

Public pages: the performance page and the show page lead with the era
record and label the compounded and buy-and-hold figures history; the show
page's model copy is the rulebook; `docs/mit_trading_method.md` tells the
truth about positions, stops, confidence and options, and documents the
measured factors.

## 4. Not fixed, on purpose

- **The recompute (`scripts/recompute_mit_benchmarks.py --apply`)** stays
  the operator's decision; the public pages now label what it would
  change.
- **Weekend picks** (Saturday and Sunday episodes enter Monday's open) are
  consistent with the rules and left as they are; the prompt now says the
  entry is Monday.
- **A mechanically computed confidence grade** was considered and not
  built: a grade the writer does not own is not a forecast. The budget
  forces variation first; if the varied grades carry no information after
  ~20 picks, compute it then.
- **Hydro One (Ep205)** is not added to the record after the fact — the
  pick never entered, and a trade recorded from hindsight is the thing the
  record exists not to contain.

## 5. Scoring prior predictions (ledger 2026-09-25 and earlier)

- Chapters collapsing on the disclaimer: **hit** (Oct 11/17 pattern fixes;
  Ep206–210 chapter files carry Market Pulse before Practice Investment).
- Pre-era best/worst recited in Portfolio Performance: **miss** — Ep199–209
  read the lifetime block every episode; the block led with it. Fixed
  above.
- Volume-confirmation taught in one segment: **miss** — "twenty-day
  average" 27 mentions in 12 episodes; the Spotlight closed on it in six.
  The measured factor now tells the writer the rule is not paying.
- Median script words ≥ 1,700: **hit** — 1,640–2,250 on the grok-4.6
  script stage since Ep198.
- `mit_new_trade_share_10ep` ≥ 0.8: **hit** (0.9).
- Options structures: **miss**, third window (0 of 103). Cadence rule above.
- Confidence non-Medium ≥ 3 of 10: **miss** (0 of 44). Budget above.
- Sources on x.com ≤ 40%: **partial** — Ep206–210 Practice Investment
  sources: 2 of 5 on x.com.

## 6. Predictions

See the ledger entry dated 2026-10-24.
