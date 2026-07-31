# Network review — 2026-07-31 (operator-directed prompt + LLM pass)

Operator ask: *"do a full prompt and llm review to actually continue to
improve all the shows and their prompts and optimize them appropriately
as llms/Grok get better and newer versions. I want the best shows
possible."* Ran as `/review-show network` methodology with four parallel
per-cluster audits (flagship: tesla/spacex/modern_investing · news:
omni_view/fascinating_frontiers/planetterrian/env_intel · AI+RU:
models_agents/models_agents_beginners/finansy_prosto/privet_russian ·
narrative: unintended_consequences/first_principles/dp_pod/age_of_ai +
shared includes + in-code prompts). Landed across PRs #926 and #927 plus
this follow-up branch. Every claim below was verified against committed
artifacts by the auditing agent before filing.

## P0 — listener-facing, shipping at review time

1. **Every show's spoken identity line was being deleted** (fixed,
   `run_show.py` + `tests/test_intros.py`). The July-30 cold-open pass
   made `build_intro_line` emit "Patrick: This is <Show>, episode N." —
   which `_clean_podcast_script`'s junk-title-header regex matched
   exactly, so every post-merge episode network-wide shipped without its
   host ever saying the show's name, and the Introduction/Welcome
   chapter was lost with it. Independently discovered by three of the
   four cluster audits (SpaceX Ep050/051, MIT Ep123 — which never says
   "Patrick" at all — OV Ep129, FF Ep147, PT Ep137, M&A Ep127, MAB
   Ep119, UC Ep075, FPD Ep056 all verified missing). Финансы Просто
   survived only because its Russian line says «выпуск», not "episode".
   The stripper now exempts spoken identity shapes ("this is" /
   «вы слушаете» / "and this is") while still dropping real metadata
   headers; guarded in both directions.

2. **DP Pod spoke "Source: Google News." aloud** (Ep022, twice) and
   **FP aired «Источник информации — bnnbloomberg.ca» 13× across 6 of
   its last 10 episodes** — two scaffold shapes the July scrub couldn't
   see (outlet names instead of domains; the Russian em-dash label
   form). Both added to `_strip_source_scaffold_lines` with
   prose-safety verified ("Source: NASA confirmed the launch." and
   "the source: nobody would confirm" survive untouched).

3. **SpaceX Ep048 digest shipped truncated mid-sentence** (3-word
   Engineering Deep Dive; the podcast improvised the segment from model
   knowledge — the exact ungrounded-claim risk the prompts ban).
   Recorded; the digest-validity floor is the existing guard, no new
   mechanism proposed this pass.

## P1 — quality ceiling (the prompt sweep)

**Seeded-tic de-seeds shipped by shape (all ⚠️ A/B-listen):**
Tesla "keep an eye on" (10/10 episodes) · MIT "the biggest mistake
with" (9/10) · SpaceX "a quick market note" (8/10, chapter-marker
safety verified) · OV anonymous "one position holds / a competing
position" scaffold (the serial-tic escape from the previously banned
frames, climbing 0→2/ep) · FF "Sun as a basketball / teaspoon of
neutron star" Cosmic Deep Dive specimens (leaked verbatim Ep138/139) ·
M&A "keep an eye on" (10/10 — the 07-19 review proposed this de-seed
but never shipped it) + the prompt instructing the model to use its own
banned "bigger trend" phrase · MAB "favourite part of the show" (8/10)
· DP Pod "the payback math I'll give you" (6/10), "I'm doing this one
this week" (13+ eps), "tell us what happened" (6/10) · FPD "on the
order of" (6/10) — seeded by the prompts' own example hedge lists, and
ALSO by `engine/generator.py`'s narrative expansion-retry prompts,
which handed the model the same quotable phrase; both de-seeded.

**Cold-open integration contradictions fixed:** Tesla legacy
intro-order block, MIT system prompt demanding "NASDAQ level in the
cold open" + ENERGY specimen, both dead Episode-1 blocks (flagship),
MAB's dead post-cold-open Welcome marker + "that is a wrap"
de-contraction chapter gap, PR's 650-900 vs 900-1200 digest/podcast
length contradiction, fabricated-etymology guard applied (PR).

**Deterministic (non-A/B) fixes:** FF ephemeris fetch-filter gained 3
title patterns for the re-headlined almanac columns (the 07-18 reopened
leak — Ep147's Venus hook came through one; zero real-news false drops
verified) · Привет, Русский! re-teach cycle root-caused to
`engine/vocab_tracker.py`: the `[:24]` cap truncated the do-not-reteach
list to ~3.5 episodes while the header promised 8, and the themes
window (6) was shorter than the no-reteach window (8) — ep58/59/60/63
each re-taught 5-7 words from exactly 7-8 episodes back; both windows
fixed · UC queue pruned of 3 briefs with fabrication red flags, FPD of
5 category-error briefs, alternation re-interleaved (runways 6.4-6.7
wk, above floors) · Age of AI: thesis name-duplication, "NARA Network"
STT garble path, and the sign-off's "guest reviewed and approved" claim
(false on the day-7 auto-approve path) fixed.

**Env Intel got the sanctioned digest-side length lever**
(`digest_expand_below_target: true`, `min_digest_words: 950` — digests
measured 563-891 words, the real ceiling) and its banned podcast-side
retry is off. Финансы Просто remains the one holdout: its digest `.md`
is a ~200-word structured brief, so a words floor needs its own design
(deferred with the AI/RU cluster's 1100-word proposal recorded as
needing verification of FP's true pre-format digest length).

## LLM / model strategy (the "as Grok gets better" ask)

grok-4.5 (released 2026-07-08) is the largest generation jump xAI has
posted (+16 Artificial Analysis points over 4.3, configurable reasoning
effort) — but its confident-hallucination rate rose 25% → 54% even as
raw accuracy improved, and it costs $2/$6 vs 4.3's $1.25/$2.50 with
half the context. For a facts-first news network:

- **Digest/fetch stages stay on grok-4.3** (hallucination profile is
  disqualifying; the 4.3 narrative-length plateau remains accepted).
- **`llm.podcast_model` shipped** (config + generator): a per-stage
  override so 4.5 can be A/B'd on the prose/script stage of ONE show
  while its digest stays grounded on 4.3. Empty default =
  byte-identical. Suggested first trial: omni_view for a week
  (~15k tokens/ep ≈ pennies); listen per landmine #17.
- **Scheduled review agent upgraded to grok-4.5**
  (`scripts/run_show_review.py`, `REVIEW_MODEL` env rollback):
  analysis-only, operator-gated output — a sharper analyst is pure
  upside at ~$0.75/run.
- `llm.reasoning_effort` already existed and stays empty by default.

## Ledger scoring (2026-07-18 network entry)

- Closing-is-final invariant: **hit** (0 post-Closing chapters in
  episodes dated ≥ 07-18).
- Dashboard voice-drift false positives: **hit** (0 warns).
- DP Pod Network-pick rotation: **miss** — Planetterrian Daily was the
  pick SIX consecutive days (Ep019-024) with the rotation-memory ban
  text present in every prompt. Different approach shipped: shows
  picked in the last 2 days are now excluded from the fresh-episode
  candidate data entirely (filter the input, don't instruct the
  output).
- FF ephemeris leakage: **miss** (still leaking; Ep147) — addressed
  with title patterns at the fetch filter, the deterministic lever.

Cluster-level scoring (details in the per-show ledger entries the
cluster audits appended): Tesla 2/2 hit · SpaceX teaser + junk-title
hit, length miss · MIT digest-lever hit (median 1382→1721w, the show's
first working length lever), alpha-significance caveat **third miss →
escalated to operator accept-or-abandon** · OV mostly hit, length miss
· PT astronomy filter held (6→1) · EI nuance tic trending hit · MAB
double-closing hit (0/20) · PR WOTD never-repeat **miss** (самолёт
Ep050→Ep055) — root-caused to the vocab_tracker windows above · DP Pod
July-20 banter pass: volley partial, exclamations **miss twice over →
two-miss escalation, no further prompt text** · UC 4/4 hit.

## Deferred / operator items

- **FP digest-side length lever** — needs FP's true digest length
  verified before a floor is set (see above).
- **DP Pod Ep023-class closing containment** (a turn deleted + label
  swapped, a shape the Ep016 relabel guard can't catch) — engine
  containment check proposed, not designed this pass.
- **Identity-line reinsertion guard** (if the LLM omits the line the
  stripper fix can't help) — mirror of the missing-closing guard;
  deferred to keep this pass's audio-affecting surface reviewable.
- **MIT alpha-significance caveat**: three misses; operator
  accept-or-abandon.
- **DP Pod dispatches.json still empty** (07-18 miss carried) —
  operator item.
- Dead shared includes `_shared/accuracy_rules.txt` /
  `ai_transparency_note.txt` (included by zero prompts) — delete or
  wire, operator call.
- Chained-outline prompt is news-shaped for narrative shows; reviewer
  prompt has no dialogue-mode checks — candidates for the next
  narrative-cluster pass.
- MIT fetch chronically collapsing (10-24 articles on 3 of last 4 days
  vs 386 healthy; alarm firing correctly) + tripled duplicate x.com URL
  in Ep123 — fetch-side investigation next pass.

## Predictions (scored by the next network review)

See the ledger entry appended to `docs/reviews/ledger/network.yaml`.
