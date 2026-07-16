Snapshot shows 3/10 episodes below 1500-word floor with persistent 'on the order of' boilerplate tic; prior length/tic predictions scored partial/miss; no P0s, chapters clean.

_Generated on **grok-4.3** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.0537**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes below 1500-word floor in last 10 _tts.txt | partial | 3/10 below (ep35 1469w, ep39 1343w, ep40 1480w) vs 5/10 baseline |
| occurrences of 'a rough magic wand estimate' across 10 transcripts | miss | phrase absent from window; 'on the order of' persists in 8+/10 transcripts |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/first_principles_podcast.txt`** (prompt) — Break recurring 'on the order of' tic while preserving required hedging language
```diff
- Preserve the brief's hedging. If the brief says a figure is approximate, keep it approximate aloud ("roughly," "on the order of," "a rough estimate").
+ Preserve the brief's hedging. If the brief says a figure is approximate, keep it approximate aloud ("roughly," "a rough estimate," "on the scale of"). Rotate among at least three distinct hedging phrases per episode.
```

## Deferred (carried forward)
- Garbage auto-segment chapter titles (shared network LLM-title class)
- Further length escalation (do_not_retry)

## Drift-guard status
```
============================= test session starts ==============================
collected 16 items

tests/test_first_principles_quality_pass.py ................             [100%]

============================== 16 passed in 1.01s ==============================
```

<sub>tokens: 41362 in / 783 out</sub>