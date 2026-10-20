Ep20–29 still run 6/10 scripts under the 1400 floor on a digest ceiling, the prompt-seeded Teardown closer “stops being the right…” remains in 6/10, and consumer desktop/console silicon (Ep25 CQDIMM, Ep27 PS6/RTX Spark) still leaks while the prior desktop exclude and closer de-seed never shipped.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1467**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| scripts/digests whose Silicon items are consumer desktop/creator PC memory modules or design awards (CQDIMM/UDIMM desktop DIMM class) | partial | No CQDIMM in ep26–29; Ep25 T-Create CQDIMM still in last-10; desktop excludes unshipped; Ep27 PS6/RTX Spark consumer leak adjacent class |
| scripts whose Teardown closing sentence matches stock predicates 'stops being the right' OR 'trade-off flips' OR 'tradeoff flips' | miss | 6/10 ep20–29 still close with 'stops being the right…'; both prompts still instruct that specimen; trade-off flips remains 0 |
| scripts missing teaser opener 'Before we go' OR 'before we wrap' | hit | ep20–29 transcripts and chapters_ep020–029 all include Tomorrow Teaser / Before we go |
| Teardown subject entity overlap with same-episode Silicon/DC/Supply headings (manual or lint) | partial | teardown_overlap still absent from digest_lints; no Ep7 full-restreak; Ep27 laptop teardown shares memory beat with news |
| podcast_script_word_count median next 7 | partial | last-10 median ≈1338 (≥1100) but 6/10 under live 1400; only ep26–29 consistently clear floor |
| digest_word_count median next 7 | miss | ep24 script 996w / 58% coverage; short half still ceiling-bound with digest_expand on — third miss → escalate format arithmetic |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/ai_chips_digest.txt`** (prompt) — SELECTION-layer mirror of new excludes so the LLM does not re-admit desktop DIMM award or console BOM copy that slips past RSS titles (Ep25, Ep27).
```diff
- Reject consumer graphics cards and gaming GPUs, phone and handset chip launches (a phone chip belongs here only when the story is its foundry, process node or packaging capacity), consumer-hardware deals and reviews, opinion without a new fact, earnings previews, and stock-price stories with no operational substance.
+ Reject consumer graphics cards and gaming GPUs, phone and handset chip launches (a phone chip belongs here only when the story is its foundry, process node or packaging capacity), consumer desktop/creator DIMM modules and design awards (CQDIMM/UDIMM/SO-DIMM — server RDIMM/MRDIMM/HBM stay in), console or handheld gaming BOM and memory-price stories (PlayStation/Xbox class), consumer-hardware deals and reviews, opinion without a new fact, earnings previews, and stock-price stories with no operational substance.
```

**`shows/prompts/ai_chips_digest.txt`** (prompt) — Digest Teardown still seeds the 6/10 closer tic and allowed Ep24 models-hosting / Ep27 laptop spines. Shape-only close + beat boundary; no new example sentence (meta-review de-seed rule).
```diff
- and the specific condition under which today's design choice stops being the right one, in this teardown's own terms. Its subject must NOT be the subject of any news item above, including a forecast or capacity item about the same technology; it is a second story, not a second pass.
+ and one concrete invalidating condition for today's design choice, named in this teardown's own verb and subject (never a stock closer). Verbatim ban in the closing sentence: "stops being the right", "trade-off flips", "tradeoff flips". Its subject must NOT be the subject of any news item above, including a forecast or capacity item about the same technology; it is a second story, not a second pass. Prefer a mechanism article on packaging, power delivery, cooling, HBM/stack, interconnect, or fab tools — not open-weight model hosting and not consumer PC/laptop products.
```

**`shows/prompts/ai_chips_podcast.txt`** (prompt) — Prompt's own 'stops being the right one' is the live 6/10 successor after trade-off flips died. De-seed by shape + verbatim bans; no replacement specimen. Reinforces contrast-open ban that Ep20/21 ignored.
```diff
- Build from the mechanism, through the worked example with every figure the briefing gives, to the condition; carry at least six numbers; end on the specific condition under which today's design choice stops being the right one, said in this teardown's own terms — the closing sentence's verb and subject change every day, and it never reuses a stock phrase about a tradeoff. The segment's digest heading is for the writer: never say that the teardown has a title, never read its title out, and never announce the segment.
+ Build from the mechanism, through the worked example with every figure the briefing gives, to one concrete invalidating condition; carry at least six numbers. The closing sentence's verb and subject must change every day. Verbatim ban on closing predicates: "stops being the right", "trade-off flips", "tradeoff flips", and any "X stops being the right Y when…" skeleton. Also never open the segment in a "take it apart at the X, not at the Y" contrast frame (banned; Ep20/Ep21 still shipped it). Do not deep-dive consumer PCs, laptops, consoles, or open-weight model hosting — infrastructure mechanism only. The segment's digest heading is for the writer: never say that the teardown has a title, never read its title out, and never announce the segment.
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/ai_chips.yaml`** (config): Fetch-side drop is highest-yield (garble/fetch class). Handset patterns do not cover Ep25 CQDIMM or Ep27 console/laptop consumer silicon; prior 10-16 desktop proposal never applied.
- **`shows/ai_chips.yaml`** (config): Fourth filing only because prior three never shipped. Garble/lint class is highest-yield; requires matching engine/digest_lint.py implementation. Show opt-in.
- **`engine/digest_lint.py`** (code): Mechanical enforcement after repeated prompt-only misses; pair with YAML digest_lints entry.
- **`tests/test_ai_chips_quality_pass.py`** (code): Every behavioral fix needs a drift-guard; pin on committed shape so CI tolerates today (Sep 2026 meta-review).

## Deferred (carried forward)
- Operator decision on digest format arithmetic after three digest-median ≥1250 miss cycles (Ep4–13, Ep14–20, ep20–25 short half) — verify expand pre/post metrics; do not third-file site-mix prompt essays or any podcast-side length lever
- Data-side Teardown-closer rotation memory (frame_memory or recent-closer injection from last N scripts) if 'stops being the right' remains after this shape de-seed ships — ledger already flagged memory over a third prompt-only filing
- Tighten handset exclude so TSMC node/capacity titles that merely mention iPhone SKUs (Ep27 A14 leakage) are not false-dropped, without re-admitting Ep6-class phone SoC launches
- Prune x_accounts handles that log No recent posts (partially mitigated by x_accounts_per_run: 4)
- Network-wide absence-sentence filter
- YouTube enable (launch policy — operator date)
- Dedicated audio theme (still assets/music/ModelsAgents.mp3 per plan §5c)
- Re-grade full RSS list with check_feeds.py ai_chips on a runner
- preferred_domains tightening if x.com Sources median stays elevated
- OP3 downloads None for this show — instrumentation/prefix investigation outside prompt edits
- Any podcast-side length lever (min_podcast_words raise, podcast_expand_below_target, write-longer pressure) — do_not_retry
- Re-proposing dc_items_unlabelled as the fix for zero DC sites — do_not_retry
- Phonetic respellings or programmatic speech-tag / <fast> injection — do_not_retry landmine #17

<sub>tokens: 55456 in / 5961 out</sub>