# Front page, Nerra Personal and the YouTube pipeline: what was broken, and what earns more viewers (2026-10-28)

Operator brief: review the Nerra landing page, the Nerra Personal setup and
the YouTube pipeline deeply; find what needs fixing and what would attract more
viewers, members and listeners, and make the three more appealing and more
useful.

Method: the front page and the member pages were rendered from the committed
data and screenshotted at 1440x900 and 390x844 (Playwright, real fonts, outside
requests blocked); the Personal Worker, builder and pages, and the YouTube
render, metadata and analytics paths were read by four parallel read-only
passes; every finding that led to a change was then checked by hand against the
code or the committed data. Numbers are read from committed files unless marked
*inferred*. Nothing in this pass changes shipped audio (no landmine-#17 item).
Register `landing-personal-youtube-2026-10-28`; guards
`tests/test_landing_personal_youtube_2026_10_28.py` and
`workers/gallery/test/member_security.test.ts`.

## TL;DR

1. **Nerra Personal had a security hole and broken plumbing.** Anyone who typed
   a member's email into a newsletter form got a cookie that could read and
   change that member's paid record. A member with no newsletter subscription
   could not sign in. A new member got no email and no feed until the next
   morning's build. Active members were still offered checkout, which bills them
   twice. A superseded subscription's cancel revoked the feed of the one that
   replaced it. The private feed answered neither HEAD nor byte ranges, which
   Apple Podcasts needs to play it. "Today" was the UTC date, so between 8 pm
   and midnight Eastern the feed pointed at an edition that did not exist yet.
   All of this is fixed in the gallery Worker and the builder (**operator:
   `wrangler deploy` in `workers/gallery` before the Stripe key goes on the
   Worker**).
2. **The site never linked a single episode's video.** 0 of 1,036 flagship blog
   posts carried the "Watch on YouTube" button. run_show wrote it, every site
   rebuild re-rendered the post without it, and since Oct 17 the run itself
   skipped it whenever the long-form was still scheduled. About 120 episodes
   per flagship have a public video. Every rebuild now links them from the
   show's own video index.
3. **Every RU and FR dub Short shipped without its custom thumbnail, and the
   window Shorts opened on the wrong story.** The thumbnail call passed the
   output path as the episode number and raised `TypeError` into a silent
   `except` (none of the 951 RU or 573 FR Shorts in the indexes ever got one).
   Since Oct 10, 77 RU and 55 FR window Shorts opened on the episode's lead
   headline while their audio told another story. No dub Short ended on a
   sentence. All three are fixed.
4. **The front page buried its lead and repeated itself.** The day's lead
   headline started at 1008 px on a 1440x900 screen and 976 px on a phone,
   below the fold on both; it now starts at 532 px and 759 px. Two shows
   telling one story now share one card that names both. The "Also in this
   episode" list no longer repeats the hook. Two different named papers are no
   longer one developing thread. The Personal band now names its price and
   plays the five-minute sample.
5. **What the site measured was not what it sent.** `episode_play` and
   `subscribe_click` had been sent since June and never fetched. Checkout
   starts, sample plays and clicks out to YouTube were not sent at all. All
   five are now read, so "did a visitor listen, start paying, or go to the
   video" has an answer.
6. **The member copy promised things the product does not do.** The privacy
   policy said xAI receives no personal information, while every Personal
   edition sends it the member's first name, city, subjects and note. The FAQ
   said an edition is never cut (Skip repeats and the length budget cut whole
   chapters) and that the shows have "human editorial oversight". A show page
   said a cancelled feed stops at once (it runs to the end of the paid period).
   The join page called all 26 shows free (five desks are members-only). All
   corrected.

## 1. Nerra Personal

### 1.1 Security and plumbing (Worker, `workers/gallery/src/`)

| Defect | Mechanism | Fix |
|---|---|---|
| A newsletter cookie read and edited a paid record | `/api/subscribe` issues the same `nn_gallery` cookie as the magic link, with no proof the visitor owns the address; the account, preferences and rebuild handlers trusted it | Magic-link cookies carry `v: 1` (`jwt.ts`, `handleMagic`); `mayUseRecord` (`personal.ts`) lets an unverified cookie use a record only when it created that record in the same session (`created_iat`); the account answers `verify_required` with no member data; the billing portal needs a verified cookie |
| A paying member with no newsletter could not sign in | `handleLogin` sent a link only when Buttondown knew the address | A KV member record also qualifies (`handlers.ts`) |
| New members got nothing until the next build | The Stripe activation wrote KV and stopped | Activation writes a welcome feed (the sample edition, only if no feed exists) and sends a welcome email: the feed URL, how to add it in Apple Podcasts, Overcast and Pocket Casts, and a 24-hour sign-in link (`buildWelcomeEmail`) |
| Active members were offered checkout | The account page showed both Payment Links to an active member | The checkout buttons hide when the status is active; the portal button shows instead, or a help line when the portal is not on |
| A superseded subscription revoked its replacement | `.deleted` / `.updated` did not check the subscription id | An event for a subscription other than the member's current one is ignored |
| Apple Podcasts could not play the feed | The feed handler answered GET only, with no ranges | HEAD and `Range` (offset, open-ended and suffix forms) from R2; 416 with `bytes */size`; `Accept-Ranges` |
| An evening dead zone | `todayIso()` was the UTC date | Eastern date (`build.ts`); an on-demand build (activation, "Build my edition now") falls back to the previous day when fewer than two of the member's shows have published yet (`scripts/build_personal_feeds.py`) |

Account page additions: the feed URL has a copy button and one-tap "Add to"
links for Apple Podcasts, Overcast, Pocket Casts and Castro; an unverified
visitor sees a sign-in prompt instead of an error.

### 1.2 Copy that now matches the product

* **Privacy policy:** a "Nerra Personal members: xAI" section says what Grok
  receives (first name, shows, city or cities, subjects, the note to Mira) and
  that it never receives the email address or payment details. The membership
  item lists what is stored. xAI joins the outside-Canada list.
* **Join page:** the FAQ says nothing is summarized and that Skip repeats or a
  length setting leaves out whole chapters, which Mira names. The AI answer
  matches the AI disclosure: no one reads every episode before it ships, and
  unverified claims are marked publicly. The email answer says who sees the
  address. The hero gives the price and says how many shows are free to
  everyone (21 of 26). The five desks carry a "Members only" badge. The
  stat that said there would never be ads is gone; the sponsor guard now also
  catches "no ads, ever".
* **Show pages:** cancelling keeps the feed to the end of the paid period, as
  the join page and the webhook already say.
* **FAQ:** the tiers are named as the join page sells them ($4.99 with a taste
  of your city's news; $8.99 for the full local brief and subjects of your own).

### 1.3 Membership is measured again

`scripts/build_member_metrics.py` reads the counts-only
`/api/admin/show-demand` with `PERSONAL_DEMAND_TOKEN` (already a repository
secret) when the admin token is absent. That token was never in this public
repo, so `api/member_metrics.json` had read "unmeasured" since Sep 21. Tier,
add-on and revenue figures stay null, because only the admin records carry them.

## 2. YouTube

| Defect | Evidence | Fix |
|---|---|---|
| Blog posts never link their video | 0 of 1,036 flagship posts carry the button; ~120 episodes per flagship have a public video | `engine.youtube_index.episode_video_links` (a video still scheduled is never linked; the hook Short wins over other Shorts); `generate_blog_posts` passes the links on every rebuild; a shorts-only episode links "Watch the Short"; run_show gates the Short on its own release time |
| Dub Shorts have no custom thumbnail | `generate_shorts_thumbnail(scene, out, show_name=…)` → `TypeError: missing 'date_str' and 'output_path'`, swallowed | Keyword call in `ru_dub` and `lang_dub`, with the Short's own headline; a failure now logs |
| Window Shorts open on another story's headline | 77 RU + 55 FR window Shorts since Oct 10 rendered `hook=` the episode lead | Short #1 keeps the lead; a window Short shows its own headline, or none |
| Dub Shorts cut mid-word | No dub path called `end_on_sentence` | Both dub paths end on the last sentence inside the final 8 s of the window, on the dub's own Whisper words |
| The Short thumbnail's punch text sat on the caption band | Lower-third punch on 1080x1920 | Punch text moves to the upper band with its own scrim; only the hook Short carries the episode's punch |
| Hashtags lost their acronyms | `#Ai`, `#Llm` from YAML keywords | A closed acronym list (`AI`, `LLM`, `TSLA`, `FSD`, …) keeps them in capitals |
| Retention could not be judged at a fixed age | 6 of 22 EN longs read exactly 0% at age 2 (analytics lag), frozen by first-observation-wins; tracking stopped at day 7 | A 0% with no watch time is recorded as unmeasured; long-forms are followed to day 21; `long_form_avp_en_age7_median` reads age 7 (7.1% on the Oct 27 file) beside the live-snapshot metric |

Clicks from the site to YouTube are now an event (`watch_on_youtube`, counted
in `api/funnel.json` as `visits.youtube_watch_clicks`).

## 3. The front page

* **Lead above the fold:** the kicker and headline come before the picture on
  the front page and both language hubs (`lt-lead-head`).
* **One card per story:** `engine.landing_test.merge_retellings` folds a later
  show's telling of the same story into the first card ("Also told on …").
  The Latest list keeps every episode, because it is the record of what
  published. `engine.newsroom.same_story` matches inflections, so
  "plans/planning" and "launches/launch" count as the same word.
* **No repeats inside a card:** "Also in this episode" drops any headline that
  is the hook in other words.
* **Developing threads:** two headlines that open on different paper names
  ("AlphaFold3: …" / "RoseTTAFold2: …") are never one thread.
* **Most Played** shows each episode's date; the flagship scenes are not
  printed a second time under Watch; read on a later day, the masthead's "N new
  episodes today" disappears and the edition button stops saying "today's".
* **The Personal band** names "Free for 7 days, then $4.99 a month" and plays
  the sample edition (`data-nn-sample="homepage"`). The sample URL has one
  owner (`generate_html.PERSONAL_SAMPLE_URL`).
* The launch strip's model-written mission and rocket names and the
  "Did you know" fact are escaped.

## 4. Measurement

`scripts/fetch_ga4_stats.ENGAGEMENT_EVENTS` now includes `episode_play`,
`subscribe_click`, `play_personal_sample`, `begin_checkout` and
`watch_on_youtube`. `build_funnel._visits` reports each by page on every
answer: null when the report was not read, 0 when it was read and nobody fired
the event. Every Payment Link on the join and account pages carries
`data-nn-tier`, which is what `begin_checkout` reads.

## 5. Not changed, and why

* **The homepage Personal band stays where it is.** Moving it above the
  developing stories conflicts with the flagship-first order the Oct 18 guards
  pin. The band now sells itself better where it is; a move is an operator
  call.
* **A paid upsell on the SpaceX and Tesla pages.** The only paid band is
  written for Nerra Daily ("Like this, but only your shows"). Those two pages
  carry the Soft Personal ask. A flagship-specific paid band needs its own
  copy.
* **Developing-story calibration.** Two false threads remain on the Oct 28
  data (airport stories in two different cities; daily Falcon 9 launches).
  Each fix that was tried also dropped real threads.
* **Mira's live prompt still says "free of advertising".** Changing a room
  needs a rehearsal PASS and an operator listen.

## 6. Operator items

1. `wrangler deploy` in `workers/gallery` **before** setting `STRIPE_SECRET_KEY`
   on the Worker. The security fix must be live first.
2. In Stripe: turn on the customer portal and add the
   `customer.subscription.updated` event to the webhook. Set each Payment
   Link's after-payment redirect to `https://nerranetwork.com/account.html`.
3. Ads that drive Personal sign-ups: point them at `join.html#sample`.
4. YouTube Studio: set each Short's "Related video" to its long-form. Links in
   a Short's description are not clickable, so this is the only tap from a
   Short to the episode.
5. Decide the EN scheduled-release question from the Oct 24 review. EN
   Shorts-feed views fell 61% in the week after scheduled release began on
   Oct 19 (*inferred* from the traffic day series; one week, confounded).
