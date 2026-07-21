This pass finds persistent under-length (9/10 episodes below 1700-word floor) and recurring network-plug boilerplate tics (10/10 episodes) with fetch-filter leakage on ephemeris titles still visible in transcripts; all prior chapter-order, stock-filter, and garble fixes remain clean.

_Generated on **grok-4.3** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.0646**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes below 1700-word floor | partial | 9/10 episodes below floor (snapshot); still digest-ceiling limited |
| occurrences of network-plug boilerplate in _tts.txt | hit | 10/10 episodes contain the exact network-closing sentences |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/fascinating_frontiers_podcast.txt`** (prompt) — Reduces the 6-9/10-episode teaser tic observed in transcripts while preserving forward-looking function
```diff
- Keep an eye on…
+ Line-anchored teaser openers only; ban exact 'keep an eye on the' phrasing for one full rotation cycle
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/fascinating_frontiers.yaml`** (config): Addresses remaining fetch-filter leakage visible in Ep126/128/134 transcripts (deterministic, no audio change)

## Deferred (carried forward)
- Cosmic Deep Dive length lever (carried; four-show A/B still open)
- Mid-section digest-driven chapter titles (network lever)
- Theme residual 'science nasa' (low harm)
- Curated narrative-tracker status pass (operator task)

## Drift-guard status
```
============================= test session starts ==============================
collected 17 items

tests/test_fascinating_frontiers_quality_pass.py .................       [100%]

============================== 17 passed in 0.33s ==============================
```

<sub>tokens: 49434 in / 1143 out</sub>