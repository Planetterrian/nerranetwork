This pass finds persistent under-length (9/10 recent episodes below 1500w floor) and recurring boilerplate tics ("keep an eye on", "Okay let's pop the hood on", network outro blocks) across transcripts, with all prior length predictions scoring hit and chapter/garble fixes remaining stable.

_Generated on **grok-4.3** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.0591**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| "An-thropic" occurrences in last-10 _tts.txt (sum) | hit | 0 in ep107–ep116 transcripts |
| episodes with an "Under the Hood" chapter, last 5 | hit | 4/5 (ep108/110/112/114) |
| episodes whose chapters include a raw mid-sentence title (ends "…" or >40 chars), last 5 | hit | 0/5 in latest batch |
| median _tts.txt words, last 10 eps | hit | ~1300 steady; no regression |
| "koo-dah" occurrences in published blog transcripts of post-merge CUDA episodes | hit | 0 post-merge (ep107+) |
| custom voice still reads CUDA cleanly (Whisper of next post-merge CUDA episode) | hit | Whisper shows "CUDA" (no letter-split) |
| verbatim-doubled sentence pairs in shipped _tts.txt scripts | partial | ep115/116 clean; prior Ep087 fixed |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/models_agents_digest.txt`** (prompt) — Shape-based de-seed of 10/10 tic; avoids quotable example per meta-rule
```diff
- Tomorrow keep an eye on
+ Use rotated forward-looking phrasing (never the exact prior teaser opener) drawn from a per-episode do-not-reuse list
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/models_agents.yaml`** (config): Direct lever per length meta-rule; targets digest ceiling without podcast-side changes

## Deferred (carried forward)
- Digest-driven / position-aware mid-section chapter titles (carried)
- Expand Under the Hood section for length after four-show A/B settles (carried)
- Chronic under-length = digest ceiling (carried)

## Drift-guard status
```
============================= test session starts ==============================
collected 7 items

tests/test_models_agents_quality_pass.py .......                         [100%]

============================== 7 passed in 0.13s ===============================
```

<sub>tokens: 44698 in / 1304 out</sub>