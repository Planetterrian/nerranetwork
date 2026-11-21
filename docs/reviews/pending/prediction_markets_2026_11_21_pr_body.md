Posture, chapters, fetch filters and Board discipline are holding at ep51–60, but one under-floor script, repeated over-ceiling scripts, two low hook-coverage episodes, a freelanced mid-week wrap, and a near-dry curriculum runway are the next-tier issues; downloads remain tiny and falling.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1188**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes (first 7) with any recommendation, pick, tip, edge or 'mispriced' language (transcript read) | hit | Launch Ep1 note plus ep51–60 transcripts: journalism posture holds; no pick/tip/edge/mispriced language |
| The Board carries more than five markets, or a market / probability / volume not in the hook articles | hit | ep51–60 spoken Boards stay at or under five markets with venue-tied prices |
| share of script words spent on The Board | hit | Chapter timings keep Board near one minute inside 8–10 minute episodes (e.g. ep51 Board 275.3–361.3s) |
| How It Works figures or named studies stripped by the claims gate (source_integrity_stripped_sentences in that section) | partial | HIW still names papers/findings in ep51–60; no stripped-sentence metric series in this snapshot |
| legal claims without a named jurisdiction and a dated source | hit | Legal tops name body + jurisdiction + date (WA suit, LA orders, MD Fourth Circuit, NY TRO, CFTC stays) |
| first Friday's The Week's Board rows | hit | ep52 and ep59 both speak multi-row 'week's board' segments |
| Board lines missing one of the four fields | partial | Audio omits volume by design; digest four-field compliance not re-audited from raw digest files in this pass |
| episodes with a number spoken as 'the odds' or a forecast in the show's voice | hit | ep51–60 use priced/implied-probability wording; no show-voice 'will happen' forecasts found |
| curriculum unproduced on 2026-10-21 | partial | Restock machinery exists; live risk is ep60 runway (hook warns at <7) — curriculum file not in bundle |
| articles_preferred_in_prompt per episode | partial | preferred_domains still in shows/prediction_markets.yaml; metric not present in snapshot |
| Top Story sourced to a regulator, court or wire when the story is a rule or ruling | partial | Legal tops dominate but often via rg.org/The Block/DeFi Rate rather than cftc.gov/reuters/bloomberg |
| episodes recording llm_model_fallback | partial | stream + same-model retry shipped Sep 24; fallback counts not in this snapshot |
| commas per 100 words in the digest | hit | Recent episodes show ~5.3–7.6 commas/100 words, not Ep2 fallback-thin 1.3 |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/prediction_markets_podcast.txt`** (prompt) — ep54 transcript freelances a full past-seven-days recap before closing though weekly_summary_segment is Sunday-only; blocks weekday week-echo without touching length.
```diff
- [Tomorrow Teaser — one sentence, or none] Open with "Before we go", then name one specific developing story from today's briefing — a story the briefing above carries, never one from an earlier episode (the teaser had aired a week-old court filing that today's briefing never mentioned). Vary the rest daily. It names only a next step — what happens and when — that no earlier sentence of this episode spoke; when every next step has already been said, leave the teaser out entirely and go straight to the closing.
+ [Week wrap — Sundays only] Speak a past-week circle only when the briefing itself carries an explicit weekly-summary / week-in-review block. Never open a "past seven days", "this week kept", or multi-beat week recap from memory or narrative context on any other day — go to the teaser or the closing instead.
+ 
+ [Tomorrow Teaser — one sentence, or none] Open with "Before we go", then name one specific developing story from today's briefing — a story the briefing above carries, never one from an earlier episode (the teaser had aired a week-old court filing that today's briefing never mentioned). Vary the rest daily. It names only a next step — what happens and when — that no earlier sentence of this episode spoke; when every next step has already been said, leave the teaser out entirely and go straight to the closing.
```

**`shows/prompts/prediction_markets_podcast.txt`** (prompt) — Snapshot hook cov ep55 33% and ep59 29%: cold open sold a stake the early body did not land; data-side anchor requirement, not a coverage-% target.
```diff
- [Top Story] Continue with the facts the cold open did not use. No agenda or summary before it. When the briefing's item ends on a named critic's counter-argument, speak it with the name and the reason as the item's last beat.
+ [Top Story] Continue with the facts the cold open did not use. No agenda or summary before it. The first Host paragraph after the identity line must reuse at least one concrete anchor from the cold open (the named party, court, bill, dollar figure, or order the hook used) before any other story begins — shape only; never copy the hook wording. When the briefing's item ends on a named critic's counter-argument, speak it with the name and the reason as the item's last beat.
```

## Code/metadata-only proposals (no A/B needed)
- **`tests/test_prediction_markets_quality_pass.py`** (code): Pins posture + the ep54 week-wrap class with wiring-through-real-config; ages episodes one day so today's uncommitted run does not false-red.

## Deferred (carried forward)
- Restock shows/curricula/prediction_markets.yaml before unproduced runway <7 (carry/escalate; not a third prompt filing)
- Re-grade feeds from a runner and verify per-handle X yield
- Expose articles_preferred_in_prompt / board_venues in review snapshot for mechanical scoring
- Named-critic beat vs first-week downloads experiment
- YouTube enable decision for prediction_markets (currently false)
- Any podcast-side min-word floor, expand-retry, or ceiling-trim lever (network length do_not_retry class)
- Phonetic respellings for Kalshi/Polymarket/Nerra/Ossoff (landmine #17)
- Enforcing max_podcast_words with trim/retry (record-only today; audio-risk)

<sub>tokens: 47007 in / 4133 out</sub>