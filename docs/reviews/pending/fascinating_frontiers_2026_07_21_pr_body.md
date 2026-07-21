Snapshot shows 9/10 episodes below 1700-word floor plus recurring network boilerplate (10/10) and ephemeris filter leakage (ep134 transcript); all prior chapter/stock/garble fixes remain clean.

_Generated on **grok-4.3** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.0633**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| ephemeris/sky-tonight title leakage in shipped digests | partial | Ep134 transcript still contains "Moon passes 2° south of Venus this afternoon" matching the planet pattern |
| occurrences of 'keep an eye on the' teaser opener across 10 episodes | hit | 6-9/10 episodes contain the exact teaser phrasing (Ep129-138 transcripts) |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/fascinating_frontiers_podcast.txt`** (prompt) — Reduces the 6-9/10-episode teaser tic observed in transcripts while preserving forward-looking function; de-seed uses shape + verbatim ban + rotation memory
```diff
- Before we go — briefly tease something listeners should watch for in the next episode based on developing stories from today's news. Keep it specific and forward-looking: "Next time, we'll be watching for..." or "Keep an eye on..."
+ Before we go — briefly tease something listeners should watch for in the next episode based on developing stories from today's news. Keep it specific and forward-looking using one of: "Next time we'll watch for...", "Watch for the upcoming...", or "The next development to track is..." (rotate; never repeat the same opener twice in one week).
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/fascinating_frontiers.yaml`** (config): Addresses remaining fetch-filter leakage visible in Ep134 transcript (deterministic, no audio change)

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

============================== 17 passed in 0.33s ==============================
```

<sub>tokens: 48040 in / 1311 out</sub>