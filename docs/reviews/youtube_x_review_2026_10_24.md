# YouTube and X review — why views and subscribers fell, and what moves them (2026-10-24)

Operator brief: review the YouTube and X pipelines, the postings and the
analytics; determine why YouTube views and subscribers seem to be declining;
name the significant improvements that would earn more time on the videos
and more subscribers.

Method: four parallel read-only passes (channel analytics rebuilt from 31
stored snapshots of `api/youtube_stats.json`, 2026-07-25 → 10-24; the
YouTube pipeline as a viewer sees it, with one real description render;
the X pipeline against the Supabase queue and 286 metrics files; retention
and subscriptions joined to the committed scripts, transcripts and chapter
files), then every claim that led to a code change was re-verified by hand
against the file or the function. Every number below is read from committed
data unless marked *inferred*. Nothing in this pass changes shipped audio
(no landmine-#17 item); the spoken levers are listed as operator decisions.
Register `youtube-x-review-2026-10-24`; guards
`tests/test_youtube_x_review_2026_10_24.py`.

## TL;DR

1. **The decline is a YouTube distribution change on the Shorts feed, dated
   Sep 15-16, and it hit @NerraRU hardest.** RU weekly views 18.8-33.8k (Aug)
   → 7.8-8.3k (Oct), about 40% of the August average; RU Shorts-feed traffic
   −65% while RU search traffic rose 21% and suggested traffic 64%; Shorts
   watch-through unchanged (44-56% every week since August); the country mix
   unchanged; the same Tesla and SpaceX scripts lost 3× more on RU than on
   EN (the RU/EN reach ratio went 2.0-3.4 → 1.0 in the week of Sep 14 and
   stayed there). Uploads were cut AFTER the fall and account for about
   10-15% of RU's loss.
2. **EN is a faded breakout, not a decline.** The Aug 31 and Sep 7 weeks
   (19.4k / 16.0k) were a breakout from three Shorts; since Sep 21 EN runs
   8.8-12.1k a week, −8% against the August weeks before the breakout and
   −45% against the breakout fortnight. Subscriber-sourced EN views are −8%,
   long-form reach per video is flat to up, and long-form is now the top four
   EN view sources.
3. **Subscriber gains follow the Shorts-feed views at a steady 0.9-2.2 per
   1,000.** EN ≈40 → ≈22 a week, RU ≈25 → ≈9, FR ≈11 → ≈5. Half the EN
   slowdown is fewer Shorts views; half is long-form converting at ~1.5 per
   1,000 instead of ~3 as its audience becomes returning subscribers
   (*inferred* from the two series).
4. **The one content effect the pipeline owns is EN long-form retention:**
   Tesla 18.4% → 12.3%, FF 13.8 → 10.4, M&A 12.4 → 8.8, MIT 8.4 → 5.7 since
   Sep 21, SpaceX held at 17.5. Views per long-form did not fall. The Oct 3
   hook-leads-body fix has not restored Tesla's 16-19%.
5. **Six pipeline defects were verified in code and five are fixed here**, all
   render or metadata: 59% of long-forms shipped a chapter list YouTube
   rejects; the description repeated the hook, carried the website twice and
   ended on an operator note; the X teaser links on four shows were untagged;
   the early-reach file had no retention by age so no slate since Oct 13 can
   be judged on retention; the tier-C long-form probe could never promote a
   show. The sixth (the Short-to-long funnel is dark while the Short earns
   its views) is an operator decision because it reverses the Oct 17
   release schedule.
6. **The lever with the most expected effect is still a spoken one** (⚠️
   AUDIO): on the Short, the hook ends at 6.9 s, the identity line at 11 s,
   and since Oct 20 the map sentence pushes the first story fact to 17.5 s
   of a ~32 s clip — 30% of viewers are gone before the show is named.

## 1. Where the views went

### 1.1 Weekly views, net subscribers and uploads (Mon weeks)

| week | EN views | EN +subs | EN uploads S/L | RU views | RU +subs | RU uploads S/L | FR views | FR +subs |
|---|---|---|---|---|---|---|---|---|
| 08-03 | 8,629 | +26 | 99/54 | **33,845** | +29 | 86/6 | 1,393 | +7 |
| 08-10 | 11,095 | +48 | 116/48 | 28,789 | +32 | 77/23 | 3,448 | +12 |
| 08-24 | 11,778 | +42 | 112/56 | 20,060 | +17 | 72/12 | 2,686 | +5 |
| 08-31 | **19,379** | +30 | 111/53 | 23,900 | +27 | 68/11 | 3,280 | +8 |
| 09-07 | 16,023 | +21 | 107/52 | 19,236 | +22 | 70/10 | 3,193 | +10 |
| 09-14 | 8,754 | +15 | 98/51 | 11,205 | +12 | 58/4 | 2,565 | +4 |
| 09-21 | 9,960 | +31 | 63/52 | 7,849 | +11 | 51/10 | 1,876 | +5 |
| 09-28 | 12,061 | +23 | 38/49 | 5,421 | +1 | 41/9 | 1,487 | +3 |
| 10-05 | 8,844 | +23 | 41/49 | 7,792 | +9 | 44/10 | 2,292 | +4 |
| 10-12 | 9,523 | +22 | 49/48 | 8,296 | +10 | 50/4 | 2,283 | +6 |

The Analytics day series is the source (the Data API `total_views` counter
stopped counting Shorts on Sep 2 and is a lower bound). The daily series
dates the step: RU 2,400-3,500 a day through Sep 14 → 1,187 on Sep 15 → 800-
1,500 → 400-600 by Sep 25; EN 1,797 → 1,195 → 1,033 on Sep 14-16. The view
fall precedes the upload cut on every channel (EN views fell in the Sep 14
week with 98 Shorts still shipping; RU fell at 58 Shorts).

### 1.2 Reach per video at a fixed age

The hook Short's median views at age 2-6 days, by publish week:

| publish week | EN hook Short | EN long | RU hook Short | FR hook Short |
|---|---|---|---|---|
| 08-10 | 16 | 15 | **487** | 54 |
| 08-24 | 14 | 20 | 142 | 36 |
| 08-31 | 31 | 32 | 260 | 64 |
| 09-07 | 24 | 21 | 220 | 45 |
| 09-14 | 12 | 16 | **47** | 41 |
| 09-28 | 25 | 26 | 44 | 40 |
| 10-12 | 14 | 26 | 44 | 37 |

The RU hook Short went from 220-487 to 42-58 (−80%). The EN hook Short is
back to its August level, not below it. EN long-form is flat to up (44-59
views at age 7 in October against 30-44 in late August).

### 1.3 Traffic source — what fell

Against the late-August baseline, Oct 5-18 average per week: EN Shorts feed
1,435 (−58%), subscriber 4,471 (−8%), search 2,170 (−26%), suggested 668
(−36%). RU Shorts feed 20,776 → 7,174 (−65%); RU search 464 → 561 (+21%);
RU suggested 101 → 166 (+64%). RU's total is the Shorts feed alone. 96% of
RU's views were Shorts-feed traffic; 46% of EN's are subscriber-sourced, so
the two channels are different products: EN is a subscriber-fed channel,
RU and FR are Shorts-feed channels.

### 1.4 Same script, different channels

161 episodes have a hook Short on at least two channels. Pre (Aug 24 - Sep
13) → post (Sep 21 - Oct 17) age-3 medians: Tesla EN −37% / RU −76% / FR
−25%; SpaceX EN −25% / RU −80% / FR −41%. A content or render change cannot
move a dub and spare its original, so the RU fall is channel-side. The
exception is Fascinating Frontiers, which fell on all three channels
together (−71 to −80%) from its own September breakout; the same-script
test cannot settle FF.

### 1.5 What it rules out

A volume cut as the cause (reach per upload fell before uploads did; the
cut EN Shorts earned 2-6 views each); a Russia-side block (RU 37-41%, UA
14-18%, KZ 8-11% across five snapshots); a render or script change (the
dubs and originals diverged, and no dub-path change lines up with Sep 15);
lower watch-through (flat everywhere). Not knowable from this data: WHY the
Shorts feed stopped distributing @NerraRU on Sep 15 — a Studio read
(restrictions, reused-content notices) the Oct 3 review already asked for.

### 1.6 Subscriber conversion — what converts

| channel × kind | views (90 d) | subs | subs / 1k |
|---|---|---|---|
| EN long | 62,961 | 131 | 2.08 |
| EN Short | 54,742 | 118 | 2.16 |
| RU Short | 198,319 | 179 | 0.90 |
| RU long | 3,057 | 18 | 5.89 |
| FR Short | 26,044 | 71 | 2.73 |

Space content converts: 17 of the top 20 subscriber videos are SpaceX or
FF; SpaceX-EN Shorts 3.1 per 1k, FF-FR Shorts 4.4, FF-RU Shorts 117 subs
on 100k views. Tesla converts at half SpaceX's rate on every surface (Tesla
Short 1.0, Tesla long 1.6); Omni View long 0.3. On EN long-form, subs per
1k rises with retention (AVP quartiles 0.85 → 1.52 → 1.80 → 2.20; AVD over
100 s converts 2.84 against 1.06 at 45-70 s). Short subscriptions follow
views, not watch-through (flat across AVP quartiles).

## 2. Retention — what the content explains

**A single average-view-percentage snapshot is not age-neutral.** EN
long-forms read 1.6% at age ≤ 2 days, 7.8 at 7-9, 14.4 at 14-20 (n=402): a
new video's first views are Shorts-feed taps that leave in seconds. So the
Oct 13 (story breaks), Oct 17 and Oct 20 (map sentence) slates cannot be
judged on retention until about Oct 30, and the Oct 13-16 window's 9.6%
median is exactly what the age table predicts. The fix shipped here records
AVP and AVD by age in `api/youtube_early_reach.json`
(`scripts/track_early_reach.py`, first observation wins), so a change is
scored at a fixed age the way reach already is.

Age-controlled (≥ 7 days old, within-show z) features of EN long-form:

- **Length.** AVP falls with duration (Spearman −0.24) while AVD is flat at
  ~70 s: viewers watch about seventy seconds whatever the length. Band
  medians: 6-8 min AVP 15.7, 91 views, 32 of 76 subs (n=96); 8-10 min 13.0;
  10-12 min 10.7; 12-15 min 9.2, 1 sub (n=13). Every minute past ~8 is
  unwatched by the average viewer and costs AVP. The 4.6 script arms run
  20-35% longer. ⚠️ Length is digest-side by rule; this is a reading, not a
  lever to pull at the script.
- **The hook.** A digit in the spoken hook: AVP 14.7 vs 12.1, views 96 vs
  38 (the hook is the title, thumbnail and Short source). 19-22 words best
  (14.8); ≤ 14 words worst (11.8). Identity line arriving before 10 s (a
  short, generic hook) 11.0 vs 14.5 at 10-12 s. No question hooks exist
  (0 of 139; the prompt bans them).
- **MIT's disclaimer block.** Four spoken sentences between the identity
  line and the first story end at 30.6 s median; 41% of MIT long-forms have
  an average view duration shorter than that (peers 10%); MIT AVP 8.7
  against 13.7 on the six peer news shows. Compliance placement — operator
  decision (the Oct 4 review flagged the same block).
- **Sunday.** FF's recap-first Sundays held 22.2 AVP against 11.5 on
  weekdays (n=7/46); other shows flat; MIT's weekend mode worse (4.5 vs 8.6).
- **Not supported by the data:** story-break beats (z −0.46 equals the age
  artefact), fact cards (more cards, lower z), motion vs stills (different
  shows and dates; the Oct 18 alternation reads 37.1 vs 41.7 at n=16/13),
  chapter count, commas per 100 words, `$`/`%` in titles.

**The Short's furniture.** EN hook Shorts (n=491): AVP 59.6, AVD 16 s of
35, 1.76 subs per 1k. The hook ends at 6.9 s median, "This is <show>,
episode N" at 11.0 s; in 30% of hook Shorts the average viewer has left
before the show is named. Since Oct 20 the map sentence lands inside the
Short: furniture ends at 17.5 s (was 11.1), and on 10 of 16 the first story
fact arrives at 14-29 s of a ~31 s clip. An acronym spelled letter by letter
as the first word ("N H T S A", "J W S T", n=55) reads AVP 36.1 / 14 views
against 46.0 / 22 for a proper noun. A digit in the hook: AVP 54.0 vs 44.8,
views 26.5 vs 19.

## 3. Pipeline defects — verified in code, fixed here (render / metadata)

**D1 — a sub-10 s chapter anywhere voids the whole block.** YouTube
activates seek-bar chapters only when every chapter runs ≥ 10 s.
`_format_chapter_block` clamped or prepended an Intro for the FIRST chapter
and never looked past it. Replay on the last 400 committed chapter files:
259 rendered a valid block before, 392 after; 141 carried a later gap under
10 s — Tesla's "Tomorrow Teaser" sits 7-9 s before "Closing" on every
episode, "Introduction" at 10 s is followed by "Top Stories" at 19 s. Now
`_merge_short_chapters` drops the chapter whose span is too short (the
earlier one of the pair, since its span ends where the next begins) and the
0:00 anchor is never moved; titles are never rewritten. 59% of long-forms
since Oct 10 shipped with no seek-bar chapters and no chapter title in the
player.

**D3 — the long-form description.** Rendered for Tesla Ep644: the hook as
line one and again as the template body's first line (the template began
with `{hook}`); "🎧 Subscribe to … on the Nerra Network" and "🌐 Show page"
carrying the identical URL; "🔔 Subscribe on YouTube" as the fifth block,
below the ~150-character fold; and the tail "—\nSuggested pinned comment:\n…"
— operator text shipped to every viewer since July. Now: hook, then the
YouTube subscribe line as the second paragraph, hashtags, the story bullets,
one website line, the discovery line, the body; the template no longer
carries `{hook}` and a show template that still opens on it is deduped;
the comment is posted by run_show, never printed in the description.

**X links — the funnel rule, broken on the one surface @teslashortstime posts
from.** The Tesla, Omni View, FF, Planetterrian, MIT and generic teaser
branches hand-built `https://nerranetwork.com/blog/<slug>/epNNN.html` with no
tag. GA4 shows the result: one t.co session in 28 days and no `x` campaign
row. Every teaser link now goes through `engine.funnel.episode_link`
(`kind="post"`, `placement=body`, `source=x`) via `run_show._x_episode_link`;
MIT's performance-page link through `network_link`. The `_build_teaser` body
is guarded against a bare blog URL.

**D4 — the tier-C long-form probe could never promote a show.** The weekly
probe (`engine.youtube_policy`) renders one long a week so a shorts-only
show can re-earn long-form, but `compute_tier` needed four longs inside 14
days before reading `long_vpd`, and a weekly probe yields at most two. The
door was one-way: Planetterrian's probe longs converted 13.2 subscribers per
1,000 views (EN median 2.1) and the show sat on tier C for a month. Now
`LONG_PROBE_MIN_VIDEOS` = 2: with long OFF, two probe longs whose average
clears the channel floor turn it ON; they never turn it off, and a show
with long ON still needs four to be read at all.

**Retention by age** — see §2; `avp_by_age` / `avd_by_age` on every record.

**Checked and NOT true:** `api/gallery_retention.json` carries a populated
`by_kind` block (short and long, 10-video floor, five top and bottom tags
each) on every show; the "dead flywheel" reading was of a different field.
Retention curves exist for 28 videos only (the fetcher pulls the top five
longs per channel), which is a measurement gap, not a defect.

## 4. Pipeline defects — operator decisions

**D2 — the Short-to-long funnel is dark while the Short earns its views.**
The Oct 17 release schedule publishes the hook Short at 7:00 ET + 15 min per
rank and the long-form at 12:00 / 18:00 ET. While the long is private the
Short's description links the website and the "▶ Full episode" comment is
queued until the long goes public (12:41 ET at the earliest). Measured on
242 EN Shorts: 67% of a Short's day-7 views arrive by day 2, 97% by day 3,
and the Short's AVD is 16 s. The design works as specified; the fix
reverses an operator direction. Options: publish the long at the Short's
slot (or 30 minutes after it) and move the second wave to a second Short,
or publish the long unlisted at 7:00 and public at noon. Code:
`release_schedule.LONG_FIRST_WAVE`, `run_show._long_hidden_from`.

**X points nowhere.** Of the 102 posts @nerranetwork queued Oct 10-24 and
their 34 full-episode replies, 0 carry a URL and 0 mention YouTube; the
native Short plays on X, so its watch time is X's. Intended by the Oct 10
cost decision ($0.20 a link post against $0.015). The lever: a `kind='link'`
reply under the Short carrying the funnel-tagged YouTube long-form URL,
timed after its `publish_at` — ~$24/mo for the four YouTube flagships, ~$115
for all 19 shows. Also: Tesla's "Watch on YouTube" line never fires (the
post goes out 06:30-06:45 ET, the long publishes 12:30 ET); the Short reused
on X carries YouTube's SUBSCRIBE end card pointing at nothing
(`_render_x_only_clip` has the end-card-free path); PT and UC's
`x_long_form` delivers 1 reply in 13 because tier C skips the long render;
no read-back of X impressions exists (`api/x_posts.json` was never built);
X spend is absent from the cost rollup; Vancouver's X slot is 15:30 Pacific.

## 5. What would earn more time on the videos and more subscribers — ranked

Render and metadata (no audio), in order of expected effect:

1. **Make the Short link the long-form in the morning** (D2, operator).
2. **Chapters that YouTube shows** (D1, shipped): 59% of long-forms regain
   seek-bar chapters and player chapter titles.
3. **A persistent subscribe pill on the Short from ~3 s** ("Subscribe ·
   <show> daily") beside the end card that half the viewers never reach (EN
   Short AVD 16 s on a 32-35 s clip; end card the last 3 s).
   `video._short_form_filter_graph`, `generate_shorts_end_card`.
4. **Per-show playlists as the subscribe target, and series branding** on
   the thumbnail (show colour bar and wordmark). Per-show channels would
   split 531 subscribers twelve ways and cannot be created by API — do not.
   Flag the podcast playlists in Studio (landmine #15; dp_pod and age_of_ai
   have no `podcast_playlist_id`).
5. **The description's first two lines** (D3, shipped).
6. **A long-form open card (0-5 s)**: show wordmark, date, the three map
   stories as text — the render twin of the spoken map. *Inferred.*
7. **Protect channel-level signals**: the dead-Shorts tier already drops
   Shorts under 10 views at age 3; the long dimension now has an honest
   two-probe floor both ways (D4, shipped).
8. **Spread the Shorts beyond 7:00-9:15 ET**: Sunday, Thursday and Saturday
   publishes earn more at age 3 than Tuesday and Friday (weak).
9. **Retention curves for every long** (the fetcher takes the top five per
   channel) so levers 3-6 can be scored.

Spoken (⚠️ AUDIO — A/B-listen; operator decisions):

- **Cut the Short's furniture.** The identity line and the Oct 20 map push
  the first fact to 17.5 s of a 32 s Short. A render rule can cut the clip
  from the hook's end to the first story's start using the Whisper word
  times (the long-form keeps its spoken map); or the map moves after the
  first story. The Oct 20 map is also measurable on its own in two weeks
  with the age-matched retention now recorded.
- **MIT's four disclaimer sentences** before the first story (compliance
  placement; AVP 8.7 against peers 13.7; 41% of its viewers leave inside
  them).
- **Hooks with a figure and a proper noun first**; no acronym spelled letter
  by letter as the first word.
- **Length**: the 6-8 minute band carries the most views and subs; digest-
  side only, by rule.

X (operator):

- The funnel-tagged YouTube link reply under the Short on the flagships.
- Tesla to clip mode with the same reply, or the direct post queued after
  the long publishes.
- The X copy without the YouTube end card; render the long-form for X on
  tier-C days (the `video_podcast_render_only` precedent); a nightly read-
  back of public metrics; Vancouver's slot on Pacific.

## 6. Measurement defects noticed

- No snapshot on Aug 6, 10, 11; the Sep 16 snapshot is partial (committed
  before the `snapshot_regression` guard); excluded.
- `traffic_day_series` exists from the Sep 24 snapshot, so the source
  split starts Aug 25 — there is none for the August RU peak.
- `early_reach` covers videos published from Aug 30; August needs the
  stored snapshots.
- 67 indexed videos have no Analytics row in any snapshot (likely deleted
  or private; nothing records why).
- `api/youtube_policy.json` carries `hook_short_d3_median_21d: null` for every
  RU and FR show (the dead-Shorts tier is EN-only), so the policy file is not
  a reach instrument for the two channels that lost the most.
- The hook-motion A/B is unreadable: 2-3 stills controls per show.
- Retention curves exist for the top five longs per channel only.

## 7. Scoring

The register entry `youtube-x-review-2026-10-24` reads out on 2026-11-14:
the share of long-forms whose rendered chapter block is valid (replay 392
of 400 against 259); `long_form_median_avp_en_14d` read at a fixed age from
the new `avp_by_age` field; the first `x` campaign rows in GA4; the long
dimension readable on Planetterrian / FPD / UC within two probe weeks. RU
reach is a Studio question, not a pipeline one; it is not a target here.
