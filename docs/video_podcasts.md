# Video podcasts on Apple (July 2026 — five shows)

Five shows now publish a **second, video-only podcast feed** alongside
their canonical audio feed (the July 25 tesla+spacex pilot expanded on
July 27):

| Show | Audio feed (unchanged) | Video feed (new) |
|---|---|---|
| Tesla Shorts Time | `podcast.rss` | `podcast.video.rss` |
| SpaceX Daily | `spacex_podcast.rss` | `spacex_podcast.video.rss` |
| Fascinating Frontiers | `fascinating_frontiers_podcast.rss` | `fascinating_frontiers_podcast.video.rss` |
| Models & Agents | `models_agents_podcast.rss` | `models_agents_podcast.video.rss` |
| Models & Agents for Beginners | `models_agents_beginners_podcast.rss` | `models_agents_beginners_podcast.video.rss` |

The video episode is the **long-form 1920×1080 MP4 the YouTube stage
already renders** — previously deleted seconds after the YouTube upload.
So a video podcast costs one R2 upload per episode and **no extra render
time and no extra Grok spend**.

## Why a separate feed, and why an MP4 enclosure

Apple relaunched video podcasts in February 2026 with an HLS-backed
player. Two constraints decide the architecture for a self-hoster:

1. **HLS is partner-gated.** The new experience is available through a
   short list of hosting companies (Acast, ART19, Omny, Simplecast, …)
   behind an API-key workflow. Self-hosted shows cannot opt in.
2. **Apple ignores `podcast:alternateEnclosure`.** There is no way to
   offer a video rendition alongside audio inside one feed and let the
   client choose.

What remains is the original, boring, still-supported route: a plain RSS
`<enclosure>` pointing at an MP4 (`MOV`/`MP4`/`M4V` are all accepted).
And [Apple's own guidance][apple] is to publish the video edition as a
**separate show** — "If you already have an audio version of your show on
Apple Podcasts, you can create a new show for the video version" — rather
than mixing formats in one feed.

Hence: a second feed, never a modification of the audio one. **No
published audio enclosure URL changes** (rewriting a live enclosure
re-downloads the episode for every subscriber).

[apple]: https://podcasters.apple.com/support/3684-video-podcasts

## How it works

```
run_show.py  _publish_youtube
  └─ build_long_form_video(...)          # the MP4 the YouTube upload uses
     └─ engine.video_feed.upload_episode_video()
          → R2  video/<slug>/<Episode_Name>.mp4   (content_type: video/mp4)
          → result["video_podcast"] = {url, bytes, filename, duration_sec}
  └─ upload_video(...)                   # YouTube, independent of the above
  └─ long_video_path.unlink()            # cleanup, as before

run_show.py  (after save_summary_to_github_pages)
  └─ engine.summaries_io.upsert_video()  # record.video = {...}
  └─ engine.video_feed.build_video_feed_for_show()
          → <show>_podcast.video.rss
```

The feed is **rebuilt fresh from the summaries JSON** every time (the
`engine.language_feeds` pattern), never by parsing the previous file. That
makes it idempotent, regenerable from committed state, and safe to run on
a schedule. Nightly maintenance re-runs
`scripts/build_video_feeds.py --all` as a repair sweep for the case where
an episode run died after the R2 upload but before the feed write.

Design details worth not undoing:

* **`type="video/mp4"`.** `engine/publisher.py` hardcodes `audio/mpeg` in
  three places, and `upload_to_r2` defaults a non-`.mp3` file to
  `application/octet-stream`. Both are wrong for Apple, so the type is
  passed explicitly on both the upload and the enclosure.
* **Deterministic GUIDs** (`spacex-video-ep044-20260725`) — namespaced
  with `video` so they can never collide with the audio feed's, and stable
  across rebuilds so subscribers are never re-notified. (`publisher.py`
  appends `%H%M%S%f` to its GUIDs; do not copy that here.)
* **Churn suppression** — a rebuild whose only difference is
  `<lastBuildDate>` is not written, so a quiet night produces no commit.
* **Never writes an empty feed** — Apple rejects one.
* **Enclosures are not OP3-prefixed.** OP3 is an audio-download analytics
  redirector, not a video CDN. Video engagement comes from Apple Podcasts
  Connect instead.
* **Its own R2 keyspace** (`video/<slug>/…`, not `<slug>/…`) so a storage
  lifecycle rule can expire video without touching the audio objects that
  every published enclosure depends on.

## Rendering is decoupled from YouTube publishing

The video episode is a by-product of the YouTube long-form render, and
that render used to be gated on the adaptive publishing policy
(`engine/youtube_policy.py`). A shorts-only tier therefore meant no video
episode that day — the feed quietly stopped growing while the audio feed
kept publishing daily, which is the state Apple de-ranks.

`run_show` now renders whenever **either** product wants the MP4:

```python
_render_long = _policy_publish_long or config.video_podcast.enabled
```

and uploads to YouTube only when `_policy_publish_long` is true. A
policy-skipped day costs render time (~10 min of runner) and **no API
spend** — the visual plan, including the Grok imagery, is already built by
that point. The run records `video_podcast_render_only: true` so those days
are visible in metrics rather than silent.

If you ever want the old behaviour for a show, turn off `video_podcast`
for it rather than reintroducing the coupling.

## Cost

R2 storage for the MP4s, and **zero egress** — R2 charges none, which is
the only reason self-hosting podcast video is economically viable here.

**Measured, 27 July 2026** — the earlier "not yet measured, somewhere
between 60 and 250 MB" estimate is now settled. Across the 50 episodes
in the five live video feeds:

| | |
|---|---|
| Mean episode | **174 MB** |
| Total bitrate | **~2.05 Mbps** (≈1.86 Mbps video + 192 kbps audio) |
| Per minute | ~15.4 MB |

Remarkably consistent, and higher than a slideshow ought to be. The
cause is the Ken Burns zoom: continuous sub-pixel motion on every frame
defeats inter-frame prediction, so CRF 22 spends real bitrate
re-describing what is visually a still photograph. Easing the zoom
ceiling (1.12 → 1.09, July 2026) helps; it does not eliminate it.

At five shows publishing daily that is **≈318 GB/year, growing forever**.
R2 is $0.015/GB-month, so the first year alone settles at roughly
$4.80/month and the second doubles it. This is the one place the video
pilot turns into a recurring bill.

**`scripts/prune_video_r2.py`** is the answer. It deletes by
*reachability*, not age: an object goes only if no `*.video.rss` and no
`digests/*/video_assets.json` references it. Dry-run by default, with a
`--keep-newest` floor (60) so a feed-generation bug can't cascade into
deleting a back catalogue.

```
python scripts/prune_video_r2.py            # report
python scripts/prune_video_r2.py --apply    # delete
```

A bucket lifecycle rule is the wrong tool here even though the `video/`
keyspace was built for one: lifecycle expires by age, but the feed window
is a *count*, so a show that pauses for two months would have
still-listed episodes deleted out from under it.

`max_episodes` is a real knob as of the durable index (below). Before it,
raising the value did nothing: `summaries_<slug>.json` is truncated to 30
records by `publisher.save_summary_to_github_pages`, so the feed could
never see further back — and worse, each episode **left the feed** on its
31st day, which Apple treats as a de-listing, while its MP4 stayed in R2
with nothing pointing at it.

## The durable index

`digests/<slug>/video_assets.json` (`engine/video_index.py`) is the
authoritative record of which episode has a video, where, and how many
bytes. Nothing truncates it. The feed builder reads summaries first — it
carries the operator-facing title and show notes — and falls back to this
index for anything summaries has forgotten, so an episode stays in the feed
for as long as `max_episodes` allows rather than for 30 days.

It follows `engine/youtube_index.py`, including being **per-show**: a dozen
show jobs run concurrently in the daily matrix, and a network-wide file
would have every one of them racing to commit the same path.

## Backfilling a new video show

A freshly enabled show's feed contains only episodes published since the
switch — everything earlier had its MP4 deleted after the YouTube upload,
and Apple routinely rejects a sparse feed. `scripts/backfill_video_feed.py`
re-renders past episodes from assets that *did* survive: R2 audio,
committed cover art, gallery scene stills, committed transcripts and
chapters. `build_long_form_video` is pure ffmpeg, so this costs runner time
and no API spend.

```
python scripts/backfill_video_feed.py spacex --latest 10
```

or dispatch **Backfill Video Podcast Feeds** in Actions for the per-show
matrix. It needs `R2_GALLERY_BUCKET` as well as the usual R2 credentials —
the public gallery CDN returns 403 for original JPEGs from CI, so without
the authenticated fallback every episode renders cover-only. The script
refuses to start rather than produce a pile of those.

Scene stills only exist in the gallery from roughly tesla ep486 / spacex
ep003 / fascinating_frontiers ep101 / models_agents ep093 /
models_agents_beginners ep052 onward. Older episodes still render, but
cover-only — reported as `scene_count: 0` rather than failing.

## Operator checklist

Nothing here is required for the code to run — the feeds build themselves
on the next Tesla / SpaceX episode. These steps are what make them
*listenable in Apple Podcasts*.

1. **Wait for one episode of each show.** The feed is not written until an
   episode carries a video track (an empty feed would be rejected). After
   the next Tesla and SpaceX runs, confirm:
   - `https://nerranetwork.com/podcast.video.rss`
   - `https://nerranetwork.com/spacex_podcast.video.rss`
2. **Check the MP4 actually serves.** Open an enclosure URL from the feed
   in a browser — it should play, and the response's `Content-Type` must be
   `video/mp4`. (If it downloads as `application/octet-stream`, the upload
   lost its content type and Apple will refuse the episode.)
3. **Submit each feed to Apple Podcasts Connect as a NEW show.**
   `podcastsconnect.apple.com` → **+** → *Add a show with an RSS feed* →
   paste the `.video.rss` URL. Do **not** point an existing show at it —
   these are separate shows by design.
   - Declare content rights ("no third-party content"), set Update
     Frequency to Daily, and confirm the category matches the audio show.
   - Apple validates the feed on submission; a fetch error here almost
     always means the MP4 is not publicly readable.
4. **Record the new Apple show IDs** as `apple_show_id:` in a follow-up, so
   the nightly Apple analytics fetch covers the video shows too.
5. **Update `docs/podcast_directories.md`** — add two rows for the video
   editions so the dashboard's distribution card counts them.
6. **Optional:** Spotify accepts video podcasts only through its own
   uploader (not RSS), so the video editions are Apple-only for now.
   YouTube already carries the same footage natively.

## Turning it off

One flag per show:

```yaml
# shows/tesla.yaml
video_podcast:
  enabled: false
```

That stops the upload and the feed rebuild immediately. The already-published
`.video.rss` and the R2 objects stay where they are — delete the feed file
and remove the show in Apple Podcasts Connect if you want it gone for
subscribers.

## Files

| Path | Role |
|---|---|
| `engine/video_feed.py` | Feed builder + R2 upload helper |
| `engine/config.py` → `VideoPodcastConfig` | The `video_podcast:` YAML block |
| `engine/summaries_io.py` → `upsert_video` | Attaches the track to an episode record |
| `scripts/build_video_feeds.py` | Manual / nightly rebuild sweep |
| `tests/test_video_podcast.py` | Drift guards |
| `docs/analytics.md` | Where the resulting numbers land |
