# Simplification plan — trust, one generation, audience-first (Sep 12, 2026)

Operator brief (Sep 12): "the codebase, pipeline and process is getting
convoluted and inefficient … is this actually making better podcasts and
blogs with high quality content that people can trust?" The Sep 9
assessment answered: partly true. This plan executes the four items the
operator chose from it, keeping every show and every cadence:

1. **Stop adding gates; remove the ones that no longer change decisions.**
2. **Source-integrity enforcement on every show**, not only the two
   narrative shows — without losing episodes.
3. *(not chosen — show count and cadence stay as they are)*
4. **One generation** for the digest and the script, so the script stops
   being a lossy rewrite of the digest.
5. **Audience retention as the headline number** on every surface a
   decision is made from.

## Why the two-pass design cannot be patched into shape

The rewrite gate's own numbers, Sep 9–12, nine gated shows, four days:

| outcome | count |
|---|---|
| gate fired | 30 of 35 episodes |
| rewrite accepted | 11 |
| rejected — `facts_lost` (rewrite told ≥15 points less of the digest) | 9 |
| rejected — `names_lost` / `still_copies` / `copies_more` | 8 |
| no fire (draft under 40% verbatim) | 5 |

The draft copies the digest (55–77% verbatim on Sep 12) and tells 85–97%
of it; the rewrite writes fresh (1–4% verbatim) and tells 40–60% of it.
The gate can pick one or the other; it cannot get both, because the
script stage is asked to re-tell a finished document. Every patch since
Sep 5 (overlap threshold, section test, hook test, names guard, coverage
guard, bounded attempts) moved the tension, never resolved it. That is
the convolution the operator sees, and it is structural.

## Phase A — remove the rewrite gate; keep the instrument

- Delete `engine.pipeline._script_rewrite_gate` and its helpers
  (`_rewrite_gate_floor_words`, `_rewrite_gate_attempts`, the three
  `REWRITE_GATE_*` constants), the `llm.script_rewrite_gate_overlap_pct`
  and `llm.script_rewrite_gate_attempts` config fields, the nine
  per-show YAML lines, and the `script_rewrite_gate_*` metrics.
- Keep `engine/script_audit.py` as the READ-ONLY instrument: overlap,
  coverage, names, filler, sections, hook. The snapshot table and the
  per-episode metrics stay. A rule that changes a script belongs in the
  prompt or in the generation design, never in a retry.
- The 36 per-episode metric keys with no code consumer are NOT deleted:
  inspection showed each is recorded only inside a retired branch
  (section TTS, the debut song) or read by a human in the metrics file.
  Deleting them changes nothing a listener gets and costs a diff; the
  rule going forward is that a new metric names its consumer.

## Phase B — one generation per episode

`llm.combined_generation: true` (network default for the news shows;
narrative, dialogue and Russian shows stay two-pass — their podcast
prompts are a different shape and were never the copying problem).

- The digest call's prompt gains a PART 2: the show's podcast prompt,
  rendered with `{digest}` = "the digest you wrote in PART 1" and
  `{hook}` = "the HOOK sentence from PART 1", separated by a fixed
  marker line. One model call writes the written record (blog, RSS,
  newsletter, memory, claims ledger) and the spoken script from the same
  facts at the same moment, so nothing is lost between them.
- `generate_digest` splits the response at the marker BEFORE any digest
  post-processing (the duplicate-story stripper must never see the
  script), runs the digest half through the unchanged chain, sanitises
  the script half and stashes it. `run_generation_phase` uses the stashed
  script and skips the script call. Output budget = digest + script
  tokens; the existing 1.5× truncation retry covers the long tail.
- Fallback is the two-pass path, automatically: no marker in the
  response, a script under the floor, or any REPLACEMENT regeneration of
  the digest (validation regen, slow-news regen, structural regen) drops
  the stashed script and the legacy script call runs. Mutations that
  only trim the digest (cross-section dedupe, scaffold scrub) keep it.
  Metric `combined_generation` records which path shipped.
- The podcast template variables that used to be built after the digest
  are built before it (`build_podcast_template_vars`), from the same
  inputs; on episode 1 the hook-dependent intro falls back to two-pass.

Expected effect: overlap stays measured; coverage returns to the 80–95%
the copied scripts had, in spoken register, with one fewer LLM call per
episode instead of one more.

## Phase C — source integrity enforced everywhere, without losing episodes

Shadow-mode data for the news shows, last seven episodes each: enforcing
as-is would have blocked SpaceX 2/7, Tesla 2/7, FF 4/7, PT 4/7, MIT 1/7,
and none of those were proven fabrications — malformed ledger entries
(the model omitted the quote), a single citation-shaped sentence on an
episode with an empty ledger, or a 403 from the publisher. Blocking the
episode for those is the wrong tool on a daily news show.

- New `source_integrity.on_failure: block | strip` (default `block`, the
  UC/FPD contract untouched). Network default: `enforce: true`,
  `on_failure: strip`.
- Strip mode, after the one repair pass: an uncovered citation-shaped
  sentence whose enclosing digest item carries a Source URL that resolves
  counts as sourced by the item; every remaining failure — a claim whose
  source could not be verified or reached, a malformed entry, an
  uncovered shape with no resolving item source, a reviewer note — has
  its sentence REMOVED from the digest (a whole item goes when it loses
  its body). The gate re-runs mechanically on the stripped text; if it
  still fails, the episode blocks exactly as today. Nothing unverified
  reaches the blog, the feed or the newsletter, and the day is not lost.
- The script is stripped in step: every script sentence that tells a
  removed digest sentence goes too, and the script-stage citation lint
  strips the invented sentence instead of exiting. Metrics:
  `source_integrity_stripped_sentences`, `_script_stripped_sentences`,
  `_covered_by_item_source`.

## Phase D — audience is the headline number

- `scripts/build_audience_headline.py` (nightly) → `api/audience_headline.json`:
  per show weekly RSS downloads (last four weeks), week-over-week
  change, first-week downloads per episode, YouTube average view
  percentage over the window, newsletter subscribers, and a network
  roll-up. Null where unmeasured, never zero.
- The management dashboard's first tile row leads with it; the review
  snapshot's first section is the audience headline (a review starts
  from the audience, then the pipeline); the daily summary line carries
  the network week-over-week figure.
- Script metrics stay diagnostics. The experiment register's readouts
  for the September passes are scored against the headline first.

## What this pass does NOT do

- Change show count or cadence (operator decision, kept as-is).
- Touch audio settings, voices, or music (landmine #17).
- Change the blog, RSS or newsletter renderers — they read the same
  digest they always did; the digest is now written in one pass with the
  script, and unverified sentences no longer reach it.

## Verification

- Unit tests for the combined split + fallback, the strip-mode gate, the
  audience builder, and the removal of the gate.
- No LLM key is available in this session, so the first live combined
  generation is the next scheduled slate. The fallback path is the
  two-pass pipeline that ran today; the `combined_generation` metric and
  the density audit on the first slate are the readout.
