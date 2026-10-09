# Network improvement review — October 9, 2026

Operator brief: after the runner upgrade, a thorough review of what else
would improve the shows, reach, audience, efficiency and ROI. Five
read-only investigations ran against the committed data (audience and
reach, funnel and revenue, cost and efficiency, episode quality,
distribution surfaces); every number below names its file. Two defects
found on the way were fixed in the same PR (§8).

## 1. The network in one paragraph

8,430 RSS downloads in 30 days, three straight up-weeks (+18% last week),
and 83,000 YouTube views a month. Five shows carry 79% of the downloads
and SpaceX alone 42%; it is the only show with a real first-week audience
(119 downloads per episode). Measured revenue is **$0** against about
**$330–380 a month** of tracked spend (up from $110–125 in July — the
thirteen-show launch cohort added the difference). The site saw 377
sessions in 28 days, 17 of them from search; six sessions in a month could
be attributed to any of the 932 videos published. Twelve newsletter
subscribers, none tagged to a show or a source. Paid Nerra Personal
members: unknown, because the token that counts them is not set. Nothing
the network makes is being lost; almost nothing it makes is being
measured on its way to a listener, and nothing is being sold.

## 2. Audience and reach (`api/audience_headline.json`, `api/op3_history.json`, `api/youtube_early_reach.json`)

| | 30d | share | notes |
|---|---|---|---|
| spacex | 3,510 | 41.6% | +29% WoW, 119/episode first week, Apple 3 ratings, 570 Spotify streams |
| tesla | 1,229 | 14.6% | +27% |
| models_agents | 984 | 11.7% | flat |
| models_agents_beginners | 561 | 6.7% | +19% |
| planetterrian | 339 | 4.0% | +118% (back-catalogue sweep, see §7) |
| omni_view / first_principles / nerra_daily | ~255 each | 3% each | |
| modern_investing | 219 | 2.6% | −77% WoW |
| launch cohort (7 of 13 measured) | 70 total | 0.8% | 1–2 downloads per episode, no growth since Sep 23 |
| unindexed by OP3 | — | — | ai_chips, mag7, omni_view_north_america, offshore_north, collingwood |

Language feeds earn **outside** that 8,430: FR 1,462 and RU 420 in 30 days.
Fascinating Frontiers' French feed (448) out-earns its English one (139).

YouTube: EN is at its early-August level and rising (+38% over four
weeks, 495 subscribers); RU has fallen 60% in four weeks (the Sep 22
distribution finding, still unexplained); FR −45%. Hook Shorts at age 3:
FF-RU 358, Tesla-EN 99, FF-EN 69, SpaceX-RU 68 — and under 10 on UC, DP
Pod, MAB, MIT, Omni View and Planetterrian, which are all in the
weekly-probe tier already. RU Shorts are 47% of views and the worst
subscriber converter (0.8 per 1,000 views; FR Shorts 2.7, EN long 1.3).

## 3. Funnel and revenue (`api/funnel.json`, `api/ga4_stats.json`, `api/buttondown_stats.json`, `api/member_metrics.json`)

- 83,293 views → **6** attributed sessions → 0 measured signups.
  `attribution_coverage_pct` 1.6. The RU SpaceX lander, built for the
  highest-reach surface, took 2 sessions from 7,157 views.
- GA4 traffic: Direct 62% (bot-shaped: Singapore is 94 of 267 users),
  YouTube referral 39, LinkedIn 20, Google 15, ChatGPT 7, newsletter 6.
  `/age-of-ai.html` is the most-viewed page (89 views) and has no video
  presence.
- **No first-party signup surface is instrumented**: the footer form and
  `join.html` fire no GA4 event on success (`assets/js/footer-subscribe.js`
  only fires on the Soft Personal path; `tracking.js` binds
  `newsletter_signup` to a Buttondown embed form only `show_page_dp_pod`
  still carries). So "0 signups" means unmeasured, not zero: the count went
  3 → 12 since July, +7 of them between Sep 17 and 30.
- Paid members, MRR, donations, book sales: all null. `PERSONAL_ADMIN_TOKEN`
  is unset (`member_metrics.json` `configured: false` since Sep 21); the
  Stripe referrer shows one returning user; the two $7.99 books have no
  sales record anywhere and their KDP/Apple/Kobo links are empty in the
  volume YAMLs.
- Capacity (`docs/industry_benchmarks.yaml`): at 8,430 downloads a month,
  podcast ads are worth $100–840 a month depending on slot and rate; one
  host-read slot ≈ $210–420. Only the top of that range clears the burn.
  The network currently sells zero ads and has no sponsor page with
  numbers on it.

## 4. Cost and efficiency (`digests/*/credit_usage_*.json`, `metrics_ep*.json`, Actions API)

Tracked 14-day spend $145 → ~$311/month (dashboard 7-day pace $361);
untracked callers (weekly newsletters, the Grok review runner, Voices,
restock) add $10–20. Lines per month: TTS $72, images $60, digest/script
LLM $58 ($35 of it the grok-4.7 cohort — a 4.7 digest call costs 2.5× a
4.3 one), search/fetch $55, multilingual $54, motion clips $11.

Per episode: median $0.36, Fascinating Frontiers and Tesla $0.70 (13 Grok
images, a motion clip, 6–7 search calls), Nerra Daily $0.09. Cost per
download $0.028.

Runner time: ~2,000 job-minutes a day, free on a public repo (≈$480 a
month if it were private). **1,220 of those minutes were the multilingual
workflow sweeping all seven shows on every successful show run** —
`workflow_run.head_commit` never named the show, so the narrowing added
in September never fired; 92 "Multilingual: …" commits on Oct 7. Fixed
in this PR (§8). Long-form render: median 1,002 s, p90 1,258 s; YouTube
publish is ~72% of a flagship's wall time.

Waste with numbers: structural digest regeneration on 37% of episodes
(+$11/mo); 16:9 and 9:16 scenes on shows whose Shorts earn under 10
views (+$10/mo); search calls at 7–9 per episode on cohort shows with
4–23 downloads (+$13/mo if capped at 3–4); FR feeds on M&A/FPD/EI that
OP3 cannot see ($11/mo — submit to Podcast Index before deciding); ZH
switched off today ($11.5/mo). The 14 recovery PRs this month cost
~$7 of re-production and ~6 runner-hours that the ledger cannot see
because reruns overwrite the same credit file.

## 5. Episode quality, Sep 30 – Oct 8 (`metrics_ep*.json`, `api/daily-review.json`)

The split that has held all week: **the grok-4.7 cohort writes (4–13%
verbatim, 12–20 verified claims per episode); every grok-4.3 script
copies (34–72%, 0–3 claims)**. Spoken-text gate: every transcript-bearing
episode passed; 42 episodes ran blind (Sep 30 and Oct 8, the PyAV days).

Worst five, with the failure mode:

1. **Unintended Consequences** — reads the brief aloud (72%), 0 verified
   claims in every episode, two gate skips in two days, reviewer 4.5/10,
   23 clipped "…" chapter titles in the window. The research step and the
   chapter rules merged today address exactly this; Ep1 is the readout.
2. **Fascinating Frontiers** — 62–77% of its 1,700-word target on 7 of 8
   episodes, one skip at 905 words, overlap 63%, "Repetitive" and
   "Incoherent" criticals on Ep215.
3. **Planetterrian** — 9 flagged claims (7 unreachable sources), 62–68%
   of target on 4 of 9, stories told twice (petal, oyster).
4. **Modern Investing** — lowest reviewer median (4.5), six recurring
   frames ("before we wrap watch" 9/9), 71–76% of target on 4 of 9.
5. **MAB** — coverage 26–48% (drops half the digest), 3 items shipped
   without a source.

Best: Vancouver, AI Chips, Prediction Markets, OV Asia Pacific,
Collingwood — all grok-4.7 cohort shows with 12–18 verified claims and
near-target length. Cross-show: `frame_memory` records no metric, so the
Sep 30 frame work cannot be scored; "to really understand how" is still
9/9 on Omni View. Reviewer warnings in two days: 50 "below target", 21
"factual errors", 16 "incoherent" (garbled transitions: "On the case on
both sides", "ex A I", "pdfu").

Overdue scoring: **15 experiments past readout still `reading`** (the
oldest, `grok-47-staged-migration`, due Sep 25) and **583 ledger
predictions `pending`** on reviews ≥ 14 days old. The register is the
network's memory; unscored, it is a list.

## 6. Distribution (`docs/podcast_directories.md`, `shows/network_meta.yaml`, `api/dashboard.json` → distribution)

- **Twenty live feeds are findable only on nerranetwork.com**: Apple
  pending ×13, Spotify pending ×15, Amazon 0 of 30, YouTube Music 0 of 30,
  Pocket Casts 0, iHeart 0. No cohort show has an `apple_url` or
  `spotify_show_id`, so their pages render no Apple/Spotify chip and
  `fetch_apple_ratings` covers 15 of 31 shows. Offshore North's Apple
  listing is still a draft (artwork refused Oct 4, fixed, needs Refresh
  Feed + Publish).
- **X posts from 7 of 31 shows** and nothing records whether a post
  succeeded (`x_post_duration_s` only). SpaceX — the largest show — Nerra
  Daily, Age of AI and all 13 cohort shows post nothing. GA4 shows
  LinkedIn referrals and no X-attributed session.
- **Instagram/TikTok is built and has never run** (tokens unset; the
  safe-zone MP4s and sidecars are produced and discarded on Tesla and
  SpaceX).
- **Age of AI's YouTube upload has never happened**: `youtube.enabled`
  since Sep 20, no `digests/age_of_ai/youtube_videos.json`, and
  `maybe_publish_youtube` swallows its own failures. The network's
  most-visited page has no video.
- SEO plumbing is sound (JSON-LD, hreflang, 2,546-URL sitemap, `llms.txt`
  — AI-assistant referrals already exceed email). Organic search is 17
  sessions because the links do not exist, not because the markup is
  wrong; no Search Console read exists in `api/`.

## 7. Measurement defects found (two fixed here)

1. **The committed `api/youtube_stats.json` lost the FR channel this
   morning.** `verify-youtube-analytics.yml` runs on any push that touches
   it (the runner upgrade did), carried EN and RU tokens only, and wrote
   whatever the fetch returned: no `channels.fr`, 474 fewer videos. The
   nightly's `snapshot_regression` would have refused it; the verify
   script never asked. **Fixed** (§8); tonight's nightly restores the block.
2. **Every successful show run swept all seven multilingual shows**
   (§4). **Fixed** (§8).
3. The trailing-7-day OP3 figure (3,013) exceeds every complete week and
   the lift is back-catalogue (finansy_prosto 128/7d against ≤3 on any
   listed episode; Привет 64; env_intel 46): a crawler or catalogue sweep,
   written into `op3_history` under "2026-10-05" as if it were a week.
   Next week's +300/+800% WoW rows are that artifact. Read the complete
   weeks only.
4. `youtube_channel_history.json` did not append on Oct 9; the FR channel
   has no snapshot in `youtube_stats.json` `channels` until the nightly.
5. First-week medians rest on 2–3 episodes per show (OP3 lists only top
   episodes): the zeros on FF, OV, MIT and FPD are sample artifacts.

## 8. What was changed in this PR

- `verify-youtube-analytics.yml` carries the FR token and
  `scripts/verify_youtube_analytics.py` applies `snapshot_regression`
  before writing (guard `tests/test_verify_analytics_snapshot_2026_10_09.py`).
- `multilingual.yml`'s resolve step reads the triggering run's jobs
  (`run (<show>)`) and sweeps only the shows that published; `actions:
  read` added; the head-commit match stays as the fallback (guard in
  `tests/test_multilingual.py`).

## 9. Recommendations, ranked by what they move against what they cost

**Reach (operator, no code) — the largest lever on the list**

1. **Finish the directories for the 20 unlisted feeds** (Apple ×13,
   Spotify ×15, Amazon, YouTube Music, Pocket Casts, iHeart; Podcast
   Index for the five OP3 cannot see). Record `apple_url` and
   `spotify_show_id` in each cohort YAML / the registry so the pages grow
   their chips and ratings become measurable. About two hours; it is the
   only item here that reaches listeners who have never heard of the site.
2. **Publish Offshore North on Apple** (Refresh Feed + Publish) — a real
   niche audience with a draft listing.

**Money (operator + small code)**

3. **Instrument capture**: fire `newsletter_signup {list, source}` on the
   footer/join success branch, add `gallery_subscribe` to
   `CONVERSION_EVENTS`, set `PERSONAL_ADMIN_TOKEN`, paste the KDP and
   Books2Read URLs into the volume YAMLs. Until this is done, every
   revenue number stays null and no growth experiment can be read.
4. **Put a sponsor page up with the real numbers** (8,430 downloads/30d,
   SpaceX 3,510 and 119 first-week, 83k YouTube views, 796 subscribers)
   and one host-read slot on SpaceX at the benchmark rate. The audience is
   small but the SpaceX number is in the top quartile per episode; the
   asking price is $210–420 a month, which is the burn.

**Shows (code; each changes audio — A/B-listen Ep1)**

5. **Script stage on grok-4.6 for Fascinating Frontiers and Planetterrian**
   next, on a GATE: PASS from the SpaceX arm (Oct 23). The data says the
   model is the lever; FF and PT are the worst two 4.3 flagships on
   overlap (63%, 61%) and length.
6. **Length is digest-side**: raise `min_digest_words` / per-item floors
   on FF, PT, OV LatAm, OV North America, MIT, where
   `podcast_script_word_count / target` sits at 72–82%. Never a
   podcast-side retry (banned).
7. **Score the register and the ledgers**: 15 experiments and 583
   predictions overdue. Half a day of reading; the next review is blind
   without it. Add a `frame_memory` metric (`recent_frames_count`) so the
   Sep 30 frame work can be scored at all.

**Efficiency (code, no audience cost)**

8. **Done here**: the multilingual sweep (−17 runner-hours/day, −90
   commits/day, fewer push races).
9. **Cut the structural regeneration rate** (37% of episodes, OV 12/14,
   FPD 11/14, Tesla 8/13): read the validator's reasons per show and fix
   the format mismatch at the prompt. ~$11/mo and a faster slate.
10. **Imagery on probe-tier shows**: `short_scenes_per_episode` 5 → 2 and
    no 16:9 set where the Short earns under 10 views (FPD, PT, UC, DP Pod,
    MIT, OV). ~$6–10/mo. End the hook-motion clips if the Oct 13 readout
    is flat (~$11/mo).
11. **Cap `web_search_queries` at 3–4** on vancouver, ai_chips, mag7,
    peptides, longevity, offshore_north (7–9 calls per episode for 4–23
    downloads). ~$13/mo; the risk is a thinner source pool on a thin day.
12. **Submit the M&A / FPD / EI French feeds to Podcast Index** before
    deciding their $11/mo; a feed OP3 cannot see is not a feed with no
    listeners.

**Distribution (code, small)**

13. **Turn X on for SpaceX, Nerra Daily and Age of AI**, and record an
    `x_posted` outcome so the channel can be read — today a silent
    failure on all seven posting shows would show nothing.
14. **Verify the Age of AI YouTube path** (one episode, by hand) and
    record landmine #15 completion per show; the Studio "podcast" flag is
    verified only on SpaceX.
15. **Instagram/TikTok tokens** only after 1, 13 and 14: the pipeline is
    ready but unproven, and the measured surfaces come first.

What I would not do: pause the cohort (its cost is the audience the
launch exists to build, and its shows are the best-written on the
network), cut TTS or flagship imagery (the product), or add another
prompt pass to the 4.3 flagships (three passes moved nothing; the model
did).
