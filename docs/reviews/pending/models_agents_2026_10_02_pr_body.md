UTH chapter coverage and entity-retention both regressed (ep185/189/190 missing Under the Hood; names-kept only ~3/10 ≥75%), 10/10 scripts remain under the 1500w floor so length stays an escalated operator A/B/C decision, and FR dubs intermittently speak the wrong episode number (ep186→196, ep191→181).

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1759**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| "Everyone talks/treats/thinks about" or "Most people assume" as UTH opener, last 10 | hit | 0/10 contrast-cliché UTH openers in ep186–191 EN; pop-the-hood/substance when UTH airs |
| episodes with Under the Hood chapter when deep-dive present, last 10 | miss | ep185, ep189, ep190 chapters_ep*.json lack Under the Hood (~7/10); ep190 also skips spoken pop-the-hood |
| script_entity_retention_pct (names kept), last 10 | miss | names-kept 53–82% with only 3/10 ≥75% (ep190=53%, ep191=54%) |
| headline-echo pairs + title-as-sentence + attribution-only sentences per episode, last 5 | partial | attribution-only rare; copied section headers + ep189 72% digest-verbatim keep paste live |
| Under the Hood concrete numerals (hand-count), last 5 | partial | ≥4 numerals when UTH airs (ep186/187/191); section absent on ep185/189/190 |
| Under the Hood re-tells a Model Updates / Agent news item, last 5 | partial | ep186/190 speculative-decoding deep-dives sit adjacent to same-family news items |
| model-number or dataset-name mangles per episode, last 5 | hit | 0 Ep166-class Nutrition5k/RTX-5090 mangles in ep187–191 EN transcripts |
| script_digest_overlap_pct median last 10 | miss | ep182–191 digest-verbatim median ~47% (spikes 65/60/72%); not ≤25% |
| successor item-opener tic: any single new throat-clear before first fact in ≥6/10 news items | hit | no new non-brand opener ≥6/10; Before we go remains brand anchor |
| chapters with raw mid-sentence auto-titles or missing Teaser when Before-we-go present, last 10 | miss | raw autos ep182/183/189; UTH missing ep185/189/190; Teaser usually present |
| 'advisory' filler shape per episode (script_audit) | hit | filler 0–3% on 9/10 last eps; ep191 8% only outlier |
| "keep an eye on" as teaser opener (regression watch) | hit | 0 keep-an-eye teaser openers in sampled ep186–191 teasers |
| chapters_ep*.json titles containing "](" or "http", or early Practical & Community | hit | 0 link titles and 0 early P&C mis-fires in ep182–191 |
| spoken continuity callbacks of the shape "we covered <tracker display name> yesterday" | hit | 0 of that quotable shape in sampled EN transcripts |
| source_integrity_claims median (Sep-24 sourcing) | partial | no source_integrity field in snapshot; preferred_domains/fetch_full_text live but unscored |
| sources on x.com per episode (Sep-24 sourcing) | partial | x_posts_as_sources: secondary + x_only_lead lint live; per-ep x.com counts not in snapshot |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/models_agents_podcast.txt`** (prompt) — ep190 skipped pop-the-hood and lost the UTH chapter; ep185/189 also lack UTH rows. names-kept miss is live at 3/10 ≥75%. Shape + verbatim bans, no replacement menu (meta-rule). A/B-listen.
```diff
- [Under the Hood / deep dive uses required pop-the-hood opener as one of the structural rules — model still sometimes substance-first]
+ UNDER THE HOOD — HARD ANCHOR: the deep-dive’s FIRST spoken sentence MUST begin with the words “Pop the hood on” (then the subject). No substance-first substitute, no “let’s look at”, no diving straight into the mechanism. If the briefing’s deep-dive is thin, still open with the anchor then give every concrete numeral the briefing carries. ENTITY KEEP: speak the digest’s exact model, tool, lab, benchmark, and product tokens (Qwen, Claude, Splash/Splish, GraphRAG, MCP, SWE-bench, etc.); do not replace a name with “the open model”, “the paper”, “the router”, or “the fork”. Section titles (Model Updates, Agent & Tool Developments, Practical & Community, Under the Hood, Things to Try) are NEVER spoken — they are navigation only.
```

**`shows/prompts/models_agents_digest.txt`** (prompt) — Sanctioned digest-substrate lever and operator option B while length A/B/C stays open. Addresses UTH retell partials and locks numeral floor when section airs. A/B-listen.
```diff
- [Under the Hood section guidance without a hard ≥4-numeral / distinct-subject floor locked in shipped output]
+ ### Under the Hood (licensed-knowledge deep dive)
+ MUST be a second technical subject distinct from EVERY Top Story / Model Updates / Agent / Practical item URL and mechanism already used above (ONE STORY = ONE SECTION still applies). Write 8–14 sentences with ≥4 concrete numerals the sources or established systems knowledge support (latencies, accept rates, parameter cuts, token ratios, FLOPs factors, dollar figures only if sourced). If you cannot name four honest numbers, pick a different deep-dive topic. Never restate a news item’s benchmark block as the deep-dive.
```

**`shows/prompts/_shared/content_discipline.txt`** (prompt) — Density audit still lists copied sections on most of ep182–191; ep189 hit 72% digest-verbatim. De-seed by shape + verbatim ban; successor-tic prediction recorded. Shared include — A/B-listen on M&A and other consumers.
```diff
- headline is a label not a line; source named inside a fact sentence, never a sentence of its own
+ headline is a label not a line; source named inside a fact sentence, never a sentence of its own. NEVER speak or paste digest section headers (Top Story, Model Updates, Agent & Tool Developments, Practical & Community, Under the Hood, Things to Try, On the Horizon) as their own sentence or as a throat-clear before the first fact. First words of each item = first fact (name, number, or capability) — not the section label and not a restated title.
```

**`engine/ (multilingual identity line / FR podcast script path)`** (code) — P0 listener-facing on FR feed: verified Ep186 FR=196 and Ep191 FR=181. Deterministic pin beats prompt hope. A/B-listen FR audio only.
```diff
- FR dub identity currently free-form from translation — can emit wrong episode numerals (196 vs 186, 181 vs 191)
+ Pin the spoken identity numeral from the canonical episode_num (same integer as EN intro_line) after translation / before FR TTS; reject or rewrite if the FR identity line’s parsed number ≠ episode_num. Do not phonetic-respell; do not touch voice IDs.
```

## Code/metadata-only proposals (no A/B needed)
- **`tests/test_models_agents_quality_pass.py`** (code): Every behavioral fix gets a drift-guard; FR ep-number mismatches and UTH chapter drops are mechanical. Judge day-old episodes so today’s in-flight run cannot false-red the suite.

## Deferred (carried forward)
- OPERATOR DECISION (length — escalated after July-19 + Aug-2 misses; today 10/10 under 1500w): (A) min_digest_words=1600, (B) UTH digest fact floor (proposed this pass), or (C) lower min_podcast_words to match ~1100–1400w natural length. Never re-enable podcast_expand_below_target; never silent-third-file 1600.
- Digest-driven / position-aware mid-section chapter titles (network-wide; markers no longer enough — raw autos ep182/183/189, mega Model Updates chapter ep190)
- RSS title truncation ownership (hook under 120 vs 100-char title cap vs title-bundle optimized title)
- Same-day double publish Ep155+Ep156 prune (operator; renumbering unsafe)
- podcast:transcript from pre-pronunciation text or Whisper post-correct (network-wide LoRA/RAG/Quinn class)
- July-2 selection rebalance A/B (lab product/feature announcements outrank preprints; arXiv items ≤40%)
- Narrative tracker: advance last_mentioned only on headline mentions; seed-only last_major_update nulls (data-side)
- MAB sibling: Big Story / Deep Dive / Cool Stuff / Quick Bits required-anchor treatment
- Sunday weekly_summary_segment must synthesize, not splice dailies’ sentences
- Brand anchors pop the hood / Before we go / pinned closing — do_not_retry de-seed or multi-variant closing re-expand
- OP3 first-week ~19 dl/ep, −28.7% WoW, YT long retention 12.9% — watch one more cycle before product changes

## Drift-guard status
```
============================= test session starts ==============================
collected 14 items

tests/test_models_agents_quality_pass.py ..............                  [100%]

============================== 14 passed in 0.27s ==============================
```

<sub>tokens: 66560 in / 7135 out</sub>