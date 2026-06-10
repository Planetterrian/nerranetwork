# CLAUDE.md — Tesla Shorts Time Podcast Network

## Project Overview

Automated daily podcast generation system running 12 shows via a unified
`run_show.py` runner + per-show YAML configs, plus 4 legacy standalone scripts
(deprecated — see note below). Shows use **Grok TTS** (`engine.tts.grok_speak_chunk`)
and (where enabled) post to X/Twitter via `engine/publisher.post_to_x()`.

| Show | Legacy Script | YAML Config | Schedule | X Account | TTS |
|------|--------------|-------------|----------|-----------|-----|
| Tesla Shorts Time | — (deleted) | `shows/tesla.yaml` | Daily | `@teslashortstime` | Grok TTS (custom) |
| Omni View | — (deleted) | `shows/omni_view.yaml` | Daily | `@omniviewnews` | Grok TTS (custom) |
| Fascinating Frontiers | — (deleted) | `shows/fascinating_frontiers.yaml` | Daily | `@planetterrian` | Grok TTS (custom) |
| Planetterrian Daily | — (deleted) | `shows/planetterrian.yaml` | Daily | `@planetterrian` | Grok TTS (custom) |
| Env Intel | — | `shows/env_intel.yaml` | Odd weekdays | `@teslashortstime` | Grok TTS (custom) |
| Models & Agents | — | `shows/models_agents.yaml` | Daily | — (X disabled) | Grok TTS (custom) |
| Models & Agents for Beginners | — | `shows/models_agents_beginners.yaml` | Daily | — (X disabled) | Grok TTS (custom) |
| Финансы Просто | — | `shows/finansy_prosto.yaml` | Even days | — (X disabled) | Grok TTS (Olya) |
| Modern Investing Techniques | — | `shows/modern_investing.yaml` | Daily | — (X disabled) | Grok TTS (custom) |
| Привет, Русский! | — | `shows/privet_russian.yaml` | Even days | — (X disabled) | Grok TTS (Olya) |
| Unintended Consequences | — | `shows/unintended_consequences.yaml` | Weekdays | — (X disabled) | Grok TTS (custom) |
| First Principles Daily | — | `shows/first_principles.yaml` | Daily | — (X disabled) | Grok TTS (custom) |

> Sunday recap: shows on a daily cadence with `weekly_recap_on_sunday: true`
> in their YAML have their Sunday slot rewritten as a weekly-recap episode
> synthesised from the past 7 days via the content lake — the daily news
> fetch is skipped. See landmine #19.

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
│   ├── tts.py                     # ElevenLabs TTS (auth, chunking, synthesis)
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

- **FF and PT** are "nearly identical twins" — same structure, same functions,
  different news topics and X account
- **TST** shares most patterns with FF/PT but adds: complex pronunciation
  fixes, content tracking, chunked TTS, x_search stock data, TST-specific
  emoji formatting via `engine.publisher.format_tst_digest_for_x()`
- **OV** is structurally different — different TTS approach (no streaming, uses
  env vars for voice settings), simpler functions
- **EI** runs exclusively via `run_show.py` + `shows/env_intel.yaml`; no legacy script
- **M&A** (Models & Agents) runs exclusively via `run_show.py` +
  `shows/models_agents.yaml`; no legacy script. X posting disabled.
- **MAB** (Models & Agents for Beginners) runs via `run_show.py` +
  `shows/models_agents_beginners.yaml`; beginner/teen-focused version of M&A.
  Uses **ElevenLabs TTS**. X posting disabled.
- **FP** (Финансы Просто) runs via `run_show.py` +
  `shows/finansy_prosto.yaml`; Russian-language financial literacy podcast
  for women in Canada. Uses **ElevenLabs TTS** (`eleven_flash_v2_5`
  with `language_code: ru`). All content generated in Russian. X posting disabled.
- **MIT** (Modern Investing Techniques) runs via `run_show.py` +
  `shows/modern_investing.yaml`; daily investing podcast focused on Canadian
  and US markets. Weekdays only. X posting disabled.
  **June 2026 quality pass** (drift guards: `tests/test_mit_quality_pass.py`):
  the recursive-learning loop had been DEAD on every episode —
  `_analyze_strategy_patterns` was called but never defined, the NameError
  was swallowed by pre_fetch's try/except, and all three learning blocks
  shipped as "temporarily unavailable" (now implemented: FAVOR/AVOID sector
  guidance). Two trades closed with NaN exit prices (yfinance returns NaN
  floats that pass `is None`) had poisoned `cumulative_pnl` into NaN —
  "Running Total: $nan" on air; all aggregations now route through
  `_finite()` and `_close_trade` rejects non-finite prices. The summary
  gained `cumulative_alpha_vs_nasdaq` (the headline metric previously read
  from a key that never existed — actual record: +20.6% across 26
  benchmarked trades, finally stated on air via the portfolio block).
  Lesson cooldowns now ESCALATE with teach-count (flat 21d let
  bid_ask_spread reteach 13×; every 3 repeats adds a full period, cap
  180d). Trade extraction logs loudly on formatting drift vs quiet on
  deliberate no-trade days. MIT opts into `podcast_expand_below_target`,
  gets a hook-led X teaser linking the episode blog + performance page,
  and the deep-dive queue carries a 6-entry evergreen Canadian bench
  (operator schedules via `when: next`). Prompt edits (no-trade platitude
  ban, Market Pulse macro frame) change output — A/B-listen per landmine
  #17.

**Tesla Shorts Time Recursive Memory System (May 2026+)**  
TST received a full recursive improvement architecture (analogous to MIT):
- `engine/tesla_memory.py` + three persistent trackers in `digests/tesla_shorts_time/`:
  `tesla_narrative_tracker.json` (major programs with status, claims, confidence),
  `tesla_performance_tracker.json` (YouTube/Shorts signals for emphasis),
  `tesla_theme_history.json` (mined from transcripts/digests).
- Injected on every episode via `shows/hooks/tesla.py` pre_fetch → rich context blocks
  (`tesla_narrative_status_block`, performance signals, theme context).
- Prompt updates in both digest and podcast prompts.
- Public page `tesla-narrative.html` (generated nightly + on demand).
- Post-episode hook + Sunday recap integration.
- Operator tooling: `scripts/update_tesla_narrative.py` for easy updates without hand-editing JSON.
- Goal: TST becomes the best long-term public chronicle of Tesla's major programs while
  continuously optimizing for real audience engagement.
- **June 2026 quality pass** (drift guards: `tests/test_tesla_quality_pass.py`):
  theme mining now reads the DIGEST only (the old code mined the narrative
  TEMPLATE text every episode — "open questions" hit count 112 and drowned
  real topics; `_THEME_STOPWORDS` + a one-time scrub fixed existing
  histories). `auto_update_narrative_from_digest` auto-advances per-program
  `last_mentioned_episode/date` on every episode (the tracker had sat 13
  days stale on a daily show) — operator-curated `status` text still only
  changes via `scripts/update_tesla_narrative.py`. The listener-value score
  gained a 15%-weight length component (`target_words` kwarg). Tesla opts
  into `llm.podcast_expand_below_target: true` — the one-shot expansion
  retry fires on ANY below-target script, not only near the 60% skip floor
  (9 of 10 episodes had shipped 15-35% under the 1600-word target). The X
  teaser leads with the episode hook + links the episode blog post. The
  prompts ban the "Taking a step back from today's headlines" opener,
  rotate three First Principles frameworks, cap the vertical-integration
  conclusion, enforce the Takeover/Top-12 zero-overlap check, and add
  3-tier attribution discipline. Prompt changes alter generated output —
  A/B-listen per landmine #17 and revert via git if quality dips.
- **June 10 2026 follow-up pass** (full review:
  [`docs/tesla_review_2026_06_10.md`](docs/tesla_review_2026_06_10.md);
  drift guards in `tests/test_tesla_quality_pass.py`,
  `tests/test_chapters.py::TestPositionalConstraints`,
  `tests/test_tesla_hook.py::TestClosingBlock`):
  chapter markers gained positional `where: start|end` constraints +
  once-per-title matching (the closing's "tesla shorts time" mention had
  titled the closing "Introduction" on every episode); the spoken closing
  now rotates 4 variants, phrases by market state, and OMITS the price
  sentence when the quote failed validation (previously spoke "closed at
  zero dollars, price unavailable"); the expansion retry now carries the
  full digest (it previously saw only its own short script — it could not
  add facts, the root cause of chronic under-length); ONE unified length
  target (2,200–2,400 words ≈ 14–16 min, `min_podcast_words: 2000` — the
  prompt had demanded four contradictory lengths); the performance loop is
  LIVE (`scripts/update_tesla_performance.py` nightly derives
  `strong_topics_last_30d` from OP3 download data — `record_performance_signal`
  previously had zero callers); theme mining filters narrative-prose echo +
  URLs and is idempotent per episode; program detection uses word-boundary
  regexes (bare "unsupervised" no longer advances FSD); the spoken show
  name dropped "Daily" to match the listing brand "Tesla Shorts Time";
  content-tracker headlines filter junk/slur titles
  (`_is_dedupe_worthy_title`); blog posts link the Story Tracker page.
  Length/brand prompt changes alter shipped audio — A/B-listen per
  landmine #17.
- **June 10 2026 four-show pass** (MIT, M&A, MAB, FF; full review:
  [`docs/four_show_review_2026_06_10.md`](docs/four_show_review_2026_06_10.md);
  drift guards: `tests/test_four_show_quality_pass.py`): every show's
  Closing chapter pattern now matches every closing-pool variant (MAB had
  shipped 50% of episodes with NO Closing chapter; M&A's bare `agent`
  pattern opened a spurious chapter ~30s into every episode) with
  `where: start|end` positional anchors; ONE unified length target per
  prompt (MIT 2,000-2,200w/floor 1800; M&A 1,600-2,200w; FF
  1,900-2,200w/floor 1700; MAB floor 1200) replacing contradictory
  anchors; `engine/show_memory.py` gained all four Tesla memory fixes
  (narrative-prose echo filter, per-episode idempotency, URL stripping,
  word-boundary program detection) + `update_performance_from_op3`; the
  nightly performance step generalized to
  `scripts/update_performance_trackers.py` (Tesla + M&A + FF + PT); the
  three memory shows' theme histories were re-scrubbed; MAB's "So
  imagine" opener tic (49 of 60 episodes — the prompt's own example was
  the template) now requires rotating opener shapes. Length/opener
  prompt edits change output — A/B-listen per landmine #17.
- **PR** (Привет, Русский!) runs via `run_show.py` +
  `shows/privet_russian.yaml`; bilingual Russian language learning podcast
  for English speakers. Even days only. Uses **ElevenLabs TTS**
  (`eleven_flash_v2_5` with `language_code: ru`). X posting disabled.
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
- `ELEVENLABS_API_KEY` — ElevenLabs TTS (all shows)
- `X_*` / `PLANETTERRIAN_X_*` — two separate X accounts
- Voice IDs: **All 11 shows are on Grok TTS** as of the May 2026 full-network migration. The 8 English shows (including Tesla Shorts Time) share the operator's custom-trained voice `kdif6sqjcyiq`. Russian shows (FP/PR) use the custom Olya voice `0b875ae2`. ElevenLabs is no longer used in production but the API key + legacy settings stay in `_defaults.yaml` for emergency rollback. See landmine #17.
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
when `gallery_enabled` is true (today: any show with
`youtube.enabled: true`, currently Tesla + MAB — see landmine #20).
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
  - `scripts/youtube_quota_preflight.py` — sums quota for YouTube-enabled shows
    and annotates when projected over the 10k/day budget (landmine #20). Wired
    as a preflight step in `run-show.yml`.
  - `scripts/post_run_summary.py` — positive heartbeat: composes an all-clear /
    cost / quota / RSS-freshness line from `api/dashboard.json` and POSTs to
    `NOTIFICATION_WEBHOOK_URL` (clean no-op when unset). Wired into the finalize
    job.

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
- **Финансы Просто YouTube category** fixed 25 (News) → 27 (Education).
- **Operator items (not code):** localize the Russian shows' spoken AI
  disclosure (still English on the Olya voice — A/B per #17); decide
  First Principles distribution-on after the queue/length fixes settle
  (review recommends waiting to ~Ep15); confirm X handles for the
  X-enabled shows so the follow CTA can be set.

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
- All 12 shows now run via `run_show.py` + YAML configs in production (CI/CD).
- Legacy scripts (`digests/{tesla_shorts_time,omni_view,fascinating_frontiers,
  planetterrian}.py`) are **deprecated** — retained for reference only.
- `run_show.py` is the canonical entry point; legacy scripts are not called
  by any workflow or cron job.

## Known Landmines

**Operator's first stop:** the live state of every landmine below is rendered
by [`management.html`](management.html), fed by
[`scripts/generate_dashboard.py`](scripts/generate_dashboard.py) → `api/dashboard.json`.
Items 7 and 10 are intentionally excluded from the dashboard (per an explicit
decision); everything else has a live status card.

### Active Issues

1. **2.2 GB of MP3s in git** — repo will hit GitHub's 10 GB limit within ~6
   months at current growth. Cloudflare R2 migration recommended.
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
    yet have the recovery escape hatch (lower risk callers). Drift guard:
    the recovery script + the warning annotation in the Actions log.

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
    - **Voice EQ chain** (`engine/audio.py:_voice_norm_full_cmd`)
      gained a 6.5 kHz dip (`equalizer=f=6500:t=q:w=1.5:g=-3`) for
      gentle de-essing on the new custom voice. Previous chain
      (highpass / lowpass / loudnorm / compressor / limiter) is
      otherwise unchanged.
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

19. **Schedule overhaul + Sunday weekly recap (May 2026)** — 7 shows
    moved to daily cadence (Omni View, Planetterrian, Fascinating
    Frontiers, Models & Agents, MAB, Modern Investing, Tesla). Cron
    times shifted +1h across the board to widen the per-slot window;
    last show now finishes ~12 UTC (~8 AM ET). The `weekly_recap_on_sunday:
    true` flag in each daily show YAML opts that show into a Sunday-only
    pipeline branch in `run_show.py`: when today is Sunday and the flag
    is set, the runner skips the news fetch + LLM digest stage and instead
    calls `engine.weekly_recap.build_weekly_recap_digest` to synthesise a
    digest-shaped summary from the past 7 days of episodes pulled from
    the content lake. The synthetic digest is fed through the unchanged
    podcast prompt + TTS pipeline so listeners get the same narrative
    quality as a daily episode. Modern Investing additionally has a
    Saturday "weekend mode" instruction in its podcast prompt covering
    international markets, crypto, lessons learned, and what to prepare
    for in the coming weeks. Drift guards in `tests/test_schedule.py`
    pin: cron consistency, the 7 daily shows carrying the recap flag,
    alt-cadence shows NOT carrying it, and the YouTube quota cap
    (only TST and MAB enabled — see also landmine #20).

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
