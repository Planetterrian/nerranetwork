# Sep 9 2026 — captions: the long-form layer is the uploaded TRACK, never the pixels

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Sep 9 2026 — captions: the long-form layer is the uploaded TRACK,
never the pixels.** The Aug 1 network-wide burn-in assumed CC defaults
off; YouTube remembers CC per account, and the operator's screenshot
showed YouTube's caption box drawn over the burned per-word captions
on long-form. `long_form_burn_in_captions: false` in `_defaults.yaml`
(guard `TestLongFormCaptionLayer`); Shorts keep burn-in and upload no
track. **Sep 17 2026:** `transcript_to_srt` never drops a real word —
Whisper closed SpaceX Ep103 on the single word "comments." at 0.34 s and
the under-0.4 s skip lost it from the track; short segments are now HELD
to the minimum (`artifact_floor_seconds` 0.15 s still drops blips). Arabic (or any other language) captions on a Short are
YouTube's auto-generated track auto-translated by the VIEWER's
caption-language preference — nothing in the pipeline carries a
language but `en`/`ru`/`fr`; it is a player setting, not a bug to
chase in code. Same day: EN `filled` Shorts (the second Short that
exists only to reach the requested count) earned a median of 3 views
across 17 uploads while the hook Short earned 48 — `shorts_fill_to_
requested: false` (EN path only; RU/FR dubs pick their own windows and
their filled Shorts earn ~225). Register: `long-form-captions-track-only`,
`en-shorts-no-fill`.
