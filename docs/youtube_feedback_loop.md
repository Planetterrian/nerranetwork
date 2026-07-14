# YouTube → workflow recursive feedback loop (June 2026)

**Goal:** stop improving YouTube packaging by hand. Read each video's
*performance* (especially retention) back into the pipeline and let it steer
future titles automatically — the same closed loop the audio side already has
via OP3 download stats.

This mirrors the proven OP3 pattern
(`fetch_op3_stats.py` → `update_performance_trackers.py` →
`engine/show_memory.py` → prompt injection), built to ship **dormant**: every
piece is a clean no-op until (a) the operator re-authorises the OAuth token
with the analytics scope and (b) a few weeks of data accrue. You collect
first, then the loop turns itself on.

## Data flow

```
publish (run_show.py _publish_youtube)
   └─ engine/youtube_index.record_video
        → digests/<slug>/youtube_videos.json   (per-show video→episode map)

nightly-maintenance.yml
   ├─ scripts/fetch_youtube_analytics.py
   │     reads every digests/<slug>/youtube_videos.json,
   │     queries YouTube Analytics API (views / watch-time / avg view %),
   │     → api/youtube_stats.json
   └─ scripts/update_youtube_performance.py
         distils per-show "what's working" from the best-retention videos
         → digests/<slug>/youtube_performance.json  ({ "title_hint": "..." })

next episode (run_show.py → engine/youtube_titles.generate_youtube_titles)
   └─ _performance_hint(slug) injects the hint into the title prompt
        → titles lean toward the angles/keywords that retained best
```

### Why per-show index files (not one shared file)

Up to a dozen show jobs run concurrently in the daily matrix. A single shared
`api/youtube_videos.json` would have every job racing to commit/push the same
file — exactly the cross-show push-contention fixed in June 2026 (the
`blog.rss` / `network.rss` exclusion; landmine #23). Each show writes only its
own `digests/<slug>/youtube_videos.json`, written by that show's serialised
job alone.

### Why retention, not CTR

`averageViewPercentage` is the strongest content-quality signal the **public**
YouTube Analytics API exposes. Impressions and click-through rate are
Studio-only (no reliable public-API metric), so they are intentionally
omitted. Retention is also the better lever: the 2026 algorithm gates "Quality
CTR" on whether the title's promise is actually kept.

### Why this is safe to run automatically (no landmine #17 gate)

The only thing the loop changes is the **YouTube title** — visual metadata,
generated separately from the spoken hook (`engine/youtube_titles.py`). It
never touches the audio script or TTS, so it sits outside the A/B-listen gate.
If the hint is empty (no data yet) the title prompt renders exactly as before.

## Operator one-time setup

Two GCP/OAuth steps — both required. Nightly logs on 2026-07-09 showed the
**API was disabled** on the project (not only a missing OAuth scope), so do
them in this order:

1. **Enable YouTube Analytics API v2** in the same Google Cloud project that
   owns `YOUTUBE_CLIENT_ID` (project number was `141610975484` in the July
   2026 403). Console → **APIs & Services → Library → "YouTube Analytics
   API"** → Enable. Wait 1–5 minutes for propagation. Uploads use Data API
   v3 (already enabled); analytics is a separate product.

2. **Re-authorise the OAuth token** with the analytics scope. The June 2026
   change added `https://www.googleapis.com/auth/yt-analytics.readonly` to
   `engine.youtube.YOUTUBE_SCOPES`. Google will not expand scopes on an
   existing refresh token, so:

   ```bash
   # Revoke the old grant first so Google re-shows consent:
   # https://myaccount.google.com/permissions  → remove the Nerra / GCP app

   python scripts/youtube_oauth_bootstrap.py ~/Downloads/client_secrets.json
   # Sign in as @NerraNetwork → paste token into YOUTUBE_REFRESH_TOKEN_EN

   python scripts/youtube_oauth_bootstrap.py ~/Downloads/client_secrets.json
   # Sign in as @NerraRU → paste token into YOUTUBE_REFRESH_TOKEN_RU
   ```

   **Until both steps are done, uploads keep working; only the analytics
   read no-ops.**

3. That's it. The nightly job already passes the YouTube secrets to the fetch
   step; `api/youtube_stats.json` and the per-show `youtube_performance.json`
   files start populating once the API + scope are live and videos have a few
   weeks of watch data. The title hint switches on the moment a show has ≥4
   videos with retention numbers.

## Verifying

```
# After re-auth, dry-run the fetch (prints what it would write):
python scripts/fetch_youtube_analytics.py --dry-run --days 90

# Then build the hints and inspect one:
python scripts/update_youtube_performance.py
cat digests/tesla/youtube_performance.json
```

Drift guards: `tests/test_youtube_feedback_loop.py`.

## Adaptive publishing policy (July 2026)

The second consumer of `api/youtube_stats.json`: instead of only steering
*titles*, the network now adapts its publish **volume/format** to what each
channel's audience actually watches (operator-approved: ~24 EN uploads/day
were earning ~182 views/day — most long-forms cost render time + Grok Imagine
spend for single-digit views).

- **`scripts/update_youtube_policy.py`** (nightly, right after the title-hint
  step; no secrets — reads the committed stats) writes
  **`api/youtube_policy.json`**: per show × channel, a publish tier computed
  from a single-snapshot **velocity** metric, `vpd = views /
  max(1, days_since_publish)`, averaged per kind over videos published in the
  trailing 14 days (≥4 videos of a kind required for a confident reading;
  fewer = that dimension holds the active tier).
- **Tier rules** (same rules on both channels, each decided from its own
  data): long-form on when `long_vpd ≥ 1.0`; Shorts `≥ 4.0` → 2/episode else
  1 — **never 0** (Shorts are the probe/recovery signal). Labels: A =
  long + 2 Shorts, B = long + 1, C = shorts-only, D = probe (shorts-only and
  `short_vpd < 0.5`; same settings as C).
- **Monday long-form probe**: a shorts-only show produces no long-form
  analytics, so it could never re-earn its long-form (a one-way door).
  `resolve_publish_plan` grants one probe long-form per week (Mondays,
  UTC) to shows whose YAML wants long-form but whose tier gates it off —
  that probe generates the data the nightly computation needs to promote.
- **Hysteresis**: the ACTIVE tier flips only after the same computed tier
  appears on 2 consecutive runs (`{active, computed, pending, streak}`
  persisted in the policy file). Cold-start actives are the `SEED_TIERS`
  hardcoded from the live 2026-07-14 analytics (RU long-form off everywhere:
  59 views across 11 RU spacex longs vs 2,513 on RU Shorts).
- **Consumers** (both via `engine.youtube_policy.resolve_publish_plan`):
  `run_show._publish_youtube` (EN + native-RU shows — skips the long-form
  render/upload on a shorts-only tier while Shorts, and the long-form
  thumbnail the Shorts end-card reuses, still ship; raises Shorts to 2 only
  when `shorts_start_mode: smart`; metrics `yt_policy_tier` /
  `yt_policy_long_skipped` / `yt_policy_shorts`), and
  `engine.ru_dub.publish_ru_dub` (@NerraRU dubs — shorts-only tier skips the
  long render+upload; the RU Short still builds from the shared audio +
  scenes + thumbnail, and its upload marks the episode done in the sweep's
  index).
- **Contract**: best-effort everywhere — a missing/unreadable policy file, an
  absent slug, or `youtube.adaptive_publishing: false` (new `YouTubeConfig`
  field, default true) resolves to exact legacy YAML behavior. The policy
  never edits YAML files and never touches audio (outside landmine #17).

Drift guards: `tests/test_youtube_policy.py`.

## Deliberately staged for later

- **Topic steering from retention** (feeding the signal into the *digest*
  prompt so the show covers more of what retains) is a bigger lever but
  changes generated **audio** → it must go through the landmine #17 A/B-listen
  gate. Left out of v1 on purpose; revisit once a few weeks of retention data
  show a clear, trustworthy signal.
- **Dashboard surfacing** of `api/youtube_stats.json` (an "Audience: YouTube"
  card next to the OP3 card) is a straightforward follow-up once real data
  exists to display.
