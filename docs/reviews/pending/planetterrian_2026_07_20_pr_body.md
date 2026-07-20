Persistent under-length (9/10 episodes below 1600-word floor) and recurring boilerplate phrases (10/10 episodes) with fetch-filter leakage on astronomy terms; chapter shape remains clean after prior fixes.

_Generated on **grok-4.3** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.0564**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes with an Introduction chapter at word 0, last 10 | hit | chapters_ep117–126 all open with Introduction at t=20s |
| episodes shipping with no Closing chapter, last 10 | hit | all 10 chapters files end Closing after Tomorrow Teaser |
| episodes with a real Science Deep Dive chapter (when a deep dive aired) | hit | 10/10 transcripts contain the seeded opener and matching chapter |
| median _tts.txt words, last 10 eps | miss | 9/10 episodes 1258–1599 words (snapshot 2026-07-15) |
| pure-astronomy items per PT episode digest | partial | filter present in YAML but 6 leakage matches still occurred |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
None.

## Deferred (carried forward)
- chronic under-length (digest ceiling) — deferred behind four-show length A/B
- garbage mid-body auto-segment chapter titles — shared LLM-title class
- boilerplate reduction — prompt edit would require A/B-listen per landmine #17
- astronomy fetch-filter tuning — leakage still observed; verify volume impact first

## Drift-guard status
```
============================= test session starts ==============================
collected 12 items

tests/test_planetterrian_quality_pass.py ............                    [100%]

============================== 12 passed in 1.23s ==============================
```

<sub>tokens: 42790 in / 1167 out</sub>