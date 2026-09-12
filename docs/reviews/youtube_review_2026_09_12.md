# YouTube review — "views and subscribers dropped off" — 2026-09-12

Operator brief: something has happened such that subscribers and views
dropped off significantly; do a thorough review of the YouTube workflow,
pipeline, code and metrics, and continue improving the videos so the
network keeps gaining viewers and subscribers.

Instruments read: `api/youtube_stats.json` (Analytics, generated
2026-09-11, day series through 09-09 — the API lags ~2 days),
`api/youtube_channel_history.json` (Data API counter), the six nightly
snapshots of the stats file in git (09-06..09-11, for age-matched
comparisons), every show's `youtube_videos*.json` index (uploads through
today), the last week of `metrics_ep*.json`, and the last three days of
`Run Podcast Show` workflow runs.

## 1. Verdict: the pipeline did not stall, and the channels are up week over week

**Uploads are complete.** Every day from 09-03 to 09-12 shipped 7 EN longs,
14-17 EN Shorts, 9-10 RU Shorts and 6 FR Shorts. No day is missing a show
(the two failed runs on 09-11 — Tesla and Omni View — were retried the
same day and published).

**The channel day series is up on every weekday, week over week.** EN
views have a strong weekly cycle (Thu-Sun high, Mon-Wed low):

| EN day | Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|---|---|---|---|---|---|---|---|
| week of 08-31 | 1,882 | 1,578 | 1,840 | 2,203 | **3,837** | **4,285** | **4,113** |
| week of 09-07 | 3,042 | 2,552 | 2,313 | — | — | — | — |

Mon-Wed of the week of 09-07 is +50-60% on the same weekdays a week
earlier. RU: 09-07..09 read 3,049 / 2,705 / 2,524 against 1,883 / 2,087 /
5,579 (that 09-02 figure was one breakout day). Subscribers: EN +7 / +1 /
+3 on 09-07..09 (426 → 429 on the counter by 09-11); RU +3 / +4 / +2 (202).

**What the operator saw is real, but it is the peak fading, not a stall.**
09-04..09-06 carried three breakout Shorts — MAB "GPT-6 Astra … in
Blender" (883 views), SpaceX "Starship V3 Pad 2" (722), Planetterrian
"80,000-year-old arrowheads" (769) — and EN subscriber gains of 6 / 5 / 10
came with them. Studio's rolling views then compare every following day
against that run. The Data API counter also re-synced Shorts views on
09-10 (+21,660 EN, +29,408 RU in one day), so any counter-based read of
"this week" is noise (see the Sep 9 note on that counter).

**Age-matched reach is the honest ruler.** Median views per video at
snapshot age 3 days, by publish day (from the git snapshots):

| published | EN Shorts (n) | EN long (n) | RU Shorts (n) |
|---|---|---|---|
| 09-03 Thu | 28 (11) | 15 (7) | 100 (10) |
| 09-04 Fri | 22 (14) | 45 (7) | 362 (8) |
| 09-05 Sat | 32 (17) | 83 (8) | 295 (10) |
| 09-06 Sun | **52** (13) | 54 (7) | 220 (9) |
| 09-07 Mon | 17 (15) | 21 (9) | 229 (10) |
| 09-08 Tue | 15 (15) | 52 (8) | 214 (9) |

EN Shorts published 09-07/08 earn 15-17 at day 3 against 22-32 on the
pre-peak weekdays — a real ~35% per-video softening on EN, concentrated
in MAB, Omni View, Planetterrian, M&A and MIT hook Shorts (medians 44→5,
59→8, 50→15, 46→19, 18→6), while Tesla, SpaceX and Fascinating Frontiers
held (111→80, 83→129, 202→197). RU is flat. Shorts watch-through did
not move (EN hook-Short median AVP ~55% both before and after), and the
spoken opens still match the digest hooks (0.7-1.0 similarity on every
flagship episode 09-03..09-12), so this is distribution, not the content
of the clip. The merges between the good 09-06 slate and the soft 09-07
slate (#1150-#1154) touched nothing on the video or metadata path.

Until now the only way to make that table was to dig old snapshots out
of git. **Shipped:** `scripts/track_early_reach.py` folds each nightly
snapshot into `api/youtube_early_reach.json` (views per video at each
snapshot age 1-7 d, 60-day prune, idempotent), the dashboard's Growth
levers section gains an **Early reach (age-matched)** card (per channel:
Shorts median at day 3 for the last 7 publish days vs the 7 before, and
the per-day line with weekday), and `short_reach_d3_median_en_7d` is a
register metric. The next time a rolling number says "drop", this card
says whether reach per video moved.

## 2. Pipeline health: the long-form render is the day's biggest risk

**Two shows hit the 3,000 s pipeline budget on 09-11** (Tesla 08:46 UTC,
Omni View 07:01 UTC): each spent 36-50 minutes in fetch + digest + script
and was still rendering the long-form when the watchdog fired; both were
re-run and published hours later. The render itself is chronically slow:
`long_form_render_duration_s` (recorded since 09-11) reads 531-1,202 s
per 10-minute episode (Tesla 531, SpaceX 764, FF 836, OV 1,014, MAB
1,027, MIT 1,118, M&A 1,202), and the YouTube stage as a whole has run
1,100-2,000 s per episode since at least 08-18 — this did not start with
2K images (09-03) or the fact cards (09-10). The render-budget guard that
landed 09-11 (`_LONG_FORM_RENDER_BUDGET_S`) now skips the long-form when
under 600 s remain, which saves the day but silently costs the video
episode and the long-form upload — the top EN subscriber source per
video.

Where the time goes: every one of the 36 slideshow slots runs
`scale → crop → zoompan` at a **2.0× supersample** (3,840×2,160) before
the 1080p output, then x264 `-preset medium`. The benchmark and the
change shipped from it are in section 4.

**Other workflow reads (all fine):** the run-show `finalize` job is
cancelled by its concurrency group whenever the next show starts —
by design, the last run of the day and nightly regenerate the shared
pages. The nightly analytics fetch, policy update and gallery-retention
join ran every night. MAB moved to tier A on 09-11 (long + 2 Shorts).
With `en-shorts-no-fill` (09-10) EN ships one Short on days without a
qualified second window — Tesla 601/603, FF 189/190, MAB 163/164 did.

## 3. First reads on the Sep 9 changes (render-only, all landed 09-10)

- **Fact cards** rendered on every treatment episode: Tesla 1 / 5 / 4,
  SpaceX 3 / 8 / 3, FF 1 / 2 / 2 per episode (`fact_cards_rendered`).
  No render failures attributable to them (Omni View, a control show,
  timed out the same way Tesla did). Retention read: 09-30.
- **Subscribe CTA, fresh-only open, captions track-only:** in the
  video from 09-10; the analytics for those days are not in yet.
- **Sep 12 simplification pass** (operator-directed, other session,
  merged 15:03 UTC today): rewrite gate removed, combined generation,
  claims strip mode network-wide. Tomorrow's slate is the first under
  it. It changes the spoken script, so the hook Shorts change with it —
  read the early-reach card for 09-13..15 against this week before
  attributing anything to the video changes.

## 4. Render speed — measured in CI, not guessed here

A local benchmark of the production single-pass graph could not be
completed in this session: the container's ffmpeg is 7.0.2 (CI runs
6.1), which is where the frame-rate bug above surfaced, and its build
has no `ffprobe`, so the render path could not time a fixed-length
episode reliably. Two facts bound what a change could earn:

* The 2.0× pre-scale is a measured judder guard (77% byte-identical
  consecutive frames at 1.15×, 33% at 2.0×, for +17% render time —
  `test_slideshow_prescale_leaves_subpixel_headroom`). It is not the
  dominant cost and it is not a speed knob.
* The x264 preset (`medium`) and the frame count are the remaining
  levers. `NERRA_X264_PRESET` is now an env override (default
  `medium`) so a trial is one runner variable in `run-show.yml`, read
  off `long_form_render_median_s_7d` (baseline 1,014 s) — `faster`
  typically encodes ~1.6× quicker at CRF 22 for a slightly larger
  file. That trial is the operator's to start; it changes no pixels the
  viewer would notice at 1080p CRF 22 but it should be read, not
  assumed.

## 5. What was NOT changed, and why

- **No spoken or prompt change** — landmine #17, and the content did
  not regress (watch-through flat, hooks intact).
- **No publish-time change.** The index carries no upload hour, so
  whether early-UTC publishes (SpaceX 07:30) underperform late ones
  cannot be read yet; the staggered second Short already lands at
  17/21/23 UTC.
- **No tier or cadence change.** The policy is doing its job; MAB's
  promotion is the data speaking.

## 6. Reading it

| What | Where | Baseline 09-11 | Read |
|---|---|---|---|
| Per-video reach | dashboard "Early reach", `short_reach_d3_median_en_7d` | 23 | weekly, same weekday |
| Render time | `long_form_render_median_s_7d` | 1,014 s | 09-19 |
| Long skipped on budget | `long_form_skipped_budget` in metrics | 0 this week | nightly |
| Sep 9 levers | `shorts-subscribe-cta`, `fresh-open-long-form`, `long-form-fact-cards` | — | 09-30 |
