# Audio first, and a release schedule for the day (Oct 17 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Audio first, and a release schedule for the day (Oct 17 2026)

Same operator direction as the Eastern schedule above (register
`audio-first-2026-10-17`, `release-schedule-2026-10-17`; guards
`tests/test_audio_first_2026_10_17.py`, `tests/test_release_schedule_2026_10_17.py`).
**A run publishes its audio before it renders video.** Video is two thirds of
a flagship run (25 of 37 minutes on Tesla), so run_show now writes the feed,
summaries, blog post and post-run validation first and pushes them through
`scripts/checkpoint_publish.sh` ("Auto-generated: <show> <date> (audio)" — the
duplicate guard's prefix; `NERRA_AUDIO_FIRST_PUSH=1` from the workflow, never
in `--test`); the workflow's final commit pushes what the video half adds.
`scripts/stage_show_artifacts.sh` is the ONE staging list both use — a new
committed path goes there. A failed checkpoint push un-commits and leaves
everything staged. **The feed item is rewritten after the video on the SAME
GUID** (`update_rss_feed(keep_existing_guid=True)` — the GUID carries a
timestamp, and a new one makes every app download the episode twice).
**`engine/release_schedule.py` owns when each surface goes public**, in
Eastern wall time, from one `RELEASE_ORDER` (news and markets first): hook
Short 7:00 ET + 15 min per rank, long-form in the SAME slot (Oct 25 2026,
operator-directed — the noon / 18:00 waves kept the long private through the
Short's first day, when 97% of its views arrive; run_show hands the long's
instant to the hook Short so the Short links it), X
preferred slot from 7:30 (7:00 reserved for Nerra Daily), daily newsletters
scheduled for 7:00 through Buttondown (`status: "scheduled"`), Vancouver on
Pacific mornings. A passed slot means now; a refused `publishAt` re-uploads
public; `youtube.release_schedule_enabled` reverts per show. A scheduled
long-form's comment is queued and posted by the half-hourly x-queue run
(`post_scheduled_short_comments.py --stateless`, which checks the video for the
comment first); the feed says when the long-form goes public. Render,
metadata and timing only — outside landmine #17.
