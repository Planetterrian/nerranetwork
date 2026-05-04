# YouTube Publishing — Setup & Operator Runbook

The pipeline can publish each episode as a long-form 1920x1080 video and
a 1080x1920 Shorts teaser, automatically disclosed as AI-narrated and
monetization-eligible. This document covers the one-time setup work an
operator (you) does outside the repo: GCP project, OAuth, channels,
quota.

For day-to-day code locations see:

- `engine/video.py` — ffmpeg long-form + Shorts builders
- `engine/youtube.py` — Google API upload wrapper
- `engine/video_metadata.py` — title / description / tag construction
- `run_show.py` — `_publish_youtube()` stage runs after RSS, before X

## Channel topology

We use two channels:

| Channel | Audience | Shows | Refresh-token secret |
|---------|----------|-------|----------------------|
| English Nerra Network | Default | tesla, omni_view, fascinating_frontiers, planetterrian, env_intel, models_agents, models_agents_beginners, modern_investing | `YOUTUBE_REFRESH_TOKEN_EN` |
| Russian Nerra Network | Russian-speaking | finansy_prosto, privet_russian | `YOUTUBE_REFRESH_TOKEN_RU` |

Per-show YAMLs select the channel via `youtube.channel: en` or
`youtube.channel: ru`. The channel handle and display names are
configured in YouTube Studio — the code only needs the OAuth refresh
token belonging to that channel's account.

## One-time GCP + OAuth setup

1. **Create a Google Cloud project** at <https://console.cloud.google.com/>.
   Name it something like `nerra-network-youtube`.
2. **Enable the YouTube Data API v3** under `APIs & Services → Library`.
3. **Configure the OAuth consent screen** (`APIs & Services → OAuth consent screen`):
   - User type: External.
   - Add yourself as a test user (until the screen is verified, only test users can authorize).
   - Scopes: `youtube.upload`, `youtube`.
4. **Create OAuth credentials** (`APIs & Services → Credentials → Create Credentials → OAuth client ID`):
   - Application type: **Desktop app**.
   - Download the JSON file. Keep it local — never commit it.
5. **Mint refresh tokens** (one per channel) by running the bootstrap
   script locally:

   ```bash
   python scripts/youtube_oauth_bootstrap.py ~/Downloads/client_secrets.json
   ```

   The script opens a browser. Sign into the Google account that owns
   the **English channel** first, then re-run for the **Russian channel**.
   Each run prints the refresh token; paste it into the matching GitHub
   secret:

   - English run → `YOUTUBE_REFRESH_TOKEN_EN`
   - Russian run → `YOUTUBE_REFRESH_TOKEN_RU`

   The script also prints `YOUTUBE_CLIENT_ID` and `YOUTUBE_CLIENT_SECRET`
   — set those once (they're shared across both channels).

## GitHub secrets

The pipeline reads four secrets:

| Secret | Source |
|--------|--------|
| `YOUTUBE_CLIENT_ID` | OAuth client JSON |
| `YOUTUBE_CLIENT_SECRET` | OAuth client JSON |
| `YOUTUBE_REFRESH_TOKEN_EN` | Bootstrap script (English channel) |
| `YOUTUBE_REFRESH_TOKEN_RU` | Bootstrap script (Russian channel) |

If any are missing, the YouTube stage logs a "credentials missing" notice
and skips the upload — the rest of the pipeline (audio, RSS, X, etc.)
continues unaffected.

## Quota — the operational gotcha

The default Google Cloud quota is **10,000 units/day** per project.
Each `videos.insert` costs **1,600 units**, so the default lets you
upload roughly six videos per day. With 11 shows × (long-form + Shorts)
that's 32,000 units — over budget by a factor of three.

Two paths forward:

1. **Phased rollout** (default in this repo): only `tesla`,
   `fascinating_frontiers`, and `models_agents` have `youtube.enabled:
   true` to start. That's 3 × (1,600 + 1,600) = **9,600 units/day** —
   right under the cap.
2. **Quota extension request** (file on day 1): in Cloud Console →
   `APIs & Services → YouTube Data API v3 → Quotas`, request an increase
   to ~50,000 units/day. Justify with:
   - Original editorial pipeline (we're not aggregating other creators).
   - Compliance with `containsSyntheticMedia` disclosure on every upload.
   - 11 daily shows × 2 video formats × OAuth-authenticated uploads.

   Reviews typically take 1–2 weeks. Once granted, flip `youtube.enabled`
   to `true` on the remaining shows.

## AI disclosure

Every upload sets `status.containsSyntheticMedia=True` via the API. This
is the field YouTube introduced in October 2024 specifically for AI/A&S
disclosure; setting it via the API renders the same "Altered or
synthetic content" label the Studio UI applies and is required for
monetization-eligible AI audio uploads.

In addition, every video description ends with a plain-language
disclosure (defined in `shows/_defaults.yaml` under
`youtube.synthetic_disclosure`):

> AI Disclosure: This podcast is curated by Patrick but uses
> AI-generated voice synthesis (ElevenLabs) for the narration. …

Do not remove or weaken this. Both layers (API flag + description text)
are needed to stay inside YouTube's monetization policy.

## YouTube Analytics vs. Google Analytics

YouTube Studio has its own analytics dashboard and **does not** stream
data into GA4. What the pipeline does instead: every video description
links to `nerranetwork.com/<show>.html` with
`?utm_source=youtube&utm_medium=video&utm_campaign=ep<N>` so when a
viewer clicks through, GA4 on `nerranetwork.com` attributes the traffic
to YouTube. Shorts use `utm_medium=shorts` to separate the two
funnels.

If you want a periodic dump of YouTube Analytics into GA4, that's a
separate manual integration (third-party connector) — out of scope here.

## Validation steps for the first uploads

1. Set `youtube.privacy_status: unlisted` in `shows/tesla.yaml` (already
   the default for phase-1 shows in this repo).
2. Run locally:

   ```bash
   python run_show.py tesla --skip-x --skip-newsletter
   ```

3. In YouTube Studio, open the new video and confirm:
   - Title, description, chapters, tags rendered correctly.
   - Custom thumbnail rendered (1280x720, hook visible).
   - Under `Details → Altered content`: "Altered or synthetic content"
     label is visible.
   - Privacy is "Unlisted".
4. Flip `youtube.privacy_status: public` in the YAML, re-run.
5. Once two or three episodes have landed cleanly, repeat for the Shorts.
