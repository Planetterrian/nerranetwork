# YouTube Publishing — Setup & Operator Runbook

The pipeline publishes each enabled episode as a long-form 1920×1080 video and
a 1080×1920 Shorts teaser, with AI disclosure on every upload. Code paths:

- `engine/video.py` — ffmpeg long-form + Shorts builders
- `engine/youtube.py` — Google API upload wrapper
- `engine/video_metadata.py` — title / description / tags
- `engine/youtube_shorts.py` — Shorts start offset + quota stagger
- `run_show.py` — `_publish_youtube()` at step **10d** (before RSS, so the watch URL can land in show notes)

## Production rollout (May 2026)

| Show | `youtube.enabled` | Notes |
|------|-------------------|--------|
| `tesla` | `true` | Grok Imagine imagery |
| `models_agents_beginners` | `true` | Pexels imagery (A/B month vs Tesla) |
| All others | `false` | Ready to flip after quota increase |

CI guard: `tests/test_schedule.py::test_only_tst_and_mab_enable_youtube`.

## Channel topology

| Channel | Shows | Refresh-token secret |
|---------|-------|----------------------|
| English `@NerraNetwork` | English shows | `YOUTUBE_REFRESH_TOKEN_EN` |
| Russian `@NerraRU` | `finansy_prosto`, `privet_russian` | `YOUTUBE_REFRESH_TOKEN_RU` |

Per-show YAML: `youtube.channel: en` or `ru`.

## One-time GCP + OAuth setup

1. Create a Google Cloud project and enable **YouTube Data API v3**.
2. OAuth consent screen: External, add yourself as test user until verified.
3. Create **Desktop** OAuth credentials; download JSON (never commit).
4. Mint refresh tokens locally:

   ```bash
   python scripts/youtube_oauth_bootstrap.py ~/Downloads/client_secrets.json
   ```

   Run once per channel (English account, then Russian). The bootstrap script
   requests `youtube.upload`, `youtube`, and **`youtube.force-ssl`** (required
   for `captions.insert` / CC track upload).

5. Paste tokens into GitHub secrets:

   | Secret | Source |
   |--------|--------|
   | `YOUTUBE_CLIENT_ID` | OAuth client JSON |
   | `YOUTUBE_CLIENT_SECRET` | OAuth client JSON |
   | `YOUTUBE_REFRESH_TOKEN_EN` | English channel run |
   | `YOUTUBE_REFRESH_TOKEN_RU` | Russian channel run |

If captions fail with HTTP 403 after upgrading scopes, **revoke** the app at
https://myaccount.google.com/permissions and re-run the bootstrap script so
Google issues a new refresh token with `force-ssl`.

## Quota

Default project quota: **10,000 units/day**.

| API call | Units |
|----------|------:|
| `videos.insert` | 1,600 |
| `thumbnails.set` | 50 |
| `playlistItems.insert` | 50 |
| `captions.insert` | 400 |

Roughly **~3,400–3,800 units per show per day** (long + Short + thumb + playlist + captions).

- **2 enabled shows (today):** ~7k units — fits default quota.
- **7 daily shows × 2 videos:** ~22k+ units on inserts alone — **request quota increase** (~50k/day) or set `youtube.shorts_upload_schedule: alternate_episodes` on some shows (Shorts only on even episode numbers).

`engine/youtube_quota.py` logs a warning at preflight when enabled shows exceed 10k.

## YouTube Podcasts playlist (manual, once per playlist)

The API adds videos to `youtube.podcast_playlist_id`, but the playlist only
appears under **YouTube Studio → Podcasts** after you choose **Set existing
playlist as a podcast** for that playlist. One-time per playlist per channel.

## AI disclosure

Every upload sets `status.containsSyntheticMedia=True` plus the
`youtube.synthetic_disclosure` footer in `_defaults.yaml` (Grok TTS wording).

## Shorts timing

Shorts audio starts at `audio.voice_intro_delay` (not `intro_duration + delay`).
Override per show:

- `youtube.shorts_start_offset: 90` — fixed seconds
- `youtube.shorts_start_mode: first_chapter` — jump to 2nd chapter marker

## Retry / resume

- **Failed upload after MP3 exists:** `python run_show.py <slug> --resume-youtube`
  (rebuilds ffmpeg assets and re-uploads; skips TTS/X/newsletter).
- **Failed RSS but MP3 ok:** `python run_show.py <slug> --resume-publish`

## Validation checklist (first uploads)

1. Run: `python run_show.py tesla --skip-x --skip-newsletter`
2. In Studio: title, description, chapters, thumbnail, synthetic label.
3. Confirm CC track on long-form (if OAuth includes `force-ssl`).
4. Confirm Shorts uses vertical thumbnail and starts on voice (not mid-sentence skip).

## Analytics

Descriptions include UTM links (`utm_source=youtube`, `utm_medium=video` or `shorts`).
YouTube Analytics does not feed GA4; use site UTMs for cross-funnel attribution.
