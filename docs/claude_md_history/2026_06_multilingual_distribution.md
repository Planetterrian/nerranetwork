# Multilingual + international distribution (late June 2026; RU/FR dubs, video podcasts, the titles loop)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Multilingual + international distribution (late June 2026)

Three additive, off-critical-path systems that turn each English episode into a
multi-language, multi-channel property. English stays the canonical master and
the fallback everywhere; every piece is best-effort and non-blocking.

- **Multilingual translation tracks (FR / RU / ES / ZH).** A post-hoc stage
  (`engine/multilingual.py`, `engine/translate.py`) translates a finalized
  English `_tts.txt` + title/description via Grok, re-voices it with the show's
  **existing** cloned Grok voice (`kdif6sqjcyiq` — one voice across languages;
  `GROK_CLONED_VOICE_ID` optional override), validates the result (rejects
  refusals / English echoes / wrong-script ZH), and uploads to R2 as
  `…/<file>.<lang>.mp3`. Enabled network-wide via `multilingual.auto: true` in
  `_defaults.yaml` (the two RU shows opt out); ~$0.18/ep (~$50-55/mo). The blog
  page renders a language switcher + inline player only when a track exists.
  Each language also gets a real subscribable **per-language podcast feed**
  (`podcast.{fr,ru,es,zh}.rss`) built fresh from `summaries_<slug>.json` by
  `engine/language_feeds.py` (deterministic per-lang GUIDs; channel
  title/description translated once + cached in
  `digests/<slug>/channel_i18n.json` so nightly rebuilds cost no credits).
  Per-language pronunciation lives in `shows/translation_overrides.yaml`
  (language-scoped; never touches the English path). Orchestrated by
  `.github/workflows/multilingual.yml` (its own workflow so RU TTS + a second
  render can never delay/break the English publish). Docs:
  [`docs/multilingual.md`](docs/multilingual.md). Drift guards:
  `tests/test_multilingual.py`, `tests/test_language_feeds.py`.
- **RU YouTube dubs → @NerraRU.** For a show with
  `youtube.ru_dub_enabled: true`, the same multilingual workflow reuses the
  already-generated RU audio track **and** the episode's existing Grok gallery
  scene images (from the R2 manifest — **$0 extra image cost**) to render a
  long-form + 1 Short and upload them to @NerraRU with Russian metadata +
  disclosure (`engine/ru_dub.py`, `scripts/publish_ru_dubs.py`). Enabled for
  `tesla`, `spacex`, `fascinating_frontiers`, `modern_investing`. Idempotent via
  a per-show `digests/<slug>/youtube_videos.ru.json` index (per-show → no
  cross-show push contention). RU Shorts reached EN-channel parity (per-word
  Cyrillic ASS captions, smart-start, end-card CTA) in PR #748. Needs
  `YOUTUBE_REFRESH_TOKEN_RU` (no-ops with a log line until set). Docs:
  [`docs/ru_youtube_dubs.md`](docs/ru_youtube_dubs.md). Drift guards:
  `tests/test_ru_dub.py`.
- **Generalized language dubs → @NerraFR (July 18 2026; future languages).**
  `engine/lang_dub.py` is the language-parameterized sibling of `ru_dub`
  (which stays bespoke + untouched for @NerraRU — the show-memory
  precedent). A `DubLanguage` registry entry + `youtube.dub_languages:
  [fr]` + a `YOUTUBE_REFRESH_TOKEN_<CH>` secret + a `SEED_TIERS` channel
  = a new dubbed channel; language-neutral machinery is IMPORTED from
  ru_dub (no fork). FR registered for tesla/spacex/FF/modern_investing
  (MIT's multilingual `languages` gained `fr` — the track is the dub's
  input), **seeded shorts-only** with the RU 2.0 long_vpd floor (RU
  lesson: dubbed longs earned ~9% retention), full RU parity (optimized-
  title translation with echo rejection, smart multi-Shorts + fill,
  French ASS captions, French end-card + funnel comment, `no_scenes_yet`
  deferral, per-show `youtube_videos.fr.json` auto-picked-up by
  analytics/policy/subscriber tracking). Sweep:
  `scripts/publish_lang_dubs.py --lang fr` in `multilingual.yml`.
  Credentials resolve generically (channel `xx` →
  `YOUTUBE_REFRESH_TOKEN_XX`; en/ru behavior pinned unchanged).
  **@NerraFR went LIVE 2026-07-21** (this section previously said
  DORMANT) — 42 videos across the four shows in its first ten days, 38
  Shorts + 4 long. It was invisible to the feedback loop until
  2026-07-29 because `fetch_youtube_analytics` globbed only
  `youtube_videos.ru.json` beside the base index, so the policy computed
  `video_count_14d = 0` for every FR show and froze them at seed tier —
  a channel that could never earn a promotion. The glob is now a
  pattern, but it landed four minutes before that night's run, so **no
  nightly has definitely included it**; every FR show still reports
  `short_vpd: null`. First clean read is the next nightly, and FR tiers
  should not be touched until a couple of weeks of real velocity exist.
  Docs: [`docs/lang_youtube_dubs.md`](docs/lang_youtube_dubs.md). Drift
  guards: `tests/test_lang_dub.py`.
- **Video podcasts → Apple (July 25 2026 pilot: tesla + spacex).** Doc:
  [`docs/video_podcasts.md`](docs/video_podcasts.md); drift guards:
  `tests/test_video_podcast.py`. Apple's Feb-2026 HLS video experience is
  gated to a short list of hosting partners and it ignores
  `podcast:alternateEnclosure`, so a self-hoster's ONLY route into the
  Apple video player is a plain MP4 `<enclosure>` — and Apple's own
  guidance is to publish video as a **separate show**. So the two pilot
  shows emit `podcast.video.rss` / `spacex_podcast.video.rss` beside their
  audio feeds; **the audio feeds are never touched and no published
  enclosure URL changes**. The asset is the long-form 1920x1080 MP4 the
  YouTube stage already renders and previously deleted right after upload
  (`run_show._publish_youtube`'s cleanup) — so the marginal cost is one R2
  upload and ZERO extra render/Grok spend. Flow: `_publish_youtube` calls
  `engine.video_feed.upload_episode_video` right after the render (BEFORE
  the YouTube upload, so a YouTube failure doesn't also cost the video
  episode, and before the `unlink`) → `engine.summaries_io.upsert_video`
  attaches `record["video"]` → `engine.video_feed.build_video_feed_for_show`
  rebuilds the feed from summaries (the `language_feeds` pattern: fresh
  rebuild, deterministic `<prefix>-video-epNNN-YYYYMMDD` GUIDs, churn
  suppression, never an empty feed). Three things that look redundant and
  are not: `content_type="video/mp4"` is passed EXPLICITLY on both the
  upload and the enclosure (`upload_to_r2` defaults non-`.mp3` to
  `application/octet-stream` and `publisher.py` hardcodes `audio/mpeg` in
  three places — either would make Apple refuse the episode); the R2 key is
  `video/<slug>/…`, outside the audio keyspace every published enclosure
  depends on, so a lifecycle rule can expire video alone; and nightly's
  add-paths needs `*.video.rss` because Tesla's audio feed is the ROOT
  `podcast.rss`, which `*_podcast.*.rss` does not match
  (youtube_channel_history silent-drop class). Enclosures are deliberately
  NOT OP3-prefixed (OP3 is an audio-download redirector, not a video CDN;
  engagement comes from Apple Connect). **Known coupling:** the video
  episode is a by-product of the long-form render, so an adaptive-policy
  shorts-only day yields no video episode — the run logs a `::warning::`
  and records `video_podcast_render_only` (Sep 22 2026 — it renders
  anyway for the feed and skips only the YouTube upload). Per-
  episode `video_podcast_bytes` is recorded so the R2 storage projection
  is measured rather than guessed (unmeasured at merge). Operator work is
  the Apple Podcasts Connect submission of each `.video.rss` as a NEW
  show — see the doc's checklist. Rollback is one YAML flag per show.
- **Recursive YouTube → titles feedback loop.** Mirrors the OP3 audio loop:
  `scripts/fetch_youtube_analytics.py` reads each show's
  `digests/<slug>/youtube_videos.json`, queries the YouTube Analytics API for
  retention (`averageViewPercentage` — the strongest public content-quality
  signal; CTR is Studio-only), and `scripts/update_youtube_performance.py`
  distils a per-show `title_hint` into `youtube_performance.json` that
  `engine/youtube_titles.generate_youtube_titles` injects into the title prompt
  (nightly). It touches ONLY the YouTube title (visual metadata, not the spoken
  hook) so it sits **outside** the landmine #17 A/B gate, and ships **dormant**
  — a clean no-op until the operator re-auths the OAuth token with the
  `yt-analytics.readonly` scope and a few weeks of data accrue. Docs:
  [`docs/youtube_feedback_loop.md`](docs/youtube_feedback_loop.md). Drift
  guards: `tests/test_youtube_feedback_loop.py`.
