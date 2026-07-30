Chronic under-length (7/10 eps <900w), recurring 'nuance here worth understanding' deep-dive tic (8+/10 transcripts, prior prediction miss), and boilerplate network-promo tics in every episode.

_Generated on **grok-4.3** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.0492**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes whose LAST chapter is Closing, last 10 | hit | 9/10 episodes end with Closing per chapters_ep*.json after July-2 reorder |
| deep-dive opener 'There's a nuance here worth understanding' does not become 5+/10 template | miss | 8/10 transcripts (Ep052-Ep061) use it verbatim |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/env_intel_digest.txt`** (prompt) — De-seed by shape + verbatim ban + rotation memory per ledger rule; prevents third-generation tic
```diff
- There's a nuance here worth understanding when benzene detections appear inconsistent
+ [shape: open deep dive with a concrete regulatory or site-specific observation drawn from today's material; rotate among calendar deadline, cross-jurisdictional comparison, or field-indicator mismatch; never reuse the same lead-in phrase within 10 episodes]
```

**`shows/prompts/env_intel_podcast.txt`** (prompt) — Mirror digest de-seed; podcast faithfully echoes digest opener
```diff
- There's a nuance here worth understanding when permafrost conditions shift regional baselines
+ [shape: open deep dive with a concrete regulatory or site-specific observation drawn from today's material; rotate among calendar deadline, cross-jurisdictional comparison, or field-indicator mismatch; never reuse the same lead-in phrase within 10 episodes]
```

## Deferred (carried forward)
- Chronic under-length (digest ceiling only)
- Mid-section chapter markers rely on literal keywords
- Numbers/dates spell-out drift (landmine #17)

## Drift-guard status
```
============================= test session starts ==============================
collected 23 items

tests/test_env_intel_quality_pass.py .......................             [100%]

============================== 23 passed in 0.47s ==============================
```

<sub>tokens: 37092 in / 1151 out</sub>