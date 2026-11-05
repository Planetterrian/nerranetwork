# CLAUDE.md — Tesla Shorts Time Podcast Network

A pass adds at most ten lines here (the rules that bind, the guard's name,
the link); its narrative goes to `docs/reviews/` or
`docs/claude_md_history/`. `tests/test_claude_md_size.py` enforces the size.
## Titles: one module owns every limit

**Never truncate a title outside `engine/titles.py`.** Import a limit and
`clip_words()` / `episode_title()` from it. A new surface adds its limit
to that module; it does not write its own slice.

This is not style preference. The same bug shipped three times
independently — `engine.blog` sliced `hook[:100]`,
`video_metadata._truncate` sliced `text[:max_len - 3]`, and `run_show`
built `f"Ep {n}: {hook}"` with no cap at all — and the consequence was
that **YouTube silently rewrote episode titles on every show in the
network** for months, cutting mid-word and emailing to say no action was
required. Current limits: YouTube 100, podcast RSS 100 (same on purpose,
YouTube ingests the feed), web `<title>` lead 62, newsletter subject 78.
`tests/test_titles.py` enforces the property against ~4,500 generated
hooks in English and Russian.

Full context, including the Search Console work, the verified state of
each subsystem and the traps found along the way:
[`docs/session_2026-07-28.md`](docs/session_2026-07-28.md).

## Funnel links: one module owns every campaign id

**Never build a `utm_*` link, campaign id, or capture tag for a
published surface outside `engine/funnel.py`.** Import
`episode_link()` / `campaign_id()` / `destination_for()` /
`capture_tags()`. A new surface adds itself to that module's closed
vocabularies; it does not hand-roll a query string.

Same shape as the titles rule, same cause. Three surfaces each invented
their own scheme and the result was that **nothing the network published
could be joined to anything it measured**: `video_metadata` wrote
`utm_campaign=ep45` with no show slug (every show's episode 45 became
one GA4 row), `ru_dub` linked the bare English homepage with no UTM at
all (@NerraRU — the network's HIGHEST-reach surface at ~25,800
views/30d — was invisible), and Buttondown captured one undifferentiated
`gallery-subscriber` tag. Four live analytics systems, no shared key, so
the July 18 2026 audit's central finding (world-class factory, funnel is
the product gap: 3,900 downloads/30d, 3 subscribers) could not be acted
on.

`campaign_id()` and `parse_campaign_id()` must stay exact inverses —
`scripts/build_funnel.py` attributes GA4 rows purely by parsing them, so
drift is SILENT (the report just goes to zero).
`tests/test_funnel.py` round-trips every generated shape and asserts
each real surface emits a parseable campaign.

Full context — the funnel report's honesty rules (null vs 0, the
30-denominator floor, `attribution_coverage_pct`), the RU SpaceX pilot,
and the Shorts motion A/B: [`docs/funnel.md`](docs/funnel.md).

## Provenance: one module owns the claim ledger

**A claim's provenance is DATA, not formatting — `engine/claims.py` owns
it.** Never add a new stripper for source/citation text without checking
the ledger path first. **Since Oct 1 2026 the gate's enforcement is the
STATUS and the public record, not removal**: `on_failure: flag` on every
show publishes the sentence and marks its claim (see "Oct 1 2026 — publish
and mark" below); `strip` and `block` remain selectable per show but are
no longer the network policy. Never turn a flagged claim's status into a
silent pass, and never render a surface that hides the flag.

Same shape as the two rules above, discovered Aug 2026: three functions
in `run_show.py` stripped every attribution the model produced (each for
a good reason — Offshore North Ep001 read its sources block ALOUD) while
nothing anywhere verified that an asserted fact traced to anything, so
**fabricated citations were the expected output** — three unrelated
chapters in two published book volumes each cited "a 1962 paper in
*Nature*" for findings actually published elsewhere (Wagner 1960
*Br J Ind Med*; Fryer 1960 *E Afr Agric J*) or nowhere (the Huxley/Aswan
paper does not exist). True facts wearing false provenance: the model
supplied the citation SHAPE, the pipeline deleted the citation, nothing
checked the difference.

Now: digest generation emits a fenced `claims` JSON ledger (extracted
before any published surface sees it), the gate verifies every entry
(URL resolves + supporting quote fuzzy-appears in the source) and lints
citation-shaped prose against it (`CITATION_SHAPE_PATTERNS` — the
fabrication signature). Verified ledgers commit as
`digests/<slug>/*_claims.json`; books render them as endnotes. Rollout:
network-wide SHADOW (`_defaults.yaml`) from Aug 2026, **enforce: true on
the narrative shows** (UC/FPD — a blocked episode there costs a rerun,
never a burned queue slot: the gate runs before the digest save).
**Since Sep 12 2026 the gate is ENFORCED on every show**, with
`source_integrity.on_failure` deciding what an enforce-mode failure
does after the one repair pass: `block` (UC/FPD — the episode skips) or
`strip` (the network default — `engine.claims.strip_unverified` REMOVES
every sentence the gate cannot vouch for from the digest, the script is
stripped in step by `strip_script_sentences`, the mechanical gate
re-runs on what is left, and only a still-failing text blocks). Shadow
data had shown blocking would lose 2–4 of 7 episodes on five news shows
for malformed ledger entries and 403s, never a proven fabrication.
Strip is not a warning: nothing unverified reaches the blog, the feed or
the newsletter; an uncovered citation shape whose item carries a
resolving `Source:` URL counts as sourced by the item; HOOK/header lines
are never edited. Guards: `tests/test_simplification_2026_09_12.py::TestStripMode`.
The three strippers stay — they
remove leakage; the ledger carries provenance. Audit tools:
`scripts/verify_claims.py` (re-verify committed ledgers),
`scripts/measure_citation_exposure.py` (corpus exposure),
`scripts/soften_citations.py` (backfill, dry-run default). `check_feeds.py`
(ex-`check_sources.py`) grades FEED health only — it has no view on
truth. Drift guards: `tests/test_source_integrity.py`.

**Aug 25 2026 — unreachable ≠ fabricated.** 403/429/5xx/transport failures
are `unreachable` — **still a gate FAILURE**, distinct from the fabrication
signature; an enforce-mode block gets ONE `attempt_claim_repair` pass (claim
text and anchor pinned; the FULL mechanical gate re-runs, so repair can never
launder an unverifiable claim); a topic the gate blocks twice is **deferred by
the picker** (`GATE_BLOCK_DEFER_THRESHOLD`). Guards `TestUnreachableClassification`,
`TestClaimRepair`, `TestGateBlockCooldown`. [history](docs/claude_md_history/2026_08_25_provenance_unreachable_not.md)


**Sep 8 2026 — reviewer notes are a gate failure, not a formatting issue
(WO-13)**: `engine.claims.find_reviewer_notes` fails the gate and `build_epub`
refuses the volume; repair only ever writes ledger entries
(`TestWO13ReviewerNoteGate`). [history](docs/claude_md_history/2026_09_08_provenance_reviewer_notes.md)


**Sep 5 2026 — the empty ledger was the norm, not the exception**: repair
also targets UNCOVERED sentences; no prompt seeds a literal citation example
(`TestClaimRepairUncoveredShapes`). [history](docs/claude_md_history/2026_09_05_provenance_empty_ledger.md)


**Oct 1 2026 — publish and mark, never strip.** A sourced story newer than
the model must never be dropped for failing memory. `on_failure: flag` is the
network default: after the one repair pass nothing is removed but reviewer
notes; every ledger entry commits with a `status` (`verified`,
`verified_from_fetched`, `verified_later`, `unverified_unreachable`,
`unverified_not_found`, `unverified_quote_mismatch`, `unverified_uncovered`,
`malformed`), `gate.policy_version` 2, metrics `source_integrity_flagged_*`.
The record is
public (`claims.html`, `claims/<slug>.html`; `engine.brand.CLAIMS_PROCESS_STEPS`
/ `CLAIMS_STATUS_LABELS` own the copy and no page describes a stronger
policy). Register `claims-flag-policy-2026-10-01`; guards
`tests/test_{claims_flag_mode_2026_10_01,claims_pages_2026_10_01}.py`. [history](docs/claude_md_history/2026_10_01_provenance_publish_mark.md)


**Oct 17 2026 — the page the run read vouches, and an unsourced back-test is
a citation shape** (`CITATION_SHAPE_PATTERNS`; guards `tests/test_citation_shapes.py`). [history](docs/claude_md_history/2026_10_17_provenance_page_vouches.md)


**Oct 5 2026 — the coverage floor reads the item's OWN source**
(`attempt_item_coverage_repair`; entries are added only when each verifies,
kept only when the gate gets no worse; it runs on a FAILING gate in flag mode
too). Register `claims-coverage-grounded-2026-10-05`; guards
`tests/test_claims_coverage_grounded_2026_10_05.py`. [history](docs/claude_md_history/2026_10_05_provenance_coverage_floor.md)


**Sep 18 2026 — the quote was the problem, not the source**: repair allows
the SAME url with a verbatim quote (`source_excerpt_for_claim`;
`_quote_consistent_with_claim`; the 0.9 check is untouched); a bag-of-words
"claim support" gate was REJECTED. Guards `tests/test_provenance_pass_2026_09_18.py`. [history](docs/claude_md_history/2026_09_18_provenance_quote_not.md)


### Cadence + model migration (Sep 21 2026)

[history](docs/claude_md_history/2026_09_21_cadence_model_migration.md); guards `tests/test_dp_pod_weekly_2026_09_21.py`.
**A show's cadence lives in six places** (CRON_MAP, the Worker's `SLOTS`, `review_episodes.py`'s registry, daily-audit's RSS limit, `engine.daily_edition`'s `monday_only`, the public `schedule` string) and `TestNoSurfaceStillSaysDaily` derives the check from CRON_MAP; **DP Pod is weekly**. **A missing section is a structural defect, same as an empty one.** **Model changes follow [`docs/model_upgrade_playbook.md`](docs/model_upgrade_playbook.md); `scripts/model_trial_report.py` is the instrument.** **The reviewer's `reasoning_effort: "low"` branch is a prefix TUPLE, not one id.** **`api/member_metrics.json` filters by Stripe PRODUCT.**

### Freshness, repetition and reproducibility (Sep 30 2026)

[history](docs/claude_md_history/2026_09_30_freshness_repetition_reproducibility.md); register `freshness-dating-2026-09-30`, `frame-memory-2026-09-30`, `whisper-av-pin-2026-09-30`; guards `tests/test_{freshness_pass_2026_09_30,repetition_pass_2026_09_30}.py`.
**An article's date has ONE owner: `engine/article_dates.py`** — **never write `now` into `published_date`**; the search helper never answers from memory (`SearchUnavailable`). **Repetition is frames and second tellings, never exact duplicates** (`engine/frame_memory.py`, never a prompt-only de-seed). **A guard that reads today's committed data must tolerate today.** `av<19`.

### First post-merge slate, the cohort on every surface, trust surfaces (Oct 1 2026)

[history](docs/claude_md_history/2026_10_01_first_post_merge.md); register `frame-memory-wired-2026-10-01`, `story-clusters-2026-10-01`, `platform-ask-2026-10-01`, `apple-ratings-instrument-2026-10-01`, `vtt-transcripts-2026-10-01`, `launch-cohort-newsletters-2026-10-01`; guards `tests/test_{top_world_sources_2026_10_01,worker_show_tags_2026_10_01,web_trust_2026_10_01}.py`.
**A wiring guard renders through the REAL config object.** **A lint measures the text that ships** (`engine/absence_sentences.py` never drops a line carrying a URL or a Source tail). **A story told once per outlet is clustered upstream, annotated, never dropped** (`engine/story_clusters.py`). **The TTS emoji strip lists the four real enclosed blocks only.** **Every show is on the Worker's `SHOW_NEWSLETTER_TAGS`.** Apple ratings are null never 0; a **Verified claims (N)** panel is never hidden; **corrections have a mechanism** (`engine/corrections.py`, `docs/corrections.md`); audio is never edited silently (landmine #25); **one listener-facing address** `engine.brand.CONTACT_EMAIL`.

## Project Overview

Automated daily podcast generation system running 31 shows via a unified
`run_show.py` runner + per-show YAML configs, plus 4 legacy standalone scripts
(deprecated — see note below). Shows use **Grok TTS** (`engine.tts.grok_speak_chunk`)
and (where enabled) post to X/Twitter via `engine/publisher.post_to_x()`.

| Show | Legacy Script | YAML Config | Schedule | X Account | TTS |
|------|--------------|-------------|----------|-----------|-----|
| Tesla Shorts Time | — (deleted) | `shows/tesla.yaml` | Daily | `@teslashortstime` | Grok TTS (custom) |
| Omni View | — (deleted) | `shows/omni_view.yaml` | Daily | `@omniviewnews` | Grok TTS (custom) |
| Fascinating Frontiers | — (deleted) | `shows/fascinating_frontiers.yaml` | Daily | `@planetterrian` | Grok TTS (custom) |
| Planetterrian Daily | — (deleted) | `shows/planetterrian.yaml` | Daily | `@planetterrian` | Grok TTS (custom) |
| Env Intel | — | `shows/env_intel.yaml` | Monday | `@teslashortstime` | Grok TTS (custom) |
| Models & Agents | — | `shows/models_agents.yaml` | Daily | — (X disabled) | Grok TTS (custom) |
| Models & Agents for Beginners | — | `shows/models_agents_beginners.yaml` | Daily | — (X disabled) | Grok TTS (custom) |
| Финансы Просто | — | `shows/finansy_prosto.yaml` | Monday | — (X disabled) | Grok TTS (Olya) |
| Modern Investing Techniques | — | `shows/modern_investing.yaml` | Daily | — (X disabled) | Grok TTS (custom) |
| Привет, Русский! | — | `shows/privet_russian.yaml` | Monday | — (X disabled) | Grok TTS (Olya) |
| Unintended Consequences | — | `shows/unintended_consequences.yaml` | Daily | — (X disabled) | Grok TTS (custom) |
| First Principles Daily | — | `shows/first_principles.yaml` | Daily | — (X disabled) | Grok TTS (custom) |
| SpaceX Daily | — | `shows/spacex.yaml` | Daily | — (X disabled) | Grok TTS (custom) |
| The DP Pod | — | `shows/dp_pod.yaml` | Monday | — (X disabled) | Grok TTS (two-voice: Patrick + Dan) |
| The Age of AI | — | `shows/age_of_ai.yaml` | When an interview is ready (Nerra Voices pipeline, NOT run_show) | — (X disabled) | Real guest phone audio + Mira narration (Grok voice `ara`) |
| Offshore North | — | `shows/offshore_north.yaml` | Monday | — (X disabled) | Grok TTS (Dan `0vscf8u8yrxc`, single-narrator) |
| AI Chips & Data Centres Daily | — | `shows/ai_chips.yaml` | Daily | — (X source only) | Grok TTS (custom) |
| MAG 7 Daily | — | `shows/mag7.yaml` | Daily | — (X source only) | Grok TTS (custom) |
| Peptides Weekly | — | `shows/peptides.yaml` | Thursday | — (X source only) | Grok TTS (custom) |
| Longevity Weekly | — | `shows/longevity.yaml` | Wednesday | — (X source only) | Grok TTS (custom) |
| Vancouver Daily News | — | `shows/vancouver.yaml` | Daily | — (X source only) | Grok TTS (Mira, `ara`) |
| Collingwood Weekly | — | `shows/collingwood.yaml` | Friday | — (X disabled) | Grok TTS (Mira, `ara`) |
| Prediction Markets Daily | — | `shows/prediction_markets.yaml` | Daily | — (X source only) | Grok TTS (custom) |
| Omni View Top World News | — | `shows/omni_view_world.yaml` | Daily | — (X source only) | Grok TTS (Mira, `ara`) |
| Omni View North America | — | `shows/omni_view_north_america.yaml` | Daily | — (X source only) | Grok TTS (Mira, `ara`) |
| Omni View Europe | — | `shows/omni_view_europe.yaml` | Daily | — (X source only) | Grok TTS (Mira, `ara`) |
| Omni View Asia Pacific | — | `shows/omni_view_asia_pacific.yaml` | Daily | — (X source only) | Grok TTS (Mira, `ara`) |
| Omni View Africa & Middle East | — | `shows/omni_view_africa_mideast.yaml` | Daily | — (X source only) | Grok TTS (Mira, `ara`) |
| Omni View Central & South America | — | `shows/omni_view_latam.yaml` | Daily | — (X source only) | Grok TTS (Mira, `ara`) |
| Nerra Daily | — | registry-only (`shows/network_meta.yaml`; NOT run_show — assembled by `scripts/build_daily_edition.py`) | Daily, 7am Eastern, after the English slate (Vancouver excluded) | — (X disabled) | Splices published show audio + Mira links (Grok voice `ara`) |

> Weekly-summary segment (July 2026): shows on a daily cadence with
> `weekly_summary_segment: true` in their YAML run a NORMAL daily episode on
> Sunday that ALSO includes one short "week in review" segment synthesised
> from the past 7 days via the content lake. (This replaced the retired full
> Sunday weekly-recap mode, which skipped the daily news fetch and turned the
> whole Sunday episode into a look-back.) The segment is appended to the
> podcast-only copy of the digest, so no host-instruction text reaches the
> blog / RSS. See landmine #19.

**Science That Changes Everything** (`digests/science_that_changes.py`, ~83 lines)
is a standalone X-posting script, not a podcast show.

## Architecture

### Pipeline (per show, per run)

1. **Fetch** news sources (RSS, xAI/Grok web search, xAI ``x_search`` for Tesla stock quote)
2. **Dedup** via ContentTracker (cross-episode) + entity dedup
3. **Generate** digest text via xAI/Grok API
4. **Synthesize** podcast audio via Grok TTS (`engine/tts.py`, WAV @ 48 kHz)
5. **Mix** intro/outro music with voice (ffmpeg) — all shows (configurable per YAML)
6. **Post** X thread via `engine/publisher.post_to_x()` + update RSS feed + commit output to git

### Key Directories

```
nerranetwork/
├── run_show.py                    # Unified show runner (~716 lines)
├── shows/                         # Per-show YAML configs
│   ├── tesla.yaml
│   ├── omni_view.yaml
│   ├── fascinating_frontiers.yaml
│   ├── planetterrian.yaml
│   ├── env_intel.yaml
│   ├── models_agents.yaml
│   ├── models_agents_beginners.yaml
│   ├── finansy_prosto.yaml
│   ├── modern_investing.yaml
│   └── privet_russian.yaml
├── digests/                       # Legacy show scripts (deprecated) + ALL generated output
│   ├── tesla_shorts_time.py       # DEPRECATED — use run_show.py tesla
│   ├── omni_view.py               # DEPRECATED — use run_show.py omni_view
│   ├── fascinating_frontiers.py   # DEPRECATED — use run_show.py fascinating_frontiers
│   ├── planetterrian.py           # DEPRECATED — use run_show.py planetterrian
│   ├── science_that_changes.py    # ~83 lines — standalone X posting script
│   ├── xai_grok.py                # Shared xAI/Grok API helper (~111 lines)
│   ├── tesla_shorts_time/         # TST output + summaries_tesla.json
│   ├── omni_view/                 # OV output + summaries_omni.json
│   ├── fascinating_frontiers/     # FF output + summaries_space.json
│   ├── planetterrian/             # PT output + summaries_planet.json
│   ├── env_intel/                 # EI output + summaries_env_intel.json
│   ├── models_agents/             # M&A output + summaries_models_agents.json
│   ├── models_agents_beginners/   # MAB output
│   ├── finansy_prosto/            # FP output (Russian)
│   ├── modern_investing/          # MIT output
│   ├── privet_russian/            # PR output (bilingual Russian)
│   └── *.mp3, *.md, *.txt        # Legacy TST flat output (historical)
├── engine/                        # Shared modules
│   ├── __init__.py
│   ├── utils.py                   # Env helpers, text processing, similarity, dedup
│   ├── tts.py                     # Multi-provider TTS (Grok primary; legacy ElevenLabs path retained) — auth, chunking, synthesis
│   ├── audio.py                   # mix_with_music (3 modes), normalize_voice, duration helpers
│   ├── publisher.py               # RSS feeds, X posting, GitHub Pages summaries, digest formatting
│   ├── content_tracker.py         # Cross-episode dedup (per-show section patterns)
│   ├── fetcher.py                 # RSS article fetching
│   ├── generator.py               # LLM digest/podcast script generation
│   ├── tracking.py                # Credit/usage tracking
│   ├── config.py                  # YAML config loader
│   ├── storage.py                 # Cloudflare R2 storage helpers
│   ├── newsletter.py              # Email newsletter helpers
│   └── validation.py              # Config validation
├── assets/
│   ├── pronunciation.py           # Shared TTS pronunciation fixes
│   └── music/                     # Centralized podcast music (intro/outro)
│       ├── README.md              # Music generation guide + AI prompts
│       ├── tesla_shorts_time.mp3  # TST + EI + M&A theme
│       ├── fascinatingfrontiers.mp3     # FF intro jingle
│       ├── fascinatingfrontiers_bg.mp3  # FF background/outro
│       ├── LubechangeOilers.mp3         # OV theme
│       └── oilers-pride.mp3             # PT theme
├── tests/                         # pytest suite
├── .github/workflows/
│   └── run-show.yml               # Unified daily cron workflow (all shows)
├── *.rss                          # Podcast RSS feeds (consumed by Apple/Spotify)
├── *.html                         # GitHub Pages web players + summaries pages
└── docs/                          # Audit docs, storage plan
```

### Script Relationships


> **Per-show review history lives in**
> [`docs/show_review_history.md`](docs/show_review_history.md) — every
> dated quality-pass narrative (root causes, what was fixed, what was
> deferred), moved out of this file on 2026-07-29 so a session does not
> pay to load ~60 KB of history it rarely needs. The entries below keep
> each show's structural facts. Canonical write-ups:
> [`docs/reviews/`](docs/reviews/); scored predictions +
> `do_not_retry`: [`docs/reviews/ledger/`](docs/reviews/ledger/).

**Live constraints from those passes** (kept here because they bind
today's work, not just explain yesterday's):

- **SpaceX AI section:** the Colossus/Anthropic material is REAL — do not
  "correct" or relitigate it (operator-confirmed, June 13 2026).
- **Length levers are digest-side only.** Podcast-side expansion retries
  are banned network-wide (July 18 playbook `do_not_retry`: ~10 misses vs
  1 hit) and were switched off in the show YAMLs on 2026-07-29 wherever a
  digest-side lever exists. Chronic under-length on FF / PT / UC / Tesla /
  EI is a DIGEST ceiling — do not re-attack it at the script. The
  **publication-floor re-roll** (Aug 2026, `engine/generator.py`) is NOT
  that lever: it fires only inside run_show's 60%-of-target skip band —
  where the alternative is losing the whole day (Tesla Ep564 skipped
  2026-08-06; the identical 2026-07-31 skip was recovered by a manual
  rerun) — and regenerates the full prompt fresh instead of expanding the
  short draft. Guarded by `tests/test_podcast_floor_reroll.py`; do not
  remove it as a "banned retry", and do not widen it above the band.
- **De-seed by shape, never with a quotable example.** Every seeded
  template tic in this network's history came from a prompt supplying the
  literal sentence it wanted; three generations of them are in the
  archive. New prompt guidance describes the shape and bans the verbatim.
  **This applies to FORMAT specs too** (Aug 15 2026): a digest FORMATTING
  line showing the literal `**Title: Source Name**` was reproduced
  verbatim by the model for months (SpaceX Ep34→70 every ~5 episodes;
  on Ep70 every headline shipped as its PUBLISHER name). Never write a
  format template whose placeholder reads as plausible content —
  `engine/newsletter_sanitizer.py` scrubs the known label,
  `engine/chapters.py` strips it from titles, and `review_snapshot.py`'s
  "Digest heading integrity" section audits the canonical .md (the
  chapters JSONs are a downstream copy — four reviews scored the wrong
  surface).
- **The grok-4.3 narrative-length plateau is accepted** (operator
  confirmed; it resists escalation). Not a bug to re-open.
- **MIT is NOT ready for live trading** and its `execution/live.py` layer
  is dormant behind a kill switch. Two operator to-dos remain open:
  `scripts/recompute_mit_benchmarks.py --apply` (needs market-data
  access) and SnapTrade Phase-0 verification.
- **The MIT recompute was, until 2026-08-18, unsafe to run.**
  `_match_bar` scanned a window opening TEN DAYS BEFORE the pick and
  returned the FIRST bar inside the ±2% price tolerance, so the tool
  built to remove hindsight backdating re-created it — a live dry run
  flagged 25 trades, including all ten whose entry bars were already
  correct. Entries are now confined to bars on/after the pick, exits to
  bars on/after the entry, and the CLOSEST price wins over the first;
  the corrected run reports 0 backdated entries and reproduces 8 of the
  10 known-good windows exactly. **Never widen that window back, and
  validate any matcher change against those ten trades** — they are the
  only ones written by the trusted path. Corrected dry run:
  **−3.35% alpha across 42 trades**, beating 1 of 3 indices; 8 trades
  reconcile to no bar at all, and they include the record's best
  (+20.11% DLTR), second-best (+13.36% AMD) and worst (−11.80% MDA).
  `--apply` rewrites published performance numbers — operator's call.
- **MIT's simulated trading has a RULEBOOK and an ERA** (2026-08-18):
  [`shows/_trading_policy.yaml`](shows/_trading_policy.yaml) is the rules
  — entry at the first session open on/after the pick, exit at the stop
  or a FIXED 5-session horizon (flash: 1), $1,000, no discretionary
  exits — and the code reads it (`load_policy` / `horizon_sessions` /
  `era_inception`). Before this, the exit was not a decision: weekly
  holds closed on whichever bar the Friday pre-market run priced, so a
  Wednesday pick got one session and a Monday pick five, and per-trade
  alpha measured pick quality and pick weekday together. Alpha spoken on
  air is now the ERA record only (`era_*` in the summary, trades picked
  on/after the inception date); earlier trades stay published as history
  and are NEVER blended in. `_alpha_scope()` is the ONE selector both
  prompt blocks use — era → verified → blended — so a value and a label
  can never come from different sources again. The sim and
  `execution/shadow.py` both derive the holding period from the same
  policy; if they drift the shadow ledger stops being a check. Public
  methodology: [`docs/mit_trading_method.md`](docs/mit_trading_method.md).
  Drift guards: `TestTradingPolicy`, `TestEraScopedRecord`,
  `TestReproducibleDecisions`.
- **MIT trades options now, and the premium is never modelled**
  (2026-08-19). The show taught options in 32 of 40 episodes and had
  traded one in 0 of 61 positions. Covered calls and cash-secured puts
  are now real: the contract is quoted LIVE at pick time (listed strike,
  listed expiry, bid/ask mid) because a premium cannot be reconstructed
  afterwards from free data, and the position is held to EXPIRY where the
  payoff is arithmetic on the underlying close with no free parameters.
  **If the chain cannot be quoted the pick degrades to shares** and
  records `option_quote_failed` — never an estimated premium. Selection
  is by rule (nearest listed expiry 21-45d, strike closest to 4% OTM,
  ITM/unquoted skipped) so it is reproducible. Returns are on capital
  actually committed, which is what makes them comparable with a $1,000
  share position. Early assignment is NOT modelled and the prompts
  require saying so. Guards: `TestOptionsPositions`.
- **MIT's learned rules ROTATE, or the loop can never score any of them**
  (2026-08-20). Across the first 15 stamped trades only two rule sets
  ever existed, differing by one rule and only because the ledger
  happened to change — four of five rules were common to both, so no rule
  could be told apart from another and the (honest) scoreboard would have
  stayed silent forever while looking like a working feedback loop.
  `learning.rule_rotation` in [`shows/_trading_policy.yaml`](shows/_trading_policy.yaml)
  now shows a rotating subset (4 slots from a ~6-rule pool, cycling on
  the episode number, so it is reproducible from the trade record) which
  gives every rule BOTH a with-rule and a without-rule arm. A rule that
  demonstrates an edge is PINNED and stops rotating (`_proven_rule_ids`,
  >=5 trades on both arms); `always_on: true` pins by hand for
  safety-shaped rules. Do not "simplify" the selector back to
  most-recent-N — that is what made attribution impossible. Guards:
  `TestRuleRotation`.
- **MIT reports alpha by strategy FAMILY, not just by sector**
  (2026-08-20). 61 trades produced 61 unique free-text strategy strings,
  so "are our momentum entries better than our valuation screens" was
  unanswerable. `STRATEGY_FAMILIES` / `strategy_family()` is a closed
  vocabulary REQUIRED on new picks and DERIVED from the free text for
  history (unmatched => `other`, never forced). The block inherits the
  window discipline: verified-window trades when there are enough,
  otherwise labelled indicative-only and explicitly not for air. Guards:
  `TestStrategyFamilies`.
- **MIT accounts on air for the number that DISAPPEARED** (2026-08-20).
  Ep141-143 all announced the new era-scoped record; one of three said
  why, none pointed at the rulebook or ledger, and none mentioned the
  **+9.28% across forty-five trades** the show had been quoting — which
  simply stopped appearing. A strong figure that quietly vanishes is
  indistinguishable from one being buried, and here the truth is the
  opposite (it could not be reproduced, so it was not ours to claim).
  `_build_methodology_disclosure` is a SELF-RETIRING correction —
  `METHODOLOGY_DISCLOSURE_EPISODES = 3` airings, stamped as a list of
  episode numbers so a second `get_prompt_context` call in one episode
  cannot burn two, never consumed by read-only runs — and it is NOT a
  recurring changelog: do not extend it, and keep pipeline internals
  (rule rotation, review coverage, scoreboard mechanics) out of it. Its
  payload is the transferable skill, not the apology: the four questions
  that audit ANY track record (when did it start and was the date chosen
  after the fact; what is the exit rule and was it fixed in advance; are
  losers and abandoned positions included; are individual trades
  published or only the summary). The segment claims the rules and
  ledger are "published for anyone to check" — that claim was FALSE in
  practice until this pass, because `api/mit_trade_ledger.*` was built
  nightly and linked from nowhere; the performance page now carries a
  *Verify this record yourself* panel and a guard asserts the links and
  the files both exist. Prompt change => A/B-listen per landmine #17.
  Guards: `TestMethodologyDisclosure`.
- **The daily audit reviews late episodes on a CATCH-UP pass** — it runs
  at a fixed 16:15 UTC while shows finish anywhere from 09:32 to 19:41,
  and anything later was logged "critical: Missed episode" then
  auto-closed next day by confirming the FILE EXISTS, so its content was
  never reviewed at all (four shows on 2026-08-19; a 32-episode
  network-wide backlog at first run). `review_episodes.py` now reviews
  the previous 3 days' unmarked episodes, tracked in
  `api/review_coverage.json` (14-day prune, committed by daily-audit so
  the pass is idempotent), capped at 10/run oldest-first because the AI
  review calls Grok per episode. Guards: `TestReviewCatchUp`.
- **MIT's rule scoreboard must refuse to claim what it cannot measure.**
  It was emitting FIVE identical `RETIREMENT CANDIDATE` verdicts (same 10
  trades, same -0.17% vs +0.43%) because all five rules were stamped on
  exactly the same trades — perfectly collinear, one undivided sample
  reported as five findings — with the disowned pre-era trades as its
  control group. It is now era-scoped, refuses a verdict when the stamped
  rule set never varies, flags collinear rules as ONE piece of evidence,
  requires >=5 trades on BOTH arms, and says "not measurable yet" instead
  of going silent (silence is how the artifacts rode for weeks). Also:
  `_is_trading_rule` keeps production-hygiene lessons — re-teach
  cooldowns, "state the NASDAQ level", the sim's own data-fetch bugs —
  out of the pick prompt, and `_rule_core` dedups on the rule's
  constraint with its scope clause stripped. Guards:
  `TestRuleScoreboardHonesty`, `TestTradingVsPipelineRules`.
- **MIT's cold streak raises the bar on the pick, never on picking**
  (2026-09-18). The COLD regime text had called an explicit no-trade day
  "acceptable and unremarkable"; from Ep152 (08-28, the first episode
  after the era record turned negative) the show declared no trade on
  19 of 23 episodes, the drought valve fired weekly, its forced pick was
  voided (voided picks reset the valve) or closed into the same
  ten-trade window, and the window never turned over — 9 closed era
  trades in a month, nothing scoreable. Now `_build_regime_block`'s COLD
  text demands named factors, an invalidation level and a graded
  confidence but still expects a pick; `_days_since_last_pick` ignores
  voided picks; and `_no_trade_budget_block` allows ONE no-trade per
  five episodes, read from the committed `trade_signal_ep*.json`, with
  a spent budget making a pick mandatory. Register
  `mit-no-trade-budget-2026-09-18` (metric `mit_new_trade_share_10ep`,
  baseline 0.1). Prompt-context change — A/B-listen the first two
  episodes. Guards: `tests/test_mit_no_trade_budget_2026_09_18.py`.
- **The MIT trade ledger is public** (`scripts/build_mit_ledger.py` ->
  `api/mit_trade_ledger.json` + `.csv`, nightly): every trade with entry/
  exit bar dates, stop, horizon, invalidation, confidence, rules in
  effect and option contract. Voided picks and pre-era trades are
  INCLUDED and flagged — a ledger that drops its failures is marketing.
  Guards: `TestPublicLedger`.
- **Two functions speak MIT's alpha, and they must never disagree:**
  `_build_portfolio_summary` and `_build_benchmark_block`. The Aug 15
  pass fixed only the first, and because both reach the same prompt the
  model fused label and value — Ep138 aired "+9.28% across forty-five
  VERIFIED-window trades", the inflated number wearing the honest label.
  Fixing one of two call sites was worse than fixing neither. Same shape
  in the index sweep: its NASDAQ leg fell back to `nasdaq_return_pct`
  (45 trades) beside 10-trade S&P/TSX legs, and the July-18 `n>=5` gate
  missed it because it checks sample SIZE, not that the legs share the
  same TRADES. Guards: `tests/test_mit_benchmark_integrity.py`
  (`TestSingleAlphaSource`, `TestRecomputeMatcherCannotBackdate`).
- **MIT speaks the VERIFIED-window alpha, never the blended one**
  (Aug 15 2026 review:
  [`docs/reviews/modern_investing_review_2026_08_15.md`](docs/reviews/modern_investing_review_2026_08_15.md)).
  `matched_window_alpha_pct` compounds every trade with a
  `nasdaq_return_pct` — including the 35 whose windows the July-3
  integrity pass itself disowned, because the recompute above has never
  run. That blend put **+9.28% across 45 trades** on air while the 10
  pick-date-aligned trades were at **−1.95%**.
  `verified_window_alpha_pct` / `verified_window_trades` (trades carrying
  `entry_bar_date`) are the on-air numbers; the blended pair stays for
  the performance page and the recompute script. Running
  `recompute_mit_benchmarks.py --apply` collapses the split — do not
  "simplify" the two back into one before then. Same pass fixed three
  more silent-number failures: the digest FORMATTING template never
  listed `### Portfolio Performance` (missing from 13 of 20 episodes, and
  the script then told listeners the feed was down), `_build_trade_review`
  only examined `closed[-1]` so 43 of 50 closed trades were never
  narrated once the pick cadence went daily (now drains oldest-first,
  bounded by `REVIEW_BACKLOG_MAX_DAYS`), and the source-collapse alarm's
  10-episode rolling baseline decayed with the collapse it was watching
  (article median 274 → ~57 for three weeks; now a second long baseline
  catches a slide, and three hard-403 feeds were replaced). Drift guards:
  `tests/test_mit_benchmark_integrity.py`.
- **The lesson from that pass, network-wide:** loops that operate on TEXT
  fail loudly (a tic shows up in a snapshot); loops that operate on
  NUMBERS fail silently, because a wrong number looks exactly like a
  right one. Any watchdog whose baseline is a rolling window of the thing
  it watches can only catch a cliff, never a slide.

- **FF and PT** are "nearly identical twins" — same structure, same functions,
  different news topics and X account
- **TST** shares most patterns with FF/PT but adds: complex pronunciation
  fixes, content tracking, chunked TTS, x_search stock data, TST-specific
  emoji formatting via `engine.publisher.format_tst_digest_for_x()`
- **OV** is structurally different — different TTS approach (no streaming, uses
  env vars for voice settings), simpler functions.
- **EI** runs exclusively via `run_show.py` + `shows/env_intel.yaml`; no legacy script.
- **M&A** (Models & Agents) runs exclusively via `run_show.py` +
  `shows/models_agents.yaml`; no legacy script.
- **MAB** (Models & Agents for Beginners) runs via `run_show.py` +
  `shows/models_agents_beginners.yaml`; beginner/teen-focused version of M&A.
  On the custom Grok voice `kdif6sqjcyiq` (inherits `_defaults.yaml`; the old
  "ElevenLabs" note was stale per landmine #17). X posting disabled.
- **FP** (Финансы Просто) runs via `run_show.py` +
  `shows/finansy_prosto.yaml`; Russian-language financial literacy podcast
  for women in Canada (even days only). Uses **Grok TTS** (Olya voice
  `0b875ae2`, `language_code: ru`). All content generated in Russian. X posting disabled.
- **MIT** (Modern Investing Techniques) runs via `run_show.py` +
  `shows/modern_investing.yaml`; daily investing podcast focused on Canadian
  and US markets. Weekdays only. X posting disabled.
- **PR** (Привет, Русский!) runs via `run_show.py` +
  `shows/privet_russian.yaml`; bilingual Russian language learning podcast
  for English speakers. Even days only. Uses **Grok TTS** (custom Olya voice
  `0b875ae2`, `language_code: ru` — `shows/privet_russian.yaml`). X posting
  disabled.
- **FPD** (First Principles Daily) runs via `run_show.py` +
  `shows/first_principles.yaml`; a **daily narrative** show
  (`narrative_mode: true`, topic-queue-driven like UC — no news fetch).
  Applies the first-principles "magic wand number" + "Idiot Index" lens,
  alternating per episode between a concrete example of the thinking in
  action (`category: concrete_example` — historical and modern: Ford,
  Bessemer, containerization, solar, batteries, mRNA, and *sometimes*
  Musk's teams, deliberately not Musk-only) and an industry ripe for it
  (`category: opportunity_area`); Ep1 is a combined debut. Patrick voice
  (inherits Grok `kdif6sqjcyiq`). Distribution OFF at launch (no newsletter,
  no X, no YouTube). Queue: `shows/topic_queues/first_principles.yaml`.
- **UC** (Unintended Consequences) runs via `run_show.py` +
  `shows/unintended_consequences.yaml`; a weekday **narrative** show
  (`narrative_mode: true`, topic-queue-driven — no news fetch). Patrick
  voice. X posting on via the @planetterrian account.
- **SpaceX** (SpaceX Daily) runs via `run_show.py` + `shows/spacex.yaml`;
  engineering-first daily on SpaceX as a public company (Nasdaq: SPCX),
  `memory_enabled`, X disabled. Has a **manual-force-only deep-dive queue**
  (`shows/deep_dives/spacex.yaml`, `deep_dive.enabled: false` so the daily
  cron never scans it): `python run_show.py spacex --deep-dive <id>` runs a
  standalone special through the spacex_deep_dive prompts (first entry:
  `q2-2026-earnings`, the Q2 2026 earnings special, Aug 2026).
- **DP** (The DP Pod) runs via `run_show.py` + `shows/dp_pod.yaml`; the
  **two-host dialogue** show, **WEEKLY on Monday since 2026-09-21**; in
  `ALT_CADENCE_SHOWS`, never `DAILY_SHOWS`, no Sunday recap. First show on
  the **two-voice dialogue TTS path** (`tts.dialogue_mode`,
  `engine/tts_dialogue.py`); dialogue mode NEVER applies the `<fast>` wrap
  and supersedes section-TTS; an unlabeled script falls back to
  `tts.voice_id` with a loud warning. The Lever, the banter and the Network pick have DATA-SIDE
  rotation memory — **do NOT re-add example actions, jokes or concession
  phrases to either prompt**; HARD CEILING 1,750 words; Ep30 stays in the
  pruned catalogue because the RSS `<itunes:episode>` max pins
  `get_next_episode_number` (a purge can never renumber future episodes into
  published GUIDs). Guards `tests/test_{tts_dialogue,dp_pod_show}.py`,
  `tests/test_dp_pod_weekly_2026_09_21.py`. Prompt edits are landmine-#17 A/B. [history](docs/claude_md_history/2026_07_dp_pod_show.md)

- **AOAI** (The Age of AI) — the **AI-hosted LIVE interview show**: Mira
  (Grok voice `ara`, deliberately NOT the Patrick clone) interviews REAL
  guests in a browser ROOM (`age-of-ai-studio.html`). **Since 2026-10-27 there are NO phone-call
  interviews at all.** Never reintroduce a phone call, in code or in copy. Do
  not describe the show as a phone-call show on any surface. **Production
  does NOT go through run_show** (`shows/age_of_ai.yaml` is registry/publish
  only; an accidental run is a clean `narrative_queue_empty` skip). The
  pipeline is **Nerra Voices** (`pipelines/voices/`, `workers/voices/`,
  `voximplant/scenarios/age_of_ai_interview.js`): **gate 1: Patrick editorial
  review (never times out into publish)** → **gate 2: guest transcript
  approval (day-7 auto-approve; redactions cut from audio FIRST)**. Guest
  words are verbatim; every episode discloses the AI host. Guards
  `tests/test_age_of_ai_show.py`. **Distribution: newsletter + YouTube ON, X
  from @nerranetwork, multilingual off.** **Any new show that bypasses
  run_show inherits this hole; wire its distribution explicitly.** **Grok Voice 3.0 is the model behind
  the room, NOT the shows' `/v1/tts`, and it is PINNED**
  (`DEFAULT_GROK_VOICE_MODEL`; never a floating alias; the next version after
  a rehearsal; register `grok-voice-3-2026-10-15`; guards
  `tests/test_grok_voice_3_2026_10_15.py`). [history](docs/claude_md_history/2026_07_age_ai_show.md)

- **NDaily** (Nerra Daily) — the **combined daily edition**: SPLICES the
  day's published English MP3s with Mira host links (`ara`). **Not a run_show show and it must never become
  one**: registry entry only (no `shows/nerra_daily.yaml`), built by
  `scripts/build_daily_edition.py` + `engine/daily_edition.py`; the summaries
  entry per date is the idempotency key. **Each segment's outro tail is
  trimmed via the committed Whisper word timestamps** (no match = ships
  whole, never a guessed cut; **extend the matcher for a new Whisper
  spelling, never lean on the fallback**; `TestPromoCutHardening`)
  and Mira speaks ONE network AI disclosure. A new AOAI episode is plugged,
  never spliced; the rundown blog never duplicates digests. **A new virtual
  show must be added to `_virtual_show_targets` and `_VIRTUAL_COST_SLUGS`.**
  **The lineup is every English show** (Vancouver out). **The release gate is
  `engine.daily_edition.ready_decision`** in WALL time, never a UTC hour.
  **A show run's push resolves a `blog/<show>/*.html` conflict by keeping its
  own render** (`TestTheBlogCollision`). Docs
  [`docs/nerra_daily.md`](docs/nerra_daily.md); guards `tests/test_{daily_edition,nerra_daily_full_lineup_2026_10_02}.py`,
  `tests/test_{nerra_daily_8am_pacific_2026_10_08,push_show_artifacts}.py`. [history](docs/claude_md_history/2026_08_nerra_daily_show.md)

- **ON** (Offshore North) runs via `run_show.py` + `shows/offshore_north.yaml`;
  **weekly ocean-racing show** (Mondays): Canada Ocean Racing / Scott
  Shawyer / EMIRA IV toward the Vendée Globe 2028. Register `offshore-north-review-2026-10-30`; guards
  `tests/test_offshore_north_{review_2026_09_14,round1_2026_09_18,resource_2026_09_19,tracker_2026_10_04,review_2026_10_30}.py`.
  `fetch_full_text: N` is **opt-in per show; 0 = byte-identical**; a per-feed
  `window_hours` may look FURTHER back than the ladder, never less.
  **Editorial (⚠️ AUDIO)**: last-known position + the DATE of the fix, never
  "unconfirmed"; never "standing facts/item" on air; Plain Sailing is never a
  length lever; **no host-experience lines**
  (`host_experience_filter`). **Vendée Globe qualification is the Notice of
  Race list** — a race off it is never a qualifier. **The campaign record is
  ONE file**, `site/data/offshore_north_dashboard.json` — never hand-write a
  date into the prompts; a new fix goes in `position_log`, never guessed;
  never a placing from memory. **The position is the tracker's**
  (`engine/yb_tracker.py`): the base is **Gosport, UK**, never
  Brittany/Lorient; older than `STALE_DAYS` is "last seen <date>", never
  present tense; a race EMIRA IV is not in is never her next milestone.
  **Instagram is read, never copied** (`media_url` never requested). [history](docs/claude_md_history/2026_09_14_offshore_north_show.md)

- **Vancouver Daily News / Collingwood Weekly** — the first run_show shows
  with an AI host (`host_kind: ai`, Mira on `ara`, NO speech wrap); roads and
  weather are sourced hook ARTICLES (`engine/local_conditions.py`). **Every
  new show runs grok-4.7** and includes `_shared/interesting_first.txt`. A
  pinned model that fails switches the run to grok-4.3 and records
  `llm_model_pinned` / `llm_model_fallback`; the cohort's calls STREAM; a
  pinned model gets ONE budget-gated same-model retry (`engine.generator._call_pinned`;
  a 5xx never retries); a retry of an existing digest runs with
  `allow_model_switch=False` and keeps the original (`PinnedModelUnavailable`).
  Missing Sources are repaired FROM THE RECORD only, never from memory. Guards
  `tests/test_new_shows_phase2_2026_09_23.py`,
  `tests/test_grok47_resilience_2026_09_24.py`,
  `tests/test_top_world_sources_2026_09_24.py`. [history](docs/claude_md_history/2026_09_23_vancouver_collingwood_grok47.md)

- **Prediction Markets Daily** (Sep 2026, pre-launch, Patrick) — the
  ecosystem, never a price tape and never a bet. The Board (≤5 markets) is
  one hook ARTICLE per market from `engine/prediction_board.py` (Polymarket
  Gamma, Kalshi's paced events crawl — it 429s a fast one — and Manifold
  play money; sports, parlays, price ladders and near-certain markets
  excluded; volume in each venue's own unit, never converted); How It Works
  is one subject a day from `shows/curricula/prediction_markets.yaml` with
  Crossref/arXiv abstracts (`engine/research_papers.py`) so the claims gate
  has papers to verify against. Board text is the pipeline's own copy, so it
  carries no specific legal claim. The Board is not content-tracked (a live
  market may lead for weeks). Guards: `tests/test_prediction_markets_2026_09_23.py`.
- **The Omni View desks + Top World** (Mira). **One definition, every
  surface:** `engine/omni_desks.py` owns the desks; the ONLY per-desk prompt
  text is `shows/prompts/omni_desks/<region>.txt`; no `keywords:` on purpose;
  sub-region balance is a note, never a quota. **Top World verifies against
  the publisher, never a sibling digest.** Guards
  `tests/test_{phase3_desks_2026_09_23,desk_ep1_review_2026_09_23}.py`,
  `tests/test_pinned_model_fallback_2026_09_23.py`. [history](docs/claude_md_history/2026_09_23_omni_view_desks.md)

- **Launch-cohort pass, PR A (2026-09-23; guards
  `tests/test_launch_cohort_pass_2026_09_23.py`).** **`engine/digest_lint.py`**
  is a closed vocabulary of digest checks (`digest_lints:`); a finding rides
  the EXISTING one-shot structural regeneration; nothing here blocks or
  strips. **X posts credit the article they link**; `x_posts_as_sources`
  (`any` | `linked_only` | `secondary`); a tag / topic / mirror page is never
  a citation; a wire copy is credited to the wire its dateline names. [history](docs/claude_md_history/2026_09_23_launch_cohort_pass.md)

- **Launch-cohort pass, formats (2026-09-23; guards
  `tests/test_launch_cohort_formats_2026_09_23.py`; register
  `launch-cohort-pass-2026-09-23`).** **Top World**'s **Saturday single-story
  edition** is decided by the hook's `edition_note`, never by the model
  reading a calendar. **Prediction Markets** scores itself on Fridays
  (`engine/board_week.py`; one reading is never resolved); a number is a
  PRICE, never "the odds". **MAG 7 and AI Chips close on a dated calendar
  read last.** Longevity names ONE hallmark, never the framework. [history](docs/claude_md_history/2026_09_23_launch_cohort_formats.md)

- **Network sourcing pass (2026-09-24; guards
  `tests/test_network_sourcing_pass_2026_09_24.py`; register
  `network-sourcing-pass-2026-09-24`).** `fetch_full_text` and
  `preferred_domains` on the established news shows; `x_posts_as_sources:
  secondary` where the show does not own the story (**Tesla and SpaceX stay
  legacy — their own posts are primary**); `evidence_rung` deliberately NOT on
  FF / planetterrian. `engine/show_notes.py` appends a linked `Sources:` line
  to every RSS description. [history](docs/claude_md_history/2026_09_24_network_sourcing_pass.md)

- **Launch-cohort PR C (2026-09-23; guards
  `tests/test_launch_cohort_schedule_2026_09_23.py`).** `PRELAUNCH_SLUGS` is
  EMPTY. **All 13 joined `ENGLISH_SHOWS`** (appended; the stride stays
  coprime). **`/mira.html` carries "Mira also reads the news"**
  (`MIRA_SHOW_SLUGS` and the `mira` strand untouched — the news shows are not
  the claim's basis). A "first scheduled episode" line comes from the
  registry's `first_run` — never a typed date. [history](docs/claude_md_history/2026_09_23_launch_cohort_pr.md)

- All shows delegate X posting to `engine.publisher.post_to_x()`
- TST/FF/PT delegate voice normalization to `engine.audio.normalize_voice()`
- All shows use `engine.audio.mix_with_music()` for music mixing (3 modes:
  standard, delayed-intro, dual-music). Music files in `assets/music/`.
  Shows without music files gracefully fall back to voice-only.

## Adding a new show

Use `python scripts/scaffold_show.py` to generate YAML, prompts, output dirs, and
`shows/network_meta.yaml` in one step. Episode 1 gets extra debut guidance via
`engine/first_episode.py`. See [`docs/NEW_SHOW.md`](docs/NEW_SHOW.md).

## Conventions

### Environment Variables

- All secrets come from `.env` (local) or GitHub Actions secrets
- `GROK_API_KEY` — primary xAI key (all shows)
- `ELEVENLABS_API_KEY` — ElevenLabs TTS (legacy/rollback only — no show uses ElevenLabs in production)
- `X_*` / `PLANETTERRIAN_X_*` — two separate X accounts
- Voice IDs: **All 13 shows are on Grok TTS** as of the May 2026 full-network migration. The 10 English shows (including Tesla Shorts Time) share the operator's custom-trained voice `kdif6sqjcyiq`. Russian shows (FP/PR) use the custom Olya voice `0b875ae2`. ElevenLabs is no longer used in production but the API key + legacy settings stay in `_defaults.yaml` for emergency rollback. See landmine #17.
- See `docs/env_var_inventory.md` for the complete inventory

### RSS Feeds

All RSS `<enclosure>` URLs now use `audio.nerranetwork.com` (Cloudflare R2).
MP3 files are uploaded to R2 during the pipeline and excluded from git commits.
**Do NOT change R2 bucket paths — this breaks podcast subscribers.**

### Image gallery (Phases 1 + 2 + 3 — May 2026)

[history](docs/claude_md_history/2026_05_image_gallery_phases.md); doc [`docs/gallery_storage.md`](docs/gallery_storage.md).
Every Grok-Imagine scene uploads to the `nerra-gallery` R2 bucket (`engine/gallery_uploader.py`, additive — a gallery failure cannot block YouTube publish); `/api/download` on the Worker proxies bytes — no signed R2 URLs. Unconfigured = clean no-op.

### YouTube Shorts production (May 2026 retune)

[history](docs/claude_md_history/2026_05_youtube_shorts_production.md); guards `tests/test_{thumbnail_autofit,captions_ass,shorts_selector,shorts_stagger,shorts_hashtags}.py`.
**Staggered publishing**: later Shorts upload PRIVATE with `publishAt` (`engine/shorts_stagger.py`). The end-screen CTA card degrades, never blocks publish.

### YouTube visual reuse + chapter-aligned scenes (June 2026)

[history](docs/claude_md_history/2026_06_youtube_visual_reuse.md); doc [`docs/youtube_visual_reuse.md`](docs/youtube_visual_reuse.md); guards `tests/test_visual_reuse.py`.
Best-effort — any failure ships the legacy render (`engine/visual_reuse.py`). Thumbnail variants are invisible to the scene selector.

### Nerra Personal — accounts, personalized feeds, donations (Aug 2026)

[history](docs/claude_md_history/2026_08_nerra_personal_launch.md); doc [`docs/nerra_personal.md`](docs/nerra_personal.md); guards `tests/test_nerra_personal.py`, `workers/gallery/test/personal.test.ts`.
**One identity**: a Nerra account IS the gallery Worker's JWT/Buttondown identity. `scripts/build_personal_feeds.py` — **PII rules: PRIVATE host only; specs carry token/name/city never email; logs truncate tokens**.

### Nerra Personal: Mira knows the listener, at no new model cost (Oct 18 2026)

[history](docs/claude_md_history/2026_10_18_nerra_personal_mira.md); register `personal-deep-2026-10-18`, `personal-trims-2026-10-18`; guards `tests/test_{personal_deep_2026_10_18,personal_handoffs_2026_10_17}.py`.
**No new model or search call per member.** The member note is fenced as information never instructions and never logged; trims cut only a WHOLE chapter in a pause, never a lead, sign-off, last chapter or members-only episode. ⚠️ AUDIO.

### The schedule runs on Eastern time; Nerra Daily out by 7am Eastern (Oct 17 2026)

[history](docs/claude_md_history/2026_10_17_eastern_schedule.md); register `nerra-daily-7am-eastern-2026-10-17`; guards `tests/test_{seven_am_eastern_2026_10_17,scheduling_punctuality}.py`.
**The scheduler Worker's `SLOTS` are EASTERN wall time**; Vancouver **is not in the edition**; gate `RELEASE_EASTERN` 06:35 / `HOLD_UNTIL_EASTERN` 06:50; **the one cron trigger is `*/5 * * * *`**; the run-show.yml fallback crons are **the slot's EST equivalent (ET + 5 h)**.

### Audio first, and a release schedule for the day (Oct 17 2026)

[history](docs/claude_md_history/2026_10_17_audio_first_release.md); register `audio-first-2026-10-17`, `release-schedule-2026-10-17`; guards `tests/test_{audio_first_2026_10_17,release_schedule_2026_10_17}.py`.
**A run publishes its audio before it renders video** (`NERRA_AUDIO_FIRST_PUSH=1`, never in `--test`); **`scripts/stage_show_artifacts.sh` is the ONE staging list**; **the feed item is rewritten after the video on the SAME GUID**. **`engine/release_schedule.py` owns when each surface goes public** (one `RELEASE_ORDER`; 7:00 ET is Nerra Daily's); a passed slot means now.

### A beat between stories (Oct 13 2026)

[history](docs/claude_md_history/2026_10_13_beat_between_stories.md); register `story-breaks-2026-10-13`; guards `tests/test_story_breaks_2026_10_13.py`.
`engine/story_breaks.py` splices `audio.story_break_seconds` of silence where a new story starts (0 = off, never on a dialogue show); each cut sits in the voice's own silence, never between Whisper word times; `[pause]` was REJECTED. ⚠️ AUDIO.

### Natural transitions, and shows that reach their length (Oct 14 2026)

[history](docs/claude_md_history/2026_10_14_natural_transitions_length.md); register `story-transitions-natural-2026-10-14`, `shows-reach-their-length-2026-10-14`, `slate-readout-2026-10-14`, `external-review-2026-10-14`; guards `tests/test_{transitions_and_length_2026_10_14,slate_readout_2026_10_14,external_review_2026_10_14}.py`.
**`audio.story_break_seconds` is the TOTAL pause (1.0)**; calibrate a cue on a REAL voice, never by ear. **The digest length floor counts PROSE**; **every skip floor stays at its old 60% line (`min_podcast_publish_words`) — never raise a target without pinning it**. **Market-research press releases never reach a prompt** (`NETWORK_EXCLUDE_TITLE_PATTERNS`). **One budget for every headline-derived chapter title** (`engine.titles.HEADLINE_CHAPTER_TITLE_MAX`).

### Story breaks that reach the audio, and handoffs that match (Oct 16 2026)

[history](docs/claude_md_history/2026_10_16_story_breaks_reach.md); guards `tests/test_slate_2026_10_16.py`.
**A Nerra Daily handoff must introduce the segment after it** (`realign_handoffs`; **Nerra Personal runs the same repair**). Ratio shorthands match only their own case; paid placements drop by URL path (`NETWORK_EXCLUDE_URL_PATTERNS`). ⚠️ AUDIO.

### A beat only where a story changes, and X video (Oct 17 2026)

[history](docs/claude_md_history/2026_10_17_beat_only_where.md); register `story-breaks-placement-2026-10-17`, `slate-2026-10-17`; guards `tests/test_slate_2026_10_17.py`.
**`MIN_STORY_SECONDS` is 12**; the cold open and the sign-off never set the story. **The expansion dedup never touches a fenced block**; a URL-slug date never wins when it is in the future. **A queued X post is `x_post_queued`, not a confirmed post.** ⚠️ AUDIO.

### The Age of AI: the room, the brief, and a loop that can hear (Oct 21 2026)

[history](docs/claude_md_history/2026_10_21_age_ai_room.md); register `age-of-ai-room-and-loop-2026-10-21`; guards `tests/test_{room_mechanics,mira_prompt_is_a_brief,audio_metrics,loop_hears,voices_worker_hardening,edit_keeps_its_promises,guest_hour,rehearsal_harness}_2026_10_21.py`.
**End of turn is a decision, not a timer** (the silence timer is never raised again). **She never speaks first on join.** **The prompt is a host's brief, not a rulebook** — **no quoted specimen of a bad line and no dated incident narrative** ([`docs/mira_craft_notes.md`](docs/mira_craft_notes.md)); **never add a prohibition to the live prompt for a fault the room can enforce**. Lessons are retired by the metric, never by age. **A guest is never the test**; **a scenario or prompt change ships to a real guest only on a PASS plus one operator listen**. **The edit keeps its promises in code.** ⚠️ AUDIO on every interview.

### The Age of AI: a server turn, a guest on another call, and a sign-off too soon (Oct 22 2026)

[history](docs/claude_md_history/2026_10_22_age_ai_server.md); guards `tests/test_room_holds_2026_10_22.py` (`tests/fixtures/room_sim.js`), `tests/test_room_rescue_2026_10_23.py`, `tests/test_round_{in_step,follow_up,sign_off,end}_2026_10_23.py`, `tests/test_round_from_stuarts_room_2026_10_24.py`.
**The hold check-in and every round turn go as that one response's `instructions`, never a conversation note**; the trace never carries the guest's words. **No sign-off while the round is unfinished** — a guest is never trapped. **A candidate room is rehearsed before it is deployed** (the live scenario is never written); **Mira is measured from the side the guest HEARD, never her own record**. **She is handed the question's words, never a description of it**; **her briefs never say "lightning"**. The scenario, `fire_interviews.CLOSING_ROUND` and both briefs change together. **A question is handed again at most once**; **the index never moves back**; **nothing is taken back on air**; **no turn with no guest in the room**. Deploy only after a candidate rehearsal reads PASS and one listen. ⚠️ AUDIO.

### The Age of AI: a feedback panel and Mira's picture in the studio (Oct 23 2026)

[history](docs/claude_md_history/2026_10_23_age_ai_feedback.md); guards `tests/test_studio_feedback_2026_10_23.py`.
**A move-on or a topic is that ONE response's instructions at her next turn**, never a conversation note. **Typed text is data, fenced and stripped**; the trace never carries it. **Never during a hold or the closing round.** Mira's picture plays only while her audio is voiced.

### The Age of AI: her pause explained, the guest on video, research she starts herself (Oct 28 2026)

[history](docs/claude_md_history/2026_10_28_age_ai_pause.md); guards `tests/test_{guest_video,mira_researches_on_her_own,turn_cues,second_test_room,video_sync_and_shorts,michaels_post_production}_2026_10_28.py`, `tests/test_michaels_publish_2026_11_01.py`, `workers/voices/test/guest_video.test.ts`.
**The guest's camera is recorded in the browser, never through the call**; **a video take never touches `local_<role>_url`**; **a take is appended in the database, never read-and-written**; **`voices.local_video` is false until a test room with a person on camera passes and the operator has watched it**; **publish uses the video only while `video_of` is the edit being published** and never for an audio-only guest; **Mira moves only while she speaks** — measured from the audio, never the transcript; the Voximplant video is never a source. A research finding reaches her as ONE sourced note that never starts a turn and never corrects the guest; **the trace never carries the guest's words**. No prosody rule goes into the room ([`docs/reviews/turn_cues_2026_10_28.md`](docs/reviews/turn_cues_2026_10_28.md)); an adaptive wait is a room change — rehearsal and a listen first. Software audio devices are never chosen; **post-production never loops on a line**.

### Members-only limited series (Oct 18 2026)

[history](docs/claude_md_history/2026_10_18_members_only_limited.md); doc [`docs/specials.md`](docs/specials.md); guards `tests/test_specials_2026_10_18.py`.
**A limited series runs outside run_show** (`engine/specials.py`; released only after the operator has listened). **Only pages the run READ are sources**; **a script is written only from its sourced dossier**; **audio goes to the private bucket under `specials/`, never a show's keyspace**; **a trailer GUID never contains `ep<digits>`**; **nothing public reads a series before `status: released`**. ⚠️ AUDIO.

### Actions minutes: the "is there work" decision leaves the runner (Oct 19 2026)

[history](docs/claude_md_history/2026_10_19_actions_minutes.md); guards `tests/test_actions_minutes_2026_10_19.py`.
**multilingual.yml and nerra-daily.yml have no `workflow_run` trigger** (`scripts/followup_dispatch.py` dispatches from the show run). **A push to main that changes only generated output never runs the test suite** (pull requests never filtered).

### The Voices Worker has a backup clock (Oct 24 2026)

[history](docs/claude_md_history/2026_10_24_voices_backup_clock.md); doc [`docs/voices_backup_clock.md`](docs/voices_backup_clock.md); guards `tests/test_voices_backup_clock_2026_10_24.py`, `workers/voices/test/backup_clock.test.ts`.
**`scheduled()` is only `runTick(env, scheduledTime, "cloudflare")`**; the cron-tick route uses `CRON_TICK_SECRET`, never ADMIN_TOKEN. **A tick claims its five-minute slot in `cron_ticks` first** and **every minute decision reads the slot, never the arrival time**; watchdog state is `cron_clock_state`, never memory.

### The Oct 19 slate: the Eastern schedule's first day, the video job's first (Oct 19 2026)

[history](docs/claude_md_history/2026_10_19_slate_review.md); guards `tests/test_slate_2026_10_19.py`.
**A bold `**Title: Outlet**` line and its paragraph are ONE item**; **a bold-wrapped heading is never the hook**; **the fire-tick gate reads interviews three hours around their slot, never two days**.

### The smoke step stopped the slate (Oct 18 2026)

[history](docs/claude_md_history/2026_10_18_smoke_step_stopped.md); guards `tests/test_slate_2026_10_18.py`.
**A per-show smoke step never runs a test that scans another show's committed content.** **Nerra Daily wakes after a failed show run too.** **The run budget is 70 min under an 80-min hard kill.** **A killed audio-first checkpoint leaves no rebase behind.**

### The 24-hour review (Oct 18 2026)

[history](docs/claude_md_history/2026_10_18_review_24h.md); register `review-24h-2026-10-18`; guards `tests/test_{review_2026_10_18,pinned_comment_2026_10_18}.py`.
**A template renders through `format_map` with every field supplied, never a swallowed `KeyError`**; **nothing links a scheduled video before its `publish_at`**; **an outcome hook is never a re-telling**; a weekend close says "closed Friday at" (⚠️ AUDIO).

### The 48-hour review (Oct 18 2026, evening)

[history](docs/claude_md_history/2026_10_18_review_48h.md); guards `tests/test_review_48h_2026_10_18.py`.
**Every model- or form-written string on the homepage goes through `| e`**; **a `wrangler.toml` never carries a placeholder id**; **the structural digest retry restores the claims and combined-script stashes on every path that keeps the original** (an abandoned generation never writes a stash); **both chapter passes use `voice_intro_delay` alone**; the video job's done marker is written BEFORE the X stage; the Sunday segment names people as the week's coverage did (⚠️ AUDIO).

### The video renders in its own job; Shorts on the front page (Oct 18 2026)

[history](docs/claude_md_history/2026_10_18_video_job_shorts.md); register `video-job-2026-10-18`, `homepage-shorts-reel-2026-10-18`; guards `tests/test_{video_job_2026_10_18,homepage_shorts_reel_2026_10_18}.py`.
**Video no longer shares the show run's time limit** (`NERRA_VIDEO_JOB=1`; `render-video.yml` fetches the MP3 by the raw URL, never the OP3 prefix); **the video and X code is the same code**; the job's credentials must equal the show run's; the sweep **never retries a handoff that already has a run**. **The front page carries a Shorts reel** (each card the episode's own scene, never a YouTube thumbnail; a muted preview never under reduced motion or Save-Data).

### What the flagship rehearsals showed in the video (Oct 18 2026)

[history](docs/claude_md_history/2026_10_18_flagship_video_rehearsals.md); register `video-pass-2026-10-18`, `hook-short-motion-ab-2026-10-18`; guards `tests/test_video_pass_2026_10_18.py`.
**A slot never repeats the previous picture when another image fits the chapter**, and **the slot cap never merges same-image neighbours first**. **A fact card shows only a label that reads.** **The hook motion clip runs on even date ordinals only** (odd days are control, never `hook_stills`). **No show renders an Instagram/TikTok variant while no workflow carries the posting secrets.**

### The follow ask on @nerranetwork, and a render budget sized from the audio (Oct 15 2026)

[history](docs/claude_md_history/2026_10_15_follow_ask_render.md); register `x-follow-ask-2026-10-15`, `long-form-render-budget-2026-10-15`; guards `tests/test_{x_follow_ask_2026_10_15,x_edition_slot_and_follow_phase_2026_10_17}.py`.
**The follow-ask order is derived, never typed** (`engine.release_schedule.x_posting_order`); the ask is used only when the hook fits whole. **A show that posts to the network account must be on the roster.** **Nerra Daily's X post is QUEUED into its reserved 7:00 ET slot** and never also posted directly. **The long-form render is budgeted at 2.1x the audio.**

### Gated shows — members-only and public-weekly (Oct 13 2026)

[history](docs/claude_md_history/2026_10_13_gated_shows.md); doc `docs/nerra_personal.md` "Gated shows"register `desks-members-only-2026-10-15`; guards `tests/test_{personal_gating_2026_10_13,desks_members_only_2026_10_15}.py`.
**`engine/access.py` owns the decision; `access:` in the show YAML is the setting (`public` default).** An unknown `access.mode` RAISES, never publishes; a members episode's text goes to `digests/<dir>/members/`, so public surfaces read the top level. **A new consumer that globs a show's digests recursively must skip `members/`.** Only the Personal builder passes `include_members=True`. **The five Omni View desks are `members_only` with `access.unknown_demand: skip`**; no show plugs them on air.

### Network review — the Oct 12-13 slate (Oct 13 2026)

[history](docs/claude_md_history/2026_10_13_network_review_slate.md); register `network-review-2026-10-13`; guards `tests/test_network_review_2026_10_13.py`.
**Sourcing narration is cut in code, at clause level where the sentence carries a fact** (sweep every committed script before widening a pattern); **a launch designator is two numbers, never a range**; **a lead section is matched by name OR "Top " prefix**; **MIT's Market Pulse reads `{nasdaq_benchmark_line}` from the hook, never the digest's copy**; **a prompt never types a sibling's cadence word**. ⚠️ AUDIO.

### Cost-efficiency pass (July 29 2026)

[history](docs/claude_md_history/2026_07_29_cost_efficiency_pass.md); guards `tests/test_cost_efficiency_pass.py`.
**Measure first.** **Single-pass long-form render is the default** (`NERRA_SINGLE_PASS_RENDER=0` forces the legacy path); **the podcast-side expansion retry is off wherever a digest-side lever exists**; **CLAUDE.md's size is a per-session cost on all future work**.

### Funnel instrumentation + RU SpaceX pilot + Shorts motion A/B (July 30 2026)

[history](docs/claude_md_history/2026_07_30_funnel_instrumentation.md); doc [`docs/funnel.md`](docs/funnel.md); guards `tests/test_{funnel,shorts_ab,ru_spacex_pilot}.py`.
`scripts/build_funnel.py` → `api/funnel.json`. **Honesty rules are load-bearing:** an unmeasured stage reports `null`, never `0`; rates stay `null` below a 30 denominator. The server owns the capture tags. Shorts motion A/B: **not a revival of `video_clips_enabled`**; a fallback ships stills AND RECORDS stills.

### Video enhancement pass — hook-first Shorts + render look v2 (July 31 2026)

[history](docs/claude_md_history/2026_07_31_video_enhancement_pass.md); guards `tests/test_video_commands.py`, `tests/test_shorts_selector.py::TestHookFirstWindows`, `tests/test_shorts_ab.py::TestWindowParityDeconfound`.
**Hook-first Shorts**: Short #1 starts at the episode opening (`hook_first_windows`, one implementation, three call sites). `RENDER_LOOK_VERSION = 2` is recorded per episode.

### Narrative-matched imagery + delivered resolution (Sep 2026)

`engine/scene_briefs.py` writes one scene per STORY and those briefs LEAD the
Grok Imagine prompts. **The image endpoint ignores `size`** — the delivered
width is the metric `grok_image_px_max`; read THAT, never the request.
**Chapter title cards are a fit gate on `engine.titles.CHAPTER_CARD_MAX`,
never a clip.** Guards `tests/test_scene_briefs.py`,
`tests/test_video_commands.py::TestChapterTitleCards`. [history](docs/claude_md_history/2026_09_03_narrative_matched_imagery.md)

**Sep 9 2026 — two numbers that lied.** **The Analytics `day_series` is the
only view-flow source for alarms and scorecards; `total_views` is a lower
bound.** **A new metric set on the publish result is NOT a metric until it is
on the allowlist in `engine.pipeline.record_youtube_outcomes`.** [history](docs/claude_md_history/2026_09_09_two_numbers_that.md)

**Sep 9 2026 — captions: the long-form layer is the uploaded TRACK, never
the pixels** (`long_form_burn_in_captions: false`; `TestLongFormCaptionLayer`);
`transcript_to_srt` never drops a real word; foreign captions on a Short are
the VIEWER's setting, not a bug. [history](docs/claude_md_history/2026_09_09_captions_track_not.md)

**Sep 9 2026 — Grok's retention plan, checked against the data** (register
`shorts-subscribe-cta`, `fresh-open-long-form`, `long-form-fact-cards`,
`pause-dead-youtube-uploads`; guards `tests/test_fact_cards.py`,
`TestFreshOpen`): **the long-form opening slot draws from the fresh pool
only**; anything spoken was rejected. **YouTube is PAUSED on env_intel and
finansy_prosto** (`YOUTUBE_ENABLED_SHOWS` pins the set). [history](docs/claude_md_history/2026_09_09_grok_retention_plan.md)

**Sep 12 2026 — compare at a fixed age, never against the peak**:
`api/youtube_early_reach.json` and the dashboard's **Early reach
(age-matched)** card — use it before calling a drop
(`TestFfmpeg7FrameRateStamp` also from this pass). [history](docs/claude_md_history/2026_09_12_compare_fixed_age.md)

**Sep 13 2026** (guards `tests/test_youtube_pass_2026_09_13.py`):
`wall_duration_s` never double-counts a nested render
(`engine.metrics._NESTED_DURATION_COUNTERS` — add a counter there when it is
nested); a failed gallery-manifest walk keeps the committed manifest. [history](docs/claude_md_history/2026_09_13_first_slate_after.md)

**Sep 17 2026 — a partial analytics fetch is not a snapshot** (guards
`tests/test_youtube_pass_2026_09_17.py`): `fetch_youtube_analytics.py` retries
5xx (never 403) and **refuses to overwrite a clean file**; never read a week
whose snapshot was refused. [history](docs/claude_md_history/2026_09_17_partial_analytics_fetch.md)

**Sep 18 2026 — a result key is not a metric, third time** (guards
`tests/test_caption_track_2026_09_18.py`; register `caption-track-retry-2026-09-18`;
metric `caption_track_refusals_14d`). [history](docs/claude_md_history/2026_09_18_result_key_not.md)

**Sep 22 2026 — the picture follows the audio, and the first sentence has a
shape** (guards `tests/test_scene_scheduler.py::TestLongFormSentenceSnap`,
`tests/test_{fact_cards,hook_short_motion}.py`,
`tests/test_spoken_open_shape_2026_09_22.py`): **every long-form image is the
episode's own** (the `visual_reuse` getattr fallbacks must equal the
dataclass); chapter boundaries never move; **the gallery-retention prior
reads `by_kind` ONLY**; a hook-Short motion shortfall is never the A/B's
`"stills"` label; **the spoken open has a shape** (`_shared/hook_shape.txt`;
`engine.titles.SPOKEN_HOOK_MAX_CHARS` is a regeneration GATE, never a
truncation). [history](docs/claude_md_history/2026_09_22_picture_follows_audio.md)

**Sep 22 2026 — "same episode, different channels" is the test for content
vs distribution** (register `en-one-short-2026-09-22`,
`dead-shorts-weekly-probe-2026-09-22`, `dub-spoken-text-gate-shadow-2026-09-22`,
`traffic-mix-instrument-2026-09-22`; guards
`tests/test_youtube_policy.py::{TestEnOneShortCap,TestDeadShortsTier}`,
`tests/test_multilingual.py::TestDubSpokenTextGate`): **EN ships ONE Short per
episode, the hook** (`MAX_SHORTS_PER_CHANNEL`, enforced on EVERY path); an
experiment shipped into a distribution drop is INCONCLUSIVE with the
confound named, never a MISS. [history](docs/claude_md_history/2026_09_22_shorts_reach_fell.md)

**Oct 3 2026** (guards `tests/test_show_review_2026_10_03.py`,
`tests/test_dub_short_titles_2026_10_03.py`): **rebuild a daily series from
the snapshot history before calling a trend**; **a dub window-Short title
never ships `is_fragment_title`**; **the sibling plug's cadence word comes
from `engine.cadence`**. [history](docs/claude_md_history/2026_10_03_august_peak_was.md)

**Oct 4 2026** (guards `tests/test_sunday_slate_2026_10_04.py`): the weekly
newsletter run has `send_preflight`, an `always()` commit step and the most
recent SUNDAY as its default week; the Sunday week-in-review goes before the
close only (⚠️ AUDIO); **read a model arm from the credit files' per-call
`model`, never from config**. [history](docs/claude_md_history/2026_10_04_sunday_slate.md)

**Oct 5 2026** (guards `tests/test_slate_review_2026_10_05.py`): a numeric
header date is read only for a host listed with proof of its order
(`_NUMERIC_HEADER_DATES`); **no surface says Mira phones guests**; a
`brand_color_dark` must clear 4.5:1 on the newsletter card. ⚠️ AUDIO. [history](docs/claude_md_history/2026_10_05_monday_slate.md)

**Oct 5 2026 — Grok reviews, acted on** (guards
`tests/test_review_followups_2026_10_05.py`): **the review writer copies each
ledger's own list indentation** and every ledger is parsed in CI; a Grok
review's claim is checked against the committed text before it is acted on. [history](docs/claude_md_history/2026_10_05_five_grok_reviews.md)

**Oct 6 2026** (guards `tests/test_slate_2026_10_06.py`): **a benchmark window
reaches the entry bar, never narrower than a month**; **a missing alpha is
never a zero**; **the MIT hook's analysis blocks fail one at a time**;
**the claims metrics record what SHIPS**. [history](docs/claude_md_history/2026_10_06_first_slate_after.md)

**Oct 8 2026 — no transcripts on the whole slate, again** (guards
`tests/test_{transcripts_pyav_2026_10_08,youtube_session_restart_2026_10_08}.py`,
`tests/test_{chapters_lead_2026_10_08,review_followups_2026_10_08}.py`):
**Whisper never decodes through PyAV**; the `av<19` ceiling stays. **Never
merge a dependency bump on a red `Run Tests`**, and read the comment above a
pin before moving it. **A spoken sentence is a chapter title only when it
fits whole**; a missing chapter never blocks an episode. **A hook may name
only what an item reports.** **Never use a real show as a fixture for a state
it will leave** (`conftest.unpublished_show`). [history](docs/claude_md_history/2026_10_08_no_transcripts_again.md)

**Oct 9 2026 — the runner upgrade.** **Every job pins `runs-on:
ubuntu-26.04`**; a runner ffmpeg bump is a render-smoke question, not a
label edit. **The scheduler Worker holds ONE cron trigger** (the account is
on Workers Paid now, Oct 23). Guards `tests/test_scheduling_punctuality.py`. [history](docs/claude_md_history/2026_10_09_runner_upgrade.md)

**Oct 9 2026 — four operator items** (register `spacex-script-grok46-2026-10-09`,
`ops-bundle-2026-10-09`; guards `tests/test_ops_bundle_2026_10_09.py`):
**the ZH track is off** on tesla, spacex and FF (the `*.zh.rss` feeds are
frozen, not deleted); **the Voices Worker holds ONE cron trigger**; the
`av>=19` Dependabot ignore stays. [history](docs/claude_md_history/2026_10_09_four_operator_items.md)

**Oct 9 2026 — the narrative shows get sources** (register
`narrative-research-2026-10-09`; guards `tests/test_narrative_research_2026_10_09.py`):
`narrative_research: N` runs ONE web search into both `*_episode.txt`
prompts as `{research_sources}`; an empty search never skips an episode;
**the claims gate never verifies against the search model's summary**. [history](docs/claude_md_history/2026_10_09_narrative_shows_get.md)

**Oct 9 2026, network improvement review** (guards
`tests/test_verify_analytics_snapshot_2026_10_09.py`): the multilingual
resolve step reads the triggering run's jobs — `workflow_run.head_commit`
is the tip the run STARTED on, never the generated commit. [history](docs/claude_md_history/2026_10_09_network_improvement_review.md)

**Oct 9 2026 — review items 9–13** (register `structural-regen-2026-10-09`,
`probe-tier-imagery-2026-10-09`, `x-accounts-rotation-2026-10-09`,
`x-on-spacex-daily-aoai-2026-10-09`; guards `tests/test_review_items_9_13_2026_10_09.py`,
`tests/test_sdk_httpx_2026_10_09.py`): **the stream reader imports the SDK's
own HTTP module** (`engine.generator.sdk_httpx`); no production module imports
`httpx` by name. **A regeneration the pipeline cannot repair is not a
structural defect**. **Nerra Daily and
The Age of AI post from the network account** (`engine.x_post`; unset secrets
= `x_post_skipped: no_credentials`). [history](docs/claude_md_history/2026_10_09_review_items_9.md)

**Oct 10 2026 — listener noise** (register `listener-noise-2026-10-10`;
guards `tests/test_listener_noise_2026_10_10.py`): **`engine/listener_noise.py`
removes, in code and network-wide, what a prompt already banned**; the
reader-only `### The Tape` never reaches the script; re-run the full sweep
before widening a pattern. The Patrick disclosure line stays as is (operator
decision; do not change it unasked). ⚠️ AUDIO. [history](docs/claude_md_history/2026_10_10_listener_noise.md)

**Oct 11 2026 — a narrative show writes only from sources** (register
`slate-2026-10-11`; guards `tests/test_slate_2026_10_11.py`):
**`narrative_research_min: 2`** on UC and FPD — a thin search skips
`narrative_research_thin`, never a case from memory. **@grok is a research
desk, never a source** (`engine/grok_leads.py`; never an article, a Source
line or claims evidence). ⚠️ AUDIO. [history](docs/claude_md_history/2026_10_11_narrative_show_writes.md)

**Oct 11 2026 — sponsor-ready** (register `sponsor-ready-2026-10-11`,
`signup-measurement-2026-10-11`, `narrative-queue-source-audit-2026-10-11`,
`fr-dub-gate-enforce-2026-10-11`; guards `tests/test_sponsor_ready_2026_10_11.py`):
**no free surface says "ad-free"** — ad-free is reserved for subscribers and
paid content, and that copy lives in `engine.brand`. **`engine.brand` owns the
sponsor policy** (a template that types a rule fails CI). The spoken-text gate
ENFORCES on French tracks only (`CALIBRATED_LANGUAGES`). [history](docs/claude_md_history/2026_10_11_sponsor_ready.md)

**Oct 11 2026 — script-stage models** (register `narrative-script-grok47-2026-10-11`,
`planetterrian-script-grok46-2026-10-11`, `flagship-script-grok46-2026-10-11`,
`mit-script-grok46-2026-10-11`, `models-agents-script-grok46-2026-10-11`,
`review-triage-2026-10-11`; guards `tests/test_script_models_2026_10_11.py`,
`tests/test_review_triage_2026_10_11.py`): every digest stays grok-4.3. **The
script call has its own effort** (`llm.podcast_reasoning_effort`) and every
follow-up script call carries the same effort and stream. **Streaming is the
network default** (no show may opt back out). ⚠️ AUDIO. [history](docs/claude_md_history/2026_10_11_script_stage_models.md)

**Oct 12 2026** (register `slate-2026-10-12`; guards `tests/test_slate_2026_10_12.py`):
**model control tokens are stripped wherever model text comes back**;
**a shared Source URL is a duplicate only when the items share the story**;
**a hook titles a lead chapter only whole**; **network plugs read the
SPEAKING show's cadence**; **Привет, Русский! closes in Russian**. ⚠️ AUDIO. [history](docs/claude_md_history/2026_10_12_first_slate_pinned.md)

**Oct 12 2026 — SpaceX story chapters and @grok leads** (register
`spacex-story-chapters-and-grok-leads-2026-10-12`): a `known_sections_only`
show's story chapters use the headline whole — never a clipped title;
`scripts/probe_x_search.py` is read before changing an x_search request. [history](docs/claude_md_history/2026_10_12_spacex_story_chapters.md)

### Anthology books — ebook + audiobook from the narrative shows (Aug 2026)

[history](docs/claude_md_history/2026_08_anthology_books.md); doc [`docs/books.md`](docs/books.md); guards `tests/test_book_compiler.py`.
Author **Patrick Novak**; `volume_chapters` never 20; published volumes never change. Text transform is **deterministic — no LLM**; art is on **pinned** `grok-imagine-image-quality` (never a floating alias); book gallery uploads carry an `intended_use` the video scene selector must NEVER match. Chapter titles are CURATED, never the hook (`engine.titles.BOOK_CHAPTER_TITLE_MAX`); EVERY reader-facing link goes through `engine.funnel` `kind="book"`; artifacts to R2 `books/<id>/` ONLY; **the EPUB embeds display-size images only** (tune the `EPUB_*` constants, never `EPUB_MAX_BYTES`). **Store-level digital-narration DECLARATIONS are non-negotiable** (never remove any). **Store links live in the volume YAML** (never hand-edit the catalog for links). **Audiobook masters reach the operator only via Actions "Export audiobook"** (never a download URL in CI).

### Site-showcase video endings (Aug 2026, operator-directed)

[history](docs/claude_md_history/2026_08_site_showcase_video.md); register `site-outro-cards`; guards `tests/test_site_showcase.py`.
Every long-form video ends on an outro card from committed `assets/site_screens/` (`engine/promo_card.py`, `PLACEMENT_OUTRO`); the render never hits the network; best-effort, outside landmine #17.

### Adaptive YouTube publishing policy (July 2026)

[history](docs/claude_md_history/2026_07_adaptive_youtube_policy.md); doc [`docs/youtube_feedback_loop.md`](docs/youtube_feedback_loop.md); guards `tests/test_{youtube_policy,youtube_growth_pass,shorts_selector,intros}.py`, `tests/test_ru_dub.py::TestClauseTrim`.
`api/youtube_policy.json` (**Shorts NEVER 0** — they're the recovery signal) via `engine.youtube_policy.resolve_publish_plan`; the policy never edits YAML at runtime and never touches audio. **`shorts_per_episode` follows the computed `short_vpd`, not the tier letter**; every nightly-written file must be in the add-paths whitelist; long-form cuts stay velocity-gated, never blanket. **Every episode opens on its hook** (`build_cold_open_spec`, no example sentence); **Shorts run 35 s**; the ceiling is `MAX_SHORTS_PER_EPISODE`. ⚠️ AUDIO.

### Testing

```bash
pytest                             # Run all tests
pytest tests/test_utils.py         # Pure function tests (AST extraction)
pytest tests/test_rss.py           # RSS feed validation
pytest tests/test_audio_commands.py  # ffmpeg command structure tests
pytest tests/test_integration.py   # Pipeline integration tests
```

Tests use AST extraction + `exec()` to load functions from show scripts because
`tesla_shorts_time.py` has a `SystemExit` guard preventing import.

**Phase 1 hardening guards (May 2026):** the network-evolution roadmap's first
phase added safety nets that the `run-show.yml` smoke step now runs on every
episode:

- `tests/test_generator.py` — the LLM-call path (`load_prompt` incl. the new
  shared-snippet include mechanism, `_call_grok` request/response shaping,
  refusal detection, fallback-model resolution). Catches a breaking Grok
  request/response change without spending credits.
- `tests/test_show_memory.py` — pins `engine.tesla_memory`'s load/save/build
  contract (and the first-run copy-isolation fix) *before* Phase 3 generalizes
  it to other shows via `engine/show_memory.py`.
- `tests/test_prompt_fidelity.py` — every show's prompts exist, are non-empty,
  and render without a malformed-brace crash.
- `tests/test_episode_validity.py` — (Run Tests only since Oct 18 2026; never the per-show smoke step) the latest committed digest per show meets
  a conservative word floor and isn't a refusal.
- `tests/test_pipeline_safety.py` — the three safety scripts below.

### Code Style

- No linter configured; scripts are large single-file programs
- Functions are defined inline (not imported), which is why we're extracting
- `logging` for all output; `sys.stdout` handler
- `pathlib.Path` for all file operations
- `tenacity` for retry logic on API calls

### Prompt composition + pipeline safety scripts (Phase 1, May 2026)

[history](docs/claude_md_history/2026_05_prompt_composition_pipeline.md); guards `tests/test_memory_lake_expansion.py::TestLakeOrchestration`.
`load_prompt` resolves `<<include: path.txt>>` BEFORE `{placeholder}` substitution (`shows/prompts/_shared/`); do NOT bulk-rewrite prompts to use includes without `test_prompt_fidelity.py` + A/B listening. The lake is a rebuild-from-repo cache; `build_search_index.py` REFUSES to overwrite a populated index with an empty one; nightly builds the dashboard AFTER the backfill. `scripts/retitle_youtube_videos.py` rebuilds fragment titles from the DIGEST HEADLINES, never the Short's stored `hook` (dry run by default).

### Growth & trust surface (Phase 2, May 2026)

[history](docs/claude_md_history/2026_05_growth_trust_surface.md); guards `tests/test_phase2_growth.py`.
Source-only web enhancements regenerated by the finalize `--blogs` step (the `ai_badge` macro; the `PodcastEpisode` JSON-LD through `tojson`; share links carry per-source UTM via `with_utm`).

### Grok prompt + voice review (June 10, 2026)

[history](docs/claude_md_history/2026_06_10_grok_prompt_voice.md); guards `tests/test_prompt_quality_pass.py`.
`engine/utils.fix_phonetic_garbles` repairs every digest + script (bans alone don't stop a known finite failure set); Tesla's system prompt forbids filling gaps from training-data knowledge.

### Network-wide show quality pass (June 2026)

[history](docs/claude_md_history/2026_06_network_wide_show.md); guards `tests/test_{network_quality_pass,queue_restock}.py`, `tests/test_cost_efficiency_pass.py::TestLengthLeverPolicy`.
**`podcast_expand_below_target` is `false` on every show with a digest-side lever** (finansy_prosto is the only sanctioned holdout). **Topic-queue restocks are AUTOMATED** (`restock-topic-queues.yml`; a never-invent rule; existing entries never modified; `TestNarrativeQueueRunway` re-runs BEFORE committing — the runway floors are the alarm that the AUTOMATION broke; `NERRA_RESTOCK_MODEL: grok-4.3`). Age of AI's deliberately-empty queue is not registered and must never be.

### Network editorial review (July 2026)

[history](docs/claude_md_history/2026_07_02_network_editorial_review.md); ledgers [`docs/reviews/ledger/`](docs/reviews/ledger/).
**De-seed by shape, never with a quotable example**; guard/retry mechanisms must not degrade the audio they protect.

### Network goals & differentiation audit (July 18, 2026)

[history](docs/claude_md_history/2026_07_18_network_goals_audit.md); guards `tests/test_chapters.py::TestClosingIsFinal`, `tests/test_dp_pod_show.py`, `tests/test_tts_dialogue.py::TestSelfIntroductionRelabel`, `tests/test_review_agent.py`.
**Closing-is-final chapter invariant** (the terminal signal is the closing TITLE set, not the `where: end` anchor). Dashboard voice baseline: Olya `0b875ae2` + sanctioned `ara`. **Playbook rules**: podcast-side length levers are banned network-wide via `do_not_retry`; de-seed-by-shape + rotation memory required; conditional predictions banned; a ledger entry is required for every prediction-bearing pass.

### Flagship review — SpaceX, Tesla, Models & Agents + shared pipeline (Sep 4, 2026)

[history](docs/claude_md_history/2026_09_04_flagship_review.md); guards `tests/test_flagship_pass_2026_09_04.py`.
**A stock quote's VERB comes from the clock, never from which data source answered.** **The spoken price line is never a Shorts opener** (`is_price_line`). **Both prompts can seed a tic** — check every prompt that touches a section before de-seeding one. **Chapter titles never carry links.** **Whitelist globs, not literals** in the committing workflows' add-paths. **Null stays null on the language card.**

### Network delivery review — content density over narration (Sep 5, 2026)

[history](docs/claude_md_history/2026_09_05_network_delivery_review.md); experiment `network-content-discipline-2026-09`; guards `tests/test_delivery_pass_2026_09_05.py`.
**`engine/script_audit.py` is a READ-ONLY instrument** — a rule that changes the script belongs in the prompt or in a gate, never in the audit; **read overlap and coverage together: overlap ≤ 15% AND coverage ≥ 70%; either alone is gamed by the other**. **Memory is for accuracy, never narration.** **Every worked example sentence was removed from the podcast prompts** — "described shape, never a quotable line" applies to EXAMPLE blocks too. **One closing per flagship.** **Sep 12: the rewrite gate is GONE — do not re-add a script retry of any shape.**

### Simplification pass — one generation, enforcement everywhere, audience first (Sep 12, 2026)

[history](docs/claude_md_history/2026_09_12_simplification_pass.md); experiments `combined-generation-2026-09-12`, `source-integrity-strip-network-2026-09-12`, `audience-headline-2026-09-12`; guards `tests/test_{simplification_2026_09_12,network_review_2026_09_17}.py`.
**The digest and the script are written in ONE model call** (`llm.combined_generation`; `combined_script_matches_digest` compares **normalised SENTENCES, never raw lines**). **A combined run can never cost an episode.** **Claims verify against the fetched copy first.** **The audience headline leads every surface a decision is made from** (`api/audience_headline.json`; the current OP3 week is never compared; null where unmeasured, never 0). **A NEW metric names its consumer.** **Check the `Run Tests` conclusion on main before reading a merge as checked.**

### Network prompt + LLM review (July 31, 2026)

[history](docs/claude_md_history/2026_07_31_network_prompt_llm.md).
run_show's junk-title-header regex exempts the identity shapes (`tests/test_intros.py`). `llm.podcast_model` lets one show A/B a script-stage model (the digest never follows it).

### LLM usage review vs the Aug-2026 xAI product state (Aug 18, 2026)

[history](docs/claude_md_history/2026_08_18_llm_usage_review.md); guards `tests/test_llm_usage_pass.py`.
**Any future model upgrade follows [`docs/model_upgrade_playbook.md`](docs/model_upgrade_playbook.md)** — staged one-show-first with a digest-latency gate, never a network-wide day-one flip. Reviewer FACTUAL_ERRORS comparisons from 2026-08-18 on are never against earlier history. Translation is pinned `grok-4.6` — **never put a published stage on a floating alias**; the TTS request has NO model param — spot-listen after major xAI voice announcements.

### Website review (June 10, 2026)

[history](docs/claude_md_history/2026_06_10_website_review.md); guards `tests/test_website_quality_pass.py`.
Absolute `og:image` default in `base.html.j2`; `noindex` on the 404 template.

### Website review (September 3, 2026)

[history](docs/claude_md_history/2026_09_03_website_review.md); guards `tests/test_website_review_2026_09_03.py`.
**The legal/trust pages are TEMPLATES** — never hand-edit the root `ai-disclosure.html` / `privacy-policy.html` / `terms-of-service.html`; the disclosure says plainly that no human reads every episode before it ships. **`--static-pages` is the one flag for every cheap page.** **`<title>` comes from `page_title` OR a `block title`.** **The blog hub renders the newest `NETWORK_BLOG_INDEX_MAX_POSTS` (240)** — do not restore the full list. **Homepage claims are computed, not typed.** ONE delegated mobile-menu close handler. **Mission Control never fabricates a zero.**

### Site + funnel + Mira program (Sep 19–20, 2026)

[history](docs/claude_md_history/2026_09_19_site_funnel_mira.md); guards `tests/test_{site_funnel_pass_2026_09_19,mira_pass_2026_09_20}.py`.
**`engine/brand.py` owns every claim the network makes about itself** (a template that hardcodes the sentence fails CI). **The Mira claim is NARROW on purpose, and widening it is the failure mode.** **The claim never ships without its basis and its correction invitation.** **A show that bypasses `run_show.py` gets none of run_show's publish surface.** **No surface advertises something that does not exist** (`has_feed`). **An internal link never carries a `utm_*` tag.** **`site/redirects.yaml` + `scripts/audit_dead_urls.py` own dead URLs**; a redirect stub is **not** an episode page.

**Sep 20 2026 — `/topics/` hubs: `engine/topic_hubs.py` owns the subject
vocabulary.** **The vocabulary is CURATED (`picker_tags.topics`), never the
search index's auto-mined `topics`**; **episode lists read the COMMITTED
`site/data/search-index.json`, never `data/content_lake.db`**; **every intro
is hand-written**; **a hub under `MIN_EPISODES_FOR_HUB` (12) is not built**
and never linked from a post. [history](docs/claude_md_history/2026_09_20_topic_hubs.md)

**Sep 21 2026 — the capture end of the funnel** (guards
`tests/test_capture_measurement_2026_09_21.py`). **The capture-tag merge is a
UNION, never a replace.** **A signup form that sends no `source` makes
`capture.by_source` structurally impossible** — the tag renders from the
`capture_source_site` global, never a literal. Engagement events are a
SEPARATE report — add the event to the constant when you add the `gtag`
call. **`api/member_metrics.json` counts paid members and carries no PII.**
**The Worker's vitest suite is not run by any workflow** — run `npx vitest`
by hand when you change `workers/`. [history](docs/claude_md_history/2026_09_21_capture_end_funnel.md)

**Sep 21 2026 — the promo rotation** (guards `tests/test_rotation_pass_2026_09_21.py`;
⚠️ AUDIO). **A surface's `spoken` line is PROMPT TEXT, not deterministic
insertion** — a quoted specimen is banned. **The on-air Mira line carries the
NARROW claim and no superlative.** **Pool length must stay coprime with the
offset stride of 3.** [history](docs/claude_md_history/2026_09_21_promo_rotation_mira.md)

**Sep 21 2026 — the registry (C1)** (guards `tests/test_registry_pass_2026_09_21.py`).
**`engine/show_lang.py` owns a show's page language** — never a repeated
literal tuple. **Before deleting a registry key, check the raw-entry readers
as well as the built context.** [history](docs/claude_md_history/2026_09_21_registry_second_owner.md)

**Sep 22 2026 — one card to hear it and read it** (guards
`tests/test_episode_card_transcript_2026_09_22.py`). **A transcript is
collapsed, never withheld, and never the page** (the preview is a LITERAL
prefix, never a reformat of the guest's words). **The bespoke DP Pod page
needs every generic-template change made twice.** The summary-preview walk
exists in `plain_preview` AND the page script — change both or neither. [history](docs/claude_md_history/2026_09_22_episode_card_transcript.md)

**Sep 22 2026 — The Age of AI: the pages say only what the record supports**
(guards `tests/test_age_of_ai_truth_2026_09_22.py`,
`tests/test_review_followups_2026_11_02.py`). **A chapter list is shown only
when the transcript vouches for it.** **Run time comes from the feed's
`itunes:duration`, never from chapters.** **Gate 2 is described as built** —
a week to approve, cut or refuse; takedown afterwards; the guard fails any
surface that claims the stronger gate. **A guard that pins a claim is only as
good as the claim.** [history](docs/claude_md_history/2026_09_22_age_ai_truth.md)

**Sep 22 2026, later** (guards `tests/test_age_of_ai_finish_2026_09_22.py`).
**`engine/brand.py` owns the interview steps** (`MIRA_INTERVIEW_STEPS`; a
template that types a step title fails CI); interview provenance says the
transcript was SENT to the guest, never "approved by". [history](docs/claude_md_history/2026_09_22_age_ai_finishing.md)

**Sep 21 2026 — chrome that scales (C2)** (guards
`tests/test_chrome_pass_2026_09_21.py`). **A source-reading guard must strip
Jinja comments first.** **A chrome guard renders its own page; it never reads
a committed one.** **`show_groups` is the one strand grouping.**
**`/explore.html` filters on the CURATED vocabulary.** [history](docs/claude_md_history/2026_09_21_chrome_that_scales.md)

### Website review (October 7, 2026)

[history](docs/claude_md_history/2026_10_07_website_review.md); register `website-review-2026-10-07`; guards `tests/test_site_review_2026_10_07_{chrome,blog,trust,dashboards,gallery_player}.py`.
**A brand colour is never TEXT on the dark surfaces** (`--show-color-text` / `--card-accent-text` / `--nn-purple-text`). **The guest's terms are stated as built, everywhere a guest or reader sees them** — never "nothing publishes until you approve". A per-show gallery never falls back to the full manifest.

### The site's languages: an English front page, one hub per language (Oct 18 2026)

[history](docs/claude_md_history/2026_10_18_site_languages.md); guards `tests/test_site_languages_2026_10_18.py`.
**`engine/show_lang.py` owns the SITE LANGUAGES** (the one reading of `multilingual.languages`). **The English homepage reads English shows only.** **`<lang>/index.html` is generated for every non-English site language** (`ru/index.html` is no longer hand-written); **every reader string is hand-written in `_LANGUAGE_HUB_COPY`**; the English topic hubs are never linked from a hub.

### The media kit (Oct 21 2026)

[history](docs/claude_md_history/2026_10_21_media_kit.md); guards `tests/test_media_kit_2026_10_21.py`.
**`press.html` is the media kit** (a dash, never 0, when unmeasured; YouTube age bands only, never gender; a flag that is off is never promised); **`engine.brand` owns the copy** (`GROWTH_NEXT` is never a forecast).

### The advertising and sponsorship kit (Oct 21 2026)

[history](docs/claude_md_history/2026_10_21_sponsorship_kit.md); guards `tests/test_sponsor_kit_2026_10_21.py`.
**`engine.brand` owns the rate card** (a template that types a price, a package or a term fails CI); **each package prints its MEASURED reach** and never a forecast; **only free shows are for sale** — never on an interview show; nothing about rates is ever sent automatically; no surface dates the network to 2024.

### The front page and the share cards (Oct 18 2026)

[history](docs/claude_md_history/2026_10_18_front_page_share.md); guards `tests/test_{homepage_landing_2026_10_18,share_cards_2026_10_18}.py`; doc `docs/landing_test.md`.
**`index.html` is the front page** (`generate_network_page`). **`engine/newsroom.py` owns the news behaviour.** **`engine/share_cards.py` owns every link preview** through ONE Jinja global, `resolve_og_image`; **a template never writes its own `og:image`**. **Episode cards are never committed** (landmine #1); the hook budget is `engine.titles.SHARE_CARD_HOOK_MAX` (`clip_words`, never a slice).

### The tagline and the promise lead (Oct 18 2026)

[history](docs/claude_md_history/2026_10_18_tagline_promise.md); guards `tests/test_brand_messaging_2026_10_18.py`.
**`engine/brand.py` owns both sentences** (`NETWORK_TAGLINE` "Feed your curiosity, not your anxiety.", `network_promise(n)`; a template or card that types them fails CI). **N is the FREE shows**, never `len(NETWORK_SHOWS)`. **`engine.brand.FLAGSHIP_SHOW_SLUGS` (`spacex`, `tesla`) is the one list** (a flagship never also runs as the lead, a top story or a section story).

### YouTube and X review — the decline, and the surfaces that ask for the subscribe (Oct 24 2026)

[history](docs/claude_md_history/2026_10_24_youtube_x_review.md); register `youtube-x-review-2026-10-24`, `long-with-short-2026-10-25`, `shorts-subscribe-pill-2026-10-25`; guards `tests/test_{youtube_x_review_2026_10_24,long_with_short_and_pill_2026_10_25}.py`.
RU reach is a Studio read, not a pipeline fix. A sub-10 s chapter is dropped (the 0:00 anchor never moves; titles never rewritten). **Every X teaser link goes through `engine.funnel`.** **Retention is read at a fixed age.** **Two probe longs can promote a shorts-only show, never a demotion.** **The long-form goes public in the hook Short's slot** (`LONG_AFTER_SHORT` 0 on purpose). **Every EN Short carries a persistent subscribe pill** (the dubs are the control).

### The hook Short skips the map (Oct 30 2026)

[history](docs/claude_md_history/2026_10_30_hook_short_skips.md); register `shorts-skip-map-2026-10-30`; guards `tests/test_short_skips_map_2026_10_30.py`.
**The hook Short renders from a spliced source** (`engine/short_furniture.py`; any failure renders as before; `youtube.shorts_skip_map`). **The episode, its feed audio and its long-form keep the map.**

### A Short never crops the show's own cover (Nov 4 2026)

Guards `tests/test_short_cover_card_2026_11_04.py`.
**A square cover is never centre-cropped to 9:16**: the Shorts cover fallback (every X-only clip) renders `engine.video._vertical_cover_card` — the whole cover inside the push-in margin over a blurred fill — and the opening hook moves below it (`_COVER_CARD_HOOK_Y_FRAC`). **The Shorts show pill grows to fit the name up to `_SHORT_SHOW_PILL_MAX_W`** and never reaches the subscribe pill on its row.

### The dub hook Shorts skip the map too (Nov 1 2026)

[history](docs/claude_md_history/2026_11_01_dub_hook_shorts.md); register `dub-shorts-skip-map-2026-11-01`; guards `tests/test_dub_shorts_skip_map_2026_11_01.py`.
**The dub map is found by POSITION, never by language cues.** **Its edges come from the dub track's own Whisper words, matched by letters** (`dub_norm`); any refusal renders as before. **The dub long-form, the language feeds and the episode keep the map.**

### YouTube pipeline pass (June 10, 2026)

[history](docs/claude_md_history/2026_06_10_youtube_pipeline_pass.md); guards `tests/test_youtube_quality_pass.py`.
**The silent config-drop class**: `_build_nested` warns loudly on YAML keys the dataclass does not declare.

### Scheduled Show Review Agent (June 2026)

[history](docs/claude_md_history/2026_06_scheduled_show_review.md); setup [`docs/REVIEW_AGENT.md`](docs/REVIEW_AGENT.md); state [`docs/reviews/review_state.yaml`](docs/reviews/review_state.yaml); ledgers [`docs/reviews/ledger/`](docs/reviews/ledger/); guards `tests/test_review_agent.py`.
`show-review.yml` reviews ONE target per run following [`.claude/commands/review-show.md`](.claude/commands/review-show.md); output is always a **draft PR** — the operator's merge is the ship gate (landmine #17). **The loop is recursive**: every review appends `predictions:` the NEXT review must score and a `do_not_retry` list (closed-unmerged PRs and reverts are never re-proposed). **The scheduled job runs on Grok** (proposals only); the ledger writer appends by **text-splice**, never a reserialize. Scoring predictions is required of EVERY pass that writes a review doc with predictions.

### Recursive narrative memory generalized (Phase 3, May 2026)

[history](docs/claude_md_history/2026_05_recursive_narrative_memory.md); guards `tests/test_{phase3_memory,show_memory,memory_lake_expansion,story_recurrence}.py`.
`engine/show_memory.py` (`SHOW_MEMORY_CONFIGS`; MIT's `investment_tracker` stays authoritative for results); Tesla keeps `engine/tesla_memory.py`. **Flag-gated, single placeholder** `{narrative_memory_section}` — **disabled is a true byte-for-byte no-op**. **Story-recurrence memory** (`engine/story_recurrence.py`) annotates update-don't-retell — never a ban; deterministic, no LLM.

### Per-show repositioning + per-episode blog title (Phase 4 partial, May 2026)

[history](docs/claude_md_history/2026_05_per_show_repositioning.md); guards `tests/test_phase4_repositioning.py`.
Omni View → "Steel Man"; Финансы Просто → women-in-finance-in-Canada; Привет, Русский! → vocabulary-first; Environmental Intelligence → all-province + "Compliance Brief". `engine/blog.py` uses the hook as the per-episode title.

### Multi-platform Shorts distribution (Instagram Reels / TikTok, May 2026)

[history](docs/claude_md_history/2026_05_multi_platform_shorts.md); doc [`docs/social_distribution.md`](docs/social_distribution.md); guards `tests/test_social_distribution.py`.
Opt-in per show (`youtube.multi_platform_enabled`, default false → no-op); best-effort, additive, non-fatal (`engine/social_distribution.py`).

### Audience-growth pass (June 2026)

[history](docs/claude_md_history/2026_06_audience_growth_pass.md); contract [`docs/analytics.md`](docs/analytics.md); guards `tests/test_{op3_stats,connector_budget}.py`.
`engine/connector_budget.py` budgets the Spotify/Apple fetches — a budget stop never shrinks the file. **The OP3 prefix is applied by each publish path, never by `update_rss_feed`** (never rewrite a live enclosure); an OP3 404 is an indexing lag unless it persists for weeks. **There are deliberately THREE curated cross-show mappings** (web `related_show`, email `newsletter.network_adjacencies`, audio/X `engine/network_promo.ENGLISH_SHOWS`) — **do not consolidate casually**. Known wart: the Russian shows speak the ENGLISH `_AI_DISCLOSURE` line (landmine-#17 A/B).

### Multilingual + international distribution (late June 2026)

[history](docs/claude_md_history/2026_06_multilingual_distribution.md); docs [`docs/multilingual.md`](docs/multilingual.md), [`docs/ru_youtube_dubs.md`](docs/ru_youtube_dubs.md), [`docs/lang_youtube_dubs.md`](docs/lang_youtube_dubs.md), [`docs/video_podcasts.md`](docs/video_podcasts.md); guards `tests/test_{multilingual,language_feeds,ru_dub,lang_dub,video_podcast,youtube_feedback_loop}.py`.
English is the canonical master and the fallback everywhere. A channel invisible to the analytics loop can never earn a promotion. **Video podcasts → Apple**: **the audio feeds are never touched and no published enclosure URL changes**; `content_type="video/mp4"` EXPLICITLY on upload and enclosure; R2 key `video/<slug>/…` outside the audio keyspace; NOT OP3-prefixed. **The YouTube → titles loop** touches ONLY the YouTube title.

## Refactoring record

The engine/ extraction (Phases 1–3) is complete: every show runs via
`run_show.py` + YAML in production, and the legacy
`digests/{tesla_shorts_time,omni_view,fascinating_frontiers,planetterrian}.py`
scripts are **deprecated** — retained for reference, called by no workflow or
cron. Module inventory: [history](docs/claude_md_history/2026_02_refactoring_goal_engine.md).

## Known Landmines

**Sitemap `lastmod` must not follow file mtime.** Blog post files are
rewritten by every regeneration; the episode date is not. If `lastmod`
tracks mtime, a network-wide regen tells Google all ~1,250 posts changed
at once, which is the exact signal the May 2026 audit removed.
`generate_sitemap()` reads `datePublished` out of each page's JSON-LD.
Do not "simplify" it back to `_file_lastmod`.

**`digests/_newsletter_sending_blocked.json` silently skips the
newsletter for 7 days.** If newsletters stop going out, check for that
file before debugging Buttondown.

**A queued Actions run checks out the SHA fixed at TRIGGER time.** Any
guard that reads committed state (the weekly newsletter's per-week
sent markers, skip markers, cooldown annotations) is blind in a run
that queued behind another in a concurrency group unless the job
first moves its workspace to the live tip (`git fetch --depth=1
origin main && git reset --hard origin/main`). Sep 6 2026: the late
Sunday cron queued behind a manual dispatch, ran twenty minutes later
on a tree from before that dispatch committed its markers, and
re-sent six shows' weeklies. `weekly-newsletter.yml` now syncs first;
guard: `TestWeeklyNewsletterSameWeekGuard`.

**Show slugs use underscores, page filenames use hyphens.**
`fascinating_frontiers` → `fascinating-frontiers.html`. Getting this
wrong in `publishing.rss_link` 404s the "website" button in every
podcast directory, and nothing in the pipeline fetches its own
`rss_link` to notice. `validate_show.py` now checks it.

**Operator's first stop:** the live state of every landmine below is rendered
by [`management.html`](management.html), fed by
[`scripts/generate_dashboard.py`](scripts/generate_dashboard.py) → `api/dashboard.json`.
The dashboard's **Growth levers** section (Aug 2026) renders the per-channel
WoW scorecard, staggered-Shorts/sweep health, the specials queue, analytics
freshness (alerts past 36h — the Aug 6 outage staleness lesson), and the
experiments register: **every change shipped to move a number gets an entry
in [`docs/experiments.yaml`](docs/experiments.yaml)** with its readout date
and (where supported) a live metric key — a typo'd metric name fails CI
(`tests/test_dashboard_growth.py`).

The page carries **three views** (Aug 2026): Operator (everything),
Sponsor (`?view=sponsor` — audience + catalogue, no spend/valuation) and
**Investor** (`?view=investor` — audience, unit economics, industry
benchmarks and now/1yr/5yr value scenarios). Every external market figure
(percentile ladder, CPMs, production costs, M&A multiples) lives ONLY in
[`docs/industry_benchmarks.yaml`](docs/industry_benchmarks.yaml) with
sources + an `as_of` date the page renders; the generator's
`build_benchmarks_section` / `build_investor_section` compute placement
and scenarios from the same audience/cost sections the rest of the page
uses. Honesty rules: episode denominators come from RSS pubDates (credit
files count dub tracks and overstate episodes), unmeasured = null never 0,
projections are labelled scenarios with their assumptions serialized next
to them. Drift guards: `tests/test_investor_dashboard.py`.
Items 7 and 10 are intentionally excluded from the dashboard (per an explicit
decision); everything else has a live status card.

### Active Issues

1. **2.2 GB of MP3s in git HISTORY (HEAD is clean)** — measured June 10
   2026: zero episode MP3s are tracked at HEAD (guards in `.gitignore` +
   the commit step's `git reset -- '*.mp3'`; only the 43 MB of
   `assets/music` themes + two voice-reference WAVs remain, which the
   pipeline needs). All enclosure URLs serve from R2. CI clones are
   shallow since the June 2026 workflow pass (~115 MB packed vs ~2.5 GB
   full), so the day-to-day clone cost is FIXED and growth is now
   text-only (~50 MB/month → years of headroom under GitHub's 10 GB
   limit). The history weight itself can only be removed by a
   `git filter-repo` rewrite + force-push of main — DESTRUCTIVE:
   requires a paused-cron window (12 daily workflows push to main and
   could race the force-push and resurrect old history), invalidates
   every existing clone, and dangles the commit SHAs referenced across
   docs/. Playbook in
   [`docs/workflow_review_2026_06_10.md`](docs/workflow_review_2026_06_10.md);
   operator-scheduled, not urgent. For full local clones meanwhile:
   `git clone --filter=blob:none` skips historical blobs.
2. **Git LFS breaks RSS** — `raw.githubusercontent.com` returns pointer files
   for LFS-tracked content. Do NOT use LFS for MP3s.
3. **Historical TST/OV flat files in `digests/`** — ~220 legacy output files
   (MP3s, markdown, JSON, HTML, TXT) remain at the `digests/` top level from
   before shows were migrated to subdirectories. These cannot be moved without
   breaking existing RSS feed URLs. New episodes now write to subdirectories.
23. **GitHub push transients on large text commits ("fatal error in commit_refs")** —
    Successful episode generation (run_show.py) can produce 8k–10k+ line commits
    (full Whisper transcripts JSON+txt, _tts.txt, metrics, chapters, digests, blog
    HTML, RSS updates). GitHub's ref-update service occasionally returns a server
    error during `git push origin main` even after the pack is accepted. The
    4-attempt rebase/merge loop in `.github/workflows/run-show.yml` handles
    normal concurrency races between matrix jobs. On final exhaustion the step
    now calls `scripts/create_recovery_pr.sh` which creates a `recovery/<show>-<run_id>-<ts>`
    branch, pushes it, and opens a **draft PR** with the complete artifacts plus
    operator instructions. The job exits 0 (data preserved). The PR appears in
    the repo for the operator to merge. This is the hardened path for the
    "Commit and push output" step (the finalize shared-pages push has a 5-attempt
    loop + warning but no recovery PR because those pages are fully regenerable).
    The `safe-commit-push` composite now has an opt-in `recovery-on-failure`
    input wired for the two callers whose commits are expensive to regenerate
    (nightly maintenance, topic-queue restock); the other composite callers
    deliberately stay fail-visible because their artifacts are regenerable
    (stale note corrected 2026-08-15). The multilingual
    sweep's commit step (`.github/workflows/multilingual.yml`) also uses the
    recovery-PR escape hatch now, since it commits large translation-track +
    per-language-feed diffs on the same push-contended `main`. Drift guard:
    the recovery script + the warning annotation in the Actions log.

24. **Schedule punctuality: exact-time dispatcher + duplicate guard (June
    2026)** — GitHub delivers cron `schedule` events 1-6 h late (Tesla's
    11:00 slot observed starting 13:54). Fix: run-show crons moved to
    off-peak :07/:37; `workers/scheduler/` (Cloudflare Cron Trigger,
    fires to the minute) dispatches each show via `workflow_dispatch` at
    its intended slot once the operator deploys it (fine-grained PAT →
    `wrangler secret put GITHUB_DISPATCH_TOKEN`, `wrangler deploy` — see
    its README); the gate's same-day duplicate guard (checks today's
    "Auto-generated: <show> <date>" commit) lets the delayed GitHub cron
    coexist as fallback without double-publishing. The Worker's SLOTS
    table must stay in sync with the gate's CRON_MAP —
    `tests/test_scheduling_punctuality.py` fails CI on drift.
    **What FIRES is what was last deployed, not what is committed** (Sep
    24 2026): a `wrangler deploy` from a checkout that predated the
    launch-cohort PR left nine new shows off the live slot table while the
    cron string already covered their hours, so every old slot fired on
    the minute and no new one did until GitHub's hours-late fallback. The
    Worker's `GET /` lists the live `slots`; `scripts/check_scheduler_deploy.py`
    diffs them against `src/index.ts` nightly once the repo variable
    `SCHEDULER_STATUS_URL` is set. Same day: the dispatcher now honours
    `FIRST_RUN` (Peptides Ep2 fired a week early — only the status page's
    `next_slot` had checked it, and a `workflow_dispatch` skips the
    workflow's own launch-date gate by design).

25. **The TTS engine can speak text we never sent — the spoken-text gate
    is the only thing standing between that and a listener (Sep 14
    2026, Tesla Ep605).** The first 45 s of the published Ep605 are Grok
    TTS reading its own text-normalizer's chain of thought in the host's
    voice ("One thing, the input has line breaks, preserve them … Rules.
    Do not convert at sign in code … So the output should be the entire
    text unchanged") in place of the hook and the identity line. The
    saved `_tts.txt` was clean: the defect was injected SERVER-SIDE by
    the `text_normalization: true` LLM stage (the same component that
    merged "S P C X" into "S&P CX" on SpaceX Ep051), and every check the
    episode passed measured something else — `tag_leak_detector` is a
    registry of tag WORDS (read 0), the opt-in `validate_transcription`
    scores the WHOLE episode (a 50-word leak in 1,083 scores ~0.9), and
    `script_audit` reads the script, never the audio. It shipped to RSS,
    both Shorts (the hook-first Short IS the leak), the Apple video feed
    and Nerra Daily Ep025. Unique across 1,709 committed transcripts.
    Now: `engine/spoken_text_gate.py` compares the Whisper transcript
    (already produced for every episode, BEFORE mix and publish) with the
    in-memory script — the opening must match (`opening_match` ≥ 0.5;
    Ep605 0.17, healthy floor 0.67) and no run of ≥ 40 spoken words may
    be absent from the script (Ep605 61, legit max 22) — with Whisper's
    own artifacts filtered first (a >6 words/s segment is a
    hallucination, M&A Ep140; an n-gram looped >3× is collapsed, MIT
    Ep162). A failure re-runs the IDENTICAL synthesis once
    (`_synthesize_raw_mp3()` closure; the defect does not repeat), a
    second failure SKIPS the episode (`_skip_episode("spoken_text_gate")`).
    `tts.spoken_text_gate: enforce` network-wide; `shadow` on the two
    Russian shows and forced for any non-English transcript (Whisper
    writes Привет's English halves as Cyrillic sound-alikes — the
    instrument is not calibrated there). A missing transcript never
    blocks; it records `no_transcript` and warns that the audio is
    unverified. Metrics `spoken_text_gate*` per episode; calibration
    re-run with `scripts/audit_spoken_text.py` BEFORE moving a
    threshold. Also: `tts.apply_text_normalization` now reaches the Grok
    request (`"off"` → `text_normalization: false`; it was hard-wired
    true) — it stays ON because residual digits (14.3.8, B1081, 845km)
    still reach the TTS text daily and switching it changes shipped
    audio on every show (landmine #17). **Not covered yet:** the FR/RU/ZH
    dub tracks and the RU/FR YouTube dubs use the same request and are
    never compared with their text.
    **Repairing such an episode: never clip, always re-synthesize**
    (Sep 15 2026). The leak REPLACES content — Ep605 never spoke its
    hook, identity line or the two opening sentences of its lead story,
    and the audio resumes mid-sentence — so cutting the defect ships an
    episode that opens on a fragment, for the same downstream cost as a
    re-run. `scripts/resynthesize_episode.py` + Actions
    **"Re-synthesize Episode"** re-run the committed `_tts.txt` through
    the same synthesis: dry-run by default, **uploads to the SAME R2
    key** so no subscriber is re-pointed, and **refuses to upload audio
    the spoken-text gate has not passed** (one retry, then abort — the
    repair tool must never become another way to ship the defect).
    Chapter titles reproduce exactly and only timestamps move; the feed
    item keeps its published title and description and is corrected for
    duration and byte length. It does not touch YouTube (the API cannot
    replace a video's file) — it computes the defect's time span and
    says per video whether to delete or KEEP, because a Short whose clip
    sits past the defect is fine and **the RU/FR dubs are a separate
    synthesis of the translated script and are never affected** (an
    earlier draft listed all eight Ep605 videos for deletion; guard
    `test_dub_videos_are_never_listed_for_deletion`). Guards:
    `tests/test_resynthesize_episode.py`.
    Review: [`docs/reviews/tesla_ep605_spoken_text_gate_2026_09_14.md`](docs/reviews/tesla_ep605_spoken_text_gate_2026_09_14.md).
    Guards: `tests/test_spoken_text_gate.py`.

### Resolved Issues (Feb 2026)

Items 4–13 in full: [history](docs/claude_md_history/2026_02_resolved_issues_4.md).

4–8. Output dirs under `digests/<show>/`; the nested `digests/digests/`
   path, the `_formatted.md` duplicates and the `NEWSAPI_KEY` secret are gone
   (`test_no_newsapi_in_active_workflow()`); `run_show.py` uses CLI flags.
9. **ElevenLabs tuning baseline lives in `shows/_defaults.yaml`**; the earlier
   baseline (stability `0.65`, similarity boost `0.9`, style `0.85`) should
   not be reintroduced without updating `_defaults.yaml`.
10–13. Early episodes deleted; **all shows on Grok TTS** (English
    `kdif6sqjcyiq`, Russian Olya `0b875ae2`; ElevenLabs rollback-only — see
    #16, #17); summaries live in `digests/<show>/summaries_*.json`; **the LLM
    default is `grok-4.3`** with the refusal fallback on `grok-4.20-reasoning`.

14. **YouTube slideshow imagery is curated, not derived from `keywords:`.**
    Every show's `youtube:` block declares `image_queries:`;
    `image_safe_skip_terms` filters off-topic results (`pexels_photos_filtered`);
    `test_every_show_yaml_has_image_queries` blocks a new show without them.
    [history](docs/claude_md_history/2026_05_landmine_14_youtube.md)

15. **YouTube Podcasts surface requires manual Studio setup, not API** (flag
    each playlist as a podcast in Studio once; the Data API has no endpoint
    for the flag). **One-time setup per playlist — not a code change.**
    [history](docs/claude_md_history/2026_05_landmine_15_youtube.md)

16. **TTS network default is Grok TTS** (`provider: grok` in `_defaults.yaml`;
    `engine/tts.py:synthesize()` dispatches on `provider`; the legacy
    ElevenLabs settings stay as a one-line flip back;
    `_validate_environment` gates the ElevenLabs key check on
    `provider == "elevenlabs"`). Guards `tests/test_tts_grok.py`.
    [history](docs/claude_md_history/2026_05_landmine_16_grok.md)

17. **Full-network voice migration + broadcast-quality audio pipeline (May
    2026).** Every English show inherits `kdif6sqjcyiq` from `_defaults.yaml`;
    `ELEVENLABS_API_KEY` and the legacy settings are **kept** for rollback.
    Guards `tests/test_tts_grok.py`. Rules that bind
    ([history](docs/claude_md_history/2026_05_landmine_17_voice.md)):
    - WAV at 48 kHz with `text_normalization: true`; one MP3 encode at the end.
    - **The voice EQ chain (`engine/audio.py:_voice_norm_full_cmd`) never had
      a 6.5 kHz de-ess dip — do not "restore" it**; de-essing was **declined**
      on a listen; re-open only with listening evidence, not spectra.
    - **Final mix** (`_final_mix_cmd`): sidechain-ducked music + loudnorm to
      **-16 LUFS**.
    - Every non-TTS consumer runs through `engine.utils.strip_speech_tags()`;
      letter-by-letter acronym expansions (`TSLA` → `T S L A`) are **kept**.
    - **Re-introduce ANY phonetic respelling or programmatic tag injection
      ONLY with A/B listen-test evidence on the custom voice, on at least 3
      different show contexts.** Theory-driven changes have a 100% regression
      rate on this voice.
    - **`<fast>` is applied via SINGLE-CALL synthesis only**: `speech_wrap_open:
      "<fast>"`, `speech_wrap_close: "</fast>"`, `use_section_tts: false`,
      `max_chars: 14000` are a *coupled set* — flipping any one without the
      others re-introduces the per-chunk tag leak; `_speak_with_grok` DROPS the
      wrap with a loud warning when a script splits into multiple chunks.
      Guards `test_{default_tts_config_dataclass_has_no_chunk_wrap,network_default_has_fast_wrap_and_single_call,speak_with_grok_drops_wrap_on_multi_chunk,speak_with_grok_keeps_wrap_on_single_chunk}`.

18a. **Newsletter dark-mode CSS must stay SCOPED (v3)**: every color rule
    inside the dark-mode block is scoped under the `.nn` marker class
    (`_scope_nn`); the `color-scheme: light dark` opt-in stays. Guards
    `tests/test_newsletter_template.py::TestDarkModeScoping`.
    [history](docs/claude_md_history/2026_06_landmine_18a_newsletter.md)

18. **Newsletter pipeline spec v2 (May 2026).** `engine/newsletter_sanitizer.py`
    (the `assert_clean` tripwire blocks send); `engine/url_utils.py`;
    `engine/newsletter_body.py`; `engine/contrast_validator.py` (a soft
    warning); `send_show_newsletter` uses `build_subject_line(hook_max_chars=50,
    is_daily=True)` and a **20-hour same-show double-send guardrail**
    (`digests/<slug>/_newsletter_lastsend.txt`). The gates log loudly — chase
    the upstream cause. [history](docs/claude_md_history/2026_05_landmine_18_newsletter.md)

19. **Schedule overhaul + weekly-summary segment.** **The full Sunday
    weekly-recap mode is RETIRED**: `weekly_summary_segment: true` shows
    include ONE "week in review" segment on Sunday
    (`engine.weekly_recap.build_weekly_summary_segment`), appended to the
    **podcast-only** copy of the digest — NOT to the published `x_thread`, so
    no instruction text reaches blog / RSS / newsletter. The retired
    machinery must not return. Guards `tests/test_schedule.py`,
    `tests/test_weekly_summary_segment.py`. Sunday prompt changes are
    landmine-#17 A/B. [history](docs/claude_md_history/2026_05_landmine_19_schedule.md)

20. **YouTube quota.** `DEFAULT_DAILY_QUOTA` is **200k** per channel
    (a RU show never counts against the EN budget). **Quota is no longer the constraint — cadence is**: the preflight
    warns (never blocks) above `SAFE_DAILY_UPLOADS_PER_CHANNEL`. **The Grok
    video-clip pilot is REMOVED network-wide: `video_clips_enabled` is
    `false` everywhere.** Doc
    [`docs/youtube_rollout_2026_06_25.md`](docs/youtube_rollout_2026_06_25.md);
    guards `tests/test_schedule.py` (`YOUTUBE_ENABLED_SHOWS`),
    `tests/test_{youtube_quota,youtube_quality_pass}.py`.
    [history](docs/claude_md_history/2026_05_landmine_20_youtube.md)

21. **`min_articles_skip` is tuned per-show, not per-network (May 2026)**
    — `engine/config.py` defaults `min_articles_skip` to `3` (a show
    skips that day's run if fewer than 3 fresh articles survive
    fetch + dedup). The default is a deliberately weak floor; every
    show that needs a different threshold pins it explicitly in its
    YAML. Current pinned values:

    | Show | `min_articles_skip` | Rationale |
    |---|---|---|
    | `tesla` | 6 | Largest property; six-segment digest needs density. |
    | `omni_view` | 4 | World-news scan; below 4 the digest reads thin. |
    | `fascinating_frontiers` | 4 | Space/science; needs multiple beats. |
    | `models_agents` | 4 | AI news firehose; sub-4 means a quiet day → skip. |
    | `finansy_prosto` | 4 | Russian financial news scarcity → wait for a real day. |
    | `modern_investing` | (default 3) | Markets always produce 3+ stories on a weekday. |
    | `env_intel` | 2 | Alt-cadence (odd weekdays); 2 substantive stories enough. |
    | `models_agents_beginners` | 2 | Re-uses M&A pool; lower bar OK because tone is explanatory. |
    | `planetterrian` | 2 | Science/longevity/health show (NOT local news — that description was stale); primary-research days can be thin, so 2 is the realistic floor. |
    | `privet_russian` | 1 | Bilingual lesson show; one solid theme is sufficient. |
    | `unintended_consequences` | 0 | Narrative show — articles aren't the input, topic queue is. |
    | `first_principles` | 0 | Narrative show — topic queue is the input (alternates concrete example / opportunity area). |

    **Landmine:** changing the default from `3` would silently
    re-tune four shows (the ones currently pinned at `4` would still
    pass; the ones below `3` rely on the explicit override winning).
    Always change the per-show YAML, not the default. The
    `unintended_consequences` value of `0` is load-bearing — that
    show pulls from `shows/topic_queues/unintended_consequences.yaml`
    and never fetches news; raising it would block every episode.

22. **TSLA price source: multi-source fallback chain.**
    `shows/hooks/tesla.py:_fetch_tsla_price()` tries three sources; the same
    validation (**sanity band `$200 – $1500`**, **25% deviation guard**) gates
    every source. **The HTTP source reads
    the previous close from `indicators.quote[0].close[-2]`, never
    `meta.chartPreviousClose`** (`test_bar_close_array_is_authoritative`). X
    posts are not an authoritative quote source. Failure never overwrites the
    previous-good cache. Guards `tests/test_tesla_hook.py`.
    [history](docs/claude_md_history/2026_05_landmine_22_tsla.md)

### Report the sourced news, never discard it (Oct 19 2026)

[history](docs/claude_md_history/2026_10_19_report_sourced_news.md); register `report-more-sourced-news-2026-10-19`; guards `tests/test_report_more_sourced_news_2026_10_19.py`.
**Every news digest carries an Also Today run** (one sentence per remaining qualifying story; a story that earns only a sentence goes THERE rather than being dropped) (⚠️ AUDIO). **The prompt lists `DEFAULT_MAX_PROMPT_ARTICLES` (60) articles.** Readout `prompt_articles_reported_pct`.

### The front page's ticker is live (Oct 19 2026)

[history](docs/claude_md_history/2026_10_19_live_ticker.md); register `live-ticker-2026-10-19`; guards `tests/test_live_ticker_2026_10_19.py`, `workers/gallery/test/markets.test.ts`.
**`GET /api/markets` on the gallery Worker** fetches a CLOSED list (`MARKET_SYMBOLS` = `engine.newsroom.MARKET_TICKERS` + SPCX, drift-guarded) — **an old quote is never "live"**; the previous close is never `chartPreviousClose`. `assets/js/live-ticker.js` never moves under reduced motion and writes network data with `textContent` only.

### The voice marks a story change; the music swell is gone (Oct 20 2026)

[history](docs/claude_md_history/2026_10_20_voice_marks_story.md); register `story-tags-and-map-2026-10-20`; guards `tests/test_story_tags_2026_10_20.py`.
Measured against NPR (+34 Hz opening a segment; 13 swells in nine minutes on Tesla): **a human newsreader does not pause longer between stories than between sentences**. **`audio.story_break_cue` is false network-wide** (the 1.0 s beat stays). `engine/story_tags.py` (`tts.story_tags`): **the landing tag ships EMPTY until Actions "Probe TTS tags" shows which pitch tag this voice consumes without speaking it**. **Every Whisper match reads the tag-stripped script.** **THE MAP** is ONE sentence after the identity line (a map, not a tease; never the lead again). **The breath is OUT**: **no breath-family tag reaches synthesis whoever wrote it** (`engine.utils.strip_breath_tags`); a tag candidate is LISTENED to on a shipped episode before it ships to a slate. **A chapter marker never fires on the identity line or the map sentence after it** unless it is a `start` marker. **The repair tool never moves a feed item** (`TestRepairNeverMovesTheFeedItem`).

### The Oct 21 slate: what a listener heard wrong (Oct 21 2026)

[history](docs/claude_md_history/2026_10_21_slate_review.md); register `slate-2026-10-21`; guards `tests/test_slate_2026_10_21.py`.
**A bare clock time never gains a half of the day the text did not give**; **no chapter starts on the identity line or the map sentence**; **a shared link is not a shared story**. The map is at most three stories on a news show (⚠️ AUDIO).

### The Oct 22 slate: the catalog writes, lead stories stay in the record (Oct 22 2026)

[history](docs/claude_md_history/2026_10_22_slate_review.md); register `slate-2026-10-22`; guards `tests/test_slate_2026_10_22.py`.
**A catalog write that sets only some columns is a PATCH, never an upsert.** `_STRUCTURAL_SECTIONS` are never stories. **MIT's era record is the AVERAGE trade, never compounded.** **13F holdings notices never reach a prompt.** ⚠️ AUDIO: MIT's record line.

### The Oct 23 slate: a billing stop, a dead mirror, and the catalog's aired flag (Oct 23 2026)

[history](docs/claude_md_history/2026_10_23_slate_review.md); register `slate-2026-10-23`; guards `tests/test_slate_2026_10_23.py`.
**The mirror is the last resort** (cached .debs, then the pinned BtbN ffmpeg build `test.yml` runs on). **A lake re-store keeps the story ids it did not change.** **Mira's T-2h reminder checks the xAI account.** **The video sweep restarts only a handoff whose one run died before "Render and publish the video" started.** **Past the hold, the Nerra Daily gate waits for a re-run.** The Cloudflare account is on Workers Paid now (operator, Oct 23).

### Modern Investing: the stop is enforced, the factors are measured, the record leads (Oct 24 2026)

[history](docs/claude_md_history/2026_10_24_modern_investing_deep.md); register `mit-deep-review-2026-10-24`; guards `tests/test_mit_review_2026_10_24.py`.
**A stop is whatever loss the pick states, and the percent form wins** (the $1,000 position size is never a stop; **open trades' stops are re-read from their committed digests every run**; the `pick_stop_loss` lint). **The loop measures the market's record, not the writer's exposure** (`_build_factor_scoreboard`: a finding only at ten a side with mean AND median agreeing). **Portfolio Performance leads with the era** and labels the lifetime block HISTORY ONLY. The recompute `--apply` stays the operator's. ⚠️ AUDIO.

### The Oct 24 slate: a retold story is one story told twice (Oct 24 2026)

[history](docs/claude_md_history/2026_10_24_slate_review.md); register `slate-2026-10-24`; guards `tests/test_slate_2026_10_24.py`.
**A cluster is retold only when ONE of its stories is told as two items.** **A retry run only for clusters must lower the count.** **A prompt-block label states a fact, never an instruction.** ⚠️ AUDIO.

### The Oct 27 slate: a step that is green can still fail every run (Oct 28 2026)

[history](docs/claude_md_history/2026_10_28_slate_review_oct.md); register `slate-2026-10-28`; guards `tests/test_slate_2026_10_28.py`, `workers/voices/test/fire_tick_window.test.ts`.
**Every timestamp in a PostgREST query string is a `Z` instant, never `+00:00`.** **Read a `continue-on-error` step's log, not its colour.** A word inside a heading is never enough to match a chapter marker. **A clock time is never glued to a letter, a digit or a glued `*`.** **The fire-tick gate reads a run by its slot (`scheduled_for`), never its creation.**

### The Oct 28-30 slate: a timeout that cost an episode, a silent edition, cut links (Oct 30 2026)

[history](docs/claude_md_history/2026_10_30_slate_review.md); register `slate-2026-10-30`; guards `tests/test_slate_2026_10_30.py`.
**A finished episode never fails on one transport error.** **A published file is pulled back down through `engine/http_download.py`.** **An unreadable 2xx is `unverified_unreachable`, never `not_found`.** ⚠️ AUDIO.

### Models & Agents: its natural length, and the names from the digest (Nov 1 2026)

[history](docs/claude_md_history/2026_11_01_models_agents_length.md); register `models-agents-length-names-2026-11-01`; guards `tests/test_models_agents_length_names_2026_11_01.py`.
**1,200–1,400 words is the show's natural length** (**the skip floor stays at 900**, pinned with `min_podcast_publish_words`). **The names are data, not an instruction** (`engine/names_to_keep.py`; no model call). **The section-chapter wiring the review re-filed three times is rejected** (ledger `do_not_retry`). ⚠️ AUDIO.

### The 24-hour review: YouTube policy, the front page through the day, My Nerra (Oct 31 2026)

[history](docs/claude_md_history/2026_10_31_review_24h.md); register `review-2026-10-31`; guards `tests/test_review_2026_10_31.py`, `tests/test_youtube_policy.py::{TestRelativeDeadShortsFloor,TestDubLongFormsNeedTheFullRead}`.
**The dead-Shorts bar is relative to the channel.** **Dub long-forms come back on the full four-video read only.** **`generate_html.py --homepage` also writes `ru/index.html` and `fr/index.html`**, and every workflow that commits `index.html` commits them. **"Updated" is the newest story's time**, never the build clock. **A one-letter unit only after a spoken quantity.** **Members-only shows never ask for a follow or a rating.**

### One email: Nerra Daily (Nov 1 2026)

[history](docs/claude_md_history/2026_11_01_one_email_nerra.md); doc [`docs/nerra_daily_email.md`](docs/nerra_daily_email.md); register `nerra-daily-email-2026-11-01`; guards `tests/test_nerra_daily_email_2026_11_01.py`, `workers/gallery/test/email.test.ts`.
**The network sends ONE email, Nerra Daily** (`engine/nerra_daily_email.py`). **It is personalized by Buttondown's per-subscriber templating on TAGS, never by sending different emails.** **`newsletter.delivery`** is `nerra_daily` network-wide; the Russian shows are `own`. **A filter tree with nothing resolved is refused, never sent unfiltered.** **One show map, two copies**: `email_show_tags()` and the Worker's `EMAIL_SHOW_TAGS`. **Every site link is `engine.funnel.newsletter_link`.**

### The six-month review (Nov 3 2026)

Operator-directed: *the best, most interesting, most informative, most
trustworthy, best-sounding shows; the best landing page, website, YouTube
pipeline and newsletter of any news network; delivered efficiently; Mira's
Age of AI built further; an alternative to traditional news networks that
grows in languages and content; beautiful on every surface.* Review
[`docs/reviews/network_review_2026_11_03.md`](docs/reviews/network_review_2026_11_03.md);
register `six-month-review-2026-11-03` and four entries beside it; guards
`tests/test_six_month_review_2026_11_03.py`. Fourteen readers, one per
surface, read the committed record against the best in each industry; the
defects they proved in code were fixed the same day. Rules that bind:

- **A no-music show masters to the published loudness like every music
  show.** `run_show`'s voice-only path calls `engine.audio.master_voice_track`
  (the translated tracks' finisher), never `normalize_voice` alone: its chain
  ends on `loudnorm=I=-18` plus a 4:1 compressor and lands ~7.6 dB under its
  own target, and only the music mix's final `loudnorm=I=-16` ever recovered a
  show. UC, Vancouver and Collingwood shipped 208 episodes at -25 LUFS, and
  their chapter inside Nerra Daily stepped 9.7 LU. **Nerra Daily levels every
  segment** (`segment_trim_cmd` carries `PUBLISHED_LOUDNESS`). A loudness
  defect is a number nothing read for six months; the back-catalogue re-master
  and an `audio_integrated_lufs` metric are the review's open items.
- **`-ss`/`-t` are INPUT options on a music piece** (`_music_fadeout_cmd`): as
  output options the filter graph saw the source from t=0 and the 30 s bed
  under the opening shipped as 12 s of music and 18 s of digital silence on
  every music show since Feb 2026. **A fade to silence uses `FADE_CURVE`
  (`qsin`)**: ffmpeg's `log` holds within 2 dB for 97% of the fade and
  plunges in the last 1%, so the YAML's "10 s fade-out to silence" had never
  shipped. **The voice branch is stereo before `amix`** — a mono voice made
  `amix` negotiate mono and `-ac 2` duplicated it: every music show was
  dual-mono (L-R vs mid -210 dB). Audio is checked for envelope and image
  now, not loudness and clicks alone (⚠️ AUDIO on all three — A/B-listen).
- **A story's picture is its own scene or none.** `engine.landing_test.episode_scene`
  matches stemmed salient tokens ("robots" / "Robotic"), accepts one shared
  word when no other scene shares any, and when the episode's prompts are
  known and none depicts the headline returns `None` (the template shows the
  show's cover) — never `candidates[0]`. The Nov 2 front page led with a coral
  reef under a protein-engineering headline two lines below the promise that
  every story is sourced.
- **A month abbreviation is a month only when a day or a year follows it**
  (`assets.pronunciation.replace_dates`; "March-a-Lago", "January Ferrigan"
  aired on Nerra Daily). `AIS` is spelled.
- **The Nerra Daily email's conditions also decide its ARCHIVE copy.**
  Buttondown renders the "View this email in your browser" page with no
  subscriber in the context, where Django's `in` / `not in` both read False;
  every "not followed" condition opens with `not subscriber or`, every
  "followed" one with `subscriber and` (`render_for(subscriber=False)` is the
  archive). The subject drops the podcast app's "<Weekday> edition — "
  prefix; release notes are judged at the SEND (`newsletter_send_time`),
  never the compose clock; a signup button says when the email arrives, never
  "Check your email" (nothing sent one).
- **The Buttondown email read follows pages and the committed send records**
  (`digests/nerra_daily/email/*.json` carry the `email_id`): one unordered page
  of 50 had read `sends 0` the night after the first send.
- **A dub channel with no destination of its own lands on its language's
  front page** (`engine.funnel.destination_for`: the channel's destination,
  then `ru/index.html` / `fr/index.html` for a language the site publishes in,
  then `default`), never the English show page.
- **The daily audit reads the prose** (`*_reader.txt`), lists the digest's own
  publishers and item titles as real names, defines REPETITIVE as restatement
  and INCOHERENT as referent-less, and reads 24,000 characters: 12 of 75
  INCOHERENT criticals in 16 days had named a pronunciation spelling,
  `shattered.io` or Musk's cluster names, and 17 of a week's 113 scripts were
  scored on an excerpt.
- **A show still on `on_failure: strip` renders every claim "malformed"** on
  `claims.html` (its policy-2 sidecar carries no per-entry status). No show
  pins strip now (Peptides and Longevity moved to flag), and
  `engine.claims_ledger` labels a status-less entry from the gate's own lists.
- **`digests/*/youtube_tmp/*_short_source.*` and `digests/**/*.flac` are
  ignored** — the hook Short's spliced FLAC rode the video job's `git add -A
  digests/` into main for three days (571 MB; landmine #1's third
  recurrence). `TestNoEpisodeAudioIsTracked` sweeps every media extension.
- **The digest expansion retry is a metric** (`digest_expansion_fired` and
  four companions; `digest_expansion_fired_share_7d` on the dashboard): it
  fired on 7/7 episodes of every flagship in the week to Nov 2 and 0/7 on the
  cohort, costed and unrecorded, and the padding it adds is the best predictor
  of a Repetitive audit flag (digest fact-free share, AUC 0.72). The fact
  floor that would replace the word floor is the review's first shows item.
- Also fixed: the gate-2 email and review page no longer say "nothing goes
  out until you have heard it and said yes" (the Nov 2 guard sweeps that
  shape across the Worker and the Voices templates); Nerra Daily posts say
  "By Mira"; Top World's intake line names the desks it read instead of "1 of
  the 5"; the edition's promo cut lands before the platform ask (ten rating
  asks in Ep074) and realigns handoffs BEFORE the variety revision; SpaceX
  says "closed Friday at" before Monday's open; tesla.html / spacex.html / the
  SpaceX dashboard ask the network's own markets route instead of Yahoo
  through two free CORS proxies; a compact cookie bar; Nerra Voices is a
  section of the one email; imagery credits are labelled by source; the Tesla
  digest's bracketed sign-off placeholder (seven digests since July) is gone;
  the Voices Worker's fire-tick catch-all is hourly; a correction's headline
  and a translated feed title clip through `engine.titles`.

**Shipped from the review's ranked plan the same day** (each with its guard;
details in the review doc §4 and `docs/experiments.yaml`):
- **Loudness, range and true peak are metrics** (`engine.audio.measure_loudness`,
  one ebur128 pass; `audio_integrated_lufs` / `audio_loudness_range_lu` /
  `audio_true_peak_dbtp` per episode and on the edition record;
  `validate_loudness` warns outside −16 ± 1.5 LUFS, log-only for a week;
  `audio_loudness_in_spec_share_7d`). Guards `tests/test_audio_loudness_metric_2026_11_03.py`.
- **The Age of AI edit encodes with the network's one master setting**
  (`engine.audio.JOIN_MP3_ENCODE_ARGS`, VBR `-q:a 0`, never a CBR cap) and its
  pads loop the adjacent piece's own room tone (`engine.story_breaks.write_room_tone_pad`,
  zeros only as a fallback); `digital_zero_sec` / `encode_kbps` measured from the
  shipped file. Guards `tests/test_voices_encode_and_room_tone_2026_11_03.py`.
- **A paid link goes through `engine.funnel`** (`KIND_AD`, `MEDIUM_CPC`,
  `SOURCE_GOOGLE_ADS`, `ad_link()`, `scripts/funnel_link.py`); **a landing
  anomaly is excluded and PRINTED** beside the raw total (`fetch_ga4_stats.landing_anomalies`:
  ≥ 50 sessions and a 95% bounce or under 3 s; None when unread, never 0);
  real-user vitals are GA4 `web_vital` events. Guards `tests/test_funnel_denominator_2026_11_03.py`.
- **`engine/promo_card.py` opens nothing under `assets/site_screens`**: the
  outro card and the Shorts end-card strip render from the covers,
  `engine.brand.network_tagline_for(channel)` and the free-show count;
  `outro_card_duration_seconds` is 3.0; the banners' lines come from
  `engine.brand.youtube_banner_lines`; the capture script exits non-zero when
  it captures nothing. Guards `tests/test_youtube_brand_surfaces_2026_11_03.py`.
- **The Nerra Daily email carries a deck of the digest's own sentences under
  every card** (`engine.landing_test.story_deck`, no model call; a flagged
  sentence never prints), **a hook's story is never listed again under it**
  (`engine.newsroom.headline_within_hook`), the masthead is compact and the
  edition card follows the body, an "Also" line is `engine.titles.EMAIL_ALSO_LINE_MAX`,
  the size guard subtracts Buttondown's wrapper. Guards `tests/test_nerra_daily_email_2026_11_03.py`.
- **A post recommends its OWN WEEK** (`_pick_cross_show_related(post_date=)`,
  7 days before to 1 after, nearest first) so old posts stop being rewritten
  every morning; **the per-show regen is `--blogs --latest 3`** on every show
  run, video job and multilingual sweep (the nightly's full rebuild reaches old
  posts); **`styles/blog.css` is the one blog stylesheet** (network-first in
  `sw.js`); **no tracked blob over 2 MB under `digests/`**. Guards
  `tests/test_repo_hygiene_2026_11_03.py`, `tests/test_blog_related_stability_2026_11_03.py`.
- **CLAUDE.md is the rules** (≤ 165 KB, `tests/test_claude_md_size.py`): every
  dated pass's narrative lives verbatim under `docs/claude_md_history/`; a
  pass adds at most ten lines here.
- **The long-form policy carries the Shorts tier's ruler on every entry**
  (`long_d3_median_21d`, the ratio to the show's own hook Short, subscribers
  per 1,000 pooled at age 7; RU/FR entries carry their hook-Short reach); **a
  dub long is a rate only from day seven** (`LONG_MIN_AGE_DAYS` per channel);
  the dub long overlay is SHIPPED OFF (`DUB_LONG_RELATIVE_ENABLED`) and only
  the operator turns it on. Guards `tests/test_long_form_policy_instrument_2026_11_03.py`.
- **Env Intel's Practitioner Deep Dive is built from a document the run read,
  never from a career the host does not have**: both prompts build it from
  one regulation or guidance document with full text in the prompt, or leave
  it out; `engine/host_experience.py` mode `experience` removes a closed set
  of first-person professional-experience shapes (`frames` is byte-identical;
  an unknown mode raises at load; re-run the committed replay before widening
  a pattern); `DEEP_DIVE_FETCHED_SECTIONS` lists the section — a YAML opt-in
  for a section missing there is a lint that never fires. ⚠️ AUDIO Mondays.
  Guards `tests/test_env_intel_sources_2026_11_03.py`.
- **A digest's expansion floor counts FACTS, never words, on Planetterrian
  first** (`llm.min_digest_facts`; `engine.script_audit.digest_fact_profile`
  is the ONE fact-state test; the retry ranks the Oct 19 stories floor first,
  never lengthens the deep dive, and is kept only when the fact count ROSE;
  0 is the word test, byte-identical). The four new density columns carry
  no threshold until a baseline week is in. ⚠️ AUDIO: thin days ship shorter
  and denser. Guards `tests/test_digest_fact_floor_2026_11_03.py`.
- **The back catalogue is re-mastered in place, by a GAIN**
  (`scripts/remaster_episodes.py`, Actions "Re-master Episodes", dry run by
  default): never a two-pass loudnorm (its linear mode falls back to dynamic
  silently at these peaks); **the upload is refused outside −16 ± 1.5 LUFS or
  over −1 dBTP**; the SAME R2 key, the feed item keeps its GUID; a pull-back
  never goes through the OP3 prefix. One episode listened to before the
  batch (⚠️ AUDIO). Guards `tests/test_remaster_episodes_2026_11_03.py`.
- **Mira's beat before the question** (⚠️ AUDIO, the room): the CRITICAL
  list's last line is the beat by shape, the opener prohibitions stay;
  `audio_metrics.bare_question_rate` — a question turn is a label, is bare,
  or carries a reaction, and the three add to one, so **read label and bare
  together**; the room-side baseline is the first audio-measured room, never
  the hand-edited Ep15. Ships to a booked room only on a two-arm rehearsal
  PASS plus one listen. Guards `tests/test_mira_beat_2026_11_03.py`.
- **The channel the repo can see**: the nightly fetch reads the uploads
  playlist back (`_channel_uploads`; keys ABSENT on a failed read, never 0);
  an "Ep N: <hook>" twin is `kind: rss_copy`, counted by
  `youtube_rss_copies_14d_<ch>` and nowhere else — **every instrument reads
  `INDEXED_KINDS` only**. **Every long of the last 14 days gets a retention
  curve** (`RETENTION_CURVE_MAX`, newest first ACROSS channels); a curve
  carries `curve_fetched_at` and a carried-forward one is never read as
  fresh; the snapshot's `generated` carries the fetch's own date. **The
  Short's job is written once** (`engine/release_schedule.py`). The Studio
  removal of the RSS podcasts is the operator's (landmine #15). Guards
  `tests/test_youtube_pass_2026_11_03.py`.
- **Listen before the slate**: `rehearse: true` on "Run show" runs the
  pipeline through TTS and mix and commits NOTHING (the MP3 is a 3-day
  artifact); `scripts/probe_audio_chain.py --script` renders a real minute
  of a committed script through the real builders; **a change to
  `_defaults.yaml`'s `audio:` / `tts:` values fails CI until the snapshot is
  regenerated and `docs/listens.md` gains its line** (the guard confirms the
  line, only the listener confirms the listening); the PR template asks for
  the rehearsal link. Playbook: "Audio changes". Guards
  `tests/test_listen_before_slate_2026_11_03.py`.
- **Findability**: `engine.blog.article_schema_type` decides NewsArticle vs
  BlogPosting from the show YAML and the curated topics; **the author stays
  the show ORGANIZATION, never a Person**; `dateModified` comes from
  corrections; **`engine.titles.web_page_title` is the one page-title shape**
  (`<lead> · <Show>`, `WEB_TITLE_LEAD_MAX` 58); `news-sitemap.xml` reads each
  post's own JSON-LD (never mtime) and is staged one path per `git add`.
  Guards `tests/test_findability_2026_11_03.py`.
- **A deep dive is a second story, measured** (`deep_dive_distinct_measure`;
  the firing form is listed only after a week under the 0.22 regen ceiling);
  **only `DEEP_DIVE_FETCHED_FIRING_SECTIONS` fire** — an essay whose prompt
  does not state the Source-line rule is measured, never regenerated; **a
  narrative hook figure sits in a read research article or the episode's
  ledger** (`hook_figure_sourced`, UC/FPD; ⚠️ AUDIO). Guards
  `tests/test_deep_dive_distinct_2026_11_03.py`.
- **Mira's rooms are costed and read**: `pipelines/voices/costs.py` normalises
  the SDK usage object; one Voice Agent rate (`engine.tracking.voice_agent_rate_per_min`);
  a room is an episode only once `scripts/build_voices_metrics.py` marks it
  `published`; `api/voices_metrics.json` is null, never 0, where a table was
  unread. Guards `tests/test_voices_metrics_2026_11_03.py`.
- **Write for the ear, by shape**: the outlet sits INSIDE the first-fact
  sentence and never ends one; no prompt or template counts sentences per
  line; no item has a two-sentence floor; no essay is a length lever;
  **`engine.titles.X_ITEM_TITLE_MAX` clips every X-post heading** (⚠️ AUDIO).
  Guards `tests/test_flagship_prompts_2026_11_03.py`.
- **The voice compressor is a named stage** (`engine.audio.VOICE_DYNAMICS`):
  **the network flips by `DEFAULT_VOICE_DYNAMICS` after the listen, never per
  surface and never in `_defaults.yaml` ahead of it**; `glue` on Tesla and
  Top World only (⚠️ AUDIO). Guards `tests/test_voice_dynamics_2026_11_03.py`.
- **The register is read nightly** (`scripts/readout_register.py` →
  `api/register_readouts.json`); **an entry from Nov 3 on needs a computable
  metric or `criteria` + `readout_plan`**; a drafted readout is a draft, the
  outcome goes in by hand. **A `rotation_only` review target is dated by the
  agent's own ledger entries, never a slate's**; a review PR closed unmerged
  is labelled, and only `rejected` writes `do_not_retry`. The latency gate
  runs nightly (`api/model_trial.json`). Guards `tests/test_review_loop_2026_11_03.py`.
- **The interview shows inherit the publish surface**: a title that does not
  fit gives its FIRST CLAUSE whole (`engine.titles.fit_first_clause`); the VTT
  comes from the EDIT transcript only; **a label or a URL is never a biography**
  (`engine.interviews.is_guest_prose`); **a camera episode never ships the
  waveform** (`camera_missing`, nothing uploaded). Guards
  `tests/test_{voices_feed_parity,age_of_ai_youtube}_2026_11_03.py`.
- **A language hub ranks and leads from its own channel's audience**
  (`_rank_shows_by_channel_views`, `engine.language_front.lead_rotation_for`;
  the English page passes neither); **the RU landers ask for the subscribe and
  the RSS, never an email**. Guards `tests/test_site_languages_2026_10_18.py`.
- **`api/buttondown_history.json` is the newsletter's one series** (a row a
  night from `scripts/fetch_buttondown_stats.py`, which owns its readers): an
  earlier date's row is never rewritten; **the open rate is over the last
  seven SENDS' summed recipients, null under `RATE_FLOOR`**; the Nerra Daily
  tile is never hidden. Guards `tests/test_email_measurement_2026_11_03.py`.
- **The daily audit is an instrument**: every YES quotes its sentence and
  `engine.claims.fuzzy_contains` must find it in the text read — an unquoted
  flag is info, counted as ungrounded, never a finding; the score persists in
  `api/editorial_score_history.json` (`editorial_score_14d_<slug>`; null,
  never 0); ONE rolling issue; **a promised length is computed from the last
  14 episodes and printed only for a show in `engine.cadence.COMPUTED_LENGTH_SHOWS`**.
  Guards `tests/test_daily_audit_instrument_2026_11_03.py`.

### Mira builds on the answer; she does not sum it up (Nov 4 2026)

Register `mira-react-builds-2026-11-04`; notes `docs/mira_craft_notes.md`; guards `tests/test_mira_builds_2026_11_04.py`.
**What she says after an answer is a bridge built from one thing the guest said, never a phrase folded from it, and never the same shape twice** (HOW TO REACT, by shape). **`one_liner_rate` reads the sameness beside label and bare.** **`learning.SUPERSEDED_BY_BRIEF` keeps lessons the brief now governs out of the prompt; it ships and rehearses with the brief.** ⚠️ AUDIO, the room: a rehearsal PASS plus one listen before merge.

### The Age of AI: a guest who asks to end, ends (Nov 5 2026)

Register `blaines-close-2026-11-05`; guards `tests/test_blaines_close_2026_11_05.py`; review [`docs/reviews/blaine_mathieu_2026_11_05.md`](docs/reviews/blaine_mathieu_2026_11_05.md).
**A recorded stop means the clock never starts the closing round** (`roundDueOnTheClock`; a TYPED wrap-up still gets its round) and her goodbye after it stands. **A typed presence check is a message, never a topic** (`TYPED_PRESENCE_RE`). Widen a stop pattern only with its false positives in the guard. Rehearse with `early_wrap`. ⚠️ AUDIO, the room.

### The Nov 4 handoff: one tracker, Vancouver time (Nov 4 2026)

Guards `tests/test_handoff_2026_11_04.py`, `tests/test_times_are_pacific.py`.
**`docs/outstanding.md` is the one tracker for operator items** (owner, status, date, evidence); no parallel list. **The network's zone is "Vancouver time", never "Pacific Time"** (B.C. is UTC−7 all year from Nov 1 2026). **A hold is only a waiting sense** ("I'll hold the silence better" is not one). **The hello invite stays off (`HELLO_INVITES: "0"`) until its Cal.com page exists.** **A candidate scenario upload is read back before it is rehearsed**; the `current` arm is rebound to the fixture's guest. **A chase reads the person, never the row.** **A correction reaches `episode_records`.**

### Hiss and clicks: joins, Mira's voice, story pauses (Oct 29 2026)

[history](docs/claude_md_history/2026_10_29_hiss_clicks.md); register `audio-clean-joins-2026-10-29`, `audio-tracks-and-mira-declick-2026-10-29`; guards `tests/test_audio_quality_2026_10_29.py`.
**A join is never an MP3 stream copy** (`engine.audio.concatenate_audio`; every caller goes through it). **Pieces are lossless, the finished file is encoded once.** **Mira goes through the shows' voice chain** (`engine.audio.voice_chain_filters` is the one owner). **A story pause carries the voice's own room tone, never digital zero.** The probe's stronger denoise is NOT shipped — a listen decision. **A translated track is mastered like the English episode.** **Mira's voice gets the strong declick** (a guard compares the setting with the `ara` voice). ⚠️ AUDIO.

### The front page, Nerra Personal and the video links (Oct 28 2026)

[history](docs/claude_md_history/2026_10_28_landing_personal_youtube.md); register `landing-personal-youtube-2026-10-28`; guards `tests/test_landing_personal_youtube_2026_10_28.py`, `workers/gallery/test/member_security.test.ts`.
**Only a magic-link cookie (`v: 1`) may use a member's paid record** (`mayUseRecord`). **Every blog rebuild links the episode's public videos** (a scheduled video is never linked). **Call `generate_shorts_thumbnail` with keywords.** **An event tracking.js sends is in `ENGAGEMENT_EVENTS`.** The members-only desks are never called free. **Long-form retention is read at a fixed age.**

### My Nerra is the member's own front page (Oct 28 2026)

[history](docs/claude_md_history/2026_10_28_my_nerra_front.md); register `my-nerra-front-page-2026-10-28`; guards `tests/test_my_nerra_2026_10_28.py`.
**The stories come from `api/personal_front.json`**, written with every homepage build (`write_personal_front` never raises; the full hook, never the clipped feed title). **A members-only show is listed with no episodes.** A new workflow that runs `--homepage` and commits `index.html` must commit it too. **Topics are open to every account.** Active members never see a checkout.

### The site is an app: one player, Watch, For you, the join builder, add-to-app (Oct 28 2026)

[history](docs/claude_md_history/2026_10_28_site_app.md); register `web-app-2026-10-28`; guards `tests/test_web_app_2026_10_28.py`.
**One player for every page** (`assets/js/nn-player.js`; **it reports the plays** — no page using it sends its own). **The service worker is conservative** (`sw.js`: never audio, another origin or a Range request; bump `VERSION` on a behaviour change). **`window.nnAccount` is the nav's one `/api/account` request.** **`/add.html#<token>`** keeps the token in the fragment, noindex, never in the sitemap. Mira's Watch-my-lineup greeting is WRITTEN (no voice — a model call per member).

### Your stocks, more of Mira, and the app on the Home Screen (Oct 29 2026)

[history](docs/claude_md_history/2026_10_29_your_stocks_more.md); register `markets-mira-app-2026-10-29`; guards `tests/test_{markets_mira_app_2026_10_29,read_buttons_2026_10_29}.py`, `workers/gallery/test/{markets,personal,handlers}.test.ts`.
**No page prints a price from api/tsla.json or api/spcx.json** (quotes come from the markets route). **One ticker shape in three places** (`engine.personal_edition.TICKER_RE`, the Worker's `MEMBER_SYMBOL_RE`, `nn-markets.js` `SHAPE`; `TICKERS_MAX` 8 in all three). **Mira's links call gets more of the listener, still one call**; memory notes say an edition CARRIED a story, never that the listener heard it. **A member's feed token never reaches analytics.** **The app is offered, not pushed** (never over the cookie choice, never in the app). **A template change to a static page commits the page it renders.** ⚠️ AUDIO.

### Every episode player is the site's player (Oct 30 2026)

[history](docs/claude_md_history/2026_10_30_every_episode_player.md); register `site-episode-player-2026-10-30`; guards `tests/test_inline_player_2026_10_30.py`.
**`nn-listen` is the Listen BUTTON's class, and its rules are `button.nn-listen`**; the blog box is `.nn-episode-listen`. **`nn-player.js` takes over every `audio[controls]`** (`data-nn-native` opts out). **A page script plays a page's audio through `NNPlayer.playElement(el, s)`.** **The players' own text updates are not new content for the body observer.** `sw.js` serves `styles/` and `assets/js/` NETWORK FIRST. **The browser's own control never shows before the player replaces it.**

### Covered means aired, and a story catalog (Oct 21 2026)

[history](docs/claude_md_history/2026_10_21_covered_means_aired.md); design [`docs/story_catalog.md`](docs/story_catalog.md); register `story-catalog-2026-10-21`; guards `tests/test_story_catalog_2026_10_21.py`.
**`engine/aired_items.py` is the one reader of "the stories a digest told".** **The tracker records what aired**, never the whole prompt list. **Story ids come from `engine/story_catalog.py`.** **The cross-show block names only today's articles a sibling told in two days, never silence.** **The story catalog is `catalog_*` in the nerra-voices Supabase** (`engine/catalog.py`; a show run's write never blocks; `missed_stories` null, never 0). **Books never print a corrected error**; a `prior_coverage.md` is never a source. ⚠️ AUDIO.

