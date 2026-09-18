# YouTube pipeline — 24-hour read and improvement plan (2026-09-18)

Operator brief: fix the caption-track metric and retry, review the
experiments the dashboard flags as past readout, and plan the next
pipeline improvements from what the data says. Window: the Sep 18 slate
(the first on main after PR #1220 and the Sep 17 fixes), the Sep 17
nightly analytics run, the age-matched reach file through 09-15, and
the committed MIT tracker and trade signals.

## 1. The last 24 hours, in numbers

All 11 run_show episodes published, no skips, no watchdog fires, the
spoken-text gate passed on the first attempt on every show, Nerra Daily
Ep029 assembled all 11 segments on frame-anchored cuts. Quota preflight
read 43,100 EN units against 200,000.

| Channel | Long-form | Shorts |
|---|---|---|
| @NerraNetwork | 7 | 15 |
| @NerraRU | 1 | 8 |
| @NerraFR | 1 | 6 |

- Tiers held: A on Tesla, SpaceX, FF, M&A, MAB; B on Omni View and
  MIT; C on Planetterrian, UC, FPD (long skipped by policy).
- The second Short on Tesla, SpaceX and M&A uploaded as scheduled for
  17:00 UTC; ten funnel comments queued for when they go public.
- FF, MAB and Planetterrian shipped one of two requested Shorts: the
  Sep 9 no-fill rule, working as designed.
- Long-form render median 1,059 s over 7 renders (MIT 1,633 s max) on
  the restored `medium` preset; 920 s the day before. Noise.

How PR #1220's items landed:

- Snapshot guard: the 09-17 nightly fetched 2,826 videos across 14
  shows with no retries and no degraded queries; full day series on all
  three channels. The guard had nothing to refuse and the 09-16 hole is
  gone. Early reach folded 228 observations; the policy regenerated
  from real velocities.
- x264 trial: `NERRA_X264_PRESET: medium` confirmed in every run log.
- Nerra Daily `cut_anchor`: recorded on Ep029.
- Combined-generation stash acceptance: did not rescue the flagships.
  Combined engaged on 2 of 11 shows (M&A, MIT). Tesla and SpaceX
  discarded their PART 2 because the digest was regenerated after the
  call (50% and 28% of the stash's lines survived); FF's PART 2 came in
  under the 1,122-word band twice; Planetterrian Ep187 was stale too.

Audience, through 09-15 (the newest complete analytics day): that day
was low on both large channels while FR held — EN 1,288 views against
2,313 the prior Tuesday, RU 1,254 against 2,524 — and the RU day-series
alarm fired at 50%. RU dubs took none of the EN render changes, so a
same-day dip on both reads as platform traffic. Age-matched reach says
the 09-14 slate was the weakest publish day on record for EN and RU
together (EN hook Shorts 14.5 median views at day 3 against 19–26 the
prior week; EN long 6.5 against 12–42; RU Shorts 68.5 against 95–216).
Subscribers keep climbing: EN 435, RU 210, FR 51.

## 2. Defect found and fixed: the caption track

Omni View Ep179's long-form shipped with no captions. `captions.insert`
answered HTTP 403 once; six sibling long-forms on the same channel token
uploaded their tracks within the hour, so it was a transient, not a
scope problem — but the warning said "likely missing youtube.force-ssl
scope", there was no retry, and `caption_track_uploaded` had been set
on the publish result since July without ever being on the
`record_youtube_outcomes` allowlist. No episode has ever recorded a
refusal. Since Sep 9 the uploaded track is the only caption layer on
long-form, so a refusal is a captionless video.

Shipped:

- `engine.youtube.upload_caption_track_detailed` returns `(ok, reason)`
  and never raises. A 403 is a scope refusal only when the API says
  `insufficientPermissions`; any other 403, a 429 and every 5xx is
  retried once after 3 s. 400/404 are never retried. The bool
  `upload_caption_track` wraps it, so the RU and FR dub paths inherit
  the retry unchanged.
- `run_show` records `caption_track_error` as the reason string and the
  warning says what the reason implies instead of presuming the scope.
- `engine.pipeline.record_youtube_outcomes` allowlists both keys;
  the dashboard gains `caption_track_refusals_14d` (null until an
  episode has recorded the key — never a fake zero); register entry
  `caption-track-retry-2026-09-18`, readout 10-02.
- Guards: `tests/test_caption_track_2026_09_18.py`.

This is the third time a publish-result key was not a metric
(`grok_image_px_max` 09-03, `shorts_fill_modes` 07-22, now this). Plan
item 6 below is the structural fix.

## 3. The seven experiments past readout, scored

| Experiment | Due | Verdict | Evidence |
|---|---|---|---|
| grok-46-wave2-scripts (OV + MAB scripts) | 09-12 | OV hit, MAB open → `decide` 09-26 | OV: overlap 17.6%, coverage 85%, 0 factual flags in 4 review days (baseline 3/10d). MAB: coverage 64.8%, 2 flags in 4 days (baseline 2/10d), LV 4.2. No missed slots. Listen verdict not on record. |
| mit-verified-window-alpha | 08-29 | still `decide`, readout 10-15 | The recompute has not run: 20 verified / 35 unverified trades. On-air figure is the era record; the blend cannot reach the prompt. |
| long-open-cliff | 09-07 | MISS, closed | EN hold at 5% = 0.48 vs 0.51 baseline, 0.55 target. Render-side levers did not move it; the spoken open is what remains. Metric continues under five successor entries. |
| mit-rules-based-era | 09-15 | PARTIAL, closed | Holds span exactly the horizon (HIT); 13/13 invalidations (HIT); confidence "Medium" on 13/13 (MISS); and the show declared no trade on 21 of 34 era episodes — see §4. |
| network-review-catch-up | 09-10 | HIT, closed | 0 unreviewed episodes 09-04..09-16 across 15 shows; backlog 0. |
| mit-methodology-correction | 09-15 | PARTIAL, closed | Aired exactly 3 times (Ep145/149/150) and retired (HIT); 0 GA4 sessions on the performance page in 28 days (MISS). Per its own criteria: reword the pointer, do not extend. |
| shorts-4-band (RU/FR 4th Short) | 09-16 | near miss, kept, readout 10-02 | FF-RU is the only member. 4th Short median 437 = 55% of the hook's 794 (target 60%, n=8); the 3rd rose 75 → 282, so no abort. ru_short_vpd_max 55 → 72. |

## 4. The finding the experiments did not anticipate: MIT starves its own record

Since Ep152 (08-28) Modern Investing has written `action=no_trade` on
19 of 23 episodes (21 of the 34 in the rules-based era). Ep152 is the
first episode after the era record turned negative, which is when
`_build_regime_block` began injecting *COLD STREAK — RAISE THE BAR for
today's Practice Investment* into the prompt. The model obeyed: it
stopped picking. The era therefore has 9 closed trades in a month,
every learned rule is unscoreable, the rule-rotation and
strategy-family entries (readouts 10-01) cannot read out, and the
"published record anyone can check" is a record of abstentions. Two
smaller holes: HPS.A (Ep150, flash) has been "open" with no entry bar
since 08-26 and needs the void path; confidence has read "Medium" on
every era pick, so the rating carries no information.

The regime block is prompt context on an audio show, so changing it is
landmine-#17 A/B and the operator's call. The recommended shape: on a
cold streak, require a *stated* reason for the pick (thesis,
invalidation, what would make it wrong) rather than a higher bar to
pick at all; keep "no trade" available but cap it at one in five
episodes by rule, the way the picker deferral works on UC. Score it on
`trade_signal` action share (baseline 4 of 23).

## 5. What to change next, ranked

1. **MIT no-trade loop** (§4). SHIPPED FOR A/B the same day (register
   `mit-no-trade-budget-2026-09-18`): the COLD text raises the bar on the
   pick rather than on picking, voided picks no longer reset the drought
   valve, and a no-trade budget of one per five episodes is read from
   the committed trade signals. Operator listens to the first two
   episodes; revert is the previous COLD text plus dropping the budget
   block.
2. **Combined generation on the flagships re-runs PART 2 after a
   regeneration.** Three of five flagship episodes discarded a good
   combined script because the overlap-drop or structural regeneration
   rewrote the digest after the call. Either move the combined call
   after the digest is final or re-run the PART 2 prompt on the final
   digest instead of a full two-pass script stage. Also FF: PART 2 under
   the band twice at 17,500 tokens — raise `podcast_max_tokens` there or
   accept two-pass for it. The 09-17 ledger prediction (≥ 70% combined
   on the flagships) is on course to miss.
3. **Read the 09-14 reach dip by show before changing anything.** The
   softest day on record hit EN and RU together, then 09-15 channel
   views halved on both. Tonight's fetch adds 09-16; if the dip holds
   two days, the question is what changed on 09-13 (x264 `faster`
   started then, on EN only) and what the spoken opens looked like —
   not the renders, which RU does not share.
4. **One Short per episode on EN** (carried from PR #1220, operator
   decision): the second `qualified` Short earns a median 8–10 views at
   day 3 against 14–31 for the hook Short.
5. **Reword the MIT methodology pointer** (prompt, A/B): the correction
   retired on schedule and sent nobody to the performance page.
6. **Make the publish-result → metrics contract structural.** Add a
   drift guard that lists every `result["…"] =` key assigned in
   `_publish_youtube` and asserts each is either allowlisted in
   `record_youtube_outcomes` or named in an explicit "not a metric"
   list. Three silent keys in six weeks is a pattern, not bad luck.
7. **Retire the RU 4th Short question on 10-02** with n ≥ 20; if the
   4th still holds under 60% of the hook, drop the band back to 3 for
   FF-RU — the 3rd is the one that improved.
8. **Overdue experiments are a cost.** Seven were past readout for up to
   20 days and the dashboard has been warning nightly. A readout is
   part of the change, not optional follow-up; the register warning
   should page when `overdue_count` > 2.

## 6. Reading table

| Number | Value | Source |
|---|---|---|
| Episodes published 09-18 | 11 of 11 | run-show.yml runs |
| Videos uploaded 09-18 | 38 (EN 22, RU 9, FR 7) | `youtube_videos*.json` |
| Long-form render median, 09-18 | 1,059 s (n=7) | `metrics_ep*.json` |
| EN hook Short day-3 median, 09-14 | 14.5 (n=10) | `api/youtube_early_reach.json` |
| EN long day-3 median, 09-14 | 6.5 (n=8) | same |
| EN views 09-15 / prior Tuesday | 1,288 / 2,313 | `api/youtube_stats.json` day series |
| RU views 09-15 / prior Tuesday | 1,254 / 2,524 | same |
| Subscribers EN / RU / FR | 435 / 210 / 51 | same |
| Open hold at 5%, EN | 0.48 (baseline 0.51) | dashboard retention curves |
| MIT no-trade share since Ep152 | 19 of 23 | `trade_signal_ep*.json` |
| MIT era closed trades | 9 | `investment_tracker.json` |
| FF-RU 4th Short / hook median | 437 / 794 (55%) | video index + stats |
| Caption-track refusals recorded, ever | 0 (key never allowlisted) | `metrics_ep*.json` |
