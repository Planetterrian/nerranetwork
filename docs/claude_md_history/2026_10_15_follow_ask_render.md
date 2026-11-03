# The follow ask on @nerranetwork, and a render budget sized from the audio (Oct 15 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### The follow ask on @nerranetwork, and a render budget sized from the audio (Oct 15 2026)

Operator-directed (register `x-follow-ask-2026-10-15`,
`long-form-render-budget-2026-10-15`; guards
`tests/test_x_follow_ask_2026_10_15.py`). **Every @nerranetwork post had ended
on one identical closer and none asked for a follow.** `engine.x_post.post_closers`
now rotates the closer and, on about one post in four, swaps in a one-sentence
follow ask (`FOLLOW_ASK_CLOSERS`): decided by the calendar and the show's place
in the X POSTING ORDER, so a daily show asks every fourth day and posting
neighbours never ask together. **Oct 17 2026: the order is derived, never
typed** — `FOLLOW_ASK_CADENCE` holds membership and weekday only, and
`FOLLOW_ASK_ROSTER` is sorted by the X slot rank
(`engine.release_schedule.x_posting_order`, Nerra Daily first); a daily show's
phase is its rank among the daily posters, and a weekly show asks once in each
block of four of its weekdays, on a day neither neighbour asks. The
ask is used only when the hook fits whole, and every list ends on the old
closer, so no hook is clipped that was not clipped before. **A show that posts
to the network account must be on the roster** (CI fails otherwise). run_show
records `x_post_follow_ask`; Nerra Daily asks by its edition date. The follower
count is read in X analytics by hand. **Nerra Daily's X post is QUEUED into its
reserved 7:00 ET slot** (`x_queue.enqueue(slot=...)`, the cover hosted on R2
per episode; `x_post_queued` / `x_post_queued_for` in the edition metrics) and
never also posted directly; no queue or a failed enqueue posts at build time as
before. nerra-daily.yml carries the queue's `VOICES_SUPABASE_*` secrets (guards
`tests/test_x_edition_slot_and_follow_phase_2026_10_17.py`). **The long-form render is budgeted at
2.1x the audio** (`engine.video.estimate_long_form_render_seconds`, measured
median 1.91x / p90 2.05x over 60 renders; the 600 s stays as the floor):
Models & Agents Ep204 started a 1,493 s render with 1,189 s left, uploaded the
long-form, died on the alarm before committing, and the fallback cron uploaded
a second long-form five hours later. Metric `long_form_render_need_s`.
