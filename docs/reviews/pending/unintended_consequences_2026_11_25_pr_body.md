Prior Nov-12 length/target and people fixes largely held, but script fact-free rates stay 63–75% (driving Repetitive flags on Ep180–181), Environmental Intelligence cross-promo has converged on a stock bridge, and 4/10 scripts still sit under the 1100 floor with no podcast-side length lever left to pull.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1199**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| share of the last 7 episodes with digest_expansion_fired | partial | No expansion_fired in snapshot; min_digest 900 shipped and median words ~1053→1169, but 4/10 still <1100 — cannot confirm ≤3/7 firings |
| episodes naming at least two people in the script, last 10 | hit | ep176–183 routinely name ≥2 people (Wagner/Portman, Cowan/Bailey, Aquino/Guiang, Kemfert/Graichen, Foad, Modi+economists, MacBride/Byrne); ≥8/10 |
| daily audit Repetitive flags, last 7 episodes | hit | Snapshot flags Repetitive only on Ep180 and Ep181 (2/7 at expected ceiling) |
| podcast prompt still stating 2200-2800 words / 15-18 minutes | hit | STRUCTURAL REQUIREMENTS now brief-scaled with hard cap 1,700; 2200–2800/15–18m band absent |
| episodes skipped for length after 2026-11-12 | hit | Continuous ep174–183 publish window; no length skips |
| last-10 scripts containing the stock lesson couplet 'Incentive structures always find their loopholes' OR 'Complex systems resist simple interventions' | hit | Absent across ep174–183 transcripts after Segment-6 de-seed |
| median _tts.txt words, last 10 (after digest floor work) | partial | Median ≈1169 (was ≈1053); 6/10 clear 1100 but still short of ≥1200 expected |

**Merge tier: B (listen)** — see docs/REVIEW_AGENT.md, "Merge tiers".

## Applied in this branch — listen before merging (landmine #17)
These changes are committed on this branch. A rehearsal of the episode was dispatched on this branch (Actions → "Run show", rehearse); listen to its artifact, then merge or close.

**`shows/prompts/unintended_consequences_podcast.txt`** (prompt) — Density audit shows 63–75% fact-free script sentences (cohort 10–22%); Ep180/181 Repetitive flags track that padding. Nov-12 cut digest-expand padding; remaining driver is script-stage fact-free reflection. Shape rule only — no coverage% prediction.

**`shows/prompts/unintended_consequences_podcast.txt`** (prompt) — EI cross-promo converged on two stock bridges across ep174/178/180/181/183 despite 'write fresh'. Meta-review: de-seed by shape + verbatim ban; predict successor bridge tic.

**`shows/prompts/unintended_consequences_podcast.txt`** (prompt) — Density copied-sections high on ep177/179/180/182; scripts march the six-beat brief as narration. Shape-only re-scene steer; no overlap/coverage numeric gate (Sep 2026 meta misses).

## ⚠️ A/B-listen required — NOT applied (landmine #17)
None.

## Deferred (carried forward)
- Data-side UC closing-pool rotation in engine/intros.py — 6/10 still share 'That's the case for today. The lessons tend to travel further…' (supplied block; not a show-prompt fix)
- Data-side lesson/cross-promo rotation memory if stock bridges survive this prompt ban (prefer over a third prompt-only pass)
- Cap 'One might ask/object' ≤1/ep (July 2 A/B; still occasional on ep180/181)
- Missing-intro guard (June; double-greeting risk if bolted on)
- Re-clear Philippine land-reform topic (delete gate_blocks) once claim-repair has a scored track record
- Operator decision: accept ~8–10 min / ~1100–1300 spoken as the product vs further digest/research-depth investment only — do not re-enable podcast_expand or third-file the same floor story
- YouTube long-form retention (~12%) and X pause (x_enabled false since Nov 14) — network growth/distribution, not UC prompt
- Named-people lint (Nov-12 deferred)
- One ask in the closing block (network decision)
- Do not re-pin grok-4.6 whole-show without fresh staged trial (Aug 27 withdrawal still binds)

## Drift-guard status
```
============================= test session starts ==============================
collected 9 items

tests/test_unintended_consequences_quality_pass.py .........             [100%]

============================== 9 passed in 0.13s ===============================
```

<sub>tokens: 45242 in / 4910 out</sub>