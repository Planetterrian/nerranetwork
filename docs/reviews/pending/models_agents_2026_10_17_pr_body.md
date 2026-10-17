UTH chapters and pop-the-hood hold 10/10, grok-4.6 cut digest-verbatim median to ~33% (≤35% target hit), and downloads rebounded, but 6/10 scripts stay under 1500w, names-kept remains ~4/10 ≥75%, and sparse mega-blob chapters (ep197/199/200) still lack non-UTH digest_section wiring proposed Oct-11 and never applied.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1943**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes with Model Updates chapter row when digest has Model Updates, last 10 | partial | ep197 mega Model Updates blob; ep199/200 no separate Model Updates/Agent/Practical rows; ep201–206 mostly per-story autos; Oct-11 digest_section wiring never merged |
| chapters with raw mid-sentence auto-titles (ellipsis or >40 chars lowercase start), last 10 | partial | truncated autos ep201/203 remain; fewer ellipsis than Oct-11; not locked ≤2/10 |
| Under the Hood chapter when deep-dive present, last 10 (regression watch) | hit | 10/10 ep197–206 chapters_ep*.json include Under the Hood |
| EN identity line speaks episode number exactly once, last 10 | hit | ep202–206 EN identity speaks episode number once; Ep200 double not repeated in provided tail |
| same-episode verbatim restated fact-blocks (≥2 near-duplicate sentence pairs on one item), last 5 | partial | facts×2 ep203=4, ep204=6, ep205=5 on density audit; not ≤1/5 episodes clean |
| digest-verbatim median last 10 under podcast_model grok-4.6 | hit | ep197–206 digest-verbatim median ~33% (range 7–64%) meets ≤35% experiment target |
| episodes below min_podcast_words (1500), last 10 | miss | 6/10 under 1500w; operator A/B/C still open — do not score silent 1600 hope |
| script_entity_retention_pct ≥75%, last 10 | miss | only 4/10 ≥75% (61/86/58/70/63/77/84/57/69/79); fourth identical podcast entity prompt is do_not_retry |
| "Everyone talks/Most people" UTH opener + keep-an-eye teaser (regression) | hit | 0/10 contrast-cliché UTH openers and 0 keep-an-eye teasers in ep202–206 samples; pop-the-hood + Before we go hold |
| source_integrity_claims median (Sep-24 sourcing) | partial | fetch_full_text:12 + preferred_domains + x_only_lead live; snapshot has no per-ep integrity score field |
| sources on x.com per episode (Sep-24 sourcing) | partial | x_posts_as_sources secondary + lint live; per-ep x.com counts not in snapshot |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
None.

## Code/metadata-only proposals (no A/B needed)
- **`shows/models_agents.yaml`** (config): UTH recovered to 10/10 after Oct-5 digest_section fallback; ep197/199/200 still ship sparse mega-blobs because the host never speaks Model Updates/Agent/Practical labels. Mirror digest_section on those markers so chapter boundaries track the digest without changing audio. Re-files the Oct-11 config proposal that never merged (shipped:[]). Does not replace deferred digest-driven mid-item titles; keep Under the Hood block as-is.
- **`tests/test_models_agents_quality_pass.py`** (code): Playbook: every behavioral fix gets a drift-guard; wiring guards must load real YAML via load_config (Oct 1 frame-memory empty-render lesson). Day-old tolerance avoids false red on in-flight runs.

## Deferred (carried forward)
- OPERATOR DECISION (length — escalated after July-19 + Aug-2 misses + continued under-floor rate; today 6/10 under 1500w): (A) min_digest_words=1600, (B) UTH digest licensed-knowledge/fact + distinct-subject floor, or (C) lower min_podcast_words to ~1200–1400 natural length. Never re-enable podcast_expand_below_target; never silent-third-file 1600.
- OPERATOR DECISION (entity retention — three identical podcast-prompt filings Sep-8/Sep-13/Oct-2 all shipped:[] / missed; fourth filing do_not_retry): pick a different lever (data-side name list, rewrite-gate on dropped entities) or accept names-kept <75% on half the window.
- UTH distinct-subject residual (ep206 Perplexity sandbox Top Story + credential-scoping UTH same family; earlier Falcon-H1 / emotion-steering pairs) — tied to option B if operator picks it.
- Digest-driven / position-aware mid-item chapter titles (network-wide; digest_section helps section rows only).
- RSS title truncation ownership (hook under 120 vs 100-char title cap vs title-bundle optimized title).
- Same-day double publish Ep155+Ep156 prune (operator; renumbering unsafe).
- podcast:transcript from pre-pronunciation text or Whisper post-correct (network-wide LoRA/RAG/Quinn class).
- July-2 selection rebalance A/B (lab product/feature announcements outrank preprints; arXiv items ≤40%).
- Narrative tracker: advance last_mentioned only on headline mentions; seed-only last_major_update nulls (data-side).
- MAB sibling: Big Story / Deep Dive / Cool Stuff / Quick Bits required-anchor treatment.
- Sunday weekly_summary_segment must synthesize, not splice dailies’ sentences.
- Brand anchors pop the hood / Before we go / pinned closing — do_not_retry de-seed or multi-variant closing re-expand.
- Truncated chapter auto-titles (ep201/203) — re-diagnose with engine title max if ≥3/10 recur next pass.
- Same-episode facts×2 restatement residual (ep203–205) — watch one more grok-4.6 cohort before another content_discipline paragraph.
- OP3 first-week ~25 dl/ep recovery and YT long retention ~12% — watch; no enclosure/path bug found this pass.

## Drift-guard status
```
============================= test session starts ==============================
collected 14 items

tests/test_models_agents_quality_pass.py ..............                  [100%]

============================== 14 passed in 0.62s ==============================
```

<sub>tokens: 78066 in / 6357 out</sub>