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

## Effectiveness audit — 2026-08-17 (3 production days on)

Measured from `api/youtube_stats.json` (generated 08-17, analytics
through ~08-15; the 08-15+ motion-era renders are still inside the
2-day analytics lag):

- **Long-form median AVP 13.1% → 16.2%** (n=129 pre / 20 post-08-13) —
  the chapters + caption-continuity batch is the change in that window.
  Early and small-n, but the direction is right and the size (~24%
  relative) is larger than any prior single-week move.
- **Shorts median AVP 49.3% → 51.2%** (n=357/62).
- **Retention curves (new instrument) localize the remaining lever**:
  mean audienceWatchRatio at the 5% mark is EN 0.51 / RU 0.54 / FR
  0.55 — half the audience leaves inside the first 30-45 s, then decay
  flattens after 25%. Outliers that held (tesla-RU ep554 0.72, spacex
  ep65 0.68) opened on exactly what the title promised.
- **Traffic mix**: EN is 53% Shorts feed / 16% suggested / **15%
  search** / 10% subscribers; RU is 98% Shorts feed; FR 89%. The EN
  search queries are concrete and content-adjacent ("starship flight
  14", "fsd v14.1 lite", "spacex flight 14") — demand that provably
  exists and that nothing was feeding back into titles or tags.
- All round-2 instruments verified live in production: traffic_sources
  + search_terms on all 3 channels, 15 retention curves, policy
  `shorts_pending`/`shorts_streak` hysteresis fields present (ru/spacex
  correctly holding 3 with streak tracking).

### Round 3 — shipped 2026-08-17

- **Search-terms loop closed**: channel-level search terms are
  token-matched to shows (conservative — unmatched terms drop) into
  `youtube_performance.json`; the title prompt gains a LIVE SEARCH
  QUERIES line and uploads prepend the matched terms as tags (through
  the guarded `build_tags`). Register: `search-terms-loop`.
- **Open-cliff instrument**: dashboard card "Long-form open cliff"
  (mean hold at 5% by channel + per-video 5/10/25/50% ladder) and the
  `long_open_hold_5pct_en` live metric (baseline 0.51). Register:
  `long-open-cliff`. Content-side changes to the spoken open are audio
  (landmine #17) and stay operator-gated; the in-flight levers against
  it are chapters, the accelerating open, and the motion batch.

## Effectiveness audit — 2026-08-24 (full week on every batch)

Verdicts per lever, from lag-corrected production data (the audit also
found and fixed the lag bug below):

- **Motion package (36 slots, adaptive KB, transition split, punch-ins,
  closing beat): WORKING.** EN Shorts views-per-day jumped ~6x by
  cohort (08-10..14 med 1.0 → 08-15..18 med 5.4 → 08-19..23 med 6.0)
  and Shorts AVP rose through the motion era (49.4 → 53.8% network;
  RU motion-era Shorts retain 58-62% vs 50-52% before). EN channel
  views +13.3% WoW, FR +74.4% WoW on the same code.
- **Chapters: NO measurable AVP lift yet.** Long-form median AVP is
  flat (13.0 pre → 13.4-13.6 after); the +3.1pt read on 08-17 was
  young-video bias and regressed as views accrued. Chapters are
  costless and still pay via search/"key moments" surfaces — keep, but
  score the 08-26 readout honestly as "flat on AVP".
- **Search-terms loop: FIRING.** 4 shows carry live matched queries
  (tesla "fsd v14.1 lite", spacex "starship flight 14", M&A/MAB
  "gemini 3.7 flash") in youtube_performance.json → title hints +
  upload tags. EN search share 14% (flat vs 15% baseline — days in).
- **Dub fragment titles: FIXED in the data** —
  dub_fragment_title_share_14d = 0.04 (was 26% on FR).
- **Open cliff: UNCHANGED** (EN hold@5% 0.51 = baseline). Remains the
  dominant retention lever; the motion batch hasn't moved the first
  30-45 s because that loss is decided by promise-match, which is
  title/thumbnail/spoken-open territory (the last is landmine #17).
- **RU cooling is real but demand-side**: RU -29.8% WoW after lag
  correction, with steady uploads (10-13/day), IMPROVED retention, and
  EN/FR growing on identical code — consistent with Shorts-feed
  rotation / mean reversion off the 08-10..14 hot streak (37 vpd med),
  not a pipeline fault. Recommendation: hold course; rising retention
  typically precedes re-distribution. Watch the scorecard, don't thrash.
- **Instrument bug found by this audit, fixed**: the WoW scorecard and
  zero_view_share counted the ~48 h of unreported YouTube Analytics
  lag as real zeros — every channel "lost" its newest 2 days of
  uploads, RU WoW read -43% during plain lag, and EN zero-view share
  read 0.22 (honest: 0.10). Windows are now lag-trimmed (_LAG_DAYS=2)
  in both the scorecard and the experiment WoW metrics; guard in
  tests/test_dashboard_growth.py::TestLagAwareAnalyticsWindows.


## All-channel analytics review — 2026-09-02 (28-day window, lag-aware)

**Where the views are.** RU Shorts on the science/space shows are the
network: FF-RU 35.4k views/28d (median 439/Short, +39 subs), spacex-RU
31.1k (median 257, +21), tesla-RU 17.2k — ~84k of ~127k network views.
FR has become a real channel (FF-FR 4.3k, spacex-FR 3.7k, +24/+9 subs).
EN Shorts: spacex 8.4k (+22 subs), FF 4.3k (+19), tesla 4.1k. Long-form
is small everywhere (best: tesla-EN 3.6k/28d, median 78 views) and the
dub long-forms are near zero (RU FF median 3 views at 5% AVP; MIT-RU 5
views total) — the weekly probe is the right ceiling for them.

**Dead weight.** Modern Investing is dead on every YouTube surface
(EN Shorts median 5, RU 6, FR 4; EN long AVP 7.8% — worst on the
channel); MAB EN Shorts median 4. Both are now register decisions
(`mit-dubs-cull`), not code.

**What the curves + windows say.**
- Long-form AVD is ~80 s regardless of episode length (<8 min 13.7% AVP,
  8-12 min 13.2%, 12-16 min 9.5%). On YouTube the long-form is a
  90-second product: the open decides everything, and structure past
  it is invisible unless the video SHOWS it — hence chapter title cards.
- Hook-first Shorts win everywhere: EN hook_open median 18 views vs
  8 qualified / 6 filled and 47 of 56 EN Shorts subs; RU 214 vs 172;
  FR 38 vs 34. The earlier "qualified retains 77%" was small-n noise.
  `shorts_first_is_hook` stays on. RU 'filled' holding ~80% of the hook
  clip's audience (n=180) is what licenses the 4-Short band.
- Shorter Short titles win on every channel (top vs bottom quartile:
  RU 66 vs 70 chars, EN 74 vs 81) — the " | show" tail is gone on Shorts.
- EN traffic: 51% Shorts feed / 16% search / 16% subscribers / 11%
  suggested. RU 98% Shorts feed. Search terms flow into 4 shows' tags.

**Readouts closed** (see `docs/experiments.yaml` outcomes): chapters
+0.4pt AVP (kept, navigation value), scene cadence (kept, not an AVP
axis), caption continuity (+4pt Shorts AVP, kept), search-terms loop
(flat, kept as plumbing), FR channel (KEEP), progress bar + outro cards
(no isolated instrument, kept).

**Shipped this pass:** chapter title cards on long-form (both render
paths, auto-derived from chapters JSON); Shorts titles headline-only;
4-Short band at 60 vpd (`MAX_SHORTS_PER_EPISODE` 4); retention curves
now carry forward across nightlies so the open-cliff instrument
accumulates past ~15 curves; MIT dubs cull raised as a decision.


## Narrative-matched imagery — 2026-09-02 (operator: "video quality
doesn't suit the subject")

Root cause, from the committed gallery prompts: every Grok Imagine
prompt LED with one of the show's static `image_queries` and tacked the
day's headline on as an 8-word tail — Tesla ep590 and ep591 both
shipped `cybertruck / electric vehicle charging / tesla supercharger /
tesla car`, whatever the stories were — and the library blend (raised
to 24 on 08-14) padded the rest of the slideshow with older copies of
the same generic pictures, ranked by weak token overlap but never
REQUIRED to overlap. Four generic images + twenty random old ones over a
narration about FSD v14 and Q3 deliveries is exactly what the comments
describe.

Shipped: `engine/scene_briefs.py` — one Grok text call per episode
writes a concrete, photographable scene per story (deterministic
headline-subject fallback, never raises); `build_image_prompts` leads
with the brief and demotes `image_queries` to fill; one fresh 16:9
scene per story (`scenes_per_episode`, cap 8, was a fixed 4) with the
scheduler context keyed on story + brief so each chapter gets ITS
picture; `short_scenes_per_episode` (5) 9:16 scenes from the same
briefs; the library blend back to 8 and on-topic only
(`gallery_blend_min_overlap` 1 — an off-topic library image is dropped,
a repeat of the episode's own relevant image is preferred). Register:
`scene-briefs-narrative-imagery`. Also: Modern Investing RU/FR YouTube
dubs culled (operator-directed).


## Video quality, continued — 2026-09-02 (same day, round 2)

- **2K source images.** `_api_size_for_aspect` now requests the
  endpoint's 2K ceiling (2048x1152 / 1152x2048). The 16:9 render
  prescales every still to 3840x2160 for Ken Burns, so a 1792-wide
  source was a 2.1x upsample before any zoom — that is the softness
  behind the quality complaints. The request ladder (2K -> legacy ->
  no size) means a revision that rejects 2K can never cost an image
  (previously a size rejection dropped straight to the 1024 default).
- **Shorts open on the scene about their own story.**
  `short_visual_extras(fresh_scene_context=)` orders the fresh 9:16
  scenes by overlap with the Short's window text; the 2nd/3rd Shorts
  cover mid-episode stories and used to open on the hook story's image.
- **Style descriptors** for the two shows that lacked a fitting one:
  Models & Agents for Beginners (teen-safe bright classroom look —
  it was defaulting to "photorealistic news photo") and a fuller Tesla
  descriptor (real vehicles/factories/charging/software on screens).
- Operator decision queued: the $0.05 quality image tier on the three
  engine shows (~+$35/mo) if 2K + story briefs do not end the complaints.


## First-round readout — 2026-09-03

What actually shipped, checked against the artifacts rather than the
PR descriptions:

- **Scene briefs ran on every YouTube episode of 2026-09-02** (the 11
  shows ran 07:32-08:07 UTC, after #1128 merged at 06:21). Per-episode
  metrics moved exactly as designed: fresh scenes 8 → 11-13 (8 long +
  5 Short; MAB/M&A returned 6/7 briefs and generated that many),
  library padding 30 → 14, image cost $0.16 → $0.26/episode. The
  committed gallery prompts for the day lead with the story brief.
- **The 2K request (#1129, merged 13:31) has not reached an episode**,
  and it would not have mattered: the endpoint ignores `size`. Every
  one of the 7,500+ committed gallery sidecars — dimensions probed from
  the real bytes at upload — is 1280x720 / 720x1280 on
  `grok-imagine-image` whatever was requested (the quality tier
  returned 1248x832 / 864x1152, i.e. 3:2 and 3:4, so its images were
  being cropped to fit as well). The documented controls (xai-sdk
  `image.sample`) are `aspect_ratio` ("16:9" / "9:16") and `resolution`
  ("1k" / "2k"); the request now sends those, keeps `size` only as the
  ladder's fallback, and records the delivered width per episode
  (`grok_image_px_max`). The first honest read is the 09-03 slate.
- **Frame check of Tesla Ep592** (the MP4 the video feed serves):
  hook overlay, per-word captions, brand pills, closing beat and outro
  card all render as designed; the fresh scenes are on-story (Solar
  Roof panels, Megapack containers, Optimus at a Supercharger). Two
  defects: a generic library image (a pier full of Model S) opened
  chapter 1 AND reappeared at 8:40 — `min_overlap=1` matched it on
  "tesla", a token present in 100% of the show's 436 library scenes
  (with "optimus", "cybercab", "fsd", "robotaxi" at 95-96%) — and the
  chapter card at 2:05 read "Several projects pair storage with solar
  to": a first-sentence fallback title (the Tesla digest's 12 items
  map poorly onto 4 spoken chapters) clipped at 60 by the chapter
  builder and again at 48, without an ellipsis, by the card stage — a
  truncation outside `engine/titles.py`, the exact rule at the top of
  CLAUDE.md.
- **Analytics cannot read any of it yet.** `api/youtube_stats.json`
  (generated 19:34 UTC) carries no rows for videos published 09-01 or
  09-02; the matured 08-25..31 baseline is EN long AVP 14.3% (n=57),
  EN Short 43.2% (n=107), RU Short 44.8% (n=67). First lag-aware read
  ~09-05; register readouts stay 09-23.
- Side finding: the topic-queue restock workflow has failed since
  09-02 17:18 on `test_uc_unproduced_interleaved_not_clustered` — two
  gate-deferred UC topics parked at the queue head made the guard read
  the airable interleaved queue as clustered. The guard now measures
  the sequence the picker will actually air.

Shipped as round 3 (`video-quality-round-3`): documented resolution
fields + delivered-size metric; salient-token library overlap
(`_common_tokens`, document frequency > 20% removed from both sides —
small candidate sets keep legacy overlap); chapter cards as a fit gate
on `engine.titles.CHAPTER_CARD_MAX` (clipped or structural titles get
no card, never a cut); the restock guard fix.
