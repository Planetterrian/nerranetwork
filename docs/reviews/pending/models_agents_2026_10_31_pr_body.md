UTH chapters and brand anchors hold, but 6/10 scripts stay under 1500w, names-kept remains ~3/10 ≥75%, and non-UTH section chapters still lack the digest_section wiring proposed Oct-11/Oct-17 and never applied—re-propose that config-only fix and keep length/entity as escalated operator decisions.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.2017**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes with distinct Model Updates (or equivalent news-body) chapter row when digest has Model Updates, last 10 | miss | ep211–220 lack separate Model Updates section rows; per-story autos + Also Today only; Oct-11/17 digest_section wiring never merged |
| episodes with Agent & Tool Developments and/or Practical & Community chapter rows when those digest sections have items, last 10 | miss | 0/10 distinct Agent or Practical section rows in ep211–220 chapters_ep*.json |
| Under the Hood chapter when deep-dive present, last 10 (regression watch) | hit | 10/10 ep211–220 chapters_ep*.json include Under the Hood |
| chapters_ep*.json titles containing "](" or "http", or early Practical & Community before 25% of script | hit | 0 link titles and 0 early P&C mis-fires in ep211–220 |
| digest-verbatim median last 10 (grok-4.6 cohort hold) | hit | median ~18.5% (range 5–31%) well under ≤35% hold bar |
| episodes below min_podcast_words (1500), last 10 | miss | 6/10 under 1500w; operator A/B/C still open — n/a-lever-not-shipped on silent 1600 |
| script_entity_retention_pct ≥75%, last 10 | miss | only 3/10 ≥75% (59–82%); fourth identical podcast entity prompt is do_not_retry |
| "Everyone talks/Most people" UTH opener + keep-an-eye teaser (regression) | hit | 0/10 contrast-cliché UTH openers and 0 keep-an-eye teasers in ep216–220; pop-the-hood + Before we go hold |
| EN identity line speaks episode number exactly once, last 10 | hit | ep216–220 EN identity speaks episode number once; Ep200 double not repeated |
| same-episode verbatim restated fact-blocks / facts×2 residual, last 5 | partial | facts×2 ep213=7, ep214=5, ep218=7 on density audit; not clean across window |
| source_integrity_claims median (Sep-24 sourcing) | partial | fetch_full_text:12 + preferred_domains + x_only_lead live; snapshot has no per-ep integrity score field |
| sources on x.com per episode (Sep-24 sourcing) | partial | x_posts_as_sources secondary + lint live; per-ep x.com counts not in snapshot |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
None.

## Code/metadata-only proposals (no A/B needed)
- **`shows/models_agents.yaml`** (config): UTH recovered to 10/10 after Oct-5 digest_section fallback; Also Today got digest_section Oct-19. ep211–220 still ship 0 named Model Updates/Agent/Practical section rows because the host never speaks those labels. Mirror digest_section on those three markers so chapter boundaries track the digest without changing audio. Re-files the Oct-11 and Oct-17 config proposal that never merged (shipped:[] both times). Does not replace deferred digest-driven mid-item titles; keep Under the Hood and Also Today blocks as-is.
- **`tests/test_models_agents_quality_pass.py`** (code): Playbook: every behavioral fix gets a drift-guard; wiring guards must load real YAML via load_config (Oct 1 frame-memory empty-render lesson). Day-old tolerance avoids false red on in-flight runs.

## Deferred (carried forward)
- OPERATOR DECISION (length — escalated after July-19 + Aug-2 misses + continued under-floor rate; today 6/10 under 1500w): (A) min_digest_words=1600, (B) UTH digest licensed-knowledge/fact + distinct-subject floor, or (C) lower min_podcast_words to ~1200–1400 natural length. Never re-enable podcast_expand_below_target; never silent-third-file 1600.
- OPERATOR DECISION (entity retention — three identical podcast-prompt filings Sep-8/Sep-13/Oct-2 all shipped:[] / missed; fourth filing do_not_retry): pick a different lever (data-side name list, rewrite-gate on dropped entities) or accept names-kept <75% on half the window.
- UTH distinct-subject residual (ep220 Anthropic monitor news+UTH; earlier Falcon-H1 / emotion-steering / Perplexity pairs) — tied to option B if operator picks it.
- Digest-driven / position-aware mid-item chapter titles (network-wide; digest_section helps section rows only).
- RSS title truncation ownership (hook under 120 vs 100-char title cap vs title-bundle optimized title).
- Same-day double publish Ep155+Ep156 prune (operator; renumbering unsafe).
- podcast:transcript from pre-pronunciation text or Whisper post-correct (network-wide LoRA/RAG/Quinn class).
- July-2 selection rebalance A/B (lab product/feature announcements outrank preprints; arXiv items ≤40%).
- Narrative tracker: advance last_mentioned only on headline mentions; seed-only last_major_update nulls (data-side).
- MAB sibling: Big Story / Deep Dive / Cool Stuff / Quick Bits required-anchor treatment.
- Sunday weekly_summary_segment must synthesize, not splice dailies’ sentences.
- Brand anchors pop the hood / Before we go / pinned closing — do_not_retry de-seed or multi-variant closing re-expand.
- Same-episode facts×2 restatement residual (ep213/214/218) — watch one more grok-4.6 cohort before another content_discipline paragraph.
- OP3 first-week ~31 dl/ep and YT long retention ~11.4% — watch; no enclosure/path bug found this pass.

## Drift-guard status
```
============================= test session starts ==============================
collected 14 items

tests/test_models_agents_quality_pass.py ..............                  [100%]

============================== 14 passed in 0.49s ==============================
```

<sub>tokens: 81724 in / 6381 out</sub>