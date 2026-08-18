# Network LLM usage review — Grok, Grok Voice, Grok Imagine (2026-08-18)

Operator ask: review the network's full LLM usage and determine whether
recent xAI updates (Grok text models, Grok Voice, Grok Imagine) warrant
changes — keep improving all shows, control costs, high-value changes
only.

Method: full call-site inventory (every model id, pricing table, and
config knob in the repo), reconciled against xAI's August 2026 product
state (releases, retirements, pricing), reconciled against the
committed spend data (`api/dashboard.json` cost rollup + per-episode
`credit_usage_*.json` files). Everything proposed here respects the
review-playbook rails: the `do_not_retry` ledgers, landmine #17 (no
audio-affecting change without operator A/B), and the experiments
register's no-stacking rule.

## Verdict in one paragraph

The network's model strategy is fundamentally sound and mostly already
current: digests/fetch on grok-4.3 (the facts-first floor), the
script-stage `podcast_model` knob already A/B-ing grok-4.5 (dp_pod,
readout 08-24) and grok-4.6 (modern_investing, readout 08-29), TTS GA
pricing ($15/M chars) already in the tracking table, and Grok Imagine on
the non-retired $0.02 base model. **No model upgrades are warranted
today** — the two in-flight A/Bs are exactly the right probes and their
readouts land within two weeks. What the review DID find is three
silent-number/silent-drift failures in the accounting and pinning layer
(fixed in this PR), which is the same failure class the Aug 15 MIT pass
warned about: loops on numbers fail silently.

## Current usage map (condensed)

| Stage | Model | Price (in/out per 1M) | Notes |
|---|---|---|---|
| Fetch (x_search/web_search), digest, X thread, synth, titles, restock | `grok-4.3` | $1.25 / $2.50 | Network default; deliberate facts-first floor |
| Podcast script | `grok-4.3` default; `grok-4.5` (dp_pod), `grok-4.6` (MIT) | $2 / $6 for 4.5/4.6 | Two A/Bs reading — readouts 08-24 / 08-29 |
| Refusal fallback | `grok-4.20-reasoning` (tesla/MIT: `-non-reasoning`) | $2 / $6 | Still live at xAI (not in the May-15 retirement) |
| Episode quality reviewer | ~~`grok-4-1-fast-non-reasoning`~~ → `grok-4.3` (this pass) | was costed $0.20/$0.50; actually billed $1.25/$2.50 | Slug retired 2026-05-15; see fix #2 |
| Multilingual translation | ~~`grok-latest`~~ → pinned `grok-4.6` (this pass) | costed at 4.3 rates; actually 4.5/4.6 | See fix #3 |
| Scheduled review agent | `grok-4.5` (`REVIEW_MODEL` env) | ~$0.75/run, 2/wk | Analysis-only, operator-gated — fine |
| TTS (all 16 shows) | Grok TTS, no model param | $15/M chars (GA; tracking already correct) | Voices: `kdif6sqjcyiq`, Olya `0b875ae2`, Dan `0vscf8u8yrxc`, `ara` |
| Images | `grok-imagine-image` | $0.02/image (~5–8/ep) | NOT the retired `-pro` slug — no change needed |
| Video | `grok-imagine-video` | dormant (`video_provider: null`) | Stays off |

Tracked spend, last 30d (dashboard, 2026-08-18): **$92.49 across 557
episodes** — grok $15.59 (17%), TTS $38.63 (42%), images+search ≈ $38.27
(41%, previously invisible as a category — see fix #4).

## What changed at xAI since the July 31 model review

1. **grok-4.6 shipped 2026-08-12** ($2/$6, 500K context, agent/visual
   focus). Factuality evidence is MIXED: it improves on grok-4.5's
   AA-Omniscience hallucination profile but posts a worse model-card
   factuality-hallucination rate (1.70% vs 4.5's 0.98%). It does not
   overturn the July-31 "digests stay on 4.3" decision — the
   confident-hallucination regression that disqualified 4.5 is
   *unmeasured* for 4.6, not disproven, and 4.6 costs 2.4× on output.
   The MIT script-stage A/B is the correct instrument; its readout
   (08-29) is the decision point.
2. **May 15 model retirement**: 8 slugs retired, all silently
   redirecting (`grok-4-1-fast-*` → grok-4.3, `grok-imagine-image-pro`
   → `-quality`) **at the redirect target's billing**. The episode
   reviewer was on a retired slug (fix #2). No grok-4.20-family model
   was retired, so both refusal fallbacks remain live — but the 4.20
   family is now two generations back; watch item.
3. **Grok TTS GA pricing $15/M chars** (the April $4.20 was launch-era).
   `engine/tracking.py` already carries $15 — verified correct, no
   change. TTS is now the single largest tracked category (42%).
4. **Grok Voice July 6 update**: 21 natively-multilingual flagship
   voices, cloning from 120s of reference, expanded speech tags. The
   TTS request carries **no model/version parameter**, so voice-stack
   improvements (and regressions) arrive server-side automatically —
   the network benefits from quality updates for free, and also cannot
   pin against them. Nothing to adopt now (see "deliberately not
   done").
5. **Search-tool billing moved from per-source ($25/1k sources) to
   per-call ($5/1k calls)**, and the usage object stopped reporting
   source counts — which zeroed the repo's search accounting (fix #1).
6. **Grok Imagine video 1.5** (1080p, $0.05/s ≈ $3/min). Irrelevant to
   current strategy: the Shorts motion A/B was formally ended as
   unreadable (2026-08-14) and stills are the network default.

## Fixes shipped in this pass

All are accounting/pinning corrections — none changes what a listener
hears today. Drift guards: `tests/test_llm_usage_pass.py` plus updated
`tests/test_cost_efficiency_pass.py` / `tests/test_tracking.py`.

1. **Search spend billed per call** (`engine/tracking.py`). Every one
   of the 136 credit files written since the July-29 search accounting
   shipped records `sources: 0` — the per-source term multiplied by
   zero on every episode while the real per-call fee went untracked
   (782 calls in August alone ≈ $3.91 untracked in 18 days, ~$6–7/mo).
   `record_search_usage` now bills `calls × SEARCH_COST_PER_CALL`
   ($0.005, env `XAI_SEARCH_COST_PER_CALL`) and keeps the per-source
   term for any future source-count reporting (currently always 0, so
   no double count).
2. **Episode quality reviewer pinned to `grok-4.3`**
   (`shows/_defaults.yaml`, `engine/config.py`, `review_episodes.py`).
   The configured `grok-4-1-fast-non-reasoning` was retired 2026-05-15;
   since then xAI has silently served grok-4.3 (reasoning effort
   `none`) and billed grok-4.3 rates while the tracker priced the
   retired model — a ~6× under-count (~$2/mo scale, but the model
   name in every config and credit file was wrong). The pin changes
   nothing served: the reviewer call passes `reasoning_effort: "none"`
   explicitly for parity with the redirect. Retired-slug pricing rows
   stay in `GROK_PRICING` only for historical file re-scoring.
3. **Translation stage pinned off the floating `grok-latest` alias**
   (`engine/translate.py`, `engine/multilingual.py`). The multilingual
   dub translations rode `grok-latest`, meaning every xAI flagship
   release silently changed shipped dub audio (4.5 on 07-08, 4.6 on
   08-12 — the 'Grog 4.6'-era brand garbles fixed on 08-15 happened on
   a model this repo never chose) with no experiment entry, while
   `_estimate_track_cost` priced it at grok-4.3 rates regardless
   (~2.4× under-estimate at 4.6 rates). Now pinned to `grok-4.6` —
   what the alias resolves to today, so current behavior is frozen,
   not changed — env override `NERRA_TRANSLATION_MODEL`, and the cost
   estimate prices the actual pinned model. ⚠️ If the alias in fact
   still resolved to 4.5, this pin is a (small) translation change —
   listen-check the first post-merge dub track per landmine #17.
   Future translation model moves are now a deliberate edit + ledger
   entry, never a vendor release.
4. **Dashboard cost rollup breaks out images + search**
   (`scripts/generate_dashboard.py`). They were 41% of tracked 30-day
   spend but absorbed into `total` with no category — the "measure
   first" rule applied to the dashboard's own blind spot. Additive
   JSON keys (`images`, `search`) in `cost_rollup`; existing consumers
   unaffected.

## Deliberately NOT done (and why)

- **No digest/fetch model change.** grok-4.3 stays. 4.6's factuality
  is unproven for this network's failure mode and costs 2.4× on the
  stage that burns the most LLM tokens. Revisit ONLY with the MIT A/B
  readout (08-29) plus a digest-side factuality probe — never on
  benchmark vibes.
- **No new `podcast_model` experiments.** dp_pod (4.5) and MIT (4.6)
  read out 08-24/08-29. Starting more before those readouts violates
  the register's no-stacking rule. Decision tree after readout: if MIT
  4.6 hits on length with factuality intact, the next candidates are
  the shows with known script-stage tics (omni_view was the July-31
  suggestion) — one at a time, each with its own experiment entry.
- **No TTS/voice changes.** Speech-tag injection and phonetic
  respellings stay banned (`do_not_retry`, 100% regression rate on the
  custom voice). The July-6 natively-multilingual voices are the one
  genuinely interesting option — the FR/ES/ZH dub tracks currently
  re-voice with the English-trained clone — but the per-language OP3
  instrument and the @NerraFR decision (08-25) may cull those very
  languages within weeks. Sequencing: cull first, then (operator
  choice) A/B a multilingual flagship voice on ONE surviving non-EN
  language with a 3-context listen test. Do not invest in dub voice
  quality for languages that may be switched off.
- **No Imagine tier upgrade.** The $0.05 `image-quality` tier would
  2.5× image spend (~$38/mo category) on zero evidence that image
  fidelity binds retention — the gallery-retention flywheel
  (`api/gallery_retention.json`) is the instrument that would justify
  it; let it speak first. Video stays off.
- **No reasoning_effort tuning.** LLM tokens are 17% of tracked spend;
  the lever is small and the knob is already wired for a measured
  trial whenever a stage needs it.
- **No multi-vendor hedge.** Single-vendor risk (flagged in
  `docs/llm_model_audit.md`) is real but the mitigation — the
  ElevenLabs rollback path + env-overridable model pins — is
  proportionate for a ~$100/mo operation.

## Watch list

- **08-24 / 08-25 / 08-29** — dp_pod 4.5 readout, FR-channel decision,
  MIT 4.6 readout + verified-alpha decision. The next model moves hang
  off these three dates; nothing model-related should ship before them.
- **grok-4.20 family retirement risk** — both refusal fallbacks live
  there. When xAI announces the next retirement wave, repoint
  `fallback_model` to a then-current non-4.3 snapshot (the fallback's
  job is a genuinely different model, not a specific vintage).
- **TTS server-side drift** — with no model param to pin, a Grok Voice
  stack update could change every show's sound overnight. After any
  major xAI voice announcement, spot-listen one episode against the
  prior day's before assuming continuity.
- **Search/TTS rates** — both now env-overridable
  (`XAI_SEARCH_COST_PER_CALL`, `XAI_SEARCH_COST_PER_SOURCE`); if xAI
  moves pricing again the operator sets an env var rather than waiting
  on a code change.

## Cost impact of this pass

No new spend. Tracked totals will rise slightly (~$8–10/mo) because
previously-invisible real spend (search per-call fees, reviewer at true
grok-4.3 rates, translation at true 4.6 rates) is now counted — the
bill was already being paid; now the dashboard admits it.

---

## ADDENDUM — Operator override, same day (2026-08-18)

Hours after this review shipped its "no model upgrades" verdict, the
operator explicitly directed a **network-wide upgrade to grok-4.6** with
full awareness of the risks laid out above (the May-13 `<fast>` re-enable
precedent: operator override, documented as such, engineered to be safe).
This addendum records what shipped and how the risk is instrumented.

**What moved** (experiment `network-grok-46-upgrade`, readout
2026-09-01): the network default `llm.model` (digest, fetch/search, X
thread, podcast script), `synth_model`, `reviewer_model`, the review
agent's `REVIEW_MODEL`, and the generator/xai_grok/titles code defaults —
all `grok-4.3` → `grok-4.6`. The refusal fallback repointed
`grok-4.20-reasoning` → `grok-4.3` (a genuinely different snapshot from
the new primary; retires the aging 4.20-family dependency this review had
flagged as a watch item). The dp_pod (`grok-4.5`) and MIT (`grok-4.6`)
`podcast_model` pins were removed — superseded/absorbed by the network
default; both experiment entries record the early end and what still gets
scored at their original readout dates. Translation was already pinned
4.6 by this review's fix #3.

**Cost**: ~+$22–25/mo (30d LLM token base re-priced: ~$25 → ~$47; the
reviewer adds ~$1.4). TTS/images/search unchanged. Network total moves
from ~$110–125 to ~$135–150/mo.

**Risk instrumentation** (this is the part that makes the override an
experiment rather than a bet):

- **Revert is one line** — `model: grok-4.3` in `shows/_defaults.yaml`
  (code defaults follow config; nothing else needs touching same-day).
- **MIT is the tripwire show**: any invented number/ticker/price in a
  script is an immediate revert (rule carried forward from
  `mit-script-model-46`).
- **The episode reviewer's `FACTUAL_ERRORS` flag rate** is the
  network-wide readout metric — it runs on every episode via the daily
  audit; compare post-upgrade rate against the pre-08-18 baseline at
  readout.
- **Fetch verification**: grok-4.6 supports function calling, but the
  first post-merge runs should confirm the server-side `x_search` /
  `web_search` tools behave on 4.6 (a failure is loud — fetch errors
  surface in the run logs, and the refusal fallback path is 4.3).
- **Landmine #17**: every script's prose changes with this merge —
  A/B-listen the first post-merge episode on 2–3 shows (suggested:
  tesla, MIT, dp_pod — dp_pod also just lost its 4.5 pin).

**What this supersedes**: the July-31 "digests stay on 4.3" decision and
this review's own "wait for the readouts" recommendation — both by
explicit operator direction, recorded here and in the network ledger so
the next review scores the outcome instead of relitigating the decision.
