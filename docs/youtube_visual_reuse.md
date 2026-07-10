# YouTube visual reuse + chapter-aligned scenes (June 2026)

Everything on this page is **render/metadata-only — no audio is touched, so
the whole system sits outside the landmine-#17 A/B gate.** Every path is
best-effort and config-gated (defaults **on**): any failure logs a warning
and degrades to the exact legacy render; a publish is never blocked.

## What / why

The network has paid Grok Imagine credits for every scene image it has ever
generated — they all live in the public `nerra-gallery` R2 bucket, indexed
by the committed `site/data/gallery-manifest.json`. Until this pass the
pipeline treated that archive as write-only: every render used only the 4
fresh images per aspect, scene changes ran on a uniform timer (long-form) or
a flat 7 s grid (Shorts), Sunday recaps regenerated imagery for stories
already illustrated during the week, a Grok Imagine outage degraded straight
to the static cover, and every long-form thumbnail was the same show cover.

Layers (bottom-up):

| Layer | Module | Role |
|---|---|---|
| Selection | `engine/gallery_library.py` | Pull relevant historical scenes/b-roll down from R2 (manifest-driven, cached, never raises) |
| Planning | `engine/scene_scheduler.py` | Chapter-aligned `[(scene, hold_s), …]` schedules + sentence-snapped Shorts cut times (pure logic) |
| Rendering | `engine/video.py` | `build_long_form_video(scene_schedule=, broll_clips=)`, `build_short_video(scene_change_times=)` — `None` = legacy byte-identical |
| Composition | `engine/visual_reuse.py` | The thin layer run_show calls: honors the config gates, assembles pools/plans, returns legacy shapes on any failure |
| Wiring | `run_show.py:_publish_youtube` | One call per surface + metrics |

## Behaviours (all defaults on)

- **Gallery blending** — each long-form render blends up to
  `gallery_blend_max_long` (8) historical 16:9 scenes into the 4 fresh ones,
  ranked by token overlap with the episode hook + chapter titles; each Short
  blends up to `gallery_blend_max_short` (4) 9:16 scenes ranked against its
  hook. Zero new image-generation cost.
- **Chapter-aligned scene schedule** — scene switches land on
  `chapters_ep<NNN>.json` boundaries (subdivided into 6–15 s holds), with
  per-chapter scene choice scored by title↔prompt overlap (fresh scenes win
  ties; reuse penalised for variety). `<2` usable chapters → uniform plan
  identical to legacy. **Slot cap:** plans are clamped to
  `_MAX_SLIDESHOW_SLOTS` (24) so a long episode cannot ask ffmpeg for 60–70+
  xfade inputs (Tesla Ep537 timeout class); holds stretch instead.
- **Sentence-snapped Shorts cuts** — scene changes snap to sentence-ending
  words from the faster-whisper word-level transcript (already generated for
  captions — no new transcription cost) instead of the flat 7 s grid.
- **Sunday recap reuse** — recap episodes pull the week's gallery scenes
  (both aspects, `collect_week_scenes`) and **skip Grok Imagine generation
  entirely** when both aspects have ≥2 pooled images; below that they
  generate as on any other day. The recap re-tells the week's stories, so
  its imagery already exists.
- **Degraded fallback** — when scene generation yields <2 usable images
  (previously: straight to the static cover), the show's historical gallery
  scenes ship instead; the cover remains the last resort (and the degraded
  `::warning::` annotation now says which fallback was used). Shows with no
  gallery history (Pexels-only) degrade to the cover exactly as before.
- **Scene-based thumbnails + variants** — the long-form thumbnail composites
  over the episode's first fresh 16:9 scene (cover fallback), and up to
  `thumbnail_variants` (2) additional composites are rendered from OTHER
  scenes (same hook text/autofit) and uploaded to the gallery R2 bucket
  (`intended_use: thumbnail_variant`) for the operator's Studio "Test &
  Compare" A/B. URLs land in the episode metrics. **July 2026:** those
  text-burned variants are **excluded from the public gallery manifest**
  (and filtered client-side) so visitors only see clean Grok Imagine
  scenes — variants remain in R2 for Studio.
- **Evergreen b-roll** — up to 3 curated silent clips interleave into the
  long-form slideshow. A clean no-op until the operator publishes a
  `digests/<dir>/broll.json` pool (below).

## Config knobs (`youtube:` block; network defaults in `shows/_defaults.yaml`)

```yaml
youtube:
  gallery_blend_enabled: true      # blend historical gallery scenes
  gallery_blend_max_long: 8        # 16:9 library scenes per long-form
  gallery_blend_max_short: 4       # 9:16 library scenes per Short
  chapter_aligned_scenes: true     # scene switches on chapter boundaries
  long_form_thumbnail_from_scene: true
  thumbnail_variants: 2            # extra Test & Compare composites
  recap_reuse_scenes: true         # Sunday recap skips generation
  gallery_fallback_enabled: true   # library before static cover
  shorts_sentence_cuts: true       # sentence-snapped Shorts scene cuts
  evergreen_broll: true            # no-op until broll.json exists
```

Disable per show by flipping any flag to `false` in the show YAML — each
gate is independent and `false` restores that surface's legacy behaviour
byte-for-byte. All fields are declared on `YouTubeConfig`
(`engine/config.py`) — remember the silent-config-drop landmine: never add a
`youtube:` YAML key without a matching dataclass field.

## Operator b-roll workflow

1. Recover Grok Video clips soon after a run (result URLs are temporary):
   `GROK_API_KEY=... python scripts/recover_grok_video.py --out-dir recovered/`
2. Curate locally — keep only evergreen footage (generic factory shots,
   rockets on the pad; nothing dated like a headline overlay).
3. Publish: `python scripts/build_broll_pool.py --show tesla clip1.mp4 clip2.mp4`
   — uploads to the gallery R2 bucket under `broll/<slug>/` and commits ONLY
   the small `digests/<dir>/broll.json` index (media in git is landmine #1).

Renders pick the pool up automatically (`evergreen_broll: true`), capped at
3 clips per episode so accents stay accents.

## Data flywheel: image ↔ retention join

`scripts/build_gallery_retention.py` (nightly, after the analytics fetch +
manifest rebuild) joins gallery images with per-video
`averageViewPercentage` from `api/youtube_stats.json` into
`api/gallery_retention.json`: per show, per image `{video_id, retention,
episode_id, tags}` plus top/bottom tags by mean retention (min 3 videos per
tag). Join key: the sidecar's `youtube_video_id` when set, else
`(show_slug, episode, kind)` — `segment_card`→long, `social`→short. Clean
no-op (empty `shows` map) until analytics data accrues (the token re-auth in
`docs/youtube_feedback_loop.md`).

## Observability (per-episode metrics)

- `visual_mode` — `chapter_schedule | uniform | cover | library_fallback | recap_pool`
- `scene_fresh_count` / `scene_library_count` — fresh vs recycled imagery
- `broll_clips_used`
- `thumbnail_base` (`scene | cover`), `thumbnail_variant_urls`
- `visual_fallback` (`library | cover`, only on degraded episodes)

Drift guards: `tests/test_visual_reuse.py` (plus `tests/test_gallery_library.py`,
`tests/test_scene_scheduler.py`, and the schedule/cut paths in
`tests/test_video_commands.py`).
