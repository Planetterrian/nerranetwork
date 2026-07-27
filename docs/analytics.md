# Nerra Network Analytics — the One-Place Contract

Every audience number the network collects lands as JSON under `api/`,
refreshed by the **Nightly Maintenance** workflow
(`.github/workflows/nightly-maintenance.yml`, ~16:45 UTC daily), and is
rolled up into **`api/dashboard.json` → `audience`** by
`scripts/generate_dashboard.py`. That file is the single source of
truth: humans read the dashboard page, and any AI tool working on this
repo (Claude, Cursor, Grok, …) should read `api/dashboard.json` first
and drill into the per-source files below only when it needs raw detail.

Every fetcher follows the same convention: **missing secret → clean
no-op** (one log line, exit 0, previously committed JSON left
untouched). A stale `fetched_at` therefore means the source is
degraded, not deleted — check the secret before assuming data loss.

## Source files

| File | Source | What it holds | Fetcher | Secret(s) |
|------|--------|---------------|---------|-----------|
| `api/op3_stats.json` | [OP3](https://op3.dev) (official API) | RSS **downloads** per show + episode, 7d/30d. Covers Apple Podcasts, Overcast, Pocket Casts and every RSS app — anything that pulls the OP3-prefixed enclosure URLs. **Does NOT see Spotify** (Spotify re-hosts audio). | `scripts/fetch_op3_stats.py` | `OP3_API_TOKEN` |
| `api/youtube_stats.json` | YouTube Analytics API (official) | Per-channel subscribers/views + per-video performance across en/ru/fr channels; feeds the adaptive policy. | `scripts/fetch_youtube_analytics.py` | `YOUTUBE_*` OAuth set |
| `api/youtube_channel_history.json` | derived | Daily subscriber snapshots (7-day deltas). | same | same |
| `api/ga4_stats.json` | GA4 Data API (official) | nerranetwork.com site traffic, 28d: totals, day series, top pages, channels, countries. Property `533581233`. | `scripts/fetch_ga4_stats.py` | `GA4_SERVICE_ACCOUNT_JSON` (+ optional `GA4_PROPERTY_ID`) |
| `api/spotify_stats.json` | Spotify for Podcasters (**unofficial**, cookie-auth) | Per-show followers / streams / listeners + demographics, 30d. Fills the OP3 blind spot. | `scripts/fetch_spotify_stats.py` | `SPOTIFY_SP_DC`, `SPOTIFY_SP_KEY` |
| `api/apple_stats.json` | Apple Podcasts Connect (**unofficial**, cookie-auth) | Apple **engagement**: plays, listeners, followers, time-listened per show, 30d. Apple *downloads* are already in OP3 — this adds the follow/finish signal nothing else measures. Needs `apple_show_id:` in each `shows/<slug>.yaml` (numeric ID from the Podcasts Connect URL). | `scripts/fetch_apple_stats.py` | `APPLE_MYACINFO`, `APPLE_ITCTX` |
| `api/buttondown_stats.json` | Buttondown API (official) | Newsletter subscriber count. | `scripts/fetch_buttondown_stats.py` | `BUTTONDOWN_API_KEY` |
| `api/op3_history.json` | derived (accumulated) | Weekly download ledger keyed by ISO-week Monday. OP3 has no all-time endpoint, so each dashboard build overwrites the current 4 rolling weeks and freezes older ones; "all-time" = sum of stored weeks ("since tracking began", 2026-06-29). Must stay in nightly's safe-commit-push add-paths (youtube_channel_history landmine class). | `scripts/generate_dashboard.py` | — |
| `api/youtube_policy.json` | derived (nightly) | Adaptive publishing tier per show × channel (A/B/C/D) + the views-per-day velocity behind it; decides long-form on/off and Shorts count. Surfaced in the dashboard's Distribution section. | `scripts/update_youtube_policy.py` | — |
| `docs/podcast_directories.md` | operator-maintained | Directory coverage (Apple, Spotify, Amazon, Podcast Index, Pocket Casts, iHeart, YouTube Music). Apple/Amazon/etc. have **no analytics API**, so this hand-kept status table is the only record of where feeds are actually distributed; the dashboard parses its "Submission Status Tracker" into per-platform coverage + operator follow-ups. | manual (submission passes) | — |
| `api/dashboard.json` | rollup of all of the above | `audience` section: `op3` (incl. `network_downloads_all_time` + `network_weekly_history`), `youtube`, `site` (GA4), `spotify`, `newsletter` — each with `configured: bool` and compact summaries. Plus `catalog` (shows count, episodes to date, news sources / topic-queue runway, capability flags per show), `gallery` (image-library counts + retention-loop status), `content_lake` (lake vitals + `healthy` flag), `distribution` (per-platform directory coverage parsed from the tracker doc), and `youtube_policy` (adaptive publish tiers). **Non-finite floats are nulled on write** — bare `NaN` is invalid JSON and blanks the whole page in the browser. | `scripts/generate_dashboard.py` | — |

Public, display-safe extracts live in `site/data/` (e.g.
`popular_episodes.json`); `api/` is robots-disallowed.

## Reading guide for AI tools

1. Start at `api/dashboard.json` → `audience`. Each sub-key carries
   `configured` and `fetched_at` — treat anything older than ~48h as
   stale and say so rather than presenting it as current.
2. Downloads ≠ listens ≠ views. OP3 counts RSS downloads; Spotify
   counts streams/listeners on its own platform; YouTube counts views.
   Never sum across them — report them side by side.
3. Coverage map: **OP3** = all RSS apps incl. Apple Podcasts;
   **Spotify** = Spotify only; **YouTube** = the three channels
   (@NerraNetwork, @NerraRU, @NerraFR); **GA4** = website;
   **Buttondown** = newsletter.
4. Per-show keys are the `shows/<slug>.yaml` slugs. YouTube per-show
   data keys by digest dir (e.g. `tesla_shorts_time`) — the mapping is
   `episode.output_dir` in each show YAML.

## Known caveats

* **Spotify cookies expire** every few months. Symptom: the nightly log
  prints "cookies have likely EXPIRED" and `api/spotify_stats.json`
  goes stale. Fix: log in at podcasters.spotify.com, copy the `sp_dc`
  and `sp_key` cookies (browser dev tools → Application → Cookies),
  update the two repo secrets. ~5 minutes.
* **Apple Podcasts — correction, 25 July 2026.** This file previously
  said Apple has "no official analytics API". That is wrong, and the
  claim also sat in `requirements.txt`. Apple ships **Reporter**, a
  command-line tool that returns `apShowListening`,
  `apEpisodeListening`, `apChannelListening` and `apProviderListening`
  reports (Daily / Weekly / Monthly) against an access token valid for
  **180 days** — no cookies, no browser session. That is exactly the
  durable, scriptable source the cookie scraper below is a workaround
  for. Two gates stand between us and it: our Apple Podcasters Program
  agreement reads **"Pending User Info"** (missing a bank account and
  the Canadian GST/HST form — see Podcasts Connect → Business), and
  Apple documents these reports as requiring at least one active
  subscription, of which we have zero. Provider number is `93825591`.
  Settle it empirically before designing around it:

  ```
  java -jar Reporter.jar p=Reporter.properties Sales.getVendors
  java -jar Reporter.jar p=Reporter.properties \
      Sales.getReport 93825591, apShowListening, Summary, Daily, YYYYMMDD
  ```

  If those return data, Reporter becomes the primary Apple source and
  the cookie path below drops to fallback.
* Apple *download* traffic is covered by OP3; the Apple-only
  engagement metrics (followers, plays, time listened) are now fetched
  via the community
  [apple-connector](https://github.com/openpodcast/apple-connector) into
  `api/apple_stats.json`, authenticated with `myacinfo`/`itctx` session
  cookies — the same unofficial trade-off already accepted for Spotify.
  **Both cookie integrations expire** and degrade to stale data (never a
  red nightly); the fetcher logs a loud re-auth hint when every show
  fails. Turning it on takes two secrets plus an `apple_show_id:` per
  show YAML.
* **OP3 history** starts the day the prefix went live — no backfill of
  earlier listens.
* **A show only appears in OP3 once OP3 knows the feed.** The lookup is
  `GET /shows/<base64 feed URL>`, and per OP3's docs a 404 means "OP3
  doesn't know about the show" — not that there were no downloads. New
  feeds therefore 404 for a while after launch (`op3: <slug> fetch
  failed: 404` in the nightly log) while their prefixed downloads are
  still being recorded; they attach retroactively once OP3 indexes the
  feed. Observed 2026-07-25 for `dp_pod` and `age_of_ai`, both of which
  had only gone LIVE on Apple two days earlier. **A 404 that persists
  for weeks is different** — check the feed's enclosures actually carry
  the `https://op3.dev/e/` prefix before assuming it's an indexing lag.
* **The prefix is applied by each publish path, not by
  `update_rss_feed`.** `run_show.py`, `engine/pipeline.py`,
  `engine/language_feeds.py` and `pipelines/voices/publish_episode.py`
  each call `apply_op3_prefix` themselves. Age of AI publishes outside
  run_show and was missing that call, so its Ep001 enclosure is
  unprefixed and its downloads were never counted (fixed 2026-07-25 for
  new episodes; the published Ep001 URL is deliberately left alone —
  rewriting a live enclosure re-downloads the episode for every
  subscriber). Any future show that bypasses `run_show` must apply the
  prefix in its own publish step.
* **Both cookie connectors are runtime-bounded.** `spotifyconnector`
  and `appleconnector` retry a failing endpoint 6 times with unbounded
  exponential backoff (~124s per endpoint). A registered feed with no
  plays yet returns `500` on `/metadata` and `/aggregate` *every* night,
  so this is a stable cost, not a transient one: with 18 of 24 Spotify
  feeds in that state the nightly fetch step ran for over an hour
  (measured 2026-07-25) before the rest of maintenance could start.
  `engine/connector_budget.py` clamps the retry constants (3 attempts,
  1s base ≈ 6s per dead endpoint) and enforces a wall-clock budget
  (`SPOTIFY_FETCH_BUDGET_SECONDS` / `APPLE_FETCH_BUDGET_SECONDS`,
  default 900s); shows not reached before the budget expires keep their
  previous entry, tagged `not_refreshed_this_run`, so the file never
  silently shrinks. Watch for the `::warning::…budget…expired`
  annotation — it means the platform got slower, not that a feed died.
* **YouTube quota** is shared between publishing and analytics;
  `scripts/backfill_dub_playlists.py` (manual workflow) also spends it —
  50 units per playlist insert.
* GA4 numbers are consent-gated (Consent Mode v2) — they undercount
  visitors who decline analytics cookies.

## Directory / distribution status

Where each show is submitted (Apple, Spotify, Amazon, …) is tracked in
`docs/podcast_directories.md`. Spotify show IDs, once assigned, are
recorded as `spotify_show_id:` in each `shows/<slug>.yaml` — that key
is what turns on the Spotify fetcher for a show.
