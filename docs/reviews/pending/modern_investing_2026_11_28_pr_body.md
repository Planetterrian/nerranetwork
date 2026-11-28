Market Pulse chapters landed after the Nov 24 matcher ship, but every close still garbles Nerra→Narin, every Portfolio Performance still recites the full March-2026 lifetime totals beside era alpha (fourth miss class—escalate, do not re-strip), and EN scripts keep splitting Invalidation and mangling names while AI flags Repetitive on Ep241–243.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.2269**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes whose chapter JSON includes a Market Pulse (or index-tape) chapter title | hit | Ep241–244 chapters_ep241–244.json all title Market Pulse after Nov 24 #1734 matcher ship |
| Portfolio Performance airings that speak March-2026 lifetime trade count or cumulative P&L as scoreboard color | miss | Ep241–244 every PP still speaks 110–111 trades and cumulative −$802 to −$811 beside era alpha; strip was not shipped |
| EN _tts.txt incidents of Narin/Narrow/naren for Nerra, or wind rate for win rate | miss | Ep241–244 closes all say Narin Network / narennetwork.com (transcript quotes) |
| episodes whose Trade Review chapter starts before Strategy Spotlight | partial | Ep240 TR@34.4s before Strategy@102.7s; Ep241–244 Strategy/Pulse before Review |
| mit_non_medium_share_10ep on dashboard at next review | hit | Ep241 FNV High + Ep243 CLSK Low in last-4; non-Medium share well above 0.2 in hand window |

**Merge tier: B (listen)** — see docs/REVIEW_AGENT.md, "Merge tiers".

## Applied in this branch — listen before merging (landmine #17)
These changes are committed on this branch. A rehearsal of the episode was dispatched on this branch (Actions → "Run show", rehearse); listen to its artifact, then merge or close.

**`shows/prompts/modern_investing_podcast.txt`** (prompt) — P0: Ep241–244 EN closes still garble Nerra→Narin/naren every episode (Nov 7+17 miss). Ep241/242 split Invalidation→In validation. Recurring Unusual Wales / Tormelene / Andthropic / In Vidya. Verbatim locks + shape bans; no phonetic hacks (landmine #17). A/B-listen.

**`shows/prompts/modern_investing_digest.txt`** (prompt) — P1: fact-free script 37–62% with AI Repetitive on Ep241–243. Playbook: length/density via digest substrate only, never podcast expand. A/B-listen resulting episodes for padding vs real claims.

## ⚠️ A/B-listen required — NOT applied (landmine #17)
None.

## Deferred (carried forward)
- OPERATOR DECISION (escalate, fourth miss): daily Portfolio Performance lifetime March-2026 trade count / cumulative $ — (A) accept one labelled history sentence as house style and retire 0/10 predictions, (B) data-side gate to ≤1×/week or when era n changes, (C) strip from on-air prompt context (performance page only). Do not file a fifth identical prompt-only ban.
- Operator: run scripts/recompute_mit_benchmarks.py --apply after adjudicating 8 unreconciled pre-era trades (history cleanup; era on-air alpha already isolated)
- Operator: significance-qualifier accept-or-abandon (third miss; no fourth mechanism — do_not_retry)
- Operator: SnapTrade Phase-0 verification; keep LIVE_TRADING_ENABLED dormant until clean shadow+sim record
- Operator decision: volume>20-day multi-segment tic — data-side recent-episode MEMORY vs accept as house style (do not file a third prompt-only de-seed)
- Options cadence / live strike+expiry+mid on air — only if operator still wants post-Ep224; zero estimated premium unchanged
- Confidence mechanical grade only if forced High/Low variation carries no information after ~20 post-budget picks
- Listener feedback loop (inbox + triage) — product decision from Aug 20
- Feed measured shadow slippage into sim cost model once ~20 matched round trips
- HPS.A Ep150 flash open with no entry bar since 08-26 — needs void path
- Long-form YouTube retention ~8.2% and −42.9% WoW downloads — network video/discovery problem, not MIT-only prompt tweak
- Closing-price lesson family — already filtered as hygiene; leave retired
- Podcast-side length expand/retries — permanent do_not_retry network-wide
- Ep240-class Trade Review-before-Strategy — monitor one more window before further yaml pattern churn
- Elevated fact-free script share — continue digest-density only after this pass's digest note; no podcast word pressure

<sub>tokens: 98827 in / 4874 out</sub>