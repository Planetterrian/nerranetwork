Ep56–65 mostly clear the 1400 floor and keep chapters clean, but the still-live prompt specimen “stops being the right…” and its near-family dominate Teardown closes, the banned contrast open still ships, and pre–Nov-24 desktop Lake leaks plus elevated fact-free/Repetitive scores remain the ceiling.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1748**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| scripts whose Teardown closing sentence matches 'stops being the right' OR 'stops earning its' OR 'trade-off flips' OR 'tradeoff flips' | miss | Specimen still in both prompts; Ep60/61/63/65 'stops being the right…'; Ep56–59/62 near-family stops holding/losing/loses its place |
| scripts/digests with consumer desktop CPU refreshes OR creator Mini PC/RTX Spark desktop SKUs OR console BOM OR desktop DIMM awards as Silicon/Also-Today leads | partial | Nov 24 excludes shipped; ep56 Razor Lake / ep59 EdgeMesa / ep62 Nova Lake are pre-ship; ep64 still has mini-ITX + robotics NUC-box news |
| scripts whose Teardown first sentence matches contrast skeleton 'take it apart at the X, not at the Y' (or 'take that … apart at the X, not at the Y') | miss | Ep62 'at the gate, not at a capacitor'; Ep63 'at the gap… not at the generator nameplate'; Ep60 'apart at the breaker' |
| Teardown subject entity overlap with same-episode Silicon/DC/Supply headings OR consumer-GPU/hobbyist teardown spines | miss | teardown_overlap still absent from digest_lints (lever not shipped); score miss on unshipped lint path — no mechanical enforcement |
| podcast_script_word_count under live min_podcast_words 1400 | hit | 1/10 under 1400 (ep61 1390); median ~1987 — floor holds without podcast-side levers |
| fetch-filter false drops / noise hits on foundry-node or mechanism titles (smartphone bare pattern; how-to on non-guide sentences) | partial | Nov 24 Lake patterns in YAML; ep60 smartphone pattern still hits TSMC designer-path copy; ep56/62 Lake still in digests pre-ship |

**Merge tier: B (listen)** — see docs/REVIEW_AGENT.md, "Merge tiers".

## Applied in this branch — listen before merging (landmine #17)
These changes are committed on this branch. A rehearsal of the episode was dispatched on this branch (Actions → "Run show", rehearse); listen to its artifact, then merge or close.

**`shows/prompts/ai_chips_digest.txt`** (prompt) — Digest still seeds the multi-generation closer tic (Ep56–65) and allowed off-beat spines in prior windows. Shape-only close + verbatim bans; no new example sentence (meta-review de-seed rule).

**`shows/prompts/ai_chips_digest.txt`** (prompt) — SELECTION-layer mirror of Nov 24 excludes plus Ep64 mini-ITX/NUC-box class so the LLM does not re-admit desk/creator silicon that slips past RSS titles while preserving foundry/rack stories.

**`shows/prompts/ai_chips_podcast.txt`** (prompt) — Prompt's own 'stops being the right one' elected the first successor tic; near-family still dominates ep56–65 while the specimen remains. De-seed by shape + verbatim bans; reinforce contrast-open ban Ep60/62/63 ignored; no replacement specimen.

## ⚠️ A/B-listen required — NOT applied (landmine #17)
None.

## Deferred (carried forward)
- Operator decision: ship teardown_overlap in engine/digest_lint.py (proposed five+ times, never landed) — escalate; do not sixth-file unpaired engine/YAML lint this pass
- Verify frame_memory injects recent Teardown closers into the podcast prompt after specimen removal (frame_memory true but specimen still elected)
- Operator decision on digest format arithmetic — monitoring only while median stays ≥1400; re-open only if floor collapses with expand pre/post metrics proving no-op
- Tighten smartphone exclude to launch/SKU-only shapes if ep60-class foundry false-drops recur — without re-admitting Ep6 phone SoC launches
- Optional YAML exclude for bare mini-ITX / NUC-box creator launches if Ep64 class recurs after SELECTION mirror
- Prune x_accounts handles that log No recent posts (partially mitigated by x_accounts_per_run: 4)
- Network-wide absence-sentence filter (precision not proven on other shows)
- Dedicated audio theme (still assets/music/ModelsAgents.mp3 per plan §5c)
- Re-grade full RSS list with check_feeds.py ai_chips on a runner
- preferred_domains tightening if x.com Sources median stays elevated
- Long-form YouTube retention pass (views-weighted long ~12% vs shorts ~60%)
- Any podcast-side length lever (min_podcast_words raise, podcast_expand_below_target, write-longer pressure) — do_not_retry
- Re-proposing dc_items_unlabelled as the fix for zero DC sites — do_not_retry
- Phonetic respellings or programmatic speech-tag / <fast> injection — do_not_retry landmine #17

<sub>tokens: 70092 in / 5765 out</sub>