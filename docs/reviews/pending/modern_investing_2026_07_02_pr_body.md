Chronic under-length (7/10 episodes <1800w target) plus heavy boilerplate repetition; prior ledger predictions remain untestable with current data.

_Generated on **grok-4.3** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.0626**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| spoken closed-trade record vs tracker after migration | partial | No new tracker JSON; transcripts still reference MU single-day outcome without closure confirmation |
| times a single closed trade is reviewed on air | partial | MU appears in consecutive daily scripts but no explicit double-review violation shown |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/modern_investing_podcast.txt`** (prompt) — Eliminates 7/10-episode tic without changing lesson content
```diff
- This is the exact scenario where our earlier rule about volume confirmation would have helped
+ (remove seeded callback sentence entirely)
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/modern_investing.yaml`** (config): Temporary relaxation while digest ceiling is investigated; matches actual shipped lengths

## Deferred (carried forward)
- Prompt or audio changes
- Digest ceiling root-cause fix
- Chapter-marker robustness for Investor Education variant

<sub>tokens: 48579 in / 746 out</sub>