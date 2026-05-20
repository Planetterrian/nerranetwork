# Environment Variable Inventory

> Updated **2026-05-20** for the unified `run-show.yml` pipeline (11 shows via `run_show.py`).

---

## Production workflow (`.github/workflows/run-show.yml`)

Secrets written to `.env` in the matrix job:

| Secret | Purpose |
|--------|---------|
| `GROK_API_KEY` | xAI / Grok LLM, TTS, web search, X-search |
| `ELEVENLABS_API_KEY` | Emergency rollback only (no show uses ElevenLabs in production) |
| `X_*` | @teslashortstime account (TST, OV, FF, M&A, MIT, etc.) |
| `PLANETTERRIAN_X_*` | @planetterrian account (Planetterrian, UC) |
| `BUTTONDOWN_API_KEY` | Daily + weekly newsletters |

Passed as step `env:` to the pipeline step (not in `.env` file):

| Secret | Purpose |
|--------|---------|
| `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | Cloudflare R2 audio upload |
| `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` | YouTube uploads (TST + MAB) |
| `PEXELS_API_KEY` | Slideshow imagery |
| `NOTIFICATION_WEBHOOK_URL` | Optional failure webhook |

HTML generation / finalize also use: `GA4_MEASUREMENT_ID`, `GOOGLE_ADS_*`, `PLAUSIBLE_DOMAIN`, `GSC_VERIFICATION`.

---

## Required for a full episode (typical English show)

| Variable | Required when |
|----------|----------------|
| `GROK_API_KEY` or `XAI_API_KEY` | Always (digest, TTS, tools) |
| `R2_*` | `storage.provider: r2` in show YAML (network default) |
| `BUTTONDOWN_API_KEY` | `newsletter.enabled: true` (default on all 11 shows) |
| `X_*` or `PLANETTERRIAN_X_*` | `publishing.x_enabled: true` |
| `YOUTUBE_*` | `youtube.enabled: true` (TST, MAB only) |
| `PEXELS_API_KEY` | YouTube enabled + Pexels/hybrid imagery |

`ELEVENLABS_API_KEY` is only required if a show sets `tts.provider: elevenlabs` (none today).

---

## Local development

Copy `.env.example` if present, or set at minimum:

```bash
GROK_API_KEY=...
# Optional for full publish dry-run:
R2_ENDPOINT_URL=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
```

Run:

```bash
python run_show.py tesla --test          # digest only
python run_show.py tesla --resume-publish  # publish-only retry (skips YouTube)
python run_show.py tesla --resume-youtube   # YouTube-only retry
```

---

## Removed / deprecated

| Variable | Notes |
|----------|-------|
| `NEWSAPI_KEY` | Removed; guarded by `test_no_newsapi_in_active_workflow` |
| Legacy per-show workflows | Replaced by `run-show.yml` |
| `GROK_MODEL` per-show overrides | Network default `grok-4.3` in `shows/_defaults.yaml` |

---

## Feature flags (CLI, not env)

| Flag | Effect |
|------|--------|
| `--test` | Fetch + digest only |
| `--dry-run` | Config validation only |
| `--skip-x` | No X post |
| `--skip-podcast` | No TTS / RSS audio |
| `--skip-newsletter` | No Buttondown send |
| `--skip-youtube` | No YouTube upload |
| `--resume-publish` | Publish from existing MP3 + digest (skips fetch/TTS/YouTube) |
| `--resume-youtube` | Rebuild/upload YouTube only (skips fetch/TTS/X/newsletter) |

Auto `--resume-publish` when today's MP3 exists but `.published_YYYYMMDD.json` is missing.
Use `--resume-youtube` when the rest of the pipeline succeeded but YouTube failed.
