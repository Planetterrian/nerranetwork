# The video renders in its own job; Shorts on the front page (Oct 18 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### The video renders in its own job; Shorts on the front page (Oct 18 2026)

Operator-directed (register `video-job-2026-10-18`, `homepage-shorts-reel-2026-10-18`;
guards `tests/test_video_job_2026_10_18.py`, `tests/test_homepage_shorts_reel_2026_10_18.py`).
**Video no longer shares the show run's time limit.** It was 67-82% of a flagship
run and the 70-minute budget cost the long-form on 5 of the last 14 episodes of
Omni View, Models & Agents and Modern Investing. Under the workflow
(`NERRA_VIDEO_JOB=1`) the show run writes `digests/<dir>/.video_pending_<date>.json`
before the audio-first checkpoint (so it rides the audio commit), sends the
newsletter, and stops; `.github/workflows/render-video.yml` ("Render Episode
Video", job `render (<show>)`) checks out main, fetches the MP3 back from R2
(the raw URL, never the OP3 prefix), runs `run_show.py <show> --video-phase
--date <date>` under its own 110-minute watchdog, commits
"Auto-generated: <show> <date> (video)", and refreshes the homepage in its own
concurrency group (never `finalize-shared-pages`: a short job would supersede a
pending full finalize). **The video and X code is the same code**:
`_make_feed_writer`, `_make_blog_writer`, `_run_video_stage` and `_run_x_stage`
were moved verbatim out of `run()` with every variable they read as a keyword
argument; an inline run (a local run, `--test`, a show with no video,
`NERRA_VIDEO_JOB=0`) calls them in the old order. **The X post moves with the
video** (it carries the Short; the full episode replies under it); a show with
no video keeps its X post in the show run. The video job's credentials must
equal the show run's (a test compares the env lists). `scripts/video_job.py
dispatch` starts it after the show run's final push; the scheduled `sweep`
starts a handoff whose dispatch never arrived and **never retries a handoff
that already has a run** (a failed run may have uploaded before it died —
re-run it by hand). A `.video_done_<date>.json` makes a second dispatch a
no-op (`--force-video` overrides). Multilingual runs after the video job too
and waits for a pending video (both write the show's summaries and posts; the
dubs need its scenes). Revert = repo variable `NERRA_VIDEO_JOB=0`.

**The front page carries a Shorts reel** under the flagship band: the newest
English hook Short of each public show, one per beat before repeating, each
card the episode's own portrait scene (never a YouTube thumbnail), a link to
the show, and an in-page player (`<dialog>`, focus-trapped, prev/next, swipe)
that loads the youtube-nocookie embed only on click and falls back to a
"Watch on YouTube / Next Short" panel when YouTube refuses an embed. A Short
row with `preview_url` (the video job cuts a muted ~6 s 360x640 loop with
`engine/short_preview.py` and uploads it to `previews/<slug>/`) plays muted,
only in view, never under reduced motion or Save-Data. `play_short`,
`select_short_show`, `play_short_unavailable` are GA4 engagement events.
