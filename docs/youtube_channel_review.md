# Nerra Network channel review

Written before the next manual Tesla workflow run, so the dynamic-visuals
(PR #253) and burned-in captions + Pexels slideshow (PR #254) changes are
in `main` but the only videos uploaded so far (Tesla 452 long+short,
Fascinating Frontiers 59 long, Tesla 453 long) predate them. The next
upload will be the first true test of the new look.

Couldn't open Studio to take fresh observations during this pass (Chrome
extension wasn't responding); recommendations below are grounded in the
repo state + everything we've configured. Flagged with **[verify in Studio]**
anything that needs eyeballs before acting on it.

## What's working

- Channel + branding live for both Nerra Network (`UC0eJVxnEBaSKLU1Hg7IaVig`)
  and Nerra RU (`UCNJ11EtU_KOlOoY_GQh_5sQ`); banners, avatars, About
  copy, links, contact email all set on both.
- OAuth pipeline working end-to-end. Tesla 452, Tesla 453, Fascinating
  Frontiers 59 successfully uploaded with the right title format,
  description, `containsSyntheticMedia=true`, and playlist-add (PR after
  the playlist-add brief).
- Phone-verified the Nerra Network brand channel, which unlocks both
  custom video thumbnails (kills the recurring `403 thumbnails.set`
  warning) AND the "Set as podcast" feature.
- 10 podcast playlists created via API with full bilingual
  descriptions, the IDs are in `shows/*.yaml`, and the pipeline now
  adds each upload into its show's playlist.
- Two engineer PRs shipped after our planning briefs:
  - **#253:** keyframe spacing fix (kills "video can't play"), Ken
    Burns + showcqt visualization, branded pill, first-frames hint
    text, hook caption on Shorts.
  - **#254:** burned-in captions on long-form, Pexels slideshow of
    on-topic scene images instead of a single static cover.

## Operator-only work, in priority order

These don't need engineering — they need you in Studio or on YouTube.

### Today

1. **Finish "Set as podcast" for the 8 EN playlists.** You phone-verified
   Nerra Network but the modal needs a thumbnail upload per playlist
   and Chrome's CDP blocks me from driving it. Mapping table is in the
   previous message — `~/Tesla-shorts-time/assets/covers/<file>.jpg`
   for each. After all 8 are done they'll appear in the Podcasts tab
   and YouTube Music will start indexing them.

2. **Flip Tesla to public.** `shows/tesla.yaml` still says
   `privacy_status: unlisted`. Edit to `public`, commit, push. Next
   cron run (or your next manual trigger) publishes for real. Sister
   shows `fascinating_frontiers` and `models_agents` are already
   `enabled: true` but also still `unlisted` — flip them once you've
   reviewed one Tesla public-mode upload and confirmed nothing
   embarrassing slipped through.

3. **Confirm the new Tesla 454 upload actually shows the new visuals.**
   Manually trigger the `tesla` workflow from Actions, wait ~20 min,
   then open the resulting watch URL. Check:
   - Long-form has visible motion throughout (Ken Burns zoom on the
     scene slideshow, showcqt frequency bars at the bottom)
   - Long-form has burned-in captions
   - Long-form plays through to the end without the "video can't
     play" error
   - A custom 1280×720 thumbnail appears (now that the channel is
     phone-verified — first time we'll see this working)
   - The "Photos via Pexels" attribution shows up in the description

### This week

4. **Record a channel trailer.** New visitors to
   `youtube.com/@NerraNetwork` see no trailer right now, which makes
   the channel look unfinished. A 30-60 second intro that says what
   the network is, names the 8 shows, and CTAs "subscribe + check
   out the playlist for the topic you care about" is high-leverage
   and one-time. Upload as a regular video, then in Studio →
   Customization → Layout, set it as the "Featured video for new
   visitors".

5. **Configure the channel layout.** Studio → Customization → Layout.
   Add sections in this order:
   1. Featured video (your trailer)
   2. Latest videos
   3. Shorts shelf
   4. "All shows" — playlist row containing all 8 podcast playlists
      (you'll need to add them once "Set as podcast" is done in step 1)

6. **Set a video watermark.** Studio → Customization → Branding →
   Video watermark. Upload the existing `assets/youtube/nerra_network_logo.png`
   scaled to ~150×150. Show "Entire video" for max recall.

7. **Set channel-wide defaults.** Studio → Settings → Channel → Basic info:
   - **Country:** Canada
   - **Channel keywords:** `nerra network, ai narrated podcast, daily
     podcast, tesla podcast, ai podcast, space podcast, science
     podcast, investing podcast` (these don't appear publicly but
     help discovery)
   Then Studio → Settings → Upload defaults:
   - Description default: a one-line note that all videos are AI-narrated
   - License: Standard YouTube License
   - Comments: "Hold potentially inappropriate comments for review"
   - Sort comments by: Top comments (not Newest)
   - **Notify subscribers** on upload: ON (default)

8. **Block obvious comment-spam terms.** Studio → Settings → Community
   → Automated filters → "Blocked words". Add at minimum: telegram,
   whatsapp, +1, contact me, dm me, click my, link in bio, signal, btc,
   eth wallet, crypto giveaway, free money. AI-narrated podcast comments
   are a magnet for this stuff. Use the "Hide users" list as you spot
   repeat spammers.

9. **Nerra RU phone verification — decide.** You've used one of the
   two-per-year verifications on this phone (when creating @NerraRU).
   To enable podcast playlists + custom thumbnails on Nerra RU you
   need a second verification slot. Options:
   - Use a Google Voice number (free, instant — recommended)
   - Use a partner/family member's number (counts against THEIR yearly
     limit)
   - Wait until the year resets (when did you first verify? probably
     April-ish, so April next year)
   The 2 RU shows can still upload videos and the playlists exist;
   they just won't appear as podcasts in YT Music until the brand
   channel is verified.

### When you cross 100 subs

10. **Claim the custom URL.** Once you hit 100 subscribers + 30 days +
    a profile picture + a banner (you have all three already), YouTube
    lets you claim the bare `youtube.com/c/NerraNetwork` URL alongside
    the `@NerraNetwork` handle. Studio nudges you when eligible.

### When you cross 1,000 subs + 4,000 watch hours

11. **Apply to the YouTube Partner Program (YPP).** Studio → Earn →
    Apply. Required for monetization, end screens to link to external
    sites, Super Chat, channel memberships. Approval normally 1-4 weeks.
    The review reads your channel description and contact email
    (`patrick@planetterrian.com`), so make sure both are clean.

12. **Hook up AdSense** for monetization revenue. Studio walks you
    through it after YPP approval.

13. **Enable Shorts monetization separately** — Studio → Earn → Shorts.

## Engineering brief — paste into Claude Code

Save the section below as a new file (or use it inline). It's
self-contained — Claude Code has everything it needs.

> **Brief: Nerra Network channel polish — phase 1**
>
> Channel is live and uploading daily across 8 EN shows. Two recent PRs
> (#253 dynamic visuals + #254 captions + Pexels slideshow) make the
> videos look professional. This brief packages the next round of
> polish — none of these are show-stoppers, they're cumulative quality
> + growth improvements. Ship them as separate PRs (one per numbered
> item) so each can be reverted independently if it goes wrong.
>
> ### 1. Hashtags in long-form descriptions
>
> YouTube shows the first 3 hashtags from a description above the
> video title. Right now `engine.video_metadata.build_long_form_metadata`
> renders the description without hashtags. Add a hashtag block
> immediately after the hook and before the chapter list:
>
> ```python
> hashtags = [f"#{tag.replace(' ', '').replace('-', '')}"
>             for tag in config.youtube.tags[:3]]
> description = f"{hook}\n\n{' '.join(hashtags)}\n\n{digest_body}\n\n..."
> ```
>
> Drop them on Shorts too — they already render `#Shorts`, just append
> the 3 show tags. Test: `tests/test_youtube.py` — assert that the
> first non-empty line of the description's first 200 chars contains
> three hashtags.
>
> ### 2. First-line CTA in description
>
> Add a single line at the very top of every long-form description:
>
> ```
> 🎧 Subscribe + listen on the podcast: https://nerranetwork.com/<show>.html
> ```
>
> The URL comes from `config.publishing.web_url` or similar — wire
> from the existing show YAML if not there. Don't add the CTA to
> Shorts (mobile users won't read it; the description preview is
> two lines at most).
>
> ### 3. Auto-pin a chapter-list comment on each long-form upload
>
> Right after the successful video upload in `_publish_youtube`,
> add a single API call that posts a comment with the chapter list
> + a "Reply with topics you want covered" prompt, then pins it.
>
> New helper in `engine/youtube.py`:
>
> ```python
> def post_and_pin_comment(*, credentials, video_id: str,
>                         text: str) -> bool:
>     """Post a top-level comment on the video and pin it.
>
>     Uses commentThreads.insert + comments.setModerationStatus (the
>     latter is what "pinning" maps to). Best-effort: returns False
>     on any 4xx/5xx, logs the error, does NOT raise.
>     """
> ```
>
> Quota: 50 + 50 = 100 units per video. Worth it for the engagement
> boost; pinned comments get ~10× more replies than unpinned ones.
> Make this gated by `config.youtube.pin_chapter_comment: bool =
> True` so a show can opt out.
>
> ### 4. Schedule uploads instead of publishing immediately
>
> Daily cron currently uploads as soon as the pipeline finishes —
> for Tesla that's around 7:55 UTC, 0:55 AM PT, 3:55 AM ET. Publishing
> "instantly at random times" is suboptimal for the algorithm; better
> to upload immediately but schedule the public release for the same
> time every day.
>
> In `engine/youtube.py:upload_video`, accept a `publish_at:
> datetime | None = None` kwarg. When set, pass
> `status.publishAt=ISO8601` and force `status.privacyStatus="private"`
> in the insert body. YouTube schedules it for the future timestamp
> and surfaces it as "Scheduled" in Studio.
>
> Wire `config.youtube.publish_at_hour_utc: int | None` per show
> (default `None` = publish immediately). For Tesla, set `13` (= 6 AM
> PT, 9 AM ET — peak commute window for the audience). Compute
> `today at HH:00:00 UTC`; if that's already in the past, push to
> tomorrow.
>
> ### 5. End screens via the API
>
> YouTube end screens (5-20 sec at the end of a video pointing to
> another video / playlist / subscribe button) are the single
> highest-leverage way to grow watch time, but Google's YouTube
> Data API does NOT expose them. There's an undocumented internal
> API the Studio UI uses, but it's brittle.
>
> Instead, two things you CAN do:
>   - **In-video CTA overlay:** Reserve the final 8 seconds of the
>     rendered MP4 for a Pillow-composited end frame: channel logo,
>     "Subscribe", "Next episode" thumbnail, the show name. Use
>     ffmpeg's `concat` filter to splice it in after the main content.
>     Add to `engine/video.py:build_long_form_video`.
>   - **Cards via API:** YouTube cards are partially supported via
>     `videos.update` with `recordingDetails` — but most card features
>     also aren't exposed. Skip this for now.
>
> Implement the in-video CTA overlay as the deliverable. Test:
> `pytest tests/test_video_commands.py` should assert the long-form
> command chain contains a `concat` segment.
>
> ### 6. Save the video ID into the per-episode metadata
>
> Currently we log the watch URL but don't persist it. Save it into
> `digests/<slug>/<base>_youtube.json` alongside the existing
> credit-usage / chapters / metrics files:
>
> ```json
> {
>   "long_form": {"video_id": "AM43XgHNrtc", "url": "...", "uploaded_at": "..."},
>   "short":      {"video_id": "VL93dtY5fWU", "url": "...", "uploaded_at": "..."}
> }
> ```
>
> Two reasons:
>   - The management dashboard can render "latest YouTube uploads"
>     per show without API calls.
>   - When the analytics pull comes (#7) we know which video IDs
>     to fetch.
>
> Wire into the existing `engine.metrics` write path; don't add a
> new write step.
>
> ### 7. YouTube Analytics → management dashboard
>
> Add a daily-cron-only step that pulls view counts + watch time +
> avg-view-percentage per uploaded video, joins on the JSON written
> in #6, and renders a "YouTube performance" panel in
> `management.html`.
>
> Use the YouTube Analytics API (`youtubeAnalytics.v2.reports.query`
> with `metrics=views,estimatedMinutesWatched,averageViewPercentage,subscribersGained`).
> 1 quota unit per dimension+metric query — basically free.
>
> Auth note: the existing `YOUTUBE_REFRESH_TOKEN_EN` already has
> the `youtube` scope which covers analytics for the channel's own
> videos. No new OAuth grant required.
>
> ### 8. Backfill historical episodes — scaffolding only
>
> Don't do the actual backfill in this PR. Just write the script
> at `scripts/backfill_youtube.py` that, given a show slug + an
> episode-number range, walks the existing MP3s + transcripts in
> `digests/<slug>/`, runs them through the existing video build +
> upload pipeline, and stops at the per-day quota limit.
>
> Quota math: 451 Tesla episodes × 3,400 units = 1.5M units —
> impossible within the current 10k/day. So the script writes a
> resumable checkpoint to `digests/<slug>/_backfill_state.json`
> and the operator runs it daily for ~150 days, OR waits until the
> YouTube quota extension is approved (parked task #8).
>
> Don't enable this script in CI; it's an operator-run admin tool.
>
> ### 9. Comment moderation hook
>
> When a viewer comments on one of our videos, we currently see
> nothing. Add `engine/youtube_moderation.py` that polls
> `commentThreads.list` for our recent uploads, classifies each
> comment with a quick LLM call ("spam? question? feedback? hate
> speech?"), and posts the classification to Slack (or emails it
> to `patrick@planetterrian.com`).
>
> Daily run via the existing cron. Free quota-wise (5 units per
> commentThreads.list).
>
> ### 10. Localized titles + descriptions for the 2 Russian shows
>
> `config.youtube.default_language: ru` is set on `finansy_prosto`
> and `privet_russian`, but the title and description we build in
> `video_metadata.py` are still English-style ("Ep 023: ..."). For
> Russian shows, use the existing Russian show-name + Russian hook
> already in the digest output.
>
> The pieces are already there in the `digests/finansy_prosto/*.md`
> files — just plumb them through. Test: assert the description of a
> Russian-show video contains Cyrillic characters and the title is
> in Russian.
>
> ### Out of scope for this brief
>
> - Channel trailer (operator-only — produce the video themselves)
> - YouTube Music distribution verification (operator opens YT
>   Music and confirms; no engineering)
> - YPP application (operator + Google, not us)
> - A/B thumbnail testing (Studio feature, no API)
> - Channel watermark, channel keywords, country, comment defaults
>   (Studio settings — operator)
>
> ### Acceptance for the whole brief
>
> - 10 separate PRs, one per numbered item, mergeable independently.
> - Full test suite stays green at each step.
> - For each PR, the operator can do exactly ONE thing to verify:
>   manually trigger the `tesla` workflow and check the resulting
>   upload (or the dashboard, for #7).

## Long-term ideas worth considering

These are bigger and need a real product conversation before any
engineering commits. Listed for completeness, not for immediate action.

- **A second AI host per show** — most successful AI-narrated podcasts
  use 2-voice conversation; the back-and-forth keeps attention better
  than monologue. ElevenLabs has the voices; the prompt change to
  dialogue is the heavier lift.
- **Vertical-video-first shows** — Shorts get the algorithmic boost
  right now. A dedicated `tesla_shorts_only` show that publishes 3
  × 55-second clips a day on the topical hook is cheap to add and
  probably outperforms the long-form per dollar of ElevenLabs spend.
- **YouTube Membership tiers when YPP lands** — $4.99/mo for the
  ad-free MP3 feed + a 24-hour-early access to each episode. The
  pipeline already produces both; just gating delivery is the work.
- **Email digest of the week's videos** — a Friday "everything Nerra
  Network published this week" newsletter. Pulls from the dashboard
  data, sends via the existing Buttondown integration.
- **Pin-board mode** — instead of YouTube, mirror the long-form audio
  to Spotify, Apple Podcasts, Overcast via RSS (we already publish
  RSS feeds at the repo root). One-time `rss → spotify-for-creators`
  submission per show; then the existing RSS feed automatically
  propagates new episodes.
