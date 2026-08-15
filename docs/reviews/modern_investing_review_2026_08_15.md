# Modern Investing Techniques — pipeline, data & learning-loop review

**Date:** 2026-08-15
**Scope:** operator-directed — "review the MIT show pipeline in detail and
especially data, analytics, recursive learning and goal adjustment
process and optimize; review past shows for performance."
**Window:** Ep118–Ep137 transcripts + digests, the full 57-trade tracker,
137 episodes of pipeline metrics, and the five predictions left pending by
the 2026-07-24 review.

---

## Verdict

The measurement machinery this show has accumulated is genuinely good —
pick-date-aligned benchmark windows, a multi-index scoreboard, stop
enforcement, rule-effectiveness stamping, a shadow execution ledger, a
t-stat on its own alpha. Four separate passes built it between July 3 and
July 24 and every one of those mechanisms still works.

What this pass found is that **three of the loops built to keep the show
honest had quietly stopped closing**, and in each case the failure mode
was the same shape: a mechanism that was correct when it shipped became
wrong as the data around it changed, and nothing was watching the seam.

1. The headline alpha the show states on air every episode was carried by
   trades whose benchmark windows the pipeline itself had already
   disowned.
2. The segment that reports the track record was **absent from 13 of the
   last 20 episodes**, and on those days the script told listeners the
   performance feed was down. It was not.
3. 43 of 50 closed trades were never narrated at all — the review-once
   guard had flipped from over-reviewing to under-reviewing.

None of these are visible from the dashboard, the metrics, or the
ledger. All three were only findable by reading the tracker against the
transcripts.

---

## P0 — the spoken alpha was built from windows we know are wrong

`_recompute_summary` computed `matched_window_alpha_pct` over every closed
trade carrying a `nasdaq_return_pct`. That is 45 trades. But only **10**
of them were priced by the July-3 pick-date-aligned code path; the other
**35** carry the pre-July-3 windows that the July-3 review itself
described as "old-window inflation" and handed to an operator script
(`scripts/recompute_mit_benchmarks.py --apply`) that **has never been
run** — it has been an open item in the ledger for six weeks.

Split the two sets and they disagree completely:

| Subset | Trades | Portfolio | NASDAQ | Alpha |
|---|---:|---:|---:|---:|
| Verified windows (`entry_bar_date` present) | 10 | +2.69% | +4.64% | **−1.95%** |
| Legacy windows (pre-July-3) | 35 | +23.55% | +12.38% | +11.17% |
| Blended — **what shipped on air** | 45 | — | — | **+9.28%** |

Ep137 said it out loud: *"Matched window alpha versus the NASDAQ reaches
nine point three percent across forty five benchmarked trades."*

A number that survives only because it is averaged with numbers we know
are wrong is not a measurement. **Fixed:** `_recompute_summary` now also
computes a verified-only set (`verified_window_alpha_pct`,
`verified_window_trades`, `unverified_window_trades`, and a t-stat over
the verified subset alone), and `_build_portfolio_summary` makes that the
headline — with the trade count fused into the same sentence, and an
explicit "NOT for air" line on the blended figure. The show will now say
−1.9% across 10 verified-window trades.

That is a worse-sounding number and a better show. It also stops being
n=10 the moment the operator runs the recompute: every trade gains an
`entry_bar_date` and the verified figure simply becomes the whole record.
**That backfill is now the single highest-value operator action on this
show.**

## P0 — the track-record segment vanished from 65% of episodes, and the script invented a reason

13 of the last 20 digests (Ep118-121, 124-127, 129, 133-136) contain **no
Portfolio Performance section at all**. On those days the podcast stage —
which only sees the digest — filled the gap by narrating an outage:

> *"Portfolio performance numbers, including win rate and year-to-date
> alpha versus the NASDAQ, are not available in today's data feed, so we
> will resume that tracking once the next update arrives."* (Ep134)

> *"Portfolio performance data including cumulative returns, win rate,
> and alpha versus the NASDAQ is not available in today's briefing, so we
> will report those figures once the tracker updates."* (Ep135)

The data was never unavailable. `investment_tracker.json` is a committed
file, it was healthy on every one of those days, and `{portfolio_summary}`
was substituted into the prompt as always. The model omitted the section,
then explained its own omission as a data failure — on the show whose
entire premise is a published track record.

**Root cause, and it is a single line:** the digest prompt supplies the
figures under `**PORTFOLIO PERFORMANCE (use these exact numbers):**` as
*input context* at line 159, and instructs "state every episode" at line
34 — but the `### FORMATTING (EXACT — USE MARKDOWN AS SHOWN)` block, which
is the template the model actually follows, **never listed the section**.
Every other segment in the show appears there. This one did not, so it
shipped roughly a third of the time.

**Fixed:** `### Portfolio Performance` added to the FORMATTING template
with the figures marked REQUIRED, plus an explicit ban — in both the
digest and podcast prompts — on ever narrating the performance data as
unavailable, pending, or awaiting a tracker update.

## P0 — 43 of 50 closed trades were never reviewed on air

The July 2 review found the opposite problem: the MU flash trade narrated
as "yesterday's trade" three times. The fix stamped `reviewed_in_episode`
on each trade the first time it was narrated. It worked, and it introduced
a second bug in the same function.

`_build_trade_review` only ever examined `closed[-1]` — the **last trade
appended**. When the pick cadence was roughly weekly this was fine, because
at most one trade closed between reviews. The cadence is now roughly one
pick per day (Aug 3, 5, 7, 8, 10, 11, 12 all produced picks), several
close between episodes, and every close except the newest was skipped
**permanently** — the stamp on the newest one sent the next episode down
the "no newly closed trade" branch.

Five closes in the ten days before this review were never narrated: LNTH
(Ep126), MU (Ep130, **+5.12%, the best result in weeks**), TBBK (Ep131),
IPCO.TO (Ep133), AAPL (Ep134). Their P&L still counted in the running
totals the segment reported — so the show was quoting an aggregate built
from trades the audience never heard resolve. This is also the mechanical
explanation for the July-24 finding of "no newly closed trade" in 9 of 10
episodes, which that review attributed to the pick drought.

**Fixed:** the review now drains the backlog oldest-first, one trade per
episode, so every result is narrated exactly once. Bounded by
`REVIEW_BACKLOG_MAX_DAYS = 14` so the 38-trade historical backlog is
retired in place rather than replayed as fresh news — with the newest
close never retired, however old, so a long pipeline outage cannot
silence the segment.

## P1 — "Weekly Hold" holds averaged 2.8 sessions, not five

Every pick is labelled a Weekly Hold and written against a five-day thesis
("+3% to +6% over the five-day window" — Ep135). The verified windows say
the holds actually ran 0–6 calendar days, median 3:

```
Ep101 COST 0d · Ep102 DAL 6d · Ep117 EPD 3d · Ep126 LNTH 3d · Ep128 AMD 1d
Ep130 MU  6d · Ep131 TBBK 3d · Ep133 IPCO.TO 3d · Ep134 AAPL 2d · Ep135 X.TO 1d
```

This is structural, not random. Exits are pinned to the Friday pre-market
run, which prices **Thursday's** bar, so a Wednesday pick resolves after a
single session. The July-18 minimum-hold guard measures calendar days
since the pick (`today - pick_date >= 2`), which a Wed→Fri pick satisfies
while still producing a one-bar window — the Ep101 zero-bar degenerate was
fixed, the one-bar case was not.

**Fixed (narration side):** the review block now states the span that
actually happened — *"Actual hold: 1 calendar day of market data
(Wednesday → Thursday)"* — with an explicit instruction never to call it a
five-day hold unless the dates say so. **Not fixed (cadence side):**
whether a "weekly" hold should run a fixed five bars from entry instead of
to the next Friday is an editorial decision, deferred to the operator; the
shadow executor's exit calendar would need to move with it.

## P1 — the source-collapse alarm went quiet as the collapse got worse

MIT's article fetch has fallen by roughly 78% and has been there for three
weeks:

| Episodes | Median articles |
|---|---:|
| Ep90–99 | 274 |
| Ep100–109 | 268 |
| Ep110–119 | 277 |
| Ep120–129 | **50** |
| Ep130–137 | **64** |

The alarm shipped on 2026-07-24 fired three times (Ep121, 123, 124) and
then stopped — because it compares today against the median of the **last
10 episodes**, and the decayed counts became the baseline. Ep132's 32
articles and Ep133's 28 passed silently. A watchdog whose reference point
follows the thing it is watching only catches a cliff, never a slide.

The cause is feed rot. Probed live with the production User-Agent:

| Feed | Result |
|---|---|
| CNBC Investing | **403 Forbidden** |
| CNBC Top Stories | **403 Forbidden** |
| Benzinga | **403 Forbidden** |
| r/stocks | 429 (Reddit rate-limits this egress; may differ in CI) |
| CBC Business | 200 (the earlier timeout was transient) |

**Fixed:** three dead feeds removed and replaced with live ones probed
first — Yahoo Finance (49 entries), a Google News earnings query (100), a
Google News Fed/BoC rates query (92). The alarm gained a **second, longer
baseline**: it now also fires when the last 10 episodes are running under
half the median of the 50 before them, which is the shape a slide makes.
Both medians are recorded as metrics so the decay is visible rather than
inferred. Reddit was left alone — a 429 from this egress is not evidence
the feed is dead in production.

This is also the upstream cause of the July-24 x.com-sourcing finding:
when RSS thins out, the X-post block is what is left. It is still
happening — 6 of the last 12 episodes cite more than two x.com sources on
normal-fetch days (Ep128 was 6 of 7).

## Learning loops — audited, mostly healthy

- **`lessons_learned.json`**: 11 distinct actives, 54 correctly marked
  `merged_duplicate`. The July-3 dedup held; no echo regrowth. ✅
- **`taught_lessons.json`**: 25 lessons under cooldown, working. ✅
- **Rule-effectiveness stamping**: 11 trades stamped with
  `rules_in_effect`. Accruing; the scoreboard needs ~8 stamped closes per
  rule before it can adjudicate. ✅
- **YouTube title feedback**: 150 videos analysed, hints distinguish
  long-form (median 9% retention) from Shorts (33%), and identify which
  titles converted subscribers. Working as designed. ✅
- **Show memory / narrative tracker**: present and updating. ✅
- **Benchmark windows**: broken as described above. ❌
- **Trade review**: broken as described above. ❌

The pattern worth naming: the loops that operate on *text* are healthy,
and the loops that operate on *numbers* are the ones that drifted. Text
loops fail loudly (a repeated phrase shows up in a snapshot); number loops
fail silently, because a wrong number looks exactly like a right one.

## Model strategy — grok-4.6

Grok 4.6 shipped 2026-08-12: a post-training upgrade over 4.5, 500K
context, an added `xhigh` reasoning level, priced at $2/$6 per 1M
(vs grok-4.3 at $1.25/$2.50).

**The digest and fetch stages stay on grok-4.3, and this is not a close
call.** The network's documented reason for holding facts-first stages
there is that grok-4.5 regressed confident-hallucination from 25% to 54%.
4.6 is built on 4.5's post-training, so that risk is *unmeasured for it,
not disproven*, and MIT is the show where a hallucinated number is most
expensive — it names real tickers, quotes real prices, and publishes a
track record. Switching its digest model on a capability headline would
be the exact trade the network already decided against.

**Shipped instead:** `llm.podcast_model: grok-4.6` — the script stage
only, following the dp_pod precedent. That stage introduces no facts; it
rewrites an already-verified digest into a script. It is also where MIT's
last unfixed chronic problem lives: 9 of the last 10 scripts came in under
the 1800-word floor (median 1535w), and the digest-substrate lever shipped
on July 24 moved that only from 1382w — which points at the script stage
as the remaining ceiling. Registered as experiment `mit-script-model-46`,
readout 2026-08-29, revert is deleting one line.

Because the model id could not be validated against the API from this
session (no key present), `engine/generator.py` now catches a failed
script-stage override, falls back to `config.llm.model`, and prints a
GitHub warning. A wrong id costs the experiment, never an episode.

---

## Scoring the 2026-07-24 predictions

| Metric | Expected | Verdict |
|---|---|---|
| Suffixed/crypto picks recorded correctly | 0 lost or mangled | **hit** — IPCO.TO and X.TO recorded verbatim with `.TO`; no crypto pick in window |
| Stop/reference ratio outside [1/3, 3] | 0 | **hit** — 0 across all non-voided trades |
| Alpha mentions carrying the significance qualifier | ≥70% | **miss (3rd)** — 0 of 22 mentions across Ep126–137 |
| Median script words | ≥1550w | **partial** — 1382w → 1535w; 9 of 10 still below the 1800 floor |
| Episodes with >2 x.com citations on normal-fetch days | 0 | **miss** — 6 of 12; Ep128 6/7, all on 58–81-article days |

**The significance-qualifier metric has now missed three times.** Per the
playbook's two-miss escalation rule, a fourth mechanism is not the answer
and none was written. Three have been tried: a separate instruction
(dropped entirely), an em-dash inline form (1/6), and a data-shaped
parenthetical fused into the value (0/22). Each was stripped during
paraphrase. This goes to the operator as **accept-or-abandon**: either the
qualifier is dropped as unachievable through prompt instruction, or the
alpha figure stops being handed to the model as a number it can rephrase.
The verified-window change above makes the second option more attractive —
the sample size is now part of the sentence the model is given, so if it
survives paraphrase at n=10 the mechanism works after all and this is
re-scorable in two weeks.

---

## Operator items

1. **Run `scripts/recompute_mit_benchmarks.py --apply`** (needs market-data
   access). Open since 2026-07-03. It collapses the verified/legacy split
   and takes the honest alpha sample from n=10 to n=45. Highest value.
2. **Decide the significance-qualifier question** (accept or abandon) —
   three mechanisms, three misses.
3. **A/B-listen the first post-merge episodes** — prompt and script-model
   changes both alter shipped audio (landmine #17).
4. **Decide the weekly-hold cadence**: fixed five bars from entry, or keep
   the Friday-close calendar and let the narration describe the real span
   (which is what shipped).
5. Carried: SnapTrade Phase-0 verification; the closing-price lesson
   retirement.
