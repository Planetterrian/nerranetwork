# Planetterrian Quality Review (June 10, 2026)

Same review-then-fix process as the Tesla (#576), four-show (#577), and
Russian (#579) passes. Drift guards: `tests/test_planetterrian_quality_pass.py`.
PT already inherited the engine-level fixes from #577 (show_memory echo
filter/idempotency/word-boundary detection, theme-history scrub, nightly OP3
performance loop) — this pass covers what remained.

**Date framing:** all audited episodes (Ep70–84, May 26–June 9) predate both
the #575 prompt bans (the "fits the tracked program" tic verified gone only
because Ep082 predates the ban — re-check post-pass episodes) and the #576
digest-carrying expand-retry. The "15 of 15 episodes under target" and the
banned-phrase findings are pre-fix states.

## Fixed

1. **Missing-closing guard (network-wide, `engine/pipeline.py`).** Ep081
   ended "See you next time." with no closing block; Ep084 ended mid-teaser
   with no sign-off, no CTA, and no Closing chapter. The prompts say "use
   this exact closing (do not rewrite it)" but the LLM occasionally omits
   it. The pipeline now appends the resolved `closing_block` verbatim when
   its opening signature is absent from the script's tail — before chapter
   parsing, so the Closing chapter always parses. Benefits every show.
2. **Contradictory length targets** — prompt said "10–13 minute", "12–15
   minute", and "at least 2400 words" while the YAML enforced 1250 (all 15
   recent episodes under it, avg ~970). One target now: **1,800–2,100 words
   ≈ 12–13 min, floor 1600** (mirrors the FF twin). The 60% skip line lands
   at 960 — the digest-carrying retry must lift a weak ~800-word draft past
   it; an episode that can't reach 960 even with the digest in hand is
   better skipped than shipped (the network's documented thin-day policy).
   **A/B-listen per landmine #17.**
3. **Chapter anchors + closing coverage** — `where: start/end` anchors;
   Closing pattern gains "see you next" (the Ep081 failure mode).

## Checked / no action

- Intros closing pool (2 variants) both matched the Closing pattern already.
- Theme-history identical lists Ep73–83 are pre-scrub snapshots; the #577
  scrub + echo filter govern from Ep85 on.
- RSS hook-first titles, narrative page freshness (rebuilt today), memory
  wiring, X teaser — all verified healthy.

## Operator items

- A/B-listen the next 2–3 episodes (length target change).
- Watch the first post-pass week for soft-floor skips (`.skip_*.json`
  markers with reason `podcast_script_too_thin`) — if PT skips more than
  once, drop `min_podcast_words` to 1400 rather than reverting the prompt.
