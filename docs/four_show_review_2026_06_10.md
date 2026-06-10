# Four-Show Quality Review — Modern Investing, Models & Agents, MAB, Fascinating Frontiers (June 10, 2026)

The same review-then-fix process as the Tesla flagship pass
([`docs/tesla_review_2026_06_10.md`](tesla_review_2026_06_10.md)), applied to
Modern Investing Techniques (MIT), Models & Agents (M&A), Models & Agents for
Beginners (MAB), and Fascinating Frontiers (FF). All fixes implemented in the
same PR. Drift guards: `tests/test_four_show_quality_pass.py`.

**Critical context that reframed the audits:** the MIT pass (#574, merged
June 9 20:09 PT) and the network pass (#575, merged June 9 20:37 PT) landed
*after* every episode the audits examined (latest: June 9 morning). Most
"critical" findings — MIT's "$+nan on air" and "portfolio unavailable"
(Ep071), M&A/FF/MAB's "expand-retry never fires" and "banned phrases still
appearing" — are **pre-fix episodes**, not live bugs. The genuinely live
issues, all fixed here:

## 1. Closing chapters were broken on all four shows (Tesla bug class)

Every show's `engine/intros.py` closing pool had variants that **no Closing
chapter pattern matched**, so episodes using them shipped without a Closing
chapter (verified: 50% of recent MAB episodes had none at all):

| Show | Orphaned closing variants | Other marker bugs |
|---|---|---|
| MIT | "That's it for today's…", "That's your…" (2 of 4) | bare `wraps up` matched mid-script sentences |
| M&A | "That wraps up today's AI briefing" (1 of 2) | bare `agent` opened a spurious "Agent & Tool Developments" chapter ~30 s into every episode (verified in Ep71/72/74 chapters) |
| MAB | "And that's a wrap!" (1 of 2) | — |
| FF | "That covers today's space and science news" (1 of 2) | `that.?s.*for today` was mid-script-matchable |

**Fixed:** all four YAMLs now use the `where: start|end` positional anchors
shipped in the Tesla pass (Introduction/Welcome → `start`, Teaser/Closing →
`end`), Closing patterns cover every pool variant, M&A's agent pattern is
`agent and tool developments|tool developments|agentic systems|agent news`,
and MIT's closing requires `that wraps up`. Guard:
`TestClosingPoolMatchesChapterPattern` (every pool variant must match its
show's Closing pattern — a new variant that matches nothing fails CI).

## 2. Contradictory length targets (same as Tesla finding 6)

| Show | Prompt said (simultaneously) | YAML floor | Recent actual | Now |
|---|---|---|---|---|
| MIT | "10–14 min (2500–3500 words)" / "55-75+ sentences, 10-14 min" / "fits in 12 minutes" | 1300 | ~1360 avg | **one target: 2,000–2,200 words ≈ 12–14 min; floor 1800** |
| M&A | "6–9 minute (1500–2200 words)" / "65-85+ sentences, 8-11 min" / "at least 1500" | 1500 | 1041–1433 | **one target: 1,600–2,200 words ≈ 10–12 min; floor 1500 (kept)** |
| FF | "10–13 minute" / "75-110+ sentences, 12-15 min" / "at least 2400 words" | 1350 | ~1100 avg | **one target: 1,900–2,200 words ≈ 12–14 min; floor 1700** |
| MAB | "8–10 min (1300–1700 words)" (internally consistent) | **900** | 808–1138 | **floor raised to 1200** (it sat so far under the prompt's own low end that 5 of 8 short episodes never tripped the retry) |

Conflicting anchors let the model satisfy the smallest number — the same
mechanism that kept Tesla 18–36% under target. With the expansion retry now
carrying the digest (Tesla pass, `engine/generator.py`), these floors are
actually reachable by covering more stories. Guard:
`TestUnifiedLengthTargets`. **Prompt edits change output — A/B-listen the
next episodes per landmine #17.**

## 3. `engine/show_memory.py` lacked all four Tesla memory fixes

The generalized memory engine (M&A, FF, Planetterrian) was generalized from
`tesla_memory` *before* the June 10 fixes:

- **Narrative-prose echo:** tracker status text echoed into digests was
  re-mined daily — verified in all three theme histories (e.g. M&A carried
  "frontier models" / "agents tool" / "models agents" echo chains; FF
  Ep85–96 had identical frozen theme blocks). Now filtered via
  `_narrative_prose_bigrams`.
- **No idempotency:** FF's Ep96 was mined multiple times (duplicate
  evolution entries in all three shows' histories). Now once per episode.
- **URL mining:** "reddit https" / "nasa https" / "science nasa" junk
  bigrams. URLs now stripped before mining.
- **Substring program detection:** "mars" in "marsupial" or "agent" in
  "reagent" advanced on-air "last covered" freshness. Now word-boundary
  regexes (`_program_mentioned`).
- **Dead performance loop:** same as Tesla — no production writer. New
  `show_memory.update_performance_from_op3` + the generalized nightly
  script `scripts/update_performance_trackers.py` (replaces the
  Tesla-only script; covers Tesla + M&A + FF + Planetterrian; trackers
  committed by the nightly push).

All three committed theme histories were re-scrubbed (M&A: 7 noise keys
removed, top themes now "open weight", "llama", "qwen"; FF: 7 removed, top
"dark matter"; PT: 11 removed, top "gene editing"). Guards:
`TestShowMemoryHardening`.

## 4. MAB "So imagine" opener tic — caused by the prompt's own example

"So imagine…" opened **49 of 60** MAB episodes. Root cause: the prompt's Big
Story guidance offered exactly one example hook shape ("So imagine you
could..."), and the model converged on it. The guidance now requires rotating
opener shapes and bans repeating the same shape two episodes in a row.
(Per-episode analogies were verified unique — the tic is structural, not
content.) A/B-listen per landmine #17.

## Findings checked and rejected (for the record)

- **MIT "$+nan" / "portfolio data unavailable on air" (Ep071)** — real on
  June 9, but pre-#574; the tracker is now clean (P&L $395.00, alpha +20.6%
  across 26 benchmarked trades) and `_build_portfolio_summary` is wired.
  Verify the next episode states the alpha; no code change needed.
- **"Expand-below-target completely inert" (M&A/FF/MAB)** — all audited
  episodes predate #575, which added the flag. The real retry weakness (the
  model never saw the digest) was fixed in the Tesla pass and benefits all
  shows.
- **Banned phrases still in scripts** (M&A "sits within the ongoing", FF
  "you know what's fascinating") — all occurrences predate the #575 bans.
  Evaluate after a few post-pass episodes before adding harder constraints.
- **Agent-proposed generator "fix"** (`keep retry only if ≥ threshold`) —
  rejected: it would *discard* an 821→1,400-word improvement that's still
  under target. Keeping the longer script is correct.
- **"Models and Agents" spoken vs "Models & Agents" written** — rejected:
  the intros pool feeds TTS, where the verbalized "and" is exactly right.
- **RSS AI-disclosure says "ElevenLabs"** — only in frozen historical feed
  items; the current `_AI_DISCLOSURE_RSS` in `run_show.py` is
  provider-neutral. Don't churn history.
- **Generic RSS item titles** — old back-catalog items only; recent items
  are hook-first on all four feeds. Same "don't bulk-retitle" call as Tesla.
- **M&A stale RSS channel description** — the feed channel is rebuilt from
  YAML on every episode publish; the June 9 episode simply ran before #575
  merged. Self-heals on the next run.

## Operator items (not code)

- A/B-listen the next 2–3 episodes of each show (length targets + MAB
  opener variation changed; landmine #17).
- M&A narrative tracker has no curated status updates since seeding (all
  `last_major_update_episode: null`); auto-freshness now runs, but one
  curated status pass via `scripts/update_tesla_narrative.py --slug
  models_agents` would make the continuity block much richer. Same for FF.
- MIT Ep071 aired "unavailable" portfolio lines and Ep067/071 shipped thin —
  consider whether any pre-fix June episodes are worth regenerating
  (probably not; the catalog moves daily).
