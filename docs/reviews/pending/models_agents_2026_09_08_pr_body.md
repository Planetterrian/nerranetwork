Sep 4–7 delivery fixes partially landed (UTH Everyone-talks cleared; advisory filler near-zero; Ep166–167 at 1–18% verbatim) but 8/10 scripts still under 1500w, chapters stay sparse/auto-titled, UTH number floor and headline-echo/attribution bans still miss, and length remains an escalated operator decision.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1507**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| "Everyone talks/treats/thinks about" or "Most people assume" as the Under the Hood opener, last 10 post-merge (digest AND spoken) | partial | 4/10 residual (ep159-162 still); 0/5 in ep163-167 after Sep-4 digest+podcast de-seed |
| episodes with an Under the Hood chapter when a deep-dive is present, last 10 | hit | 10/10 ep158-167 chapters_ep*.json include Under the Hood |
| chapters_ep*.json titles containing "](" or "http", or a "Practical & Community" chapter starting before 25% of the script | hit | 0 link titles and 0 early P&C mis-fires in ep158-167 |
| single closing variant share in last-10 transcripts | miss | 8/10 one pinned sign-off — but Sep-5 intentionally reversed the four-variant pool; treat as n/a-lever-reversed going forward |
| digests carrying a "DEPTH OVER BREADTH" heading | hit | Sep-4 bracketed-instruction rewrite; no DEPTH OVER BREADTH heading evidence in recent output |
| spoken continuity callbacks of the shape "we covered <tracker display name> yesterday" | hit | 0/10 of that quotable shape in ep158-167 transcripts |
| Under the Hood subject distinct from every news item (manual) | partial | ep163-167 mostly distinct; ep158-162 still re-used same-day news topics as the deep-dive |
| script_digest_overlap_pct, median of last 10 | partial | ep165-167 at 12/1/18%; full-window median still high from ep159-164 29-62% |
| 'advisory' filler shape per episode (script_audit) | hit | ep165-167 filler 0-1%; snapshot filler column at most 9% and falling |
| continuity callbacks that state a delta (manual) | partial | bare re-tells cleared; not every remaining callback names a delta |
| headline-echo pairs per episode (hand-count), 3 episodes | partial | Ep165=9; ep166/167 cleaner but not yet ≤1 across 3 straight |
| attribution-only sentences per episode (hand-count) | partial | Ep165 ~6 'Reports from… covered'; ep166/167 near-zero on that shape |
| Under the Hood numbers (hand-count), 3 episodes | partial | Ep165=2 vs ≥4 floor; ep166/167 richer — not 3 straight ≥4 |
| model-number or dataset-name mangles per episode (hand-count), 5 episodes | partial | Ep166=5 (Nutrition5k/RTX 5090 class); ep167=0 after Sep-7 fix — need 5 clean post-merge |
| script_entity_retention_pct, last 10 | miss | ep166=53% ep167=63% and half the window <75%; not ≥75% on 8/10 |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/models_agents_digest.txt`** (prompt) — Sep-6 UTH numbers miss (Ep165=2 vs ≥4) and Sep-5 distinct-subject partial. Digest-substrate lever only (playbook length meta-rule); also the sanctioned operator option B if length decision stays open. A/B-listen.
```diff
- On thin-news days, LENGTHEN the Under the Hood / deep-dive section first rather than padding news items with "this sits within the ongoing…" boilerplate.
+ On thin-news days, LENGTHEN the Under the Hood / deep-dive section first rather than padding news items with "this sits within the ongoing…" boilerplate.
+ 
+ UNDER THE HOOD FACT FLOOR: the deep-dive section is incomplete unless it carries at least four concrete numerals drawn from sources or licensed knowledge (benchmark points, milliseconds, percentages, token counts, parameter counts, dollar figures, speedup ratios). If fewer than four numerals are available, pick a different deep-dive topic — do not ship a mechanism-only essay. The Under the Hood subject must be a SECOND technical story, distinct from every news item above (never a restatement of Top Story / Model Updates / Agent item).
```

**`shows/prompts/models_agents_podcast.txt`** (prompt) — Sep-7 entity-retention miss (ep166=53%, half the window <75%) and Sep-6 UTH number miss. Shape + verbatim discipline, no quotable menu (meta-rule). A/B-listen.
```diff
- SHAPE OF IDEAL STORY COVERAGE (the ratio to hit on every item — described, never copied): what shipped, with the exact model or tool name and version and the lab named; a benchmark or capability number with its comparison point; the price or license; where and when it is available; one more concrete detail the source carries; then the next item's first fact. Zero commentary sentences. Write it fresh every time.
+ SHAPE OF IDEAL STORY COVERAGE (the ratio to hit on every item — described, never copied): what shipped, with the exact model or tool name and version and the lab named; a benchmark or capability number with its comparison point; the price or license; where and when it is available; one more concrete detail the source carries; then the next item's first fact. Zero commentary sentences. Write it fresh every time.
+ 
+ ENTITY KEEP: every named model, version, benchmark, lab, and tool in the digest item must appear in the spoken item. If you have to drop something under time pressure, drop the outlet name before the model name. Ban the shape that replaces a proper name with "a new paper", "a new tool", or "a recent release" when the digest named it. Do not add an example list — vary naturally.
+ 
+ UNDER THE HOOD NUMBERS: the deep dive must speak at least four concrete numerals (the digest floor flows through). A mechanism-only deep dive with fewer than four numbers is a failed section — add the missing measurements or cut.
```

**`shows/prompts/_shared/content_discipline.txt`** (prompt) — Sep-6 readout: Ep165 shipped 9 headline-echo pairs + ~6 attribution-only sentences after the first discipline pass. Tighten by shape + verbatim ban; record successor-tic watch in ledger. Shared file — A/B-listen on M&A (and any other consumer of the include).
```diff
- headline is a label not a line; source named inside a fact sentence, never a sentence of its own
+ headline is a label not a line — never speak the bold heading and then restate it as the next sentence (headline-echo pairs). Source is named inside a fact sentence, never a sentence of its own. Verbatim ban on standalone attribution throat-clears of the shape "Reports from <outlet> covered/reported…", "According to <outlet>…" as a full sentence with no other fact, or "<Outlet> wrote/notes that…" with the fact deferred to the next line. Lead with the fact; tuck the outlet mid-clause only when needed.
```

## Code/metadata-only proposals (no A/B needed)
- **`tests/test_models_agents_quality_pass.py`** (code): Every behavioral fix gets a drift-guard per playbook; pins Sep-4 chapter marker wins and the new discipline so a later edit cannot silently drop them.

## Deferred (carried forward)
- OPERATOR DECISION (length — escalated after July-19 + Aug-2 misses; do not re-file min_digest_words=1600 without an explicit choice): (A) raise min_digest_words to 1600, (B) Under-the-Hood licensed-knowledge sentence/fact floor in digest prompt, or (C) accept ~1200-1400w and lower min_podcast_words. Never re-enable podcast_expand_below_target. Today still 8/10 under 1500w.
- Digest-driven / position-aware mid-section chapter titles (network-wide; markers no longer the bottleneck — UTH 10/10 — but ep160/164/167 sparse and ep166 raw auto-titles remain)
- RSS title truncation ownership (hook spec under 120 vs 100-char title cap vs title-bundle optimized title)
- Same-day double publish Ep155+Ep156 prune (operator; renumbering unsafe)
- podcast:transcript from pre-pronunciation text or Whisper post-correct (network-wide LoRA/RAG/Quinn class)
- July-2 selection rebalance A/B (lab product/feature announcements outrank preprints; arXiv items <= 40%)
- Narrative tracker: advance last_mentioned only on headline mentions; seed-only last_major_update (data-side)
- MAB sibling: Big Story / Deep Dive / Cool Stuff / Quick Bits required-anchor treatment (host never says them → Welcome spans minutes)
- Recap must synthesize, not splice dailies' sentences (Sunday weekly_summary_segment)
- Signature opener 'okay let's pop the hood on' + pinned closing + 'Before we go' teaser — brand anchors; revisit only with explicit A/B evidence

## Drift-guard status
```
============================= test session starts ==============================
collected 14 items

tests/test_models_agents_quality_pass.py ..............                  [100%]

============================== 14 passed in 0.42s ==============================
```

<sub>tokens: 54915 in / 6804 out</sub>