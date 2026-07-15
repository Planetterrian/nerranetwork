Length ceiling and rigid boilerplate tics persist (6/10 episodes <1300w, 'from an engineering standpoint' and 'quick market note' in 10/10); no new P0s; prior length/teaser predictions scored miss.

_Generated on **grok-4.3** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.0622**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes >=1300w in next 10 | miss | only 4/10 (Ep27-30,32-33); Ep24-26,31 remain 949-1259w |
| tomorrow-teaser frame count | miss | still 8/10 episodes use the exact 'Watch for the [first/next] <test>' frame |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/spacex_podcast.txt`** (prompt) — teaser frame hardening into tic (8/10); low-risk rotation to restore variety
```diff
- Patrick: Before we go — tease something specific listeners should watch for, drawn from today's developing stories.
+ Patrick: Before we go — [rotate among: 'the next item to watch is', 'keep an eye on', 'coming up next is'] something specific listeners should watch for, drawn from today's developing stories.
```

**`shows/prompts/spacex_digest.txt`** (prompt) — explicit floor vs own spec; A/B only after four-show length decision
```diff
- ### Engineering Deep Dive
- This is the flagship section — a flowing 3-paragraph engineering analysis (4–6 sentences each; ~280–360 words total — do not ship a short stub)
+ ### Engineering Deep Dive
+ This is the flagship section — a flowing 3-paragraph engineering analysis (4–6 sentences each; ~280–360 words total — do not ship a short stub). Target 300+ words on thin-news days.
```

## Deferred (carried forward)
- Engineering Deep Dive length floor (pending four-show A/B)
- SPCX price spoken twice (observe post-reorder)
- tomorrow-teaser rotation if frame deadens
- junk-title filter prediction from network pass still pending

<sub>tokens: 47872 in / 942 out</sub>