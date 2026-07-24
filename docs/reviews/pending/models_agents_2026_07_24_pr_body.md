Persistent under-length (9/10 episodes below 1500w) and boilerplate tics ("keep an eye on", "Okay let's pop the hood on", network outros) continue; prior length/garble predictions hit with no regressions; chapters remain clean.

_Generated on **grok-4.3** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.0575**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes below min_podcast_words (1500) in last 10 | miss | 9/10 still below (snapshot ep112-121) |
| "keep an eye on" occurrences as Tomorrow Teaser opener, last 10 | miss | 10/10 (transcripts ep112-121) |
| verbatim-doubled sentence pairs in shipped _tts.txt scripts | hit | ep115/116+ clean |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/models_agents_digest.txt`** (prompt) — Shape-based de-seed per meta-rule; avoids quotable example; adds successor-tic prediction to ledger
```diff
- Tomorrow keep an eye on expanded autonomous code repair agent evaluations.
+ Shape-based de-seed: ban verbatim rotation-pool openers for Tomorrow Teaser; require fresh per-episode phrasing drawn from current news only; maintain do-not-reuse list of prior 10 teaser openers in memory.
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/models_agents.yaml`** (config): Direct digest-substrate lever per length meta-rule; targets ceiling without podcast-side changes

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

<sub>tokens: 43917 in / 1059 out</sub>