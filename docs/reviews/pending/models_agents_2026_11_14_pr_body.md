Option C length and brand anchors hold, but Under the Hood is missing from 7/10 recent chapters (ep226–231/233) with only ep225/232/234 carrying it, names-kept stays ~5/10 ≥75% after names_to_keep, and non-UTH digest_section wiring remains correctly do_not_retry.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1991**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes with Under the Hood chapter AND spoken pop-the-hood anchor when digest has ### Under the Hood, last 10 | miss | Only ep225/232/234 have UTH chapters; ep226 full drop; ep230 speaks pop-the-hood but no chapter row; ep227-231/233 lack UTH — 3/10 vs expected ≥9/10 |
| episodes below live min_podcast_words (1200), last 10 | hit | 0/10 under 1200 (shortest ep232=1272); option C floor holds |
| script_entity_retention_pct ≥75%, last 10 (post names_to_keep wiring verify) | partial | 5/10 ≥75% (77-86% on ep227/228/231/232/233); tail ep225=57 ep226=52 ep229=54 — short of ≥6/10 |
| digest-verbatim median last 10 (grok-4.6 hold) | hit | median ~14% (range 2-27%) well under ≤35% hold bar |
| "Everyone talks/Most people" UTH opener + keep-an-eye teaser (regression) | hit | 0 contrast-cliché when UTH airs; 0 keep-an-eye; Before we go holds on ep230-234 |
| named Model Updates/Agent/Practical section chapter rows forced via digest_section | miss | n/a-lever-not-shipped / do_not_retry — story-auto + Also Today shape; only ep227 named Model Updates row |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/models_agents_podcast.txt`** (prompt) — Belt-and-suspenders with the code gate for ep226-class full-section drops. Meta-rule: shape + verbatim presence, no quotable tic menu. A/B-listen required (landmine #17).
```diff
- Under the Hood / deep-dive guidance already requires pop-the-hood in the deep dive's first sentence when the section is written, but does not hard-fail a full section drop when the digest carried ### Under the Hood.
+ One short mandatory-presence belt: if the briefing contains Under the Hood, the script MUST include that deep-dive with pop-the-hood in its opening sentence — never skip the section entirely. Shape only; no replacement opener menu; no length pressure.
```

## Code/metadata-only proposals (no A/B needed)
- **`engine/generator.py`** (code): P0 structure: 7/10 recent episodes missing UTH chapter and/or body after Nov-6 already flagged ep226. Code presence gate beats a third prompt-only reminder. ab_listen false — guard only fires on non-compliant scripts.
- **`tests/test_models_agents_quality_pass.py`** (code): Playbook: every behavioral fix gets a drift-guard; wiring guards use real YAML (Oct-1 frame-memory lesson); honor do_not_retry on non-UTH digest_section.

## Deferred (carried forward)
- Digest-driven / position-aware mid-item chapter titles (network-wide; story autos preferred after Nov-1 rejected section-label wiring)
- RSS title truncation ownership (hook under 120 vs 100-char title cap vs title-bundle optimized title)
- Same-day double publish Ep155+Ep156 prune (operator; renumbering unsafe)
- podcast:transcript from pre-pronunciation text or Whisper post-correct (network-wide LoRA/RAG/Quinn class)
- July-2 selection rebalance A/B (lab product/feature announcements outrank preprints; arXiv items ≤40%)
- Narrative tracker: advance last_mentioned only on headline mentions; seed-only last_major_update nulls (data-side)
- MAB sibling: Big Story / Deep Dive / Cool Stuff / Quick Bits required-anchor treatment
- Sunday weekly_summary_segment must synthesize, not splice dailies' sentences
- Brand anchors pop the hood / Before we go / pinned closing — do_not_retry de-seed or multi-variant closing re-expand
- UTH distinct-subject residual — readout via deep_dive_distinct_measure / deep_dive_fetched_source before more prompt text
- names-kept: if still ≤5/10 ≥75% after another full cohort with wiring green, operator accept metric vs entity-drop rewrite-gate only (no fourth podcast entity paragraph)
- facts×2 / copied section-header residual — watch one more grok-4.6 cohort before another content_discipline paragraph
- OP3 7d 243 (−21.1% WoW), YT long ~9.7% — watch; no enclosure/path bug this pass
- Sep-24 source_integrity / per-ep x.com snapshot fields — instrumentation, not show prompt
- Non-UTH digest_section on Model Updates/Agent/Practical — do_not_retry (Nov-1 replay)

## Drift-guard status
```
============================= test session starts ==============================
collected 14 items

tests/test_models_agents_quality_pass.py ..............                  [100%]

============================== 14 passed in 0.28s ==============================
```

<sub>tokens: 82304 in / 5753 out</sub>