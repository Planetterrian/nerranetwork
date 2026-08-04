Length ceiling (6/10 episodes <1300w) and rigid boilerplate tics persist; prior length/teaser predictions scored miss per ledger; no new P0s; de-seed tics by shape only.

_Generated on **grok-4.3** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.0646**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes >=1300w in next 10 | miss | only 4/10 (Ep40-42,46); Ep43-45,47-49 still 1148-1264w |
| tomorrow-teaser frame count | miss | still 8/10 episodes use the exact 'Watch for the [first/next] <test>' frame |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/spacex_podcast.txt`** (prompt) — rigid marker now a tic (9/10); de-seed by shape + verbatim ban + rotation memory per July 2026 meta-review
```diff
- REQUIRED: the segment's first sentence must contain "from an engineering standpoint" or "the engineering angle"
+ REQUIRED: open the Engineering Deep Dive with a sentence that names the engineering lens or first-principles angle on the chosen system; never reuse the exact prior opener phrase from the last three episodes
```

## Deferred (carried forward)
- Engineering Deep Dive ~280-360w floor in prompts (four-show A/B reason still holds)
- SPCX price spoken twice (observe post-reorder)
- Teaser rotation if frame goes fully dead
- Junk-title filter prediction from network pass still pending

<sub>tokens: 49818 in / 929 out</sub>