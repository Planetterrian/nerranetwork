# Distribution debt runbook — Aug 2026

Operator-directed (Aug 15 2026 flagship review, item 4): the detailed,
do-this-then-that outline for clearing every open distribution gap. All of
this is console/operator work — **no code changes are required for any item
below**; the feeds and analytics wiring already exist and are current. The
dashboard's `distribution` card is the scoreboard: every row below moves a
`missing` cell to a listed one.

Ordering is by expected reach per hour of effort.

---

## 1. Video podcasts → Apple (tesla + spacex) — ~30 min, unlocks a new surface

The pilot feeds are LIVE and current (`podcast.video.rss` 29 items,
`spacex_podcast.video.rss` 30 items, daily MP4s on
`audio.nerranetwork.com`, correct `video/mp4` content type) — they have
simply never been submitted. Full detail: `docs/video_podcasts.md` §"Apple
submission checklist". Condensed:

1. Validate both feeds at castfeedvalidator.com (30 seconds each).
2. Open one enclosure URL per feed in a browser — it must PLAY (a download
   as `application/octet-stream` means the content type was lost; that
   would be a bug report, not a submission blocker — none observed).
3. `podcastsconnect.apple.com` → **+** → *Add a show with an RSS feed* →
   paste `https://nerranetwork.com/podcast.video.rss`. Submit as a **NEW
   show** ("Tesla Shorts Time (Video)"), never by repointing the audio
   show. Repeat for `https://nerranetwork.com/spacex_podcast.video.rss`.
4. Record the two new Apple show IDs (needed so the nightly Apple
   analytics fetch can cover them — file them in an issue or hand them to
   the next Claude session to wire `apple_show_id`).
5. Add two rows to `docs/podcast_directories.md` so the dashboard's
   distribution card counts the video editions.

Note: Spotify takes video only via its own uploader (not RSS) — video
editions stay Apple-only by design; YouTube already carries the footage.

## 2. `spacex_ru` on Spotify — ~10 min, fixes the RU pilot's biggest gap

`spacex_podcast.ru.rss` never indexed on Spotify (dashboard
`distribution.notes`), while `tesla_ru`/`tesla_fr`/`spacex_fr` are listed.
The RU pilot's whole thesis is @NerraRU reach → Russian-language capture;
Spotify is a real listening surface for that audience.

1. podcasters.spotify.com → *Add your podcast* → paste
   `https://nerranetwork.com/spacex_podcast.ru.rss`.
2. The feed's channel `<title>` is now «SpaceX Ежедневно» (fixed
   2026-08-15 — it was untranslated English, which may be why the earlier
   submission never stuck; if there is a stalled prior submission in the
   dashboard, delete and resubmit).
3. Verification email goes to the feed's `itunes:email` — check that
   inbox during submission.

## 3. Podcast Index — ~15 min, unlocks every PI-backed app at once

Podcast Index feeds Fountain, Podverse, CurioCaster and a long tail of
Podcasting-2.0 apps, and the feeds already carry `podcast:` namespace tags
that only render there. The dashboard notes the stored API keys return
HTTP 401 (stale).

1. Regenerate keys at api.podcastindex.org (log in → new key/secret pair).
2. Replace the `PODCASTINDEX_API_KEY` / `PODCASTINDEX_API_SECRET` GitHub
   Actions secrets.
3. Re-run the "Submit Podcast Directories" workflow (workflow_dispatch) —
   it submits every feed in `docs/podcast_directories.md` idempotently.
4. Confirm the dashboard's Podcast Index column flips from 0% on the next
   nightly.

## 4. YouTube Music + Amazon Music + iHeart + Pocket Casts — ~45 min total

All four show 0% listed / `missing` for tesla and spacex. Each is a
one-time form with the RSS URL; all four then auto-update from the feed.

- **YouTube Music**: music.youtube.com/podcasts (Creator flow) → *Add RSS
  feed* under the @NerraNetwork Google account. Both flagship audio feeds.
  (Distinct from the YouTube video uploads — this lists the PODCAST in the
  Music app's podcast tab.)
- **Amazon Music**: podcasters.amazon.com → *Add or claim your podcast* →
  RSS URL → verification email. Covers Amazon Music + Audible.
- **iHeartRadio**: podcasters.iheart.com → *Submit a podcast* → RSS URL.
- **Pocket Casts**: pocketcasts.com/submit → RSS URL (usually indexed
  within a day; no account needed).

Start with tesla + spacex only (the ask that prompted this runbook); the
other 14 shows can follow the same four forms whenever convenient — the
submission workflow's table in `docs/podcast_directories.md` is the
checklist of record either way.

## 5. Funnel click surfaces on YouTube — ~20 min, multiplies the Aug-15 tagging work

The description links are now funnel-tagged (code-side, shipped), but the
two highest-click surfaces are operator-only:

1. **Pin the funnel comment** on new uploads in Studio (the API cannot
   pin). Priority: @NerraRU — it has the reach. Even doing this for a week
   of uploads gives the funnel report its first readable click numbers.
2. **Channel About links**: add the show page + `ru/spacex.html` +
   `ru/tesla.html` (tagged links — copy them from any recent description's
   "Show page" line) to the About tab of @NerraNetwork, @NerraRU, @NerraFR.

## 6. Worker deploy for the new `ru-tesla` capture tag — ~5 min, REQUIRED

`workers/gallery/src/handlers.ts` now allow-lists `ru-tesla`, but the
Worker serves the OLD list until deployed:

    cd workers/gallery && wrangler deploy

Until then, captures from `ru/tesla.html` fall back to the gallery list
(mis-tagged, not lost). Deploy before promoting the lander anywhere.

---

### Explicitly NOT on this runbook

- **OP3 prefixes on video enclosures** — deliberate omission (OP3 is an
  audio redirector; Apple Connect is the video engagement instrument).
- **ZH distribution** — no decision yet; see the language-expansion
  analysis (Aug 15 2026 session): the recommended next language is a
  properly-distributed Spanish relaunch, not ZH, whose natural platforms
  (mainland) are unreachable for YouTube/Spotify.
- **Re-prefixing the published Age of AI Ep001 enclosure** — standing
  rule: never rewrite a live enclosure URL.
