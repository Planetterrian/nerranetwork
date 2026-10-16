Ep16–25 cleared the handset and trade-off-flips predictions after Oct-5/earlier prompt+YAML fixes, but 9/10 scripts still sit under the 1400-word floor on a digest ceiling, the prompt-seeded teardown closer calcified into “stops being the right X when…”, and consumer desktop memory plus a models-flavored teardown still leak the beat.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1387**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| scripts/digests containing consumer handset or flagship-phone Silicon items (Snapdragon mobile / iPhone / Vivo / OriginOS class) | hit | Ep16–25: no flagship-phone SKU blocks; Oct-5 exclude_title_patterns for smartphones/handsets/Snapdragon Elite/Dimensity present in shows/ai_chips.yaml |
| episodes whose chapters JSON lacks a 'The Teardown' chapter OR whose script lacks phrase 'take it apart' | hit | chapters_ep016–025 all include The Teardown at startTime continuity from 3.0s intros; take/apart forms present (widened marker) |
| Teardown subject entity overlap with same-episode Silicon/DC/Supply item headings | partial | No Ep7-style full restatement streak; Ep25 teardown walks same QFX5252/Tomahawk6/Helios tray as news; teardown_overlap still absent from digest_lints |
| scripts whose Teardown close uses the predicate family 'trade-off flips' / 'tradeoff flips' | hit | 0/10 ep16–25 transcripts; replaced by prompt-seeded 'stops being the right … when' (≥6/10) |
| podcast_script_word_count median Ep14–20 | partial | Last-10 median ≈1205 (≥1100) but 9/10 still under live min_podcast_words 1400; only ep23 at 1460 |
| digest_word_count median Ep14–20 | miss | Scripts remain ceiling-bound with digest_expand already on; ep18/24 coverage 55–58%; second miss → escalate format arithmetic |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/ai_chips_digest.txt`** (prompt) — SELECTION-layer mirror of new excludes so the LLM does not re-admit desktop DIMM award copy that slips past RSS titles (Ep25).
```diff
- Reject consumer graphics cards and gaming GPUs, phone and handset chip launches (a phone chip belongs here only when the story is its foundry, process node or packaging capacity), consumer-hardware deals and reviews, opinion without a new fact, earnings previews, and stock-price stories with no operational substance.
+ Reject consumer graphics cards and gaming GPUs, phone and handset chip launches (a phone chip belongs here only when the story is its foundry, process node or packaging capacity), desktop or creator PC memory modules and design awards (CQDIMM/UDIMM/consumer DDR kits — server RDIMM, MRDIMM, HBM and module supply stay in), consumer-hardware deals and reviews, opinion without a new fact, earnings previews, and stock-price stories with no operational substance.
```

**`shows/prompts/ai_chips_podcast.txt`** (prompt) — Prompt's own 'stops being the right one' became the ≥6/10 successor tic after trade-off flips was banned. De-seed by shape + verbatim ban; no new example sentence (meta-review de-seed rule).
```diff
- Build from the mechanism, through the worked example with every figure the briefing gives, to the condition; carry at least six numbers; end on the specific condition under which today's design choice stops being the right one, said in this teardown's own terms — the closing sentence's verb and subject change every day, and it never reuses a stock phrase about a tradeoff.
+ Build from the mechanism, through the worked example with every figure the briefing gives, to one concrete invalidating condition named in this teardown's own nouns; carry at least six numbers. The closing sentence must change verb and subject every day. Verbatim ban on stock closer predicates: "stops being the right", "trade-off flips", "tradeoff flips", "the trade off flips". Never close on a generic tradeoff slogan or a copied invalidation template — describe the failing condition with today's parts, sites or measurements only (no specimen closer sentence in this prompt).
```

**`shows/prompts/ai_chips_podcast.txt`** (prompt) — Shape ban alone missed three times in ep19–21; add verbatim ban without seeding a replacement opener.
```diff
- Its first sentence names the mechanism's subject with a fact from the article it is built on; the words "take it apart" may sit inside it when they read naturally, never as its opening words, never in a "take it apart at the X, not at the Y" frame, and never bent to fit (chapters find the segment either way).
+ Its first sentence names the mechanism's subject with a fact from the article it is built on; the words "take it apart" may sit inside a later sentence when they read naturally, never as the segment's opening words, and never bent to fit (chapters find the segment either way). Verbatim ban on contrast-open skeletons: "take it apart at the …, not at the …" and "take it apart at the … not at the …" (Ep19 module/logo, Ep20 replay/application, Ep21 parts bin/purchase order still shipped that frame).
```

**`shows/prompts/ai_chips_digest.txt`** (prompt) — Ep24 Teardown spine was open-weight model hosting. Tighten Teardown beat boundary without seeding a specimen topic.
```diff
- One engineering explanation (450-600 words) of a mechanism behind today's layer of the stack — why a packaging step bottlenecks supply, what actually limits rack power density, how a cooling method trades water for energy, why an interconnect choice matters.
+ One engineering explanation (450-600 words) of a hardware-layer mechanism — packaging, power delivery, cooling, interconnect PHY, lithography/tooling, memory hierarchy at the package or rack — not model distribution, parameter counts, or open-weight hosting as the spine (those belong to Models & Agents; Ep24 memory-shelf teardown drifted into model hosting).
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/ai_chips.yaml`** (config): Ep25 admitted a desktop creator DDR5 CQDIMM design-award item. Fetch-side drop is highest-yield (garble/fetch class); handset patterns do not cover this class.
- **`shows/ai_chips.yaml`** (config): Prompt-only teardown uniqueness missed Ep1/Ep2/Ep7 and Ep25 still deep-dives the same news object. Opt-in lint forces one-shot retry; requires matching engine/digest_lint.py implementation. Third proposal only because prior two never shipped.
- **`engine/digest_lint.py`** (code): Mechanical enforcement after repeated prompt-only misses; garble/lint class is highest-yield per meta-review.
- **`tests/test_ai_chips_quality_pass.py`** (code): Every behavioral fix needs a drift-guard; pin on committed episodes so main is not red on empty run days (Sep 2026 meta-review).

## Deferred (carried forward)
- Operator decision on digest format arithmetic after two digest-median ≥1250 misses (Ep4–13 and Ep14–20) — verify expand pre/post metrics; do not third-file site-mix prompt essays or any podcast-side length lever
- Data-side teardown-closer rotation memory (frame_memory or recent-closer injection) if 'stops being the right' successor remains after one prompt de-seed — ledger already flagged this path
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

<sub>tokens: 50418 in / 6310 out</sub>