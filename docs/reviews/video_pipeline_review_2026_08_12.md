# Video + YouTube pipeline deep review — 2026-08-12

Operator ask: review the video and YouTube pipelines in detail for
performance, viewing experience, and audience reach, and ship
improvements. Three parallel review tracks (render engine / Shorts
experience / reach + metadata + feedback loop) produced ~60 findings;
this doc records what shipped (PR #992 follow-up branch) and what is
deliberately proposed-only. Drift guards for everything shipped live in
the tests named per item.

## Context from the data (2026-08-12)

- RU Shorts remain the network's engine: 31.9k views/14d (median 272
  per Short, 26 subs) vs EN 6.2k / FR 70.
- Smart-selector windows retain far better than hook-open windows on
  Shorts: `qualified` median retention 77.5% (n=11) vs `hook_open`
  43.2% (n=94) vs `filled` 45.4% (n=56). Confounded by channel mix and
  stagger slots — worth a dashboard cut before acting on
  `shorts_first_is_hook`.
- The Shorts motion A/B is still collecting (4 treatment / 12 control
  of 14 per arm), so the held render items (transition split, progress
  bar, punch-ins, long-form ending beat) STAY HELD.
- Nightly maintenance failed Aug 10 + 11: a hand-edited
  `age_of_ai_podcast.rss` lost its closing tags, flipping the
  RSS-integrity card to fail, and `generate_dashboard.py` exits 1 on
  any failing card — which killed the job after the analytics fetches
  and before the commit. Two nights of analytics were computed and
  discarded; the adaptive policy steered on 3-day-old data. Fixed
  (feed repaired in #991; the dashboard step is loud-but-non-fatal
  now; the policy gained its own staleness freeze).

## Shipped — audience reach

| Fix | Why it matters | Guard |
|---|---|---|
| Chapters actually ship in long-form descriptions | 0 of 1,333 committed chapter files start at 0:00 (they start after the music intro), and the formatter returned `""` unless the first stamp was 0:00 — so no episode EVER shipped seek-bar chapters. A synthetic localized `0:00 Intro` line is prepended (clamped when chapter 1 starts <10s). | `tests/test_youtube.py` |
| Description tail reserved | The CC BY footage credit (a license obligation) and the AI disclosure sat LAST in a flat list clipped from the tail — a long digest body silently deleted them. Head clips to the room the tail leaves. | assembly in `engine/video_metadata.py` |
| Shorts #2/#3 hashtags/tags from the episode hook | Window excerpts often carry no proper nouns; the clickable 3-tag row above the Shorts title collapsed to `#Shorts #podcast` on half the network's Shorts. New `topic_hook` param. | `tests/test_shorts_hashtags.py` |
| Hashtag extraction fixes | Uncapped Title-Case runs made one unsearchable mega-tag that then blocked its own constituents; character-substring dedup ate `#AI` whenever `#Ukraine` was picked (`"ai" in "ukraine"`); stopword gaps (`We/New/Will/Says/...`). | `tests/test_shorts_hashtags.py::TestAug2026ExtractionFixes` |
| Shorts-only days keep the "▶ Full episode" line | The description's strongest funnel placement disappeared exactly on the tiers that have nothing but Shorts; now falls back to the funnel-tagged show destination (the comment path already did). | `engine/video_metadata.py` |
| EN window-Short fragment titles repaired | When the title bundle has no SHORTn line, `headline_from_excerpt("en")` turns the mid-sentence excerpt into a complete headline before the legacy fallback (both dub channels already did this; EN never did). | best-effort, `""` keeps legacy |
| Over-length LLM titles clipped, not dropped | 3 near-miss candidates (asked ≤90, got ~104) used to mean an empty bundle → silent hook-title fallback. All title clipping now routes through `engine.titles.clip_words` (incl. the dub `_word_trim`). | `tests/test_youtube_titles.py` |
| Shorts out of podcast playlists | Shorts were inserted into `podcast_playlist_id` — the playlist YouTube Music ingests as the show's podcast — 1-3 broken "episodes" per real one. New optional `shorts_playlist_id`; unset = no playlist. | config comment |
| Bogus `status.publishToSubscriptions` removed | Not a real API field (silently ignored); `notifySubscribers` (query param, default true) is the actual control and its default is the intent. | — |

## Shipped — viewing experience

| Fix | Why it matters | Guard |
|---|---|---|
| Captions burn in ON TOP of the end card | The opaque CTA card was overlaid over the burned captions, so the last ~3 s of every Short played speech with its text hidden (8.6% of a 35 s Short, always the final thought). | `tests/test_video_commands.py` layering tests |
| Caption card holds between words | One ASS Dialogue per word left every inter-word gap dark — Whisper leaves 150-600 ms at breaths, so the card flickered off/on 10-20×/Short. Cues extend to the next word's start (cap 0.6 s); the min-duration floor can no longer overlap the successor (libass two-line jump). | `tests/test_captions_ass.py` |
| Accelerating open survives the slot cap | `_cap_slots` merged the smallest pair first = the 7.5-8 s D1 opening slots by construction; Ep537-shape shipped a 40 s first hold. In-open pairs are last-resort merges; the 8-slot fast open now survives intact. | `tests/test_scene_scheduler.py::…spares_the_accelerating_open` |
| Shorts cover fallback is never a frozen frame | The degraded path shipped a static bicubic-upscaled JPEG for 35 s; now lanczos 2× prescale + slow centred push-in, mirroring long-form. | `tests/test_video_commands.py` |
| Shorts b-roll clamps to 6 s accents | One long stock master could consume the whole Short (33 s of continuous stock, zero paid imagery). | — |
| dissolve/fadeblack out of the xfade rotation | Per-pixel noise burst on stills / mid-episode dip-to-black that reads as a glitch. Replaced with photographic-safe moves. | — |
| Ken Burns frame-count round + p-clamp | `int()` truncation vs the trim duration made zoompan's progress overshoot 1.0 on tail frames — clamped pans exactly during crossfades. | — |
| Outro card geometry | QR block overlapped the right site screenshot; the FR scan label rendered 46 px off-frame. Verified on a real render. | `tests/test_site_showcase.py` |

## Shipped — pipeline integrity / performance

- **Dead fallbacks live again**: both "fall back to cover" handlers
  caught only `CalledProcessError` while `_run_ffmpeg` raises
  `RuntimeError` — a slideshow failure lost the whole long-form (and
  video-podcast episode) or Short for the day.
- **run_show's ~80-line metrics tail was inside an except handler**
  (ran only if the quota estimator raised — never). `shorts_ab` — the
  counter the motion-A/B spend report reads — and the
  `grok_slideshow_degraded` `::warning::` were dead. Restored;
  duplicate keys pipeline.py already records were deleted.
- **`caption_track_uploaded` honesty**: the uploader returns False on
  its documented 403 path without raising; success was recorded
  unconditionally while videos shipped captionless.
- **Metric key mismatches**: `shorts_caption_mode` (was
  `shorts_captions_path`, read by nothing), `shorts_end_card_generated`
  (read but never written).
- **Scheduled comments posted 2-3× per Short**: the multilingual
  matrix (max-parallel 3) ran a GLOBAL sweep per job. Sweeps are now
  show-scoped in the matrix (`--show`), attempts-bounded (drop after 3
  failures instead of 7 days of quota-charged retries), and stagger
  fallback times extend the tail instead of landing ~18 h out.
- **Stage-1 intermediates**: `.part` + atomic replace (a truncated
  file from a killed run used to satisfy the idempotency check and
  silently truncate the delivered episode); hybrid path now uses the
  FAST encode profile; `+faststart` dropped from intermediates (full
  extra pass over ~150 MB per render); hybrid slot count clamps to
  `_MAX_SLIDESHOW_SLOTS`; fused graph pins `format=yuv420p`.
- **Feedback loop**: per-channel `title_hint_<ch>` (FR analytics were
  mined into nothing; every non-RU channel read the English hint);
  hints >21d ignored; policy freezes loudly on >3d-old stats (a dead
  fetch could flip a tier on day 2 and hold it); weekly long-form
  probes shard by `sha1(channel/slug) % 7` instead of all landing on
  the same Monday.
- **Selector safety**: a failed ffprobe (`audio_duration=0`) silently
  disabled both end-of-audio guards — windows could start 10 s before
  the file ends; duration now recovers from the transcript, and the
  candidate index is carried instead of dict-equality `.index()`
  (duplicate filler segments scored the wrong window; O(n²)).

## Round 2 — shipped 2026-08-14 (from the list below)

Items 1, 2, 4 (in full: guarded tags + caption tracks + Short
thumbnails + Shorts out of dub podcast playlists), 6 (traffic sources,
search terms, retention curves for top recent longs), 7 (shorts-count
hysteresis; retention gating still open), 8 (FR channel + policy-driven
dub Shorts count + caption-track cost), and 9 (transport-error retry).
The slot cap rose 24 → 36 on the back of item 1, with
`gallery_blend_max_long` 16 → 24 so the pool covers the deeper plan.
Performance context at ship time: RU Shorts median retention 43→54%
WoW, FR Shorts 46→71% (small n), EN Shorts flat ~44-46%; the motion
A/B is STALLED (treatment frozen at n=4 — `shorts_ab_enabled: false`
landed via the merged spacex review PR #973) and is now a `decide`
entry in the experiments register.

## Proposed — NOT shipped (each needs its own decision)

1. **ffmpeg input dedup for cycled slideshows** (render #12): one
   `-loop 1` input per SLOT means the same 4-8 files open 24×. Deduping
   by path + `split=` fan-out would let `_MAX_SLIDESHOW_SLOTS` rise to
   48+ and retire the 86 s post-cap tail holds entirely. Highest-value
   remaining render change; medium-risk graph surgery.
2. **Duration-adaptive Ken Burns amplitude** (render #9): fixed
   amplitude means an 86 s hold moves at 0.1%/s (sub-perceptual). Gate
   on `kb_extended` to keep the A/B control arm pinned. Do after (1),
   which removes most long holds.
3. **Hybrid b-roll path modernization** (render #3b/3c): no crossfades
   (bare concat) and no single-pass fusion. Dormant until a show
   publishes `broll.json` — modernize before enabling b-roll anywhere.
4. **Dub metadata parity** (reach #5/6/7): RU/FR uploads ship raw
   English YAML keywords as tags (no 500-char guard — modern_investing
   is 40 chars from a 400 on every dub upload), no caption track
   (Whisper output exists in-process and is discarded — CC +
   auto-translate + caption search indexing for free), no custom Short
   thumbnails. Biggest remaining reach item; needs `_build_tags`
   promotion + translated tag plumbing.
5. **`recordingDetails.recordingDate` + `localizations` on
   videos.insert** (reach #9): freshness signal for daily news content;
   RU/FR localized title+description on EN videos (the EN channel's
   geography report shows where that pays).
6. **Analytics dimensions not yet queried** (reach #14):
   `insightTrafficSourceType/Detail` (the literal search queries
   reaching each show — free tag/title input),
   `elapsedVideoTimeRatio` retention curves (measures the hook-first
   directive instead of asserting it), `sharingService`,
   `subscribedStatus`.
7. **Policy uses retention/subscribers, not just views** (reach #15);
   **Shorts-count hysteresis** (reach #16 — the 20 vpd 3-Short band
   boundary can oscillate nightly).
8. **Quota estimator blind spots** (reach #19): FR channel invisible
   (`dub_languages` never read), RU dub Shorts hardcoded at 1,
   comment inserts (~50 units) uncounted.
9. **Upload retry predicate** (reach #20): retries only `HttpError`;
   a `ConnectionResetError` mid-resumable-upload costs the day's
   long-form.
10. **Window-type retention cut on the dashboard**: `qualified`
    windows retain ~34 points better than `hook_open` — if it holds at
    n>50 with channel controls, revisit `shorts_first_is_hook`
    (currently default-true everywhere except spacex).

## Process notes

- Main's CI was red before this branch: `test_workflow_is_scheduled`
  contradicted the operator's Aug 10 no-scheduled-publish rule
  (commit `ffb62541`) — the guard now pins dispatch-only. A second
  pre-existing failure (FR `deferred` status rows missing `channel`,
  written by `publish_lang_dubs._record_status_row` and committed by
  that morning's sweep) was masked by `maxfail=1`.
- `pytest -x`/`maxfail=1` hid the second failure behind the first for
  two days — worth considering `--maxfail=5` in CI so one red guard
  can't mask others.
