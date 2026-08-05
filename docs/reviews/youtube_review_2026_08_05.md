# YouTube pipeline & viewer review — RU vs EN vs FR (2026-08-05)

Operator-requested review of the full YouTube pipeline and viewer
statistics, focused on: how to increase reach and viewers, which shows to
adjust, why the Russian channel outperforms the English channel on
views/watch-time-per-video, and why the French channel is doing so poorly.

Data: `api/youtube_stats.json` (90-day window, generated 2026-08-04),
`api/youtube_policy.json`, `api/youtube_channel_history.json`,
`api/funnel.json`, per-show `youtube_videos.<lang>.json` indexes. The
30-day slices below cover 2026-07-06 → 2026-08-04. Honesty caveats are
flagged inline — the FR channel has only ~2 weeks of clean data.

## Channel scorecard (30 days)

| Channel | Subs | Views/30d | Net subs/30d | Uploads in window | Views per video |
|---|---|---|---|---|---|
| EN @NerraNetwork | 273 | 20,272 | +102 | 534 | ~30 (shorts) / ~26 (long) |
| RU @NerraRU | 88 | 38,135 | +49 | 243 | **192 (shorts)** / 11 (long) |
| FR @NerraFR | 2 | 39 | +2 | ~72 since 07-21 launch | ~2 |

RU delivers **1.9× EN's total views on 45% as many uploads**. FR is
effectively invisible.

## RU vs EN — what the numbers actually say

**RU Shorts are the network's single best surface, and it's concentrated.**
30-day short views by show×channel: spacex-RU 15,483 (337/video), FF-RU
12,115 (327/video), tesla-RU 5,132 (132/video), MIT-RU 1,541 (43/video).
spacex + FF alone are 80% of all RU views. The RU audience is a
**space-content audience** — the shows that aren't space (MIT, FP, PR)
do EN-typical numbers.

**EN still owns the two metrics that compound.** Watch time: EN long-form
8,333 min/30d is the largest watch-time block in the network (RU shorts
7,659, EN shorts 2,104, RU long 990). Subscribers: EN +102 net vs RU +49
— and within EN, long-form on the big three (tesla 8.9 long-vpd, spacex
7.2, M&A 5.2) is what converts. RU long-form remains dead (11 views/video,
11% median retention) — the policy's RU long freeze is correct; do not
revisit.

**Retention is now format-driven, not channel-driven.** Median short AVP
is ~44% on both EN and RU (the 35s cut working as designed); long-form
median AVP is ~11% on both. The July-30 cold-open change targets exactly
this — its first full week isn't in this window yet, so **hold further
retention surgery until ~08-15 data reads out**.

### Recommendations (RU/EN)

1. **Feed the RU spacex/FF machine.** The supply ladder already grants
   them 3 Shorts each (short_vpd 52/61) — verify 3 actually ship
   (`yt_policy_shorts` metric) now that the two silent caps are fixed.
   Today's earnings special will flow to @NerraRU automatically via
   ru_dub — RU spacex at 337 views/short makes it the special's
   highest-reach surface.
2. **Don't cut EN long-form on the big three.** It's the subscriber and
   watch-time engine even at 11% retention. The velocity-gated policy is
   doing the right per-show pruning (omni_view is one streak away from
   earning long-form back; env_intel/planetterrian/UC/first_principles
   correctly held at shorts-only).
3. **Weakest EN surfaces, watch-list not action-list:** MAB shorts (0.54
   vpd, 4.8 views/video) and env_intel (13 videos → 88 views). Policy
   already holds both at minimum supply. If MAB is still flat at the
   September review, re-pausing its YouTube (as before June 26) saves
   render+image cost with near-zero reach loss.
4. **Measure the cold-open effect before the next retention change** —
   one variable at a time; the 08-15 window will say if long AVP moves
   off 11%.

## Why FR is doing so poorly

The honest headline: **53 of 72 FR uploads have zero recorded views** (a
video with no activity gets no analytics row at all — only 19 have rows).
This is not "low CTR"; it's "the algorithm isn't surfacing the channel to
anyone."

Diagnosis, in order of weight:

1. **Cold start with no seed, vs RU's warm start.** @NerraRU launched
   with two *native* Russian shows (FP/PR, full format since June) plus
   four dub shows and had ~61 subscribers before the July window. @NerraFR
   launched 07-21 with dubs only, zero native content, zero subscribers,
   zero external traffic. A new channel with no engagement signal gets no
   impressions to fail at.
2. **Market structure.** Russian-language space content is structurally
   underserved, so the algorithm had demand and no supply — RU spacex
   shorts found 337 views/video almost immediately. Francophone space
   content has strong native incumbents; a dubbed 35s clip competes
   against them directly.
3. **Metadata quality at launch.** Until the 07-30 clause-trim fix, 26%
   of FR short titles ended on a dangling preposition (worst of the three
   languages — FR runs 15-20% longer than its EN source so the 70-char
   cut hit mid-clause). The first-impression window of the channel shipped
   with the worst titles it will ever have.
4. **Retention of the few views it gets is half of RU's** (19.4% vs 43.8%
   median short AVP). Small n, but consistent with dub quality being
   noticeable — the FR track is the EN cloned voice speaking French.
   Operator should A/B-listen one FR dub (landmine #17 ears apply to
   dubs too).
5. *(Not a cause of zero views, but of blindness:)* the analytics glob
   bug hid FR from the feedback loop until 07-29, so tiers froze at seed
   and nothing could be learned. Clean data only exists since then —
   which is why this review sets a decision date instead of a verdict.

### FR recommendations

- **Set a decision date, don't kill it today: 2026-08-25** (~5 weeks
  post-launch, ~4 weeks of clean analytics). Criteria to keep going: any
  show reaching short_vpd ≥ 1.0, or visible organic subscriber traction.
  Below that on all four shows → pause FR dubs (`dub_languages: []` in
  the four YAMLs — one-line, reversible).
- **Within the window, only cheap fixes:** operator listens to one FR
  short for dub quality; confirm post-07-30 FR titles are clause-clean;
  FR-language hashtags/keywords in descriptions. Do **not** build a FR
  funnel lander yet — there is no traffic to convert (the RU lander was
  justified by 25k+ views/30d).
- **Decouple the two FR bets.** FR *YouTube dubs* (this channel) and FR
  *podcast tracks* (~$20/mo, 7 shows) are separate instruments: the
  per-language OP3 `language_feeds` data decides the podcast tracks
  independently. Zero FR YouTube traction does not by itself condemn the
  FR podcast feeds — and vice versa.
- **The structural lesson from RU:** a language channel works here when
  the niche is underserved AND there's an anchor building channel-level
  engagement. If FR is to be retried seriously later, the RU playbook
  says: pick the underserved francophone niche first, consider a native
  FR show (or FR-first metadata at minimum), don't lead with dubs alone.

## Pipeline health notes (incidental findings from today's run log)

- The 08-05 spacex run shipped clean end-to-end (Ep057, 2 Shorts, video
  podcast, RU/FR handled downstream), with two non-fatal warts worth a
  look: **long-form thumbnail upload failed 403** ("request might not be
  properly authorized" — Short thumbnails succeeded, so this looks like
  the long-form video's thumbnail-set call hitting a permission/timing
  issue, worth watching for recurrence), and the **gallery public CDN
  rejected reads (HTTP 403)** forcing the authenticated-R2 fallback all
  run — check the `gallery.nerranetwork.com` public-access / custom-domain
  config on the bucket.
- Podcast script came in at 1,147 words vs the 1,300 target with the
  expansion retry correctly off (digest-side lever is the sanctioned
  path) — consistent with the known digest ceiling, no action.

## What was shipped alongside this review

The **SpaceX Quarterly Earnings Special Q2 2026** is set up as a
manual-force deep dive on the spacex show (the MIT deep-dive mechanism):
`shows/deep_dives/spacex.yaml` (queue entry `q2-2026-earnings` with the
verified 10-Q/press-release numbers + live web/X research queries),
`shows/prompts/spacex_deep_dive{,_podcast}.txt`, and a forced-only
`deep_dive:` block in `shows/spacex.yaml`. Run it with:

    python run_show.py spacex --deep-dive q2-2026-earnings

It publishes as the next SpaceX Daily episode through every normal
surface (RSS, YouTube, newsletter, blog, multilingual, RU dub).
