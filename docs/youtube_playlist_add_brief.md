# Brief — Add uploaded YouTube videos to their show's podcast playlist

Hand this whole file to Claude Code (`claude` in the repo root). It's
self-contained.

## Context — what shipped, what's still missing

The 10 podcast playlists exist on YouTube and their IDs are now in
`shows/<slug>.yaml` under `youtube.podcast_playlist_id` (commit
`a87c4097`). Each playlist has `podcastStatus=enabled` and
`privacy=public` so YouTube Music indexes it as a podcast.

What's NOT wired up: the upload pipeline doesn't yet add the video
into its playlist. Today, `_publish_youtube` in `run_show.py` calls
`engine.youtube.upload_video(...)`, gets a watch URL back, and
returns. The new `youtube.podcast_playlist_id` field is read by
nothing.

This brief: add the playlist-add step. Two videos per episode (long
form + Shorts) → two `playlistItems.insert` calls per episode → both
videos appear in the show's podcast playlist within seconds of upload.

The change is intentionally surgical. The pipeline must continue to
behave exactly as today when:

- the YAML has no `podcast_playlist_id` (empty / missing field)
- the playlist add returns 4xx (e.g. token doesn't own the playlist)
- the playlist add returns 5xx (transient — but we don't retry; we
  log + continue)

In any of those cases, the upload itself is already done; failing the
run because we couldn't add to a playlist would be silly.

## The change

### 1. New helper: `engine.youtube.add_video_to_playlist`

Add a small public function in `engine/youtube.py`, alongside
`upload_video`:

```python
def add_video_to_playlist(
    *,
    credentials,
    video_id: str,
    playlist_id: str,
) -> bool:
    """Append a video to a playlist via the YouTube Data API.

    Returns True on success, False on any 4xx (we don't own the
    playlist, video is private and not viewable, etc.) or 5xx (which
    we don't retry — playlist membership is best-effort, not the
    upload).
    """
```

Implementation:

- Build a `youtube` client from `credentials` (same pattern as
  `upload_video`).
- Call `youtube.playlistItems().insert(part="snippet", body={...})`
  with `snippet.playlistId`, `snippet.resourceId={"kind":
  "youtube#video", "videoId": video_id}`.
- Wrap the call in a `try/except HttpError` that logs at WARNING
  with the status code and message and returns `False`.
- Log at INFO with the playlist ID and video ID on success.
- 50 quota units per call (cheap relative to the 1600 each upload
  costs).

Don't add retries — the upload itself just succeeded, so we already
know the credentials are valid; if the playlist insert is failing
it's almost certainly a permission or schema issue, not transient.

### 2. Modify `engine.youtube.upload_video` to return the video ID

Right now `upload_video` returns a string watch URL like
`https://www.youtube.com/watch?v=AM43XgHNrtc`. The downstream code
in `_publish_youtube` needs the bare ID for the playlist insert.

The cleanest fix: change the return type to a small dataclass / dict
exposing both:

```python
@dataclass
class UploadResult:
    video_id: str
    watch_url: str
```

…and change every call site to use `result.watch_url` /
`result.video_id`. There are exactly two call sites (long-form +
Shorts, both in `run_show.py:_publish_youtube`), so the blast
radius is small.

If you'd rather not introduce a dataclass, returning a `dict` with
the same two keys is fine — but pick one and be consistent.

Update the existing tests in `tests/test_youtube.py` that pin the
return type (the `test_upload_video_invokes_api_and_returns_watch_url`
case at line 274) to match the new shape.

### 3. Wire it into `_publish_youtube`

In `run_show.py:_publish_youtube` (around line 2440 for long-form
and the matching block ~30 lines below for Shorts):

```python
# After the successful upload_video(...) call:
upload = upload_video(...)
result["long_url"] = upload.watch_url

playlist_id = (config.youtube.podcast_playlist_id or "").strip()
if not playlist_id:
    logger.info("Podcast playlist ID empty — skipping playlist add.")
else:
    add_video_to_playlist(
        credentials=credentials,
        video_id=upload.video_id,
        playlist_id=playlist_id,
    )
```

Same pattern for the Shorts block. Use the existing `credentials`
local that's already in scope from earlier in the function.

The "Podcast playlist ID empty — skipping playlist add" line is
exactly what the original PR brief promised (operator brief said
"a single-line skip log entry until the IDs are populated"). Since
the IDs ARE populated now, the skip log will only ever fire for a
NEW show that hasn't been backfilled — useful breadcrumb to flag
"hey, you added a show but didn't run create_youtube_playlists.py
for it".

### 4. Config schema — already done

`config.youtube.podcast_playlist_id` should already exist as an
optional field. Double-check `engine/config.py` — if it's not in
the YouTube config dataclass / schema, add it as
`Optional[str] = None`.

### 5. Tests in `tests/test_youtube.py`

Add three new tests:

```
test_add_video_to_playlist_calls_playlistitems_insert
test_add_video_to_playlist_returns_false_on_http_error
test_upload_result_has_video_id_and_watch_url
```

Mock the `googleapiclient.discovery.build` chain the same way the
existing `test_upload_video_*` tests do. Don't hit the network.

Also adjust whichever existing tests inspect `upload_video`'s return
shape (just the one at line 274 from grep).

### 6. Local verification

```
# Pick a recent existing audio file:
AUDIO=$(ls digests/tesla_shorts_time/*_Ep4*_*.mp3 | tail -1)
COVER=assets/covers/tesla.jpg

# This dry-run mocks the API but exercises the dataclass + flow:
pytest tests/test_youtube.py -v
```

For an actual end-to-end check (only do this once you've reviewed
the diff): manually trigger the `tesla` workflow from GitHub Actions
and confirm:

1. Workflow logs include a NEW INFO line:
   `engine.youtube: added video AM43XgHNrtc to playlist
   PLRHMnzNNXPYCRrcYpPwAzjaRXqzKRUl23` (twice — once long form,
   once Shorts).
2. Open https://www.youtube.com/playlist?list=PLRHMnzNNXPYCRrcYpPwAzjaRXqzKRUl23
   — the new long-form + Shorts videos should be in the list.
3. The playlist appears in YouTube Music as a podcast (search the
   show name in YT Music; the playlist will show up as a podcast
   subscription target).

If step 1's log lines don't appear but the upload still succeeded,
search the workflow logs for the WARNING — the most likely cause is
that the OAuth token doesn't have permission to modify the playlist
(scope issue: `youtube.upload` is enough to upload but you need
`youtube` for playlist writes). Both scopes are already granted via
the existing bootstrap script, so this should work.

## Quota note (read this before opening the PR)

Each `playlistItems.insert` is 50 quota units. Each episode now
costs:

  - upload (long form):     1600
  - upload (short):         1600
  - thumbnails.set ×2:       100
  - playlistItems.insert ×2: 100
  ──────────────────────────────
  total per episode:        3400

With 8 phase-1 EN shows running daily, that's 27,200 units/day —
already over the default 10,000-unit quota. Operator already knows
about this; the YouTube API quota extension request is parked as a
follow-up. Do NOT use this PR to flip more shows to
`youtube.enabled: true`. Stick with the existing phase-1 set
(`tesla`, `fascinating_frontiers`, `models_agents`).

If you find the quota is still tight on phase-1 (e.g. the digest
retry loop multiplies API spend on a bad day), the easiest knob is
making the playlist add fully optional via a per-show
`youtube.add_to_playlist: bool = True` flag. Don't ship that flag
unless you have evidence we need it.

## Out of scope for this change

- Backfilling old episodes into the playlist. There are 451 Tesla
  episodes uploaded to R2 but only one Tesla video on YouTube
  (`AM43XgHNrtc`). A backfill is a separate one-time script.
- Auto-removing videos from playlists when they're privacy-deleted.
- Cross-posting to YouTube Music's podcast directory beyond what
  the `podcastStatus=enabled` flag already does — there's no API
  for that and it's not needed.
- Custom thumbnail upload fix (the 403 is a separate
  account-gating issue; will likely resolve itself once the
  channel has more activity).

## Files to touch

- `engine/youtube.py` — add `UploadResult` dataclass (or keep dict),
  add `add_video_to_playlist`, change `upload_video` return type
- `run_show.py` — update both call sites in `_publish_youtube`
  (~lines 2440 and ~2475 — search for `upload_video(`)
- `engine/config.py` — confirm `podcast_playlist_id: Optional[str]`
  is in the YouTube config dataclass (add if not)
- `tests/test_youtube.py` — adjust the upload return-shape test,
  add 2-3 new tests for `add_video_to_playlist`

## Acceptance criteria

1. `pytest tests/test_youtube.py` passes.
2. `_publish_youtube` either logs `added video <id> to playlist
   <PL...>` (success), `Podcast playlist ID empty — skipping
   playlist add` (no ID configured), or a WARNING containing the
   API error (failure) — never a crash.
3. After commit + push to `main`, manually re-trigger the `tesla`
   workflow; the new long-form + Shorts videos appear in
   https://www.youtube.com/playlist?list=PLRHMnzNNXPYCRrcYpPwAzjaRXqzKRUl23
   within a minute of the workflow finishing.
4. The pipeline run time goes up by ~1-2 seconds total (two extra
   API round-trips at 50 units each).
