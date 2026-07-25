# Video podcasts — the Tesla + SpaceX pilot (July 2026)

Two shows now publish a **second, video-only podcast feed** alongside their
canonical audio feed:

| Show | Audio feed (unchanged) | Video feed (new) |
|---|---|---|
| Tesla Shorts Time | `podcast.rss` | `podcast.video.rss` |
| SpaceX Daily | `spacex_podcast.rss` | `spacex_podcast.video.rss` |

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

## The one coupling to know about

The video episode is a **by-product of the YouTube long-form render**. If
the adaptive publishing policy (`engine/youtube_policy.py`) demotes a show
to a shorts-only tier on a given day, no MP4 is rendered and the video
feed gains no episode. The run does not render a second time just to feed
it — instead it logs

```
::warning::spacex: video podcast is enabled but the adaptive YouTube
policy skipped long-form today …
```

and records `video_podcast_skipped: long_form_not_rendered` in the
episode metrics. Both pilot shows are on full-format tiers today, so this
should be rare; if a video feed must stay strictly daily, set
`youtube.adaptive_publishing: false` for that show.

## Cost

R2 storage for the MP4s, and **zero egress** — R2 charges none, which is
the only reason self-hosting podcast video is economically viable here.

The per-episode size is **not yet measured**. The long-form render is a
mostly-static slideshow with crossfades, so its real bitrate can't be
inferred from the CRF setting alone — it could plausibly land anywhere
between ~60 MB and ~250 MB for a 13-minute episode. Rather than guess, the
pipeline records **`video_podcast_bytes`** in each episode's metrics; read
the first week of those before making any storage projection. Even at the
top of that range, 30 episodes × 2 shows is well under a cent a month at
$0.015/GB-month.

There is deliberately **no retention sweep** in this pilot. The feed lists
`max_episodes` (30) but older objects stay in R2. If storage grows past
what you want to keep, add an R2 lifecycle rule on the `video/` prefix —
that keyspace exists precisely so such a rule can't touch audio.

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
