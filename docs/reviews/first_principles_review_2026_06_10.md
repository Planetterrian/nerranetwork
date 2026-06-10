# First Principles Daily — quality pass (2026-06-10)

First review of **First Principles Daily** (FPD), a daily *narrative* show
(`narrative_mode: true`, topic-queue-driven, no news fetch). Launched
2026-06-07; 5 episodes shipped (Ep001-005). Distribution OFF at launch
(no newsletter, X, or YouTube). Patrick voice on the blessed Grok TTS
chain. Methodology: `.claude/commands/review-show.md`. Transcripts are the
ears (no audio listened).

## TLDR

Two genuinely FP-specific defects, both fixed:

1. **Chapters were broken** — FP was skipped by the June 10 Tesla/four-show
   chapter hardening and had **no positional `where` anchors**. The
   brand-heavy closing ("That's *First Principles Daily* for today…")
   re-opened an `Introduction` chapter on the sign-off, and Ep001-004
   shipped with **no `Closing` chapter at all**. Fixed with
   `where: start` (Introduction) / `where: end` (Closing) — the same
   pattern every other show already has.
2. **`podcast_expand_below_target: true` was a dead path for FP** — the
   expansion-retry prompt is news-framed ("cover **more stories** at full
   depth", "find every story in the digest you skipped"). FP is a
   one-topic narrative show with no "stories", so the retry gave the model
   nothing actionable and the script kept its length. Every thin FP
   episode fired the retry and stayed thin (Ep002 953w, Ep004 935w). Fixed
   by branching the retry on `narrative_mode`: narrative shows now expand
   by **deepening the single topic from the brief** (walk the arithmetic,
   name specifics, address objections) — which is what FP's own prompt asks
   for on the first pass.

Two P0-looking symptoms from the committed Ep001-004 files (missing closing
block; duplicate chapters) were verified **already fixed upstream today** by
the Planetterrian missing-closing guard (`engine/pipeline.py`) and the
Tesla once-per-title chapter matching — **Ep005 (today) already ships a
clean chapter set and the full closing**. They are not re-fixed here; the
`where` anchors add the FP-specific robustness the upstream once-per-title
matching doesn't (greeting/closing brand-mention edge cases).

---

## Phase 0 — context

- No prior FP review or ledger existed; this is the first pass.
- `review_state.yaml` had FP last-reviewed 2026-06-09 (seed).
- `api/op3_stats.json`: no OP3 data for FP yet (launched 3 days ago,
  distribution off).
- Snapshot (`scripts/review_snapshot.py first_principles`): all 5 episodes
  below the 1500 floor (1414/953/1182/935/1121w); duplicate/multiple
  `Introduction` chapters on 4/5 episodes; cost avg $0.086/ep.

## Phase 1/2 — findings

### P0 (verified, already fixed upstream — documented, not re-fixed)

- **Ep004 shipped with no closing block.** `..._Ep004_..._tts.txt` ends
  "Watch for that same question surfacing next…" then jumps straight to the
  AI disclosure — no "That's First Principles Daily… See you tomorrow."
  Root cause: the LLM omitted the supplied `closing_block`. The
  missing-closing guard added today (`engine/pipeline.py:331-351`, PT
  review) appends the resolved block verbatim when absent. **Ep005 has the
  full closing** → guard confirmed working on the FP path.
- **Duplicate `Introduction` / missing `Closing` chapters (Ep001-004).**
  `chapters_ep001.json` has Introduction at both 20s and 571s; ep002/003
  likewise; ep001-004 have no Closing chapter. Root cause: the closing
  variant contains "First Principles Daily" (Introduction trigger) and
  "first principle"/"opportunity". Once-per-title matching
  (`engine/chapters.py:162`, Tesla pass today) + the new `where` anchors
  resolve this; **Ep005 already parses to unique titles + a real Closing.**

### P1 (fixed)

- **No `where` anchors on FP chapter markers**
  (`shows/first_principles.yaml`). Every other show got `where: start|end`
  in the Tesla/EI/four-show passes; FP was omitted. Added `where: start`
  to Introduction and `where: end` to Closing. Belt-and-suspenders on top
  of once-per-title: protects against greeting variants that don't contain
  the brand and against the closing's brand mention. Drift guard +
  realistic-script parse test.
- **Narrative expansion retry was a dead path**
  (`engine/generator.py:1786`). `podcast_expand_below_target: true` is set
  for FP, so the one-shot retry fires on every <1500w script — but the
  retry prompt told the model to "cover MORE STORIES … find every story in
  the digest you skipped". A one-topic narrative show has none, so the
  retry returned ~the same length ("Retry did not improve script length …
  keeping original"). Refactored the retry-prompt construction into
  `_build_expansion_retry_prompt(..., narrative=)` and branch on
  `config.narrative_mode`: narrative shows expand by deepening the single
  topic from the full brief. Also benefits Unintended Consequences.

### P2 / deferred

- **Digest stage is itself under-length.** The briefs ship 870–1498w vs
  the episode prompt's 1600/2000 floor, and the podcast script is ~1:1
  with the brief (Ep004: 935w script ≈ 932w brief). `generate_digest` has
  only a refusal retry, no length-expansion retry, so a thin brief is
  never rescued and caps the podcast. A digest-stage expansion retry is
  the natural next lever — **deferred** to keep this pass to the verified
  podcast-stage fix; logged in the ledger.
- **Lesson-sentence echo.** "…is announcing a design or process problem,
  not a material shortage" recurs ~3/5 episodes — it is the prompt's own
  example lesson principle becoming a template (MAB "So imagine" class).
  Real but mild; a prompt edit here risks the lesson's quality with no
  length/clarity payoff. Deferred — not worth an audio-affecting change on
  thin evidence.
- **Length ceiling is accepted, not a bug.** The YAML already documents the
  operator regenerating 3× (8 → 10.6 → 10.1 min) and concluding grok-4.3
  plateaus ~1200–1500w network-wide and resists prompt escalation. This
  pass deliberately does **not** re-litigate the target; it only makes the
  thin-pass rescue functional. Recorded under `do_not_retry`.
- **Topic queue runway healthy:** 26 unproduced, concrete/opportunity
  alternation intact (~3.7 weeks). RSS titles are per-episode hooks (good
  SEO). No action.
- **Distribution stays OFF** (operator decision; network review says wait
  to ~Ep15). Recorded under `do_not_retry`.

---

## ⚠️ A/B-listen required (landmine #17)

- **`engine/generator.py` — narrative expansion retry.** Changes generated
  audio *only when a narrative episode's first pass lands below target and
  the retry fires*. Strictly better framing (deepen the existing topic vs a
  no-op instruction), but per landmine #17 the operator should listen to
  the next FP (or UC) episode that triggers an expansion to confirm the
  deepened script reads naturally and doesn't drift from the brief. No
  prompt-file was changed and there is no deterministic single-run output
  to paste (the retry only fires on a thin first pass); behavior is pinned
  by unit tests.
- The chapter `where` anchors (`shows/first_principles.yaml`) are
  **metadata only** — they don't change the audio, only the chapter list.
  No listen required.

## Tests

- New: `tests/test_first_principles_quality_pass.py` (8 tests) — chapter
  anchors, every closing variant matched, realistic-script parse (single
  Introduction first + Closing last), narrative-vs-news retry branching,
  FP is narrative_mode.
- Regression: `test_generator.py`, `test_chapters.py`,
  `test_four_show_quality_pass.py`, `test_prompt_fidelity.py`,
  `test_episode_validity.py` — **176 passed**.

## Recommended next pass

1. Score the two predictions in the ledger against new episodes.
2. If thin episodes persist after the retry fix, add a **digest-stage**
   length-expansion retry (the deferred item) — the brief is the substrate
   and it is itself under the prompt floor.
3. Re-evaluate distribution-on once Ep~15 is reached and length stabilizes.
