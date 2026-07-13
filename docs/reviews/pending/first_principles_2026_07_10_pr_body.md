Persistent short scripts (5/10 episodes below 1500w floor) and recurring boilerplate tics ('rough magic wand estimate' 7/10, 'on the order of' 8/10) remain after prior length/lesson fixes.

_Generated on **grok-4.3** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.0535**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes below 1500-word floor in last 10 _tts.txt | partial | 5/10 still below vs 4/10 baseline |
| occurrences of 'a rough magic wand estimate' across 10 transcripts | miss | 7/10 transcripts still contain it |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/first_principles_podcast.txt`** (prompt) — Break recurring tic while preserving hedging language
```diff
- a rough magic wand estimate
+ a back-of-the-envelope floor
```

**`shows/prompts/first_principles_podcast.txt`** (prompt) — Vary second most common tic
```diff
- on the order of
+ roughly
```

## Deferred (carried forward)
- Garbage auto-segment chapter titles (shared network LLM-title class)
- Further length escalation (do_not_retry)

## Drift-guard status
```
============================= test session starts ==============================
collected 16 items

tests/test_first_principles_quality_pass.py ................             [100%]

============================== 16 passed in 1.07s ==============================
```

<sub>tokens: 41337 in / 728 out</sub>