# Operator checklist — October 10, 2026

Every open item that needs the operator, ranked by return on the time it
takes. Each item says why it is worth doing, exactly how, and whether Claude
can do it once you say go. State checked against `main` at 850848c9 on
2026-10-10. Decisions already made are not listed: the spoken AI disclosure
stays as it is (operator, 2026-10-10).

## Tier 1 — minutes each, every episode or every new listener

### 1. Listen to the first episodes after the listener-noise merge

- **Why:** Planetterrian/nerranetwork#1403 was merged on 2026-10-10. It
  removes engagement counts, the minute a post went up and the closing-price
  tape from every show, and caps the filler quotas, from the next run on.
- **How:** A/B-listen the first MAG 7, Tesla, Fascinating Frontiers and
  Planetterrian episodes after the merge (landmine #17). Revert by git if one
  sounds worse.

### 2. Finish the directory listings (the only lever that reaches people who have never heard of the network)

- **Why:** 20 live feeds are findable only on nerranetwork.com. The 13
  launch-cohort shows were submitted to Apple, Spotify and Amazon on Oct 3
  and still read PENDING. None is in Podcast Index, which is how OP3 measures
  downloads, so five shows read "not indexed". Nerra Daily (~255
  downloads/30d) has never been submitted anywhere. Offshore North's Apple
  listing is a draft.
- **How, about two hours:**
  1. **Apple** (podcastsconnect.apple.com): for each of the 13 cohort shows,
     open the show and publish it if approved, or fix what the review flagged.
     For Offshore North, click "Refresh Feed", then "Publish". Add Nerra Daily
     as a new show with `https://nerranetwork.com/nerra_daily_podcast.rss`.
  2. **Spotify** (podcasters.spotify.com): confirm the 15 pending shows and
     add Nerra Daily.
  3. **Amazon** (podcasters.amazon.com): click the confirmation email for each
     Oct 3 submission, then add Nerra Daily.
  4. **Podcast Index** (podcastindex.org/add, about a minute each): the 13
     cohort feeds, Offshore North, Nerra Daily, and the three French-only
     feeds (`models_agents_podcast.fr.rss`, `first_principles_podcast.fr.rss`,
     `env_intel_podcast.fr.rss`). Feed URLs are in
     `docs/podcast_directories.md`.
  5. **Send Claude the IDs.** Each Apple listing URL ends in `id<number>`;
     each Spotify URL contains the show id. Claude adds `apple_show_id` and
     `spotify_show_id` to each show YAML, which puts the Apple and Spotify
     buttons on the show pages, turns on the nightly Apple ratings read, and
     updates the tracker table.
- **Optional, same sitting:** Pocket Casts (pocketcasts.com/submit) and
  YouTube Music (Studio → Settings → Channel → Advanced → Podcast RSS feed)
  for the five largest shows.

### 3. Move Planetterrian, Unintended Consequences and First Principles to the newer script model

- **Why:** the model is the one measured quality lever. SpaceX's script stage
  ran on grok-4.6 for the first time on Ep126: 7% of the script copied from
  the digest. On the same day Planetterrian copied 77%, Unintended
  Consequences 71% and First Principles 69% — they read their briefs aloud.
- **How:** say go. Claude adds `podcast_model: grok-4.6` and `stream: true`
  under `llm:` in the three show YAMLs, registers the experiment and opens a
  PR. Extra cost is a few dollars a month.
- **Caution:** SpaceX's arm has one completed run. Waiting for two or three
  more (by about Oct 12) is the cautious path. ⚠️ AUDIO — A/B-listen each
  show's first episode.

## Tier 2 — under an hour each, turns unmeasured money into numbers

### 4. Set the membership token so paid members are counted

- **Why:** `api/member_metrics.json` has read "not configured" since Sep 21,
  so paid Nerra Personal members and MRR are unknown, not zero.
- **How:** GitHub → repository Settings → Secrets and variables → Actions →
  New repository secret. Name `PERSONAL_ADMIN_TOKEN`; value is the same
  admin token set on the gallery Worker. If you never set one, run
  `npx wrangler secret put PERSONAL_ADMIN_TOKEN` in `workers/gallery` with a
  long random string, then paste the same string into GitHub. The nightly
  fills the file.

### 5. Measure newsletter signups (Claude, code)

- **Why:** the footer form and `join.html` fire no analytics event on
  success, so "0 signups" in the funnel report means unmeasured. The
  subscriber count went 3 to 12 since July and nothing recorded where any
  came from.
- **How:** say go. Claude fires `newsletter_signup {list, source}` on both
  success paths, adds `gallery_subscribe` to the conversion events, and adds
  a guard.

### 6. Paste the book store links

- **Why:** both live books have empty Amazon, Apple Books, Google Play and
  Kobo buttons, and no sale is recorded anywhere.
- **How:** in `books/volumes/unintended_consequences_collected.yaml` and
  `books/volumes/first_principles_collected.yaml`, fill `amazon`,
  `apple_books`, `google_play` and `kobo` under `buy_links` with each store's
  listing URL. Or send the URLs and Claude commits them. `/books.html` picks
  them up on the next regeneration.

### 7. Turn on X posting for Nerra Daily and The Age of AI

- **Why:** the code shipped Oct 9 and skips silently without credentials.
- **How:** in the X developer portal, create an app for @nerranetwork with
  read and write access. Add four repository secrets:
  `NERRANETWORK_X_CONSUMER_KEY`, `NERRANETWORK_X_CONSUMER_SECRET`,
  `NERRANETWORK_X_ACCESS_TOKEN`, `NERRANETWORK_X_ACCESS_TOKEN_SECRET`. The
  next edition posts; `x_posted` in its metrics confirms.

### 8. Fix The Age of AI's YouTube upload (Claude, code)

- **Why:** `/age-of-ai.html` is the most-visited page on the site, and the
  show has never uploaded a video. The Ep10 publish log says why: the
  publisher looks for the waveform video at `…/age_of_ai/raw/video/<name>.mp4`
  and gets a 404, because the audio URL it derives from sits under `raw/` and
  the produce step uploads the video elsewhere.
- **How:** say go. Claude fixes the derived path, and adds a one-off backfill
  that uploads Ep8 to Ep12.

### 9. Put a sponsor page up with real numbers

- **Why:** the network has $0 revenue against about $330–380 a month of
  spend. SpaceX alone earns 3,510 downloads a month and 119 per episode in
  its first week, which is enough for one host-read slot at roughly
  $210–420 a month — about the burn.
- **How:** Claude can build `/sponsor.html` from the committed audience files
  (downloads, first-week median, YouTube views, subscribers), with a contact
  link. You decide the rate and answer the email.

## Tier 3 — scheduled reads and quality passes (Claude does the work, you approve)

### 10. Score the overdue experiments, then act on what they say

- **Why:** 17 register entries are past their readout and unscored, the
  oldest from Sep 25. The next review is blind without them.
- **How:** say go. Two actions follow from the readouts:
  - **Oct 13, spoken-open experiment:** score it, then add
    `_shared/hook_shape.txt` to Omni View, Models & Agents, Modern Investing
    and Env Intel (the control shows) if the arm won. ⚠️ AUDIO.
  - **Dub spoken-text gate** (readout was Oct 6): move the RU/FR/ES gate from
    shadow to enforce if the calibration read is clean.

### 11. One ask in the closing, with a sibling show that fits the topic

- **Why:** closings run 100–200 words with four to six asks, and the sibling
  plug is a date rotation (Tesla plugged the Latin America desk).
- **How:** say go. Claude cuts the closing to one ask and picks the sibling
  from each show's `related_show`, keeping the Nerra Daily promo-cut anchors
  working. ⚠️ AUDIO.

### 12. Stop the same story twice on Nerra Daily, and deep dives that re-tell the lead

- **Why:** Nerra Daily splices every show, so a story covered by Omni View
  and a desk plays twice. Planetterrian told its aspen story three times.
- **How:** say go. Claude wires the existing sibling-coverage note into the
  news shows and adds a lead-overlap check to the deep dives that rides the
  existing structural regeneration. ⚠️ AUDIO.

### 13. Cost trims, about $20–30 a month

- **How:** say go. Claude cuts portrait scenes on probe-tier shows (Shorts
  under 10 views) from five to two, ends the hook-motion clips if the
  Oct 13 readout is flat, and caps web searches at three or four on the
  smallest cohort shows.

## Tier 4 — confirm once, or decide later

14. **Confirm the Worker deploys.** In each of `workers/scheduler`,
    `workers/voices` and `workers/gallery`, run `npx wrangler deploy`. Then
    open the scheduler Worker's root URL and check that its `slots` list has
    every show. Skip any you already deployed after Oct 9.
15. **French-only feeds** on Models & Agents, First Principles and Env Intel
    (about $11 a month): after item 2's Podcast Index submissions, wait two
    complete weeks of OP3 data, then switch off any that read zero
    (`multilingual.languages` in the show YAML).
16. **Age of AI newsletter tag:** the Ep10 send refused because Buttondown
    has no "The Age of AI" tag. It is created automatically when the first
    person subscribes from that show's page, so this needs no action unless
    you want to tag existing subscribers by hand in Buttondown.
17. **Modern Investing benchmark recompute:** run
    `scripts/recompute_mit_benchmarks.py --apply` only if you want the
    published performance numbers rewritten (the corrected dry run reads
    −3.35% alpha across 42 trades).
18. **Russian disclosure:** the two Russian shows speak the English AI
    disclosure. Localizing it changes audio; A/B-listen first.
19. **Age of AI chapter rows:** Supabase `editorial_packages.chapter_markers`
    still holds the three fabricated chapter lists removed from the site.
    Delete those three rows' chapter markers in the Supabase table editor.
20. **Instagram and TikTok tokens:** built and dormant. Worth setting only
    once the podcast audience is larger.
21. **Git history rewrite** (2.2 GB of old MP3s): needs a paused-cron window
    and invalidates every clone. Not urgent.
