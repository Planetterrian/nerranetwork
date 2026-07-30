Snapshot shows 10/10 episodes below 1700-word floor plus recurring network boilerplate (10/10) and ephemeris filter leakage (ep137/138/143 transcripts); all prior chapter/stock/garble fixes remain clean.

_Generated on **grok-4.3** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.0642**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes below 1700-word floor | partial | 10/10 episodes below floor (snapshot); still digest-ceiling limited |
| occurrences of network-plug boilerplate in _tts.txt | hit | 10/10 episodes contain the exact network-closing sentences |
| ephemeris/sky-tonight title leakage in shipped digests | partial | Ep137/138/143 transcripts still contain almanac titles matching the planet pattern |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/fascinating_frontiers_podcast.txt`** (prompt) — Reduces the 6-9/10-episode teaser tic observed in transcripts while preserving forward-looking function; de-seed uses shape + verbatim ban + rotation memory
```diff
- Before we go — briefly tease something listeners should watch for in the next episode based on developing stories from today's news. Keep it specific and forward-looking: "Next time, we'll be watching for..." or "Keep an eye on..." This builds habitual listening.
+ Before we go — briefly tease something listeners should watch for in the next episode based on developing stories from today's news. Keep it specific and forward-looking. Never open the teaser with the phrase "keep an eye on" or "watch for". Use a fresh forward-looking sentence each episode and record the exact opener used so the same phrasing is never reused within 30 days. This builds habitual listening.
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/fascinating_frontiers.yaml`** (config): Addresses remaining fetch-filter leakage visible in Ep137/138/143 transcripts (deterministic, no audio change)

## Deferred (carried forward)
- Cosmic Deep Dive length lever (carried; four-show A/B still open)
- Mid-section digest-driven chapter titles (network lever)
- Theme residual "science nasa" (low harm)
- Curated narrative-tracker status pass (operator task)
- Ephemeris title-filter tuning (still leaking on some patterns)

## Drift-guard status
```
============================= test session starts ==============================
collected 17 items

tests/test_fascinating_frontiers_quality_pass.py .................       [100%]

============================== 17 passed in 0.35s ==============================
```

<sub>tokens: 48606 in / 1369 out</sub>