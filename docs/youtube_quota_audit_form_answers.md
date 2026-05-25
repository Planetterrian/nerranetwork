# YouTube API Audit & Quota Extension — form answers

Copy-paste these into the form at
https://support.google.com/youtube/contact/yt_api_form?hl=en

Fields marked **[YOU FILL]** need your PII or a file upload — I left those
for you. Everything else is ready to paste verbatim.

Submit while signed in to the Google account that owns the GCP project
(patricknovak1@gmail.com).

---

## Reason for filling this form

Select: **"I am completing a Compliance Audit or requesting additional
API quota"**

## General Information

- **Your full legal name:** Patrick Novak
- **Your organization's name:** Nerra Network
- **Your organization's website:** https://nerranetwork.com
- **Your organization's address:** **[YOU FILL — your address]**
- **Organization contact email address:** patrick@planetterrian.com
- **Google representative email address:** (leave blank)
- **Content Owner ID:** (leave blank)

**Describe your organization's work as it relates to YouTube** (100–1000 chars):

```
Nerra Network is an independent, single-operator podcast network
(sole proprietorship, Patrick Novak) that publishes daily news-and-
education podcasts. Each episode is editorially curated and written by
the operator from primary news sources, then narrated with AI voice
synthesis (ElevenLabs) and rendered to video. We publish to two YouTube
channels: Nerra Network (English) and Nerra RU (Russian). YouTube is a
primary distribution surface — every daily episode is uploaded as a
long-form video plus a Shorts clip, organized into per-show podcast
playlists. All AI-synthesized narration is disclosed via the
containsSyntheticMedia flag on every upload and a written disclosure in
every description.
```

## API Client Information

- **Have you undergone an audit since June 2019?** No
- **Is there any way your client's use of the YT API changed since the
  last audit?** No
- **Please provide details on how API Client's usage has changed:**
  ```
  Not applicable — this is our first audit. No prior audited usage to
  compare against.
  ```
- **Please list all your API Client(s):** Nerra Network Publisher
- **Project numbers for each API Client:** 141610975484
- **Is this a publicly or privately available API Client?** Internal use
  only
- **Please provide details on how API Client accesses the YouTube Data
  API:**
  ```
  The client is an internal, server-side automation (Python, running in
  GitHub Actions on a daily cron). It is not a consumer-facing app. It
  authenticates once per channel via OAuth 2.0 (offline refresh tokens
  for the two channels we own) and calls videos.insert, thumbnails.set,
  captions.insert, playlists.insert, and playlistItems.insert to publish
  each day's episodes. No end users interact with the client; it only
  ever writes to the two YouTube channels owned by the operator.
  ```
- **Where can we find each API Client(s)?**
  ```
  The client publishes to our own channels (it has no public UI):
  Nerra Network: https://www.youtube.com/channel/UC0eJVxnEBaSKLU1Hg7IaVig
  Nerra RU:      https://www.youtube.com/channel/UCNJ11EtU_KOlOoY_GQh_5sQ
  Network site:  https://nerranetwork.com
  ```
- **Demo account / login instructions:**
  ```
  No login required — both channels are public. The client itself is an
  internal automation with no user-facing interface to demo. Example
  uploads it produced are visible on the channels above.
  ```
- **Does your API Client commercialize YouTube Data?** Yes
  - (Reason if asked: the channels will participate in the YouTube
    Partner Program for ad revenue once eligible; no YouTube data is
    resold or exposed to third parties.)
- **Choose the option that best resembles your API Client's use case:**
  YouTube video uploads
- **List other use cases:** (leave blank, or "Automated podcast
  publishing")
- **Specify all YouTube API Services used by this API Client:** Data API
- **Select the primary audience for your API Client:** Strictly internal
  use only
- **Approximately how many users use your API Client?** 1
- **Explain how your API Client is used by your users:**
  ```
  There is a single user: the operator (Patrick Novak). The client runs
  unattended on a daily schedule and uploads that day's podcast episodes
  to the operator's own two YouTube channels. There are no other users
  and no third-party access.
  ```
- **Does your API Client use multiple projects to access YouTube APIs?**
  No
- **Please list all project numbers:** 141610975484
- **Does this API Client create, access or use any metrics derived from
  YouTube data?** No
- **Does this API Client display data from, or provide features/services
  across, multiple platforms?** No
- **Do you create/provide any type of reports using YouTube API Data?**
  No
- **How long do you store YouTube API Data?** <24 hours
- **How often do you refresh YouTube API Data?** Never
- **Does this API Client allow users to authenticate with their Google
  credentials?** Yes
- **Please provide more detail on how many users have authenticated, and
  how authenticated data is used:**
  ```
  Only the operator's own account is authenticated (one OAuth grant per
  owned channel, two total). The authenticated credential is used solely
  to upload videos, thumbnails, captions, and playlist memberships to the
  operator's own channels. No other users authenticate; no authenticated
  data is stored beyond the in-run upload.
  ```
- **Upload supporting documents / screencast:** **[YOU FILL]**
  - A 1–2 minute screen recording is the strongest evidence. Record:
    your terminal triggering the GitHub Actions workflow, the run log
    showing a successful `videos.insert`, and the resulting video live on
    the Nerra Network channel. Export as a single file < 10 MB (trim /
    compress if needed). If you'd rather not record, attach a PDF with
    2–3 screenshots: (1) the GitHub Actions run log, (2) the YouTube
    Studio Content tab showing uploaded episodes, (3) a published video
    page with the "Altered or synthetic content" label visible.

## Quota Request Form

- **Which API Client are you requesting a quota increase for?**
  Nerra Network Publisher
- **What API project number?** 141610975484
- **Which YouTube API Service(s)?** Data API
- **How much "Additional Quota" are you requesting?** 190000
  - (= 200,000 total needed − 10,000 current default)

**Justification for requesting additional quota** (200–1000 chars):

```
We publish daily podcast episodes across 11 shows on two owned channels.
Each episode is uploaded as a long-form video plus a Shorts clip. Per
episode the client spends ~3,800 units: 2x videos.insert (3,200) +
2x thumbnails.set (100) + captions.insert (400) + 2x playlistItems.insert
(100). At full rollout that is 11 shows x ~3,800 = ~41,800 units/day for
steady-state daily publishing alone. The 10,000-unit default caps us at
2 shows; 9 built-and-ready shows are blocked. We are also backfilling
~450 historical Tesla episodes (and back-catalogs for the other shows)
into YouTube, which needs substantial temporary headroom. We request
200,000 units/day to cover daily publishing for all shows plus a steady
historical backfill, with margin for the digest-retry days that
occasionally double our LLM/API round-trips.
```

**Explain in detail how you use YouTube API Services today** (200–1000 chars):

```
Today the client runs on a daily GitHub Actions cron. For each enabled
show it: (1) renders a long-form MP4 (cover + audio waveform + Pexels
scene slideshow + burned-in captions) and a 55-second vertical Shorts
clip; (2) calls videos.insert (resumable upload) for each, with
status.containsSyntheticMedia=true and a written AI disclosure in the
description; (3) calls thumbnails.set with a per-episode 1280x720
thumbnail; (4) calls captions.insert to attach an SRT track to the
long-form; (5) calls playlistItems.insert to add both videos to the
show's podcast playlist. We currently run only 2 of 11 shows (Tesla
Shorts Time + Models & Agents for Beginners) because the default quota
cannot support more. Daily usage today is ~7,600 units, right against
the ceiling.
```

**What functionality would your API client be lacking without more
quota?** (200–1000 chars):

```
Without more quota we cannot enable the 9 remaining shows that are
already built, configured, and producing audio daily — they publish to
podcast RSS, our website, and email, but cannot reach YouTube. We also
cannot backfill the ~450 existing Tesla episodes (and other shows'
back-catalogs) that exist as published podcast episodes but are absent
from YouTube, which fragments the listener experience and forfeits
YouTube's podcast/discovery surfaces for our archive. In short, the
quota cap freezes the network at 2 of 11 shows on YouTube and blocks any
historical catalog import.
```

**What potential workarounds would you use to compensate for less
quota?** (200–1000 chars):

```
We already mitigate within the cap: only 2 shows are YouTube-enabled,
Shorts upload is scheduled on alternating episodes for some shows, and
the pipeline estimates quota cost and logs a warning before exceeding it
so a run skips rather than fails mid-batch. If a smaller increase is
granted we would stage rollout — enable shows in batches and run the
historical backfill slowly over many months with a resumable checkpoint
— but daily steady-state for all 11 shows fundamentally needs ~42k
units/day, so any grant below that forces us to permanently leave some
shows off YouTube.
```

## Acknowledgements — **[YOU FILL]**

Check all three boxes yourself after reviewing:
- I have read and agree to the YouTube API Services Terms of Service…
- I agree (demo account terms) — applies only if you provided a demo
  login; we did not, so this is moot but check it if required.
- The above facts are true to the best of my knowledge…

Then **Submit**. A copy emails to patrick@planetterrian.com. Approval
typically takes a few days to a few weeks; Google may reply with
follow-up questions — answer promptly, they often close applications
that go quiet.

---

## After you submit

- Don't flip any more `youtube.enabled: true` until the increase is
  granted — doing so produces `quotaExceeded` failures in CI (predictable,
  not a bug). The `test_only_tst_and_mab_enable_youtube` drift guard in
  the repo enforces this.
- When the grant email arrives, flip the 9 remaining shows' YAMLs to
  `enabled: true` in batches (validate one upload each at `unlisted`
  first, then `public`), and kick off the historical backfill with the
  `scripts/backfill_youtube.py` scaffold from the channel-review brief.
