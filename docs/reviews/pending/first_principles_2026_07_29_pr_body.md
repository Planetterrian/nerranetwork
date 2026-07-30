Persistent shorts (6/10 episodes below 1500w floor) and recurring boilerplate tics ('on the order of' in 6/10 transcripts plus expected disclosures/sign-offs) with chapters clean; prior length/tic predictions scored partial/miss; no P0s; digest-stage levers only per category rules.

_Generated on **grok-4.3** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.0547**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes below 1500-word floor in last 10 _tts.txt | partial | 6/10 below vs 3/10 baseline (ep45 1403w, ep47 1337w, ep48 1341w, ep49 1425w, ep51 1293w, ep52 1320w) |
| occurrences of 'on the order of' across 10 transcripts | miss | phrase present in 6/10 transcripts (ep45,46,48,49,52,54); prior 'rough magic wand estimate' absent |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/first_principles_episode.txt`** (prompt) — De-seed recurring 'on the order of' tic by shape description + verbatim ban + rotation MEMORY per July 2026 meta-review category rule; A/B-listen required (landmine #17).
```diff
- Estimate the raw-material floor for this thing, reasoning out loud: name the major materials and their rough commodity values, add them up, and clearly flag every estimate AS an estimate.
+ Estimate the raw-material floor for this thing, reasoning out loud: name the major materials and their rough commodity values, add them up, and clearly flag every estimate AS an estimate. Never open any segment with the phrase 'on the order of'; use fresh per-episode phrasing that varies sentence shape while preserving hedging. Maintain a per-show rotation memory of the last 8 episodes' hedging openers and avoid reuse.
```

## Deferred (carried forward)
- Garbage auto-segment chapter titles (shared network LLM-title class)
- Further length escalation (do_not_retry)

## Drift-guard status
```
============================= test session starts ==============================
collected 16 items

tests/test_first_principles_quality_pass.py ................             [100%]

============================== 16 passed in 0.86s ==============================
```

<sub>tokens: 41694 in / 1013 out</sub>