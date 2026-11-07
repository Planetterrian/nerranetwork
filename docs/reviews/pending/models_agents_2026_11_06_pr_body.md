Option C length (1200w) and names_to_keep shipped and hold the floor, but ep226 dropped Under the Hood entirely, names-kept stays ~4/10 ≥75% after the data-side lever, and the thrice-filed non-UTH digest_section wiring is correctly do_not_retry after the Nov-1 replay.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.2201**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes with distinct Model Updates chapter row when digest has Model Updates, last 10 | miss | Only ep223 named Model Updates/Agent/Practical; ep217–222/224–226 story-autos + Also Today; digest_section lever now do_not_retry |
| episodes with Agent & Tool Developments and/or Practical & Community chapter rows when those digest sections have items, last 10 | miss | 0/10 distinct Agent/Practical rows except ep223; same closed lever |
| Under the Hood chapter when deep-dive present, last 10 (regression watch) | partial | 9/10 ep217–225 have UTH; ep226 chapters_ep226.json + EN transcript omit UTH and pop-the-hood entirely |
| chapters_ep*.json titles containing "](" or "http", or early Practical & Community before 25% of script | hit | 0 link titles and 0 early P&C mis-fires in ep217–226 |
| digest-verbatim median last 10 (grok-4.6 cohort hold) | hit | median ~20% (range 7–29%) under ≤35% hold bar |
| episodes below min_podcast_words (1500), last 10 | hit | Option C shipped Nov-1: live min_podcast_words=1200; 0/10 under 1200 (ep218–220 sit in accepted 1200–1400 band) |
| script_entity_retention_pct ≥75%, last 10 | miss | only 4/10 ≥75% (80/82/70/73/78/59/81/63/57/52) after names_to_keep:true; ep226=52% |
| "Everyone talks/Most people" UTH opener + keep-an-eye teaser (regression) | hit | 0 contrast-cliché UTH openers when UTH airs; 0 keep-an-eye teasers; Before we go holds |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/models_agents_podcast.txt`** (prompt) — Belt-and-suspenders with the code gate for ep226-class full-section drops. Shape + mandatory presence only; no replacement tic menu (meta-rule). A/B-listen required (landmine #17).
```diff
- [Under the Hood section already requires pop the hood in the deep dive's first sentence; no explicit 'never omit the whole section when the briefing has it' line — ep226 omitted the block entirely.]
+ Add one shape rule under the Under the Hood structural block (no quotable opener menu): If the briefing contains an Under the Hood / deep-dive section, the script MUST deliver that section in full with the required pop-the-hood anchor in its first sentence — never drop the deep dive to shorten the episode or to jump to Things to Try. If the briefing has no Under the Hood section, skip it.
```

## Code/metadata-only proposals (no A/B needed)
- **`engine/generator.py (or run_show podcast accept path)`** (code): P0/P1 structure: ep226 is a full deep-dive drop after 9/10 UTH holds. Enforcing the existing Sep-4 required anchor in code beats a third prompt reminder. ab_listen false — guard only fires on non-compliant scripts.
- **`tests/test_models_agents_quality_pass.py`** (code): Playbook: every behavioral fix gets a drift-guard; wiring guards must use real YAML (Oct-1 frame-memory empty-render lesson); day-old tolerance avoids false red on today’s run.

## Deferred (carried forward)
- Digest-driven / position-aware mid-item chapter titles (network-wide; story autos preferred after Nov-1 rejected section-label wiring)
- RSS title truncation ownership (hook under 120 vs 100-char title cap vs title-bundle optimized title)
- Same-day double publish Ep155+Ep156 prune (operator; renumbering unsafe)
- podcast:transcript from pre-pronunciation text or Whisper post-correct (network-wide LoRA/RAG/Quinn class)
- July-2 selection rebalance A/B (lab product/feature announcements outrank preprints; arXiv items ≤40%)
- Narrative tracker: advance last_mentioned only on headline mentions; seed-only last_major_update nulls (data-side)
- MAB sibling: Big Story / Deep Dive / Cool Stuff / Quick Bits required-anchor treatment
- Sunday weekly_summary_segment must synthesize, not splice dailies’ sentences
- Brand anchors pop the hood / Before we go / pinned closing — do_not_retry de-seed or multi-variant closing re-expand
- UTH distinct-subject residual — readout via existing deep_dive_distinct_measure / deep_dive_fetched_source lints before more prompt text
- names-kept: if wiring-green and still ≤4/10 ≥75% after another full cohort, operator choose accept metric vs entity-drop rewrite-gate (new lever only — no fourth podcast entity paragraph)
- facts×2 / copied section-header residual — watch one more grok-4.6 cohort before another content_discipline paragraph
- OP3 first-week ~29 dl/ep, −12.6% WoW, YT long ~11.1% — watch; no enclosure/path bug this pass
- Sep-24 source_integrity / per-ep x.com snapshot fields still missing — instrumentation, not show prompt

## Drift-guard status
```
============================= test session starts ==============================
collected 14 items

tests/test_models_agents_quality_pass.py ..............                  [100%]

============================== 14 passed in 0.40s ==============================
```

<sub>tokens: 92556 in / 5826 out</sub>