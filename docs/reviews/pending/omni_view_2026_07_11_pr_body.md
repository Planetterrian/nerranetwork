This pass finds persistent under-length episodes (ep102 at 1218w), verbatim boilerplate tics in 10/10 transcripts, and continued saturation of the 'Both sides agree X; they differ on whether Y' digest template (12/12 stories in Ep099).

_Generated on **grok-4.3** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.0539**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes (last 10) with a Closing chapter in chapters_ep*.json | hit | chapters_ep100–ep109.json all contain Closing |
| chapters with sentence-fragment / ellipsis titles (last 10 eps) | hit | 0 fragment/ellipsis titles in any chapters_ep*.json |
| max "the strongest case" count in any single episode (last 10) | partial | script clean but digest Ep085 shipped it 24× |
| episodes opening stories with anonymous "one side frames / the other side frames" (last 10) | hit | 0 anonymous frames in window |
| median _tts.txt words (last 10 eps) | miss | ep102=1218w; median still <1600 |
| "Both sides agree" constructions per episode digest | pending | 12/12 stories in Ep099 |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/omni_view_digest.txt`** (prompt) — Remove the literal seed that produces saturation (12/12 stories Ep099).
```diff
- Both sides agree on [factual basis]; they differ on [interpretation/priority].
+ Lead with the empirical ground both sides accept, then the divide; rotate at least three structures across stories; cap the construction at <=2 per digest.
```

**`shows/prompts/omni_view_podcast.txt`** (prompt) — Mirror the digest ban to prevent template echo in audio.
```diff
- Both sides agree that… / Both sides face comparable…
+ Only when sourced; otherwise delete; rotate at least three structures across stories.
```

## Deferred (carried forward)
- Milder "Both sides agree" frame still recurs — watch whether it becomes the next tic
- Chronic under-length (digest ceiling, four-show length A/B)
- Low OP3 downloads (network-funnel question)

## Drift-guard status
```
============================= test session starts ==============================
collected 11 items

tests/test_omni_view_quality_pass.py ...........                         [100%]

============================== 11 passed in 0.28s ==============================
```

<sub>tokens: 40626 in / 1245 out</sub>