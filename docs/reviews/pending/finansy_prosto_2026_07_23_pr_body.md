This pass finds persistent under-length episodes (9/10 below 1000w), 10+ cross-episode boilerplate tics shipping in transcripts, and a pending ledger prediction that can now be scored hit; proposes digest-only length levers and shape-based de-seeds.

_Generated on **grok-4.3** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.0445**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| spoken source-scaffold lines («Сорс …» / «Source …») | hit | No scaffold lines appear in Ep66-75 transcripts |
| median FP _tts.txt words | miss | 9/10 episodes still below 1000w per snapshot |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/fp_digest.txt`** (prompt) — digest-substrate lever only (per July meta-review); de-seed by shape + memory list to avoid example convergence
```diff
- current tip/quick-news/article counts and example phrasing
+ raise to 3-4 tips / 3 quick-news / 5-7 articles; add shape-only de-seed rule + verbatim ban list from recent episodes; require rotated deep-dive entry points
```

**`shows/prompts/fp_podcast.txt`** (prompt) — prevents padding ban violation while allowing digest-driven growth
```diff
- current length targets and example sentences
+ align length language to reachable digest output; ban verbatim tic phrases by shape description only
```

## Deferred (carried forward)
- podcast-prompt length-target reconciliation after digest expansion lands
- operator cadence confirmation (even-days vs mixed dispatch)

## Drift-guard status
```
============================= test session starts ==============================
collected 14 items

tests/test_finansy_prosto_quality_pass.py ..............                 [100%]

============================== 14 passed in 0.18s ==============================
```

<sub>tokens: 33730 in / 945 out</sub>