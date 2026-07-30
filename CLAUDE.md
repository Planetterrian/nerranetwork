# CLAUDE.md — Tesla Shorts Time Podcast Network

## Titles: one module owns every limit

**Never truncate a title outside `engine/titles.py`.** Import a limit and
`clip_words()` / `episode_title()` from it. A new surface adds its limit
to that module; it does not write its own slice.

This is not style preference. The same bug shipped three times
independently — `engine.blog` sliced `hook[:100]`,
`video_metadata._truncate` sliced `text[:max_len - 3]`, and `run_show`
built `f"Ep {n}: {hook}"` with no cap at all — and the consequence was
that **YouTube silently rewrote episode titles on every show in the
network** for months, cutting mid-word and emailing to say no action was
required. Current limits: YouTube 100, podcast RSS 100 (same on purpose,
YouTube ingests the feed), web `<title>` lead 62, newsletter subject 78.
`tests/test_titles.py` enforces the property against ~4,500 generated
hooks in English and Russian.

Full context, including the Search Console work, the verified state of
each subsystem and the traps found along the way:
[`docs/session_2026-07-28.md`](docs/session_2026-07-28.md).

## Funnel links: one module owns every campaign id

**Never build a `utm_*` link, campaign id, or capture tag for a
published surface outside `engine/funnel.py`.** Import
`episode_link()` / `campaign_id()` / `destination_for()` /
`capture_tags()`. A new surface adds itself to that module's closed
vocabularies; it does not hand-roll a query string.

Same shape as the titles rule, same cause. Three surfaces each invented
their own scheme and the result was that **nothing the network published
could be joined to anything it measured**: `video_metadata` wrote
`utm_campaign=ep45` with no show slug (every show's episode 45 became
one GA4 row), `ru_dub` linked the bare English homepage with no UTM at
all (@NerraRU — the network's HIGHEST-reach surface at ~25,800
views/30d — was invisible), and Buttondown captured one undifferentiated
`gallery-subscriber` tag. Four live analytics systems, no shared key, so
the July 18 2026 audit's central finding (world-class factory, funnel is
the product gap: 3,900 downloads/30d, 3 subscribers) could not be acted
on.

`campaign_id()` and `parse_campaign_id()` must stay exact inverses —
`scripts/build_funnel.py` attributes GA4 rows purely by parsing them, so
drift is SILENT (the report just goes to zero).
`tests/test_funnel.py` round-trips every generated shape and asserts
each real surface emits a parseable campaign.

Full context — the funnel report's honesty rules (null vs 0, the
30-denominator floor, `attribution_coverage_pct`), the RU SpaceX pilot,
and the Shorts motion A/B: [`docs/funnel.md`](docs/funnel.md).

## Project Overview

Automated daily podcast generation system running 15 shows via a unified
`run_show.py` runner + per-show YAML configs, plus 4 legacy standalone scripts
(deprecated — see note below). Shows use **Grok TTS** (`engine.tts.grok_speak_chunk`)
and (where enabled) post to X/Twitter via `engine/publisher.post_to_x()`.

| Show | Legacy Script | YAML Config | Schedule | X Account | TTS |
|------|--------------|-------------|----------|-----------|-----|
| Tesla Shorts Time | — (deleted) | `shows/tesla.yaml` | Daily | `@teslashortstime` | Grok TTS (custom) |
| Omni View | — (deleted) | `shows/omni_view.yaml` | Daily | `@omniviewnews` | Grok TTS (custom) |
| Fascinating Frontiers | — (deleted) | `shows/fascinating_frontiers.yaml` | Daily | `@planetterrian` | Grok TTS (custom) |
| Planetterrian Daily | — (deleted) | `shows/planetterrian.yaml` | Daily | `@planetterrian` | Grok TTS (custom) |
| Env Intel | — | `shows/env_intel.yaml` | Monday | `@teslashortstime` | Grok TTS (custom) |
| Models & Agents | — | `shows/models_agents.yaml` | Daily | — (X disabled) | Grok TTS (custom) |
| Models & Agents for Beginners | — | `shows/models_agents_beginners.yaml` | Daily | — (X disabled) | Grok TTS (custom) |
| Финансы Просто | — | `shows/finansy_prosto.yaml` | Monday | — (X disabled) | Grok TTS (Olya) |
| Modern Investing Techniques | — | `shows/modern_investing.yaml` | Daily | — (X disabled) | Grok TTS (custom) |
| Привет, Русский! | — | `shows/privet_russian.yaml` | Monday | — (X disabled) | Grok TTS (Olya) |
| Unintended Consequences | — | `shows/unintended_consequences.yaml` | Daily | — (X disabled) | Grok TTS (custom) |
| First Principles Daily | — | `shows/first_principles.yaml` | Daily | — (X disabled) | Grok TTS (custom) |
| SpaceX Daily | — | `shows/spacex.yaml` | Daily | — (X disabled) | Grok TTS (custom) |
| The DP Pod | — | `shows/dp_pod.yaml` | Daily | — (X disabled) | Grok TTS (two-voice: Patrick + Dan) |
| The Age of AI | — | `shows/age_of_ai.yaml` | When an interview is ready (Nerra Voices pipeline, NOT run_show) | — (X disabled) | Real guest phone audio + Mira narration (Grok voice `ara`) |

> Weekly-summary segment (July 2026): shows on a daily cadence with
> `weekly_summary_segment: true` in their YAML run a NORMAL daily episode on
> Sunday that ALSO includes one short "week in review" segment synthesised
> from the past 7 days via the content lake. (This replaced the retired full
> Sunday weekly-recap mode, which skipped the daily news fetch and turned the
> whole Sunday episode into a look-back.) The segment is appended to the
> podcast-only copy of the digest, so no host-instruction text reaches the
> blog / RSS. See landmine #19.

**Science That Changes Everything** (`digests/science_that_changes.py`, ~83 lines)
is a standalone X-posting script, not a podcast show.

## Architecture

### Pipeline (per show, per run)

1. **Fetch** news sources (RSS, xAI/Grok web search, xAI ``x_search`` for Tesla stock quote)
2. **Dedup** via ContentTracker (cross-episode) + entity dedup
3. **Generate** digest text via xAI/Grok API
4. **Synthesize** podcast audio via Grok TTS (`engine/tts.py`, WAV @ 48 kHz)
5. **Mix** intro/outro music with voice (ffmpeg) — all shows (configurable per YAML)
6. **Post** X thread via `engine/publisher.post_to_x()` + update RSS feed + commit output to git

### Key Directories

```
nerranetwork/
├── run_show.py                    # Unified show runner (~716 lines)
├── shows/                         # Per-show YAML configs
│   ├── tesla.yaml
│   ├── omni_view.yaml
│   ├── fascinating_frontiers.yaml
│   ├── planetterrian.yaml
│   ├── env_intel.yaml
│   ├── models_agents.yaml
│   ├── models_agents_beginners.yaml
│   ├── finansy_prosto.yaml
│   ├── modern_investing.yaml
│   └── privet_russian.yaml
├── digests/                       # Legacy show scripts (deprecated) + ALL generated output
│   ├── tesla_shorts_time.py       # DEPRECATED — use run_show.py tesla
│   ├── omni_view.py               # DEPRECATED — use run_show.py omni_view
│   ├── fascinating_frontiers.py   # DEPRECATED — use run_show.py fascinating_frontiers
│   ├── planetterrian.py           # DEPRECATED — use run_show.py planetterrian
│   ├── science_that_changes.py    # ~83 lines — standalone X posting script
│   ├── xai_grok.py                # Shared xAI/Grok API helper (~111 lines)
│   ├── tesla_shorts_time/         # TST output + summaries_tesla.json
│   ├── omni_view/                 # OV output + summaries_omni.json
│   ├── fascinating_frontiers/     # FF output + summaries_space.json
│   ├── planetterrian/             # PT output + summaries_planet.json
│   ├── env_intel/                 # EI output + summaries_env_intel.json
│   ├── models_agents/             # M&A output + summaries_models_agents.json
│   ├── models_agents_beginners/   # MAB output
│   ├── finansy_prosto/            # FP output (Russian)
│   ├── modern_investing/          # MIT output
│   ├── privet_russian/            # PR output (bilingual Russian)
│   └── *.mp3, *.md, *.txt        # Legacy TST flat output (historical)
├── engine/                        # Shared modules
│   ├── __init__.py
│   ├── utils.py                   # Env helpers, text processing, similarity, dedup
│   ├── tts.py                     # Multi-provider TTS (Grok primary; legacy ElevenLabs path retained) — auth, chunking, synthesis
│   ├── audio.py                   # mix_with_music (3 modes), normalize_voice, duration helpers
│   ├── publisher.py               # RSS feeds, X posting, GitHub Pages summaries, digest formatting
│   ├── content_tracker.py         # Cross-episode dedup (per-show section patterns)
│   ├── fetcher.py                 # RSS article fetching
│   ├── generator.py               # LLM digest/podcast script generation
│   ├── tracking.py                # Credit/usage tracking
│   ├── config.py                  # YAML config loader
│   ├── storage.py                 # Cloudflare R2 storage helpers
│   ├── newsletter.py              # Email newsletter helpers
│   └── validation.py              # Config validation
├── assets/
│   ├── pronunciation.py           # Shared TTS pronunciation fixes
│   └── music/                     # Centralized podcast music (intro/outro)
│       ├── README.md              # Music generation guide + AI prompts
│       ├── tesla_shorts_time.mp3  # TST + EI + M&A theme
│       ├── fascinatingfrontiers.mp3     # FF intro jingle
│       ├── fascinatingfrontiers_bg.mp3  # FF background/outro
│       ├── LubechangeOilers.mp3         # OV theme
│       └── oilers-pride.mp3             # PT theme
├── tests/                         # pytest suite
├── .github/workflows/
│   └── run-show.yml               # Unified daily cron workflow (all shows)
├── *.rss                          # Podcast RSS feeds (consumed by Apple/Spotify)
├── *.html                         # GitHub Pages web players + summaries pages
└── docs/                          # Audit docs, storage plan
```

### Script Relationships


> **Per-show review history lives in**
> [`docs/show_review_history.md`](docs/show_review_history.md) — every
> dated quality-pass narrative (root causes, what was fixed, what was
> deferred), moved out of this file on 2026-07-29 so a session does not
> pay to load ~60 KB of history it rarely needs. The entries below keep
> each show's structural facts. Canonical write-ups:
> [`docs/reviews/`](docs/reviews/); scored predictions +
> `do_not_retry`: [`docs/reviews/ledger/`](docs/reviews/ledger/).

**Live constraints from those passes** (kept here because they bind
today's work, not just explain yesterday's):

- **SpaceX AI section:** the Colossus/Anthropic material is REAL — do not
  "correct" or relitigate it (operator-confirmed, June 13 2026).
- **Length levers are digest-side only.** Podcast-side expansion retries
  are banned network-wide (July 18 playbook `do_not_retry`: ~10 misses vs
  1 hit) and were switched off in the show YAMLs on 2026-07-29 wherever a
  digest-side lever exists. Chronic under-length on FF / PT / UC / Tesla /
  EI is a DIGEST ceiling — do not re-attack it at the script.
- **De-seed by shape, never with a quotable example.** Every seeded
  template tic in this network's history came from a prompt supplying the
  literal sentence it wanted; three generations of them are in the
  archive. New prompt guidance describes the shape and bans the verbatim.
- **The grok-4.3 narrative-length plateau is accepted** (operator
  confirmed; it resists escalation). Not a bug to re-open.
- **MIT is NOT ready for live trading** and its `execution/live.py` layer
  is dormant behind a kill switch. Two operator to-dos remain open:
  `scripts/recompute_mit_benchmarks.py --apply` (needs market-data
  access) and SnapTrade Phase-0 verification.

- **FF and PT** are "nearly identical twins" — same structure, same functions,
  different news topics and X account
- **TST** shares most patterns with FF/PT but adds: complex pronunciation
  fixes, content tracking, chunked TTS, x_search stock data, TST-specific
  emoji formatting via `engine.publisher.format_tst_digest_for_x()`
- **OV** is structurally different — different TTS approach (no streaming, uses
  env vars for voice settings), simpler functions.
- **EI** runs exclusively via `run_show.py` + `shows/env_intel.yaml`; no legacy script.
- **M&A** (Models & Agents) runs exclusively via `run_show.py` +
  `shows/models_agents.yaml`; no legacy script.
- **MAB** (Models & Agents for Beginners) runs via `run_show.py` +
  `shows/models_agents_beginners.yaml`; beginner/teen-focused version of M&A.
  On the custom Grok voice `kdif6sqjcyiq` (inherits `_defaults.yaml`; the old
  "ElevenLabs" note was stale per landmine #17). X posting disabled.
- **FP** (Финансы Просто) runs via `run_show.py` +
  `shows/finansy_prosto.yaml`; Russian-language financial literacy podcast
  for women in Canada (even days only). Uses **Grok TTS** (Olya voice
  `0b875ae2`, `language_code: ru`). All content generated in Russian. X posting disabled.
- **MIT** (Modern Investing Techniques) runs via `run_show.py` +
  `shows/modern_investing.yaml`; daily investing podcast focused on Canadian
  and US markets. Weekdays only. X posting disabled.
- **PR** (Привет, Русский!) runs via `run_show.py` +
  `shows/privet_russian.yaml`; bilingual Russian language learning podcast
  for English speakers. Even days only. Uses **Grok TTS** (custom Olya voice
  `0b875ae2`, `language_code: ru` — `shows/privet_russian.yaml`). X posting
  disabled.
- **FPD** (First Principles Daily) runs via `run_show.py` +
  `shows/first_principles.yaml`; a **daily narrative** show
  (`narrative_mode: true`, topic-queue-driven like UC — no news fetch).
  Applies the first-principles "magic wand number" + "Idiot Index" lens,
  alternating per episode between a concrete example of the thinking in
  action (`category: concrete_example` — historical and modern: Ford,
  Bessemer, containerization, solar, batteries, mRNA, and *sometimes*
  Musk's teams, deliberately not Musk-only) and an industry ripe for it
  (`category: opportunity_area`); Ep1 is a combined debut. Patrick voice
  (inherits Grok `kdif6sqjcyiq`). Distribution OFF at launch (no newsletter,
  no X, no YouTube). Queue: `shows/topic_queues/first_principles.yaml`.
- **UC** (Unintended Consequences) runs via `run_show.py` +
  `shows/unintended_consequences.yaml`; a weekday **narrative** show
  (`narrative_mode: true`, topic-queue-driven — no news fetch). Patrick
  voice. X posting on via the @planetterrian account.
- **SpaceX** (SpaceX Daily) runs via `run_show.py` + `shows/spacex.yaml`;
  engineering-first daily on SpaceX as a public company (Nasdaq: SPCX),
  `memory_enabled`, X disabled.
- **DP** (The DP Pod: The Do Positive Podcast) runs via `run_show.py` +
  `shows/dp_pod.yaml`; the network's **two-host dialogue** show (July 2026
  launch) — Dan Perra + Patrick Novak, daily ~10 min of good news in science/
  tech plus one individual action with honest numbers ("The Lever"). Segments:
  Cold Open → The Positive Papers → The Lever → Do Positive Dispatch →
  sign-off "Do something about it." Fresh episode all 7 days (NO Sunday
  recap — deliberately absent from `DAILY_SHOWS` in `tests/test_schedule.py`).
  First show on the **two-voice dialogue TTS path**: `tts.dialogue_mode: true`
  + `tts.dialogue_voices` (`PATRICK: kdif6sqjcyiq`, `DAN: 0vscf8u8yrxc`) make
  the pipeline preserve `DAN:`/`PATRICK:` speaker labels (three legacy
  prefix-strippers are gated on the flag — `engine/generator.py`
  `_sanitize_podcast_script`, run_show's `_clean_podcast_script` + final
  defense strip) and synthesize per-speaker via `engine/tts_dialogue.py`
  (turn-group parsing, per-group Grok calls, pause padding, shared WAV
  crossfade → single MP3 encode). Dialogue mode NEVER applies the `<fast>`
  wrap (per-turn wraps are the landmine-#17 leak shape ×30 handoffs) and
  supersedes section-TTS. An unlabeled script falls back to single-voice
  `tts.voice_id` with a loud warning + `dialogue_fallback_single_voice`
  metric. Show page is `thedppod.html` (registered via
  `shows/network_meta.yaml` `show_page` override). RSS + site only at launch
  (X/YouTube/newsletter/multilingual off). Drift guards:
  `tests/test_tts_dialogue.py` (engine; existing shows pinned to
  `dialogue_mode is False`), `tests/test_dp_pod_show.py` (launch shape).
  Prompt edits change shipped audio — A/B-listen per landmine #17; the first
  episodes are the calibration set for `dialogue_pause_ms` handoff pacing.
- **AOAI** (The Age of AI) — the network's **AI-hosted LIVE interview show**
  (July 2026): Mira, an AI documentarian persona (Grok voice `ara`,
  deliberately NOT the Patrick clone), phones REAL guests via a Voximplant
  scenario bridged to a Grok Voice Agent, dual-track records the call, and
  the episode is produced from the real recording. **Production does NOT go
  through run_show** — `shows/age_of_ai.yaml` exists for registry/publish
  surfaces only, and its narrative mode + permanently-empty topic queue make
  an accidental `run_show.py age_of_ai` a clean `narrative_queue_empty` skip.
  The real pipeline is **Nerra Voices**: `pipelines/voices/` + the five
  `nerra_voices_*.yml` workflows + `workers/voices/` (webhooks, Mira's 3
  in-call tools, triage/review UIs — Cloudflare Worker at
  `api.nerranetwork.com/voices/*`, a documented deviation from the spec's
  Vercel sketch) + `supabase/migrations/20260704_nerra_voices_schema.sql`
  (separate Supabase instance; 6 tables are the state machine) +
  `voximplant/scenarios/age_of_ai_interview.js` (the central glue: outbound
  PSTN → Grok Voice bridge → stereo recorder → hangup webhook; 50-min hard
  cap). Flow: apply form → Patrick triage (~30 s) → Cal.com booking → T-1d
  LLM prep brief emailed to guest → T-2h SMS → fire (5-min cron,
  drift-tolerant window, idempotent) → live call → post-processing (R2, mix,
  per-channel Whisper STT — the stereo tracks ARE the diarization, 8
  schema-validated editorial passes) → **gate 1: Patrick editorial review
  (never times out into publish)** → **gate 2: guest transcript approval
  (day-4 reminder, day-7 auto-approve; redactions cut from audio FIRST at
  assembly)** → Mira narration TTS + ffmpeg assembly + waveform video →
  publish via the standard `engine.publisher` surface. Guest words are
  verbatim; every episode discloses the AI host. Spec-as-implemented +
  operator bootstrap (Voximplant/Supabase/Cal.com/Worker provisioning +
  phase-1 smoke test): [`docs/age_of_ai_plan.md`](docs/age_of_ai_plan.md);
  drift guards: `tests/test_age_of_ai_show.py` (registry no-op shape, spec
  artifacts, dispatch-event coherence, validators, the two human gates).
  RSS + site only at launch; X/YouTube/newsletter/multilingual off until
  the phase-8 public launch.
- All shows delegate X posting to `engine.publisher.post_to_x()`
- TST/FF/PT delegate voice normalization to `engine.audio.normalize_voice()`
- All shows use `engine.audio.mix_with_music()` for music mixing (3 modes:
  standard, delayed-intro, dual-music). Music files in `assets/music/`.
  Shows without music files gracefully fall back to voice-only.

## Adding a new show

Use `python scripts/scaffold_show.py` to generate YAML, prompts, output dirs, and
`shows/network_meta.yaml` in one step. Episode 1 gets extra debut guidance via
`engine/first_episode.py`. See [`docs/NEW_SHOW.md`](docs/NEW_SHOW.md).

## Conventions

### Environment Variables

- All secrets come from `.env` (local) or GitHub Actions secrets
- `GROK_API_KEY` — primary xAI key (all shows)
- `ELEVENLABS_API_KEY` — ElevenLabs TTS (legacy/rollback only — no show uses ElevenLabs in production)
- `X_*` / `PLANETTERRIAN_X_*` — two separate X accounts
- Voice IDs: **All 13 shows are on Grok TTS** as of the May 2026 full-network migration. The 10 English shows (including Tesla Shorts Time) share the operator's custom-trained voice `kdif6sqjcyiq`. Russian shows (FP/PR) use the custom Olya voice `0b875ae2`. ElevenLabs is no longer used in production but the API key + legacy settings stay in `_defaults.yaml` for emergency rollback. See landmine #17.
- See `docs/env_var_inventory.md` for the complete inventory

### RSS Feeds

All RSS `<enclosure>` URLs now use `audio.nerranetwork.com` (Cloudflare R2).
MP3 files are uploaded to R2 during the pipeline and excluded from git commits.
**Do NOT change R2 bucket paths — this breaks podcast subscribers.**

### Image gallery (Phases 1 + 2 + 3 — May 2026)

Every Grok-Imagine scene generated for the YouTube long-form / Shorts
slideshow is uploaded to a separate R2 bucket (`nerra-gallery`) with a
JSON sidecar and a watermarked WebP thumbnail.

**Phase 1 — storage.** Module:
[`engine/gallery_uploader.py`](engine/gallery_uploader.py). The hook
into `run_show.py:_publish_youtube` is purely additive — gallery
upload failure cannot block YouTube publish. New env vars:
`R2_GALLERY_BUCKET` (default `nerra-gallery`),
`R2_GALLERY_PUBLIC_BASE_URL` (optional). License default: **CC BY-SA
4.0** with attribution to Nerra Network. Backfill:
[`scripts/backfill_gallery.py`](scripts/backfill_gallery.py) — note
historical scene dirs are in `.gitignore` so there is nothing to
backfill from on-repo state without an external archive.

**Phase 2 — manifest + rendering.** A workflow
([`.github/workflows/build-gallery-manifest.yml`](.github/workflows/build-gallery-manifest.yml))
runs nightly + after every successful `Run Podcast Show` and rebuilds
[`site/data/gallery-manifest.json`](site/data/gallery-manifest.json)
from the R2 sidecars via
[`scripts/build_gallery_manifest.py`](scripts/build_gallery_manifest.py).
The frontend is **vanilla JS** ([`assets/js/gallery.js`](assets/js/gallery.js))
— no build step — hydrating the mount point declared in
[`templates/_gallery_section.html.j2`](templates/_gallery_section.html.j2).
The network-wide page is
[`templates/gallery_page.html.j2`](templates/gallery_page.html.j2)
rendered to `/gallery.html` by `generate_gallery_page()` in
`generate_html.py`. Per-show galleries are embedded on each show page
when `gallery_enabled` is true (any show with `youtube.enabled: true`
AND `image_provider: grok`; as of June 14 2026 that's Tesla, SpaceX,
Fascinating Frontiers, Modern Investing + the two RU shows — MAB's
YouTube is paused so its gallery auto-hides — see landmine #20).
Prompt visibility is a per-image **toggle** (hidden by default in the
lightbox).

**Phase 3 — email-gated downloads.** Cloudflare Worker at
`api.nerranetwork.com` ([`workers/gallery/`](workers/gallery/)) with
four endpoints: `POST /api/subscribe` (Buttondown subscribe + 90-day
JWT cookie), `GET /api/login` (magic-link email via Resend, always
200 so the address can't be enumerated), `GET /api/magic` (consume
the magic JWT, set cookie, 302 to /gallery), `GET /api/download`
(verify cookie, stream the R2 object via the bucket binding with
`Content-Disposition: attachment`). JWT is HS256, hand-rolled in
[`workers/gallery/src/jwt.ts`](workers/gallery/src/jwt.ts) — no
third-party dep on the Worker. The download endpoint **proxies bytes
through the Worker** instead of issuing signed R2 URLs (revocation
works, no shareable URLs, no SigV4 plumbing — documented deviation
from the spec). Frontend [`assets/js/gallery.js`](assets/js/gallery.js)
calls these endpoints with `credentials:'include'`; gate modal
supports both "Subscribe & download" and "Already subscribed? Sign
in instead" paths. New secrets (set via `wrangler secret put` once):
`JWT_SECRET`, `BUTTONDOWN_API_KEY`, `RESEND_API_KEY`,
`RESEND_FROM_EMAIL`. The Worker doesn't need new R2 credentials —
the bucket is wired declaratively as `GALLERY_BUCKET` in
[`workers/gallery/wrangler.toml`](workers/gallery/wrangler.toml).

Layout, schema, env vars, deployment steps, and the operator
checklist live in
[`docs/gallery_storage.md`](docs/gallery_storage.md) and
[`workers/gallery/README.md`](workers/gallery/README.md).
Unconfigured environments (env vars unset) are a clean no-op: the
manifest builder writes an empty manifest, the frontend renders a
friendly empty state, and the gate modal surfaces a network error if
the Worker hostname isn't reachable yet.

### YouTube Shorts production (May 2026 retune)

Two Shorts-quality fixes shipped after the operator caught issues
with the first wave of episodes:

* **Thumbnail title auto-shrink-to-fit.**
  [`engine/publisher.py:generate_episode_thumbnail`](engine/publisher.py)
  iteratively shrinks the hook font (start at the YouTube-spec max,
  step down by 8 px) until the wrapped block fits inside 60 % of the
  frame height AND ≤ max-lines (3 on Shorts 1080×1920, 4 on long-form
  1280×720). Floor at ~32 px. Replaces the legacy fixed-size
  rendering that clipped long Tesla hooks against the safe area.
  Drift guard: `tests/test_thumbnail_autofit.py`.
* **Shorts burn-in caption upgrade.** Bumped from outline-only
  FontSize=34 to FontSize=48 bold on a 50 %-opaque box
  (`BorderStyle=3` + `BackColour=&H80000000`) in
  `engine.video._SHORTS_SUBTITLES_FORCE_STYLE` — TikTok-style
  "subtitle card" that stays readable over Grok-Imagine backgrounds.
  Position shifted to `MarginV=340` to keep the larger card clear of
  the URL pill (y ≈ 1820) and below the hook overlay (y ≈ 1056).
  Caption wrap tightened to 24 chars / 2 lines (was 32 / 3) to match
  the larger font; see
  `engine.captions.transcript_to_srt_window`. Drift guard:
  `tests/test_video_commands.py::test_short_form_filter_graph_burns_subtitles_when_path_provided`.

`shows/models_agents_beginners.yaml` also flipped from
`image_provider: pexels` to `grok` in May 2026 — Pexels A/B was
inconclusive and the gallery pipeline (Phase 1) requires Grok
Imagine. Cost: ~$0.16/episode added.

**Per-word caption highlighting (TikTok / Reels look).** Shorts now
ship with per-word "current word" highlighting instead of static
segment cards.
[`engine.captions.transcript_to_ass_window`](engine/captions.py)
generates an ASS file (the modern subtitle format the ffmpeg
`subtitles` filter accepts identically to SRT — no `video.py` change
needed) with one `Dialogue` line per word; each line shows the full
chunk text with the active word colour-flipped to Nerra cyan
(`#00D4FF` / ASS `&H00FFD400`). Word timestamps come from
`faster-whisper` which already runs with `word_timestamps=True` in
`engine.transcripts` — no new transcription cost. Words are chunked
to ≤24 chars / ≤8 words per chunk to match the FontSize=48 caption
card. `run_show.py` tries the ASS path first; if the transcript has
no word data (older episodes) or no overlap with the Shorts window,
it falls back to the legacy segment-level SRT so the Short always
has captions of some kind. Drift guards in
`tests/test_captions_ass.py`.

**Smart Shorts segment selection.** Tesla + MAB now use
`shorts_start_mode: smart` in their YAML, which calls
[`engine.shorts_selector.pick_engaging_window`](engine/shorts_selector.py)
to scan the Whisper transcript and start the Shorts clip at the
most engaging beat (numeric reveal, hook framing like "the kicker
is…", surprise / question / superlative). Pure heuristic — no LLM
call, no per-episode cost. Falls back to the legacy
`voice_intro_delay` start when no segment scores above the noise
threshold (5.0). The chosen offset + the resolved mode are recorded
as metrics (`shorts_start_offset`, `shorts_start_mode_resolved`) per
episode so the dashboard can show smart-vs-fallback rates. New shows
opt in by setting `youtube.shorts_start_mode: smart` in their YAML.
Drift guards in `tests/test_shorts_selector.py`.

**Multiple Shorts per episode.** Setting `youtube.shorts_per_episode`
to N (default 1; cap at 2-3 for YouTube quota safety on the
@NerraNetwork channel — see landmine #20) makes the runner publish
N Shorts per episode instead of one. Each Short comes from one of
the top-N non-overlapping windows the smart selector
([`pick_top_n_engaging_windows`](engine/shorts_selector.py)) picks
from the transcript; each gets a distinct headline (the window's
opening text), a distinct thumbnail (cycled through the available
Grok-Imagine scene images), and a distinct filename
(`_short_1.mp4`, `_short_2.mp4`, …). Uploads are sequential; one
failure doesn't block the others. Per-Short error captures land in
`result["short_errors"][i]` and the aggregate
`shorts_count_requested` / `shorts_count_uploaded` metrics fire on
every episode so the dashboard can plot the multi-Shorts hit rate.
Requires `shorts_start_mode: smart` (the voice / first_chapter
modes only know about one offset). Default 1 preserves legacy
single-Short behaviour byte-for-byte. Drift guards in
`tests/test_shorts_selector.py` under the
`pick_top_n_engaging_windows` block.

**Auto-hashtag injection on Shorts descriptions.** Every Shorts
upload now carries entity-derived hashtags in its description
(via [`engine.shorts_hashtags.extract_hashtags`](engine/shorts_hashtags.py)).
YouTube renders the **first 3** hashtags as clickable topic-tag
links above the video title — biggest discovery lever on Shorts
after the title itself. Heuristic-only parser, no LLM call:
multi-word Title-Case entities (`Tesla Cybercab` →
`#TeslaCybercab`) outrank single proper nouns (`Tesla` →
`#Tesla`) which outrank all-caps acronyms (`TSLA` → `#TSLA`),
with the show's YAML `keywords` blended in at the tail to fill
remaining slots. Substring de-dupe across bands prevents
"#Tesla" eating a slot when "#TeslaCybercab" already covers the
entity. Caps at 5 hashtags + the static `#Shorts #podcast`
suffix. Real-hook probes: Tesla wireless-BMS hook →
`#BatteryManagementSystem #Tesla #Cybercab`; Modern Investing
TFSA/RRSP hook → `#ModernInvestingTechniques #TFSA #RRSP`. Drift
guards in `tests/test_shorts_hashtags.py`.

**Hook overlay auto-shrink-to-fit.** The 0–3 s static hook
overlay on the Shorts MP4 used to render at a fixed
fontsize=44 with a conservative char-based wrap (26 chars × 4
lines = 104-char budget) that truncated longer Tesla hooks with
"...". `engine.video.autofit_hook_overlay` now applies the same
shrink-to-fit pattern the thumbnail uses: start at 44 px, drop
in 4-px steps (44 → 40 → 36 → 32) only if the wrapped text
would truncate at the larger size. Pixel-accurate wrap via PIL
`ImageFont.getbbox` uses the actual 1080-px Shorts frame width
instead of the char-budget approximation, so a 110-char hook
(Tesla Ep461 Cybercab wireless-BMS) now fits at 44 px without
truncation, and runaway 170+-char hooks shrink to 32 px and
still fit. Drift guards in `tests/test_video_commands.py` under
the "Shorts hook overlay auto-shrink-to-fit" header.

**End-screen CTA card.** The last
`youtube.shorts_end_card_duration_seconds` (default 3 s) of every
Short overlays a PNG end card composited at run time by
[`engine.publisher.generate_shorts_end_card`](engine/publisher.py).
The card shows the long-form 1280×720 thumbnail in the upper third
(framed with a thin white border so it reads as a tap target),
a big white headline ("WATCH FULL EPISODE"), a cyan sub-line
("Tap Subscribe ↗", matching the per-word caption highlight from
PR #415), and a small `nerranetwork.com` footer. The
`engine.video._short_form_filter_graph` overlays the PNG via a
single `overlay=enable='between(t,END-3,END)'` filter. When PNG
generation fails (or the long-form thumbnail upstream failed),
the chain falls back to the drawtext-only version originally
shipped in PR #417 — soft degradation, never blocks the Shorts
publish. Implemented as a drawbox + 2 drawtext
filters in the existing filter graph — zero filesystem dependency,
no per-episode asset generation. YAML knobs to customise:
`shorts_end_card_enabled` (default true network-wide), plus
`shorts_end_card_main_text` / `shorts_end_card_sub_text` /
`shorts_end_card_duration_seconds` for per-show overrides (useful
for Russian-language shows when they migrate to YouTube). Drift
guards in `tests/test_video_commands.py` under the "Shorts end-
screen CTA card" header.

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

### Cost-efficiency pass (July 29 2026)

Six changes that cut spend without touching what a listener gets. The
rule for the whole pass was **measure first** — every item below was
justified from committed data, not from reasoning about where waste
"should" be. Drift guards: `tests/test_cost_efficiency_pass.py`.

Context: the dashboard's tracked figure (~$29/30d) was roughly a third of
real spend. Adding the pieces it did not count — multilingual (~$38/mo)
and Grok Imagine (~$50-60/mo, only counted since July 28) — the true
total is ~$110-125/mo. The two largest lines were the two least measured,
which is why measurement leads this list.

- **Per-language OP3 measurement.** Multilingual is ~1/3 of spend and its
  audience was measured NOWHERE: the per-language enclosures carry the
  OP3 prefix, but `fetch_op3_stats.py` only ever resolved each show's
  English feed, so `api/op3_stats.json` had zero language-track entries
  and a language with no listeners looked exactly like a popular one.
  The fetcher now also resolves the 14 feeds the network actually pays to
  produce (scoped to each show's `multilingual.languages`, not the 44
  feed files on disk) into a separate `language_feeds` section — separate
  because every consumer iterates `shows` keyed by slug. The dashboard
  gains `multilingual.by_language` (downloads vs approximate cost) and
  per-show `audience_by_language`. **This is a decision instrument, not a
  saving:** after 2-4 weeks, a language reading zero across several weeks
  is a candidate to switch off in the show YAML. Today's split is FR
  ~$20/mo (7 shows), RU ~$13/mo (4), ZH ~$8/mo (3); RU feeds @NerraRU and
  earns its keep regardless, ZH has no channel and no directory listing.
- **16:9 scene generation follows the render.** Shorts-only policy days
  still generated 4 fresh 16:9 Grok Imagine scenes, but those feed only
  the long-form slideshow, its thumbnail, and the gallery — Shorts use
  their own 9:16 set. On a shorts-only day for a show with no
  video-podcast feed, three of four paid images were never seen. Now 1
  (thumbnail base + gallery contribution); the 9:16 set is untouched, and
  `video_podcast.enabled` shows still get all four because they render
  long-form regardless of tier. ~$0.06/episode on tier-C shows.
- **xAI search-tool spend is counted.** Server-side `x_search` /
  `web_search` bill per SOURCE consulted; the Responses path returned
  only text, so every search-fetching show under-reported its spend
  (flagged as uncounted by the July 24 pass, still missing after the July
  28 cost fix). `digests/xai_grok.py` accumulates usage per process — the
  fetch layer has no tracker reference — and run_show drains it into the
  episode's credit file via `engine.tracking.record_search_usage`. Rate
  is `SEARCH_COST_PER_SOURCE` ($0.025), env-overridable with
  `XAI_SEARCH_COST_PER_SOURCE`. Also wired `record_render_seconds`, which
  the July 28 pass shipped with no caller.
- **Single-pass long-form render is now the default** (was opt-in behind
  a repo variable). A/B on both production shapes at 1920x1080: uniform
  stills 24.6s -> 16.2s (-34%), chapter-schedule + burned-in captions
  22.3s -> 17.2s (-23%), with outputs equivalent — identical duration,
  frame count, geometry and codecs, mean pixel difference < 0.3/255 at
  every sampled timestamp, identical scene timeline, matching brand pill
  / URL pill / caption rendering. `NERRA_SINGLE_PASS_RENDER=0` forces the
  legacy path, which also remains the automatic fallback on any fused-
  command failure. The escape hatch now covers the RU/FR dub renders too.
  Render-only, no audio — outside landmine #17.
- **The podcast-side expansion retry is off** wherever a digest-side
  lever exists (11 shows). See the superseded note in the June 2026
  network-pass section above for the measurement. **A/B-listen the first
  post-merge episode on a show that used to fire it** — when the retry
  fired, its output was what shipped.
- **`CLAUDE.md` trimmed ~185 KB -> ~124 KB** by moving the dated per-show
  quality-pass narratives verbatim to
  [`docs/show_review_history.md`](docs/show_review_history.md), keeping
  each show's structural facts plus a new "Live constraints" block for
  the rules that still bind (Colossus/Anthropic is real, length is
  digest-side only, de-seed by shape, the grok-4.3 plateau, MIT not
  live-trading ready). This file is loaded in full at the start of every
  Claude Code session and replayed across the agentic loop, so its size
  is a per-session cost on all future work — the June 2026 token review
  found exactly this pattern was the network's largest Anthropic line
  item before the review agent moved to Grok.


### Funnel instrumentation + RU SpaceX pilot + Shorts motion A/B (July 30 2026)

Three connected pieces answering the July 18 audit's central finding
(world-class factory, funnel is the product gap). Full doc:
[`docs/funnel.md`](docs/funnel.md); drift guards:
`tests/test_funnel.py`, `tests/test_shorts_ab.py`,
`tests/test_ru_spacex_pilot.py`.

- **Instrumentation.** [`engine/funnel.py`](engine/funnel.py) is now the
  ONLY builder of funnel URLs / campaign ids / capture tags (see the
  rule at the top of this file). Nightly
  [`scripts/build_funnel.py`](scripts/build_funnel.py) joins
  youtube_stats + op3_stats + ga4_stats + buttondown_stats into
  **`api/funnel.json`** — four stages (reach → click → visit → capture),
  per show / channel / campaign / A-B variant, plus a dashboard card.
  `fetch_ga4_stats.py` gained the `sessionSource/Medium/CampaignName`,
  landing-page and `newsletter_signup` conversion reports (without the
  campaign dimension nothing on the site could be traced to a video);
  `fetch_buttondown_stats.py` gained per-tag counts (the bare total
  cannot attribute anything). **Honesty rules are load-bearing:** an
  unmeasured stage reports `null`, never `0`; rates stay `null` below a
  30 denominator; unparseable GA4 campaigns are summed under
  `unattributed` with an `attribution_coverage_pct`, so the report never
  implies it sees everything.
- **RU SpaceX pilot.** @NerraRU is the network's highest-reach surface
  (~25,800 views/30d vs ~13,800 EN) and every one of its Shorts pointed
  at the bare English homepage. Now: `funnel.destinations.ru` →
  **`ru/spacex.html`** (generated by `generate_ru_landing_page` from
  `templates/ru_landing.html.j2`, path driven off the SAME YAML field the
  descriptions link, so page and link cannot drift), one Russian ask
  («Хроника SpaceX», a Sunday letter), footer show-picker suppressed via
  `hide_footer_subscribe` (default false → every other page unchanged),
  and the letter is actually sent by
  [`scripts/send_ru_spacex_weekly.py`](scripts/send_ru_spacex_weekly.py)
  + `ru-spacex-weekly.yml`. Captures carry `list` + `source` through the
  Worker's **server-side allow-list** (`resolveSubscribeTags`) — the
  client names a list, the server owns the tags. Also fixed: the RU
  funnel comment posted NOTHING on most days because @NerraRU is
  shorts-only and `long_url` was empty; it now falls back to the lander.
- **Shorts motion A/B.** SpaceX Short #1 stays stills (control), Short #2
  renders over Grok Imagine video ([`engine/shorts_ab.py`](engine/shorts_ab.py)
  + `build_short_video(clip_paths=…)`), same episode/audio/channel/day.
  **Not a revival of `video_clips_enabled`** (still false everywhere —
  that was the retired long-form pilot): bounded to ~3 clips on one 35 s
  Short, a hard `shorts_ab_max_cost_usd` checked BEFORE each request, and
  a fallback that ships stills AND RECORDS stills (a treatment arm
  containing disguised control episodes is worse than no experiment).
  ~$1.05/ep ≈ $32/mo — **read it and end it.**
  [`scripts/build_shorts_ab_report.py`](scripts/build_shorts_ab_report.py)
  → `api/shorts_ab.json` refuses to compare below 14/arm and reports a
  95% CI (Welch), not a p-value. Render/metadata-only — outside landmine #17.

### Adaptive YouTube publishing policy (July 2026)

Publish volume/format now adapts to what each channel actually watches
(full doc: [`docs/youtube_feedback_loop.md`](docs/youtube_feedback_loop.md)
"Adaptive publishing policy"). Nightly `scripts/update_youtube_policy.py`
(no secrets; runs right after the title-hint step) turns
`api/youtube_stats.json` into **`api/youtube_policy.json`**: per
show × channel tiers from 14-day views-per-day velocity (A = long + 2
Shorts, B = long + 1, C = shorts-only, D = probe; long on at
`long_vpd ≥ 1.0`, 2 Shorts at `short_vpd ≥ 4.0`, Shorts NEVER 0 — they're
the recovery signal; <4 in-window videos of a kind holds that dimension).
**Hysteresis:** the active tier flips only after the same computed tier on
2 consecutive runs; cold-start actives are `SEED_TIERS` hardcoded from the
2026-07-14 analytics (RU long-form seeded off everywhere). Consumers via
`engine.youtube_policy.resolve_publish_plan`: `run_show._publish_youtube`
(EN + native-RU shows; a shorts-only tier skips the long-form render/upload
while Shorts + the shared thumbnail still ship; Shorts raise to 2 only with
`shorts_start_mode: smart`; metrics `yt_policy_tier` /
`yt_policy_long_skipped` / `yt_policy_shorts`) and
`engine.ru_dub.publish_ru_dub` (@NerraRU dubs; the sweep's done-check now
also counts an uploaded Short). Best-effort by contract: missing policy
file / absent slug / `youtube.adaptive_publishing: false` (new field,
default true) = exact legacy YAML behavior. The policy never edits YAML
files at runtime and never touches audio (outside landmine #17). Drift
guards: `tests/test_youtube_policy.py`.

**July 18 2026 growth pass** (review:
[`docs/reviews/youtube_growth_review_2026_07_18.md`](docs/reviews/youtube_growth_review_2026_07_18.md);
drift guards: `tests/test_youtube_growth_pass.py`,
`tests/test_shorts_selector.py::TestFillToRequested`): post-policy
verification found tier gating exact, RU titles fixed, and RU/EN Shorts
massively outperforming long-form — but tier-A shows chronically
under-shipped Shorts (FF 1-of-2 on EVERY July episode). Shipped:
**fill-to-requested** in the multi-Shorts selector (sub-threshold windows
ship rather than fewer Shorts; `qualified` flag + `shorts_fill_modes`
metric; FF threshold 3.5 parity); **RU multi-Shorts** (policy may raise to
2 — RU Shorts are the network's best surface, spacex-RU short_vpd 30);
**subscriber tracking** (analytics schema v2: per-video subscribersGained,
channel snapshots + `api/youtube_channel_history.json`, dashboard card,
subs-blended title hints — subscribers were previously tracked nowhere);
**title bundle** (one Grok call → long titles + 2-4-word ALL-CAPS
thumbnail punch text + per-window Short titles; empty fields = exact
legacy fallbacks; opt-outs `thumbnail_punch_text` / `optimized_titles`);
**auto-comments** (`engine.youtube.post_video_comment` — long-form posts
the pinned-comment template, Shorts post the full-episode funnel link, RU
only when a RU long exists; API can't pin, operator pins in Studio;
opt-out `auto_comment`); **channel-specific long-form floor**
(`LONG_VPD_FLOOR` en 1.0 / ru 2.0 — RU longs earned ~9% retention);
**gallery-retention style tags** now mined from image prompts (per-show
doc-frequency boilerplate filter). Operator declined publishAt scheduling
(uploads stay immediate). All render/metadata-side — outside landmine #17.

**July 22 2026 scoring pass** (review:
[`docs/reviews/youtube_review_2026_07_22.md`](docs/reviews/youtube_review_2026_07_22.md);
drift guards: `tests/test_youtube_policy.py::TestShortsCountFollowsData`,
`tests/test_youtube_growth_pass.py::TestSmartShortsNetworkWide`): scored the
07-18 rollout list — fill-to-requested HIT (Tesla/FF/SpaceX all 2/2 since
the fix), Monday probe HIT (MIT Ep112, Mon 07-20), FF-RU long demotion HIT;
two MISSes fixed: (1) **`shorts_per_episode` now follows the computed
`short_vpd`, not the tier letter** — `TIER_SETTINGS[active]` had pinned
shorts-only (C) shows to 1 Short, discarding the computed "-> 2 Short(s)"
(RU spacex/tesla/FF sat at short_vpd 18-45, the network's hottest surface,
shipping half the allowed Shorts; policy regenerated, they get the 2nd
Short now); (2) **`api/youtube_channel_history.json` was never committed**
(nightly add-paths whitelist gap — 4 runs silently dropped the snapshot;
path added, file seeded en 207 / ru 61 subs, dashboard `_delta_7d` falls
back to the day_series net gain while history is <7 days old). Also:
**smart Shorts start network-wide** — 7 enabled shows (OV, M&A, EI, PT, UC,
FP, PR) still resolved `voice` (every Short opened on the 10 s intro) and
MAB/FPD's smart mode fell back 6/6 at the 5.0 default threshold; all
enabled shows now pin `smart` + fleet threshold 3.5 (guarded). And
`record_youtube_outcomes` finally persists `shorts_fill_modes` /
`thumbnail_punch_text` / `yt_comments_posted` (the 07-18 layers had shipped
invisibly — verify punch + comments in metrics from 07-23). Subscriber
attribution insight: EN long-form converts subs best (24 vs 15 EN-short /
10 RU-short of 56 tracked) — long-form cuts stay velocity-gated, never
blanket. All policy/metadata-side — outside landmine #17.

**July 30 2026 retention pass** (drift guards:
`tests/test_intros.py`, `tests/test_shorts_selector.py::TestShortsClipLength`,
`tests/test_youtube_policy.py::{TestShortsSupplyLadder,TestMaxShortsCeiling}`,
`tests/test_ru_dub.py::TestClauseTrim`):

- **Every episode now opens on its hook** (AUDIO — A/B-listen per
  landmine #17). Ten seconds of theme music played alone, then
  `build_intro_line` emitted a ~35-word greeting with the date, so the
  first fact arrived around second 28. Long-form median retention was
  10.7% EN / 6.3% RU with average view durations of 18-85 s on 5-13
  minute videos; Shorts, which skip the intro, run ~42% on the same
  audio. `build_intro_line` now emits one short identity line,
  `build_cold_open_spec` injects the shared cold-open rules into all 15
  podcast prompts (no example sentence — de-seed by shape), the prompts
  put `{hook}` before `{intro_line}`, and `voice_intro_delay` is 0 with
  `intro_duration` 3 network-wide. **Music still plays from t=0 and the
  sidechain holds it at the same level under the opening line as
  mid-episode (-31.7 dB either side, verified by render), so this is a
  cold open in structure, not a bare one in sound.** Three shows keep a
  short `identity_tail` / `identity_template` because their line carries
  something load-bearing: DP Pod names both hosts, Age of AI discloses
  its AI host, and the Russian shows would otherwise be handed English.
- **Shorts run 35 s** (was 55 default / 40 on five shows). Median Short
  holds 21 s (n=348, 90-day window), so length mostly decides what
  percentage that is: 38% at 55 s, 60% at 35 s. The dataclass default and
  the four `getattr` fallbacks moved too — `ru_dub` / `lang_dub` /
  `youtube_shorts` each resolve through one, so a stale default would
  ship long Shorts on the dub channels only.
- **Shorts supply ladder gained a 3-Short band** at 20 vpd (`SHORT_VPD_BANDS`
  + `shorts_for_vpd`). RU spacex 62.3 / FF 60.5 had the same supply as
  RU MIT 4.9. Two silent caps had to go first: `build_policy` carried a
  second copy of the threshold rule (logged "-> 3" and wrote 2), and
  `ru_dub`/`lang_dub` each had a local `min(2, ...)` — and the band's
  members are RU dubs, so those literals would have made it a total
  no-op. The ceiling is now `engine.youtube_policy.MAX_SHORTS_PER_EPISODE`,
  enforced in `resolve_publish_plan`.
- **Dub Short titles trim to a clause** (`_clause_trim`). 26% of published
  FR Short titles ended on a dangling preposition (RU 5%, EN 1%) because
  the title is cut from the translated LONG title at 70 chars and French
  runs ~15-20% longer than its English source. Per-language stop-word
  tails, a 55%-of-budget floor, and an unregistered language stays a
  plain word trim.

### Testing

```bash
pytest                             # Run all tests
pytest tests/test_utils.py         # Pure function tests (AST extraction)
pytest tests/test_rss.py           # RSS feed validation
pytest tests/test_audio_commands.py  # ffmpeg command structure tests
pytest tests/test_integration.py   # Pipeline integration tests
```

Tests use AST extraction + `exec()` to load functions from show scripts because
`tesla_shorts_time.py` has a `SystemExit` guard preventing import.

**Phase 1 hardening guards (May 2026):** the network-evolution roadmap's first
phase added safety nets that the `run-show.yml` smoke step now runs on every
episode:

- `tests/test_generator.py` — the LLM-call path (`load_prompt` incl. the new
  shared-snippet include mechanism, `_call_grok` request/response shaping,
  refusal detection, fallback-model resolution). Catches a breaking Grok
  request/response change without spending credits.
- `tests/test_show_memory.py` — pins `engine.tesla_memory`'s load/save/build
  contract (and the first-run copy-isolation fix) *before* Phase 3 generalizes
  it to other shows via `engine/show_memory.py`.
- `tests/test_prompt_fidelity.py` — every show's prompts exist, are non-empty,
  and render without a malformed-brace crash.
- `tests/test_episode_validity.py` — the latest committed digest per show meets
  a conservative word floor and isn't a refusal.
- `tests/test_pipeline_safety.py` — the three safety scripts below.

### Code Style

- No linter configured; scripts are large single-file programs
- Functions are defined inline (not imported), which is why we're extracting
- `logging` for all output; `sys.stdout` handler
- `pathlib.Path` for all file operations
- `tenacity` for retry logic on API calls

### Prompt composition + pipeline safety scripts (Phase 1, May 2026)

- **Shared prompt snippets.** `engine.generator.load_prompt` resolves
  `<<include: relative/path.txt>>` directives (relative to the including
  prompt's dir, recursive, cycle/depth-guarded) **before** `{placeholder}`
  substitution. Canonical snippets live in `shows/prompts/_shared/`. The
  mechanism is **opt-in**: a prompt with no directive renders byte-for-byte as
  before, so existing prompts are unchanged. Do NOT bulk-rewrite prompts to use
  includes without re-running `test_prompt_fidelity.py` + A/B listening (it
  changes generated output). See `shows/prompts/_shared/README.md`.
- **Fail-loud safety nets** (all *loud-but-non-blocking by default*; pass
  `--strict` to hard-fail in a dedicated guard job):
  - `scripts/backfill_content_lake.py` — evaluates the rebuilt lake and emits a
    GitHub `::error::`/`::warning::` annotation when it's empty/thin (was a
    silent failure mode that broke dedup/recaps/search).
    **July 24 2026 orchestration pass** (drift guards:
    `tests/test_memory_lake_expansion.py::TestLakeOrchestration`): the lake
    ENGINE was healthy (1,200+ episodes, 1.5M words, FTS working) but three
    orchestration bugs hid it. (1) The run-show **finalize job** rebuilt the
    public search index on a fresh checkout WITHOUT backfilling the
    gitignored lake — every episode (~13×/day) committed a zero-episode
    `site/data/search-index.json`, so site search served 0 results most of
    every day (nightly repaired it once; the next morning wiped it again).
    Finalize now backfills before `build_search_index.py`, and the index
    builder additionally REFUSES to overwrite a populated index with an
    empty one (loud `::warning::`, non-blocking). (2) **Nightly built the
    dashboard BEFORE the backfill**, so `api/dashboard.json` reported
    "lake: 0 episodes" every night (the mission-control card showed a
    permanent false empty-lake warning) — steps reordered. (3) Shows that
    don't produce run_show digests (**Age of AI**) never entered the lake;
    the backfill gained a summaries-JSON fallback importer so every
    published episode is searchable. The lake remains a rebuild-from-repo
    cache by design: committed `digests/**` are the durable store, the DB
    is derived — safe to delete, cheap to rebuild (~30 s), reliable for
    future content products via `query_show_range` / `search_content` /
    `query_by_entity`.
  - `scripts/youtube_quota_preflight.py` — sums quota for YouTube-enabled shows
    and annotates when projected over the 10k/day budget (landmine #20). Wired
    as a preflight step in `run-show.yml`.
  - `scripts/post_run_summary.py` — positive heartbeat: composes an all-clear /
    cost / quota / RSS-freshness line from `api/dashboard.json` and POSTs to
    `NOTIFICATION_WEBHOOK_URL` (clean no-op when unset). Wired into the finalize
    job.
  - `scripts/retitle_youtube_videos.py` — repairs transcript-fragment titles on
    ALREADY-PUBLISHED videos. Before the July 18 2026 title bundle, a Short's
    title was the raw opening text of its clip: 11% of Shorts published before
    that date carry a fragment title against 1% after. The pipeline was fixed
    forward; the back catalogue never was, and those videos are still live and
    still the first thing a new viewer sees. Rebuilds the title from the
    episode's DIGEST HEADLINES (the Short's own stored `hook` IS the fragment
    for exactly the videos this repairs, so it can never supply the
    replacement; sibling Shorts take different headlines so one episode does
    not produce four identically-titled clips). **Dry run by default** —
    `--apply` is required to write. Run it from Actions ("Retitle YouTube
    Videos"), not a laptop: the YouTube credentials live there, and a local run
    prints its plan then writes nothing. ~51 quota units per video. 31 fixable
    at last count.

### Growth & trust surface (Phase 2, May 2026)

Additive web/distribution enhancements (source-only — generated HTML is
regenerated by the pipeline's finalize `--blogs` step, so these propagate
site-wide within a day without committing hundreds of HTML files):

- **AI-transparency badge.** Reusable `ai_badge(path_prefix, is_ru)` macro in
  [`templates/_macros.html.j2`](templates/_macros.html.j2), wired into blog
  posts and show pages, linking to `ai-disclosure.html`. Turns the AI question
  into a trust signal. Drift guards assert the wiring.
- **PodcastEpisode JSON-LD completed.** The blog-post `PodcastEpisode` block
  previously rendered empty `url`/`datePublished`/`contentUrl`/`transcript`
  (the vars were never supplied). `engine/blog.py` now passes `page_url`,
  `date`, `audio_url`, `transcript_url`, and the template builds the block as a
  dict piped through `tojson` (always-valid JSON; `isPartOf` → PodcastSeries,
  `inLanguage`, optional members only when present; `name` prefers the episode
  hook over the show-name title fallback).
- **Transcript anchored.** The inline transcript `<section>` carries
  `id="transcript"`; the JSON-LD `transcript` points at `…#transcript`.
- **Share + attribution.** Blog share row adds Facebook + Email and tags every
  network link with per-source UTM (`utm_medium=share`) via the existing
  `with_utm` filter, so shared traffic is attributable.
- **Not done (deliberate):** per-episode OG images were deferred — generating
  hundreds of PNGs into git worsens landmine #1 (repo size); revisit via R2
  like the gallery. Live Buttondown subscriber count / referral need a runtime
  API dependency and were left out. Drift guards: `tests/test_phase2_growth.py`.

### Grok prompt + voice review (June 10, 2026)

All 49 show prompts + in-code prompts (outline/retry, weekly synthesizer,
episode reviewer, X fetch) reviewed against prompt-engineering practice —
canonical writeup: [`docs/prompt_review_2026_06_10.md`](docs/prompt_review_2026_06_10.md);
drift guards: `tests/test_prompt_quality_pass.py`. Voice/TTS config verified
consistent and deliberately untouched (landmine #17). Shipped:
`engine/utils.fix_phonetic_garbles` repair layer on every digest + script
("nassa" had shipped verbatim in a published transcript — bans alone don't
stop a known finite failure set); the X-post fetch prompt now requires
SUBSTANTIVE posts (emoji spam + a slur one-liner had flowed into prompts);
stale "ElevenLabs engine" claims removed from the 9 remaining podcast
prompts; MIT's residual "at least 2500 words" contradiction fixed; Tesla
digest selection rules unified (count-tier table vs judgment rule) and the
template's 🎙️ emoji removed; reviewer QUALITY_SCORE got calibration
buckets; the weekly synthesizer must ground cross-domain threads in actual
coverage; Tesla's system prompt now explicitly forbids filling gaps from
training-data knowledge. Deferred behind A/B (in the doc): few-shot
exemplars for prompts lacking one, converting ban-lists to rotation menus.

### Network-wide show quality pass (June 2026)

After the Tesla (#573) and Modern Investing (#574) flagship passes, the
same review ran across the other ten shows. Drift guards:
`tests/test_network_quality_pass.py`.

- **`engine/show_memory.py` inherited both Tesla memory bugs** (it was
  generalized from `tesla_memory` *before* the fixes). Theme mining read
  the narrative TEMPLATE every episode — "open questions" hit count 96 on
  Models & Agents, Fascinating Frontiers, AND Planetterrian — now
  digest-only with the shared `_THEME_STOPWORDS`; the three live histories
  were scrubbed. Narrative trackers were seeded May 29 with no program
  ever updated; `auto_update_narrative_from_digest` (ported from Tesla)
  now advances per-program "last covered on air" freshness each episode
  via `memory_post_generate`, and the status block gained the
  make-continuity-audible callback wording.
- **`podcast_expand_below_target: true`** added to the eight chronically-
  short shows (M&A, FF, PT, MAB, Env Intel, Финансы Просто, Unintended
  Consequences, First Principles — all were ≥50% below target, several
  100%). Models & Agents also got an explicit `min_podcast_words: 1500`
  (was relying on the implicit default).
  **SUPERSEDED 2026-07-29 — this flag is now `false` on the 11 shows that
  have a digest-side lever.** Measured over 901 committed episodes, 81%
  still shipped BELOW target *with* the retry running (Tesla 96.7%, M&A
  95.2%): it fires on nearly every episode and almost never reaches the
  goal, because the ceiling is the DIGEST. It also pads by
  paraphrase-duplication (the July 28 pass had to add
  `_dedup_expansion_sentences` to strip its near-duplicates), so what it
  did ship was the weaker copy — and the July 18 playbook had already
  banned podcast-side length levers network-wide. Only `env_intel` and
  `finansy_prosto` keep it, because they have no digest lever yet;
  give them one before switching theirs off. Drift guard:
  `tests/test_cost_efficiency_pass.py::TestLengthLeverPolicy`.
- **Hook-led X teasers network-wide**: Omni View / FF / Planetterrian's
  hardcoded teasers and the generic fallback (used by Unintended
  Consequences) now lead with the episode hook + link the episode blog
  post, matching Tesla/MIT. Models & Agents/MAB/Env Intel/Russian shows
  don't post to X (unchanged).
- **Boilerplate-tic bans** (prompt edits — A/B-listen per landmine #17):
  M&A "This development sits within the ongoing…"; FF "you know what's
  fascinating / blew my mind" deep-dive openers; PT "this development
  fits the tracked program on X" (ran 6×/episode); Omni View's
  every-story "the strongest case for X / for Y" template (now rotates
  three framings, "strongest case" ≤1×/episode); UC "That wraps today's
  case" closer. Plus: MAB requires ≥2 concrete "try this" experiments;
  Env Intel Compliance Brief required even on thin-news days; Финансы
  Просто requires 3-4 practical tips (was 2 → chronic shortfall).
- **RSS channel descriptions rewritten** as value props for the listing
  pages: M&A, FF, MAB, Omni View (Steel Man), Env Intel (odd-weekday
  cadence + Compliance Brief), Unintended Consequences. PT and the two
  Russian shows already had strong descriptions (kept).
- **Topic-queue restock** (the narrative shows' critical operational
  risk): Unintended Consequences +14 → 38 unproduced (~7.6 wk runway, was
  ~4.8); First Principles +12 → 27 unproduced (~3.9 wk, was ~1.3 and
  about to dry up), preserving the concrete/opportunity alternation.
  **July 24 2026 — restocks are now AUTOMATED** (drift guards:
  `tests/test_queue_restock.py`): `.github/workflows/restock-topic-queues.yml`
  (daily 13:37 UTC + dispatch, `force` input) runs
  `scripts/restock_topic_queues.py` — trigger-gated (FPD <4wk, UC <5wk;
  refills to ~8wk) Grok generation against per-show restock prompts
  (`shows/prompts/*_restock.txt` — full queue history injected for dedupe,
  category balance for FPD's alternation, an explicit never-invent honesty
  rule since briefs become episodes). Validation rejects thin briefs, bad
  categories, id dupes, and fuzzy near-duplicate titles vs the ENTIRE
  history (produced included); existing entries are never modified; the
  workflow re-runs `TestNarrativeQueueRunway` BEFORE committing, so the
  runway floors (3.0/4.0wk) are now the alarm that the AUTOMATION broke,
  not a manual chore. Age of AI's deliberately-empty queue is not
  registered and must never be. Generated topics sit unproduced for weeks
  — prune any weak ones directly in `shows/topic_queues/*.yaml`.
- **Финансы Просто YouTube category** fixed 25 (News) → 27 (Education).
- **Operator items (not code):** localize the Russian shows' spoken AI
  disclosure (still English on the Olya voice — A/B per #17); decide
  First Principles distribution-on after the queue/length fixes settle
  (review recommends waiting to ~Ep15); confirm X handles for the
  X-enabled shows so the follow CTA can be set.

### Network editorial review (July 2026)

Full editorial pass over every transcript in the 2026-06-18 → 07-02 window
(~150 episodes, all 13 shows — fit, interest, content quality, positioning).
Canonical writeup:
[`docs/reviews/network_review_2026_07_02.md`](docs/reviews/network_review_2026_07_02.md);
prediction verdicts + new entries in every per-show ledger
([`docs/reviews/ledger/`](docs/reviews/ledger/) — new ledgers for
privet_russian, modern_investing, network). Four cross-cutting classes:
(1) **number/name garbles in flagship positions** — the comma-blind
currency/ordinal formatter shipped "fifty-nine dollars,990"-class hooks on
Tesla/SpaceX (fixed, `assets/pronunciation.py`); (2) **guard/retry mechanisms
degrading the audio they protect** — the missing-closing guard's literal
signature match double-spoke MAB's closing 5/15 (fixed: fuzzy match in
`engine/pipeline.py`) and the expand-below-target retry pads by
paraphrase-duplication (fixed: near-duplicate sentence stripping);
(3) **third-generation seeded-template convergence** (OV "Both sides
agree…" 12/12, EI "There's a nuance here…" 6/6, MAB/FP/MIT/SpaceX tics) —
ALL prompt de-seeds are PROPOSED-not-applied pending operator A/B (landmine
#17); meta-lesson: de-seed by shape, never with a quotable example;
(4) **same-day sibling overlap** — PT astronomy fetch filter (the pass's
highest-leverage fix), FF lookback 2→7 + ephemeris filter, SpaceX junk-title
filter. Also shipped: EI Closing/Teaser-before-body chapter reorder, MIT
voided phantom trades (honest 37-trade record + review-once), PR vocab
no-reteach 8 + WOTD never-repeat + theme gap, network-wide Source-line scrub
(FP scaffold leak), UC/FPD queue hygiene, Tesla second-brand-normalizer
completion, and `review_snapshot.py` Unicode + missing-final-Closing fixes.
Operator items: three same-day double-publishes + SpaceX's silently missed
June-28 recap (scheduler forensics).

### Network goals & differentiation audit (July 18, 2026)

Operator-requested whole-network review — canonical writeup:
[`docs/reviews/network_review_2026_07_18.md`](docs/reviews/network_review_2026_07_18.md).
Verdict: the factory is world-class (100% run success, ~90 eps/week in 5
languages at ~$35-40/mo) while the funnel is the product gap (3,070
downloads/30d, 3 newsletter subs); differentiation is TOPICAL AUTHORITY
(Tesla+M&A+SpaceX = 53% of downloads), and the two most differentiated bets
(DP Pod, Age of AI) have no market feedback loop. Shipped (all
code/metadata-only): **closing-is-final chapter invariant** in
`engine/chapters.py` (the 07-16 rotating network outro's sibling-show plugs
were stolen by un-anchored body markers AFTER the closing — Tesla Ep544
"First Principles" at 642s, MIT Ep104 "Investor Education"; terminal signal
is the closing TITLE set, not the `where: end` anchor, because EI anchors
only its Teaser); **dp_pod Network-pick rotation memory**
(`_recent_network_picks` — FF was the pick 5/10 with a fixed host+frame); **July 20 2026 Ep016 name-swap fix + banter pass (operator listened:
  hosts signed off as each other; wants human flow + comedic banter):**
  the LLM rotated the supplied closing's speaker labels to dodge a
  same-host boundary (turn before the closing and the closing's first
  line were both DAN's), so Dan's voice said "I'm Patrick Novak" on air.
  Two-layer fix: `_fix_self_introduction_labels` in
  `engine/tts_dialogue.py` relabels any turn whose self-intro names the
  OTHER host (deterministic; joint intros untouched; verified self-healing
  on the real Ep016 script), and the podcast prompt forbids closing-label
  rotation outright. Flow: Ep014-016 shipped ZERO exclamations, ZERO
  voice tags, 12-26% one-liners against the DELIVERY asks — enforcement
  moved INTO the Positive Papers segment spec (per-story 3+ turn volley +
  earned exclamation) and a COMEDY block (2-3 character-driven beats,
  one callback, device rotates daily, no catchphrases). Prompt edits
  change shipped audio — A/B-listen per landmine #17. Drift guards:
  `tests/test_tts_dialogue.py::TestSelfIntroductionRelabel`,
  `tests/test_dp_pod_show.py::TestEp016NameSwapAndBanter`;
**dashboard voice-baseline fix** (stale ElevenLabs RU baseline flagged
FP/PR/Age-of-AI as drift on every build; now Olya `0b875ae2` + sanctioned
`ara`); **snapshot fetch-filter leakage counter** (scored three long-pending
filter predictions immediately: SpaceX/Tesla clean, FF ephemeris still
leaking 3/10 → reopened); **playbook category rules** from the 15-ledger
meta-review (podcast-side length levers formally banned network-wide via
`do_not_retry` — ~10 misses vs 1 hit; de-seed-by-shape + rotation memory
required; conditional predictions banned; two-miss escalation; ledger entry
required for every prediction-bearing pass). Verified with new data: the
07-16 denoise chain IS engaged in shipped audio (re-denoising shipped
episodes removes ~0 dB). P0 operator item: **FP/PR publish off-schedule via
the daily-audit retry path** — CRON_MAP/Worker say Monday-only,
`review_episodes.py` says even days, FP's description says daily; 8
unplanned episodes in one week; pick a cadence and align all three. A/B
proposals (NOT applied): FP double-seeded templates (100% saturation), MIT
seeded transition, PT takeaway tic, PR secret opener, FF ephemeris
digest-scope bullet. Drift guards:
`tests/test_chapters.py::TestClosingIsFinal`,
`tests/test_dp_pod_show.py::TestNetworkPickRotationMemory`,
`tests/test_review_agent.py::{TestSnapshotFetchFilterLeakage,TestDashboardVoiceBaseline}`.

### Website review (June 10, 2026)

Full public-site review — canonical writeup:
[`docs/website_review_2026_06_10.md`](docs/website_review_2026_06_10.md);
drift guards: `tests/test_website_quality_pass.py`. Implemented (source-only,
propagates via nightly regen): absolute `og:image` default in
`templates/base.html.j2` (the relative default broke share previews on every
page without an explicit `og_image`); `noindex` on the 404 template; footer
Gallery link (287 CC-licensed images were reachable from nowhere);
`MIN_SOCIAL_PROOF_SUBSCRIBERS` 100→50. Deferred with rationale in the doc:
blog-index pagination, hero inline-CSS extraction, homepage gallery rail,
Russian brand-page translations, inline-style cleanup, contrast audit.
Rejected after verification: nav-cover empty alts (correct WCAG — visible
text adjacent), search loading state (already exists), blog next-episode nav
(already exists).

### YouTube pipeline pass (June 10, 2026)

Full video-pipeline review — writeup:
[`docs/youtube_review_2026_06_10.md`](docs/youtube_review_2026_06_10.md);
drift guards: `tests/test_youtube_quality_pass.py`. Headline: the
**silent config-drop class** — `_build_nested` discarded YAML keys the
dataclass didn't declare (now warns loudly + CI guard). Casualties fixed:
`shorts_min_score_threshold` (Tesla's 3.5 never applied anywhere — the
smart Shorts selector fell back to the voice start almost daily; the
single-Short path additionally never passed a threshold at all),
five NewsletterConfig fields (`requires_financial_disclaimer` was
ALWAYS False on the dataclass path), and `_defaults.yaml`'s network-wide
`min_audio_duration: 180` (dead inside the `audio:` block; now
top-level). Viewer-facing: long-form slideshow scenes now CYCLE (≤25 s
per image hold vs 168 s on Ep505) at zero added Grok-Imagine cost;
`channel: ru` without `YOUTUBE_REFRESH_TOKEN_RU` warns loudly;
`shorts_captions_path` metric records ASS vs SRT-fallback. Rejected with
reasons in the doc: bitrate floor, more images, `-preset slow`.

### Scheduled Show Review Agent (June 2026)

The manual quality-pass workflow (Tesla #573/#576, MIT #574, network #575)
is now automated and reproducible. A scheduled Claude Code agent
([`.github/workflows/show-review.yml`](.github/workflows/show-review.yml),
Tue + Fri 07:00 UTC) reviews ONE target per run — the least-recently-
reviewed of the 13 shows + a cross-cutting `network` target, per
[`docs/reviews/review_state.yaml`](docs/reviews/review_state.yaml) /
`scripts/pick_review_target.py` — following the codified playbook in
[`.claude/commands/review-show.md`](.claude/commands/review-show.md)
(same P0/P1/P2 method as the manual passes; transcripts as ears; hard
guardrails baked in). Output is always a **draft PR** on branch
`agent/review-<slug>-<YYYYMMDD>` with prompt/audio changes called out
under "⚠️ A/B-listen required" — the operator's merge is the ship gate,
so landmine #17 is preserved. New review docs go to `docs/reviews/`;
merging a review PR advances the rotation. Run `/review-show <slug>` in
any Claude Code session for a manual pass with identical methodology.
The loop is **recursive, not just scheduled**: every review appends to a
per-target ledger ([`docs/reviews/ledger/`](docs/reviews/ledger/)) with
measurable `predictions:` the NEXT review must score (`hit`/`partial`/
`miss` — a miss reopens the problem) and a `do_not_retry` list built from
operator verdicts (closed-unmerged review PRs = rejections; git reverts
of review commits = failed A/B listens — never re-proposed). Reviews
start from `scripts/review_snapshot.py <slug>` (deterministic
length/tic/chapter/cost/OP3 numbers — the cross-episode repeated-phrase
detector finds boilerplate tics mechanically). When the agent edits a
prompt and `GROK_API_KEY` is present it regenerates a digest via
`run_show.py <slug> --test` and pastes before/after OUTPUT excerpts into
the PR. `network` runs additionally meta-review the ledgers and may
propose edits to the playbook itself (drift guards pin the safety
language). The Daily Audit also dispatches an out-of-rotation review via
`scripts/dispatch_quality_reviews.py` when a show ships editorial-
critical issues (max 1/day, skips shows with an open review PR;
`daily-audit.yml` gained `actions: write` + `pull-requests: read` for
this). A review PR opening pings `NOTIFICATION_WEBHOOK_URL` (no-op when
unset). Setup + tuning: [`docs/REVIEW_AGENT.md`](docs/REVIEW_AGENT.md).
Drift guards: `tests/test_review_agent.py` (rotation covers every show —
scaffolded new shows must be added to the state file; playbook keeps its
safety language; ledger schema; snapshot + dispatcher logic).

**June 2026 — scheduled job migrated to Grok (cost).** A token-usage review
found the scheduled review agent was the network's largest Anthropic line item:
~$6-9/run of Claude Opus 4.8 (~$1,500-2,000/yr), dominated by cache-reads of
this 125 KB `CLAUDE.md` replayed across a long agentic loop and amplified by the
daily-audit out-of-rotation dispatches (the podcast pipeline itself has zero
Anthropic spend — all Grok). `show-review.yml` now runs
[`scripts/run_show_review.py`](scripts/run_show_review.py) on **Grok-4.3** (xAI;
`GROK_API_KEY`, already used everywhere else) instead of the Claude Code GitHub
Action — ~$0.30/run, a >95% cut; the `ANTHROPIC_API_KEY` secret is no longer
needed by the scheduled job. The runner gathers context (snapshot + ledger +
last ~10 transcripts), makes ONE Grok call with the playbook as its system
prompt, writes the review doc + ledger entry + advances rotation, and opens the
draft PR. One deliberate behavior change: it **proposes** prompt/audio edits in
the PR body under "⚠️ A/B-listen required — NOT applied" rather than auto-editing
them — which *strengthens* landmine #17 (nothing audio-affecting is
auto-committed). The fully-autonomous Claude path stays on demand: run
`/review-show <slug>` manually in a Claude Code session for a deep, multi-file
pass. The ledger writer appends by **text-splice** (never reserializes the
existing file) because three committed ledgers contain unquoted `: ` inside list
items and `safe_dump` line-wrapping can corrupt long plain scalars.

### Recursive narrative memory generalized (Phase 3, May 2026)

The content moat: Tesla's narrative-memory pattern generalized so other shows
become longitudinal chronicles, not disposable daily recaps.

- **`engine/show_memory.py`** — generalized engine (narrative tracker +
  performance signals + auto-mined themes), parameterized by a `MemoryConfig`
  (slug, label, file_prefix, seeded `default_programs`, `theme_keywords`).
  `SHOW_MEMORY_CONFIGS` registers **Models & Agents, Fascinating Frontiers,
  Planetterrian** (MIT already has its own `investment_tracker`; Tesla keeps
  its bespoke `engine/tesla_memory.py` — a future cleanup could fold Tesla into
  this engine).
- **Flag-gated, single placeholder.** Prompts carry one
  `{narrative_memory_section}` placeholder; the show's thin hook
  (`shows/hooks/<slug>.py` → `show_memory.memory_pre_fetch/`
  `memory_post_generate`) injects the composed section when
  `config.memory_enabled` (new YAML flag, default false) is true, and an empty
  string otherwise — so **disabled is a true byte-for-byte no-op**.
  `run_show.py` `setdefault`s the key so a hook-load failure can never KeyError.
- **Public "story tracker" pages.** `generate_narrative_page(slug)` +
  `templates/narrative_page.html.j2` render `<show>-narrative.html` from the
  committed `digests/<slug>/<slug>_narrative_tracker.json`; show pages link it
  via a "Story Tracker" button. Sunday recaps inject the narrative block too.
- **Seeded conservatively** (factual program status, no speculative claims);
  themes accrue automatically from each digest. Operator can disable any show
  with one YAML flag (`memory_enabled: false`) — per landmine #17, A/B-listen
  before trusting the output change. Drift guards: `tests/test_phase3_memory.py`
  (+ `tests/test_show_memory.py` still pins the untouched Tesla module).
- **July 24 2026 expansion + hygiene pass** (drift guards:
  `tests/test_memory_lake_expansion.py`): **MIT, DP Pod, and Age of AI**
  joined the registry (all 8 non-Tesla content pillars now have memory;
  Tesla stays bespoke). MIT's narrative layer tracks MARKET NARRATIVES
  (rate cycle, AI-infra trade, Canadian wealth mechanics, crypto, the
  practice-portfolio story arc) — the bespoke `investment_tracker`
  trade/lesson ledger is untouched and stays authoritative for results.
  DP Pod tracks progress arcs (clean-energy build-out, health, conservation,
  The Lever track record). **Age of AI never runs through run_show**, so its
  memory feeds the Nerra Voices pipeline instead:
  `pipelines/voices/common.py:episode_memory_block` (reads the committed
  summaries file) injects a `{{show_memory}}` chronicle block into the
  question-generation / episode-thesis / Mira-narration prompts (continuity,
  callbacks, no retreading); the registry entry still gives it the narrative
  page + Story Tracker button + nightly OP3 signals. The podcast stage in
  run_show now `setdefault`s `{narrative_memory_section}` like the digest
  stage (a hook-load failure on a memory show could previously KeyError the
  podcast prompt). Mining hygiene: doubled-word bigrams ("google google"
  ×109 on Tesla — from unstripped `[Google News](url)` labels; the June-13
  label-strip was never ported to the bespoke Tesla module, now is) and
  generic-prose junk bigrams ("need know" ×78 on M&A) are filtered +
  committed histories scrubbed. Memory-section injection changes prompt
  context for MIT/DP Pod → A/B-listen per landmine #17.

### Per-show repositioning + per-episode blog title (Phase 4 partial, May 2026)

Editorial repositioning of four shows (prompt + sourcing changes — they change
generated output; per landmine #17, A/B-listen and revert via git if needed):

- **Omni View → "Steel Man".** Digest + podcast now require presenting each
  competing position in its *strongest* form (best supporting reason first),
  not a caricature — the listener shouldn't be able to tell which side the show
  favours.
- **Финансы Просто → women-in-finance-in-Canada.** New high-priority INCLUDE
  category + "Объясни как подруге" topic steer toward spousal RRSP,
  maternity/parental EI, childcare deduction, FHSA, financial independence;
  two women-finance `web_search_queries` added.
- **Привет, Русский! → vocabulary-first.** Theme is chosen FIRST (rotating
  everyday domains); news is optional backdrop only — it's a language course,
  not a news show.
- **Environmental Intelligence → all-province + B2B brief.** Added a scannable
  "Compliance Brief" section (digest + podcast) for forwarding to a team, plus
  four provincial `web_search_queries` (ON/AB/QC/SK-MB-Atlantic) for true
  national coverage (provincial bodies lack reliable RSS, so search not feeds).

- **Per-episode blog title (Phase 2 carry-over).** `engine/blog.py` now uses
  the unique episode **hook** for the blog `<title>`/`<h1>`/BlogPosting
  headline whenever the extracted title is just the show name (digests lead
  with a `# <Show Name>` heading) — previously every post's title was identical,
  killing per-episode SEO. Falls back to the show name only when there's no
  hook. Drift guards: `tests/test_phase4_repositioning.py`.

- **Operator tooling:** `scripts/update_tesla_narrative.py` now takes `--slug`
  (default tesla) for any memory show.

### Multi-platform Shorts distribution (Instagram Reels / TikTok, May 2026)

Opt-in per show (`youtube.multi_platform_enabled`, default false → no-op). When
on, each published Short also gets: a **safe-zone variant MP4** (drops the
bottom URL pill + end-card and lifts captions via
`build_short_video(drop_url_pill=, caption_margin_v=)` so overlays clear the
IG/TikTok UI bands), a **`.social.json` sidecar** with per-platform
caption/hashtags (`engine/social_metadata.py`), optional **R2 hosting**
(`social_r2_prefix`; needed for IG's URL-based API), and best-effort
**auto-posting** (`engine/social_publisher.py` — IG Graph + TikTok Content
Posting; a clean no-op until `IG_ACCESS_TOKEN`/`IG_USER_ID` /
`TIKTOK_ACCESS_TOKEN` are set, and requires the operator's developer-app
approval). Orchestrated by `engine/social_distribution.py`, called once per
Short from `run_show.py`'s YouTube stage (additive, non-fatal). YouTube uploads
use the original Short, unchanged. Full setup + limitations:
[`docs/social_distribution.md`](docs/social_distribution.md). Drift guards:
`tests/test_social_distribution.py`.

### Audience-growth pass (June 2026)

Full network review + growth implementation —
[`docs/network_review_2026_06.md`](docs/network_review_2026_06.md) is the
canonical writeup (market analysis, first real audience numbers, roadmap,
operator checklist). Shipped, all no-ops when secrets unset:

- **Audience read-back.** `scripts/fetch_op3_stats.py` (needs
  `OP3_API_TOKEN`) + `scripts/fetch_buttondown_stats.py` run in nightly
  maintenance before the dashboard build → `api/op3_stats.json`,
  `api/buttondown_stats.json`, public `site/data/popular_episodes.json`.
  Surfaces: dashboard "Audience" card, homepage "Most Played This Week"
  rail, homepage "Join N+ readers" social proof (hidden < 100 subs).
  OP3 response shapes are pinned in `tests/test_op3_stats.py` — verified
  live June 2026 (`monthlyDownloads`/`weeklyDownloads`; episode
  `downloads1/3/7/30/All` keys are OMITTED when the data span is young).
  **July 25 2026 nightly-fetch hardening** (drift guards:
  `tests/test_connector_budget.py`; contract:
  [`docs/analytics.md`](docs/analytics.md)): a live run surfaced two
  issues the JSON outputs had been hiding. (1) The Spotify step ran for
  **over an hour** — `spotifyconnector` retries a failing endpoint 6×
  with unbounded exponential backoff (~124 s each), and a registered
  feed with no plays yet answers `500` on `/metadata` + `/aggregate`
  *every* night (18 of 24 feeds were in that state, ~32 dead endpoints).
  New `engine/connector_budget.py` clamps the connectors' retry
  constants (3 attempts / 1 s base ≈ 6 s per dead endpoint, measured)
  and adds a wall-clock budget (`SPOTIFY_/APPLE_FETCH_BUDGET_SECONDS`,
  default 900 s) as the backstop; unreached shows keep their previous
  entry tagged `not_refreshed_this_run`, so a budget stop never shrinks
  the file. Applied to the Apple fetcher too (its constant is
  `MAX_RETRY_ATTEMPTS`, not `MAX_REQUEST_ATTEMPTS` — a copy-paste would
  clamp nothing). (2) **Age of AI's enclosures carried no OP3 prefix**:
  the prefix is applied by each publish path, never by
  `update_rss_feed`, and the Nerra Voices publisher
  (`pipelines/voices/publish_episode.py`) bypasses run_show — so its
  downloads were invisible. Fixed for new episodes; the published Ep001
  URL is deliberately left unprefixed (rewriting a live enclosure
  re-downloads it for every subscriber). Any future show that bypasses
  run_show must apply the prefix in its own publish step. The `dp_pod` /
  `age_of_ai` OP3 **404s are an indexing lag**, not a bug — OP3's docs
  define 404 as "OP3 doesn't know about the show"; downloads attach
  retroactively once it indexes the feed. A 404 persisting for weeks
  means check the prefix first.
- **Adjacency-map bug fixed.** `newsletter.network_adjacencies` (and the
  other newsletter composition keys) had been mis-indented under
  `cost_circuit_breakers:` in `shows/_defaults.yaml` — newsletter +
  synthesizer read an empty map, so the cross-network email module was
  silently degraded network-wide. Drift guard pins the location. NOTE:
  there are deliberately THREE curated cross-show mappings — web
  (`generate_html.NETWORK_SHOWS[slug]["related_show"]`), email
  (`newsletter.network_adjacencies`), audio/X
  (`engine/network_promo.ENGLISH_SHOWS`). Do not consolidate casually;
  each is tested and serves a different surface.
- **Newsletter growth loop.** Every show now gets a deterministic
  Buttondown slug (`<show>-ep<num>-<hook>`; was Russian-only) so the
  view-in-browser/archive link renders pre-send on dailies AND weeklies;
  reply/share row gained a localized "Forwarded this email? Subscribe
  here" line (UTM `forward_subscribe`).
- **X cross-promo reply.** Flag `publishing.x_cross_promo` (network
  default true in `_defaults.yaml`, dataclass default false) posts a
  second tweet threaded under the teaser: "Follow @{x_handle}" + one
  sibling plug from the `network_promo` rotation. `x_handle` set only for
  tesla/@teslashortstime + the PLANETTERRIAN_X_ shows/@planetterrian;
  OV/M&A/MIT pending operator confirmation. Roughly doubles posts/day per
  X app — flip the flag off if the free-tier cap trips.
- **Podcasting 2.0 channel tags.** `update_rss_feed` now injects
  `podcast:funding` (→ `/#newsletter`) + `podcast:person` (host) on every
  rebuild via `_inject_channel_funding_person_tags` (same pattern as
  `podcast:locked`); empty kwargs = byte-for-byte legacy behavior.
- Sitemap: + `player.html` + `modern-investing-performance.html`,
  − `404.html`. Nightly site-regen step now passes the marketing env vars
  (was silently stripping analytics tags on nightly rebuilds).
- **Known wart (operator decision pending):** Russian shows speak the
  ENGLISH `_AI_DISCLOSURE` line at the end of every episode; a localized
  `_AI_DISCLOSURE_RU` is a one-liner in `run_show.py` but changes shipped
  audio → landmine #17 A/B-listen first.

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
  and records `video_podcast_skipped` rather than rendering twice. Per-
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

## Current Refactoring Goal

**Extract duplicated code from the show scripts into `engine/` modules.**

Phase 1 (complete):
- `engine/utils.py` — `number_to_words`, `_env_float/int/bool`,
  `calculate_similarity`, `remove_similar_items`, `deduplicate_by_entity`
- `engine/tts.py` — `validate_elevenlabs_auth`, `speak`, `_speak_chunk`,
  `_chunk_text_for_elevenlabs`
- `engine/audio.py` — `get_audio_duration`, `format_duration`,
  `mix_with_music` (standard / delayed-intro / dual-music modes),
  `normalize_voice`

Phase 2 (complete):
- `engine/publisher.py` — `update_rss_feed`, `get_next_episode_number`,
  `save_summary_to_github_pages`, `post_to_x`, `format_digest_for_x`,
  `format_tst_digest_for_x`, `apply_op3_prefix`
- `engine/content_tracker.py` — `ContentTracker` with per-show section patterns
  (TST, FF, PT, OV, EI, M&A)
- `engine/fetcher.py` — `fetch_rss_articles`
- `engine/generator.py` — `generate_digest`, `generate_podcast_script`
- `engine/tracking.py` — `create_tracker`, `record_llm_usage`,
  `record_tts_usage`, `record_x_post`, `save_usage`

Phase 3 (current):
- All 13 shows now run via `run_show.py` + YAML configs in production (CI/CD).
- Legacy scripts (`digests/{tesla_shorts_time,omni_view,fascinating_frontiers,
  planetterrian}.py`) are **deprecated** — retained for reference only.
- `run_show.py` is the canonical entry point; legacy scripts are not called
  by any workflow or cron job.

## Known Landmines

**Sitemap `lastmod` must not follow file mtime.** Blog post files are
rewritten by every regeneration; the episode date is not. If `lastmod`
tracks mtime, a network-wide regen tells Google all ~1,250 posts changed
at once, which is the exact signal the May 2026 audit removed.
`generate_sitemap()` reads `datePublished` out of each page's JSON-LD.
Do not "simplify" it back to `_file_lastmod`.

**`digests/_newsletter_sending_blocked.json` silently skips the
newsletter for 7 days.** If newsletters stop going out, check for that
file before debugging Buttondown.

**Show slugs use underscores, page filenames use hyphens.**
`fascinating_frontiers` → `fascinating-frontiers.html`. Getting this
wrong in `publishing.rss_link` 404s the "website" button in every
podcast directory, and nothing in the pipeline fetches its own
`rss_link` to notice. `validate_show.py` now checks it.

**Operator's first stop:** the live state of every landmine below is rendered
by [`management.html`](management.html), fed by
[`scripts/generate_dashboard.py`](scripts/generate_dashboard.py) → `api/dashboard.json`.
Items 7 and 10 are intentionally excluded from the dashboard (per an explicit
decision); everything else has a live status card.

### Active Issues

1. **2.2 GB of MP3s in git HISTORY (HEAD is clean)** — measured June 10
   2026: zero episode MP3s are tracked at HEAD (guards in `.gitignore` +
   the commit step's `git reset -- '*.mp3'`; only the 43 MB of
   `assets/music` themes + two voice-reference WAVs remain, which the
   pipeline needs). All enclosure URLs serve from R2. CI clones are
   shallow since the June 2026 workflow pass (~115 MB packed vs ~2.5 GB
   full), so the day-to-day clone cost is FIXED and growth is now
   text-only (~50 MB/month → years of headroom under GitHub's 10 GB
   limit). The history weight itself can only be removed by a
   `git filter-repo` rewrite + force-push of main — DESTRUCTIVE:
   requires a paused-cron window (12 daily workflows push to main and
   could race the force-push and resurrect old history), invalidates
   every existing clone, and dangles the commit SHAs referenced across
   docs/. Playbook in
   [`docs/workflow_review_2026_06_10.md`](docs/workflow_review_2026_06_10.md);
   operator-scheduled, not urgent. For full local clones meanwhile:
   `git clone --filter=blob:none` skips historical blobs.
2. **Git LFS breaks RSS** — `raw.githubusercontent.com` returns pointer files
   for LFS-tracked content. Do NOT use LFS for MP3s.
3. **Historical TST/OV flat files in `digests/`** — ~220 legacy output files
   (MP3s, markdown, JSON, HTML, TXT) remain at the `digests/` top level from
   before shows were migrated to subdirectories. These cannot be moved without
   breaking existing RSS feed URLs. New episodes now write to subdirectories.
23. **GitHub push transients on large text commits ("fatal error in commit_refs")** —
    Successful episode generation (run_show.py) can produce 8k–10k+ line commits
    (full Whisper transcripts JSON+txt, _tts.txt, metrics, chapters, digests, blog
    HTML, RSS updates). GitHub's ref-update service occasionally returns a server
    error during `git push origin main` even after the pack is accepted. The
    4-attempt rebase/merge loop in `.github/workflows/run-show.yml` handles
    normal concurrency races between matrix jobs. On final exhaustion the step
    now calls `scripts/create_recovery_pr.sh` which creates a `recovery/<show>-<run_id>-<ts>`
    branch, pushes it, and opens a **draft PR** with the complete artifacts plus
    operator instructions. The job exits 0 (data preserved). The PR appears in
    the repo for the operator to merge. This is the hardened path for the
    "Commit and push output" step (the finalize shared-pages push has a 5-attempt
    loop + warning but no recovery PR because those pages are fully regenerable).
    The `safe-commit-push` composite used by nightly + 8 other workflows does not
    yet have the recovery escape hatch (lower risk callers). The multilingual
    sweep's commit step (`.github/workflows/multilingual.yml`) also uses the
    recovery-PR escape hatch now, since it commits large translation-track +
    per-language-feed diffs on the same push-contended `main`. Drift guard:
    the recovery script + the warning annotation in the Actions log.

24. **Schedule punctuality: exact-time dispatcher + duplicate guard (June
    2026)** — GitHub delivers cron `schedule` events 1-6 h late (Tesla's
    11:00 slot observed starting 13:54). Fix: run-show crons moved to
    off-peak :07/:37; `workers/scheduler/` (Cloudflare Cron Trigger,
    fires to the minute) dispatches each show via `workflow_dispatch` at
    its intended slot once the operator deploys it (fine-grained PAT →
    `wrangler secret put GITHUB_DISPATCH_TOKEN`, `wrangler deploy` — see
    its README); the gate's same-day duplicate guard (checks today's
    "Auto-generated: <show> <date>" commit) lets the delayed GitHub cron
    coexist as fallback without double-publishing. The Worker's SLOTS
    table must stay in sync with the gate's CRON_MAP —
    `tests/test_scheduling_punctuality.py` fails CI on drift.

### Resolved Issues (Feb 2026)

4. **TST/OV output dirs fixed** — `shows/tesla.yaml` and `shows/omni_view.yaml`
   now use `digests/tesla_shorts_time/` and `digests/omni_view/` for
   `output_dir` and `audio_subdir`, matching FF/PT/EI. Legacy scripts already
   pointed to subdirectories. Audio URL construction in both legacy scripts
   also fixed.
5. **Legacy `digests/digests/` path bug cleaned up** — nested directory deleted,
   RSS references removed, SETUP.md corrected. Defensive scanning code remains
   in `tesla_shorts_time.py` in case any legacy files resurface.
6. **58 duplicate `_formatted.md` files deleted** — removed in commit
   `0c10b7f`, code no longer generates them.
7. **`NEWSAPI_KEY` dead secret removed** — not present in active workflow
   (`run-show.yml`), not used in any code. Integration test
   `test_no_newsapi_in_active_workflow()` guards against re-introduction.
8. **Feature flags consistent across shows** — all four legacy scripts
   (TST, FF, PT, OV) support env-overridable `TEST_MODE`, `ENABLE_X_POSTING`,
   `ENABLE_PODCAST`, and `ENABLE_GITHUB_SUMMARIES`. `run_show.py` uses
   CLI flags (`--test`, `--skip-x`, `--skip-podcast`) instead.
9. **ElevenLabs tuning baseline lives in `shows/_defaults.yaml`** — the
   canonical network baseline is now whatever
   [`shows/_defaults.yaml`](shows/_defaults.yaml) declares (today:
   `stability=0.5`, `similarity_boost=0.75`, `style=0.0`, English voice
   `dTrBzPvD2GpAqkk1MUzA`, Russian voice `gedzfqL7OGdPbwm0ynTP`). Per-show
   overrides are allowed; drift is tracked live in the management
   dashboard's *Voice settings consistency* table. Any show row flagged
   with a drift is either intentional (record the reason in the show's
   YAML as a comment) or a regression to investigate. Historical note:
   an earlier baseline had stability `0.65`, similarity boost `0.9`, and
   style `0.85`; that combination is no longer blessed and should not be
   reintroduced without updating `_defaults.yaml`.
10. **Early episodes deleted** — first 20 Tesla, 10 FF, 10 PT, 10 OV episodes
    removed (quality issues). RSS entries removed where applicable.
11. **All 10 shows on Grok TTS (May 2026, full-network migration)** —
    Chatterbox, Kokoro, and Fish Audio were trialled and removed.
    English shows (including Tesla Shorts Time as of the third migration
    wave) all use the operator's custom-trained voice `kdif6sqjcyiq`
    for a single consistent host identity. Russian shows use the
    custom Olya voice (`0b875ae2`). ElevenLabs is no longer used in
    production. Network cost: ~36× cheaper per character on Grok
    ($4.20/M vs $150/M for ElevenLabs Flash). Reuses `GROK_API_KEY` /
    `XAI_API_KEY` — no new secret. See landmines #16 and #17.
12. **Summaries JSONs moved** — all summaries live in per-show subdirectories
    (`digests/<show>/summaries_*.json`), not at the `digests/` top level.
13. **LLM default migrated to `grok-4.3` (May 2026)** — released 2026-04-30,
    always-on reasoning, $1.25/$2.50 per 1M tokens (~55% cheaper per
    episode than the previous `grok-4.20-*` defaults). Network default,
    synth model, Tesla / Modern Investing per-show overrides, and the
    tool-use path (`digests/xai_grok.py`, X / web search via the
    Responses API — confirmed grok-4.3 supports `x_search` and
    `web_search` built-in tools) all now run on `grok-4.3`. Refusal
    fallback stays on `grok-4.20-reasoning` so refusals genuinely
    switch model snapshot rather than retrying the same primary.
    Pricing for the historical 4.20 family is retained in
    `engine/tracking.py` so old `credit_usage_*.json` files still cost
    out correctly.
14. **YouTube slideshow imagery is curated, not derived from `keywords:`**
    — early Tesla videos (e.g. Ep456) shipped with topless / fashion-model
    photos because `engine/visual_assets.py:_select_keywords()` was passing
    raw show keywords (`model 3`, `model y`, `model s`) to Pexels with no
    topic context. Pexels treats `model` as a person who poses, not a car.
    Fix landed May 2026: every show's `youtube:` block now declares
    `image_queries:` (curated, disambiguated phrases) and optionally
    `image_query_prefix:` (auto-prepended to any `keywords:` fallback).
    A safety filter (`image_safe_skip_terms`, default list in
    [`engine/config.py`](engine/config.py)) drops Pexels results whose
    URL slug contains people-only / off-topic substrings. The filter
    count is recorded as the `pexels_photos_filtered` metric — a spike
    means a show's queries need tightening. The
    `test_every_show_yaml_has_image_queries` test in
    [`tests/test_visual_assets.py`](tests/test_visual_assets.py) blocks
    any new show from going live without curated phrases.
15. **YouTube Podcasts surface requires manual Studio setup, not API**
    — the pipeline correctly creates per-show playlists and adds each
    upload via `engine/youtube.add_video_to_playlist()`, and every show
    YAML carries a `podcast_playlist_id:` (verified live in CI). But a
    playlist only appears under "YouTube Podcasts" once it's been
    flagged as a podcast in YouTube Studio: open
    `Studio > Content > Podcasts > "Set existing playlist as a podcast"`
    on each channel (`@NerraNetwork` for English shows, `@NerraRU` for
    Финансы Просто / Привет, Русский!) once per playlist. The YouTube
    Data API has no endpoint for this flag. Once flagged once, every
    future video added via the API automatically becomes a podcast
    episode. **One-time setup per playlist — not a code change.**
16. **TTS network default flipped to Grok TTS (May 2026)** — staged in
    two PRs:
    - **First wave (Russian shows):** Финансы Просто and Привет,
      Русский! switched from ElevenLabs voice `gedzfqL7OGdPbwm0ynTP` to
      Grok TTS with the custom "Olya" voice `0b875ae2` (trained on the
      xAI Console). Validated with one live episode (PR Ep017,
      2026-05-02) before broader rollout.
    - **Second wave (English shows):** Network default in
      [`shows/_defaults.yaml`](shows/_defaults.yaml) flipped to
      `provider: grok`, `voice_id: sal` (Grok built-in named voice),
      `language_code: en`. The 7 non-Tesla English shows (Omni View,
      Fascinating Frontiers, Planetterrian, Env Intel, Models &
      Agents, Models & Agents for Beginners, Modern Investing) now
      inherit those defaults — their `tts:` blocks are intentionally
      empty (`{}`) to make inheritance the contract. Tesla Shorts Time
      explicitly overrides back to `provider: elevenlabs`,
      `voice_id: dTrBzPvD2GpAqkk1MUzA` because voice continuity on the
      network's largest show outweighs the cost delta.

    Implementation details: `engine/tts.py:synthesize()` dispatches on
    the `provider` kwarg; the Grok path posts to
    `https://api.x.ai/v1/tts` and reuses `GROK_API_KEY` /
    `XAI_API_KEY` (no new secret). ElevenLabs-only voice settings
    (`stability`, `similarity_boost`, `style`, `use_speaker_boost`,
    `model`, `speed`) live in [`shows/_defaults.yaml`](shows/_defaults.yaml)
    under a `# ---- Legacy ElevenLabs baseline ----` block — harmless
    when `provider=grok` (Grok path silently ignores them) and a tuned
    starting point if any show flips back to ElevenLabs. Pricing is
    per-provider in [`engine/tracking.py`](engine/tracking.py):
    `TTS_PROVIDER_PRICING`. Three drift guards in
    [`tests/test_tts_grok.py`](tests/test_tts_grok.py) block silent
    regressions: `test_russian_shows_use_grok_tts` (Olya voice on
    Russian shows), `test_english_shows_resolve_to_grok_sal` (sal voice
    on the 7 English shows after deep-merge), and
    `test_tesla_stays_on_elevenlabs` (TST voice continuity).
    `ELEVENLABS_API_KEY` is still required because Tesla uses it; if
    Tesla ever migrates, the env-var requirement disappears
    (`run_show.py:_validate_environment` already gates the check on
    `provider == "elevenlabs"`).
17. **Full-network voice migration + broadcast-quality audio pipeline
    (third TTS wave, May 2026)** — Tesla Shorts Time joined the rest of
    the network on Grok TTS. Every English show now inherits the
    operator's custom-trained voice `kdif6sqjcyiq` from
    [`shows/_defaults.yaml`](shows/_defaults.yaml); the previous `sal`
    built-in voice was retired and TST's ElevenLabs override
    (`provider: elevenlabs`, voice `dTrBzPvD2GpAqkk1MUzA`) was removed.

    Same migration shipped a broadcast-quality audio pipeline. Cumulative
    changes to the per-episode signal flow:

    - **Grok TTS request:** now requests **WAV at 48 kHz** with
      `text_normalization: true` (`engine/tts.py:grok_speak_chunk`).
      Previously MP3 at 24 kHz with no normalization. The pipeline
      crossfades chunks in WAV and only encodes to MP3 once at the very
      end (one lossy pass instead of two). Server-side text normalization
      handles dates, currencies, and ordinary numbers — the
      `pronunciation_map.yaml` layer remains for proper-noun / acronym
      overrides.
    - **Voice EQ chain** (`engine/audio.py:_voice_norm_full_cmd`) —
      highpass 80 / lowpass 15k / adeclick+afftdn / loudnorm -18 /
      acompressor 4:1 / alimiter. **This entry used to claim the chain
      "gained a 6.5 kHz dip (`equalizer=f=6500:t=q:w=1.5:g=-3`) for
      gentle de-essing". It never did** — `git log -S "6500"` on
      `engine/audio.py` returns nothing, the string has never existed in
      the file. Corrected 2026-07-30. Do not "restore" it: there is
      nothing to restore.
      **De-essing was then measured and deliberately declined.** With a
      live key, 2:34 of real Tesla Ep557 synthesized on the production
      voice and pushed through the chain shows the midrange flat
      (-0.1 dB) while the sibilance band (5.5-8.5 kHz) gains **+5.1 dB**
      and air (8.5-16 kHz) **+5.0 dB** — the 4:1 broadband compressor
      lifts consonants faster than vowels. Four variants (no de-ess /
      static -3 dB / static -5 dB / ffmpeg `deesser`) were rendered and
      **the operator listened: all four sound the same on this voice.**
      So the +5 dB is a measurement, not a defect, and the network ships
      the chain unchanged — adding a stage that buys no audible benefit
      but alters every episode on 15 shows is the landmine-#17 shape.
      Re-open only with listening evidence, not spectra.
    - **Final mix** (`engine/audio.py:_final_mix_cmd`) replaced the
      simple `amix` with sidechain-ducked music + EBU R128 loudnorm
      to **-16 LUFS** (Apple Podcasts / Spotify spec). Music
      automatically pulls down 8 dB when voice is present and rises
      smoothly when voice pauses. The fixed-curve `mix_with_music`
      music timeline still runs upstream to control intro / overlap /
      fadeout / outro volumes; the sidechain ducking adds the
      moment-to-moment dynamic response that makes voice + music feel
      cinematic instead of mechanical.
    - **Final encode** bumped from CBR 192 kbps to VBR `-q:a 0`
      (~245 kbps) for archival-quality spoken-word + music. ~6.5 MB
      per 30-min episode (was ~5 MB).
    - **Speech tags** are now allowed in podcast prompts (every
      `shows/prompts/*_podcast.txt` carries a `DELIVERY` block).
      Allowed: `[breath]`, `[pause]`, `[long-pause]`,
      `<emphasis>...</emphasis>`. Banned: every other Grok tag
      (`[laugh]` / `<whisper>` / `<slow>` / etc. — they sound
      performative). The TTS path keeps tags; every non-TTS consumer
      runs through `engine.utils.strip_speech_tags()` before publishing
      so blog markdown, RSS show notes, X teaser, and YouTube
      descriptions never see them.
    - **Drift guards:** `tests/test_tts_grok.py` now has
      `test_english_shows_resolve_to_custom_voice` (every English show
      including Tesla resolves to `kdif6sqjcyiq`),
      `test_no_show_uses_elevenlabs_in_production` (catches accidental
      rollback flips), and `test_russian_shows_use_grok_tts` (Olya
      voice unchanged).

    `ELEVENLABS_API_KEY` is **kept** in GitHub Secrets / `.env` for
    emergency rollback even though no show currently needs it. The
    legacy ElevenLabs settings in `_defaults.yaml` (model, stability,
    similarity_boost, style, etc.) are also preserved — harmless under
    `provider=grok` and a one-line YAML flip back to ElevenLabs if
    Grok TTS has an outage.

    **May 4 2026 update — speech-tag wrap simplified.** The chunk-
    send wrap was originally `<fast><build-intensity>...</build-intensity></fast>`
    (PR #293). Whisper transcripts of UC Ep001 ("Build intensity." at
    line 3 + "build intended to dig" at line 127) and Tesla Ep461 (line
    112) showed Grok occasionally **speaking** "build intensity" out
    loud instead of consuming the tag — `<build-intensity>` was never
    in Grok's documented tag list. Wrap simplified to `<fast>...</fast>`.

    **May 11 2026 update — chunk wrap dropped entirely, programmatic
    `<emphasis>` injection added.** M&A Ep045 transcript caught Grok
    voicing the opening `<fast>` aloud as "Fast." at section-TTS
    boundaries (twice — at "in its latest release. Fast. The updates…"
    and "make sense for their workloads. Fast. Okay, let's pop the
    hood…"). Verified against xAI docs: `<fast>` is **not** on Grok's
    documented tag list (only `[breath]`, `[pause]`, `[long-pause]`,
    `<emphasis>`, `<whisper>`, `<slow>`, `<soft>` are). The energy
    lift `<fast>` was supposed to provide was paid for in occasional
    audible tag leakage at every chunk boundary multi-section TTS
    creates. Wrap dropped to empty strings in both `engine.config`
    and `shows/_defaults.yaml`.

    Programmatic `<emphasis>` injection was added in the same PR
    (`engine/prosody.py:inject_prosody_tags()` wrapping currency /
    percentages / cashtags at script-save time) — and **paused the
    same day** (see below).

    The DELIVERY prompt block was also dropped from all 12 podcast
    prompts (`shows/prompts/*_podcast.txt`); 56 recent `_tts.txt`
    files showed the LLM was ignoring it (only 10 had any tags at
    all, never reliably). The block was paying prompt-token cost
    for no measurable audio benefit.

    Defense-in-depth: `engine.utils.strip_speech_tags()` is wired
    into RSS show notes (`engine/publisher.py:_markdown_to_rss_html`),
    newsletter body (`engine/newsletter.py:send_show_newsletter`),
    and YouTube metadata (`engine/video_metadata.py:_strip_markdown`)
    so any speech tag that enters the digest body is scrubbed before
    subscribers / readers / YouTube see it. Drift guard
    `test_default_tts_config_has_no_chunk_wrap` blocks accidental
    re-introduction of the chunk wrap.

    **May 11 2026 update (later same day) — pause all TTS
    modifications, run raw Grok TTS.** Operator A/B-listened to
    Planetterrian Ep060 and Fascinating Frontiers (with the phonetic
    respellings for "Planetterrian", "tissue", "neurodegenerative"
    active) against raw audio and concluded **every phonetic
    respelling sounded worse than the original word** on the custom
    voice `kdif6sqjcyiq`. Same call for the just-shipped programmatic
    `<emphasis>` injector — adding any modification risked regressing
    a voice that already handles these tokens naturally.

    Pause decision:
    - `engine/prosody.py` and its tests **deleted**. The
      `inject_prosody_tags()` call in `run_show.py` reverted.
    - Phonetic respellings (`tissue`/`Tissue`/`tissues`/`Tissues`,
      `neurodegenerative` and 3 case/inflection variants) **removed**
      from `shows/pronunciation_map.yaml`. The Planetterrian
      WORD_PRONUNCIATIONS entry was already removed in PR #355.
    - **Kept**: letter-by-letter acronym expansions in
      `shows/pronunciation_map.yaml` (`TSLA` → `T S L A`, `LLM` → `L
      L M`, `TFSA` / `RRSP` / `FHSA` / `RESP`, `HW4` / `HW5` / `AI5`,
      `MCP`). Those are NOT phonetic guesses — they're literal
      letter-spellings, and the operator-verified failure mode
      without them is Grok saying "lum" / "tezz-luh".
    - **Kept**: `<fast>` chunk-wrap removal + DELIVERY-block removal
      + `strip_speech_tags()` defense (those are removals of broken
      modifications + a no-op safety net, not modifications).

    Re-introduce ANY phonetic respelling or programmatic tag
    injection ONLY with A/B listen-test evidence on the custom voice
    that the modified audio is measurably better than raw on at
    least 3 different show contexts. Theory-driven "this should
    sound better" changes have a 100% regression rate on this voice
    so far (Planetterrian, tissue, neurodegenerative, `<fast>` wrap,
    `<build-intensity>` wrap — every one made it worse).

    **May 13 2026 update — `<fast>` wrap re-enabled via single-call
    synthesis.** Operator listened to the May 13 episodes (post-#365
    editorializing reduction + #366 audio retune + #367 streamline)
    and asked for whole-script `<fast>` energy on every podcast
    ("Option B for all podcasts please"). The historical chunk-wrap
    leak (M&A Ep045 voicing "Fast." at section-TTS boundaries) was
    a *multi-call* problem: section-TTS + chunked synthesis meant
    every chunk got its own `<fast>...</fast>` wrap as an
    independent Grok API call, and Grok occasionally voiced the
    opening tag aloud at the boundary between calls.

    Leak-safe implementation (the only safe path):
    - Network default `shows/_defaults.yaml`: `speech_wrap_open:
      "<fast>"`, `speech_wrap_close: "</fast>"`, `use_section_tts:
      false`, `max_chars: 14000`.
    - The four fields are a *coupled set* — flipping any one
      without the others re-introduces the leak.
    - `run_show.py:1714` gates section-TTS on `config.tts.use_section_tts`
      so the network-wide flip is one YAML field.
    - `engine/tts.py:_speak_with_grok` has a May 13 safety guard:
      if a script overflows `max_chars` and splits into multiple
      chunks, it DROPS the wrap (with a loud warning) rather than
      apply it per-chunk. Episode loses the energy lift but ships
      clean audio.

    Trade-off: section-TTS off means **no transition stings between
    chapter markers**. Chapter markers themselves still work in
    podcast apps (Apple, Spotify, Pocket Casts) because they come
    from `chapters.json` not from section-TTS. The brief musical
    stings between chapters are gone — most listeners won't notice;
    one-line revert (`use_section_tts: true` + drop the wrap) if
    desired.

    Drift guards in `tests/test_tts_grok.py`:
    - `test_default_tts_config_dataclass_has_no_chunk_wrap` —
      dataclass default stays empty (backwards compat for callers
      that bypass YAML).
    - `test_network_default_has_fast_wrap_and_single_call` — pins
      the four coupled fields on the loaded Tesla YAML so a partial
      revert (e.g. re-enabling section-TTS without dropping the
      wrap) fails CI.
    - `test_speak_with_grok_drops_wrap_on_multi_chunk` — verifies
      the safety guard fires when a script overflows.
    - `test_speak_with_grok_keeps_wrap_on_single_chunk` — verifies
      the happy path applies the wrap as expected.

    The policy above (no theory-driven tag changes) still stands
    for any FUTURE additions. The May 13 `<fast>` re-enable was an
    *operator override* with explicit awareness of the historical
    risk; it ships as a single coherent infrastructure change
    (single-call synthesis) rather than as a tag-injection retry.

18a. **Newsletter dark-mode CSS must stay SCOPED (v3, June 2026)** —
    the iPhone dark-mode bug (subject title, "NERRA NETWORK · date"
    byline, forward line, and unsubscribe footer rendering white-on-
    light = invisible; operator screenshots Jun 9 2026, after several
    failed fixes) was caused by GLOBAL selectors in the dark-mode
    `<style>` block (`h1 { color:#fff }`, universal `p/td/div/span`
    text flips, td-style-attribute background matches). Those rules
    leak onto **Buttondown's own wrapper**, whose backgrounds we cannot
    flip. v3 contract in `engine/newsletter_template.py`:
    `wrap_with_branding` stamps every emitted table/div with the `nn`
    marker class (`_scope_nn`), and every color rule inside the
    `@media (prefers-color-scheme: dark)` block is scoped under `.nn`
    (surface classes like `.surface-white` are ours alone and stay
    class-targeted). Buttondown chrome keeps its native always-readable
    colors; our cards adapt. The `:root/body { color-scheme: light
    dark }` opt-in stays — removing it regresses to Apple Mail's
    auto-transform (washed-out headings, the original May 2026 bug).
    Drift guards: `tests/test_newsletter_template.py::TestDarkModeScoping`
    (no unscoped color selectors, no attribute background selectors,
    every block carries `.nn`).

18. **Newsletter pipeline spec v2 (May 2026)** — multi-day refinement
    pass on the Buttondown send pipeline addressing contrast bugs,
    LLM scaffold leaks, and daily-vs-weekly template parity. Files:

    - **`engine/newsletter_sanitizer.py`** (new) — regex blocklist of
      known LLM scaffold patterns (`**HOOK:**`, `**Date:**`,
      `ЗАГОЛОВОК:`, `**The Surprising Truth:**`, box-drawing rules
      `━━━`, etc.) plus a hard tripwire (`assert_clean`) that blocks
      send if any pattern survives scrubbing. Run by
      `send_show_newsletter` before the wrapper sees the body.
    - **`engine/url_utils.py`** (new) — strips C0/C1 control chars
      from RSS-scraped URLs (the `?ito\x14` bleed), and resolves
      Google News redirect URLs (`news.google.com/rss/articles/CBMi…`)
      to their canonical publisher form at fetch time. Both ops are
      best-effort; failures pass through unchanged. Wired into
      `engine/fetcher.py`'s per-article loop.
    - **`engine/newsletter_body.py`** (new) — body-text transforms
      applied between scrub and wrap: box-rules → `<hr>`, Tesla
      `**REAL-TIME TSLA price:**` → styled stock-watch block, Russian
      vocabulary list (Привет) → card stack, Omni View "Read more"
      duplicate-URL dedup.
    - **`engine/contrast_validator.py`** (new) — WCAG 2.1 AA tripwire
      that walks rendered HTML, checks every inline `color:` against
      its nearest-ancestor background. Currently a soft warning in
      `send_show_newsletter` (logs but doesn't block) so we can
      calibrate against real renders before flipping to hard-block.
    - **`engine/newsletter_template.py`** — surgical template fixes:
      hero pill is now a `<table>` with `bgcolor` instead of an
      `rgba()` div (Outlook fix); cover `<img>` carries inline
      `color/font-size/font-weight` so alt-text fallback is readable;
      VML wrapper added for Outlook gradient fallback; dark-mode
      `<style>` block expanded with per-brand-color tokens
      (`.brand-text-tesla` / `.brand-text-mit` / etc.) and surface
      classes (`.surface-white` / `.card` / `.preheader`) to win the
      inline-style override war on Outlook iOS / mobile Gmail; light-
      mode `#94a3b8` / `#64748b` muted greys swapped for `#475569`
      where they appeared as primary text (3.0:1 → 6.4:1 on white);
      P.S. block re-styled with dashed top-border separator + italic
      body; cross-network show names are now full-row clickable
      links; new `_build_view_in_browser_html` partial at top of
      body and `_build_issue_counter_html` per-show counter just
      above Buttondown's auto-footer.
    - **`engine/newsletter.py:send_show_newsletter`** — full daily-
      caller overhaul. Subject line uses
      `build_subject_line(hook_max_chars=50, is_daily=True)` for the
      same `<hook> · <show> <emoji>` shape as weekly (replaces the
      broken `f"{config.name}: {hook}"`). Body is scrubbed → body-
      transformed → wrapped with the same hero / featured-episode /
      P.S. / cross-network / reply-share blocks weeklies use.
      Russian shows render the disclaimer and reply/share copy in
      Russian via the localised `_build_financial_disclaimer_html` /
      `_build_reply_share_html` paths. Buttondown ``slug`` is set
      explicitly for Russian shows using a GOST-7.79 Cyrillic→Latin
      transliteration map so archive URLs read as
      ``privet-russian-ep018-kosmos-9-russkikh-slov`` instead of
      ``u041f-u0440-u0438-…``. Same-day double-send guardrail: each
      show writes a `digests/<slug>/_newsletter_lastsend.txt` after
      a successful send; the next call refuses to re-send within
      20 hours (catches the May 2 Привет Ep 17 + Ep 18 double-send).
    - **`shows/prompts/omni_view_digest.txt`** — the "Read more
      (sources)" instruction now explicitly forbids three identical
      URLs under three different descriptions (the May 2 daily
      shipped with `[Daily Mail](https://...)` × 3). The
      `dedup_read_more_sources` body transform is the
      defense-in-depth layer.

    Operator workflow: nothing changes for the daily cron — it still
    calls `send_show_newsletter`. The added safety gates (sanitizer,
    contrast validator, send guardrail) are defensive — they log
    loudly when they fire so the operator can chase the upstream
    cause (a regressed prompt, a fetcher bug, or a scheduler race).
    The `ELEVENLABS_API_KEY` and legacy ElevenLabs settings in
    `_defaults.yaml` remain untouched — separate concern.

19. **Schedule overhaul + weekly-summary segment (May 2026; restructured
    July 2026)** — 7 shows moved to daily cadence (Omni View,
    Planetterrian, Fascinating Frontiers, Models & Agents, MAB, Modern
    Investing, Tesla; SpaceX joined later). Cron times shifted +1h across
    the board to widen the per-slot window; last show now finishes ~12 UTC
    (~8 AM ET). **July 2026 restructure:** the full Sunday weekly-recap
    mode was RETIRED. Sunday is no longer a special episode — every daily
    show runs a NORMAL daily episode every day, and shows with
    `weekly_summary_segment: true` (was `weekly_recap_on_sunday`) simply
    include ONE short "week in review" *segment* on Sunday. Mechanically:
    `_resolve_weekly_summary` in `run_show.py` gates on Sunday + the flag
    + not-a-deep-dive; when true, the daily digest generates as usual and
    `engine.weekly_recap.build_weekly_summary_segment` synthesises a
    compact host-instruction block from the past 7 days in the content
    lake. That block is appended to the **podcast-only** copy of the digest
    (`clean_digest`, after cleanup) — NOT to the published `x_thread` — so
    the host weaves a brief recap into the episode while zero instruction
    text reaches the blog / RSS / newsletter. A thin content lake (<2
    episodes in window) returns `None` → a plain daily episode with no
    segment. The retired full-recap machinery (digest short-circuit,
    daily-validator skip, and the recap "republish from clean narrative"
    step) is gone; the video recap-scene-reuse path in `_publish_youtube`
    remains as a dormant default-off capability. Prompt/audio-affecting on
    Sunday → A/B-listen per landmine #17. Modern Investing additionally has
    a Saturday "weekend mode" instruction in its podcast prompt covering
    international markets, crypto, lessons learned, and what to prepare for
    in the coming weeks. Drift guards in `tests/test_schedule.py` +
    `tests/test_weekly_summary_segment.py` pin: cron consistency, the daily
    shows carrying the weekly-summary flag, alt-cadence/narrative shows NOT
    carrying it, the segment shape/append point, and that the retired
    full-recap machinery does not return. The legacy `weekly_recap_on_sunday`
    YAML key is still read as a back-compat fallback in `engine/config.py`.

20. **YouTube quota cap (May 2026; four-show expansion June 2026)** —
    the YouTube Data API quota is 10,000 units/day **per channel**;
    each `videos.insert` costs 1,600 units (plus thumbnail 50 /
    playlist 50 / caption 400 on the paper model in
    `engine/youtube_quota.py`). The May 2026 schedule overhaul had
    disabled YouTube on every English show except Tesla and MAB
    (long-form + 2 Shorts each). **June 2026 expansion (operator
    decision, quota-increase request submitted and pending):**
    - Tesla + MAB dropped from 2 Shorts to 1 each.
    - Fascinating Frontiers + Modern Investing enabled **Shorts-only**
      (`publish_long_form: false`) on `@NerraNetwork`. Flip
      `publish_long_form: true` per show once the increase is granted.
    - Финансы Просто + Привет, Русский! enabled **full format** on
      `@NerraRU` (`channel: ru`, its own 10k/day quota; both run even
      days only ≈ 7,600 paper-units). Requires the
      `YOUTUBE_REFRESH_TOKEN_RU` secret — uploads no-op with a logged
      warning until it's set.
    EN channel paper-math now projects 11,000/day — the SAME paper
    level as the previous Tesla+MAB 2-Shorts config, which ran in
    production without quota failures (the documented-cost model is
    conservative vs. actual charging), so the daily preflight
    `::error::` annotation is expected until the increase lands.
    `estimate_network_daily_units` groups per channel since June 2026
    (a RU show never counts against the EN budget). Drift guards:
    `test_only_tst_and_mab_enable_youtube` pins the exact enabled set,
    `test_youtube_expansion_quota_shape` pins the 1-Short /
    Shorts-only / ru-channel shape so a partial revert fails CI.
    - **June 14 2026 — SpaceX Daily swapped in for MAB.** SpaceX Daily
      took MAB's EN-channel **full-format** slot (long-form + 1 Short);
      MAB's `youtube.enabled` flipped to `false` (rest of its block
      retained for a one-line re-enable). Same per-episode EN footprint,
      so the 11,000/day paper-math and the expected preflight `::error::`
      are unchanged. The EN full-format pair is now **Tesla + SpaceX**;
      FF + MIT stay Shorts-only; RU shows unchanged. `YOUTUBE_ENABLED_SHOWS`
      in `tests/test_schedule.py` updated accordingly. **All YouTube-enabled
      shows now generate imagery with Grok Imagine** (FF/MIT/RU previously
      inherited the `pexels` default → stock Shorts; now `image_provider:
      grok` is pinned, guarded by `test_all_youtube_shows_use_grok_imagine`).
      Operator one-time setup pending: create the SpaceX podcast playlist in
      Studio + flag it (landmine #15); uploads publish without it (warned).
    - **June 26 2026 — quota raised 10k → 200k; full-network rollout.** The
      @NerraNetwork quota increase landed, so the constrained shape above is
      undone (full rollout doc:
      [`docs/youtube_rollout_2026_06_25.md`](docs/youtube_rollout_2026_06_25.md)).
      `DEFAULT_DAILY_QUOTA` is now **200k**, env-overridable per channel
      (`YOUTUBE_DAILY_QUOTA[_EN|_RU]`, `resolve_daily_quota()`). **All 13 shows**
      publish to YouTube: FF + MIT flipped back to long-form, FPD added Shorts,
      MAB un-paused, and the 6 disabled shows (env_intel, planetterrian,
      omni_view, models_agents, models_agents_beginners, unintended_consequences)
      enabled with `image_provider: grok`. Tesla + SpaceX back to **2
      Shorts/episode**. EN steady state ≈ **24 uploads/day, ~45k units** (vs
      200k). Quota is no longer the constraint — **cadence is**: the preflight
      now warns (never blocks) above `SAFE_DAILY_UPLOADS_PER_CHANNEL` (default
      30, env `YOUTUBE_SAFE_DAILY_UPLOADS`), since YouTube's inauthentic-content
      policy penalises mass posting. Mitigations shipped same-day: LLM-optimized
      long-form titles separate from the spoken hook
      (`engine/youtube_titles.py`, `youtube.optimized_titles`) and the
      slideshow still-hold cap lowered 25 → 15 s for more motion network-wide
      (commit `6559b3a9`). None of these touch audio (outside landmine #17).
      **The hybrid Grok video-clip pilot on Tesla + SpaceX has since been
      REMOVED network-wide (commit `72d81cce`, June 29 2026): the Ep526 pilot
      showed ~1/3 clip success at ~$0.35/ep for the weakest payoff and pushed
      the render toward the 40-min pipeline timeout — the most expensive
      component for the least value (full Grok Video was already disabled
      June 23, commit `08021ebe`, as ~$40-50/ep). `video_clips_enabled` is
      `false` everywhere; motion now comes entirely from slideshow crossfades
      + varied Ken Burns over Grok Imagine stills. Recovery scripts
      (`scripts/recover_grok_video.py` et al.) still exist for any
      already-generated clips.** Enabled-set + 200k + 15 s cap pinned by
      `tests/test_schedule.py`, `tests/test_youtube_quota.py`,
      `tests/test_youtube_quality_pass.py`, `tests/test_config.py`. Operator
      one-time tasks: create/flag the 6 new shows' podcast playlists (landmine
      #15), confirm quota scope + set the env budget if EN-only, and enable
      Studio Title/Thumbnail "Test & Compare" (the runner stashes 3 title
      candidates).

21. **`min_articles_skip` is tuned per-show, not per-network (May 2026)**
    — `engine/config.py` defaults `min_articles_skip` to `3` (a show
    skips that day's run if fewer than 3 fresh articles survive
    fetch + dedup). The default is a deliberately weak floor; every
    show that needs a different threshold pins it explicitly in its
    YAML. Current pinned values:

    | Show | `min_articles_skip` | Rationale |
    |---|---|---|
    | `tesla` | 6 | Largest property; six-segment digest needs density. |
    | `omni_view` | 4 | World-news scan; below 4 the digest reads thin. |
    | `fascinating_frontiers` | 4 | Space/science; needs multiple beats. |
    | `models_agents` | 4 | AI news firehose; sub-4 means a quiet day → skip. |
    | `finansy_prosto` | 4 | Russian financial news scarcity → wait for a real day. |
    | `modern_investing` | (default 3) | Markets always produce 3+ stories on a weekday. |
    | `env_intel` | 2 | Alt-cadence (odd weekdays); 2 substantive stories enough. |
    | `models_agents_beginners` | 2 | Re-uses M&A pool; lower bar OK because tone is explanatory. |
    | `planetterrian` | 2 | Science/longevity/health show (NOT local news — that description was stale); primary-research days can be thin, so 2 is the realistic floor. |
    | `privet_russian` | 1 | Bilingual lesson show; one solid theme is sufficient. |
    | `unintended_consequences` | 0 | Narrative show — articles aren't the input, topic queue is. |
    | `first_principles` | 0 | Narrative show — topic queue is the input (alternates concrete example / opportunity area). |

    **Landmine:** changing the default from `3` would silently
    re-tune four shows (the ones currently pinned at `4` would still
    pass; the ones below `3` rely on the explicit override winning).
    Always change the per-show YAML, not the default. The
    `unintended_consequences` value of `0` is load-bearing — that
    show pulls from `shows/topic_queues/unintended_consequences.yaml`
    and never fetches news; raising it would block every episode.

22. **TSLA price source: multi-source fallback chain (May 2026)** —
    `shows/hooks/tesla.py:_fetch_tsla_price()` tries three sources
    in priority order until one returns a quote that passes
    validation:

    1. **`yfinance.Ticker.history(period="5d")`** — primary.  Same
       library + endpoint Modern Investing uses successfully every
       weekday.  yfinance manages a cookie + crumb-token session
       against Yahoo internally, which Yahoo's anti-bot trusts.
    2. **`yfinance.Ticker.fast_info`** — secondary.  Adds the live
       pre / post-market price when `history()` alone gives only
       end-of-day closes.  Treats `0.0` as falsy (the historical
       degraded-response failure mode) so it falls through cleanly.
    3. **Direct HTTP to Yahoo v8 chart API** — last resort.  Works
       locally and from some egress IPs but the bare `requests.get`
       call (no session cookies / no crumb token) is observed to
       return non-200s from GitHub Actions runner IPs at times.

    Each source returns `(price, prev_close, market_state)` or
    `None`; the same validation (`$200–$1500` sanity band, 25%
    deviation guard) gates every source, so a single bad source
    can't ship a wrong number.

    The `api/tsla.json` cache the hook writes is the single source
    the website's primary path reads.  Cache file records
    `"source": "yfinance_history"` / `"yfinance_fast_info"` /
    `"yahoo_v8_chart"` so the management dashboard can tell at a
    glance which path is winning — and notice if the primary has
    been silently failing for days.

    **Three prior fetchers failed and were superseded:**

    - **yfinance `fast_info` only (early 2026):** operator caught
      it repeatedly returning `$0.00 (price unavailable)`.  The
      `or` chain treated `0.0` as falsy and fell through every
      fallback to no data.  See git blame on commit `3247317`.
    - **Grok `x_search` (May 1–18 2026):** queried X for the latest
      `$TSLA` cashtag post.  Failed twice within 48 h.  TST Ep473
      (May 15) returned $250 vs a real ~$444 (Grok pulled from a
      stale post — caught by the deviation guard).  TST Ep474 (May
      16) returned `price == prev_close == $415.50` because the X
      post Grok latched onto only quoted a single number (caught
      by the operator).  X posts are not an authoritative quote
      source.
    - **Direct Yahoo HTTP only (PR #385, May 18 2026):** worked
      locally but Ep477 (May 19) + Ep478 (May 20) both shipped
      `(price unavailable)` on GitHub Actions.  Bare `requests.get`
      doesn't carry the cookie + crumb session yfinance manages,
      and Yahoo's anti-bot apparently treats GHA egress IPs
      differently for unauthenticated v8 calls than for
      session-managed yfinance calls to the same endpoint.

    **Subtle previous-close bug fixed at the same time:** the
    direct HTTP source originally read `meta.chartPreviousClose`
    as previous close.  That field is the close BEFORE the chart's
    range window (so for `range=5d` it's the close from 6 trading
    days ago — `$445.27` on 2026-05-20 vs the correct
    `$404.11` for yesterday).  The HTTP source now reads
    `indicators.quote[0].close[-2]` (the bar immediately before
    the latest), which mirrors what `yfinance.Ticker.history()`
    returns.  Meta fields are only fallbacks for null bar data.

    **Sanity band:** prices outside `$200 – $1500` are rejected.

    **Dynamic deviation guard:** new prices that swing more than
    25% from the last cached close are rejected.  Load-bearing
    under the Grok fetcher; kept on the multi-source chain as
    defence-in-depth (any single source's bad day still gets the
    chain to fall through to the next).

    **`yfinance` is now also the primary** — it remains required
    for Modern Investing's trade-execution pricing across many
    tickers, and now powers Tesla too.

    **Drift guards:** 31 unit tests in `tests/test_tesla_hook.py`
    pin per-source happy paths, chain fall-through semantics
    (source 1 fails → source 2 tries; source 1 + 2 fail → source
    3 tries), validation rejection forcing fall-through to the
    next source, `marketState: null` rendering as REGULAR (not
    After-hours), and persistence (success writes, failure does
    NOT overwrite the previous-good cache).  Plus the
    `test_bar_close_array_is_authoritative` guard explicitly
    pins the HTTP source on `indicators.quote[0].close[-2]` over
    `meta.chartPreviousClose`.
