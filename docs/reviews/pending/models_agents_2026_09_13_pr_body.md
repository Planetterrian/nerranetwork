Sep-4–9 delivery wins largely held (Everyone-talks cleared, UTH chapters 10/10, advisory near-zero, no link titles) but 8/10 scripts still under 1500w, entity retention stays ~half the window below 75%, residual headline-echo/attribution and UTH-number misses continue, and length remains an escalated operator A/B/C decision — no silent 1600 re-file.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1677**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| "Everyone talks/treats/thinks about" or "Most people assume" as UTH opener, last 10 | hit | 0/10 in ep163–172 spoken UTH openers (pop-the-hood / substance-first); clears Sep-8’s 4/10 residual |
| episodes with Under the Hood chapter when deep-dive present, last 10 | hit | 10/10 ep163–172 chapters_ep*.json include an Under the Hood chapter |
| Under the Hood concrete numerals (hand-count), last 5 | partial | ep167–172 deep-dives carry ≥4 numerals; ep165=2 was the miss — not locked by a digest fact floor |
| script_entity_retention_pct (names kept), last 10 | miss | names-kept 53–84%; only ~4–5/10 ≥75% (ep166=53%, ep170=57%, ep167/169=63%, ep171=67%) |
| headline-echo pairs + attribution-only sentences per episode (hand-count), last 5 | partial | ep168 still pastes title-as-sentence; ep165 worst-in-window; not ≤1 echo + 0 attribution on 4/5 |
| model-number or dataset-name mangles per episode, last 5 | partial | Ep166=5 baseline; ep167–172 = 0 of Nutrition5k/RTX-5090 class after Sep-7 fix — need full 5-clean cohort |
| script_digest_overlap_pct median last 10 | partial | ep166=1%, ep170=5% clean; ep164=58%, ep171=55%, ep169=40% keep full-window median >25% |
| chapters with raw mid-sentence auto-titles (ellipsis or >40 chars lowercase start), last 10 | partial | ep166 three raw auto-titles; ep164/167 sparse; ep172 missing Teaser chapter — durable drop still waits on digest-driven titles |
| Under the Hood subject distinct from every news item (manual) | partial | newest window mostly second technical stories; ep167 UTH re-told Model Updates sparse-attention item |
| 'advisory' filler shape per episode (script_audit) | hit | snapshot filler 0–8%; ep165–172 mostly 0–4% |
| spoken continuity callbacks of the shape "we covered <tracker display name> yesterday" | hit | 0/10 of that quotable shape in ep163–172 |
| "keep an eye on" as teaser opener (regression watch) | hit | 0/10 in ep163–172 teasers |
| chapters_ep*.json titles containing "](" or "http", or early Practical & Community | hit | 0 link titles and 0 early P&C mis-fires in ep163–172 |
| digests carrying a "DEPTH OVER BREADTH" heading | hit | no counter-evidence post Sep-4 bracketed-instruction rewrite |
| digest_placeholder_tokens, next 15 episodes | partial | ep168–172 transcripts show no fresh placeholder tokens; 15-ep window not yet full |
| script_rewrite_gate_reject_reason=section_still_copied when the rewrite copied less overall | partial | gate change shipped Sep-9; no fresh reject-of-cleaner-rewrite observed in this window |
| Under the Hood re-tells a Model Updates item (hand-count), 5 episodes | partial | ep167 = 1 re-tell; not yet ≤1/5 locked across a full 5-ep window |
| single closing variant share in last-10 transcripts | hit | n/a-lever-reversed: Sep-5 re-pinned one sign-off; 8/10 one variant is intended brand behavior |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/models_agents_digest.txt`** (prompt) — Sep-6 UTH numerals miss (Ep165=2 vs ≥4) and Sep-9 UTH-retell-of-Model-Updates (ep167) are still partial. Digest-substrate lever only (playbook length meta-rule); also sanctioned operator option B while the length A/B/C decision stays open. A/B-listen.
```diff
- On thin-news days, LENGTHEN the Under the Hood / deep-dive section first rather than padding news items with "this sits within the ongoing…" boilerplate.
+ On thin-news days, LENGTHEN the Under the Hood / deep-dive section first rather than padding news items with "this sits within the ongoing…" boilerplate.
+ 
+ UNDER THE HOOD — DISTINCT SECOND STORY + FACT FLOOR (do not copy this heading): Under the Hood MUST be a technical mechanism the news items did not already cover. Ban restating any Top Story / Model Updates / Agent & Tool / Practical item under a deeper frame. Required ingredients every episode: (1) named mechanism or paper, (2) ≥4 concrete numerals the source or licensed knowledge actually carries (benchmark points, milliseconds, percents, token counts, dollar figures, parameter counts — never invented), (3) one engineering trade-off or failure mode, (4) one builder-facing implication. If fewer than four real numerals exist for the candidate story, pick a different deep-dive. Sentence count follows fact count.
```

**`shows/prompts/models_agents_podcast.txt`** (prompt) — Sep-7/Sep-8 entity-retention miss still live (only ~4–5/10 ≥75%). Shape + verbatim discipline, no quotable menu (meta-rule). Reinforces UTH distinct-subject on the podcast side so ep167-class retells cannot return. A/B-listen.
```diff
- SHAPE OF IDEAL STORY COVERAGE (the ratio to hit on every item — described, never copied): what shipped, with the exact model or tool name and version and the lab named; a benchmark or capability number with its comparison point; the price or license; where and when it is available; one more concrete detail the source carries; then the next item's first fact. Zero commentary sentences. Write it fresh every time.
+ SHAPE OF IDEAL STORY COVERAGE (the ratio to hit on every item — described, never copied): what shipped, with the exact model or tool name and version and the lab named; a benchmark or capability number with its comparison point; the price or license; where and when it is available; one more concrete detail the source carries; then the next item's first fact. Zero commentary sentences. Write it fresh every time.
+ 
+ ENTITY-KEEP DISCIPLINE (shape, not examples): every named model, version, lab, benchmark, tool, dataset, and hardware identifier the briefing carries must be spoken as that name — never replaced with "the model", "the paper", "the team", "the new system", or a pronoun on first reference. Dropping a name for a description is a failure mode (Ep166 names-kept 53%, Ep170 57%). Secondary identifiers (outlet names inside a fact sentence, parameter counts, context lengths) stay when the briefing has them. Under the Hood may not restate any news-section item; if the briefing's deep-dive collides with a news item, skip the collision and cover the deep-dive's mechanism only.
```

**`shows/prompts/_shared/content_discipline.txt`** (prompt) — Sep-6 readout partially cleared; ep168 title-as-sentence residual shows the first discipline pass was not tight enough. De-seed by shape + verbatim ban, no replacement menu; successor-tic prediction recorded. Shared include — A/B-listen on M&A and any other consumer.
```diff
- headline is a label not a line; source named inside a fact sentence, never a sentence of its own
+ HEADLINE / ATTRIBUTION SHAPE (tighten — Ep165 shipped 9 headline-echo pairs + ~6 attribution-only sentences; Ep168 still spoke "…is the title of the [outlet] piece"):
+ - The headline is a label for YOU, never a spoken line. Do not read the bold heading aloud, do not paraphrase it as the first sentence, and do not follow a spoken headline with a body that restates it.
+ - Never speak a freestanding attribution sentence: ban shapes including "Reports from [outlet] covered…", "[Outlet] reported that…", "…is the title of the [outlet] piece/post", "According to [outlet]" as its own sentence. Name the outlet only inside a sentence that also carries a concrete fact.
+ - First sentence of every item = first concrete fact (what shipped / what number / what changed). No throat-clear, no headline echo, no attribution wind-up.
+ - Successor-tic watch: if any new pre-fact throat-clear converges in ≥6/10 items, the next review bans it by shape.
```

## Code/metadata-only proposals (no A/B needed)
- **`tests/test_models_agents_quality_pass.py`** (code): Every behavioral fix gets a drift-guard per playbook so a later edit cannot silently drop Sep-4 chapter wins or the new discipline.

## Deferred (carried forward)
- OPERATOR DECISION (length — escalated after July-19 + Aug-2 misses; do not re-file min_digest_words=1600 without an explicit choice): (A) raise min_digest_words to 1600, (B) Under-the-Hood licensed-knowledge sentence/fact floor in digest prompt, or (C) accept ~1200–1400w and lower min_podcast_words. Never re-enable podcast_expand_below_target. Today still 8/10 under 1500w.
- Digest-driven / position-aware mid-section chapter titles (network-wide; UTH 10/10 but ep164/167 sparse, ep166 raw auto-titles, ep172 missing Teaser remain)
- RSS title truncation ownership (hook spec under 120 vs 100-char title cap vs title-bundle optimized title)
- Same-day double publish Ep155+Ep156 prune (operator; renumbering unsafe)
- podcast:transcript from pre-pronunciation text or Whisper post-correct (network-wide LoRA/RAG/Quinn class)
- July-2 selection rebalance A/B (lab product/feature announcements outrank preprints; arXiv items <= 40%)
- Narrative tracker: advance last_mentioned only on headline mentions; seed-only last_major_update (data-side)
- MAB sibling: Big Story / Deep Dive / Cool Stuff / Quick Bits required-anchor treatment (host never says them → Welcome spans minutes)
- Recap must synthesize, not splice dailies' sentences (Sunday weekly_summary_segment)
- Signature opener 'pop the hood' + pinned closing + 'Before we go' teaser — brand anchors; revisit only with explicit A/B evidence
- ep172 Tomorrow Teaser chapter miss — re-diagnose with engine chapter trace next pass if missing-Teaser recurs ≥3/10
- OP3 first-week median ~19 downloads/episode + YT long-form retention 11.2% — watch one more cycle before product changes; no metadata root cause this pass

## Drift-guard status
```
============================= test session starts ==============================
collected 14 items

tests/test_models_agents_quality_pass.py ..............                  [100%]

============================== 14 passed in 0.23s ==============================
```

<sub>tokens: 57444 in / 8796 out</sub>