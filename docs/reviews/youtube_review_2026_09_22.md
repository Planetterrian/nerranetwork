# YouTube pipeline review — 2026-09-22

Operator brief: review the full YouTube pipeline, codebase, statistics and
everything YouTube-adjacent, to keep improving audio and video and to keep
growing audience and subscribers on all current channels.

Method: three parallel passes (code map, statistics, review history) over
the working tree, then hand verification of every surprising number
against the raw files (`api/youtube_stats.json` generated 2026-09-22 with
the day series through 09-19, `api/youtube_early_reach.json`,
`api/youtube_policy.json`, `api/dashboard.json`, the per-episode metrics
files, the older snapshots still in the shallow history). Nothing in this
pass changes shipped audio (no landmine-#17 item). Ledger:
`docs/reviews/ledger/network.yaml` 2026-09-22.

## TL;DR

1. **The factory is healthy.** Every episode-day has its uploads on every
   enabled show × channel; the spoken-text gate passed 91/91 EN episodes;
   caption tracks 32/32 since 09-19; every scene is 2K (2816 px); the
   stagger sweep is not stuck; analytics are fresh; long-form EN average
   view percentage is 15.8 (14d) and subscribers grew +14 / +9 / +4 in the
   week (EN 448, RU 220, FR 56).
2. **Shorts reach fell on all three channels between 09-13 and 09-16, and
   it is not the content.** Same episode, different channels diverged:
   Tesla-EN's hook Shorts held while the RU and FR dubs of the same
   episodes fell five to ten times. That is a distribution-side change
   (YouTube's Shorts feed or a channel-level signal), and nothing in the
   repo measured which source moved.
3. **Operator decisions (2026-09-22):** EN ships one Short per episode
   (the hook); a weekly-probe tier for shows whose hook Short is dead; the
   spoken-text gate on the RU/FR/ES/ZH tracks in shadow first.
4. **Silent numbers fixed:** Tesla split across two audience-headline
   keys; the subscribe-CTA experiment scored on a per-video rate that
   falls with reach; fact cards blind to any count under 100.

## 1. The reach finding

### 1.1 What the age-matched ruler shows

`api/youtube_early_reach.json` records each video's views at snapshot
ages 1–7. For a Short the number at age 3 equals the number at age 7 on
every cohort (e.g. the 09-05 cohort reads 53 at ages 3, 4, 5, 6 and 7;
the 09-16 cohort reads 2 at every age) — a Short earns its views on the
publish day and then stops. So "age 3" is the final number, not a lag
artifact, and the snapshot lag (two to three days depending on the fetch
hour; recent days are revised downward by 5–13 % between snapshots) does
not explain a halving.

EN hook-Short median views at age 3 by publish day:

| 09-03 | 09-04 | 09-05 | 09-06 | 09-07 | 09-08 | 09-09 | 09-10 | 09-11 | 09-12 | 09-13 | 09-14 | 09-15 | 09-16 | 09-17 | 09-18 | 09-19 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 33 | 26 | 53 | 58 | 23 | 19 | 26 | 26 | 14 | 21 | 31 | 14 | 34 | **2** | **10** | **9** | **8** |

RU hook Shorts: ~220 through 09-12, then 72 / 46 / 92 / 15 / 71 / 49.
FR: 50–75, then 41 / 66 / 30 / 41 / 8 (09-16 onward).

Channel day series (views/day, all videos): EN 2,000–2,200 on 09-09..13
→ 1,000–1,300 on 09-15..19; RU 3,200–3,500 → 800–1,500; FR ~700 →
140–290. The pre-breakout baseline week (08-23..29) was EN 11,011 /
RU 18,574 / FR 3,124 against 9,761 / 13,656 / 2,971 for 09-13..19 — so
part of the channel-level fall is the 09-04..06 breakout fading, as the
09-12 review warned, but the per-video age-3 numbers are below the
pre-breakout cohorts too (22–32 on pre-peak weekdays).

### 1.2 Why it is not the 09-12 script change

Per show × channel, latest-age views of the hook Short by publish day:

| show / channel | 09-08 | 09-10 | 09-12 | 09-13 | 09-14 | 09-15 | 09-16 | 09-17 | 09-18 | 09-19 |
|---|---|---|---|---|---|---|---|---|---|---|
| tesla EN | 79 | 51 | 110 | 382 | – | 39 | **128** | 5 | **146** | 41 |
| tesla RU | 310 | 242 | 133 | 239 | 45 | 33 | **23** | **15** | 47 | 49 |
| tesla FR | 24 | 66 | 110 | 66 | 281 | 32 | 41 | **1** | 41 | **8** |
| spacex EN | 202 | 133 | 46 | 44 | 14 | 66 | 25 | 42 | 25 | 12 |
| spacex RU | 381 | 343 | 223 | 31 | 112 | 46 | 87 | **10** | 37 | 28 |
| FF RU | 19 | 1041 | 1087 | 651 | 1068 | 5 | 468 | 677 | 452 | 310 |
| omni_view EN | 2 | 2 | 4 | 70 | 15 | 2 | 8 | 1 | 7 | 5 |
| modern_investing EN | 5 | 13 | 10 | 0 | 11 | 21 | 1 | – | 1 | 40 |

The RU and FR dubs are translations of the EN script, rendered from the
same scene images. A script change (the 09-12 simplification pass, which
the 09-17 review blamed: "the softening tracks the script, not the
render") would move the original and its dubs together. Instead Tesla-EN
held at 128 and 146 while its dubs fell to 15–49 and 1–41; SpaceX-RU
fell from 343–381 to 10–46 while SpaceX-EN drifted. The one surface with
a real returning audience (FF-RU, 11 of the network's top 15 videos)
held at 310–677. No pipeline change touched the dub renders in that
window (the x264 trial was EN-only; the price-line filter changed dub
window choice, not the hook Short). The pattern — exploration traffic to
new videos gone on every channel within four days, the
established-audience surface intact, long-form flat to up, subscribers
still climbing — is YouTube-side distribution.

### 1.3 What was missing, and what ships

The only traffic-source read was `channels[ch].traffic_sources`, a
90-day aggregate. Between the 09-20 and 09-22 snapshots the SHORTS
source read 15,281 → 13,928 (draining out of a rolling window) — a
direction, not a date. `scripts/fetch_youtube_analytics.py` now stores
`traffic_day_series` per channel (views per day by
`insightTrafficSourceType`, pivoted to SHORTS / SUBSCRIBER / YT_SEARCH /
RELATED_VIDEO / other); it is informational by contract — retried on
5xx like the day series, but a failure is log-only and never joins the
degraded marker that refuses a snapshot. The dashboard's **Traffic mix**
card shows four complete weeks of source shares per channel and
`shorts_feed_share_7d_en` is the distribution read for the one-Short
experiment. Register: `traffic-mix-instrument-2026-09-22`.

**Reading rule for the next pass:** "same episode, different channels"
is the test for content vs distribution. If the dubs and the original
move together, look at the script or the imagery; if they diverge, look
at the channel.

### 1.4 The lever the pipeline owns: upload quality on the channel

EN runs ~24 uploads/day against the 30/day cadence ceiling, and a large
share are dead on arrival:

| EN Shorts by window, 28 days | n | median views | subscribers |
|---|---|---|---|
| `hook_open` (Short #1) | 274 | 22 | 30 |
| `qualified` (Short #2) | 59 | 6 | **0** |
| `filled` (before 09-09) | 54 | 4 | 3 |

At age 7 the `qualified` Short reads 3–6 against 28–32 for the hook — the
read the 09-17 review asked for. Four EN shows' hook Shorts have sat
under 10 median views for three weeks (dp_pod 4.5, omni_view 6, MAB 7,
modern_investing 9 over 14 days).

**Decision A — EN ships one Short per episode.**
`engine.youtube_policy.MAX_SHORTS_PER_CHANNEL = {"en": 1}`, enforced in
`resolve_publish_plan` on both clamps (YAML floor and policy value), so a
stale policy file or `tesla.yaml`'s `shorts_per_episode: 2` cannot
reintroduce it. `run_show.py` now reads the plan's count on every path —
it used to take it only when a policy entry applied, which let a missing
policy file ship the YAML 2. The nightly writer reads the same constant
and caps `shorts_pending` too (or the raise-hysteresis would hold a
phantom 2 forever). RU/FR keep the ladder: their filled Shorts earn
100–225 views. Revert = delete the dict entry. Register
`en-one-short-2026-09-22`, metric `short_reach_d3_median_en_7d`
(baseline 10, target ≥ 15 by 10-06 with EN net subscribers not down; if
it does not move with ~10 fewer uploads a day, the drop is
distribution-side and the cap stays for the cost saving alone).

**Decision B — dead-Shorts weekly-probe tier.** A show whose hook
Short's age-3 median sits under `DEAD_SHORTS_FLOOR` (10) across the last
21 publish days with ≥ 7 videos drops to one Short a week on its sharded
probe day (`_is_probe_day`, the same weekday as its long-form probe)
after two consecutive nights, and climbs back when the median of its
last three probe Shorts clears the floor. "Shorts never 0" becomes
"never 0 for more than 7 days". The ruler is
`api/youtube_early_reach.json` (hook Shorts, `views_by_age["3"]`), never
the rolling channel total; a missing reach file holds every show's
state. EN only (`SHORTS_PROBE_CHANNELS`). On the 09-22 file the
regeneration enrols omni_view (8.5, n=16) and modern_investing (9.0,
n=15) at night 1 of 2; MAB (11.0) and dp_pod (14.5) sit above the floor
on the 21-day ruler and enter only if they keep falling — stated rather
than tuned. dp_pod is enrolled in `SEED_TIERS` (its own experiment asked
for a tier line, and the tier can only reach an enrolled slug).
run_show records `yt_policy_shorts_skipped` on a no-Short day and the
pipeline no longer coerces a policy 0 to 1. Register
`dead-shorts-weekly-probe-2026-09-22`.

## 2. Findings

### P0 — audio safety: the dub tracks were never checked against their text

`engine/spoken_text_gate.py` (landmine #25, the Tesla Ep605 leak) had one
production caller, run_show's EN path. `engine/multilingual.py`,
`engine/ru_dub.py` and `engine/lang_dub.py` never imported it — although
the dub engines already Whisper the same MP3 for captions and windows
and the translated script sits beside the track as `<stem>.<lang>.txt`.
The same server-side text normalisation that read its own reasoning
aloud on Ep605 runs on every dub synthesis, and @NerraRU carries 14 of
the network's top 15 videos. CLAUDE.md said "not covered yet"; no
register entry, no ledger prediction, no operator item existed.

**Decision C — shadow first.** `generate_for_episode` now Whispers every
rendered track and runs `check_transcript_files` against the translated
script BEFORE the R2 upload that feeds the per-language podcast feeds
and the YouTube dubs. Shadow: the verdict goes to
`digests/<slug>/spoken_text_gate.<lang>.json` (and onto the translation
record as `spoken_text_gate` / `transcript_file`), a failure is a
`::warning::`, nothing that ships changes — `resolve_gate_mode`
downgrades `enforce` to shadow for any non-English transcript until a
language is calibrated, which is what the shadow data is for. The dub
engines reuse the sweep's Whisper JSON (`track_transcript_path`) instead
of transcribing the same bytes twice; the JSON is gitignored, the plain
transcript and the sidecar are committed. `scripts/audit_spoken_text.py
--dubs` is the calibration read; `dub_gate_fail_share_14d` (null under
10 tracks) is the dashboard metric. `MultilingualConfig.spoken_text_gate:
shadow | off`. Register `dub-spoken-text-gate-shadow-2026-09-22`, readout
10-06: enforce if every failure is a Whisper artifact.

Also found: the dub paths record no per-episode metrics at all
(`caption_track_uploaded` is set at `ru_dub.py` / `lang_dub.py` and
dropped). The sidecar above is the first per-track record; caption
refusals on the dubs remain unmeasured (deferred).

### P1 — silent numbers

- **Tesla under two audience-headline keys.** `youtube_stats.json`'s
  top-level `shows` keys are digests DIRECTORY names
  (`tesla_shorts_time`); OP3 is keyed by slug (`tesla`).
  `build_audience_headline` unioned them, so the tile had `tesla` with
  downloads and no YouTube and `tesla_shorts_time` with YouTube and no
  downloads — the network's second-largest YouTube show read as dead in
  both rows. Now grouped by the videos' `show_slug`; a guard asserts every
  headline key is a show slug against the committed files.
- **The subscribe-CTA experiment could not score a CTA.**
  `short_subs_per_video_14d_en` read 0.11 → 0.053 while EN Short views per
  video halved; a per-video rate falls with reach. The dashboard now
  computes `short_subs_per_1k_views_14d_en` (1.51 on 09-22: 9 subs /
  5,964 views; null under 300 views) and the entry reads that.
- **Five experiments shared one flat metric.** `chapter-title-cards`,
  `scene-briefs-narrative-imagery`, `video-quality-round-3`,
  `long-form-captions-track-only` and `fresh-open-long-form` all read
  `long_open_hold_5pct_en`, which sits at 0.48 (baselines 0.48–0.51).
  Inseparable by construction; the four due 09-23 are closed
  INCONCLUSIVE on the metric with their mechanisms kept (§4).
- **Two ledger predictions were already decided.** The 09-18 network
  entry predicted flagship combined generation "stays under 50% until
  the regeneration path re-runs PART 2"; the flagships ran 17/25 combined
  over 09-18..22 (1/5, 2/5, then 5/5, 5/5, 4/5) with that item unshipped —
  the sentence-normalised stash comparison merged 09-18 was the fix. MISS
  in the pipeline's favour; the 09-17 "≥ 70%" prediction is a PARTIAL
  (68 % on five of seven days, 93 % on the trailing three).
- **`api/gallery_retention.json` is not empty.** The Sep 9 note in
  CLAUDE.md ("has never held a tag — do not cite it") is stale: it now
  carries 7,182 image records and per-show top/bottom tags (min 3
  videos). Not acted on here; noted so the next pass does not discard it.

### P2 — render and measurement gaps

- **Fact cards blind to counts.** `_score` returned 0 for any bare value
  under 100, so "1 gigawatt", "9 satellites", "18 months" never carded;
  SpaceX rendered ≥ 3 cards on 4/12 episodes, FF 5/12, Tesla 8/12,
  while recent transcripts carry 12–25 digit figures. A closed set of
  count nouns now rides into the run (the label never repeats it) at
  score 2, below money and percentages; a number after a capitalised
  word ("Falcon 9 booster", "Raptor 3 engines") is a designation and
  never cards; spelled-out numbers stay out of scope. Re-run on the last
  four transcripts: SpaceX 1 / 6 / 2 / 1, FF 3 / 2 / 4 / 2, Tesla 3 / 4 /
  5 / 5 — better on the flagship, still short on SpaceX, where the
  remaining figures are years, designations and prices already carded.
  The AVP criterion of `long-form-fact-cards` is met (treatment 17.4–20.3
  vs control 13.0–16.2, +3–4 points); the density criterion is scored in
  the ledger.
- **Allowlist hygiene.** `record_youtube_outcomes` allowlisted
  `shorts_selector_scores` and `video_podcast_skipped`, which no code
  writes; the shorts-only day sets `video_podcast_render_only` (it
  renders anyway for the video feed), which was dropped. Now recorded;
  `video_podcast_skipped` removed. `yt_comments_queued`, `outro_card` and
  `short_errors` beyond the first stay exempted (carriers, not metrics).
- **Planetterrian's weekly long-form probe** shows AVP 1.26 / 1.95 % and
  average view duration 6–10 s on its last three uploads (network longs
  12–20 %). Operator: watch the first 15 s of the 09-14 upload before
  the next probe; a broken open on a weekly probe costs a full render
  each Monday for nothing.
- **Four (show, channel) rows in the policy with zero uploads**
  (env_intel-EN and finansy_prosto-RU paused; modern_investing RU/FR
  culled 09-01) — held at null velocity, harmless.

## 3. What is healthy (verified, do not re-fix)

- 100 % of episode-days have uploads on every enabled show × channel (EN
  327 / RU 146 / FR 94 videos in 14 days); no gaps.
- Spoken-text gate `pass` on 91/91 EN episodes in the last 7 days; the
  09-14 Ep605 class has not recurred.
- Caption tracks 32/32 since 09-19; `caption_track_refusals_14d` = 0
  (four days of a 14-day claim — read again 10-02).
- `grok_image_px_max` 2816 on every episode; `visual_mode`
  `chapter_schedule` on every long-form; 13 fresh + 14 library scenes per
  flagship episode.
- Long-form render median 953 s (n=60, 7d); the preset trial measured no
  effect and is closed; the filter graph is the remaining lever.
- Cold open (Aug) POSITIVE and holding; EN long AVP 15.8 (14d).
- Stagger sweep: 4 pending comments (all RU, due 15:00 UTC), 524 posted,
  not stuck.
- Combined generation on the flagships 14/15 over 09-20..22.

## 4. Experiments scored (readout ≤ 09-23)

| entry | verdict |
|---|---|
| `nerra-daily-launch` | SURFACE FOUND — 153 downloads/30d, weekly [13, 23, 61, 56]; keep |
| `chapter-title-cards` | INCONCLUSIVE — shared flat metric (0.48 vs 0.49); kept |
| `scene-briefs-narrative-imagery` | INCONCLUSIVE on the metric, kept on the mechanism |
| `image-source-2k-and-story-matched-shorts` | HIT on delivery (2816 px everywhere), inconclusive on retention |
| `video-quality-round-3` | HIT on (1)(2), inconclusive on the metric |
| `long-form-captions-track-only` | HIT — no doubling, hold no worse |
| `shorts-title-headline-only` | INCONCLUSIVE — confounded by the 09-13/16 drop (§1.2) |
| `en-shorts-no-fill` | HIT on its terms (0 filled), SUPERSEDED by `en-one-short-2026-09-22` |

Rule applied: an entry shipped 09-02..09 reading out against the
09-13/16 distribution drop is INCONCLUSIVE with the confound named,
never a MISS — a MISS would pollute the ledger's category rates with a
change the pipeline did not make.

Due 09-25..30 and NOT scored here (their windows are open):
`dp-pod-youtube-shorts` (16 Shorts, 195 views, 0 subs, AVP 27–31 % —
the network's lowest; keep/pause is the operator's), `shorts-subscribe-cta`
(re-instrumented), `fresh-open-long-form` (flat, will be INCONCLUSIVE),
`long-form-fact-cards` (AVP criterion met, density improved above),
`pause-dead-youtube-uploads` (its metric `channel_views_wow_en` cannot
separate the pause from the drop; score on the two shows' absence
costing nothing).

## 5. Operator items (not code)

1. **Podcast playlists missing on age_of_ai and dp_pod** — the only live
   critical alert (landmine #15; Studio, no API).
2. **YouTube Music RSS ingestion 0/15.** Worth doing only for shows whose
   long-form is policy-skipped (first_principles, planetterrian,
   unintended_consequences, dp_pod, the interview shows, nerra_daily);
   on a show that already uploads long-form, Studio ingestion would
   duplicate it.
3. **dp-pod-youtube-shorts readout 09-25** — keep or pause.
4. **Planetterrian long-form probe** — spot-check the first 15 s of the
   09-14 upload (§2, P2).
5. Standing: pin the auto comments; Studio Title/Thumbnail Test &
   Compare; channel trailer; IG/TikTok credentials; `GA4_SERVICE_ACCOUNT_JSON`.
6. **Listen items from earlier passes still open:** the MIT no-trade
   budget's first two episodes (A/B, landmine #17).

## 6. Deferred, with reasons

- Enforcing the dub gate — after the 10-06 shadow readout; needs
  per-language thresholds in `resolve_gate_mode`.
- Filter-graph benchmark (branch count, `filter_threads`) — the only
  remaining long-form render lever; a separate measured pass.
- Dub caption-refusal metrics — the dub engines have no per-episode
  metrics file; the gate sidecar is the first per-track record.
- Russian chapters on RU long-forms; dub-Short titles from translated
  headlines — polish, not reach (RU filled Shorts earn ~225 regardless).
- The `qualified` window selector itself — moot on EN under the cap;
  RU/FR pick their own windows and their second/third Shorts earn.

## 7. Shipped in this pass

- `engine/youtube_policy.py`, `scripts/update_youtube_policy.py`,
  `run_show.py`, `engine/pipeline.py`, `api/youtube_policy.json` — EN
  cap, dead-Shorts tier, honest `yt_policy_shorts`, `yt_policy_shorts_skipped`,
  `video_podcast_render_only`; dp_pod enrolled.
- `engine/multilingual.py`, `engine/ru_dub.py`, `engine/lang_dub.py`,
  `engine/config.py`, `shows/_defaults.yaml`, `scripts/audit_spoken_text.py`,
  `.gitignore` — the dub gate in shadow, transcript reuse, audit mode.
- `scripts/fetch_youtube_analytics.py`, `scripts/generate_dashboard.py`,
  `management.html` — traffic-source day series, Traffic mix card,
  `shorts_feed_share_7d_en`, `short_subs_per_1k_views_14d_en`,
  `dub_gate_fail_share_14d`, dead-tier columns on the policy section.
- `scripts/build_audience_headline.py` — one key per show.
- `engine/fact_cards.py` — count nouns.
- `docs/experiments.yaml` — 8 closed, 4 registered;
  `docs/reviews/ledger/network.yaml` — 3 re-scored, 7 new predictions;
  CLAUDE.md — the Sep 22 block.
- Guards: `tests/test_youtube_policy.py::{TestEnOneShortCap,TestDeadShortsTier}`
  (+ amendments), `tests/test_multilingual.py::TestDubSpokenTextGate`,
  `tests/test_youtube_pass_2026_09_17.py::TestTrafficDaySeries`,
  `tests/test_dashboard_growth.py::{TestReachNormalisedSubs,TestDubGateMetric,TestTrafficMix}`,
  `tests/test_fact_cards.py::TestCountNouns`,
  `tests/test_simplification_2026_09_12.py::TestAudienceHeadline` (+2).

⚠️ A/B-listen required (landmine #17): **none** — no change in this pass
touches a prompt, a voice, or the audio chain. The dub gate records; it
does not alter a track.
