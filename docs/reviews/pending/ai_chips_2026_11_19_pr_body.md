Ep50–59 mostly clear length and keep chapters clean, but the still-unshipped prompt specimen “stops being the right…” remains a multi-episode Teardown closer, consumer/desktop silicon still leaks, two scripts sit under 1400, and handset title filters still false-hit foundry copy.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1811**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| scripts whose Teardown closing sentence matches 'stops being the right' OR 'trade-off flips' OR 'tradeoff flips' | miss | Specimen still in both prompts; Ep54 'stops being the right machine'; near-family stops earning/holding/losing on Ep50/52/56/57/58/59 — de-seed never applied |
| scripts/digests with consumer desktop CPU refreshes OR SBC/Pi hobby kits OR console BOM OR desktop DIMM awards as Silicon/Also-Today leads | miss | Ep51 ASUS creator Mini PC; Ep54 Razor Lake desktop IDs + 4090 teardown; Ep56 Razor Lake 12P; Ep59 MSI EdgeMesa desktop — excludes unshipped |
| scripts whose Teardown first sentence matches contrast skeleton 'take it apart at the X, not at the Y' | miss | Ep51 'Take that split apart at the power lead, not at the zip code' |
| Teardown subject entity overlap with same-episode Silicon/DC/Supply headings (manual or lint) | miss | teardown_overlap still absent from digest_lints (n/a-lever path); Ep54 consumer-GPU teardown off-beat — score miss on unshipped lint commitment |
| podcast_script_word_count median next 7 under live min_podcast_words 1400 | partial | 2/10 under 1400 (ep51 1334, ep55 1341); median ~2103 — floor mostly holds |
| fetch-filter false drops of foundry/node titles that merely mention phone SKUs (smartphone pattern on TSMC process stories) | partial | No new smartphone-title hit in ep50–59 leakage list; ep50 how-to noise on mechanism prose; tighter SKU patterns still unshipped |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/ai_chips_digest.txt`** (prompt) — SELECTION-layer mirror of new excludes so the LLM does not re-admit desktop/creator/console copy that slips past RSS titles (Ep51, Ep54, Ep56, Ep59) while preserving foundry/node and rack stories.
```diff
- Reject consumer graphics cards and gaming GPUs, phone and handset chip launches (a phone chip belongs here only when the story is its foundry, process node or packaging capacity), consumer-hardware deals and reviews, opinion without a new fact, earnings previews, and stock-price stories with no operational substance.
+ Reject consumer graphics cards and gaming GPUs, phone and handset chip launches (a phone chip belongs here only when the story is its foundry, process node or packaging capacity), creator/desktop Mini PCs and RTX Spark desktop SKUs, consumer desktop CPU refreshes sold as gamer/creator parts, console/handheld BOM-as-news, desktop/creator DIMM awards, SBC/Pi hobby kits, consumer-hardware deals and reviews, opinion without a new fact, earnings previews, and stock-price stories with no operational substance. Server RDIMM/MRDIMM/HBM, rack/GPU server boards, and Grace Blackwell rack-scale stay in.
```

**`shows/prompts/ai_chips_digest.txt`** (prompt) — Digest still seeds the multi-generation closer tic and allowed Ep54 consumer-GPU spine. Shape-only close + beat boundary; no new example sentence (meta-review de-seed rule).
```diff
- and the specific condition under which today's design choice stops being the right one, in this teardown's own terms. Its subject must NOT be the subject of any news item above, including a forecast or capacity item about the same technology; it is a second story, not a second pass. Carry as many sourced numbers as the article supports, up to eight. Open on the mechanism or the number, never on a claim about what most people believe, and never on a "not X but Y" contrast.
+ and a closing sentence that states, in this teardown's own nouns and verbs, the concrete limit at which the mechanism stops paying for itself — a measured threshold from the article (a wattage, a dollar-per-megawatt, a yield gate, a latency budget), never a stock predicate. Verbatim ban in the closing sentence: "stops being the right", "stops earning its", "trade-off flips", "tradeoff flips", "becomes the right tool". No specimen closer. Its subject must NOT be the subject of any news item above, including a forecast or capacity item about the same technology; it is a second story, not a second pass — and never a consumer-GPU training guide, desktop SKU, or hobbyist retro board. Carry as many sourced numbers as the article supports, up to eight. Open on the mechanism or the number, never on a claim about what most people believe, and never on a "not X but Y" or "at the X, not at the Y" contrast.
```

**`shows/prompts/ai_chips_podcast.txt`** (prompt) — Prompt's own 'stops being the right one' elected the first successor tic; 'stops earning its place when' is the live second-generation family (Ep50/52/56/57/58/59) while the specimen remains. De-seed by shape + verbatim bans; no replacement specimen. Reinforces contrast-open ban Ep51 ignored.
```diff
- Build from the mechanism, through the worked example with every figure the briefing gives, to the condition; carry at least six numbers; end on the specific condition under which today's design choice stops being the right one, said in this teardown's own terms — the closing sentence's verb and subject change every day, and it never reuses a stock phrase about a tradeoff. The segment's digest heading is for the writer: never say that the teardown has a title, never read its title out, and never announce the segment.
+ Build from the mechanism, through the worked example with every figure the briefing gives, to a limit; carry at least six numbers; end on one concrete limit from the article at which the mechanism stops paying for itself (a measured threshold — wattage, dollar-per-megawatt, yield gate, latency budget), said in this teardown's own nouns and verbs. Verbatim ban in the closing sentence and the open: "stops being the right", "stops earning its", "trade-off flips", "tradeoff flips", "becomes the right tool", and the contrast skeleton "take it apart at the X, not at the Y" / "take that … apart at the X, not at". No specimen closer or specimen open — rotate verb and subject every day using only this article's terms. Never restock a consumer-GPU training guide or desktop SKU as the Teardown spine. The segment's digest heading is for the writer: never say that the teardown has a title, never read its title out, and never announce the segment.
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/ai_chips.yaml`** (config): Fetch-side drop is highest-yield (garble/fetch class). Bare handset/how-to patterns false-hit foundry and mechanism copy; desktop/creator/console patterns never applied despite Ep25/27/51/54/56/59 leaks.
- **`shows/ai_chips.yaml`** (config): Sixth filing only because prior five never shipped. Garble/lint class is highest-yield; requires matching engine/digest_lint.py. Show opt-in. If operator declines code this cycle, leave YAML unchanged and keep under Deferred as operator decision.
- **`engine/digest_lint.py`** (code): Mechanical enforcement after repeated prompt-only misses; pair with YAML digest_lints entry. Highest-yield fix class per meta-review.
- **`tests/test_ai_chips_quality_pass.py`** (code): Every behavioral fix needs a drift-guard; pin on committed shape so main is not red on empty run days (Sep 2026 meta-review).

## Deferred (carried forward)
- Operator decision on digest format arithmetic — monitoring only while median stays ≥1400; re-open only if floor collapses with expand pre/post metrics proving no-op
- Operator decision: ship teardown_overlap in engine/digest_lint.py (proposed five+ times, never landed) — escalate, do not sixth-file prompt-only uniqueness without the lint
- Verify frame_memory actually injects recent Teardown closers into the podcast prompt (frame_memory true but specimen still elected)
- Prune x_accounts handles that log No recent posts (partially mitigated by x_accounts_per_run: 4)
- Network-wide absence-sentence filter (precision not proven on other shows)
- Dedicated audio theme (still assets/music/ModelsAgents.mp3 per plan §5c)
- Re-grade full RSS list with check_feeds.py ai_chips on a runner
- preferred_domains tightening if x.com Sources median stays elevated
- Long-form YouTube retention pass (views-weighted long 12.7% vs shorts 62.1%)
- Any podcast-side length lever (min_podcast_words raise, podcast_expand_below_target, write-longer pressure) — do_not_retry
- Re-proposing dc_items_unlabelled as the fix for zero DC sites — do_not_retry
- Phonetic respellings or programmatic speech-tag / <fast> injection — do_not_retry landmine #17

<sub>tokens: 67812 in / 7579 out</sub>