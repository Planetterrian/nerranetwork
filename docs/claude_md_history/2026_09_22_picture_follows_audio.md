# Sep 22 2026, second pass — the picture follows the audio, and the first sentence has a shape

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Sep 22 2026, second pass — the picture follows the audio, and the
first sentence has a shape** (review:
[`docs/reviews/video_quality_pass_2026_09_22.md`](docs/reviews/video_quality_pass_2026_09_22.md);
guards `tests/test_scene_scheduler.py::TestLongFormSentenceSnap`,
`tests/test_fact_cards.py::{TestWindow,TestShortRenderStage}`,
`tests/test_video_commands.py::TestShortsPunchFrame`,
`tests/test_hook_short_motion.py`, `tests/test_spoken_open_shape_2026_09_22.py`).
The EN retention curve reads 0.74 at 3% elapsed and 0.48 at 5%: viewers
leave in a steady slide over seconds 6–60, before any chapter change,
and every render lever since August left that number where it was.
Rules that bind: **every long-form image is the episode's own** —
`gallery_blend_max_long` 3 / `min_overlap` 2 / `max_short` 2 (half the
images on a flagship were older library shots matched on one token),
and the `visual_reuse` getattr fallbacks must equal the dataclass. **Long-
form interior cuts snap to sentence ends** (`_snap_slots`, ±2.5 s; a hold
may run past the max by the tolerance, never under the min; chapter
boundaries never move) — the Whisper words are voice-only, shift them by
`voice_intro_delay`. **The gallery-retention prior reads `by_kind` ONLY
and matches prompt text**: pooled over kinds the 9:16 framing hint was
every show's top tag, and the tags-only match had scored 0 on all 1,646
images — the flywheel had never moved a rank; the Grok Imagine hint
strings are module constants so the join excludes exactly them.
`style_feedback_for` writes ONE audience-note sentence into the scene-
brief prompt only when a phrase sits ≥ 5 points from the kind's median on
≥ 10 videos (every flagship reads `None` on 09-22 — that is the design).
**Shorts fact cards + the punch frame** (tesla/spacex/FF, EN only; the
dubs are the control) are `None`-by-default keyword stages on
`_short_form_filter_graph`; a punch shifts the hook window to
1.2–4.25 s. **The hook-Short motion retry** (`engine/hook_short_motion.py`)
is one $0.28 clip with the cost gate before any request; a shortfall
records `hook_stills`, a b-roll-pool open records `broll_open`, and
neither is ever the A/B's `"stills"` label; `variant` rides into
`api/youtube_early_reach.json` for the per-arm read. **The spoken open
has a shape** (⚠️ audio, A/B-listen): `shows/prompts/_shared/hook_shape.txt`
on the three arm digest prompts (their WEAK/STRONG specimen hooks are
gone — Tesla's labelled the digit-bearing one WEAK), `engine.titles.
SPOKEN_HOOK_MAX_CHARS` = 150 as a regeneration GATE in run_show's
structural retry (never a truncation; it now runs on an over-long hook
for every daily show, SpaceX included, which had no validation config),
scored on `long_open_hold_5pct_arm` vs `_control` — `long_open_hold_5pct_en`
stays closed. Seven register entries dated 2026-09-22; readouts 10-13.
