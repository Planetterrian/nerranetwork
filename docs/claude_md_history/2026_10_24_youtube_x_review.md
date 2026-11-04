# YouTube and X review — the decline, and the surfaces that ask for the subscribe (Oct 24–25 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### YouTube and X review — the decline, and the surfaces that ask for the subscribe (Oct 24 2026)

Operator-directed (review
[`docs/reviews/youtube_x_review_2026_10_24.md`](docs/reviews/youtube_x_review_2026_10_24.md);
register `youtube-x-review-2026-10-24`; guards
`tests/test_youtube_x_review_2026_10_24.py`). Measured from 31 stored
snapshots: **the view fall is a YouTube Shorts-feed distribution step on
Sep 15-16 that hit @NerraRU** (feed traffic −65% while RU search and
suggested traffic rose, watch-through and geography flat, the same Tesla and
SpaceX scripts fell 3× more on RU than on EN; uploads were cut AFTER the fall
and explain 10-15% of RU's loss). **EN is a faded breakout** (−8% against
pre-breakout August; subscriber-sourced views −8%; long-form reach flat to
up). Subscriber gains follow Shorts-feed views at 0.9-2.2 per 1,000. The one
content effect the pipeline owns is EN long-form retention (Tesla 18 → 12%,
FF 14 → 10, M&A 12 → 9; SpaceX held 17.5). Rules that bind, all render /
metadata:

- **A sub-10 s chapter ANYWHERE voids YouTube's chapter block, not only the
  first** (`engine.video_metadata._merge_short_chapters`): the chapter whose
  span is too short is dropped (the earlier of the pair; the 0:00 anchor is
  never moved), titles never rewritten. 141 of the last 400 committed chapter
  files carried a later gap under 10 s (Tesla's "Tomorrow Teaser" 7-9 s before
  "Closing" on every episode), so 59% of long-forms shipped no seek-bar
  chapters; replay 259 → 392 valid blocks of 400.
- **The long-form description's second paragraph is the YouTube subscribe
  line**, the hook appears once (the template no longer opens on `{hook}`,
  and a show template that does is deduped), the website is one tagged line,
  and no operator note reaches the viewer ("Suggested pinned comment:" had
  shipped at the end of every description since July — run_show posts the
  comment itself).
- **Every X teaser link goes through `engine.funnel`**
  (`run_show._x_episode_link` / `_x_network_link`, `kind="post"`,
  `placement=body`, `source=x`); the Tesla, Omni View, FF, Planetterrian, MIT
  and generic branches had hand-built the blog URL untagged (1 t.co session in
  28 days, no `x` campaign row). A guard reads the `_build_teaser` body for a
  bare blog URL.
- **Retention is recorded by age** (`avp_by_age` / `avd_by_age` in
  `api/youtube_early_reach.json`, first observation wins): a live AVP snapshot
  is not age-neutral (EN long 1.6% at age ≤ 2 d, 14.4% at 14-20 d), so no slate
  since Oct 13 could be judged on retention and `long_form_median_avp_en_14d`
  is read at a fixed age from now on.
- **Two probe longs can promote a shorts-only show**
  (`scripts/update_youtube_policy.LONG_PROBE_MIN_VIDEOS` = 2, floor-gated,
  never a demotion; long ON still needs four to be read): the weekly probe
  yields at most two longs in 14 days, so the old four-video floor held every
  tier-C show off long-form forever while Planetterrian's probes converted
  13.2 subs per 1,000.
- Checked and not true: the gallery-retention `by_kind` block is populated on
  every show.

**Oct 25 2026 — two of the decisions, shipped** (register
`long-with-short-2026-10-25`, `shorts-subscribe-pill-2026-10-25`; guards
`tests/test_long_with_short_and_pill_2026_10_25.py`): **the long-form goes
public in the hook Short's slot** (`release_schedule.LONG_AFTER_SHORT` is 0 on
purpose — a long even a minute later is still private when the Short goes
public, and the Short then links the website), and **every EN Short carries a
persistent "Subscribe · <cadence> episodes" pill** from 3 s to the end card
(top-left on the brand pill's row, cadence from `engine.cadence`,
`youtube.shorts_subscribe_pill`, off byte-identical; the dubs are the control;
metric `shorts_subscribe_pill_rendered`). The podcast-playlist flag has no
API; The DP Pod and The Age of AI still have no `podcast_playlist_id`.

Operator decisions (⚠️ the spoken ones are AUDIO): the long-form publishes at
or after the Short's slot (97% of a Short's views arrive by day 3 and the
long is private until noon — reverses the Oct 17 waves); a funnel-tagged
YouTube link reply under the Short on X (~$24/mo on the flagships; today 0 of
102 posts point anywhere); the X copy without the YouTube end card; the
Short's furniture (hook ends 6.9 s, identity line 11 s, the Oct 20 map pushes
the first fact to 17.5 s of a 32 s clip — 30% of viewers gone before the show
is named); MIT's four disclaimer sentences before the first story (41% of its
viewers leave inside them); a persistent subscribe pill on Shorts from ~3 s;
per-show playlists flagged in Studio (landmine #15). RU reach is a Studio
read (restrictions, reused-content notices), not a pipeline fix.
