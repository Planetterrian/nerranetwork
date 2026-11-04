# YouTube audit — the pipeline end to end, and the two shows it was missing (2026-11-04)

Operator ask: check the full YouTube pipeline and its analytics, and make it
work as well as it can for viewers and subscribers. Follows
[`youtube_review_2026_10_30.md`](youtube_review_2026_10_30.md) and the
YouTube sections of [`network_review_2026_11_03.md`](network_review_2026_11_03.md);
the Shorts title and layout work is a separate thread and is not touched
here. Read from `api/youtube_stats.json` (Nov 3 22:21 UTC),
`api/youtube_policy.json`, `api/youtube_channel_history.json`,
`api/audience_headline.json`, `api/dashboard.json` and the per-episode
`digests/<show>/metrics_ep*.json` of the last six episodes of every EN show.

## TL;DR

1. **The pipeline is working.** Every EN show uploaded what its policy
   asked for on each of its last six episodes (long-form, hook Short,
   caption track, end card, subscribe pill, scheduled release); no upload
   error is recorded. The nightly analytics fetch is fresh (Nov 3).
2. **Where growth comes from.** EN runs ~1,000 views and ~3 net subscribers
   a day (554 subscribers). Over 28 days: subscriber-feed 16.9k views,
   search 8.0k, Shorts feed 3.9k, suggested 2.8k. Long-forms published since
   Oct 7 earned 17.8k views and 27 subscribers (95 per video); Shorts 5.4k
   and 5. SpaceX alone is 7.7k of the long-form views.
3. **The one structural gap: 13 of the network's shows have never been on
   YouTube.** The launch plan (`docs/new_shows_plan_2026_09_22.md` §7) said
   "after four weeks of RSS data, AI Chips and MAG 7 may join the EN channel
   at one Short each". Six weeks on, nothing had done it, and the reason they
   were held (EN at ~24 uploads a day against a 30 ceiling) no longer holds:
   EN uploads ~13 a day since the one-Short cap. **Shipped here** (see §3).
4. **Retention-curve coverage**: 3 of 99 EN longs since Oct 20 carry a
   curve. Not a fault: the "curve for every long" change (0505c457b) merged
   at 04:58 UTC Nov 4, after the Nov 3 nightly. Tonight's nightly is the first
   run; check `curve_fetched_at` on Nov 5.

## 1. What the long-forms show

Retention, median of the 12 EN longs with a curve (Sep 16 - Oct 26): 87% of
viewers at 10 s, 45% at 30 s, 30% at 60 s, 17% at 2 min. The spoken opening
is already tight (hook, then "This is <show>, episode N", then one map
sentence, then the lead story, voice from t=0), so the 10-30 s drop is not
an audio preamble. The next read is per-second against the picture once
tonight's curves land; nothing is changed on the evidence of 12 videos.

Audience: EN long-form viewers are 100% male and 100% 55+ (Analytics
28-day demographic, long-form only); the whole channel is 99.8% male. Korea
(10%) and Germany (10%) are EN's second and third countries by views, with
9.6 s and 13 s per view against 29 s for the US: Shorts-feed views that do
not watch. Unchanged by anything here; recorded for the "who is the network
for" question in the Nov 3 review.

## 2. The policy, show by show (Nov 3)

The adaptive policy is doing its job and needs no change:

- SpaceX, Tesla, Omni View: tier A (long + Short; EN cap is one Short).
- Models & Agents, MAB, FF, MIT, UC: tier B. MAB and MIT are on the weekly
  Short probe (hook-Short day-3 medians 5.5 and 2.5).
- Planetterrian, First Principles: tier C, long-form off. Their weekly probe
  longs on Oct 19 and Oct 26 drew 4 and 3 views (Planetterrian) and 3 and
  37 (FPD), under the 1.0 views/day floor, so the probe correctly kept them
  off. Planetterrian's September probes had converted well; the October ones
  did not.
- RU SpaceX and RU FF compute A on the full four-video read and will flip
  long-form back on tonight unless the operator enables the dub long
  overlay (`DUB_LONG_RELATIVE_ENABLED`, decision C17 in the Nov 3 review).

## 3. Shipped here

- `shows/ai_chips.yaml`, `shows/mag7.yaml`: `youtube.enabled: true`
  (long-form plus the hook Short; both blocks were complete with seven
  curated image queries since launch).
- `publishing.x_long_form: true` on both, like every other @nerranetwork
  clip show with a long-form (`tests/test_x_long_form_2026_10_17.py`): the
  full episode rides as a reply under the X post.
- `scripts/update_youtube_policy.py` `SEED_TIERS["en"]`: both seeded B;
  the velocity read and the weekly probes decide from there.
- AI Chips' cost breaker 8 -> 12 USD/week: text alone ran $5.38 over 7
  days, and the video adds ~13 Grok scenes and an even-day motion clip per
  episode, which would have tripped 8.0 mid-week.
- `scripts/create_youtube_playlists.py` knows both shows, so the one
  operator step (below) is a single command.
- Pins: `tests/test_schedule.py::YOUTUBE_ENABLED_SHOWS`,
  `tests/test_new_shows_2026_09.py` (Peptides and Longevity stay off).
- Register `cohort-youtube-ai-chips-mag7-2026-11-04`, readout Nov 25.

Why these two and not more: they are the plan's named candidates, their
subjects sit on the EN channel's proven audience (Models & Agents and SpaceX's
AI-compute stories, Tesla investors), and two shows are a readable test.
Peptides and Longevity stay off until a medical-content policy review; the
desks are members-only; Vancouver, Collingwood and Top World were planned
for a separate channel.

## 4. Operator items

- Create the two podcast playlists: `python3 scripts/create_youtube_playlists.py <client_secrets.json> en`
  (writes `podcast_playlist_id` into both YAMLs; until then uploads publish
  and log a warning).
- Unchanged from Nov 3, still the biggest Studio levers: the end-screen
  template on the Tesla and SpaceX long-forms, the banners and channel
  copy, and the Nov 16 removal of the RSS-ingested podcast copies that
  double every EN long-form on the channel.
- The funnel-tagged YouTube link under the X post (open since Oct 24).
