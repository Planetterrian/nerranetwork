# Nerra Network — Daily Podcast Network

Automated daily podcast generation system running **11 shows** via a unified
`run_show.py` runner + per-show YAML configs. Each show fetches news via RSS
and xAI/Grok web search (or topic queues for narrative shows), generates a
digest and podcast script via xAI/Grok, synthesizes audio via Grok TTS (full
network migration May 2026; ElevenLabs retained only as emergency rollback),
mixes intro/outro music, and publishes to RSS, GitHub Pages, YouTube (long-form
+ smart Shorts for enabled shows), and X/Twitter where configured.

Nerra Network produces shows for a **global audience** — independently produced
in **Vancouver, British Columbia, Canada**. Globally focused shows (Tesla Shorts
Time, Models & Agents, Fascinating Frontiers, etc.) carry no regional constraint;
shows with a Canadian focus (Modern Investing Techniques, Финансы Просто,
Environmental Intelligence) cover Canadian markets, policy, and personal finance
alongside their global context.

**Website:** [nerranetwork.com](https://nerranetwork.com)

## Shows

| Show | Schedule | Player | RSS |
|------|----------|--------|-----|
| **Tesla Shorts Time** | Daily | [Player](https://nerranetwork.com/tesla.html) | [RSS](https://nerranetwork.com/podcast.rss) |
| **Omni View** | Daily (Sun = weekly recap) | [Player](https://nerranetwork.com/omni-view.html) | [RSS](https://nerranetwork.com/omni_view_podcast.rss) |
| **Fascinating Frontiers** | Daily (Sun = weekly recap) | [Player](https://nerranetwork.com/fascinating_frontiers.html) | [RSS](https://nerranetwork.com/fascinating_frontiers_podcast.rss) |
| **Planetterrian Daily** | Daily (Sun = weekly recap) | [Player](https://nerranetwork.com/planetterrian.html) | [RSS](https://nerranetwork.com/planetterrian_podcast.rss) |
| **Environmental Intelligence** | Odd weekdays | [Player](https://nerranetwork.com/env-intel.html) | [RSS](https://nerranetwork.com/env_intel_podcast.rss) |
| **Models & Agents** | Daily (Sun = weekly recap) | [Player](https://nerranetwork.com/models-agents.html) | [RSS](https://nerranetwork.com/models_agents_podcast.rss) |
| **Models & Agents for Beginners** | Daily (Sun = weekly recap) | [Player](https://nerranetwork.com/models-agents-beginners.html) | [RSS](https://nerranetwork.com/models_agents_beginners_podcast.rss) |
| **Финансы Просто** | Even days | [Player](https://nerranetwork.com/ru/finansy-prosto.html) | [RSS](https://nerranetwork.com/finansy_prosto_podcast.rss) |
| **Modern Investing Techniques** | Daily (Sat = weekend angle, Sun = recap) | [Player](https://nerranetwork.com/modern-investing.html) | [RSS](https://nerranetwork.com/modern_investing_podcast.rss) |
| **Привет, Русский!** | Even days | [Player](https://nerranetwork.com/ru/privet-russian.html) | [RSS](https://nerranetwork.com/privet_russian_podcast.rss) |
| **Unintended Consequences** | Weekdays (narrative) | [Player](https://nerranetwork.com/unintended-consequences.html) | [RSS](https://nerranetwork.com/unintended_consequences_podcast.rss) |

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
| Привет, Русский! | [Apple](https://podcasts.apple.com/us/podcast/%D0%BF%D1%80%D0%B1%D0%B8%D0%B2%D0%B5%D1%82-%D1%80%D1%83%D1%81%D1%81%D0%BA%D0%B8%D0%B9/id1885236720) | [Spotify](https://open.spotify.com/show/7rB9mPNBp5S6RCpHPKIZbL) |
| Unintended Consequences | Search "Nerra Network" on Apple | Search "Nerra Network" on Spotify |

## Architecture

```
run_show.py                     # Unified entry point for all 11 shows
├── engine/                     # ~50 shared modules (see engine/ + CLAUDE.md)
│   ├── config.py               # YAML deep-merge + ShowConfig dataclasses
│   ├── fetcher.py              # RSS + web_search + x_search
│   ├── generator.py            # Grok LLM digest/script (refusals, fallbacks)
│   ├── tts.py                  # Grok TTS (primary) + ElevenLabs (rollback)
│   ├── audio.py                # ffmpeg mix + normalize + sidechain ducking
│   ├── publisher.py            # RSS, GitHub Pages, X, thumbnails, end-cards
│   ├── content_tracker.py      # Cross-episode dedup + cooldowns
│   ├── content_lake.py         # SQLite for weekly recaps, briefings, search
│   ├── weekly_recap.py         # Sunday synthetic digest from lake (7 shows)
│   ├── shorts_selector.py      # Heuristic "most engaging" window picker
│   ├── youtube*.py + video.py  # Long-form + multi-Shorts (smart + hashtags)
│   ├── gallery_uploader.py     # Grok-Imagine scenes → R2 + sidecars
│   ├── tracking.py             # Per-ep LLM/TTS/X/Imagine cost rollup
│   ├── metrics.py              # Stage timings + counters (dashboard fuel)
│   ├── newsletter*.py          # Sanitizer + body transforms + template (v2)
│   └── ...                     # transcripts, chapters, grok_imagine, etc.
├── shows/                      # Per-show configuration (11 + _defaults)
│   ├── *.yaml                  # Sources, LLM, TTS, audio, youtube, hooks
│   ├── prompts/                # digest / podcast / system / weekly
│   ├── hooks/                  # Pre-fetch (Tesla TSLA price, etc.)
│   └── topic_queues/           # Narrative shows (Unintended Consequences)
├── digests/                    # All generated output (per-show subdirs)
├── workers/gallery/            # Cloudflare Worker (email-gate + JWT + R2 proxy)
├── assets/
│   ├── music/                  # Centralized intro/outro (per-show)
│   └── pronunciation.py        # Shared TTS fixes + map
├── scripts/                    # 30+ ops tools (scaffold, dashboard, audits, backfills)
├── .github/workflows/          # 12 workflows (staggered cron + matrix + landmines)
└── *.rss + *.html            # Public RSS feeds + static site
```

See `CLAUDE.md` (operator bible) and `docs/` for the full current module list and 20+ live landmines tracked on the management dashboard.

### Pipeline (per show, per run)

1. **Load + preflight** config (YAML + _defaults deep merge, env keys, prompts, music, cost circuit breaker, LLM ping)
2. **Pre-fetch hook** (optional, e.g. yfinance TSLA) + resume decision (publish / YouTube only)
3. **Fetch + dedup** (RSS + Grok web_search + X accounts, multi-layer ContentTracker + entity + sim + lake)
4. **Digest** (or Sunday weekly recap from content lake for 7 shows)
5. **Podcast script** (with pronunciation, chapters, AI disclosure, length gates)
6. **TTS** (Grok single-chunk primary; section stings optional) + Whisper transcript
7. **Audio mix** (music ducking, EBU R128 -16 LUFS, chapters JSON)
8. **Upload + publish** (R2 + OP3, post-run validation hard gate, RSS + chapters, GitHub Pages, blog)
9. **YouTube** (long-form + N smart Shorts with per-word captions, auto-hashtags, end-card CTA — only TST + MAB enabled due to quota)
10. **Gallery side-effect** (Grok-Imagine scenes → nerra-gallery R2 + thumbs + sidecars for enabled shows)
11. **Newsletter + X** (sanitized, Buttondown tag-aware; teaser with YouTube link)
12. **Metrics + lake write** (full cost + timing + entity extraction for recaps)

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

`tesla`, `omni_view`, `fascinating_frontiers`, `planetterrian`, `env_intel`, `models_agents`, `models_agents_beginners`, `finansy_prosto`, `modern_investing`, `privet_russian`, `unintended_consequences`

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

## Recent Improvements & Roadmap (May 2026+)

Major 2026 milestones shipped:
- Full-network Grok TTS migration (36× cheaper than previous ElevenLabs baseline; custom trained voice for consistent host identity across English shows).
- YouTube Shorts production for Tesla Shorts Time + Models & Agents for Beginners (smart segment selection, per-word highlighting, auto-hashtags, end-screen CTAs, multi-Shorts per episode).
- Nerra Gallery (Phases 1-3): Grok-Imagine scenes stored in dedicated R2 bucket with sidecars + watermarked WebP thumbs; network-wide + per-show embeds; email-gated full-res downloads (Buttondown + magic-link JWT via Cloudflare Worker).
- Sunday weekly recap episodes for the 7 daily shows (synthesized from the content lake instead of fresh news fetch).
- Broadcast-quality audio pipeline (48 kHz WAV Grok TTS → single lossy encode, sidechain-ducked music, -16 LUFS EBU R128).

A full internal codebase review was performed in May 2026. Quick wins and strategic improvements (global site search, progressive enhancement for JS surfaces, gallery auth hardening, proactive alerting, pipeline modularization, dynamic metadata, live quota/cost visibility, onboarding automation, etc.) are tracked in the operator plan.

See:
- `CLAUDE.md` — Single source of truth for architecture, 20+ live landmines (enforced on the management dashboard), and current invariants.
- `management.html` (powered by `api/dashboard.json`) — Live status of costs, landmines, RSS health, YouTube success rates, etc.
- `docs/` — Detailed audits (gallery_storage.md, youtube_quota..., pipeline_audit..., etc.).

The network is intentionally kept as a set of static sites + GitHub Actions + serverless Worker so it remains simple, cheap, and reliable at 10+ episodes/week.
