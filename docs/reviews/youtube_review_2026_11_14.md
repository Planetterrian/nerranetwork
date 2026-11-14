# YouTube and X review — what Nov 8 did, and the number nobody could see (2026-11-14)

Operator ask: a thorough review of the YouTube video pipeline and analytics,
and how to keep improving the videos and growing viewers and subscribers on
YouTube and X. Follows [`youtube_x_video_review_2026_11_08.md`](youtube_x_video_review_2026_11_08.md).
Read from `api/youtube_stats.json` (Nov 13 22:20 UTC, analytics through
Nov 11), `api/youtube_early_reach.json`, `api/youtube_policy.json` and the
metrics of every episode since Nov 9.

## 1. What the Nov 8 changes did

**They ship.** Across the 73 episodes with a long-form since Nov 9:

| Change | Fired |
|---|---|
| Subscribe pill on the long-form | 2 windows on 70 of 73; three Planetterrian episodes recorded none |
| "Coming up" card | 39 of 73 (none on UC/FPD, which have no map) |
| Clean X clip | `no_youtube_asks` on 50 of 73; the rest recorded no clip variant |

**One defect, fixed here.** The card's item cleaner dropped a leading
"first" ("First, X ..."), so Tesla's closing section rendered as
**"Principles"** on four long-forms (Nov 9, 11, 13, 14) and on 14 more maps
in the replay. A capitalised "First" before a capitalised word is now a
name, never a list word.

**Too early to score.** 17 EN long-forms published Nov 9-11 carry a
retention curve: median 0.78 at 10 s, 0.54 at 20 s, 0.42 at 30 s and 0.29
at 60 s, against 0.83 / 0.57 / 0.42 / 0.26 for the 67 published Oct 25 -
Nov 8. The samples are small and young; the readout stays Nov 29.
Subscribers per 1,000 EN views were 1.65 on Oct 29 - Nov 8 and 2.74 on Nov
9-11 (11 net in three days on 4,019 views). Encouraging, not yet evidence.

## 2. Where viewers and subscribers come from now (EN, 14 days)

| Kind | Videos | Views | Subscribers |
|---|---|---|---|
| Long-form | 118 | 7,794 | 16 |
| Short | 100 | 1,824 | 1 |
| RSS copy | 89 | 911 | 4 |

- **Browse is the channel.** "SUBSCRIBER" (home + subscriptions) is 300-2,000
  views a day, search 230-525, suggested 50-330, the Shorts feed 12-250.
- **EN Shorts reach almost no one.** The median EN Short has 3-7 views at
  two days old, against ~95 for the RU dubs of the same episodes. Only Tesla
  (median 31 at a week) and SpaceX (26) clear 20. The adaptive policy has
  already moved UC, FPD, Omni View, MAB and MIT to a weekly probe; it is
  working as designed and is left alone.
- **Long-forms convert by show:** subscribers per 1,000 views at age 7 over
  21 days are MAB 6.6, Models & Agents 3.2, FF 1.2, SpaceX 1.1, Tesla 0.6,
  zero on six shows. SpaceX, Tesla and M&A carry most of the views.
- **The RSS copies still take a tenth of the long-form views** (291 in 35
  days). Their Studio removal is the Nov 16 operator item.

## 3. The number nobody could see: impressions and click-through

Browse traffic is decided by whether the thumbnail and title are clicked
when YouTube shows them. The Analytics API has no impressions metric, so
since July every title, thumbnail and card change was judged on views,
which mix how often a video was shown with how often it was chosen.

**Shipped:** `scripts/fetch_youtube_reach.py` reads the YouTube Reporting
API's reach report (thumbnail impressions and CTR per video per day) into
`api/youtube_reach.json`, nightly. The first night creates a reporting job
per channel; YouTube writes the first report about two days later and does
not backfill, so data starts around Nov 16-17. Absent rows stay absent, a
CTR is printed only over 100 impressions, and every video is read at age 7
days. Register `youtube-reach-instrument-2026-11-14`.

With it, the next YouTube pass can test titles and thumbnails on the number
they actually move.

## 4. The "Coming up" card, wider

Besides "First Principles": a map closing on section names after "then"
("then Tools, Quick Hits, and the record"), "come in that order", "is/are
next", a bare "later" after a semicolon, and an over-long item split once at
"and a/an/the". Replay on the 308 mapped episodes since Oct 20: 239 cards
before, 250 after, every changed card read by eye.

## 5. X

The account locked three times this week, each within a minute of an
Unintended Consequences post; PR 1711 turned UC's X posts off and PR 1701
slowed posting after an unlock. Nothing reads X impressions or followers
back, and adding API reads to an account that locks on activity is the
wrong week for it. Recommended: let the posting fixes run a clean week, then
add a nightly read of the queued posts' public metrics (`api/x_posts.json`,
null when unread).

## 6. Open (operator)

- **End screens** on the long-forms (Studio only): suggested is the
  longest-watching traffic and end screens still send ~nothing.
- **Remove the RSS podcast copies** (Nov 16).
- **Concentrate EN Shorts?** The data says Tesla and SpaceX Shorts reach
  people and the rest do not; the policy is already cutting the weakest.
  No change proposed until the reach data shows whether they are shown and
  skipped or never shown.
