# A beat only where a story changes, and X video (Oct 17 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### A beat only where a story changes, and X video (Oct 17 2026)

Slate review ([`docs/reviews/slate_review_2026_10_17.md`](docs/reviews/slate_review_2026_10_17.md);
register `story-breaks-placement-2026-10-17`, `slate-2026-10-17`; guards
`tests/test_slate_2026_10_17.py`). The Oct 16 anchoring held (1 unplaced of
133); what failed was WHICH lines got a beat. **`MIN_STORY_SECONDS` is 12**
(20 dropped 15 real stories in a day — Tesla's run 14-22 s apart). The cold
open (to "This is <Show>, episode") and everything from the sign-off never set
the story; unsourced paragraphs join the sourced paragraph that ends their
section unless it opens on its own bold title; an all-essay digest moves
forward only; the lead runs two lines before the first beat; an anchor backs
off by LETTERS and snaps to a word start. A "retells" overlap suppression was
measured and REJECTED (it ate Planetterrian's deep-dive opener 3/3). Content:
**the expansion dedup never touches a fenced block** (it had deleted ledger
lines — 45 malformed entries in a week); **a date in the URL slug ages an
article** (`engine.article_dates.url_slug_date`, the older date wins, never a
future one, a `/YYYY/MM/` path wins); MIT's pick prompt names the open
positions; Top World says nothing about desks when none fed it; the X teaser
clips through `engine.titles`. **A queued X post is `x_post_queued`, not a
confirmed post** — the x-queue workflow is the delivery record
(`x_queued_share_7d`). Full-episode video on X is possible without Premium up
to 20 min (design in the review doc; needs a Supabase migration — operator).
⚠️ AUDIO — A/B-listen one Tesla and one UC episode.
