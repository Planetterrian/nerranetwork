# The Oct 27 slate: a step that is green can still fail every run (Oct 28 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### The Oct 27 slate: a step that is green can still fail every run (Oct 28 2026)

Review [`docs/reviews/slate_review_2026_10_28.md`](docs/reviews/slate_review_2026_10_28.md);
register `slate-2026-10-28`; guards `tests/test_slate_2026_10_28.py`. 16
shows published, 10/10 videos, Nerra Daily complete. Rules that bind:

- **Every timestamp in a PostgREST query string is a `Z` instant, never
  `+00:00`.** An unencoded `+` reaches PostgREST as a space and the call
  returns 400. The guest survey and the hello invite (both
  `continue-on-error`) had failed on every "Fire scheduled interviews" run
  since they shipped, so no guest had ever been surveyed. The hello query
  also filtered `interviews` on `scheduled_for`; that column belongs to
  `interview_runs`, and `interviews` has `scheduled_at`. Read a
  `continue-on-error` step's log, not its colour.
- **A system-package cache hit installs through `dpkg -i`.**
  `apt-get install --no-download` resolved against the image's stale lists
  and fell back to the mirror on all 50 hits. The mirror install carries
  `-f`.
- **The page-date probe opens up to 40 pages**
  (`engine.article_dates.DEFAULT_MAX_PROBES`, 8 at a time). At 12, Tesla
  Ep647 aired a 2022 IEEE Spectrum article as news.
- **A number inside a bold item heading is not part of the title**
  (`**1. Title — Source**`, FF Ep235's chapters).
- **A digest heading that a marker's spoken pattern matches whole takes the
  marker's title** (SpaceX Ep143 had "Engineering Deep Dive" beside "The
  Engineering Angle"). A word inside a heading is never enough: on the
  replay, Env Intel's "Regulatory Calendar" had matched "regulatory".
- **Frame 1's opening clause ("before you go, this show is part of") is a
  promo-cut anchor.** Whisper had lost the network's name on SpaceX Ep142.
- **A clock time is never glued to a letter, a digit or a glued `*`**
  ("HLA-DRB1*01:03" had aired as "one oh three A M").
- **A capital-K resolution next to a screen or video word is a name**
  ("4K video" had aired as "four thousand video").

Eight corrections filed. A members-only episode has no correction mechanism
yet: the North America Ep029 item is the operator's. **The fire-tick gate
reads a run by its slot (`scheduled_for`), never its creation**: every run is
staged a day ahead, so the old 48-hour `created_at` read held the gate open
for two days per booking (232 dispatches on Oct 27; 65 on the replay;
`workers/voices/test/fire_tick_window.test.ts`). Open: Mira's compiled prompt
is over budget for the next two guests (needs a rehearsal), and MIT's script
runs past the single-call `<fast>` ceiling.
