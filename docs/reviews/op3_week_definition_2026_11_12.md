# What an OP3 "week" is (Nov 12 2026)

Operator-directed: check how OP3 defines its weekly buckets, then correct
the reading everywhere. Owner module `engine/op3_weeks.py`; guards
`tests/test_op3_weeks_2026_11_12.py`.

## The question

`api/op3_stats.json` carries, per show, `weekly_downloads`: four numbers,
oldest first, and an `asof` date. Since Sep 12 2026 every surface read the
newest of the four as the calendar week in progress ("partial, never
compared"), so week over week was the second-newest against the
third-newest. On Nov 10 that printed -16.9% on the sponsor view while the
newest number was the highest of the four.

## What OP3's documentation says

`https://op3.dev/api/docs`, `/queries/show-download-counts`:
`weeklyDownloads` is "non-bot downloads per week over the last four weeks
(ascending in time)"; `numWeeks` is "number of recent weeks with full data
on OP3". `asof` is not defined. Nothing says calendar weeks, and nothing
says the newest entry is in progress.

## What the nightly files say

Network sums of `weekly_downloads` on 29 consecutive nightly commits of
`api/op3_stats.json`. `asof` is the day before the fetch.

| Fetched | asof | w-3 | w-2 | w-1 | w0 |
|---|---|---|---|---|---|
| Oct 22 | Wed Oct 21 | 1942 | 3013 | 4651 | 3881 |
| Oct 29 | Wed Oct 28 | 3013 | 4651 | 3861 | 2977 |
| Nov 5 | Wed Nov 4 | 4651 | 3861 | 2977 | 3685 |
| Nov 12 | Wed Nov 11 | 3861 | 2977 | 3687 | 4160 |
| Oct 18 | Sat Oct 17 | 1800 | 2890 | 3114 | 4068 |
| Oct 25 | Sat Oct 24 | 2890 | 3114 | 4078 | 3783 |
| Nov 1 | Sat Oct 31 | 3114 | 4078 | 3808 | 2969 |
| Nov 8 | Sat Nov 7 | 4078 | 3808 | 2969 | 4260 |

1. **Every one of the four numbers changes every night.** A calendar week
   that has ended would stand still.
2. **Each night's series reappears seven nights later, one place to the
   left.** The same seven days, named one window older. (A window grows by
   under 1% over the following week as OP3 processes late requests: 3783
   became 3808, 4068 became 4078.)
3. **Two fetches with the same `asof` are identical** (Oct 19 and Oct 20,
   both asof Oct 18), so the series is a function of `asof`, not of the
   clock.
4. **The data runs through the end of the `asof` day.** In all 145
   show-fetches checked (five daily shows, 29 nights), the episode
   published on the `asof` day was already listed with downloads, and no
   episode published after `asof` ever was, though the fetch ran about
   fourteen hours after the next day's episode came out.

So `weeklyDownloads` are four back-to-back trailing seven-day windows, the
newest ending on `asof`, every one complete. The live API could not be
queried from this session (the host is not on the network allowlist); the
conclusion rests on the documentation and the committed files.

## What was wrong

| Surface | Was | Now |
|---|---|---|
| Audience headline `wow_pct`, `last_week`, `prior_week` (and everything that reads them: the front-page tile, the media kit stat, Mission Control's tiles, the review snapshot, the audience contract) | second-newest window against third-newest: the week before last | newest against second-newest; `week_ending` names the day |
| The ledger `api/op3_history.json` | all four windows written every night under the Monday of the fetch date: the newest four "weeks" changed nightly, overlapped the frozen week before them by up to six days, and the all-time total counted those days twice | written only on the night `asof` is a Saturday; weeks run Sunday to Saturday, keyed by the Monday inside them |
| All-time downloads | sum of the ledger including the overlap (42,049 on Nov 12) | whole weeks through the last Saturday on file (38,401 through Nov 7); `all_time_through` says so |
| Growth panel and media kit charts | skipped the newest key, charted three misaligned ones | every week on file is whole and is charted |

Figures on Nov 12: week over week +12.8% (3,687 to 4,160) where the old
rule printed +23.8% (2,977 to 3,687). Two days earlier the old rule printed
-16.9% where the newest window against the one before was +56.5% (2,989 to
4,678).

## The ledger repair

The frozen weeks were already Sunday to Saturday windows, because a week's
last write under the old rule was the Sunday fetch (asof Saturday). Only
the newest four keys were misaligned. Keys 2026-10-19, 10-26 and 11-02 were
restored per show from the Sunday Nov 8 fetch (commit `a174ffee1`): 3,808,
2,969 and 4,260. Key 2026-11-09 was removed; the Sunday Nov 15 fetch writes
it. 2026-10-12 was already that fetch's value (4,078).

## Read with care

* In the window ending Nov 9 several shows read three to ten times their
  previous window (MAG 7 12 to 122, AI Chips 24 to 134, Modern Investing
  92 to 398, Prediction Markets 18 to 76), and MAG 7 and AI Chips were
  still high in the window ending Nov 11. Whether that is the ad burst of
  that week, a crawler OP3 does not filter, or new listeners is not
  established here; a rolling week over week moves with a few such days.
* A rolling seven-day comparison changes every night. The four-week
  average on Mission Control's growth panel is the steadier figure, and it
  stays the headline for sponsors.
* Every `wow_pct` quoted in a review before Nov 12 described the week
  before last.
