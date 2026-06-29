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

1. **Re-authorise the OAuth token** with the analytics scope. The June 2026
   change added `https://www.googleapis.com/auth/yt-analytics.readonly` to
   `engine.youtube.YOUTUBE_SCOPES`. Google rejects a stored refresh token that
   lacks a requested scope, so re-run:

   ```
   python scripts/youtube_oauth_bootstrap.py        # @NerraNetwork (EN)
   ```

   and re-consent, then update the `YOUTUBE_REFRESH_TOKEN_EN` secret (and
   `YOUTUBE_REFRESH_TOKEN_RU` for @NerraRU if RU shows are publishing). **Until
   this is done, uploads keep working on the old token; only the analytics
   read no-ops** (it logs "Analytics query rejected … re-auth needed").

2. That's it. The nightly job already passes the YouTube secrets to the fetch
   step; `api/youtube_stats.json` and the per-show `youtube_performance.json`
   files start populating once the scope is live and videos have a few weeks of
   watch data. The title hint switches on the moment a show has ≥4 videos with
   retention numbers.

## Verifying

```
# After re-auth, dry-run the fetch (prints what it would write):
python scripts/fetch_youtube_analytics.py --dry-run --days 90

# Then build the hints and inspect one:
python scripts/update_youtube_performance.py
cat digests/tesla/youtube_performance.json
```

Drift guards: `tests/test_youtube_feedback_loop.py`.

## Deliberately staged for later

- **Topic steering from retention** (feeding the signal into the *digest*
  prompt so the show covers more of what retains) is a bigger lever but
  changes generated **audio** → it must go through the landmine #17 A/B-listen
  gate. Left out of v1 on purpose; revisit once a few weeks of retention data
  show a clear, trustworthy signal.
- **Dashboard surfacing** of `api/youtube_stats.json` (an "Audience: YouTube"
  card next to the OP3 card) is a straightforward follow-up once real data
  exists to display.
