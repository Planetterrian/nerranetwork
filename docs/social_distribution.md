# Multi-platform Shorts distribution (Instagram Reels / TikTok)

The Shorts pipeline can cross-post each Short to Instagram Reels and TikTok (and
leave a ready-to-post bundle for anywhere else). This is **opt-in per show** and
a **clean no-op until you finish the one-time account/app setup** below — so the
code can ship and sit dormant safely.

## What the pipeline produces

When `youtube.multi_platform_enabled: true` for a show, every Short it publishes
to YouTube *also* gets:

1. **A safe-zone variant MP4** (`<episode>_short[_N]_social.mp4`). It's the same
   clip but with overlays moved out of the bands Instagram Reels & TikTok cover
   with their own UI: the bottom URL pill and the end-card are dropped, and the
   burned-in captions are lifted (`MarginV` 340 → `social_caption_margin_v`,
   default 480). The top brand pill and centred hook stay. YouTube uploads still
   use the original (unchanged) Short — this variant is for the vertical-social
   platforms whose UI is more aggressive.
2. **A `.social.json` sidecar** with ready-to-post copy per platform:
   ```json
   {
     "youtube":        {"title": "...", "description": "...", "tags": [...]},
     "instagram_reels":{"caption": "<hook> … #Tag #Reels #podcast", "hashtags": [...]},
     "tiktok":         {"caption": "<hook> #Tag #podcast #fyp",       "hashtags": [...]}
   }
   ```
   Captions lead with the episode hook and reuse the same entity-derived hashtags
   as the YouTube Short (`engine/shorts_hashtags.py`).
3. **(Optional) R2 hosting** — if `youtube.social_r2_prefix` is set and the
   gallery R2 env is configured, the variant is uploaded so it has a stable
   public URL (required for Instagram's URL-based API, and handy for grabbing the
   asset to post manually).
4. **Auto-posting** to the platforms you've enabled + credentialed (below).

Even with **no** credentials, you still get the variant MP4 + sidecar, so you can
post manually with one paste.

## Enabling it (per show YAML)

```yaml
youtube:
  enabled: true            # YouTube must be on (Shorts are produced there)
  multi_platform_enabled: true
  instagram_enabled: true  # attempt IG auto-post (needs creds below)
  tiktok_enabled: true     # attempt TikTok auto-post (needs creds below)
  social_r2_prefix: "social/tesla"   # host variants here (needed for IG)
  # optional tuning:
  # social_caption_margin_v: 480   # px from bottom for captions on the variant
  # social_drop_url_pill: true
  # social_drop_end_card: true
```

Default is everything off → YouTube-only, byte-for-byte unchanged.

## One-time credential / app setup (operator)

These require **your** accounts and developer apps; they can't be scripted blind.

### Instagram Reels (Graph API)
- Convert the IG account to **Business/Creator** and link it to a **Facebook Page**.
- Create a **Meta app**, add **Instagram Graph API**, request the
  `instagram_content_publish` + `instagram_basic` permissions (App Review).
- Generate a long-lived **IG access token** and find the **IG user id**.
- Set env / GitHub secrets: `IG_ACCESS_TOKEN`, `IG_USER_ID`.
- IG is **URL-based**: the Short must be at a public URL → set `social_r2_prefix`
  and the gallery R2 env (`R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`,
  `R2_SECRET_ACCESS_KEY`, `R2_GALLERY_BUCKET`, `R2_GALLERY_PUBLIC_BASE_URL`).

### TikTok (Content Posting API)
- Register a **TikTok developer app**, request the **`video.publish`** scope
  (requires app review/audit).
- Complete user OAuth and store a user **access token**: `TIKTOK_ACCESS_TOKEN`.
- Until the app passes audit, posts are created as `SELF_ONLY` (the publisher
  sets this deliberately); flip to public in `engine/social_publisher.py`
  (`privacy_level`) once approved.

## Where it lives

- `engine/social_metadata.py` — pure per-platform caption/hashtag builder.
- `engine/social_publisher.py` — credential-gated IG/TikTok API calls (no-op
  without creds; never raises).
- `engine/social_distribution.py` — orchestrator (variant + sidecar + R2 + post),
  called once per Short from `run_show.py`'s YouTube publish stage.
- `engine/video.py` — `build_short_video(..., drop_url_pill=, caption_margin_v=)`
  renders the safe-zone variant.

## Status / limitations

- The IG/TikTok API flows are implemented against the documented endpoints but
  have **not** been run against live apps here — verify on the first real post.
- Posting is best-effort and non-fatal: a failure never blocks the episode.
- Other platforms (YouTube Shorts already covered; Facebook Reels, etc.) can
  reuse the same safe-zone MP4 + sidecar.
