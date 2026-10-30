# YouTube review — the second EN Shorts step, and the map in the hook Short (2026-10-30)

Follows [`youtube_x_review_2026_10_24.md`](youtube_x_review_2026_10_24.md),
which explained the September fall (a Shorts-feed distribution change on Sep
15-16 that hit @NerraRU hardest; EN a faded breakout). This pass reads the
data through Oct 27 (Analytics lags two days) from the 123 stored snapshots
of `api/youtube_stats.json` (`git log`, one per day), `api/youtube_early_reach.json`,
the committed transcripts and the per-episode metrics.

## TL;DR

1. **28 days to Oct 27 against the 28 before:** EN views 38.8k vs 53.9k
   (−28%), RU 30.5k vs 59.4k (−49%), FR 9.7k vs 10.5k (−7%). Subscribers
   gained EN 81 vs 97, RU 35 vs 63, FR 20 vs 27. The subscriber COUNT is
   still rising on all three channels (EN 545, RU 260, FR 78); gains have
   slowed (EN ~25 a week in September, 10-15 in late October).
2. **RU is the September step, unchanged** (Shorts-feed traffic about a
   quarter of August's; reach per RU Short at day 3 is recovering: median 42
   → 101 over the last three weeks). Nothing new to fix there in the pipeline.
3. **EN took a second, separate step on Oct 19-20, on Shorts only.**
   EN Shorts-feed views fell from ~220 a day (Oct 12-18) to ~90 (Oct 19-27);
   reach per EN Short at day 3 fell from a median 15-16 to 8.5. The
   flagships fell hardest: Tesla 87 → 26, SpaceX 55 → 13, FF 29 → 7 (median
   day-3 views, Oct 12-18 vs Oct 19-26). EN long-form reach did not move, and
   EN long-forms now carry the channel (22.2k views and 28 subscribers since
   Sep 29 against 7.9k and 10 for Shorts).
4. **What changed on Oct 20 is inside the Short.** Since Oct 20 every English
   opening is hook → identity line → *the map* (one sentence listing the
   other stories). The hook Short is a clip of that opening, so ~9 s of a
   ~32 s Short became a list of OTHER stories ("Intel's new process node,
   Japan's self-driving filing, testing, Rivian's point-to-point assist,
   then first principles…"). At the same age (5 days), Shorts published
   after Oct 20 hold viewers for less on every channel: EN 16.0 → 13.5 s and
   46.5 → 41.7%, FR 16 → 13 s and 46.8 → 37.5%, RU 19 → 17 s and 55 → 49%.
5. **Fixed here (render only):** the hook Short is now cut from a spliced
   copy of the mix and transcript with the map removed
   (`engine/short_furniture.py`, `youtube.shorts_skip_map`). The episode,
   its feed audio and its long-form keep the map. Replay: 128 of the 176
   English episodes since Oct 20 get the cut (median 8.7 s); 0 of the 379
   episodes before Oct 20 would have been touched.

## 1. Where the views went (weekly, Monday weeks)

| Week | EN views | EN subs | RU views | RU subs | FR views | FR subs |
|---|---|---|---|---|---|---|
| Aug 3 | 8,629 | 26 | 33,845 | 29 | 1,393 | 7 |
| Aug 31 | 19,379 | 30 | 23,900 | 27 | 3,280 | 8 |
| Sep 14 | 8,754 | 15 | 11,205 | 12 | 2,565 | 4 |
| Sep 28 | 12,061 | 23 | 5,421 | 1 | 1,487 | 3 |
| Oct 5 | 8,844 | 23 | 7,792 | 9 | 2,292 | 4 |
| Oct 12 | 9,523 | 22 | 8,296 | 10 | 2,283 | 6 |
| Oct 19 | 7,048 | 12 | 7,468 | 10 | 3,113 | 4 |

EN traffic by source, daily average:

| | Shorts feed | Subscribers | Search | Suggested |
|---|---|---|---|---|
| Oct 12-18 | 219 | 617 | 331 | 123 |
| Oct 19-24 | 84 | 359 | 249 | 66 |
| Oct 25-27 | 104 | 1,604 | 307 | 117 |

The Oct 25-27 jump in subscriber-sourced views is one video: SpaceX's Oct 24
long-form "Starship Cabin Images Advance Dual 2028 Lunar Landings" (2,735
views, the network's best in 90 days). A topic, not a pipeline change.

## 2. Ruled out

- **Upload failures.** Every EN show uploaded its planned Short and long on
  every day Oct 19-30 (metrics); captions, end card, punch frame and fact
  cards rendered as before.
- **Retention on the flagships.** Tesla/SpaceX/FF Shorts held 19-20 s at
  age 5 before and after; the retention loss is in the other shows' Shorts.
- **The 7:00 ET schedule.** Since Oct 19 the EN Shorts go public 7:00-9:15
  ET; RU/FR were not moved and did not fall. But Oct 23, the one recent day
  the EN Shorts were not scheduled, had a median of 3 views at day 3 — no
  better than the scheduled days. Not the cause on this evidence.
- **The video job (Oct 19).** Same windows, same render metrics, same
  metadata in the video index.

What cannot be separated: a YouTube-side change to the EN Shorts feed in the
same week. The map is the one change inside the Short, it measurably cut
watch time on all three channels, and it costs nothing to remove from the
clip.

## 3. Fixed here

- `engine/short_furniture.py`: finds the map in the committed script (the
  line after the identity line that lists what comes next — a sequencing word
  and a list comma, never an attribution or a continuation), locates it in
  the Whisper words, splices it out of a copy of the mix (30 ms fades, FLAC)
  and of the transcript, so captions, fact cards, sentence-snapped cuts and
  the clip read one timeline. Any failure renders the Short as before.
- `run_show.py`: the hook Short (Short #1, `hook_open`) renders from that
  source; metric `shorts_map_cut_s`.
- `youtube.shorts_skip_map` (dataclass `False`, `_defaults.yaml` `true`).
- Guards: `tests/test_short_skips_map_2026_10_30.py`.

## 4. Operator decisions

- **The dub Shorts carry the map too** (RU/FR retention fell with it). The
  same cut needs a dub-language locator: the transcript matcher reads ASCII
  only, so the dubs would locate the map by sentence count against the
  line-aligned `.ru.txt` / `.fr.txt` and check the span's letters against the
  translated line. Not shipped here because no committed dub transcript has
  word timings to test it on; the next multilingual sweep's Whisper JSON is
  the test set.
- **The dead-Shorts tier is now reading a channel-wide slump as six weak
  shows.** Since Oct 24-28 FF (median 9), Models & Agents (8.5), Omni View (7),
  First Principles (5), MAB and MIT ship one Short a week, because their
  hook Short's day-3 median fell under the absolute floor of 10 — set on Sep
  22 when the channel's typical median was 20-40. The tier's original reason
  (24 EN uploads a day against a ~30 cadence ceiling) no longer binds: EN now
  uploads ~14 a day. Options: hold the tier until two weeks of map-free
  Shorts are measured, or make the floor relative (under half the channel's
  own hook-Short median). `scripts/update_youtube_policy.py`.
- **Still open from Oct 24:** the funnel-tagged YouTube link under the X
  Short, MIT's four disclaimer sentences before the first story, per-show
  playlists flagged in Studio.

## 5. Scoring

Register `shorts-skip-map-2026-10-30`, readout 2026-11-13: EN hook-Short
median views at day 3 (baseline 8.5, week of Oct 19) and average view
duration at age 5 (baseline 13.5 s), from `api/youtube_early_reach.json` and
the stored snapshots, read against RU/FR (still carrying the map) as the
control.
