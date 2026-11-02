Post–grok-4.6 window is much healthier (verbatim 3–28%, copied-sections 2/10, facts×2 ≤2, zero fetch leakage, strong OP3), but 6/10 scripts still miss the 1400 floor and tesla_podcast.txt still fights YAML/RSS with a 1600–1900 word band plus contradictory First Principles duration lines.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1262**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| spoken digest section labels / copied-sections rate on FP\|Top-12\|X Takeover (2026-10-01) | partial | Copied-sections 2/10 (Ep646 Short Spot, Ep647 FP) vs 8/10 baseline; no multi-ep literal section-label tic in phrase detector |
| podcast prompt length anchors aligned to ~10 min and min_podcast_words 1400 (2026-10-01) | partial | Single STRUCTURAL band remains but still '1,600–1,900 words' / 10–13 min — not aligned to YAML 1400 or RSS about-ten |
| facts×2 median ≤2 on last 10 after story_clusters (2026-10-01) | hit | Ep644–653 facts×2 all 1 or 2; no ≥5 multi-outlet retell |
| excluded-class 13F/fund/aggregator items in last-10 digests (Sep-4 hold) | hit | review_snapshot fetch-filter leakage: 0 hits on 12 exclude_title_patterns |
| script_digest_overlap_pct median ≤25% every episode (Sep-5) | miss | Verbatim 3–28% (improved vs ~55%) but density-% targets are do_not_retry; do not re-predict |
| copied sections on Tesla First Principles ≤2/10 (Sep-6) | hit | 2/10 copied-section flags this window (Ep646/647); FP alone 1/10 |
| script_filler_pct ≤5% on 9/10 (Sep-5) | hit | All ten episodes 0–1% filler |
| script_words median ≥1200 (Sep-7/9) | hit | Median ≈1315w; still 6/10 under the 1400 publish floor |
| script_digest_coverage_pct ≥70% on 7/10 (Sep-9) | partial | 8/10 ≥69% coverage; Ep644 and Ep645 at 64% |
| script_entity_retention_pct ≥75% on 8/10 (Sep-7) | partial | names-kept ≥75% on ~6/10; Ep645 61%, Ep649 68% |
| source_integrity_claims median ≥4 (Sep-24 sourcing) | miss | Claims counts absent from snapshot — prediction still open/unverified |
| digest words vs min_digest_words floor stability (Sep-24) | miss | Digest word totals absent from snapshot; 6/10 podcast under-1400 implies substrate still binding |
| spoken_text_gate 0 audio≠script publishes network 30d (Sep-14) | partial | No Tesla Ep605-class leak in Ep644–653; network-wide 30d tally not in snapshot |
| script_rewrite_gate_accepted when fired (Sep-6/9) | miss | Gate removed network-wide 2026-09-12; do_not_retry — obsolete lever |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/tesla_podcast.txt`** (prompt) — Oct-1 partial fix left a single but still-misaligned 1600–1900 band against YAML min_podcast_words 1400 and RSS 'about ten'. Anchor hygiene only — not a podcast expand-retry (do_not_retry).
```diff
- - You are writing a 10–13 minute episode: 1,600–1,900 words. Target 80–110 "Patrick:" lines. This is the ONE length target for this script — there is no other.
+ - You are writing an about-ten-minute episode. Cover every Top-12 story at full factual depth; the publish floor is 1,400 words — going under it means stories were dropped or gutted, not that a higher word band was missed. Target roughly 70–100 "Patrick:" lines. This is the ONE length target for this script — there is no other minute or word band.
```

**`shows/prompts/tesla_podcast.txt`** (prompt) — Same prompt currently states both '~2.5 minutes' (structural / Oct-14 whole-essay fix) and '60–90 seconds' (segment block). Dual duration anchors are the length-anchor bug class; unify to the Oct-14 intent. Not a third FP restatement de-seed.
```diff
- [First Principles — brief analytical segment]
- If the digest includes a First Principles section, cover it in about 60–90 seconds.
+ [First Principles — analytical segment]
+ If the digest includes a First Principles section, tell the briefing's whole essay in your own words with every figure — about two and a half minutes. Do not re-impose a six-sentence or 60–90s cap.
```

## Code/metadata-only proposals (no A/B needed)
- **`tests/test_tesla_quality_pass.py`** (code): Locks the two prompt-hygiene fixes without touching audio; matches existing tesla_quality_pass drift-guard pattern. No A/B.

## Deferred (carried forward)
- OPERATOR LENGTH DECISION (escalated again): raise digest substrate (full-text/FP floor) vs accept ~10 min and 1400 as real ceiling vs hard FP digest word floor — never podcast_expand_below_target
- Expose digest word totals + source_integrity_claims + digest_cross_section_dupes_removed in review_snapshot before re-predicting substrate health
- Digest-driven chapter titles + late chapter-anchoring walk-back in engine/chapters.py (network-scoped; shape clean 10/10 this window)
- Narrative-tracker curated status lag — operator via scripts/update_tesla_narrative.py
- Pure valuation domain excludes (Trefis / Motley Fool / Intellectia / MarketBeat alerts) — operator call
- Weekend closer "Friday's close" qualifier in shows/hooks/tesla.py — small A/B never merged
- Historical double-publish forensics (June-23 Ep519+520; Aug-28 Ep586+587)
- Further RSS minute-count copy edits — only after explicit length decision (already about ten)
- Hard data-side script paraphrase/copied-section retry gate — FORBIDDEN (removed 2026-09-12; do_not_retry)
- Third prompt-only First Principles 'do not restate the body' de-seed — FORBIDDEN; residual Ep647 1/10 observe-only
- Weak hook-coverage minority days — watch; escalate data-side only if <50% hook cov stays ≥3/10

## Drift-guard status
```
============================= test session starts ==============================
collected 60 items

tests/test_tesla_quality_pass.py ....................................... [ 65%]
.....................                                                    [100%]

============================== 60 passed in 0.81s ==============================
```

<sub>tokens: 45740 in / 5793 out</sub>