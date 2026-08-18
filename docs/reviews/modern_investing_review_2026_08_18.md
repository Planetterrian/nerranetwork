# Modern Investing Techniques — impact review of the Aug 15 pass

**Date:** 2026-08-18
**Scope:** operator-directed — "review all recent MIT changes and how they
have impacted the show, and continue to improve and refine to beat the
NASDAQ."
**Window:** Ep138–140 (the first three episodes generated after the
2026-08-15 merge), plus a live realignment dry run over all 50 closed
trades.

---

## Scorecard on the August 15 pass

| Change | Result | Evidence |
|---|---|---|
| `### Portfolio Performance` in the digest template | **HIT** | present in 3/3 episodes; was 7/20 before |
| Ban on narrating a performance-data outage | **HIT** | 0 outage claims in Ep138–140 (was 6 in the prior 20) |
| Trade-review backlog drain | **HIT** | LNTH→Ep138, MU→Ep139, TBBK→Ep140, exactly one per episode; 38 stale retired; 2 left |
| Honest hold-span narration | **HIT** | spans stated from real bar dates |
| Source-decay alarm (long baseline) | **HIT (fired correctly)** | `article_count_degraded` true on all three — the show *is* running below half its long-run baseline |
| `grok-4.6` on the script stage | **HIT** | see below |
| Verified-window alpha on air | **PARTIAL — and it produced a worse failure than the bug it fixed** | see P0 |

### grok-4.6 script stage — the clearest win

| | Ep134–137 | Ep138–140 |
|---|---:|---:|
| Script words | 1441–1576 | **2078–2366** |
| vs the 1800-word floor | 0 of 4 clear it | **3 of 3 clear it** |

Length had been stuck for months and survived a digest-substrate lever
that moved it only 1382w → 1535w. The script stage was the ceiling.

Factuality — the experiment's revert criterion — holds. Every spelled-out
number in all three scripts traces to its digest, including the large
ones that looked suspicious on first pass (`$1.799T`/`$1.775T` deficit
figures, Anthropic's `$190–200B`/`$2T`, Cerebras `$842M`). No invented
tickers. **Recommend continuing to the 2026-08-29 readout.**

One cosmetic regression: grok-4.6 verbalised `$1.799 trillion` as *"one
trillion seven hundred ninety-nine billion dollars"* (twice, Ep138). It is
correct but clumsy. Not worth a prompt edit on its own — note it for the
next A/B listen.

---

## P0 — the verified-alpha fix was half-applied, and the half was worse

Two functions feed alpha into the same prompt:

- `_build_portfolio_summary` → the Portfolio Performance block
- `_build_benchmark_block` → the "PORTFOLIO vs NASDAQ COMPOSITE (state
  every episode)" scoreboard

August 15 switched the first to the verified-window figure and left the
second on the blend. The model received two different alphas under two
labels and did what models do — it fused them:

| Episode | Spoken |
|---|---|
| Ep138 | *"plus nine point two eight percent across forty-five **verified-window** trades"* |
| Ep139 | *"plus nine point three percent across forty-five benchmarked trades"* |
| Ep140 | *"minus one point nine percent across ten verified-window trades"* ✅ |

Ep138 is the worst outcome available: **the inflated number wearing the
honest label.** Before the pass the show quoted a wrong number under a
neutral name; after it, one episode quoted the wrong number under a name
that asserts it had been verified.

The lesson is not "the fix was wrong" — it is that **fixing one of two
call sites is worse than fixing neither**, because the label and the value
can then travel separately.

Also fixed in the same block: the major-index sweep read `benchmark_scores`,
where the NASDAQ leg fell back to `nasdaq_return_pct` (45 trades) while
S&P/TSX used `benchmark_returns` (10). It reported *"beating 1 of 3"* from
a 45-trade NASDAQ score sitting beside 10-trade peers — and printed
`+9.28%` two sentences after the corrected `-1.95%`. The July-18 `n>=5`
gate did not catch it because it checks each sample's **size**, not that
the legs share the same **trades**. All three legs now read the same
verified windows; the sweep reads *beating 0 of 3*.

---

## The realignment script would have corrupted the record

`scripts/recompute_mit_benchmarks.py --apply` has been the show's
top-billed operator item since 2026-07-03, and the August 15 review called
it "the highest-value action on this show." **That recommendation was
wrong, and this pass caught it before it was acted on.**

Market data is reachable from the pipeline environment via plain
`requests` (only yfinance's bundled `curl_cffi` transport fails), so the
dry run could finally be executed. It flagged **25 trades as
hindsight-backdated — including all ten whose entry bars were already
correct**:

```
Ep135 X.TO   recorded 2026-08-12 (= pick date)  →  proposed 2026-08-04
Ep130 MU     recorded 2026-08-07 (= pick date)  →  proposed 2026-07-31
```

Cause: the script fetches bars from **ten days before the pick** to
tolerate date skew, and `_match_bar` returned the **first** bar whose price
fell inside the ±2% tolerance while scanning that window forward. For any
stock in a tight range an earlier bar qualifies — so the repair tool
re-created the precise hindsight backdating it was written to remove.

Fixed: entries are confined to bars on or after the pick date, exits to
bars on or after the entry, and among qualifying bars the **closest** price
wins rather than the first. Re-run against live data, the script now
reports **0 backdated entries** (was 25) and reproduces 8 of the 10
known-good windows exactly — the validation that matters, since those ten
were written by the trusted code path.

### What the corrected realignment says

| | Trades | Alpha vs NASDAQ |
|---|---:|---:|
| Currently on air (verified subset) | 10 | −1.95% |
| **After correct realignment** | **42** | **−3.35%** |
| Blended figure the show used to quote | 45 | +9.28% |

Beating **1 of 3** major indices (TSX only; NASDAQ −3.35%, S&P −0.57%,
TSX +4.58%).

**Eight trades cannot be reconciled to market data at all** — their
recorded prices match no bar within ±2%:

```
Ep5  SOFI  -7.49%   Ep10 TSLA  -1.44%   Ep17 SSRM  -4.21%   Ep35 AMD  +13.36%
Ep41 ACM  -11.35%   Ep50 CNR   +8.66%   Ep55 DLTR +20.11%   Ep81 MDA  -11.80%
```

That list contains the record's **best trade (+20.11% DLTR), its
second-best (+13.36% AMD), and its worst (−11.80% MDA)** — the extremes of
the published track record are exactly the trades that cannot be verified.
Ep50 CNR is the already-documented wrong-instrument case, which confirms
the class is real rather than a tolerance artifact.

**`--apply` was NOT run.** It rewrites the show's published performance
numbers, which is an outward-facing, hard-to-reverse change and the
operator's call. The tooling is now correct and the dry run is
reproducible.

---

## So: is the show beating the NASDAQ?

**No — and honestly, it does not yet have enough evidence to claim
either way.**

On the 10 verified trades: mean per-trade alpha **−0.17%**, median
−0.22%, beating the benchmark in 4 of 10, t = −0.20. That is
indistinguishable from zero. After the corrected realignment the sample
grows to 42 and the estimate is −3.35% — still no demonstrated edge, but
now measured on a sample big enough to start being informative.

Two things stand out as fixable causes rather than bad luck:

**Confidence is a dead field.** Across all 50 closed trades: 48 are
"Medium", 2 are "Low", **zero are "High"**. The digest prompt asks for a
confidence rating, the model emits a constant, and every downstream
consumer treats it as signal. A field that never varies cannot inform
sizing, selection, or the rule scoreboard. Either it earns its place —
with the prompt requiring calibration against the trade's actual setup —
or it should stop being presented as information.

**Hold windows are an artifact, not a decision.** Verified holds ran 0–6
days (median 3) against picks written to a five-day thesis, because exits
are pinned to the Friday pre-market run, which prices Thursday's bar. The
alpha attributed to "the pick" is really the alpha of a pick plus an
arbitrary exit date. Until the exit is a decision — a fixed five bars from
entry, or a stated rule — per-trade alpha is measuring two things at once.

Neither is a strategy change; both are measurement-integrity changes, and
they are the prerequisite for any strategy work being legible.

---

## Recommendations, in order

1. **Adjudicate the 8 unreconciled trades**, then run the corrected
   `--apply`. This is the real path to an honest n=42 baseline. The script
   is now safe; it was not on August 15.
2. **Decide the exit rule.** Fixed five bars from entry is the option that
   matches what the picks are written against.
3. **Make confidence mean something, or drop it.**
4. **A/B-listen Ep141+** — the alpha the show speaks changes again with
   this pass (both blocks now agree), and grok-4.6 is still new.
5. Carried: the significance-qualifier accept-or-abandon; SnapTrade
   Phase-0; the closing-price lesson retirement.

## Still open, deliberately not changed

Article volume remains at ~30–67 against a long-run median of 274, and the
new decay alarm fires on every episode — correctly. Three feeds were
replaced on August 15 (one of them, Yahoo Finance, was then removed by the
repo's own blocked-source check — a reachability probe cannot see an
editorial ban, which is a good lesson about probing the wrong axis). But
source **count** does not track article volume: Ep139 cited 8 sources from
30 articles while Ep138 cited 3 from 67. Since the mechanism is not
understood, no fetch-config change was made on a guess. The alarm is doing
its job; the next pass should read it with more episodes.
