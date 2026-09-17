# YouTube pipeline, workflow and audience review — 2026-09-17

Operator brief: full review of the YouTube pipeline, workflow, performance
statistics, viewers and subscribers, and a comparison against model
updates or other improvements that could keep the channel growing.
Window: the four slates since the Sep 13 readout (09-14..09-17, 46
episodes), analytics through 09-15 (the last healthy snapshot — see §2),
the age-matched reach file, the Actions run history, and the xAI model
catalogue as published today.

## 1. Verdict

The factory is healthy: 46 of 46 episodes published, no watchdog fires,
no skips, the finalize job runs in ~80 s instead of 39 minutes. The
**measurement layer had a silent failure** on 09-16 that this PR fixes.
Audience is up on the honest numbers (EN views +32% week over week on
complete days, +27 net subscribers; RU flat at +0.7% and +20; FR +24%
and +8), while the **age-matched reach of the newest non-flagship EN
Shorts is down 45-60%** against the week before the Sep 9 changes, and
RSS downloads fell 15% in the last complete week. The x264 trial
measured nothing and is closed. No text-model update is available to
move to; one image model is.

## 2. The 09-16 analytics snapshot was a partial fetch, and it overwrote the good one

The YouTube Analytics API answered **HTTP 500** to 13 of the per-video
batch queries and to the 30-day day-series query on all three channels
during the 09-16 nightly (25 seconds of "An internal error has
occurred"). `fetch_youtube_analytics.py` treats every query failure as
an empty result, `any_data` was true from the batches that succeeded,
and the step is `|| true` — so a file with **927 of 2,753 videos, six of
17 shows, and no day series** replaced the healthy 09-15 file and the
step reported success.

What read it: `update_youtube_policy.py` (every show but three went to
`video_count_14d: 0`, `short_vpd: null`), the dashboard scorecard (views
0, `zero_view_share` 0.79 on EN — the FR-launch early warning, on every
channel), `channel_views_wow_en` (null on the register), the audience
headline and the early-reach tracker (+35 observations from a partial
file; the values were real for the videos it had, so nothing was
poisoned, only skipped). The 36-hour freshness alert never fired because
the file was fresh.

Fixed in this PR, three layers:

- **Retry 5xx, never 403** (`_execute_with_retry`, 2 s then 5 s) on the
  batch and day-series queries; failed queries are counted into
  `payload["degraded"]`.
- **Refuse to overwrite a clean file** (`snapshot_regression`): failed
  queries against a clean committed file, fewer than 60% of the
  committed videos, or a channel that lost its day series → `::error::`
  and the file stays as committed. A degraded file may still be replaced
  by a better one, so the fetch can recover on its own.
- **The early-reach tracker skips a degraded snapshot** (first
  observation wins, so a partial one would freeze).

Also in this PR: `api/youtube_stats.json` is restored to the 09-15
snapshot and `api/youtube_policy.json` regenerated from it, so the
dashboard is honest until tonight's fetch. Tonight's nightly, if the API
is healthy, writes a fuller file over it; if not, it refuses and says so.

## 3. Audience: what the honest numbers say

**Channels** (scorecard, last 7 complete analytics days vs the 7 before):

| Channel | Views 7d | WoW | Net subs 7d (prior) | Subscribers | Views/video 14d short · long |
|---|---|---|---|---|---|
| @NerraNetwork | 20,319 | +32% | +27 (+21) | 434 | 54 · 117 |
| @NerraRU | 21,264 | +0.7% | +20 (+25) | 211 | 308 · 14 |
| @NerraFR | 3,423 | +24% | +8 (+6) | 52 | 68 · 50 |

EN daily views since the 09-06 peak: 4,077 → 3,012 → 2,535 → 2,313 →
1,997 → 2,169 → 2,382 → 2,143 (09-13). The week-over-week gain is the
breakout week of 09-04..06 rolling out of the prior window, not a new
climb — the daily run rate is ~2,100-2,400, half the peak days.

**Subscriber sources, 28 days:** EN long 43 subs (25,186 views), EN
Shorts 39 (19,143), RU Shorts 58 (68,435), FR Shorts 30 (11,400), RU
long 3, FR long 3. EN long-form remains the best subscriber converter
per view on the network (1 per 586 views vs 1 per 1,180 on RU Shorts).

**RSS (audience headline):** last complete week 1,352 downloads, −14.9%
against 1,588; this week 1,430 so far. First-week downloads per episode:
SpaceX 69, Tesla 27, M&A 20. Newsletter: 5 subscribers.

**Retention (28d, views-weighted):** Shorts 75%, long 15%.

**Age-matched reach** — median views at snapshot age 3, EN, week
09-03..09-07 (before the Sep 9 changes) vs 09-10..09-14 (after; all
from healthy snapshots):

| Show | Shorts before → after | Long before → after |
|---|---|---|
| Tesla | 18 → 76 | 110 → 25 |
| SpaceX | 8 → 14 | 83 → 40 |
| Fascinating Frontiers | 8 → 75 | 15 → 8 |
| Models & Agents | 32 → 12 | 55 → 53 |
| MAB | 38 → 44 | 44 → 79 |
| Modern Investing | 15 → 8 | 9 → 18 |
| Omni View | 26 → 4 | 12 → 5 |
| Planetterrian | 44 → 8 | — |
| First Principles | 44 → 12 | — |
| DP Pod | 47 → 4 | — |
| Unintended Consequences | 20 → 26 | — |

EN Shorts overall by weekday at age 3: Thu 28 → 19, Fri 19 → 11, Sat 32
→ 13, Sun 52 → 21. The flagships with fact cards and the strongest hooks
(Tesla, FF) went up; the mid-tier shows went down by two thirds. Two
things changed in that window for every show: the Sep 9 render items
(subscribe end card, fresh open, fact cards on three shows) and the Sep
12 simplification (strip on every show, the rewrite gate gone). The
end-card and open changes are the same on Tesla and Omni View, so they
do not explain a split by show; what differs by show is the spoken
opening the hook Short is cut from. **Read: the softening tracks the
script, not the render.** `short_subs_per_video_14d_en` reads 0.092
against the 0.11 baseline of the subscribe-CTA experiment.

**The second EN Short is dead weight.** By window, EN Shorts published
08-19..09-13:

| Window | Shorts | Views | Median | Subs | Age-7 median |
|---|---|---|---|---|---|
| hook_open (1st Short) | 269 | 17,697 | 22 | 34 | 37 |
| qualified (2nd, smart window) | 60 | 908 | 6 | 2 | 5 |
| filled (retired 09-09) | 65 | 538 | 5 | 3 | 4 |

The `qualified` second Short earns what the `filled` one did before it
was retired. It is 60 of ~340 EN uploads a month for 5% of Shorts views
and 2 subscribers, on a channel already near the 30-uploads-a-day
cadence warning. **Recommendation (not shipped — a supply decision):
drop the EN channel to one Short per episode** (`shorts_for_vpd` band
or `shorts_per_episode` on the EN path only; RU/FR filled Shorts earn
~200 and stay). The saved render time is a side benefit.

## 4. Pipeline

**Renders.** 30 long-form renders under x264 `faster`: per-day medians
957 / 947 / 835 / 920 s, overall 932 s, spread 503-1,216 s — the
1,024 s `medium` baseline within noise. The preset reached the runner
(`NERRA_X264_PRESET: faster` in the step env); the encoder is not where
the time goes. **Trial closed, reverted to `medium`** (register entry
`x264-preset-faster-2026-09-13`, outcome NO EFFECT). The cost is the
36-branch, 2×-supersampled zoompan graph. The supersample is a measured
judder guard, so the next lever is a benchmark of branch count and
`filter_threads`, not another preset.

**Combined generation, four days:** 1 `combined` (env_intel), 4
`combined_stale` (M&A three days running, Offshore North), 41
`two_pass`. M&A's script was discarded every day at a 0.3-0.5 forward
line share — run_show's trims (section dedupe, scaffold scrub, claim
strip) remove lines from the stash digest, and the check only looked
forward. **Fixed:** `combined_script_matches_digest` now also accepts a
digest whose own lines are all in the stash (a trim), still rejects a
replacement (both shares low), and the discard warning logs both shares.
Expect M&A to ship `combined` from tomorrow; the seven chained flagships
and the three grok-4.6 script shows are still excluded by design.

**Strip mode, four days:** 19 sentences removed on 16 of 46 episodes
(PT four days running, OV, MIT, FF, dp_pod, M&A once). Every one was an
unreachable source; none a fabrication. Still the designed trade.

**Wall time** now reads 1,200-2,100 s per episode with the render
counted once (MAB 09-16 was the longest at 2,085 s).

**Dub price line:** clean since the 09-13 fix — none of the RU/FR Shorts
on 09-14..09-17 opens on the quote. Garbled Whisper-fragment titles on
RU filled Shorts remain (a title-source item, not a reach item).

## 5. Workflow

- Every run-show, multilingual and nightly run since 09-14 succeeded
  (60 of 60 run-show runs; the only red nightly is the 09-13 dispatch
  during the books test break).
- Finalize's "Regenerate shared pages" holds at 80-90 s (was 38 min).
- The nightly's analytics step needs the guard above; the `|| true` is
  correct (never block the dashboard build) once the refusal is loud.

## 6. Model updates, checked against the catalogue today

Read from docs.x.ai (models + release notes) and the September coverage:

- **Text: Grok 4.6 (Aug 12) is still the newest.** Grok 4.7 was
  promised for ~Sep 12 and has not shipped; no model id, pricing or card
  exists. Grok 4.8 is in training. Nothing to move to. The network's
  stance stands: digests/fetch on grok-4.3 (4.6 digest latency ran 5-10×
  on 08-18), 4.6 on dp_pod's script stage and the synth/reviewer
  stages. The staged playbook applies to 4.7 when it lands: one show
  first, digest-latency gate, never a network flip.
- **Images: `grok-imagine-image-2.0` at $0.04** now sits between the
  network's `grok-imagine-image` ($0.02, every scene) and `-quality`
  ($0.05, book art). **`grok-imagine-image-quality` retires on Nov 2**
  and its slug is routed to 2.0 at the lower price. `engine/book_art.py`
  pins `-quality` deliberately (never a floating alias) — the operator
  should re-pin the book art to `grok-imagine-image-2.0` before Nov 2 on
  a build they eyeball, so the routing never changes cover art
  unannounced. For the video scenes, 2.0 is the candidate for an A/B on
  age-matched reach (one show, 13 images × $0.02 extra ≈ $0.26/episode),
  not a blanket switch: Tesla/FF reach rose on the current model.
- **Video: `grok-imagine-video-1.5`** ($0.08/s; 25 s for a 6 s 720p
  clip). A 35 s Short fully in generated video is ~$2.80; the Shorts
  motion A/B on the older model froze at n=4 and read nothing. No case.
- **Voice: TTS is $15/1M chars** (tracking's 0.015/1k matches); voice
  cloning now spans TTS and the Voice Agent API; `grok-voice-think-fast-2.0`
  is the agent model (Age of AI's domain, not run_show's). No TTS model
  parameter exists, so spot-listen after xAI voice announcements stays
  the rule.

## 7. What to change next, ranked

1. **Merge this PR** — the snapshot guard is the one item that stops a
   repeat of a day of false zeros.
2. **One Short per episode on EN** (operator decision, §3).
3. **Read the reach split by show against the spoken openings** — the
   mid-tier softening began when the scripts changed, not the renders.
   The Sep 17 readout of the content-discipline experiment
   (`network-content-discipline-2026-09`, due 09-26) should be scored
   on `short_reach_d3_median_en_7d` per show alongside the script
   metrics, and the chained-flagship/combined-generation decision from
   the Sep 13 readout is still open.
4. **Re-pin book art to `grok-imagine-image-2.0` before Nov 2** and run
   one show's scenes on it as an A/B.
5. **Benchmark the filter graph** (branch count, `filter_threads`)
   before touching render time again.

## 8. Reading table

| Question | Where | When |
|---|---|---|
| Did tonight's fetch write or refuse | nightly log: `Wrote api/youtube_stats.json` vs `::error::…REFUSED` | 09-18 |
| M&A ships `combined` | `combined_generation` counter | 09-18 |
| 2nd EN Short at age 7 | early reach file, `window == qualified` | weekly |
| Reach vs spoken openings | `short_reach_d3_median_en_7d` per show + `script_*` counters | 09-26 readout |
| Book art on image-2.0 | `books/` build, eyeball | before 11-02 |
