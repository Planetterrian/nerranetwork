UTH chapters and pop-the-hood anchors recovered to 10/10, but 8/10 scripts stay under 1500w, names-kept still only ~3–4/10 ≥75%, digest-verbatim median ~43% with section-header paste, and sparse/auto-titled chapters dominate—length/entity/overlap stay escalated operator decisions after repeated unshipped identical proposals; propose digest_section wiring for non-UTH sections only.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1844**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| FR dub identity line episode number matches EN episode number, last 10 FR transcripts | hit | do_not_retry 2026-10-05: .fr.txt correct; Whisper mishears French compounds — not a dub/identity bug |
| episodes with Under the Hood chapter when deep-dive body present, last 10 | hit | 10/10 ep191–200 chapters_ep*.json include Under the Hood (was ~7/10 at Oct-2) |
| "Pop the hood" (or exact required anchor) as first sentence of deep-dive body, last 10 | hit | ep195–200 all open UTH with pop-the-hood / let-me-pop-the-hood |
| script_entity_retention_pct (names kept) ≥75%, last 10 | miss | only ~3–4/10 ≥75% (range 54–86%; ep191/194=54, ep199=58) |
| digest-verbatim median last 10 + copied section-header count | miss | median ~43% verbatim; section headers still copied on ep191–194/198/200 |
| Under the Hood concrete numerals when UTH present, last 5 | hit | ep195/198/199/200 UTH sections carry ≥4 concrete numerals when present |
| successor UTH-opener tic: any single new non-pop-the-hood opener in ≥6/10 deep-dives | hit | 0 non-anchor openers at ≥6/10; pop-the-hood remains the opener |
| episodes below min_podcast_words (1500), last 10 | miss | 8/10 under 1500w; operator A/B/C still open (lever not shipped) |
| "Everyone talks/treats/thinks about" or "Most people assume" as UTH opener, last 10 | hit | 0/10 contrast-cliché UTH openers in ep191–200 EN |
| "keep an eye on" as teaser opener (regression watch) | hit | 0 keep-an-eye teaser openers in sampled ep195–200 teasers |
| chapters_ep*.json titles containing "](" or "http", or early Practical & Community | hit | 0 link titles and 0 early P&C mis-fires in ep191–200 |
| advisory filler shape per episode (script_audit) | hit | filler 1–8% last 10; mostly ≤4% (ep191 8% outlier only) |
| model-number or dataset-name mangles per episode (Ep166 class), last 5 | hit | 0 Nutrition5k/RTX-5090-class mangles in ep195–200 EN |
| source_integrity_claims median (Sep-24 sourcing) | partial | fetch_full_text:12 + preferred_domains + x_only_lead live; snapshot has no integrity score field |
| sources on x.com per episode (Sep-24 sourcing) | partial | x_posts_as_sources secondary + lint live; per-ep x.com counts not in snapshot |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/models_agents_podcast.txt`** (prompt) — Ep200 EN shipped “Episode 200, Episode 200” plus “Thanks for sticking with us” (`Models_Agents_Ep200_20261011_transcript.txt`). Belt-and-suspenders on the injected identity line so milestone/stutter doubles cannot return. A/B-listen.
```diff
- [Identity — one short line, immediately after the cold open]
- Use this exact line (do not rewrite it, do not add a date):
- {intro_line}
+ [Identity — one short line, immediately after the cold open]
+ Use this exact line once (do not rewrite it, do not add a date, do not repeat the episode number on the next line):
+ {intro_line}
+ If the cold open already contained the episode number, still speak this identity line exactly once and do not re-say the number again in the following sentence.
```

**`shows/prompts/models_agents_podcast.txt`** (prompt) — Ep200 same-episode paraphrase triples are listener-facing padding under the new grok-4.6 script stage. Shape ban + verbatim “no second opening fact” with no replacement menu (meta-rule). Narrower than a fourth full content_discipline rewrite. A/B-listen.
```diff
- SHAPE OF IDEAL STORY COVERAGE (the ratio to hit on every item — described, never copied): what shipped, with the exact model or tool name and version and the lab named; a benchmark or capability number with its comparison point; the price or license; where and when it is available; one more concrete detail the source carries; then the next item's first fact. Zero commentary sentences. Write it fresh every time.
+ SHAPE OF IDEAL STORY COVERAGE (the ratio to hit on every item — described, never copied): what shipped, with the exact model or tool name and version and the lab named; a benchmark or capability number with its comparison point; the price or license; where and when it is available; one more concrete detail the source carries; then the next item's first fact. Zero commentary sentences. Write it fresh every time.
+ SAME-EPISODE NO-RESTATE: never deliver the same item's opening fact twice in different words (Ep200 restated the Python 3.15 matrix line, the temperature-zero flip formula, and the clinical safety-prompt item ~2–3× each). If a fact is already spoken, add only a new number/name/limit or move on.
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/models_agents.yaml`** (config): UTH recovered to 10/10 after Oct-5 digest_section fallback; ep197/199/200 still ship sparse mega-blobs because the host never speaks Model Updates/Agent/Practical labels (prompt forbids spoken section titles). Mirror digest_section on those markers so chapter boundaries track the digest without changing audio. Does not replace deferred digest-driven mid-item titles; keep Under the Hood block as-is.
- **`tests/test_models_agents_quality_pass.py`** (code): Playbook: every behavioral fix gets a drift-guard; wiring guards must load real YAML via load_config (not stand-ins). Day-old tolerance avoids false red on in-flight runs.

## Deferred (carried forward)
- OPERATOR DECISION (length — escalated after July-19 + Aug-2 misses + continued 8/10 under): (A) min_digest_words=1600, (B) UTH digest licensed-knowledge/fact floor, or (C) lower min_podcast_words to ~1200–1400 natural length. Never re-enable podcast_expand_below_target; never silent-third-file 1600.
- OPERATOR DECISION (entity retention — three identical podcast-prompt filings Sep-8/Sep-13/Oct-2 all shipped:[] / missed): pick a different lever (data-side name list, rewrite-gate on dropped entities) or accept names-kept <75% on half the window; do not re-file the same keep-exact-names paragraph a fourth time.
- OPERATOR DECISION (digest-verbatim / section-header paste): wait for grok-4.6 script-stage readout (experiment models-agents-script-grok46-2026-10-11) before another content_discipline paragraph; median still ~43%.
- Digest-driven / position-aware mid-item chapter titles (network-wide; digest_section helps section rows only).
- RSS title truncation ownership (hook under 120 vs 100-char title cap vs title-bundle optimized title).
- Same-day double publish Ep155+Ep156 prune (operator; renumbering unsafe).
- podcast:transcript from pre-pronunciation text or Whisper post-correct (network-wide LoRA/RAG/Quinn class).
- July-2 selection rebalance A/B (lab product/feature announcements outrank preprints; arXiv items ≤40%).
- Narrative tracker: advance last_mentioned only on headline mentions; seed-only last_major_update nulls (data-side).
- MAB sibling: Big Story / Deep Dive / Cool Stuff / Quick Bits required-anchor treatment.
- Sunday weekly_summary_segment must synthesize, not splice dailies’ sentences.
- Brand anchors pop the hood / Before we go / pinned closing — do_not_retry de-seed or multi-variant closing re-expand.
- UTH distinct-subject residual (ep195 Falcon-H1 family news+UTH; ep197 emotion-steering news+UTH) — tied to option B fact/distinct floor if operator picks it.
- OP3 first-week ~20 dl/ep and YT long retention ~12% — watch; no enclosure/path bug found this pass.

## Drift-guard status
```
============================= test session starts ==============================
collected 14 items

tests/test_models_agents_quality_pass.py ..............                  [100%]

============================== 14 passed in 0.33s ==============================
```

<sub>tokens: 69147 in / 7686 out</sub>