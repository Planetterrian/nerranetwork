# Modern Investing — Review 2026-07-24 (operator-directed, out of rotation)

Operator request: review the latest episodes, **how sources are referenced**,
the **performance review of individual picks**, and **overall performance
reporting** — "all of those items have had recent issues." All four concerns
verified real. Method per `.claude/commands/review-show.md`; numbers from
`scripts/review_snapshot.py modern_investing` (2026-07-24) and the raw
episode/tracker files.

## Scoring the 2026-07-18 predictions (ledger updated)

| Prediction | Verdict | Evidence |
|---|---|---|
| ≥1 Monday weekly pick/week under regime v2; no >7-day drought while SELECTIVE RESET reachable | **partial** | The escape valve worked — a weekly pick resumed 2026-07-21, three days after v2 merged (drought had reached 11 days, mostly pre-fix). But it landed on **Tuesday**, not Monday (Mon 07-20 was an explicit no-trade), and the pick itself was lost to the extraction bug below. |
| 0 new one-bar weekly holds | **pending** | No weekly hold closed in the window (the only new pick was voided — see P0-1). |
| Inline significance caveat in ≥70% of alpha mentions | **miss** (second miss on this metric) | Post-merge mentions: Ep111 0/1, Ep112 1/2, Ep113 0/1, Ep114 0/2 → **1/6 ≈ 17%**. Even riding the data line as an em-dash instruction, the model strips it. Third mechanism shipped (below); a third miss should go to the operator as an accept-or-abandon decision. |

## P0 — record integrity: the extractor can't parse the symbols the digest now emits

The July 3 pass taught the **digest** to emit exchange-native symbols
(`CNR.TO`, `BTC-USD`). The **extractor** still only accepted bare
`[A-Z]{1,5}` (`shows/hooks/modern_investing.py:2633`). Both recent picks hit
this within three days:

- **Ep111 (Sun 07-19): the spoken pick was never recorded.** The digest
  (and the aired episode — "Today's practice investment is a weekly hold on
  CNR… Canadian National Railway") picked `CNR.TO`. The extraction regexes
  choke on the `.` and returned None; the trade signal shipped
  `no_trade / no_pick_extracted`. Listeners heard a pick that does not
  exist in the tracker, the signal, or the shadow ledger.
- **Ep113 (Tue 07-21): the wrong instrument reached the execution layer.**
  `**Today's Pick:** BTC-USD — Bitcoin` was truncated to `BTC`;
  `**Market:** Crypto` fell through the market regex (`TSX|NYSE|NASDAQ|TSX-V`)
  to UNKNOWN; `_probe_pick` then **validated** bare `BTC` — an unrelated
  equity at **$28.80** — while the narrated stop was **$64,500** (Bitcoin
  levels; stop 2,240× the reference, and *above* entry, violating the
  July-4 stop invariant on shipped state). The signal routed an equity BUY
  to Webull with `pick_validated: true`, and the **shadow executor
  would_place'd $1,000 of the wrong instrument at $29.62**
  (`shadow_ledger.json`, 2026-07-21). Had the live layer been armed, real
  money would have bought the wrong asset. The trade sat open and was on
  course to be **closed against the wrong instrument at today's (Fri 07-24)
  evaluation**.

**Shipped (deterministic, no A/B):**
- Extraction accepts suffixed/hyphenated symbols (`CNR.TO`, `BTC-USD`,
  `ABC.V`); market regex gains `CRYPTO` and fixes a latent alternation bug
  (`TSX|…|TSX-V` could never match TSX-V).
- `_yf_symbol_candidates`: pre-suffixed symbols pass through verbatim;
  `CRYPTO` market forces the `-USD` Yahoo pair with **no bare fallback**
  (bare "BTC" is an equity — the exact trap).
- **Wrong-instrument tripwire**: a narrated stop outside `[ref/3, ref×3]`
  of the resolved listing's price voids the pick at record time
  (`instrument_scale_mismatch`), writes an explicit no-trade signal
  (`override_reason`), and a self-healing migration voids any
  already-recorded trade in that state — the committed tracker is migrated
  in this PR (Ep113 BTC → voided; nothing else changed).
- **Void transparency**: when a pick the show announced on air is voided,
  the next episode's trade-review block instructs one plain-spoken
  correction ("tracking error, not a market outcome, excluded from
  totals"), stamped so it is said exactly once.

**Not done (deliberate):** retro-recording the lost Ep111 CNR.TO pick or
re-opening Ep113 as `BTC-USD` — both would price entries with the benefit
of a known 3–5-day price path, the hindsight class the July 3 pass
eliminated. The record honestly shows: one lost pick (documented), one
voided pick (disclosed on air).

## P0 — sources: Ep115 shipped with a collapsed source pool

`metrics_ep115.json`: **9 articles fetched** vs 222–337 on the four prior
days (fetch stage "succeeded"; Tesla/PT/M&A were normal that day, Omni View
also degraded — likely a shared Google-News throttle). Consequences in the
shipped digest: **6/6 `Source:` citations are x.com posts** (unusual_whales
×3 — one URL cited twice, violating the prompt's own one-URL-once and
2-per-publication rules), portfolio "Action:" advice hung off second-hand
X commentary, and the episode ran thin (1,346 words). Nothing surfaced
because 9 > `min_articles_skip` (3).

**Shipped:**
- **Source-collapse alarm** (`run_show.py`, all shows): when today's
  article count falls below 25% of the show's own recent median (median
  ≥40, ≥5 samples), the run records `article_count_degraded` and emits a
  GitHub `::warning::`. Log-only — never blocks (house fail-loud pattern).
- **Prompt (⚠️ A/B)**: x.com counts as ONE publication for the 2-max rule;
  publisher citation preferred when both exist; x.com acceptable as a
  Source only when the post is the primary source; thin days must prefer
  fewer/deeper sections over stretching X posts across the template.
- **Prompt (⚠️ A/B)**: the Tools & Techniques header template contained a
  literal scaffold typo — `**[Tool/Technique Name]: Source**` — which
  Ep115 rendered verbatim as "**OptionsPlay IV Color-Coding Tool:** Source"
  on the blog. Header fixed to `**[Tool/Technique Name]**`.
- **Prompt (⚠️ A/B)**: the Today's Pick template carried its instruction
  *inside the value slot* — Ep111 echoed "(only for new picks on Monday or
  Flash Trades)" verbatim after the company name. Instructions moved to
  their own rules lines; the Market menu gains TSX-V/Crypto; ticker format
  (bare US / `.TO` / `.V` / `-USD`) is now stated explicitly, aligned with
  the extractor.

## P1 — performance reporting

- **Significance caveat (second miss, third mechanism).** The alpha is
  quoted in most episodes at t=0.31 with no qualifier. The caveat is now a
  **data-shaped parenthetical fused to the value** — the block renders
  `alpha +6.59% (early, not yet statistically significant, t=+0.31)` — so
  quoting the number without the qualifier requires actively editing the
  statistic, plus one short "the parenthetical is part of the statistic"
  note. ⚠️ A/B. If this misses a third time, stop prompt-side attempts and
  put the accept/abandon call to the operator.
- **Chronic under-length, attacked at the sanctioned substrate.** 10/10
  recent scripts run 1,158–1,746w against the 1,800 floor (median ~1,382).
  Podcast-side levers are ledger-banned network-wide; MIT never opted into
  the digest-stage lever. Shipped: `digest_expand_below_target: true`,
  `min_digest_words: 1500` (FPD/OV precedent). ⚠️ A/B when the retry fires.
- Carried operator items: `scripts/recompute_mit_benchmarks.py --apply`
  still not run (current +6.59% matched alpha retains old-window inflation);
  SnapTrade Phase-0 verification; closing-price lesson-family retirement.

## P1 — pick-performance review cadence

"No newly closed trade since the last review" ran in **9/10** episodes.
Root causes, in order: the regime-v1 deadlock (fixed 07-18), then the two
extraction losses above (the only post-fix pick never became a priceable
trade). With extraction fixed, the weekly cadence (pick → mid-week
snapshots → Friday close → review) can resume; no additional lever shipped
here — measured by the predictions below.

## P2 / deferred

- **Ep31 "BTC" flash trade (April, closed +0.42% at $33.67)** is the same
  wrong-instrument class historically (labeled a macro/crypto play, priced
  as an equity). No stop was recorded, so the tripwire can't catch it
  mechanically — adjudicate via the recompute script's wrong-instrument
  report (operator, carried).
- Shadow-executor cron delay (runs 15:04–16:48 UTC vs the 13:50 slot) —
  carried (landmine #24 class).
- The Ep111 lost pick cannot be disclosed automatically (it was never
  recorded); if the operator wants an on-air acknowledgment, it's a
  one-line note for the next episode.

## Verification

- `tests/test_mit_benchmark_integrity.py` +18 new drift guards
  (suffixed-symbol extraction incl. the exact shipped Ep111/Ep113 lines,
  crypto candidate resolution, scale-mismatch tripwire + migration, void
  disclosure once-only, data-shaped caveat, collapse-alarm source pin,
  YAML lever pin); 2 stale July-18 caveat guards updated to the new
  contract. Full MIT suites: **136 passed**. Smoke suites
  (`test_prompt_fidelity`, `test_generator`, `test_snaptrade_execution`,
  `test_config`, `test_episode_validity`, `test_dashboard_mit_section`,
  `test_schedule`): **260 passed**.
- `GROK_API_KEY` unset in this environment — the digest-prompt changes
  were not exercised live; `test_prompt_fidelity` confirms they render.
  Operator: the first post-merge episode is the A/B set.
- Time-sensitive note: merging **before the next 08:16 UTC run** prevents
  the voided-BTC state from being re-evaluated with stale code; if a run
  lands first and closes "BTC" wrongly, the shipped migration voids that
  close on the next load — either order self-heals.
