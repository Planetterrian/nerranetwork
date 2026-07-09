Persistent short scripts on 4/10 recent episodes plus recurring boilerplate tics ('rough magic wand estimate' 7/10, 'on the order of' 8/10) that prior length/lesson fixes did not address.

_Generated on **grok-4.3** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.0547**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| consecutive same-category episodes (concrete vs opportunity) | hit | Ep025-034 alternate with no adjacent duplicates |
| spoken markdown-style sub-headings in _tts.txt | hit | None appear in any of the 10 Whisper transcripts |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/first_principles_episode.txt`** (prompt) — Replace the recurring phrase with a fresh variant to break the tic
```diff
- A rough magic wand estimate
+ A first-principles floor estimate
```

**`shows/prompts/first_principles_podcast.txt`** (prompt) — Vary the second most common tic while preserving hedging
```diff
- on the order of
+ roughly
```

## Deferred (carried forward)
- Garbage auto-segment chapter titles (shared network LLM-title class)

## Drift-guard status
```
============================= test session starts ==============================
collected 16 items

tests/test_first_principles_quality_pass.py ................             [100%]

============================== 16 passed in 1.01s ==============================
```

<sub>tokens: 42292 in / 745 out</sub>