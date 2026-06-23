# First Principles Daily — quality pass (2026-06-23)

Second review of **First Principles Daily** (FPD), a daily *narrative* show
(`narrative_mode: true`, topic-queue-driven, no news fetch). Now 18 episodes
shipped (Ep001–018); distribution turned ON since the last pass (YouTube +
newsletter enabled — operator decision, at Ep~12, in line with the "wait to
~Ep15" guidance). Methodology: `.claude/commands/review-show.md`. Transcripts
are the ears (no audio listened).

## TLDR

One genuinely listener-facing **P0** plus two **P1** quality-ceiling fixes:

1. **P0 — 7 of the first 18 episodes ship with NO Closing chapter.** The
   June-10 `where` anchors did not fully fix the orphan-Closing class. The
   sign-off tagline "one example or one opportunity, every day" contains
   **"opportunity"**, and the brand "First Principles Daily" contains **"first
   principle"** — so the body markers *The Opportunity* / *The First Principle*
   steal the sign-off line whenever they had not already matched in the body.
   Reproduced on the committed scripts: Ep001/004/007/009/011/015/017 all have
   no Closing chapter. Fixed by listing **Closing before the body markers** (the
   EI June-11 / SpaceX June-18 ordering rule); `where: end` keeps it out of the
   body. **18/18 episodes get a Closing chapter after the fix.** Metadata-only
   (no audio change). This reopens the prior review's prediction #2 as a MISS.
2. **P1 — lesson-template echo (de-seeded).** The June-10 pass deferred this on
   thin evidence (~3/5). It has grown to **12 of ~16 episodes** opening the
   lesson with the verbatim prompt-seeded formula *"a [part] whose price greatly
   exceeds its [materials] is announcing a design problem"*. Same tic class as
   Omni View "strongest case" / Env Intel "You arrive at a…": a seeded example
   became a fill-in-the-blank template. Fixed by de-seeding the example in both
   tracks of the digest prompt and requiring the lesson be phrased freshly per
   topic. Verified via `--test`: the regenerated digest opened "One lesson is
   that when regulatory review and on-site coordination dominate the cost
   stack…" — the verbatim formula is gone.
3. **P1 — digest-stage under-length (the deferred lever, now shipped).** The
   prior review's #1 recommended next lever. Briefs ship 848–1116w against the
   prompt's 1600 floor, and the podcast tracks the brief (now slightly exceeds
   it). Added an opt-in **digest-stage expansion retry** mirroring the
   podcast-stage one. Verified via `--test`: a 1146-word first pass was lifted
   to 1400 words by the deepen-the-brief retry — refuting the worry that
   grok-4.3 flatly resists (the trigger is set at 1400, below the observed
   ~1200–1500w plateau, so it rescues thin briefs without fighting the ceiling).

---

## Phase 0 — context

- Prior review: `docs/reviews/first_principles_review_2026_06_10.md` (PR #587).
- Snapshot (`scripts/review_snapshot.py first_principles`): all 10 recent
  `_tts.txt` below the 1500 floor (1003–1399w); cost avg $0.070/ep; OP3 7d=24,
  30d=31 (distribution recently on).
- **Prediction scoring (prior ledger):**
  - *Prediction 1* (narrative podcast retry → thin first-passes ≥1100w):
    **PARTIAL.** Scripts now consistently exceed their briefs (Ep018 brief
    869w → script 1190w) and the genuinely-thin band has lifted from 935–953w
    to mostly 1100–1400w — but Ep011 (1003w) and Ep014 (1040w) still land
    below 1100. The retry *works* (it deepens from the brief); the residual is
    the thin **brief**, attacked here at the digest stage.
  - *Prediction 2* (duplicate-Introduction + Closing-present on every new
    episode): **MISS on the Closing half.** Duplicate-Introduction is gone
    (0/18) — that half HIT. But Ep007/009/011/015/017 (all post-June-10)
    shipped with **no Closing chapter** for a different reason than the
    duplicate-Introduction bug the anchors fixed (see P0). Reopened and fixed
    here with a different approach (marker ordering).
- `do_not_retry` honored: no length-via-prompt-escalation, no phonetic
  respellings / tag injection, no premature distribution flip (already an
  operator call). The digest-stage expansion retry is **not** prompt
  escalation of the podcast target — it is a distinct mechanism explicitly
  deferred (not rejected) by the prior review.
- No closed-unmerged FP review PRs; no reverts touching FP files
  (`git log --grep=revert` clean for FP).

## Phase 1 / 2 — findings

### P0 — Closing chapter dropped on 7/18 episodes (fixed, metadata-only)

`shows/first_principles.yaml` chapter markers. Reproduced with `parse_chapters`
on every committed `_tts.txt`:

```
CURRENT order:  Ep001/004/007/009/011/015/017 → NO Closing chapter (7/18)
REORDERED:      all 18 episodes → Closing present (18/18)
```

Root cause (instrumented on Ep017): the closing line matched **The
Opportunity** via `opportunity` in "one example or one opportunity, every day"
because *The Opportunity* had not matched in the hearing-aids body and was
listed before *Closing*; `break` (first-marker-per-line) then consumed the
sign-off and Closing never matched. Episodes whose body *does* trigger *The
Opportunity* earlier (e.g. the genome Ep018) escaped — which is why the bug was
intermittent and the prior `where` anchors (which fix the *duplicate-
Introduction* class) missed it. Fix: list **Closing before the body markers**;
`where: end` already confines it to the final 15% so this only changes which
marker wins the sign-off line. Drift guard:
`TestClosingNotStolenByBodyMarkers` (an Ep017-style script whose body lacks
"opportunity"/"first principle").

### P1 — lesson-template echo (de-seeded; ⚠️ A/B-listen)

12 of ~16 `_tts.txt` open the lesson with the verbatim seeded formula:

```
Ep001 …whose price greatly exceeds its raw materials is announcing a design or process problem…
Ep002 …whose price greatly exceeds its materials is announcing a design or process problem…
Ep008 A part whose price greatly exceeds its materials is announcing a … material shortage.
Ep016 A product whose price greatly exceeds the value of its raw atoms is announcing a design or process problem…
… (Ep004/007/009/011/012/013/015/018 likewise)
```

Source: the digest prompt seeded the literal example in Track A
(`first_principles_episode.txt`) and Track B. The digest echoes the seed; the
podcast faithfully echoes the digest. De-seeded both tracks (and Track C for
consistency) and added an explicit instruction to phrase the lesson freshly per
topic and never open with the stock formula. Drift guard:
`TestLessonTemplateDeSeed`.

### P1 — digest-stage expansion retry (shipped, opt-in; ⚠️ A/B-listen when it fires)

`engine/generator.py` `generate_digest` had only refusal/truncation/repetition
retries — no length-expansion path — so a thin brief was never rescued and
capped the podcast. Added `_build_digest_expansion_retry_prompt` + a one-shot
retry gated on the new `llm.digest_expand_below_target` / `llm.min_digest_words`
config (default `False` / `0` = byte-for-byte no-op for every other show).
Narrative shows deepen the single topic; news shows develop more depth. FP opts
in at `min_digest_words: 1400`. Drift guard: `TestDigestExpansionRetry`.

### P2 / deferred

- **Garbage auto-segment chapter titles** (e.g. Ep011 "Interconnection queues
  add another layer"). Shared LLM-title class across the network; out of scope.
  Deferred (carried forward).
- **Residual under-length below ~1100w on a few episodes** even after both
  retries — bounded by the grok-4.3 plateau (do-not-retry). The digest retry
  raises the substrate; further escalation is off-limits.
- **Length ceiling itself stays accepted** (operator-confirmed grok-4.3
  plateau). Not re-litigated.

---

## ⚠️ A/B-listen required (landmine #17)

- **`shows/prompts/first_principles_episode.txt` — lesson de-seed.** Changes the
  digest (and therefore the spoken lesson) on every episode. The lesson now
  derives from today's subject instead of the stock formula. `--test` render
  confirms it renders and drops the formula; the operator should listen to the
  next episode to confirm the freshly-phrased lessons read as cleanly as the
  template did.
- **`engine/generator.py` + `shows/first_principles.yaml` — digest expansion
  retry.** Changes the brief (and therefore the episode) *only when a brief
  lands below 1400 words and the retry fires*. `--test` showed a 1146→1400w
  lift with the deepened content staying on-topic; operator should listen to
  the next FP episode whose brief triggers the retry.
- **`shows/first_principles.yaml` — Closing marker reorder.** Metadata only
  (chapter list); **no audio change**. No listen required.

### `--test` before/after excerpt (lesson de-seed + digest retry)

Topic regenerated: *"Why a Restaurant Kitchen Costs Half a Million Dollars"*
(opportunity_area). First pass 1146w → expansion retry → 1400w. New lesson
opener:

> One lesson is that when regulatory review and on-site coordination dominate
> the cost stack, the opportunity lies in moving certification and assembly
> upstream into repeatable factory modules rather than treating each site as a
> fresh construction project.

(vs. the shipped template "A [part] whose price greatly exceeds its materials is
announcing a design problem…").

## Tests

- New drift guards in `tests/test_first_principles_quality_pass.py`:
  `TestClosingNotStolenByBodyMarkers`, `TestLessonTemplateDeSeed`,
  `TestDigestExpansionRetry` (16 tests total in the file, all pass).
- Regression: `test_prompt_fidelity.py`, `test_episode_validity.py`,
  `test_generator.py`, `test_chapters.py` — **176 passed**;
  `test_network_quality_pass.py`, `test_four_show_quality_pass.py`,
  `test_unintended_consequences_quality_pass.py`, `test_config.py` — **120
  passed**.

## Recommended next pass

1. Score the three predictions in the ledger against new episodes
   (Closing-present rate, lesson-formula recurrence, brief word count).
2. If briefs still cap the episode after the digest retry, the only remaining
   non-padding lever is the grok-4.3 plateau itself — leave it (do-not-retry).
3. Take the network-wide garbage auto-segment chapter-title class (Ep011).
