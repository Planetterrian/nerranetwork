Fetch-filter and chapter hygiene are holding (0 leakage, 10/10 clean chapters) and filler/coverage improved, but First-Principles/Top-12 section copying is still 8/10, digest-verbatim remains ~50%+ on most episodes, and 7/10 scripts sit under the 1400 floor despite digest-side levers and Sep-24 full-text fetch.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1170**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| excluded-class 13F/fund/aggregator items in last-10 tesla digests (incl. X-sourced) | hit | review_snapshot fetch-filter leakage: 0 hits across 12 exclude_title_patterns on last-10 digests |
| closings saying "closed at" on an episode generated inside the regular session | partial | No broken closer-class phrase in last-10 tic scan; per-episode ET session audit not in snapshot |
| closer grammar defects ("one dollars"/"one cents"/comma-joined amount+percent) in last-10 _tts.txt | hit | No closer-grammar tic above threshold in last-10 cross-episode phrase list |
| script_digest_overlap_pct, median of last 10 _tts.txt | miss | digest-verbatim mostly 41–68% (median ~55%); only Ep615/618/619 under 25% |
| script_filler_pct, last 10 | hit | All ten episodes at 0–5% filler in density table |
| copied sections (script_copied_sections) on Tesla First Principles, last 10 | miss | FP and/or Top-12/X Takeover copied-sections on 8/10 (Ep613,614,616,617,618,620,621,622) — expected ≤2/10 |
| script_entity_retention_pct, last 10 | partial | names-kept ≥75% on ~5–6/10 (81,91,93,86,79); Ep619 at 56%, several mid-60s |
| script_words, last 10 | hit | median ≈1291 words (≥1200); still 7/10 under the 1400 YAML floor |
| script_digest_coverage_pct, last 10 | hit | 9/10 episodes ≥70% coverage (Ep619 at 66% the only miss) |
| closing text identical across episodes | partial | No multi-episode closer string above phrase threshold; 10/10 identity not confirmed |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/tesla_podcast.txt`** (prompt) — Prompt still states 14–16 min AND 10–13 min / 1600–1900w while YAML floor is 1400 and RSS already promises ~10 min (Aug 15). Conflicting anchors let the model satisfy the smallest subset; 7/10 Ep613–622 still miss 1400. Single anchor matching accepted reality — A/B-listen required.
```diff
- You are writing a 14–16 minute solo podcast script for "Tesla Shorts Time" Episode {episode_num}.
- 
- HOST: Patrick in Vancouver — Canadian, scientist, newscaster. Think Rob Maurer on Tesla Daily: clear, measured, conversational. A knowledgeable friend explaining the day's Tesla news, not a hype man or morning radio DJ. Professional and measured: {tone_hint}.
- 
- STRUCTURAL REQUIREMENTS (these determine episode length — NON-NEGOTIABLE):
- - You are writing a 10–13 minute episode: 1,600–1,900 words. Target 80–110 "Patrick:" lines. This is the ONE length target for this script — there is no other.
+ You are writing a solo podcast script for "Tesla Shorts Time" Episode {episode_num}.
+ 
+ HOST: Patrick in Vancouver — Canadian, scientist, newscaster. Think Rob Maurer on Tesla Daily: clear, measured, conversational. A knowledgeable friend explaining the day's Tesla news, not a hype man or morning radio DJ. Professional and measured: {tone_hint}.
+ 
+ STRUCTURAL REQUIREMENTS (these determine episode length — NON-NEGOTIABLE):
+ - ONE length target only: about ten focused minutes, roughly 1,400–1,600 words, about 70–100 "Patrick:" lines. Do not aim for a longer show and do not pad to hit a word count. If the digest is thin, cover every real story at full factual depth and let the episode run shorter.
```

## Code/metadata-only proposals (no A/B needed)
- **`tests/test_tesla_quality_pass.py`** (code): Copied-sections still 8/10 after two delivery passes; a deterministic spoken-label guard is highest-yield/no-A/B and matches playbook 'lint is true of the text that ships'. Avoids banned script-density predictions.
- **`docs/reviews/tesla_review_<YYYY_MM_DD>.md`** (config): Playbook escalate-instead-of-re-filing: identical length and copied-section proposals have already missed; further filings pollute ledger rates.

## Deferred (carried forward)
- Digest-driven chapter titles + late chapter-anchoring walk-back in engine/chapters.py (network-scoped; chapters clean 10/10 this window but anchoring quality not re-measured)
- Narrative-tracker curated status lag — operator task via scripts/update_tesla_narrative.py (auto-freshness ≠ curated programs)
- Same-URL / cross-section double-tell: verify digest_cross_section_dupes_removed metrics next pass before more prompt pressure
- Pure valuation domain excludes (Trefis / Motley Fool / Intellectia / MarketBeat alerts) — operator call
- Weekend closer "Friday's close" qualifier in hooks/tesla.py _price_sentence — small A/B never merged
- Historical double-publish forensics (June-23 Ep519+520; Aug-28 Ep586+587) — operator
- Further RSS minute-count copy edits — only after explicit length accept/lower decision
- Hard data-side paraphrase/copied-section reject beyond current rewrite gate — only if operator picks escalation (a)
- source_integrity_claims median and post-full-text digest word floor — re-score when metrics_ep / digest lengths are in the next snapshot

## Drift-guard status
```
============================= test session starts ==============================
collected 60 items

tests/test_tesla_quality_pass.py ....................................... [ 65%]
.....................                                                    [100%]

============================== 60 passed in 1.43s ==============================
```

<sub>tokens: 42110 in / 5470 out</sub>