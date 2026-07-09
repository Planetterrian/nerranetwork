# YouTube visual + description pass (July 9, 2026)

Operator ask: gallery images all have text overlaid and aren't useful;
YouTube keyframes look like a dark image behind white text; want videos,
Shorts, and descriptions that are beautiful and compelling while keeping
the key elements already built (UTM links, chapters, disclosure, hashtags,
show page, performance title loop).

**Scope:** render / metadata / gallery only — **no audio / TTS / podcast
prompts** (outside landmine #17).

## Root causes found

1. **Thumbnail compositor** (`engine/publisher.generate_episode_thumbnail`)
   full-frame `Brightness(0.55)` + centred white hook → every keyframe
   read as a title card, not photography.
2. **Gallery pollution** — text-burned `thumbnail_variant` composites were
   uploaded to the public `nerra-gallery` bucket and surfaced newest-first
   in `gallery-manifest.json` (~7% of images, often the ones visitors see
   first).
3. **Grok Imagine prompts** appended the full episode headline after
   `depicting: …`, which the model painted as on-image chyron text despite
   a soft "no text" hint.
4. **Shorts titles** used `text[:80]` mid-word truncation from the smart
   selector's `opening_text`.
5. **Descriptions** buried entity hashtags after body/chapters (below the
   mobile "Show more" fold); intro template was bland.
6. **Performance iteration** — code path is live
   (`engine/youtube_titles` + `scripts/update_youtube_performance.py`) but
   **data-dormant** until OAuth is re-authed with `yt-analytics.readonly`
   and a few weeks of retention accrue. No code change required for the
   loop itself; operator action noted below.

## Shipped

| Change | Why |
|---|---|
| Image-first thumbnail: bottom gradient scrim + lower-third hook (no full darken) | Keyframes stay photographic and enticing |
| Public gallery excludes `thumbnail_variant` / `thumbnail` / `youtube_thumbnail` (manifest builder + JS defense) | Gallery shows clean Grok scenes only |
| Grok prompts: `visual subject:` short phrase + hard ZERO-text cue (no `depicting:` dump) | Fewer on-image text overlays in new scenes |
| Shorts end card prefers a clean scene still over the text-burned long-form thumb | End card isn't a slide-of-a-slide |
| Word-boundary Shorts `opening_text` trim | Titles don't cut mid-word |
| Hashtags moved above the fold (long-form + Shorts); stronger description intro | Discovery tags + compelling copy visible without "Show more" |

## Operator follow-ups (not code)

1. **Re-auth YouTube OAuth** with `yt-analytics.readonly` so
   `youtube_performance.json` / title hints start accruing (see
   [`docs/youtube_feedback_loop.md`](../youtube_feedback_loop.md)).
2. **Rebuild the gallery manifest** once (nightly workflow or
   `python scripts/build_gallery_manifest.py`) so existing
   `thumbnail_variant` sidecars drop from the public page. R2 objects
   can stay for Studio A/B; they just won't list publicly.
3. Spot-check the next 2–3 YouTube publishes (Tesla + one Shorts-heavy
   show) for thumbnail look + description fold.

## Drift guards

- `tests/test_thumbnail_autofit.py` — bright top-of-frame + 160-char cap
- `tests/test_grok_imagine.py` — no `depicting:`, ZERO-text, subject compress
- `tests/test_build_gallery_manifest.py` — excludes thumbnail variants
- `tests/test_youtube.py` — hashtags before show-page line
- `tests/test_shorts_selector.py` — word-boundary trim

## Predictions (next review scores)

1. New gallery uploads after merge are ≥95% `segment_card`/`social` (no
   new `thumbnail_variant` in the public manifest).
2. Fresh Grok scenes show on-image text in ≤1 of 10 spot-checks (was
   near-universal when headlines were dumped).
3. Long-form / Shorts thumbnails keep mean top-band brightness clearly
   above the old 0.55-darkened look (visual A/B on next publish).
