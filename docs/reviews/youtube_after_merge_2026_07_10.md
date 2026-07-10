# YouTube after-merge follow-up (July 10, 2026)

Status of the three operator items from
[`youtube_visual_pass_2026_07_09.md`](youtube_visual_pass_2026_07_09.md)
after PR #793 merged.

## 1. Gallery rebuild — DONE

- Post-merge `Build Gallery Manifest` run succeeded
  ([run 29027676783](https://github.com/Planetterrian/nerranetwork/actions/runs/29027676783)).
- Nightly 2026-07-09 rebuilt from **2506** R2 sidecars → public manifest
  **2312** images (`segment_card` 1158 + `social` 1154).
- **0** `thumbnail_variant` / text-burned composites in
  `site/data/gallery-manifest.json`.
- Live gallery: https://nerranetwork.com/gallery.html

No further action.

## 2. Spot-check next publishes — PARTIAL (looks good)

Episodes that ran **after** the merge (e.g. Env Intel Ep055, 2026-07-09
~18:21 UTC) already used the image-first compositor. Local variant thumbs
for Ep055 show a bright top band (mean ~144) vs the older full-darken look
(Ep054 top ~58). Bottom band stays darker (scrim) as designed.

Worth a quick human look in YouTube Studio on the next Tesla + one Shorts
upload (titles/descriptions/hashtag fold), but no code blocker.

## 3. YouTube Analytics / performance loop — NEEDS YOUR LOCAL STEPS

Nightly already calls `fetch_youtube_analytics.py` with all four YouTube
secrets set. On 2026-07-09 it failed with:

> YouTube Analytics API has not been used in project **141610975484**
> before or it is disabled.

So the blocker is **API enablement first**, then (if still 403) OAuth
re-consent. The fetch script previously labelled every 403 as “re-auth
needed”; that message is now split so the next nightly log is actionable.

### Do this on your machine (browser required)

**A. Enable the API (~1 minute)**

1. Open Google Cloud Console for the project that owns
   `YOUTUBE_CLIENT_ID` (number `141610975484` from the log).
2. **APIs & Services → Library → YouTube Analytics API → Enable**.
3. Confirm **YouTube Data API v3** is still Enabled (uploads).

**B. Re-mint refresh tokens with analytics scope (~5 minutes)**

```bash
# 1. Revoke the old grant so Google re-shows consent:
#    https://myaccount.google.com/permissions

# 2. From a local clone with google-auth-oauthlib installed:
python scripts/youtube_oauth_bootstrap.py ~/Downloads/client_secrets.json
# Sign in as the @NerraNetwork Google account → copy refresh token
# → GitHub → Settings → Secrets → YOUTUBE_REFRESH_TOKEN_EN

python scripts/youtube_oauth_bootstrap.py ~/Downloads/client_secrets.json
# Sign in as @NerraRU → YOUTUBE_REFRESH_TOKEN_RU
```

**C. Verify (optional, same night or next morning)**

```bash
# After secrets are updated, either wait for Nightly Maintenance or:
gh workflow run nightly-maintenance.yml

# Or locally with secrets in .env:
python scripts/fetch_youtube_analytics.py --dry-run --days 90
python scripts/update_youtube_performance.py
cat digests/tesla_shorts_time/youtube_performance.json
```

Title hints turn on once a show has ≥4 videos with retention numbers
(usually a few weeks of watch data after the API starts returning rows).

This cloud agent **cannot** complete A/B: no browser OAuth, no write access
to GitHub Actions secrets, no GCP console.

## Code shipped in this follow-up

- Clearer 403 classification in `scripts/fetch_youtube_analytics.py`
- Docs: `docs/youtube_feedback_loop.md`, `docs/youtube_setup.md` list
  Analytics API enablement before re-auth
