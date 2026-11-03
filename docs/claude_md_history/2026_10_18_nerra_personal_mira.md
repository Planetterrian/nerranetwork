# Nerra Personal: Mira knows the listener, at no new model cost (Oct 18 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Nerra Personal: Mira knows the listener, at no new model cost (Oct 18 2026)

Operator-directed (guards `tests/test_personal_deep_2026_10_18.py`,
`tests/test_personal_handoffs_2026_10_17.py`; docs `docs/nerra_personal.md`
"Oct 18 2026"; register `personal-deep-2026-10-18`, `personal-trims-2026-10-18`).
**The cost rule binds: no new model or search call per member** — every
personal feature is deterministic code, ffmpeg on the cached segments, or a
few more lines in the ONE existing links call. What it adds: a member note
("Tell Mira about you", ≤ `PROFILE_MAX_CHARS` 240, scrubbed like every
free-text field, fenced in the prompt as information about the listener and
never instructions, at most two observations an edition, never logged);
edition memory (each `episodes.json` row records what the edition contained;
today's stories are matched against the last seven, so Mira says a story is
an update, never fresh news; the first edition explains what she does, Sunday
counts the week's threads); cross-show repeat notes; an opt-in `skip_repeats`
add-on and a length budget (`TARGET_MINUTES` 20/30/45/60) that trim only a
WHOLE show chapter whose edges sit in a pause between sentences, never a lead,
sign-off, last chapter or members-only episode, every trim named on air and in
the notes; and story chapters from the shows' own chapter files. **A music
show's story-break pause carries the theme (~-21 dB), so `silencedetect`
finds nothing there** — a ≥ 0.8 s sentence-ending Whisper gap counts as a
pause. On Oct 4-17 data no repeat trim passed every rule (chapters start late,
see `engine/chapters.py`); the notes are the benefit until they do. The
handoff repair (`realign_handoffs`) runs on every personal edition (Oct 17).
`PROFILE_MAX` / `TARGET_MINUTES` are mirrored in `workers/gallery/src/personal.ts`
(drift-guarded). Operator: `wrangler deploy` in `workers/gallery`; A/B-listen
the first edition with the new prompt blocks. ⚠️ AUDIO (Mira's lines).
