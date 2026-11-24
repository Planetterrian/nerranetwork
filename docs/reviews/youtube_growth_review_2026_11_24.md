# YouTube growth review — where the growth is, and what the first seconds show (2026-11-24)

Operator ask: a deep analysis of the YouTube pipeline, the analytics and
what is newly possible, to grow viewers and subscribers much faster than the
last few months, then build what will do it and make it measurable. Follows
[`youtube_review_2026_11_14.md`](youtube_review_2026_11_14.md). Read from
`api/youtube_stats.json` (Nov 24 03:10 UTC), `api/youtube_channel_history.json`,
`api/youtube_early_reach.json`, `api/youtube_policy.json`, the committed
scripts and transcripts, and the live channel and four videos watched in a
browser on Nov 24.

## 1. The trend: English is slowing, Russian is the growth

Net subscribers and views, last four weeks against the four before
(`api/youtube_growth.json`, new):

| Channel | Subscribers | Net subs, 4 wk | Prior 4 wk | Views, 4 wk | Prior 4 wk |
|---|---|---|---|---|---|
| EN @NerraNetwork | 586 | 46 | 67 | 30,827 | 37,930 |
| RU @NerraRU | 307 | 50 | 28 | 48,908 | 29,596 |
| FR @NerraFR | 87 | 8 | 18 | 7,727 | 9,399 |

EN gained 35-40 subscribers a week in August, about 20 in September, 15 in
October and 11 now. RU, with three shows and no long-forms on two of them,
now adds more subscribers and 60% more views than EN with fifteen.

## 2. Same episode, different channel

The hook Short is the one clip all three channels cut from the same place
in the same episode. Median views at three days old, last 28 days:

| Show | EN | FR | RU |
|---|---|---|---|
| Fascinating Frontiers | 7.5 | 34 (4.5x) | 213 (28x) |
| SpaceX Daily | 25 | 13.5 | 100.5 (4x) |
| Tesla Shorts Time | 31 | 26 | 59 (1.9x) |

The RU Short is not the better video. For FF Ep259 the EN Short opens on
on-topic Milky Way imagery with a punch title; the RU one opens on an
aurora over a satellite dish from the library, and has 1,138 views against
a handful. Average view percentage is the same (EN 56%, RU 60%). The
difference is the room: English science and news Shorts is the most crowded
feed on YouTube; Russian is not. **The same pipeline output earns 4-28x in
a language with less competition.** That is the largest lever in the data
and it is a decision (section 6).

## 3. Why the EN channel stalls

- **Viewers leave in the first half minute.** Median of 141 EN long-form
  retention curves (Sep 16 - Nov 21): 0.85 at 10 s, 0.63 at 20 s, 0.47 at
  30 s, 0.29 at 60 s. Views from home and the subscriptions feed (the
  largest source, 12,750 in 28 days) average 16 seconds watched; search
  (8,921) averages 21. Suggested is the only source that watches (78 s).
- **The Nov 8 card and pill did not move it.** 0.46 at 30 s before, 0.48
  after, on 82 and 50 curves. They render correctly; they are not the leak.
- **Seconds 8-22 are the identity line and the map.** A viewer who clicked
  "Starlink Satellite Drops 12 km Then Climbs Back" hears the hook, then
  the show's name and number, then a list of other stories and section
  names ("then the Counterpoint and the Engineering Deep Dive"), and only
  then the story. The audience falls from 0.85 to 0.63 across exactly that
  stretch. The hook Short lost 2.5 s of average view duration to the same
  sentence and got it back when the map was cut (Oct 30).
- **SpaceX Daily, the largest show, opened every video on stock footage.**
  `_interleave_broll_into_schedule` put the first evergreen clip *before*
  the first scene. SpaceX is the only show with a b-roll pool (7-second
  NASA DART night-launch clips), so every SpaceX long-form since August
  spent its first 7 seconds, the hook, on a bright plume and then an empty
  brown frame; the episode's own scene arrived at 0:08
  (`youtube-growth-2026-11-24/spacex_opening_before.png` in the project
  files). SpaceX is also the only flagship below 0.95 at 5 s (0.93) and
  the lowest at 10 s (0.80; Tesla 0.83, Models & Agents 0.89, AI Chips
  0.96). The stated rule since Sep 9 was that the opening slot draws from
  the episode's fresh scenes; the b-roll interleave ran after that guard.
  Tesla's opening, watched the same way, is on-topic from the first frame.
- **The channel page is fifteen unrelated shows and their duplicates.**
  The Videos tab on Nov 24: fire-bricks, peat bogs, GTA 6, gene therapy,
  Mercury, TSMC, Rohingya, gold, each at 0-9 views, with the RSS copy of
  the same episode ("Ep 241: Franco-Nevada raised its 2026 guidance…") a
  row below (`en_channel_videos_tab.png`). In 28 days eight shows (FF,
  Beginners, MAG 7, Omni View, MIT, UC, FPD, Planetterrian) published 171
  of the channel's 293 long-forms for 26% of long-form views and 4 of 26
  subscribers; their median long-form has 4-19 views. SpaceX, Tesla,
  Models & Agents and AI Chips carry the rest. The audience is 99.6% male
  and 38% over 55: one audience, served a daily Tesla video and a daily
  window-tax history under one name.
- **The RSS copies are still being created**: 257 in the last 35 days,
  about nine a day, each a second upload of an episode already on the
  channel with a truncated title. Removing the RSS podcasts in Studio has
  been the operator's item since Nov 16.

## 4. The instrument that never ran

`api/youtube_reach.json` has read nothing since Nov 14. Every night, on
all three channels: HTTP 403, "YouTube Reporting API has not been used in
project 141610975484 before or it is disabled". The Analytics API has no
impressions or click-through, so thumbnails and titles are still being
judged blind, and the Nov 29 readout of `youtube-reach-instrument-2026-11-14`
is a MISS as it stands. One click in Google Cloud fixes it; the script now
says `api_disabled` with the link instead of `error`.

## 5. Built in this pass

| Change | What it does | How it is read |
|---|---|---|
| **Evergreen b-roll never opens a long-form** | The first picture is the episode's own first scene; a stock clip follows a still. Fixes SpaceX from its next episode. | SpaceX retention at 5 s and 10 s (0.93 / 0.80 before), `api/youtube_stats.json` curves. |
| **The long-form opens on the story (A/B)** | `youtube.long_form_skip_map: ab`: on odd episode numbers the YouTube long-form is rendered from a copy of the mix with the map spliced out (8-11 s). Captions, scene cuts, fact cards and the description's chapters read the same spliced timeline; the "Coming up" card is left out; the Apple video item omits the audio's chapters and transcript. The episode, its feed audio and its podcast chapters keep the map. | `api/youtube_growth.json` `long_form_map_ab`: retention at 30 s and 60 s, average view duration and subscribers per 1,000 views at age 7 by arm; a verdict only at 20 curves an arm. Register `long-form-skip-map-2026-11-24`, readout Dec 15. |
| **`api/youtube_growth.json`, nightly** | The three tables above (weekly trend per channel, the same hook Short across channels, the A/B) and whether the reach instrument is blocked. No API call. | It is the readout. |
| **Reach status** | `api_disabled` with the enable link. | `api/youtube_reach.json` `channels.*.status`. |

Replay of the map finder on every English episode of Nov 1-24: a map is
found and cut on 21 of 25 SpaceX, 21 of 24 Tesla, 22 of 24 Models & Agents,
23 of 24 AI Chips, 24 of 24 MAG 7 episodes (median cut 7-11 s, never over
17.3 s); UC and FPD have no map and are in neither arm. Any failure renders
the long-form from the episode as before.

## 6. Decisions for the operator

1. **Enable the YouTube Reporting API** (Google Cloud, project
   141610975484, free). Nothing can test a thumbnail or title on
   click-through until this is on.
2. **Remove the RSS podcast copies in Studio.** Nine duplicate uploads a
   day on the channel being judged.
3. **More languages, Shorts first (recommended).** The RU result says
   where the same output reaches people. In order of cost: (a) add the
   shows that travel, Planetterrian and Unintended Consequences, to the RU
   and FR dubs, Shorts-only, about $0.20 an episode per language, no new
   account; (b) a Spanish channel for FF, SpaceX and Tesla
   (`docs/lang_youtube_dubs.md` is the recipe; needs a new channel and its
   OAuth token); Portuguese after it. Each is seeded shorts-only and earns
   long-forms through the existing policy.
4. **Narrow what the EN channel carries.** Options: keep everything
   (today); long-forms only for the four shows that are watched, the rest
   Shorts-only on EN; or a second EN channel for the science and history
   shows (FF, Planetterrian, UC, FPD), the way RU is in effect an FF
   channel. The second is reversible in one YAML line per show and is the
   recommendation; it also halves the daily upload count.
5. **Finance shows on video.** A sibling thread reports a July 2026 YouTube
   rule withholding monetization from AI personas giving finance views,
   judged over a channel's last 30 uploads. Not verified here against
   YouTube's own policy page; if it holds, MIT, MAG 7 and Prediction
   Markets on the EN channel are a reason for option 4 before any Partner
   Program application (EN is at 586 of 1,000 subscribers).

## 7. Next, once the instruments read

- With impressions and CTR: thumbnail punch text. Today's read "650 LBS PER
  1000", "28 LAYERS TWICE", "ONE SHOT, 2 MONTHS": a number without its
  subject, and every show in the same white type with a 10-pixel show
  label. Test subject-first punch text and a per-show colour band on CTR.
- The RU and FR Shorts take library pictures that do not match the story
  (aurora for a galaxy). They win anyway; matching them is cheap upside.
- A realistic generated likeness of a named person (Musk at a desk, SpaceX
  Ep172 at 0:20 and 0:45) is labelled "AI" by YouTube today. Worth a rule
  in the scene briefs before a policy makes it one.
