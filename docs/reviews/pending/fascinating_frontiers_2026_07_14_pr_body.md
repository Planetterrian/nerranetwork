Snapshot shows persistent under-length (7/10 episodes below 1700-word floor) plus recurring boilerplate tics in transcripts; prior stock-filter, chapter-order, and garble fixes remain clean.

_Generated on **grok-4.3** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.0651**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| 0 market-action items in Ep115 recap | hit | Ep115 recap clean per network pass 2026-07-02 |
| 0 launch/mission titles false-dropped | hit | Ep122-131 kept Falcon 9, Roman, Artemis coverage |
| every episode has Closing as last marker | hit | chapters_ep122-131.json all end Tomorrow Teaser → Closing |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/fascinating_frontiers_podcast.txt`** (prompt) — Reduces the 6/10-episode 'keep an eye on the' tic observed in transcripts.
```diff
- Use this exact teaser opener (do not rewrite it): {teaser_line}
+ Rotate among three forward-looking openers drawn from digest items; never repeat the same phrase two episodes in a row.
```

**`shows/prompts/fascinating_frontiers_podcast.txt`** (prompt) — Direct response to 7/10 episodes landing below 1700 words while staying inside the digest ceiling.
```diff
- Cover 12-14 stories from the digest's Top 15 list
+ Cover 13-15 stories; if digest supplies 15 items, use all 15 unless an item is <2 sentences.
```

## Deferred (carried forward)
- Cosmic Deep Dive length lever (carried; four-show A/B still open)
- Mid-section digest-driven chapter titles (network lever)
- Theme residual "science nasa" (low harm)
- Curated narrative-tracker status pass (operator task)

## Drift-guard status
```
============================= test session starts ==============================
collected 17 items

tests/test_fascinating_frontiers_quality_pass.py .................       [100%]

============================== 17 passed in 0.26s ==============================
```

<sub>tokens: 49952 in / 1053 out</sub>