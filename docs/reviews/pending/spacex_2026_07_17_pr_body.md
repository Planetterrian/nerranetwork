Length ceiling and rigid boilerplate tics persist (ep26/ep35 <1300w; 'from an engineering standpoint' and 'on the ai front' in 10/10 episodes); prior length/teaser predictions scored miss; no new P0s.

_Generated on **grok-4.3** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.0627**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes >=1300w in next 10 | miss | only 8/10 (Ep27-30,32-34); Ep26,35 still 1196w/1264w |
| tomorrow-teaser frame count | miss | still 8/10 episodes use the exact 'Watch for the [first/next] <test>' frame |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/spacex_podcast.txt`** (prompt) — rigid marker now a tic (10/10); low-risk rotation restores variety
```diff
- REQUIRED: the segment's first sentence must contain "from an engineering standpoint" or "the engineering angle"
+ REQUIRED: the segment's first sentence must contain "from an engineering standpoint" or "the engineering angle"; rotate the exact opener daily across at least four variants
```

**`shows/prompts/spacex_podcast.txt`** (prompt) — teaser frame hardening into dead rotation (8/10); low-risk rotation to restore variety
```diff
- Patrick: Before we go — tease something specific listeners should watch for, drawn from today's developing stories.
+ Patrick: Before we go — tease something specific listeners should watch for, drawn from today's developing stories. Rotate the exact teaser opener daily across at least four variants (e.g. "Keep an eye on", "Watch for", "The next data point is", "One thing to track").
```

**`shows/prompts/spacex_digest.txt`** (prompt) — explicit floor vs own spec; A/B only after four-show length decision
```diff
- On thin-news days, LENGTHEN the Engineering Deep Dive first — it is the licensed-knowledge length lever (target ~280–360 words / three full paragraphs of 4–6 sentences each).
+ On thin-news days, LENGTHEN the Engineering Deep Dive first — it is the licensed-knowledge length lever (target ~280–360 words / three full paragraphs of 4–6 sentences each). Enforce a hard 280-word minimum for this section before expanding Top News.
```

## Deferred (carried forward)
- Engineering Deep Dive length floor (pending four-show A/B)
- SPCX price spoken twice (observe post-reorder)
- tomorrow-teaser rotation if frame deadens
- junk-title filter prediction from network pass still pending

<sub>tokens: 47923 in / 1137 out</sub>