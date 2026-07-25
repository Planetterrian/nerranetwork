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
* **Apple Podcasts** has no official analytics API. Apple *download*
  traffic is already covered by OP3; Apple-only engagement metrics
  (followers, time listened) live in
  [Podcasts Connect](https://podcastsconnect.apple.com/) and are not
  fetched. If that changes (or the cookie-based
  [apple-connector](https://github.com/openpodcast/apple-connector) is
  adopted), add `api/apple_stats.json` here.
* **OP3 history** starts the day the prefix went live — no backfill of
  earlier listens.
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
