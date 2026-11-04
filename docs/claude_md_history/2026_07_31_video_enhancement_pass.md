# Video enhancement pass — hook-first Shorts + render look v2 (July 31 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Video enhancement pass — hook-first Shorts + render look v2 (July 31 2026)

Operator-directed ("enhance the videos 200%+; one Short per channel is
the starting hook sequence"). Render/metadata-only — outside landmine
#17. Drift guards: `tests/test_video_commands.py`,
`tests/test_captions_ass.py`, `tests/test_scene_scheduler.py`,
`tests/test_shorts_selector.py::TestHookFirstWindows`,
`tests/test_shorts_ab.py::TestWindowParityDeconfound`,
`tests/test_youtube_feedback_loop.py`.

- **Hook-first Shorts:** Short #1 on every channel (EN/RU/FR) starts at
  the episode opening (= the hook since the cold-open pass); smart
  windows fill the rest (`engine.shorts_selector.hook_first_windows`,
  one implementation, three call sites). Every Short records
  `window="hook_open"|"qualified"|"filled"|"legacy_fallback"` in the
  video index → analytics, so hook-vs-smart is attributable. Config:
  `youtube.shorts_first_is_hook` (default true; **spacex pins false
  until the motion A/B reads out** — flipping mid-experiment would
  confound arm with window position).
- **Render look v2** (`RENDER_LOOK_VERSION = 2`, recorded per episode so
  analytics segment by visual era): network color grade
  (`_GRADE_CHAIN`: eq + vignette + gradfun, no grain) on every [bg];
  Shorts-only `unsharp`; long-form 0-4s fading hook title (autofit,
  h*0.42); long-form per-word ASS captions
  (`transcript_to_ass_full`, SRT fallback, `long_form_captions_path`
  metric); Shorts hook alpha-fade + end-card fade-in; active-word
  `\t` pop; 8-move episode-seeded Ken Burns at 1.06/1.09/1.12
  (CRC32-of-stem seed; `kb_extended=False` keeps byte-identical legacy
  for A/B-enrolled shows); accelerating open (<60s slots cap holds at
  8s); supersampled v2/v3 pills. The four items HELD for the motion-A/B
  verdict all shipped once the A/B was formally ENDED as unreadable
  (operator, 2026-08-14 — enrollment froze at n=4 via the merged spacex
  review PR #973; see `docs/experiments.yaml` `shorts-motion-ab-stalled`):
  progress bar (A3, earlier), Shorts transition split (A2 — vertical
  slideshows join on `_SHORTS_XFADE_S` 0.25 s vs long-form 0.6 s),
  punch-in easing (E1 — alternate Shorts segments front-load their Ken
  Burns travel, `ease="out"`), long-form closing beat (D2 — the final
  scene settles on a gentle centred push-in before the outro card).
  Drift guards: `tests/test_video_commands.py::TestUnheldRenderUpgrades`.
- **Learning loop:** title hints mined per-kind (Shorts retention no
  longer steers long-form titles) with fragment/dateline exemplars
  banned; gallery-retention flywheel CLOSED (bounded ±10 ranking prior
  in `gallery_library._rank` — overlap stays primary, missing report =
  legacy order); motion-A/B window-parity de-confound (top-two windows
  swap by episode parity on enrolled shows).
