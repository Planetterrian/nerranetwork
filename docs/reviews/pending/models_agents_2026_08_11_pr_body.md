Aug-4 teaser/UTH de-seeds and UTH marker still never shipped: “keep an eye on” cleared but “Before we go” is now 10/10 and “Everyone talks/treats about…” opens 10/10 deep-dives, while 8/10 scripts stay under 1500w and length remains an operator decision after two missed levers.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1325**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| "keep an eye on" as Tomorrow Teaser / before-we-go opener, last 10 post-merge | hit | ~0/10 in ep129–138 teasers; phrase cleared even though shape-ban never merged |
| "Everyone talks about" as Under-the-Hood / deep-dive opener, last 10 post-merge | miss | 7/10 exact + 3/10 "Everyone treats" = 10/10 contrast-cliché openers; Aug-4 de-seed never applied |
| successor UTH-opener tic: any single new contrast-cliché opener in >=6/10 deep-dives (convergence watch) | hit | "Everyone treats" alone is 3/10; no independent new phrase ≥6/10 while original formula still dominates |
| successor teaser-opener tic: "Before we go" (with or without keep-an-eye) in >=6/10 teasers | miss | 10/10 ep129–138 teasers open with "Before we go" |
| episodes with an Under the Hood chapter when a deep-dive is present, last 10 | miss | 8/10 (ep132/133 missing UTH when host led with Everyone-talks and skipped pop-the-hood); marker alternate never shipped |
| spoken episode-number continuity callbacks in last 10 | hit | 0 continuity episode-N/EpN callbacks in ep129–138 Whisper (identity line only) |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/models_agents_podcast.txt`** (prompt) — UTH contrast-cliché is 10/10 (Everyone talks/treats); teaser locked on Before we go 10/10 after keep-an-eye cleared; episode-number ban never landed. Meta-rule: de-seed by shape + verbatim ban, no quotable replacement menu; successor-tic predictions recorded in ledger.
```diff
- AVOID EDITORIAL PADDING (this is the #1 reason episodes feel like commentary rather than AI news):
- The following sentence patterns are how a script drifts from reporting into editorializing. Use them sparingly — AT MOST ONCE per item:
+ UNDER-THE-HOOD OPENER — SHAPE BAN (Aug 2026 quality pass):
+ After the signature deep-dive line ("okay, let's pop the hood on …" / "let's pop the hood on …"), go straight into the engineering mechanism. Do NOT open the body with a contrast-cliché that pits a vague public take against "the real engineering."
+ VERBATIM BANNED as deep-dive body openers (and close paraphrases):
+ - "Everyone talks about …"
+ - "Everyone treats …"
+ - "Most teams still …" / "Most people think …"
+ - "The common story is …" / "The usual take is …"
+ Shape to avoid: any throat-clear of the form "[everyone/most teams/the industry] [talks about/treats/assumes] X as if Y — in practice Z." Start with the mechanism, the constraint, or the measurement instead. Do not replace the ban with a new stock opener menu — vary naturally from the topic.
+ 
+ TOMORROW TEASER OPENER — SHAPE BAN (Aug 2026 quality pass):
+ Do not open the Tomorrow Teaser the same way every episode. Lead with the substance of what to watch (the lab, release, or evaluation), not a stock framing clause.
+ VERBATIM BANNED as default teaser openers (and close paraphrases):
+ - "Before we go, …"
+ - "Before we wrap, …"
+ - "keep an eye on …" / "Tomorrow keep an eye on …" / "Before we go, keep an eye on …"
+ A brief varied framing clause is fine if it is not one of the banned defaults and does not recur episode after episode. Never invent a replacement rotation menu of example phrases.
+ 
+ CONTINUITY CALLBACKS (Aug 2026 quality pass):
+ At most ONE continuity callback per episode. Prefer "yesterday" / a calendar date / "the prior episode." NEVER speak episode numbers or "EpN" / "episode one hundred twenty" as continuity ("tracked since episode N", "arc from episode N"). The structural identity line that names today's episode number once is allowed; callbacks to prior episode numbers are not.
+ 
+ AVOID EDITORIAL PADDING (this is the #1 reason episodes feel like commentary rather than AI news):
+ The following sentence patterns are how a script drifts from reporting into editorializing. Use them sparingly — AT MOST ONCE per item:
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/models_agents.yaml`** (config): ep132/133 deep-dives opened Everyone-talks without pop-the-hood → zero UTH chapter. Adding the live formula phrases restores the chapter without changing audio. Teaser marker alternates prevent chapter loss when Before-we-go is de-seeded. Does not replace deferred digest-driven titles.
- **`tests/test_models_agents_quality_pass.py`** (code): Drift-guard the two prompt bans, UTH/teaser marker alternates, and no-podcast-expand so a later edit cannot silently drop them.

## Deferred (carried forward)
- OPERATOR DECISION (length — escalated after July-19 + Aug-2 misses; do not re-file min_digest_words=1600 without an explicit choice): (A) raise min_digest_words to 1600, (B) Under-the-Hood licensed-knowledge sentence/fact floor in digest prompt, or (C) accept ~1200–1400w and lower min_podcast_words. Never re-enable podcast_expand_below_target. Today still 8/10 under 1500w.
- Digest-driven / position-aware mid-section chapter titles (carried; ep130/132/133/135–137 ellipsis auto-titles, ep132/133 lost UTH before marker patch — markers remain brittle)
- Under the Hood licensed-knowledge sentence/fact floor in digest prompt — operator option B
- Accept ~1200–1400w natural length and lower min_podcast_words — operator option C
- Signature opener "okay let's pop the hood on" (~8/10) — intentional chapter signal; revisit only with A/B evidence
- Network-wide: blog/RSS transcript sourced from pre-pronunciation text or Whisper (LoRA/RAG/JAXA class leaks) — collision-unsafe for lone-token restore
- July-2 selection rebalance A/B (lab product/feature announcements outrank preprints; arXiv items <= 40%) — still not applied
- Recap must synthesize, not splice dailies' sentences (Sunday weekly_summary_segment) — carried

## Drift-guard status
```
============================= test session starts ==============================
collected 7 items

tests/test_models_agents_quality_pass.py .......                         [100%]

============================== 7 passed in 0.09s ===============================
```

<sub>tokens: 49420 in / 5604 out</sub>