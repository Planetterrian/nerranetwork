# Modern Investing Techniques — on-air disclosure of the record restart

**Date:** 2026-08-20
**Trigger:** operator question — *"Should we add a segment into the next
show to discuss all the recent changes and how it will impact future
episodes?"*

## What the show actually said

The question is worth answering from the tape, not from intent. Ep141–143
are the first three episodes after the era-scoped record started:

| | Ep141 | Ep142 | Ep143 |
|---|---|---|---|
| Announces the new regime | ✅ | ✅ | ✅ |
| Explains **why** it restarted | — | ✅ | — |
| Points at the rulebook or ledger | — | — | — |
| Mentions the figure it used to quote | — | — | — |

So the show told listeners a new record had started and, once, roughly
why. What it never did was account for what left. The old cumulative
figure — **+9.28% across forty-five trades** — was quoted on air for
weeks and then simply stopped appearing.

## Why that is the problem worth fixing

A strong number that quietly disappears from a track record is the
oldest tell in performance reporting, and a listener has no way to
distinguish it from the honest case. Here the honest case is the actual
one: that figure blended trades whose entry and exit prices could not be
tied back to the sessions the trade was held, an audit could not
reproduce it, and it was therefore not the show's to claim.

Saying that out loud is not damage control. It is the single most
transferable thing this show has had to teach — the listener's real
takeaway is not "MIT restarted its record", it is **how to interrogate
any track record they are shown**.

## What shipped

A **one-off** correction, not a standing changelog.

- `_build_methodology_disclosure()` emits a ~250-word segment inside
  Portfolio Performance and retires itself after
  `METHODOLOGY_DISCLOSURE_EPISODES = 3` airings.
- Airings are stamped on the tracker as a list of episode numbers, so a
  second `get_prompt_context` call within one episode cannot consume two
  airings, and the record shows exactly which episodes carried it.
- Read-only (`--test` / rehearse) runs never consume an airing.
- Content covers, in order: the figure is gone and that is deliberate;
  it could not be reproduced; the exit rule was the deeper problem (a
  Monday pick was held ~5 sessions and a Wednesday pick ~1, so per-trade
  performance was measuring the weekday as much as the idea); some older
  trades match no market bars at all and include both the best and the
  worst results; the published rulebook that replaced it; the honest cost
  (a small record means a near-meaningless alpha number for weeks); and
  the four questions to ask of any record — when did it start and was
  that date chosen after the fact, what is the exit rule and was it fixed
  in advance, are losers and abandoned positions included, and are the
  individual trades published or only the summary.

**Deliberately out of scope:** rule rotation, review coverage, scoreboard
mechanics, model choices, anything about the pipeline. A listener cares
what the numbers mean, not how the repo is wired, and a drift guard fails
if any of it leaks into the spoken portion.

## The claim had to be made true first

The segment tells listeners the rules and the trade-by-trade ledger are
"published for anyone to check". Before this pass that was true only for
someone who knew the repo layout: `scripts/build_mit_ledger.py` wrote
`api/mit_trade_ledger.json` + `.csv` nightly and **nothing linked them**.

`modern-investing-performance.html` now carries a *Verify this record
yourself* panel linking the rulebook and both ledger formats, with the
framing that matters — the ledger includes the losers, the voided picks,
and the pre-era trades that are flagged and never blended into the
on-air number. A guard asserts both the links and the files exist, so the
claim cannot silently become false again.

## Predictions

Scored in `docs/reviews/ledger/modern_investing.yaml` (2026-08-20b):
exactly three airings then zero; no listener-value regression below 7.0
on the correction episodes; and measurable traffic to the performance
page within 14 days — if that stays flat, the on-air pointer is not
working and needs rewording rather than repeating.

## Landmine #17

This is a prompt change and it changes shipped audio. **A/B-listen the
first episode that carries the correction** before trusting it.

## Verified on air — Ep144, not Ep145

The episode shipped at 17:38 UTC, *after* both merges landed, so Ep144
was the first carrier rather than Ep145 as expected. All four checks
pass:

| Check | Result |
|---|---|
| Correction present in `### Portfolio Performance` | ✅ |
| `methodology_disclosure_episodes` | `[144]` |
| Pick carries a strategy family | `catalyst_event` |
| Stamped rule set varies | `LL-002, LL-067, LL-066, LL-041` vs Ep142's `LL-066, LL-054, LL-041, LL-028, LL-017` |

Rule rotation is live: two rules never stamped before (LL-002, LL-067)
entered, three rotated out. The catch-up pass wrote its first
`api/review_coverage.json` — 10 backlog entries from 2026-08-17 plus the
day's 10, exactly the per-run cap, oldest first.

### Two gaps the first airing exposed

**The segment invited verification and named no destination.** It said
the rules and ledger are "published for anyone to check" and stopped
there. A listener had nowhere to go — and the page-traffic prediction
was untestable, because nobody was ever told where to look. The
disclosure now names the performance page in the show's usual spoken-URL
style, guarded by `test_names_where_to_check`.

**The correction and the performance numbers fused into one block.** The
whole segment ran into "Portfolio Performance (simulated, $1,000 per
trade): Total trades: 51…" as a single paragraph. The prompt now
requires the correction to stand as its own paragraph ahead of the
numbers.

### Unrelated finding: the daily audit is timing out

The 2026-08-20 audit was **cancelled at its 20-minute job ceiling** with
the review step killed at 19m15s. 2026-08-18 died the same way *before*
the catch-up pass existed, so 20 minutes was already marginal; adding up
to ten Grok calls made it binding. Coverage still persisted (the pass is
idempotent and resumes), but that run's audit findings were lost — the
exact failure the catch-up pass exists to end. Job budget raised to 45
minutes with a 35-minute step cap beneath it, so a hung review can never
take the persist and remediation steps down with it.
