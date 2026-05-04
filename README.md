# Nerra Network — Daily Podcast Network

Automated daily podcast generation system running **11 shows** via a unified
`run_show.py` runner + per-show YAML configs. Each show fetches news via RSS
and xAI/Grok web search, generates a digest and podcast script via xAI/Grok,
synthesizes audio via ElevenLabs TTS, mixes intro/outro music, and publishes
to RSS feeds, GitHub Pages, and X/Twitter.

All shows are produced independently in Vancouver, Canada.

**Website:** [nerranetwork.com](https://nerranetwork.com)

## Shows

| Show | Schedule | Player | RSS |
|------|----------|--------|-----|
| **Tesla Shorts Time** | Daily | [Player](https://nerranetwork.com/tesla.html) | [RSS](https://nerranetwork.com/podcast.rss) |
| **Omni View** | Odd days | [Player](https://nerranetwork.com/omni-view.html) | [RSS](https://nerranetwork.com/omni_view_podcast.rss) |
| **Fascinating Frontiers** | Even days | [Player](https://nerranetwork.com/fascinating_frontiers.html) | [RSS](https://nerranetwork.com/fascinating_frontiers_podcast.rss) |
| **Planetterrian Daily** | Odd days | [Player](https://nerranetwork.com/planetterrian.html) | [RSS](https://nerranetwork.com/planetterrian_podcast.rss) |
| **Environmental Intelligence** | Odd weekdays | [Player](https://nerranetwork.com/env-intel.html) | [RSS](https://nerranetwork.com/env_intel_podcast.rss) |
| **Models & Agents** | Odd days | [Player](https://nerranetwork.com/models-agents.html) | [RSS](https://nerranetwork.com/models_agents_podcast.rss) |
| **Models & Agents for Beginners** | Even days | [Player](https://nerranetwork.com/models-agents-beginners.html) | [RSS](https://nerranetwork.com/models_agents_beginners_podcast.rss) |
| **Финансы Просто** | Even days | [Player](https://nerranetwork.com/ru/finansy-prosto.html) | [RSS](https://nerranetwork.com/finansy_prosto_podcast.rss) |
| **Modern Investing Techniques** | Weekdays | [Player](https://nerranetwork.com/modern-investing.html) | [RSS](https://nerranetwork.com/modern_investing_podcast.rss) |
| **Привет, Русский!** | Even days | [Player](https://nerranetwork.com/ru/privet-russian.html) | [RSS](https://nerranetwork.com/privet_russian_podcast.rss) |

## Listen

All shows are available on **Apple Podcasts**, **Spotify**, and via **RSS**.

| Show | Apple Podcasts | Spotify |
|------|:---:|:---:|
| Tesla Shorts Time | [Apple](https://podcasts.apple.com/us/podcast/tesla-shorts-time-daily/id1855142939) | [Spotify](https://open.spotify.com/show/7I1DIaUaSlVsYliigOe6sS) |
| Omni View | [Apple](https://podcasts.apple.com/us/podcast/omni-view-balanced-news-perspectives/id1885661594) | [Spotify](https://open.spotify.com/show/4KuOgvZMm4Mweorshrm2qR) |
| Fascinating Frontiers | [Apple](https://podcasts.apple.com/us/podcast/fascinating-frontiers/id1864803923) | [Spotify](https://open.spotify.com/show/61S2fHlitcYUZZ0PmCkJYE) |
| Planetterrian Daily | [Apple](https://podcasts.apple.com/us/podcast/planetterrian-daily/id1857782085) | [Spotify](https://open.spotify.com/show/0GgrsEDFLaZfTOQkQm5DI2) |
| Models & Agents | [Apple](https://podcasts.apple.com/us/podcast/models-agents/id1885231539) | [Spotify](https://open.spotify.com/show/28dfMGTVsgQxPuUs7YoJYD) |
| M&A for Beginners | [Apple](https://podcasts.apple.com/us/podcast/models-agents-for-beginners/id1885231582) | [Spotify](https://open.spotify.com/show/7vRUrQAJWzOB729A9aVDd5) |
| Modern Investing | [Apple](https://podcasts.apple.com/us/podcast/modern-investing-techniques/id1886870483) | [Spotify](https://open.spotify.com/show/2Txa9atsocnmm91r65Ahy9) |
| Финансы Просто | [Apple](https://podcasts.apple.com/us/podcast/%D1%84%D0%B8%D0%BD%D0%B0%D0%BD%D1%81%D1%8B-%D0%BF%D1%80%D0%BE%D1%81%D1%82%D0%BE/id1885235226) | [Spotify](https://open.spotify.com/show/35jCJTVe3ITGah3ryeKzzM) |
| Привет, Русский! | [Apple](https://podcasts.apple.com/us/podcast/%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D1%80%D1%83%D1%81%D1%81%D0%BA%D0%B8%D0%B9/id1885236720) | [Spotify](https://open.spotify.com/show/7rB9mPNBp5S6RCpHPKIZbL) |

## Architecture

```
run_show.py                     # Unified entry point for all shows
├── engine/                     # Shared modules (22 files)
│   ├── config.py               # YAML-based show configuration
│   ├── fetcher.py              # RSS feed fetching + keyword scoring
│   ├── generator.py            # xAI/Grok LLM digest + podcast generation
│   ├── tts.py                  # ElevenLabs TTS synthesis
│   ├── audio.py                # ffmpeg audio processing + music mixing
│   ├── publisher.py            # RSS feed update, GitHub Pages, X posting
│   ├── content_tracker.py      # Cross-episode deduplication
│   ├── newsletter.py           # Buttondown newsletter integration
│   ├── storage.py              # Cloudflare R2 audio storage
│   ├── blog.py                 # Blog post generation
│   ├── chapters.py             # MP3 chapter markers
│   ├── transcripts.py          # Episode transcript generation
│   ├── synthesizer.py          # Newsletter/report content synthesis
│   ├── tracking.py             # API usage + cost tracking
│   ├── validation.py           # Output validation + repair
│   └── utils.py                # Text processing, similarity, helpers
├── shows/                      # Per-show configuration
│   ├── _defaults.yaml          # Network-wide defaults (TTS, audio, storage)
│   ├── *.yaml                  # Show configs (sources, LLM, TTS, publishing)
│   ├── prompts/                # LLM prompt templates (4 per show)
│   ├── hooks/                  # Show-specific pre-fetch hooks
│   ├── segments/               # Slow-news segment libraries
│   └── templates/              # Jinja2 templates for shows
├── digests/                    # Generated output (audio, markdown, JSON)
│   └── <show>/                 # Per-show subdirectories
├── assets/
│   ├── music/                  # Intro/outro music files
│   └── pronunciation.py        # Shared TTS pronunciation fixes
├── scripts/                    # Utility scripts (dashboard, audits, etc.)
├── styles/
│   └── main.css                # Shared stylesheet (dark theme, glassmorphism)
├── .github/workflows/
│   ├── run-show.yml            # Unified daily cron workflow (all shows)
│   ├── test.yml                # CI test + lint
│   ├── dashboard.yml           # Management dashboard updates
│   └── ...                     # Feed audit, newsletters, reports, etc.
└── *.rss                       # Podcast RSS feeds
```

### Pipeline (per show, per run)

1. **Load config** from `shows/<show>.yaml` (merged with `_defaults.yaml`)
2. **Pre-fetch hook** (optional — e.g., Tesla stock price via yfinance)
3. **Fetch** news from RSS sources + xAI/Grok web search
4. **Dedup** via ContentTracker (cross-episode) + entity dedup
5. **Generate** digest text via xAI/Grok API
6. **Generate** podcast script via xAI/Grok API
7. **Synthesize** audio via ElevenLabs TTS (with chunking + section-aware synthesis)
8. **Mix** intro/outro music with voice (ffmpeg)
9. **Upload** to Cloudflare R2
10. **Update** RSS feed + chapter markers
11. **Generate** blog post, transcript
12. **Save** summary to GitHub Pages JSON
13. **Send** newsletter (if configured)
14. **Post** X/Twitter teaser (if configured)

## Usage

```bash
# Run a show (full pipeline)
python run_show.py tesla

# Test mode (fetch + digest only, no TTS/posting)
python run_show.py omni_view --test

# Dry run (print plan, no API calls)
python run_show.py env_intel --dry-run

# Skip specific steps
python run_show.py tesla --skip-x --skip-newsletter
python run_show.py fascinating_frontiers --skip-podcast

# Regenerate all HTML pages
python generate_html.py --all
```

### Available shows

`tesla`, `omni_view`, `fascinating_frontiers`, `planetterrian`, `env_intel`, `models_agents`, `models_agents_beginners`, `finansy_prosto`, `modern_investing`, `privet_russian`

## Adding a New Show

1. Create `shows/<slug>.yaml` with sources, LLM, TTS, audio, and publishing config
2. Create `shows/prompts/<slug>_digest.txt`, `<slug>_podcast.txt`, `<slug>_system.txt`, `<slug>_weekly.txt`
3. Optionally create `shows/hooks/<slug>.py` for pre-fetch logic
4. Add the slug to `run_show.py` choices
5. Add cron schedule to `.github/workflows/run-show.yml`
6. Add show config to `generate_html.py` and run `python generate_html.py --all`

## Testing

```bash
pytest                           # Run all tests
pytest tests/test_utils.py       # Pure function tests
pytest tests/test_rss.py         # RSS feed validation
pytest tests/test_audio_commands.py  # ffmpeg command structure
pytest tests/test_integration.py # Pipeline integration tests
```

## Environment Variables

See `docs/env_var_inventory.md` for the complete list. Key variables:

- `GROK_API_KEY` — xAI/Grok API (all shows)
- `ELEVENLABS_API_KEY` — ElevenLabs TTS (all shows)
- `X_*` / `PLANETTERRIAN_X_*` — X/Twitter credentials
- `R2_*` — Cloudflare R2 storage
- `BUTTONDOWN_API_KEY` — Buttondown newsletter

### Analytics & Marketing (optional)

These activate Google Analytics 4, Google Ads conversion tracking, or Plausible
when set. All default to disabled — leaving them unset keeps the website
analytics-free.

- `GA4_MEASUREMENT_ID` — Google Analytics 4 property ID (e.g. `G-XXXXXXX`)
- `GOOGLE_ADS_ID` — Google Ads conversion ID (e.g. `AW-1234567890`)
- `GOOGLE_ADS_SIGNUP_LABEL` — Conversion label fired on newsletter signup
- `PLAUSIBLE_DOMAIN` — Plausible Analytics domain (e.g. `nerranetwork.com`)

When any GA4/Ads ID is set:
- gtag.js loads and Google Consent Mode v2 defaults all storage to `denied`
- A cookie consent banner asks visitors before any tracking cookies are set
- Newsletter form submits and Apple/Spotify clicks fire conversion events
- All outbound subscription links carry UTM parameters for source attribution

Podcast download analytics (OP3) are enabled by default for all shows in
`shows/_defaults.yaml` — listener stats appear at https://op3.dev once
deployed.

## Documentation

- `CLAUDE.md` — Detailed architecture reference and known issues
- `docs/env_var_inventory.md` — Environment variable reference
- `docs/pipeline_audit_april2026.md` — Latest pipeline audit and fixes
- `docs/audio_storage_plan.md` — R2 migration strategy
- `docs/newsletter_comparison.md` — Newsletter platform evaluation
- `docs/podcast_directories.md` — Directory submission guide
- `docs/monetization_roadmap.md` — Revenue strategy and timeline
