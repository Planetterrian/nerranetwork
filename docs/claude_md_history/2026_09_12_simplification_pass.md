# Simplification pass — one generation, enforcement everywhere, audience first (Sep 12 – Sep 17, 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Simplification pass — one generation, enforcement everywhere, audience first (Sep 12, 2026)

Operator brief: the pipeline had become convoluted and costly and its
episodes were not trustworthy by construction; keep every show and every
cadence, do 1 (stop adding gates), 2 (claims enforcement on all shows),
4 (collapse digest + script into one generation) and 5 (audience as the
headline number). Plan + evidence:
[`docs/reviews/simplification_plan_2026_09_12.md`](docs/reviews/simplification_plan_2026_09_12.md);
experiments `combined-generation-2026-09-12`,
`source-integrity-strip-network-2026-09-12`,
`audience-headline-2026-09-12`; ledger `network` 2026-09-12. Drift
guards: `tests/test_simplification_2026_09_12.py`. Rules that bind:

- **The digest and the script are written in ONE model call**
  (`llm.combined_generation`, network default in `_defaults.yaml`; the
  Russian shows pin it off; narrative, dialogue, `podcast_model`-override
  and episode-1 runs stay two-pass by code — chained shows became
  eligible on Sep 17, see below).
  run_show renders the podcast prompt BEFORE the digest call through
  `engine.pipeline.build_podcast_template_vars` (extracted from
  `run_generation_phase`, which still calls it) with PART-1 placeholders
  for `{digest}` and `{hook}`; `generate_digest` appends it as PART 2
  after a fixed marker line, splits every response at the marker BEFORE
  any digest validation or post-processing, and stashes the script
  paired with the digest it was written from. `run_generation_phase`
  ships the stashed script only when the current digest still derives
  from that digest (a REPLACEMENT regeneration fails the line test —
  `combined_script_matches_digest`); a missing marker, a refusal-shaped
  or under-band PART 2, or a stale stash runs the script call exactly as
  before. Metric `combined_generation` = `combined` | `two_pass` |
  `combined_stale`. Output budget = `max_tokens + podcast_max_tokens`.
  **Sep 18 2026: the stash test compares normalised SENTENCES, never
  raw lines** — run_show rewrites the tail of every item line after
  generation (`transform_daily_body` turns `Source: <url>` into
  `Source: [domain](url)`, the Google-News resolver swaps the url), so
  on the first flagship slate Tesla Ep609 / SpaceX Ep104 / PT Ep187
  discarded their combined scripts at ~50 % line survival with no
  regeneration behind it and paid for the script twice.
  `engine.generator._combined_units` drops links, URLs, Source tails,
  markdown and punctuation; a trim, strip or link rewrite scores ~1.0
  on today's real digests and yesterday's digest against today's
  scores 0.0–0.02 (`TestStashSurvivesRunShowTrims`).
  **A combined run can never cost an episode; the first live slate is
  the A/B-listen set (landmine #17).** Revert = one line in
  `_defaults.yaml`.
- **Source integrity is enforced on every show** — see the Provenance
  section at the top of this file for the strip contract.
- **The audience headline leads every surface a decision is made from.**
  `scripts/build_audience_headline.py` → `api/audience_headline.json`
  (nightly, committed): per show and network — RSS downloads 7d/30d,
  the LAST COMPLETE week vs the week before (`wow_pct`; the current OP3
  week is partial and never compared), median first-week downloads per
  episode (episodes 7–30 days old; OP3 lists only a show's top episodes,
  so the network view names the carrying shows), views-weighted YouTube
  `averageViewPercentage` over 28 days by kind, newsletter subscribers.
  Null where unmeasured, never 0. It is the dashboard's FIRST tile, the
  review snapshot's FIRST section, and the second line of the daily
  summary. A review scores prompt passes against it first; the 99
  per-episode script metrics are diagnostics.
- **Nothing was pruned from the metrics file**: every unread key is
  recorded inside a retired branch or read by a human; deleting them
  changes nothing a listener gets. A NEW metric names its consumer.
- **Sep 17 2026 — first slate, scored** (review:
  [`docs/reviews/network_review_2026_09_17.md`](docs/reviews/network_review_2026_09_17.md);
  guards `tests/test_network_review_2026_09_17.py`). 100/100 runs, 0
  episodes lost, no placeholder leakage — and combined generation on
  5 of 56 episodes, because `podcast_chain: true` (every flagship) was
  an exclusion. **A chained show is eligible now**; the chain runs only
  on the fallback script call. The five combined episodes kept coverage
  (72–84 %) but read PART 1 aloud (38–59 % verbatim), so the bridge says
  "PART 2 is not PART 1 with the markdown removed" and asks the script to
  name each section once (chapters had collapsed to four on PT 12/15 and
  MIT 13/16). Strip mode removed 1–3 TRUE sentences a day on
  Planetterrian — X posts and 403 journals — while the fetch stage held
  the text: **claims verify against the fetched copy first**
  (`engine.claims.build_local_texts`, `via: fetched_copy`, metric
  `source_integrity_verified_from_fetched`), HTTP only for a quote the
  copy lacks; the committed sidecar now records `stripped_sentences`
  (it had shown the post-strip ledger as "claims=0, passed"). Not a
  length lever: the under-target week (Tesla 56 %, PT skipped at 858 w)
  is the digest-ceiling class, and the combined path's first flagship
  week is its measurement.
- **Sep 17 2026, same day — main had been red for eleven runs.** The
  merge of that review was the first the operator could not trust CI
  on: the test workflow had failed on every push since Sep 16 (seven
  Voices / co-host assertions pinned code other sessions had moved on
  from; the SpaceX caption replay, the promo-cut sweep and the UC
  runway guard are data-driven and all tripped). The fixes are the
  three commits before the review's follow-up merge (captions HOLD a
  short segment, the YouTube call-out anchors a promo cut, the restock
  falls back off grok-4.6 — each noted in its own section above);
  §6 of the review doc is the record. Two things it adds: **the
  grok-4.6 restock arm was never exercised in the window it was read
  out on** (no queue needed topics Aug 19 – Sep 7; every needed run
  since failed, nine in a row — the register entry carries the
  correction, and the run summary's `model` field says whether the
  fallback is doing all the work), and UC was hand-restocked with three
  documented briefs (the June 2026 precedent) so the alarm clears
  while the automation refills. **Check the `Run Tests` conclusion on
  main before reading a merge as checked.**
