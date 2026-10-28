# Audience contract (`api/audience_contract.json`)

Versioned JSON Mission Control (and any other portfolio surface) pins to
for Nerra network audience metrics.

**Nothing here requires parsing prose.** Every field is a number, string,
object, array, or explicit `null`. A missing or unmeasured source is
`null`, never `0`.

`schema_version` is an integer (this document describes **version 1**).
`generated_at` is an ISO-8601 UTC timestamp for when the contract file
was built. Each surface block also carries that source's own
`fetched_at` / `generated_at` so a consumer can see which block is stale.

The builder (`scripts/build_audience_contract.py`) is a pure
read-transform-write over already-committed `api/dashboard.json` and
`api/audience_headline.json`. It does not fetch, recompute, or change
how any existing number is produced.

---

## Do not sum these surfaces into one "reach" number

**RSS downloads, YouTube views, and Spotify streams must never be added
together into a single reach / audience total.**

This is a product decision, not a technical one:

- The surfaces **overlap in unknowable ways** — one person can be counted
  as a podcast download, a YouTube view, and a Spotify stream in the same
  week.
- Each surface is measured over a **different window** (7d / complete
  week / 30d / cumulative 92d / 28d GA4). Adding them mixes incompatible
  denominators.

Consumers must keep `op3`, `youtube`, and `spotify` separate. Comparing
within a surface over time is fine; cross-surface addition is not.

---

## Top-level shape

| Field | Type | Meaning |
|-------|------|---------|
| `schema_version` | int | Contract version; start at `1`. Bump when a field is removed or changes meaning. |
| `generated_at` | string | ISO-8601 UTC when this file was written. |
| `op3` | object \| null | Podcast RSS downloads (OP3). |
| `youtube` | object \| null | YouTube per-channel + network 7d. |
| `spotify` | object \| null | Spotify for Podcasters (30-day). |
| `apple` | object \| null | Apple Podcasts Reporter (cumulative retained window). |
| `site` | object \| null | GA4 site traffic. |
| `newsletter` | object \| null | Buttondown subscribers. |

A whole surface is `null` when its source block is missing or
unconfigured.

---

## `op3` — podcast RSS downloads (source: OP3)

**Window:** `network_downloads_7d` / `network_downloads_30d` are rolling
7- and 30-day totals as of the OP3 fetch. `last_week` / `prior_week` /
`wow_pct` compare the last **complete** calendar week of downloads to
the week before it. The current partial week is never compared.

| Field | Type | Notes |
|-------|------|-------|
| `fetched_at` | string \| null | OP3 fetch timestamp from the dashboard. |
| `network_downloads_7d` | int \| null | Rolling 7-day network downloads. |
| `network_downloads_30d` | int \| null | Rolling 30-day network downloads. |
| `last_week` | int \| null | Downloads in the last complete week. |
| `prior_week` | int \| null | Downloads in the week before `last_week`. |
| `wow_pct` | number \| null | Percent change last vs prior; **null** when prior is 0 or unmeasured. |
| `unindexed_shows` | string[] | Show slugs OP3 does not track. **Every OP3 download figure excludes these.** As of 2026-10-28 this list is `nerra_voices`, `offshore_north`, `omni_view_north_america`. Carry it as data so a consumer can render the caveat rather than hard-code it. |
| `shows_measured` | int \| null | Count of shows OP3 resolved and measured. |

Sources: `dashboard.audience.op3` for the rolling totals and
`unindexed`; `audience_headline.network` for WoW fields and
`shows_measured` / `shows_unindexed`.

---

## `youtube` — YouTube Analytics (per channel)

**Window:** `subs_net_7d` is the net subscriber change over the last 7
**complete** reporting days. `views_7d` is views summed over those same
7 complete days. **YouTube Analytics finalizes day-data about 48 hours
behind**, so the 7-day window ends ~2 days before the build date. Do not
treat these as "calendar last 7 days including today."

| Field | Type | Notes |
|-------|------|-------|
| `generated_at` | string \| null | YouTube analytics generation timestamp. |
| `channels` | object | Keys `en`, `ru`, `fr`. |
| `channels.<ch>.subscribers` | int \| null | Current subscriber count. |
| `channels.<ch>.subs_net_7d` | int \| null | Net subscribers gained − lost over the lag-trimmed 7d window. |
| `channels.<ch>.views_7d` | int \| null | Views summed over the lag-trimmed 7d window. |
| `network_views_7d` | int \| null | Sum of per-channel `views_7d` when every channel that reports has a number; otherwise null if none measured. |

**Source note (v1):** `dashboard.audience.youtube` carries
`subscribers` and `subscribers_delta_7d` but **not** `views_7d`. The
lag-trimmed `views_7d` / `subs_net_7d` values the contract documents
already live under `dashboard.growth.channel_scorecard` (same nightly
dashboard build, same YouTube Analytics fetch — not a new computation).
The builder reads that scorecard for the 7d fields and falls back to
`audience.youtube.channels` for subscriber counts when the scorecard is
absent. It does not recompute from raw day series.

---

## `spotify` — Spotify for Podcasters

**Window:** rolling **30 days** (`window_days`), as of the Spotify fetch.

| Field | Type | Notes |
|-------|------|-------|
| `fetched_at` | string \| null | |
| `streams` | int \| null | Network total streams in the window. |
| `listeners` | int \| null | Network total listeners in the window. |
| `window_days` | int \| null | Reporting window length (30 as of 2026-10-28). |

Source: `dashboard.audience.spotify.totals` + `window_days`.

---

## `apple` — Apple Podcasts Reporter

> **Apple's `totals` are cumulative over the reporter's whole retained
> window (92 days as of 2026-10-28), NOT a weekly figure. No Apple field
> in this contract is a per-week number.** A consumer must not treat
> `plays` as a weekly number or derive a weekly rate from it.
>
> `shows_reporting` was **5 of 30** at 2026-10-28, so Apple is a partial
> slice. Any trend read from it will look like a collapse the moment more
> shows start reporting — that is coverage changing, not listening
> collapsing.

**Window:** the reporter's retained history, bounded by `window_start` /
`window_end`, length `days_retained`. Staleness is visible from those
three fields.

| Field | Type | Notes |
|-------|------|-------|
| `fetched_at` | string \| null | |
| `plays` | int \| null | Cumulative plays over the retained window. |
| `listeners` | int \| null | Cumulative listeners over the retained window. |
| `listening_hours` | number \| null | Cumulative listening hours. |
| `shows_reporting` | int \| null | Count of shows that **actually reported** — not the network's show count. |
| `shows_in_network` | int \| null | Companion: network show count so a consumer can see the fraction (`shows_reporting` / `shows_in_network`). |
| `window_start` | string \| null | First date in the retained window (`YYYY-MM-DD`). |
| `window_end` | string \| null | Last date in the retained window (`YYYY-MM-DD`). |
| `days_retained` | int \| null | Length of the retained window in days (92 as of 2026-10-28). |

Source: `dashboard.audience.apple` (flattened reporter totals).
`shows_in_network` is taken from `dashboard.network.shows_count` (the
dashboard's existing network rollup — not invented).

---

## `site` — GA4

**Window:** `days` reporting days (28 at 2026-10-28).

| Field | Type | Notes |
|-------|------|-------|
| `fetched_at` | string \| null | |
| `days` | int \| null | Length of the GA4 reporting window. |
| `totals.active_users` | int \| null | |
| `totals.sessions` | int \| null | |

Source: `dashboard.audience.site`.

---

## `newsletter` — Buttondown

**Window:** point-in-time subscriber count as of the fetch (not a period
total).

| Field | Type | Notes |
|-------|------|-------|
| `fetched_at` | string \| null | |
| `subscriber_count` | int \| null | |

Source: `dashboard.audience.newsletter`, with
`audience_headline.network.newsletter_subscribers` as fallback.

---

## Honesty rules

1. **Unmeasured → `null`, never `0`.** Zero means "we measured and the
   answer was zero." Null means "we did not measure / the source is
   missing."
2. **Do not invent substitutes.** If a documented field has no value in
   the sources, emit `null` and keep the field present.
3. **Carry provenance timestamps** per surface so staleness is visible
   without opening the upstream files.
4. **Keep surfaces separate** — see the reach-sum ban above.
5. **Bump `schema_version`** when removing a field or changing its
   meaning; additive fields may stay on the same version if documented.
