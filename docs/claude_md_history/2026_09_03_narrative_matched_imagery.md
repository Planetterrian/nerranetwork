# Narrative-matched imagery + delivered resolution (Sep 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Narrative-matched imagery + delivered resolution (Sep 2026)

Operator complaints about video quality traced to two silent defaults:
every Grok Imagine prompt led with a static `image_queries` phrase (so
each Tesla episode shipped the same four pictures) and the library blend
padded the slideshow with older images ranked by weak token overlap.
Now `engine/scene_briefs.py` writes one photographable scene per STORY
(one Grok text call; deterministic fallback) and those briefs LEAD the
prompts (`build_image_prompts(scene_briefs=)`); one fresh 16:9 scene
per story (`scenes_per_episode`) + `short_scenes_per_episode` 9:16;
Shorts open on the scene matching their own window text
(`short_visual_extras(fresh_scene_context=)`). **The image endpoint
ignores `size`** (Sep 3 2026 — every one of 7,500+ committed sidecars
is 1280x720 whatever was requested): the request carries the documented
`aspect_ratio` + `resolution: "2k"` (`engine/grok_imagine.py`, `size`
only as the ladder's fallback) and the delivered width is a per-episode
metric (`grok_image_px_max`) — read THAT, never the request. **Library
overlap is counted on salient tokens** (`gallery_library._common_tokens`:
document frequency > 20% dropped from both sides — "tesla"/"optimus"/
"cinematic" sit in ~100% of the library and matched every image).
**Chapter title cards are a fit gate on `engine.titles.CHAPTER_CARD_MAX`,
never a clip.** Register: `scene-briefs-narrative-imagery`,
`image-source-2k-and-story-matched-shorts`, `video-quality-round-3`
(readouts 2026-09-23). Guards: `tests/test_scene_briefs.py`,
`tests/test_video_commands.py::TestChapterTitleCards`.
