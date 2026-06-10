# YouTube Pipeline Review — Shorts + Long-Form Quality (June 10, 2026)

Review of the full video pipeline (engine/video.py, shorts_selector,
captions, grok_imagine/visual_assets, video_metadata, youtube.py,
thumbnails/end-cards, per-show YAML) for current shows (Tesla + MAB full,
FF + MIT Shorts-only, FP/PR on @NerraRU) and future shows. Drift guards:
`tests/test_youtube_quality_pass.py`.

## Root-cause discovery: the silent config-drop class

`_build_nested` instantiates config dataclasses and silently discarded any
YAML key the dataclass didn't declare. Three live casualties found:

1. **`shorts_min_score_threshold` (P0, the headline bug)** — Tesla's May
   retune set 3.5 so the smart Shorts selector would actually pick
   engaging beats for measured/narrative content. The field was never
   declared on `YouTubeConfig`, so every episode ran at the 5.0 default —
   Ep505's "best score 3.0 below threshold 5.0 → legacy start" fallback
   was this bug. ALSO: the single-Short resolver
   (`engine/youtube_shorts.py`) never passed the threshold to
   `pick_engaging_window` at all. Both fixed; Tesla Shorts should start
   at engaging beats from the next episode.
2. **Five `NewsletterConfig` fields** (`requires_financial_disclaimer`,
   `emoji`, `short_label`, `length_target_words`,
   `newsletter_start_date`) — set in YAMLs, read via `getattr` on the
   dataclass, silently defaulted. Most serious:
   **`requires_financial_disclaimer` was always False**, so the FP and
   MIT newsletters' YAML-requested financial disclaimer depended entirely
   on the template path that happens to read the raw YAML dict. Declared
   now; both access styles agree.
3. **`min_audio_duration: 180`** sat inside `_defaults.yaml`'s `audio:`
   block but is a top-level `ShowConfig` field — the network-wide
   too-short-audio guard was dead for all 11 shows that didn't set it
   top-level (only Tesla did). Moved to top level.

**Class fix:** `_build_nested` now logs a WARNING naming any unknown key,
and a CI guard asserts every `youtube:` key used in any show YAML is a
declared field.

## Viewer-facing improvements implemented

- **Slideshow scene cycling (long-form)**: the May 12 cost retune (4
  images/aspect) left each Grok-Imagine image on screen for 2–3 minutes
  (Ep505: 673 s / 4 scenes = 168 s/image) — visually static. Scenes now
  CYCLE in rotation so no image holds longer than ~25 s, restoring visual
  rhythm at **zero** additional image cost (the retune's spend decision
  stands).
- **RU-channel observability**: `channel: ru` configured with
  `YOUTUBE_REFRESH_TOKEN_RU` missing now logs an explicit WARNING instead
  of an INFO "skipping" (FP/PR uploads had silently no-oped for days).
- **Captions observability**: each Short records
  `shorts_captions_path: ass | srt_fallback` in metrics so the operator
  can see whether the TikTok-style per-word highlighting actually shipped.

## Reviewed and rejected (with reasons)

- **"Add `-b:v 5M` bitrate + lower CRF"** — rejected: the long-form is a
  mostly-static slideshow; CRF 22 constant-quality already preserves it
  well and a bitrate floor would inflate the 140 MB uploads (and upload
  time) for negligible transcode gain. Revisit only if motion-heavy
  content is added.
- **"Buy more Grok images (16/episode) to fix cadence"** — rejected in
  favour of cycling (above): same visual effect, $0 instead of doubling
  image spend the operator deliberately halved.
- **"Per-scene contexts skipped for long-form"** — false: both aspects go
  through `_run_grok_path`, which passes `per_scene_contexts`.
- **"`-preset slow`"** — deferred: 2–3× encode time on a step already
  taking ~6 min, for marginal source-quality gain through YouTube's
  re-encode. Benchmark someday; not now.
- **Shorts duration assertion, hashtag-count knob, end-card context
  text, thumbnail font-size trend metric** — P2s documented here for a
  future pass; none affect current output correctness.

## Future shows

`scaffold_show.py` generates no `youtube:` block — a new show is
YouTube-dark until the operator hand-copies one. Recommended (not
implemented): scaffold a disabled-but-complete block
(`enabled: false`, `image_queries` placeholder, `shorts_start_mode:
smart`, category) so enabling is one flag flip. The
`test_every_show_yaml_has_image_queries` guard already blocks shows from
going video-live without curated queries.
