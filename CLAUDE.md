# CLAUDE.md — Tesla Shorts Time Podcast Network

## Project Overview

Automated daily podcast generation system running 10 shows via a unified
`run_show.py` runner + per-show YAML configs, plus 4 legacy standalone scripts
(deprecated — see note below). Shows use **ElevenLabs TTS** (`eleven_flash_v2_5`) and post to X/Twitter via
`engine/publisher.post_to_x()`.

| Show | Legacy Script | YAML Config | Schedule | X Account | TTS |
|------|--------------|-------------|----------|-----------|-----|
| Tesla Shorts Time | — (deleted) | `shows/tesla.yaml` | Daily | `@teslashortstime` | Grok TTS (custom) |
| Omni View | — (deleted) | `shows/omni_view.yaml` | Odd days | `@omniviewnews` | Grok TTS (custom) |
| Fascinating Frontiers | — (deleted) | `shows/fascinating_frontiers.yaml` | Even days | `@planetterrian` | Grok TTS (custom) |
| Planetterrian Daily | — (deleted) | `shows/planetterrian.yaml` | Odd days | `@planetterrian` | Grok TTS (custom) |
| Env Intel | — | `shows/env_intel.yaml` | Odd weekdays | `@teslashortstime` | Grok TTS (custom) |
| Models & Agents | — | `shows/models_agents.yaml` | Odd days | — (X disabled) | Grok TTS (custom) |
| Models & Agents for Beginners | — | `shows/models_agents_beginners.yaml` | Even days | — (X disabled) | Grok TTS (custom) |
| Финансы Просто | — | `shows/finansy_prosto.yaml` | Even days | — (X disabled) | Grok TTS (Olya) |
| Modern Investing Techniques | — | `shows/modern_investing.yaml` | Weekdays | — (X disabled) | Grok TTS (custom) |
| Привет, Русский! | — | `shows/privet_russian.yaml` | Even days | — (X disabled) | Grok TTS (Olya) |

**Science That Changes Everything** (`digests/science_that_changes.py`, ~83 lines)
is a standalone X-posting script, not a podcast show.

## Architecture

### Pipeline (per show, per run)

1. **Fetch** news sources (RSS, xAI/Grok web search, yfinance for Tesla)
2. **Dedup** via ContentTracker (cross-episode) + entity dedup
3. **Generate** digest text via xAI/Grok API
4. **Synthesize** podcast audio via ElevenLabs TTS (`eleven_flash_v2_5`)
5. **Mix** intro/outro music with voice (ffmpeg) — all shows (configurable per YAML)
6. **Post** X thread via `engine/publisher.post_to_x()` + update RSS feed + commit output to git

### Key Directories

```
nerranetworks/
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
  fixes, content tracking, chunked TTS, yfinance stock data, TST-specific
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
- **PR** (Привет, Русский!) runs via `run_show.py` +
  `shows/privet_russian.yaml`; bilingual Russian language learning podcast
  for English speakers. Even days only. Uses **ElevenLabs TTS**
  (`eleven_flash_v2_5` with `language_code: ru`). X posting disabled.
- All shows delegate X posting to `engine.publisher.post_to_x()`
- TST/FF/PT delegate voice normalization to `engine.audio.normalize_voice()`
- All shows use `engine.audio.mix_with_music()` for music mixing (3 modes:
  standard, delayed-intro, dual-music). Music files in `assets/music/`.
  Shows without music files gracefully fall back to voice-only.

## Conventions

### Environment Variables

- All secrets come from `.env` (local) or GitHub Actions secrets
- `GROK_API_KEY` — primary xAI key (all shows)
- `ELEVENLABS_API_KEY` — ElevenLabs TTS (all shows)
- `X_*` / `PLANETTERRIAN_X_*` — two separate X accounts
- Voice IDs: **All 10 shows are on Grok TTS** as of the May 2026 full-network migration. The 8 English shows (including Tesla Shorts Time) share the operator's custom-trained voice `b4cusb2omvkz`. Russian shows (FP/PR) use the custom Olya voice `0b875ae2`. ElevenLabs is no longer used in production but the API key + legacy settings stay in `_defaults.yaml` for emergency rollback. See landmine #17.
- See `docs/env_var_inventory.md` for the complete inventory

### RSS Feeds

All RSS `<enclosure>` URLs now use `audio.nerranetwork.com` (Cloudflare R2).
MP3 files are uploaded to R2 during the pipeline and excluded from git commits.
**Do NOT change R2 bucket paths — this breaks podcast subscribers.**

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

### Code Style

- No linter configured; scripts are large single-file programs
- Functions are defined inline (not imported), which is why we're extracting
- `logging` for all output; `sys.stdout` handler
- `pathlib.Path` for all file operations
- `tenacity` for retry logic on API calls

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
- All 10 shows now run via `run_show.py` + YAML configs in production (CI/CD).
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
    wave) all use the operator's custom-trained voice `b4cusb2omvkz`
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
    operator's custom-trained voice `b4cusb2omvkz` from
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
      including Tesla resolves to `b4cusb2omvkz`),
      `test_no_show_uses_elevenlabs_in_production` (catches accidental
      rollback flips), and `test_russian_shows_use_grok_tts` (Olya
      voice unchanged).

    `ELEVENLABS_API_KEY` is **kept** in GitHub Secrets / `.env` for
    emergency rollback even though no show currently needs it. The
    legacy ElevenLabs settings in `_defaults.yaml` (model, stability,
    similarity_boost, style, etc.) are also preserved — harmless under
    `provider=grok` and a one-line YAML flip back to ElevenLabs if
    Grok TTS has an outage.
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
