Persistent under-length (9/10 episodes <1200 words), recurring boilerplate tics in 6-10/10 transcripts, and one chapter-shape failure (ep112 ends without Closing).

_Generated on **grok-4.3** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.0426**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| "not so scary, right?" occurrences in last-10 transcripts | hit | 0/10 post-merge per 2026-07-02 ledger |
| Big Story openers using "Something [adj] just happened", last 10 | hit | 0/10 post-merge per 2026-07-02 ledger |
| median _tts.txt words, last 10 eps | miss | still 9/10 below 1200 (snapshot) |
| episodes with a "The Big Story" chapter, last 10 | pending | still 0/10 (deferred) |
| episodes with a double-spoken closing (guard false-fire) | pending | no data in current window |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/mab_podcast.txt`** (prompt) — 10/10 transcripts repeat the exact outro tic; de-seed by shape + verbatim ban per July 2026 meta-review rule.
```diff
- End with the network outro and "This episode used AI voice synthesis..."
+ End with network outro only; ban verbatim "this episode used ai voice synthesis of my voice editorial selection and analysis are my own" and "see you tomorrow and if you'd rather watch" as exact strings; require fresh per-episode phrasing for sign-off.
```

**`shows/prompts/mab_podcast.txt`** (prompt) — 8/10 transcripts repeat the tic; de-seed by shape, never quotable example.
```diff
- "okay now for my favorite part of the show"
+ Ban exact phrase "okay now for my favorite part of the show"; use shape description only (transition to deep-dive segment) with rotation memory.
```

**`shows/prompts/mab_digest.txt`** (prompt) — 6/10 transcripts echo the prompt's own example.
```diff
- Include "let's break down today's coolest ai news so anyone can understand it"
+ Remove the exact sentence from rotation; ban as verbatim opener.
```

## Deferred (carried forward)
- chronic under-length (digest ceiling only)
- "The Big Story" chapter marker (dead; gated on digest-driven titles)
- MAB pronunciation hook respellings (0 impact; align with M&A)

<sub>tokens: 31537 in / 1256 out</sub>