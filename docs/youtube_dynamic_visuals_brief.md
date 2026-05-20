# Brief — Make YouTube videos play, and make them dynamic

Hand this whole file to Claude Code (`claude` in the repo root), or paste
it as the prompt. Everything is self-contained.

## Background — what shipped, what broke

The first end-to-end YouTube run (Tesla ep452) succeeded at the *upload*
layer:

- Long-form: https://www.youtube.com/watch?v=AM43XgHNrtc
- Shorts:    https://www.youtube.com/watch?v=VL93dtY5fWU

Both uploaded as Unlisted, both have the AI-disclosure flag set, both
landed on the correct channel (Nerra Network). But:

- The **long-form** shows YouTube's "video can't play" / infinite spinner.
- The **Shorts** plays fine.
- Custom thumbnails 403'd on both with `"The authenticated user doesn't
  have permissions to upload and set custom video thumbnails"`. That is a
  YouTube account-gating problem, not our code — leave it for later.

The feedback from the operator: dynamic visuals for both formats, generic
enough to work across all 10 shows, conforming to YouTube's AI-content
guidance. The engine should not require any per-show artwork beyond what
we already have under `assets/covers/`.

## Root cause for the long-form playback failure

`engine/video.py:_long_form_cmd` uses `-loop 1` on a single image and
encodes with `-c:v libx264 -preset medium -crf 22 -profile:v high -level
4.1` — no `-g`, no `-keyint_min`, no `-force_key_frames`. With identical
input frames, x264 compresses the GOP almost arbitrarily long (the
encoder sees no scene change and rate control sees no benefit in
spending bits on a redundant IDR). The result is an MP4 that has one
keyframe at t=0 for a 573-second video. YouTube's transcoder either
produces a stream the HTML5 player can't seek into, or refuses to
publish the rendition entirely; either way the user sees "video can't
play".

The Shorts file (55 s) is short enough that the single starting
keyframe is still in the player's initial buffer, so it plays.

Fixing the keyframe spacing alone would unblock playback — but the
operator also wants real motion, so we'll do both at once.

## What to build

### 1. Replace the static-cover approach with a generic dynamic scene

The new visual recipe (same for every show, no per-show config):

- **Background:** the show cover (`assets/covers/{slug}.jpg` — already
  resolved by the caller) with a slow Ken Burns zoom (zoom from 1.00 to
  1.08 over the full audio duration, anchored at center). Use the
  `zoompan` filter; do not pre-resize the cover.
- **Background tint:** apply a 25% black overlay underneath the
  visualization strip so the waveform/spectrum reads against any cover.
- **Visualization (foreground):** burn in `showcqt` (constant-Q
  transform — the colorful "music visualizer bars" you see on Lofi Girl,
  Spotify Canvas, etc.) along the bottom 25% of the frame. `showcqt`
  produces inherently dynamic, frame-by-frame motion that pairs well
  with both speech and music, so it works for every show without tuning.
- **Branding watermark:** small "Nerra Network · AI-narrated" pill in
  the top-left, padding 24 px from each edge. Render this once with
  Pillow (write to `digests/<slug>/youtube_tmp/_brand_pill.png`) and
  overlay it.
- **AI-disclosure burn-in for the first 4 seconds:** centered text
  "AI-narrated content · Editorial by Nerra Network" rendered with
  `drawtext` and faded out via `enable='between(t,0,4)'` and an alpha
  expression. The persistent disclosure stays in the video description
  footer and the `containsSyntheticMedia` API flag — this is a UX hint,
  not the disclosure itself.

For the **Shorts** variant, use the same recipe at 1080×1920 with the
visualization strip at the vertical mid-band (rows 800–1320), the
brand pill in the top-right, and a larger first-3-seconds caption that
shows the hook headline (passed in as a kwarg) so it's readable on a
phone scroll. Skip the Ken Burns on the Shorts cover — the cover is
already cropped to fill, and 55 s of zoom looks frenetic.

### 2. Fix the keyframe spacing

Add to the `_VIDEO_ENCODE` profile **for both formats**:

```
-g 60                       # GOP = 2 seconds at 30 fps
-keyint_min 60              # don't let the encoder skip keyframes
-sc_threshold 0             # disable scene-cut detection (every frame
                            #   looks like a scene change with showcqt)
-force_key_frames "expr:gte(t,n_forced*2)"
                            # belt-and-suspenders: force IDR every 2 s
```

That alone makes the long-form playable. The motion from `zoompan` +
`showcqt` keeps x264's rate control honest so the keyframes actually
get inserted.

### 3. Keep the function signatures

`build_long_form_video(audio_path, cover_path, output_path, *, fps=30)`
and `build_short_video(audio_path, cover_path, output_path, *,
start_offset, duration, fps)` are called from
`run_show.py:_publish_youtube` (lines 2300+ on `main`). Don't change
those signatures — add a single optional kwarg if you need to pass the
hook headline through to the Shorts caption.

If you do add `hook: str | None = None` to `build_short_video`, update
the call site in `run_show.py` to thread the existing `hook` variable
through. Default to `None` (no caption) so existing tests stay
correct.

### 4. Tests

Update `tests/test_video_commands.py` to assert:

- Both ffmpeg commands include `-g 60`, `-keyint_min 60`,
  `-sc_threshold 0`, and `-force_key_frames`.
- The `_long_form_filter_graph()` output contains `zoompan`, `showcqt`,
  and an overlay chain (don't pin the exact filter string — just check
  for the presence of each filter name and the final `[v]` label).
- The `_short_form_filter_graph()` output contains `showcqt`, the
  expected vertical dimensions, and (when a hook is passed)
  `drawtext=text='...'` with `enable='between(t,0,3)'`.

Also verify the brand pill PNG is generated on first call (write to
the show's `digests/<slug>/youtube_tmp/` so it stays per-run and
gitignore-able) and reused if it already exists.

### 5. Local verification (before pushing)

These all need ffmpeg installed locally; the workflow already has it.

```
# Pick a recent existing audio file:
AUDIO=$(ls digests/tesla_shorts_time/*_Ep4*_*.mp3 | tail -1)
COVER=assets/covers/tesla.jpg
mkdir -p /tmp/yt_check

python3 -c "
from pathlib import Path
from engine.video import build_long_form_video, build_short_video
build_long_form_video(Path('$AUDIO'), Path('$COVER'),
                      Path('/tmp/yt_check/long.mp4'))
build_short_video(Path('$AUDIO'), Path('$COVER'),
                  Path('/tmp/yt_check/short.mp4'),
                  start_offset=15.0, duration=55.0,
                  hook='Tesla just unveiled a Virtual Queue for Superchargers.')
"

# Confirm playable structure: should print >= 5 keyframes for the long form,
# > 1 for the short, and ~30 fps for both.
ffprobe -v error -select_streams v:0 \
  -show_entries packet=pts_time,flags -of csv \
  /tmp/yt_check/long.mp4 | grep -c K
ffprobe -v error -show_entries stream=avg_frame_rate \
  -of default=noprint_wrappers=1:nokey=1 \
  /tmp/yt_check/long.mp4 /tmp/yt_check/short.mp4

# Sanity: open both in QuickTime / VLC and confirm:
#   - You can scrub past the first keyframe without the video freezing
#   - The bottom band has visibly moving spectrum bars
#   - The cover is slowly zooming on the long form
```

If any of those checks fail, fix and re-run before opening a PR.

## Files to touch

- `engine/video.py` — main changes (filter graphs, encoder args,
  optional hook kwarg, brand-pill helper)
- `tests/test_video_commands.py` — new assertions
- `run_show.py` — thread `hook` into `build_short_video` if you added
  the kwarg (search for the `_publish_youtube` block, ~line 2300)
- `engine/publisher.py` — if there is shared font/brand resolution,
  reuse it; otherwise add a small helper in `engine/video.py` to find
  a system bold font (DejaVuSans-Bold on the Linux runner is fine —
  there's no need for the Inter font from the original plan)

## Out of scope for this change

- Custom thumbnail upload (the 403 is a YouTube account-gating issue
  that resolves once the channel has a few uploads + watch time; leave
  the existing non-fatal warning path alone)
- Per-show visualization customization (the operator wants one recipe
  that works for every show)
- Subtitle/transcript burn-in beyond the first 3-4 second hint (large
  follow-up; we already generate full transcript files in
  `digests/<slug>/*_transcript.txt` so a future PR could add an
  optional `subtitles` kwarg)
- Audio-reactive cover transforms (would require pre-analysis of the
  audio's RMS curve; skip for now, showcqt already provides the
  audio-reactive visual)

## Out of scope, but worth knowing about for the description

The video description should already include the AI-disclosure footer
from `engine/video_metadata.py:build_long_form_metadata` /
`build_short_metadata`. Don't duplicate disclosure language inside the
video burn-in — keep the burn-in to a brief 3-4 second hint plus the
brand pill, so we don't fill the visual with text.

## Acceptance criteria

1. `pytest tests/test_video_commands.py` passes.
2. Locally rendered long-form MP4 plays in QuickTime / VLC and is
   seekable to any timestamp without freezing.
3. Locally rendered Shorts MP4 has the hook headline visible for the
   first 3 seconds and shows the spectrum visualization throughout.
4. After commit + push to `main`, manually trigger the `tesla` workflow
   from the GitHub Actions UI; the resulting upload at
   `https://www.youtube.com/watch?v=<new_id>` plays back fully on
   YouTube without the "video can't play" message.
5. The same recipe works for `fascinating_frontiers` — render its long
   form locally and confirm the visual is sensibly composed (no text
   overflow, the cover fills, the visualization is visible).
