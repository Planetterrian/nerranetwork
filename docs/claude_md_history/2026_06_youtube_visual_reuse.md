# YouTube visual reuse + chapter-aligned scenes (June 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### YouTube visual reuse + chapter-aligned scenes (June 2026)

Renders now reuse the imagery the network already paid for and time scene
changes editorially — full doc:
[`docs/youtube_visual_reuse.md`](docs/youtube_visual_reuse.md). **Everything
here is render/metadata-only (no audio → outside the landmine-#17 A/B
gate)**, config-gated with defaults **on** (`youtube:` knobs in
`shows/_defaults.yaml`: `gallery_blend_enabled` + per-aspect caps,
`chapter_aligned_scenes`, `long_form_thumbnail_from_scene` /
`thumbnail_variants`, `recap_reuse_scenes`, `gallery_fallback_enabled`,
`shorts_sentence_cuts`, `evergreen_broll`), and best-effort by contract —
any failure logs a warning and ships the exact legacy render.

- **Layers:** [`engine/gallery_library.py`](engine/gallery_library.py)
  (pull relevant historical scenes/b-roll from the `nerra-gallery` R2
  bucket via the committed manifest; cached, never raises) →
  [`engine/scene_scheduler.py`](engine/scene_scheduler.py) (pure planning:
  chapter-aligned scene schedules + sentence-snapped Shorts cuts) →
  `engine/video.py` render hooks (`scene_schedule` / `broll_clips` /
  `scene_change_times`; `None` = legacy byte-identical) →
  [`engine/visual_reuse.py`](engine/visual_reuse.py) (the thin composition
  layer run_show calls: `long_form_visual_plan`, `short_visual_extras`,
  `recap_scene_pool`, `fallback_scene_pool`).
- **Per episode:** long-form blends ≤8 library 16:9 scenes into the 4 fresh
  ones (ranked by hook/chapter-title overlap) and switches scenes on
  chapter boundaries; Shorts blend ≤4 library 9:16 scenes and snap scene
  cuts to sentence ends from the existing Whisper word transcript.
- **Sunday recaps** skip Grok Imagine entirely and reuse the week's gallery
  scenes when both aspects have ≥2 pooled images (below that: generate as
  usual). **Degraded days** (<2 fresh scenes) fall back to gallery-library
  scenes BEFORE the static cover; the degraded `::warning::` says which
  fallback shipped.
- **Thumbnails:** long-form thumbnail composites over the first fresh 16:9
  scene (cover fallback) + up to 2 variant composites from other scenes
  (`engine.publisher.generate_thumbnail_variants`), uploaded to the gallery
  bucket (`intended_use: thumbnail_variant` — invisible to the scene
  selector) for Studio "Test & Compare".
- **Evergreen b-roll:** ≤3 curated clips interleaved into the long-form
  slideshow; a clean no-op until the operator publishes
  `digests/<dir>/broll.json` via `scripts/build_broll_pool.py`.
- **Flywheel:** `scripts/build_gallery_retention.py` (nightly, after the
  analytics fetch + manifest rebuild) joins gallery images with per-video
  `averageViewPercentage` → `api/gallery_retention.json` (top/bottom image
  tags by mean retention, min 3 videos). Clean no-op until analytics data
  accrues.
- **Metrics:** `visual_mode` (chapter_schedule|uniform|cover|
  library_fallback|recap_pool), `scene_fresh_count`, `scene_library_count`,
  `broll_clips_used`, `thumbnail_base`, `thumbnail_variant_urls`. Drift
  guards: `tests/test_visual_reuse.py`.
