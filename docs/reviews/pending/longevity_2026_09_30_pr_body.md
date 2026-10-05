Ep2 fixed Ep1’s chapter-start and off-scope-lead failures but shipped ~884 words (below the 1200 floor) on a thin digest substrate, while Ep1’s committed audio still shows TTS show-name garble and off-scope disease trials.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.0682**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes (first 4) presenting an animal or cell result as a human result | partial | Ep1 labels evidence levels in transcript; ep2 chapter title is RCT/sarcopenia; 0 clear animal-as-human slips in n=2/4 |
| week stories that re-tell a Planetterrian headline from the same week without a new fact | partial | Sibling notes hooked via shows/hooks/longevity.py; sole ep1 transcript shows no Planetterrian retell tic; n=2/4 |
| spotlight claims stripped by the claims gate | partial | No strip-count field in snapshot/credit metrics — rate not measurable this pass |
| news items not about aging (disease trials not studied as aging) | partial | Ep1 still 3/6 off-scope in transcript + fetch-leakage; ep2 lead in-scope and no ep2 leakage rows; bar was 0 on 5/6 of first 6 |
| first chapter startTime (s) | partial | chapters_ep001.json startTime 325.9s; chapters_ep002.json Introduction 9.7s after fix — not yet ≤25 on 6/6 |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/longevity.yaml`** (config) — Ep2 shipped 884 spoken words at 100% digest coverage / 44 sentences — thin substrate, not missing podcast retries. Raise digest floor so Mechanism 550–700 + 4–7 week items can support ≥1200 spoken words. A/B-listen because runtime length changes.
```diff
- min_digest_words: 1300
-   digest_expand_below_target: true
+ min_digest_words: 1600
+   digest_expand_below_target: true
+   # keep podcast_expand_below_target: false — length is digest-side only (network ledger rule)
```

**`shows/prompts/longevity_podcast.txt`** (prompt) — Density audit flags 76–78% digest-verbatim and copied header blocks (Week in Longevity / Mechanism / What This Show Covers). Shape ban + no specimen phrase to avoid seeding the next tic. A/B-listen required.
```diff
- [The week's stories] Each from its first fact, with its evidence level. Move between stories with the next story's fact or a connective of six words or fewer. Never announce a section by name.
+ [The week's stories] Each from its first fact, with its evidence level. Move between stories with the next story's fact or a connective of six words or fewer. Never announce a section by name. Never speak digest markdown headings, label lines, or outlet 'Source' tails — paraphrase into speech only (ban the shape: reading a heading then the body).
```

## Code/metadata-only proposals (no A/B needed)
- **`tests/test_longevity_quality_pass.py`** (code): Locks Ep1-review fixes and this pass’s digest-floor / scope / hallmark regressions without touching audio pipeline settings.
- **`engine/chapters.py (regression coverage only if not already pinned)`** (code): Ep2 shows the fix works (9.7s); Ep1 on-disk file remains a landmine for naive 'all chapters clean' reads.

## Deferred (carried forward)
- Operator decision: prune or keep Ep1 (off-scope lead + hallmark recital + chapter gap) without breaking GUIDs
- TTS brand garble restore for Longevity/Nerra without phonetic prompt hacks (landmine #17)
- YouTube enable only after medical-content policy review
- Newsletter enable on/after 2026-10-01 with requires_health_disclaimer path
- Re-grade RSS list via check_feeds.py longevity on a runner; prune dead X handles from live fetch logs
- Network-wide absence_sentence_filter default (precision not proven on all shows)
- Dedicated music bed (still assets/music/oilers-pride.mp3)
- Per-episode claims-gate strip counter so launch prediction can score hit/miss
- Raise fetch_full_text or PMC spotlight depth only if digest floor still misses after min_digest_words 1600

<sub>tokens: 21365 in / 4239 out</sub>