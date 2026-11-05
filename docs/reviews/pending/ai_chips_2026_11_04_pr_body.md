Ep35–44 finally clear the 1400-word floor (median ~1780) and keep chapters clean, but the still-unshipped prompt specimen “stops being the right…” remains a 6/10 Teardown closer, consumer/edge silicon and a hobbyist PDP-11 teardown still leak the beat, and handset title filters false-drop foundry copy.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1675**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| scripts/digests with consumer desktop DIMM awards OR console/handheld gaming BOM-as-Silicon (CQDIMM/UDIMM/PlayStation/Xbox class) | partial | No CQDIMM/PS6 in ep35–44; excludes unshipped; Ep36 Raptor Lake desktop, Ep39 Pi kit, Ep40 Threadripper AI TOP still leak consumer/edge class |
| scripts whose Teardown closing sentence matches 'stops being the right' OR 'trade-off flips' OR 'tradeoff flips' | miss | 6/10 ep35–44 still close with 'stops being the right…'; both prompts still instruct that specimen; prior de-seed never applied |
| scripts whose Teardown first sentence matches contrast skeleton 'take it apart at the X, not at the Y' | partial | Ep39 opens 'Take it apart at the research clock, not the fab clock'; shape ban alone did not hold |
| Teardown subject entity overlap with same-episode Silicon/DC/Supply headings (manual or lint) | miss | teardown_overlap still absent from digest_lints (lever not shipped); score as miss on the lint path — no mechanical enforcement this window |
| podcast_script_word_count median next 7 | hit | ep35–44 median ≈1783 words; 0/10 under live min_podcast_words 1400 |
| digest_word_count median next 7 | partial | Script floor fully cleared with digest_expand on; raw digest median not in snapshot; format-arithmetic operator decision still not documented as shipped |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/ai_chips_digest.txt`** (prompt) — SELECTION-layer mirror of new excludes so the LLM does not re-admit desktop/SBC/console copy that slips past RSS titles (Ep36, Ep39, Ep40) while preserving foundry/node stories.
```diff
- Reject consumer graphics cards and gaming GPUs, phone and handset chip launches (a phone chip belongs here only when the story is its foundry, process node or packaging capacity), consumer-hardware deals and reviews, opinion without a new fact, earnings previews, and stock-price stories with no operational substance.
+ Reject consumer graphics cards and gaming GPUs, phone and handset chip launches (a phone chip belongs here only when the story is its foundry, process node or packaging capacity — keep TSMC/Intel/Samsung node and capacity stories even if a phone SKU is named as a customer), consumer desktop CPU refreshes and creator/SBC/Raspberry Pi kits, desktop/UDIMM/CQDIMM memory modules and design awards (server RDIMM/MRDIMM/HBM stay in), console or handheld gaming BOM-as-Silicon, consumer-hardware deals and reviews, opinion without a new fact, earnings previews, and stock-price stories with no operational substance.
```

**`shows/prompts/ai_chips_digest.txt`** (prompt) — Digest still seeds the 6/10 closer tic and allowed Ep41 PDP-11 spine. Shape-only close + beat boundary; no new example sentence (meta-review de-seed rule).
```diff
- and the specific condition under which today's design choice stops being the right one, in this teardown's own terms. Its subject must NOT be the subject of any news item above, including a forecast or capacity item about the same technology; it is a second story, not a second pass. Carry as many sourced numbers as the article supports, up to eight. Open on the mechanism or the number, never on a claim about what most people believe, and never on a "not X but Y" contrast.
+ and one concrete invalidating condition for today's design choice, stated in this teardown's own nouns and verbs (a dated limit, a failed budget, a physical bound the article names) — never a stock predicate. Verbatim ban in the closing sentence: "stops being the right", "trade-off flips", "tradeoff flips", "fails when", "only when it". No example closing sentence. Its subject must NOT be the subject of any news item above, including a forecast or capacity item about the same technology; it is a second story, not a second pass. The Teardown is an infrastructure mechanism article only (packaging, power path, cooling, HBM/memory stack, fab tool, interconnect, grid interconnection) — never hobbyist retro hardware, consumer PC bring-up, or model-hosting software. Carry as many sourced numbers as the article supports, up to eight. Open on the mechanism or the number, never on a claim about what most people believe, never on a "not X but Y" contrast, and never on "take it apart at the X, not at the Y".
```

**`shows/prompts/ai_chips_podcast.txt`** (prompt) — Prompt's own 'stops being the right one' is the live 6/10 successor after trade-off flips died. De-seed by shape + verbatim bans; no replacement specimen. Reinforces contrast-open ban Ep39 ignored.
```diff
- Build from the mechanism, through the worked example with every figure the briefing gives, to the condition; carry at least six numbers; end on the specific condition under which today's design choice stops being the right one, said in this teardown's own terms — the closing sentence's verb and subject change every day, and it never reuses a stock phrase about a tradeoff. The segment's digest heading is for the writer: never say that the teardown has a title, never read its title out, and never announce the segment.
+ Build from the mechanism, through the worked example with every figure the briefing gives, to one concrete invalidating condition; carry at least six numbers; end on that condition in this teardown's own nouns and verbs — the closing sentence's verb and subject change every day. Verbatim ban on closing with: "stops being the right", "trade-off flips", "tradeoff flips", "fails when", "becomes the right tool". Never open the segment with "take it apart at the X, not at the Y" or any "at the X, not at the Y" contrast skeleton (banned frame; Ep39 still shipped it). The segment's digest heading is for the writer: never say that the teardown has a title, never read its title out, and never announce the segment.
```

**`engine/frame_memory.py`** (code) — Data-side closer rotation after consecutive prompt-only miss cycles; ledger already flagged memory over a third prompt-only filing. frame_memory already true on this show.
```diff
- 
+ When frame_memory is on for ai_chips, also collect the last N Teardown closing sentences from recent _tts.txt (sentence containing or following the take-apart segment through On the horizon) and inject them as a do-not-reuse closer list into podcast context — same pattern as opener memory. Ban list should include any closer matching stops being the right / trade-off flips regardless of N.
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/ai_chips.yaml`** (config): Fetch-side drop is highest-yield. Handset bare pattern false-drops foundry titles; desktop/console/SBC patterns never applied despite Ep25/27/36/39/40 leaks.
- **`shows/ai_chips.yaml`** (config): Fifth filing only because prior four never shipped. Garble/lint class is highest-yield; requires matching engine/digest_lint.py implementation. Show opt-in.
- **`engine/digest_lint.py`** (code): Mechanical enforcement after repeated prompt-only misses; pair with YAML digest_lints entry.
- **`tests/test_ai_chips_quality_pass.py`** (code): Every behavioral fix needs a drift-guard; pin on committed shape so CI tolerates today (Sep 2026 meta-review).

## Deferred (carried forward)
- Operator decision on digest format arithmetic — monitoring only while scripts clear 1400; re-open only if floor collapses with expand pre/post metrics proving no-op
- Prune x_accounts handles that log No recent posts (partially mitigated by x_accounts_per_run: 4)
- Network-wide absence-sentence filter (precision not proven on other shows)
- Dedicated audio theme (still assets/music/ModelsAgents.mp3 per plan §5c)
- Re-grade full RSS list with check_feeds.py ai_chips on a runner
- preferred_domains tightening if x.com Sources median stays elevated
- OP3 first-week downloads still ~0 — instrumentation/prefix and distribution ramp outside prompt edits
- Any podcast-side length lever (min_podcast_words raise, podcast_expand_below_target, write-longer pressure) — do_not_retry
- Re-proposing dc_items_unlabelled as the fix for zero DC sites — do_not_retry
- Phonetic respellings or programmatic speech-tag / <fast> injection — do_not_retry landmine #17

<sub>tokens: 63380 in / 6794 out</sub>