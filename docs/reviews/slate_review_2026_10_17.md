# Slate review — October 17, 2026

Operator brief: review today's slate and the breaks between stories; review
how the network posts to X, and whether full episode videos can go to X as
well as YouTube.

## The slate

Fifteen public shows published. All five regional desks skipped with
`no_member_demand`, which is the gate working (the demand check could read
membership this time). The spoken-text gate passed on all 15 episodes.

| Show | Script words | Script model | Claims (flagged) | Breaks found / inserted / unplaced |
|---|---|---|---|---|
| Tesla Ep637 | 1,285 | grok-4.6 | 10 (0) | 15 / 10 / 0 |
| SpaceX Ep133 | 1,354 | grok-4.6 | 3 (0) | 10 / 8 / 0 |
| Omni View Ep208 | 1,584 | grok-4.6 | 9 (1) | 9 / 8 / 0 |
| Fascinating Frontiers Ep225 | 1,377 | grok-4.6 | 9 (0) | 10 / 9 / 0 |
| Planetterrian Ep216 | 1,107 | grok-4.6 | 7 (1) | 11 / 10 / 0 |
| Models & Agents Ep206 | 1,470 | grok-4.6 | 6 (2) | 9 / 8 / 1 |
| MAB Ep199 | 1,238 | grok-4.6 | 4 (0) | 3 / 3 / 0 |
| Modern Investing Ep203 | 2,030 | grok-4.6 | 5 (0) | 12 / 11 / 0 |
| Unintended Consequences Ep145 | 1,857 | grok-4.7 | 2 (0) | 10 / 9 / 0 |
| First Principles Ep133 | 1,723 | grok-4.7 | 3 (2) | 6 / 6 / 0 |
| AI Chips Ep026 | 1,470 | grok-4.7 | 16 (2) | 7 / 6 / 0 |
| MAG 7 Ep025 | 1,261 | grok-4.7 | 10 (0) | 8 / 7 / 0 |
| Prediction Markets Ep025 | 1,627 | grok-4.7 | 22 (0) | 8 / 8 / 0 |
| Vancouver Ep025 | 1,583 | grok-4.7 | 22 (0) | 13 / 10 / 0 |
| Omni View Top World Ep025 | 1,485 | grok-4.7 | 18 (0) | 2 / 2 / 0 |

## Story breaks — measured in the shipped audio

Yesterday's fix (PR #1451) worked: one break of 133 could not be placed in
the audio, against 22 of 130 on Oct 16. Every beat that was inserted had the
designed length: 0.94–1.08 s median per episode, 1.6–1.8 times the ordinary
gap between lines. The cue still sits 7.5–10 dB under the speech's mean
power, the same as before the PR. No beat landed before a sign-off, and no
pause was doubled.

What went wrong was **which lines got a beat**. Eight episodes were read
line by line against their digests:

1. **The 20 s spacing dropped real stories.** It dropped 17 beats, and 15 of
   them were genuine story changes. Tesla's stories run 14–22 s apart, so a
   given story got a beat roughly half the time. Five Tesla stories got none,
   among them Mike Snyder, the Roadster and Song Jae-hee's Cybertruck.
2. **Mid-story beats: 10 of 67 in the eight episodes**, six of them on
   Unintended Consequences. Four causes:
   - **The cold open set the story.** The hook summarises the lead, so the
     lead's first body line counted as a new story. This hit FF Ep225's
     "El Gordo, as the cluster is nicknamed…" and UC Ep145's first line.
   - **A section split at its citation.** Unsourced paragraphs followed by
     the sourced paragraph were cut into two stories. This put beats inside
     Vancouver's Closer Look and Both Sides, and inside MAG 7's Thread.
   - **Narrative digests leaned sideways.** UC's segments share vocabulary
     (marshes, dams, pulse), so two lines leaning toward another segment were
     enough for a beat.
   - **The lead story got a beat after one line.** On Planetterrian Ep214 the
     Spotlight, which retells the lead, began on the next line and took a
     beat inside the lead.
3. **An anchor landed late.** The search backed off by a count of script
   words, so on M&A Ep206 Whisper's "m i t c s a l" put the anchor five words
   late and outside the pause window. That was the one unplaced break.

Fixes, all in `engine/story_breaks.py`:
- **Spacing:** `MIN_STORY_SECONDS` drops from 20 to 12 s. Twelve seconds
  still blocks the 7 s stutter that set the rule.
- **Cold open and sign-off:** lines up to the identity line ("This is <Show>,
  episode N") and lines from the sign-off onward never set the story.
- **Citations don't split sections:** unsourced paragraphs join the sourced
  paragraph that ends their section, unless that paragraph opens on its own
  bold title (MAB pools both of a section's Source lines at the end of its
  last item).
- **Narrative digests move forward only:** on an all-essay digest a beat goes
  only to a segment not yet told, and only when two of the next three lines
  are on it.
- **The lead story runs at least two lines** before the first beat.
- **Anchoring** backs off by the skipped words' letters and snaps to the
  nearest word start.

Replay on the Oct 17 audio:

| | Before | After |
|---|---|---|
| Found | 133 | 121 |
| Anchored | 132 | 121 |
| Inserted | 115 | 116 |
| Dropped by spacing | 17 | 5 |

The 12 fewer found are the mid-story beats. Across Oct 13–17 the totals go
from 830 to 758. Every new beat was read: segment openers ("On the
calendar…", "For what's on around town…") and "Before we go" teasers.

Rejected after measuring: suppressing a beat when one unit "retells" another
(token overlap ≥ 0.40). It removed FF's mid-Spotlight beat, but it also
removed Planetterrian's deep-dive opener in three of three episodes and
merged Tesla's Sunrun and solar items, which are separate stories.

⚠️ AUDIO — A/B-listen one Tesla episode (more beats) and one Unintended
Consequences episode (fewer beats).

## Content fixes

- **Claims ledgers written as "malformed".** This week 45 entries on 12
  shows (Omni View Ep208: 6 of 9) were damaged by the digest expansion
  retry. `_dedup_expansion_sentences` treated the fenced `claims` JSON as
  prose and deleted each `claim` and `supporting_quote` line, because both
  repeat a sentence of the digest. Fenced lines now pass through untouched
  and are never used as dedup anchors.
- **MAB's "Explain Like I'm 14" was emptied.** The overlap dedupe read the
  explainer, which explains the Big Story by design, as a repeat; Ep199
  shipped a bare heading. The section is now exempt on MAB.
- **A week-old quake aired as news.** Omni View Ep208 read The Hindu's
  `…panama-earthquake…update-october-10-2026` as fresh, with a toll less
  accurate than the one the show aired on Oct 11. The feed date was new, and
  nothing read the date the publisher wrote into the slug.
  `engine.article_dates.url_slug_date` reads month-name and ISO slug dates,
  and `article_age_days` now takes the older of page/feed and slug.
  - A future-dated slug (a deadline) never makes an article older.
  - A URL with a `/YYYY/MM/` path is left to that path.
  - Calibrated on 732 slug-dated tracker URLs: four were aired more than
    three days after their slug date, and all four were re-surfaced stories.
- **MIT picked a symbol it already held.** Ep203 picked ENB.TO while the
  Ep201 ENB.TO position was still open. The pick prompt now lists the open
  positions and requires a different symbol.
- **Prediction Markets teaser.** It aired a week-old court filing that
  today's briefing never mentioned. The teaser now names a story from today's
  briefing (⚠️ AUDIO).
- **Top World intake line.** It told public readers that "no regional desk
  published today", which is a members-only product. With no desk in the
  intake there is now no line at all.
- **X teaser clipping.** `_build_teaser` clipped the hook with `[:199]` /
  `[:179]` slices outside `engine/titles.py`. It now uses `clip_words` with
  `X_TEASER_TEXT_MAX` / `X_TEASER_TWO_LINK_TEXT_MAX`.

### Corrections for the operator (not filed)

- **Unintended Consequences Ep145.** The episode recast Saddam's deliberate
  drainage of the marshes as a "response to scarcity". The queue's own
  SOURCE AUDIT note (`shows/topic_queues/unintended_consequences.yaml`)
  says the drainage was political.
- **First Principles Ep133.** Two facts are wrong:
  - The $80 set was the Model 60, in a wooden cabinet; the metal set was
    the Model 57, at $105.
  - The 12,000 workers figure is the 1929 peak, not 1927.

### Found and left for a later pass (verify before acting)

- Omni View conflated Flávio and Jair Bolsonaro.
- MIT's hook put US PPI on "Bank of Canada hike odds", and the show cited an
  unsourced "58% back-test". MIT's Saturday weekend mode never fires, because
  the prompt has no weekday variable; that is an operator decision.
- AI Chips' Teardown was built from a page that was never read.
- Prediction Markets' Board collapsed to one Manifold market.
- Vancouver aired betting lines.
- Hook figures were missing from the body: Top World's "100 percent" and
  MAG 7's "16,000".
- SpaceX's "factor of a million" is an arithmetic error.
- M&A aired a sidebar teaser as reporting.
- Whisper suffix-echo tokens appear in captions; this needs calibration.

## X — how the network posts today

- **@nerranetwork shows** (SpaceX, FF, Planetterrian, Omni View, M&A, MIT,
  UC):
  - The run queues one post in Supabase `x_post_queue`, carrying the 35 s hook
    Short as native video.
  - `x-queue.yml` posts it in a half-hour daytime slot; every queue run since
    Oct 11 is green.
  - Ten more shows start posting on `x_start_date: 2026-10-24`.
- **Tesla** posts a link teaser plus a cross-promo reply from
  @teslashortstime: two link posts a day, about $0.40/day at pay-per-use
  prices.
- **Nerra Daily** posts a cover image.
- **The Age of AI** posts a link and records no outcome.

Defects:
- **Fixed:** `x_posted` was set when the post was queued, not when it was
  posted. A queued post now also records `x_post_queued`, and the dashboard
  reports `x_queued_share_7d` beside `x_posted_share_7d`, so a hand-off is
  never read as a confirmed post.
- **Open:**
  - X spend is not in the cost rollup.
  - The reused Short carries YouTube calls to action onto X.
  - The Age of AI records no X outcome.

## Full episode videos on X

**Yes, without Premium**, for every show but two. The X API accepts video up
to 20 minutes and 8 GB without Premium, and up to 125 minutes and 16 GB with
it. Every run_show long-form fits under 20 minutes. Nerra Daily (2–3 h) does
not fit even with Premium. The Age of AI (40–50 min) needs Premium.

The design is a reply under the Short, not a second post:

1. `publishing.x_long_form: true` in the show YAML (pilot: SpaceX, FF, M&A,
   whose long-form MP4 is already uploaded to R2 for the video podcast feed
   or can be uploaded the same way).
2. run_show keeps the long-form MP4's R2 URL (`result["x_long_url"]`) before
   the render's cleanup deletes it, and enqueues a second row with
   `kind='long'`.
3. Supabase migration on `x_post_queue`:
   - adds `kind`, `parent_kind` and `subtitles_url`;
   - makes `(show_slug, episode_num, kind)` the unique key.
4. `post_x_queue.py` posts the long row as a reply to the Short's post once
   the Short is up. `engine/x_media.upload_media` gets a longer processing
   wait (about 900 s), and the WebVTT the feed already carries goes up
   through `/2/media/subtitles`. `x-queue.yml` gets a 30-minute timeout.
5. A nightly read-back writes `api/x_posts.json`, so the dashboard counts
   posts X confirmed.

Cost: a post with no URL is $0.015, so about $2.25 a month for the three
pilot shows. Effort: about 1–1.5 days.

Operator steps:
- Apply the Supabase migration.
- Keep the pay-per-use credit topped up.
- Turn on X's automated-account label for @nerranetwork.
- Decide on Premium only if The Age of AI should post in full.
