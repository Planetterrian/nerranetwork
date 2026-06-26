# YouTube Growth Rollout — June 2026 (200k quota)

## Context

The YouTube Data API quota for the @NerraNetwork project was raised
**10,000 → 200,000 units/day**. The pipeline had been built defensively around
the 10k cap (landmine #20): only 7 of 13 shows published, several in degraded
modes, and `shorts_per_episode` was pinned at 1. The cap is no longer the
constraint — so this rollout spends the headroom on **reach + retention
quality**, not raw volume.

Two findings from the 2025-2026 best-practice review shaped every decision:

1. **YouTube's "inauthentic content" policy** (renamed July 2025, enforcement
   expanded Jan 2026) demonetises templated, no-variation mass posting and
   **pure static-image slideshows**. The policy targets *mass-produced sameness*
   — not a network of editorially distinct shows with unique daily scripts.
2. **Motion beats stills** (+15-30% retention), **Shorts are the discovery
   engine** that funnels to long-form subscribers, and packaging (title +
   thumbnail) is now gated on retention ("Quality CTR") — honest packaging that
   the episode pays off wins over clickbait.

**Audio-safety:** nothing here changes shipped audio. Titles are separate
metadata (the spoken hook is untouched), video clips are visual, quota is
config. The landmine #17 A/B-listen gate does **not** apply to these changes.

## What shipped

### 1. Configurable quota budget (`engine/youtube_quota.py`)
- `DEFAULT_DAILY_QUOTA` 10k → **200k**, env-overridable: `YOUTUBE_DAILY_QUOTA`
  (global) and `YOUTUBE_DAILY_QUOTA_EN` / `YOUTUBE_DAILY_QUOTA_RU` (per-channel,
  win over global) via `resolve_daily_quota()`. Works whether the grant is one
  shared project pool or EN-only.
- Preflight (`scripts/youtube_quota_preflight.py`) now also emits a soft
  **authenticity cadence warning** when a channel projects more than
  `SAFE_DAILY_UPLOADS_PER_CHANNEL` (default 30, env `YOUTUBE_SAFE_DAILY_UPLOADS`)
  uploads/day — cadence, not units, is the binding risk now.

### 2. Full-network enablement (all 13 shows)
- Flipped Fascinating Frontiers + Modern Investing back to **long-form**;
  First Principles now also publishes **Shorts**.
- Enabled the 6 previously-disabled shows (env_intel, planetterrian, omni_view,
  models_agents, models_agents_beginners, unintended_consequences) with
  `image_provider: grok`.
- EN steady state: **~24 uploads/day, ~45k units** (vs 200k budget). RU
  (finansy_prosto, privet_russian): 4 uploads/day, 7.6k units.

### 3. LLM-optimized titles (`engine/youtube_titles.py`)
- A click-tuned long-form title generated via one cheap Grok call (front-loaded
  keywords, honest curiosity gap), **separate from the spoken hook**. Prompt:
  `shows/prompts/_shared/youtube_title.txt`. Falls back to the hook-based SEO
  title on any failure. Up to 3 candidates are stashed in the run result for
  A/B "Test & Compare". Toggle: `youtube.optimized_titles` (default true).
- Shorts keep their **distinct per-window headlines** (multi-Short distinctness;
  YouTube's native A/B is long-form-only anyway).

### 4. Hybrid Grok video clips — Tesla + SpaceX pilot
- `engine/grok_video_clips.py`: a few SHORT clips (3-6s) generated via
  text-to-video, interleaved with the still slideshow by
  `engine.video.build_long_form_video` (`_hybrid_*` graph). ~$1/episode (vs
  ~$50 for the full-episode `grok_video` path, which stays disabled).
- Best-effort with a wall-clock budget; falls back to all-stills on any
  failure. Config: `youtube.video_clips_enabled/_count/_seconds/_resolution`
  (default off). Enabled only on `tesla` + `spacex`.

### 5. Motion + multi-Shorts
- Slideshow still-hold cap **25 → 15s** (`_MAX_SCENE_HOLD_S`) so stills cycle
  more often (free rhythm; addresses the static-slideshow penalty network-wide).
- Tesla + SpaceX bumped to **2 Shorts/episode** (distinct discovery surfaces).
- Long-form descriptions already carry entity hashtags; Shorts end-card CTA
  already ships network-wide; chapters ship on every long-form.

## Operator one-time tasks (not code)

1. **Confirm the quota scope** and set the env budget if the grant is EN-only
   (`YOUTUBE_DAILY_QUOTA_EN=200000`); otherwise the 200k default already applies.
2. **Create + flag the podcast playlist** in YouTube Studio for each
   newly-enabled show (landmine #15 — the Data API can't set the "podcast" flag).
   Uploads publish without it (warned), but won't surface under YouTube Podcasts.
3. **Enable Title/Thumbnail "Test & Compare"** on long-form episodes (Studio,
   desktop). The pipeline supplies up to 3 title candidates in the run result;
   the operator picks them into a test. (No reliable Data API endpoint for this.)
4. **Watch the clip pilot**: review Tesla/SpaceX retention + cost for ~1 week
   before flipping `video_clips_enabled` on more shows. Each show opts in with
   that one YAML flag.

## Deferred (rationale)

- **Long-form vs Shorts staggered posting times.** Research says they peak at
  different times of day, but the pipeline generates+uploads both in one per-show
  run. Decoupling upload time is a scheduler re-architecture; shows are already
  staggered across the day via the :07/:37 crons + the Cloudflare scheduler
  (landmine #24). Revisit if analytics show a clear timing lift.
- **Image-to-video clips** (vs text-to-video) for pixel-coherence with the
  stills — needs a hosted URL for each still; deferred until the clip pilot
  proves the retention win.
- **Crossfade transitions** between scenes — riskier filter-graph change against
  the large `test_video_commands` guard set; the lower hold cap + clips deliver
  most of the motion benefit.

## Drift guards

`tests/test_youtube_quota.py`, `tests/test_schedule.py`,
`tests/test_youtube_quality_pass.py`, `tests/test_config.py`,
`tests/test_video_commands.py`, `tests/test_slideshow_scene_cadence.py`,
`tests/test_youtube_titles.py`, `tests/test_grok_video_clips.py`,
`tests/test_gallery_render.py`, `tests/test_unintended_consequences.py`.
