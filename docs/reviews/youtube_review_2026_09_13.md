# YouTube + pipeline readout — 2026-09-13 (first slate after the Sep 12 passes)

Operator brief: start the render-speed trial (`NERRA_X264_PRESET=faster`)
and review how the Sep 13 videos landed and how the whole pipeline and
workflow behaved under the Sep 12 changes (the review's ffmpeg-7 stamp
and early-reach instrument, and the other session's simplification pass:
rewrite gate removed, combined generation, source-integrity strip on
every show). Evidence is the committed `metrics_ep*.json`, the video
indexes, `api/youtube_early_reach.json`, `api/youtube_stats.json`
(generated 09-12 18:51 UTC, so analytics through ~09-10) and the Actions
job logs for the MAB, M&A, PT and finalize jobs.

## 1. Every show published; 34 videos across three channels

| Channel | Long | Shorts | Notes |
|---|---|---|---|
| @NerraNetwork (EN) | 7 | 15 | tier-A shows shipped 2/2 (Tesla, SpaceX, FF, M&A); MAB/FPD/PT requested 2, shipped 1 — the selector found no second window above 3.5 and `en-shorts-no-fill` held (by design since 09-09) |
| @NerraRU | 1 | 7 | FF 4 Shorts (the 60-vpd band), SpaceX long + 3 |
| @NerraFR | 0 | 4 | FF 2, SpaceX 2 |

Tesla's RU/FR dubs were not yet in the index at 14:32 UTC (its episode
committed 14:04; the multilingual sweep runs after). All 12 run-show
episodes committed; no skips, no watchdog fires, no recovery PRs.

**What landed well.** 2K scenes on every show (`grok_image_px_max`
2816), chapter-schedule visuals with 11-13 fresh scenes on every
long-form, fact cards rendered on Tesla (2), SpaceX (1) and FF (6), end
cards generated everywhere, funnel comments posted on every upload,
newsletters sent on all 12.

**What did not.** Two of the five SpaceX dub Shorts opened on the
market-close line: @NerraRU "рост на 2,3%" and @NerraFR "151 dollars et
21 cents en hausse de 2,3 %". The Sep 4 rule ("the spoken price line is
never a Shorts opener") lived in an English-only regex, and the dubs pick
their windows on the RU/FR Whisper transcript. **Fixed:**
`engine.shorts_selector._PRICE_LINE_RE` now carries the RU/FR close
verbs, the "<n> dollars et <n> cents" body and a bare "up/рост/hausse
<n>%" tail (guard `TestPriceLineCoversTheDubs`). One RU filled Short
shipped a garbled title ("Старлинг продолжает формировать решение на все
обозрение") — Whisper's RU transcription of the dub audio, faithfully
turned into a headline by `headline_from_excerpt`, which is grounded in
the excerpt by design. Not fixed here; the honest fix is to title filled
dub Shorts from the translated digest headlines (the `retitle` approach)
rather than from a transcript slice. Filled dub Shorts earn ~225 views
regardless (Sep 9), so this is a polish item, not a reach item.

## 2. Pipeline health: the render is still the run, and the finalize job was hiding a bigger cost

**Long-form render on 09-13** (`long_form_render_duration_s`): SpaceX
639, M&A 788, FF 858, Tesla 894, OV 1,024, MIT 1,142, MAB 1,273 —
median 894 s; the 7-day median the register reads is **1,024 s**. MAB's
step ran 37 minutes, 21 of them in the render. **Trial started** (this
PR): `NERRA_X264_PRESET` defaults to `faster` in run-show.yml (repo
variable overrides it; set `medium` to end), experiment
`x264-preset-faster-2026-09-13`, decision 2026-09-20 on
`long_form_render_median_s_7d` against 1,024 plus a two-video
spot-check. The dub renders stay on `medium` (a same-week control).

**`wall_duration_s` was double-counting the render.** MAB reported
3,257 s on a 2,225 s step because `long_form_render_duration_s` (added
09-11) is recorded inside `youtube_publish_duration_s` and the wall
clock sums every `*_duration_s` counter. Any file since 09-11 with a
long-form render overstates its wall time by the render; the 09-11
watchdog fires in the Sep 12 review were read from the Actions logs, not
from this number, and stand. Fixed in `engine.metrics`
(`_NESTED_DURATION_COUNTERS`); historical files are left as written.

**The finalize job spent 38 of its 39 minutes re-downloading 10,642
gallery sidecars, after every episode.** `build_gallery_manifest.py`
walks the whole R2 bucket serially (0.21 s per GET) inside "Regenerate
shared pages", which runs ~13 times a day; three of today's finalize
jobs were cancelled by the next one before they could commit, and the
one that finished pushed at 09:10 for an episode committed at 08:17. The
June 2026 note that moved it here assumed it was cheap. **Fixed:** the
walk is incremental (the committed manifest is a complete cache of every
sidecar it lists — only keys absent from it are fetched; vanished keys
drop out because the listing is the truth) and parallel (8 workers), the
nightly and the standalone workflow run `--full` as the safety re-read,
and a failed walk now keeps the committed manifest instead of writing an
empty one (which would also have deleted every per-show slice — the
July 24 search-index lesson, one directory over). Expected finalize
step: ~2-3 minutes.

## 3. The simplification pass, first slate: what actually engaged

**Combined generation ran on one show out of twelve, and that one fell
back.** The flag is the network default, but the code excludes chained
shows (`podcast_chain: true` — Tesla, SpaceX, FF, PT, MIT, FPD, UC),
shows whose script stage runs a different model (`podcast_model:
grok-4.6` — MAB, OV, dp_pod) and the two RU shows (off by config). That
left Models & Agents, whose PART 2 came back at 852 words under the
990-word band, so the script stage ran anyway. Metric
`combined_generation` reads `two_pass` on all 12.

With the rewrite gate gone, the scripts on the chained flagships copy
the digest again: verbatim 8-gram overlap Tesla 51% / FF 54% / PT 50% /
SpaceX 61% (coverage 39-70%), against the Sep 9 goal of ≤15% overlap
with ≥70% coverage. The four shows on a single script call read
18-30% (M&A 30/80, MAB 26/79, MIT 18/74, OV 18/87). FPD/UC at 76-77% are
narrative shows and by design. **Not changed here** — the exclusion
list is the pass's own contract and the flagship prompt chain is
audio-affecting (landmine #17) — but the operator should know that
"digest and script in one call" currently applies to M&A on Sunday,
plus env_intel and Offshore North on Monday, and that the shows carrying
half the downloads are back to reading the digest aloud. Two ways
forward, either one is an A/B-listen: make the chain eligible (render
the chain's outline step into PART 2), or drop `podcast_chain` on the
flagships and let the combined call write them.

**Source-integrity strip did what it says, and what it removed was
true.** Planetterrian: 3 claims, 2 unreachable (403 to the runner), both
sentences removed from the digest and named in the log — "Early tests
showed 98 percent sensitivity." and "Researchers at Columbia University
Vagelos College of Physicians and Surgeons found that base editing can
accurately edit genes in human embryos." — the second is the story's
finding. FF: 1 of 4 failed, 1 sentence removed from digest and script.
OV: 1 of 2 unverified, nothing to strip. Nothing fabricated was caught;
every removal was an unreachable source. That is the designed trade (a
sentence the gate cannot vouch for does not ship) and it should be read
weekly: `source_integrity_stripped_sentences` per show, and whether the
stripped sentence was the lede. A repair pass fired on both and
"produced no usable replacements".

## 4. Reach: the age-matched card, one day older

EN Shorts, median views at a fixed age (from `api/youtube_early_reach.json`):

| Published | Age 2 | Age 3 |
|---|---|---|
| 09-05 Sat | 26 | 32 |
| 09-06 Sun | 48 | 52 |
| 09-07 Mon | 14 | 17 |
| 09-08 Tue | 14 | 15 |
| 09-09 Wed | 10 | 10 |

Channel totals are up (EN +63.7% WoW on complete days, RU +35.7%, FR
+28.0%; net subscribers EN +30 / RU +23 in 7 days) while the newest
non-flagship EN Shorts keep earning less at the same age. Per show at
age 2, the weekday softening is Omni View (8 → 1 → 11), MIT (5 → 4 →
10), MAB (3 → 41 → 3) and M&A (12 → 15 → 17); FF (125 → 94 → 73),
SpaceX (26 → 83 → 66) and Tesla (81 → 30 → 14) are the exceptions in
different directions. 09-10 is the first day under the Sep 9 changes
(subscribe end card, fresh open, fact cards, no-fill) and 09-13 is the
first Sunday comparable to 09-06 (52); neither has an age-2 row yet.
**Read the card on 09-16 before concluding anything** — the two
weekdays needed to say "the Sep 9 changes helped/hurt" do not exist
yet.

## 5. What to watch

| Question | Where | When |
|---|---|---|
| Render median under `faster` | `long_form_render_median_s_7d` (register) | 09-20 decision |
| Finalize step length after the incremental manifest | Actions, "Regenerate shared pages" | next finalize |
| Sep 9 changes on age-matched reach | Early reach card, rows 09-10..09-13 | 09-16 |
| Strip: what gets removed, and is it the lede | `source_integrity_stripped_sentences` + the run log's "stripped unverified sentence" lines | weekly |
| Combined generation engaging anywhere | `combined_generation` counter | Monday (env_intel, Offshore North) |
| Dub Shorts never open on the quote | `window` + title in `youtube_videos.{ru,fr}.json` | 09-14 SpaceX dubs |
