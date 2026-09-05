# Nerra Voices — show notes and launch runbook

Nerra Voices (slug `nerra_voices`) is the network's second Mira-hosted live
interview show, launched September 2026 as the sister of
[The Age of AI](age_of_ai_plan.md). Same host, same pipeline, same two
human review gates; a different premise and a different audience.

Config: [`shows/nerra_voices.yaml`](../shows/nerra_voices.yaml) and the
`nerra_voices:` block of [`shows/network_meta.yaml`](../shows/network_meta.yaml)
(display order 13.5, directly after The Age of AI). Brand:
[`age_of_ai_brand.md`](age_of_ai_brand.md#nerra-voices--the-sister-brand).

## What the show is

Real people on the work they've chosen, interviewed live by Mira, the
network's AI documentarian. Founders, clinicians, tradespeople, teachers,
artists and organizers on what they do, why it matters, and what they've
learned the hard way. Every episode discloses that the host is a machine
and the guests never are; every guest approves their transcript before
anything publishes.

Opening line: *"Welcome to Nerra Voices. I'm Mira. I'm an AI, and my guests
never are."* Closing question: *"What's the one thing about your work that
you wish more people understood?"* Sign-off: *"— Nerra Voices, Nerra
Network"*. (All three live in the yaml `voices:` block and are read by
`pipelines/voices/shows.py`.)

## How it differs from The Age of AI

| | The Age of AI | Nerra Voices |
|---|---|---|
| Premise | How AI is changing a person's work and life | The work itself; AI comes up only if the guest brings it up |
| Who lands here | Guests with a real AI angle | Everyone else who pitches the network and deserves a full interview |
| Brand | Signal Violet `#7C3AED`, Deep Field | Signal Teal `#0F766E`, Deep Water |
| Apple category | Technology / Society & Culture | Society & Culture / Personal Journals |
| Start Here group | Technology & AI | Stories & Case Studies |
| Newsletter adjacencies | Models & Agents, M&A for Beginners | The Age of AI, Unintended Consequences |
| Feed | `age_of_ai_podcast.rss` | `nerra_voices_podcast.rss` |
| Pages | `age-of-ai.html`, `age-of-ai-summaries.html`, `age-of-ai-apply.html` | `nerra-voices.html`, `nerra-voices-summaries.html`, `nerra-voices-apply.html` |
| Studio | `age-of-ai-studio.html` | the same studio page, branded via `?show=nerra_voices` |

Everything else is shared: Mira's voice (`ara`), the Supabase tables, the
Cloudflare Worker (`workers/voices/`), the five `nerra_voices_*` GitHub
Actions workflows, the editorial passes, and the two human gates
(editorial review, guest transcript approval) before publish.

The split exists so neither audience gets confused: an Age of AI listener
expects the AI transition to be the subject; a Nerra Voices listener
expects a person and their craft. A guest who pitched The Age of AI but
has no AI story is not rejected — they are reassigned.

## How routing works

The pipeline is keyed on a `show` column (`guest_applications.show`,
`interviews.show`; migration `supabase/migrations/20260905_voices_show_routing.sql`,
default `age_of_ai`). Show-specific values — brand colour, apply/studio
page, R2 prefix, music bed, cover, prompt directory, premise, opening
line, closing question, sign-off — are read from the show yaml `voices:`
block by `pipelines/voices/shows.py` (`VoiceShow`) and mirrored in the
Worker's `SHOWS` map (`workers/voices/src/index.ts`). Change a value in the
yaml and in the Worker map together.

The show is decided once, early, and carried on the row from then on:

1. **Apply page.** `nerra-voices-apply.html` posts `show=nerra_voices`;
   `age-of-ai-apply.html` posts `show=age_of_ai`. Unknown or missing →
   `age_of_ai`.
2. **Producer.** The Nerra Producer inbox job creates `invited` rows from
   inbound pitches and records `pitched_show`; the operator assigns the
   show at triage (`/voices/admin/triage` groups pending rows by show and
   has a per-row "Reassign" control → `POST /voices/triage-reassign
   {application_id, show}`). Approval emails the show's booking link.
3. **Cal.com event type.** Each show has its own event type. The booking
   webhook matches the payload's event type against
   `CALCOM_EVENT_SLUG_AGE_OF_AI` / `CALCOM_EVENT_SLUG_NERRA_VOICES` when
   set; otherwise an event slug containing `voices` → `nerra_voices`, else
   `age_of_ai`. The interview row inherits the application's show.
4. **Downstream** (briefs, the live call, post-interview passes, produce,
   publish) every script resolves the show from the interview row and asks
   `VoiceShow` for paths: audio under `digests/nerra_voices/`, R2 prefix
   `nerra_voices`, feed `nerra_voices_podcast.rss`, summaries
   `digests/nerra_voices/summaries_nerra_voices.json`, blog under
   `blog/nerra_voices/`.

`run_show.py nerra_voices` is a deliberate no-op (`narrative_mode` with a
permanently empty topic queue → `narrative_queue_empty` skip), exactly like
`age_of_ai`. The show is exempt from the daily audit's schedule-based
missed-episode detection (`review_episodes.AUDIT_EXEMPT_SLUGS`), exempt
from dashboard publish-staleness (`_PUB_AGE_THRESHOLDS_H`), and excluded
from the Nerra Daily / Nerra Personal lineups.

## What the site does

`python generate_html.py --show nerra_voices --blogs` renders
`nerra-voices.html`, `nerra-voices-summaries.html` and
`blog/nerra_voices/index.html` from `network_meta.yaml` + the summaries
JSON. The show page hero and the empty blog index promote the apply page
(the same treatment as The Age of AI). Shared pages (network index, Start
Here, FAQ, AI disclosure, sitemap, nav menus) pick the show up from
`NETWORK_SHOWS` on their next nightly regeneration.

`digests/nerra_voices/summaries_nerra_voices.json` starts as
`{"episodes": []}` — the voices pipeline's shape (`publish_episode.py`
appends to `episodes`), matching `summaries_age_of_ai.json`.

## Operator steps to launch

1. **Cal.com.** Create a "Nerra Voices with Mira" event type (same
   duration and questions as the Age of AI one, its own slug containing
   `voices`). Point its webhook at `POST /voices/cal-com-booked`. Set the
   Worker secrets `CALCOM_BOOKING_URL_NERRA_VOICES` (the public booking
   link the approval email sends) and, if the slug does not contain
   `voices`, `CALCOM_EVENT_SLUG_NERRA_VOICES`:

   ```
   cd workers/voices
   wrangler secret put CALCOM_BOOKING_URL_NERRA_VOICES
   wrangler secret put CALCOM_EVENT_SLUG_NERRA_VOICES   # optional
   ```

   `GET /voices/health` reports `calcom_nerra_voices: true` once set.
2. **Music bed (optional).** `voices.music_bed` points at
   `assets/music/nerra_voices.mp3`. As of launch that file does not exist,
   and neither does `assets/music/age_of_ai.mp3` (The Age of AI has shipped
   without a bed since July 2026) — `produce_episode.py` assembles without
   a bed when the file is missing, so this is not a launch blocker. Drop
   an MP3 at that path (see `assets/music/README.md` for the licensing
   convention) when there is one.
3. **First episode.** Nothing to pre-create: `engine.publisher.update_rss_feed`
   writes `nerra_voices_podcast.rss` on the first publish, the same way
   `age_of_ai_podcast.rss` appeared. Do not commit a hand-made empty feed.
4. **Directories.** After the first episode is in the feed, submit
   `https://nerranetwork.com/nerra_voices_podcast.rss` to Apple Podcasts
   Connect and Spotify for Podcasters (`scripts/submit_to_directories.py`
   lists the show; `docs/podcast_directories.md` has the per-directory
   notes). When they approve, fill `spotify_show_id` and `apple_show_id`
   in `shows/nerra_voices.yaml` and `spotify_url` / `apple_podcasts_url`
   in the `network_meta.yaml` block; the show page's subscribe chips and
   the Apple/Spotify stats fetchers key off those.
5. **Regenerate.** `python generate_html.py --show nerra_voices --blogs`
   after the first publish (the publish workflow does this), then let the
   nightly shared-pages job pick up the rest.
6. **Review rotation.** `docs/reviews/review_state.yaml` carries a
   launch-day registration (`nerra_voices: 2026-09-05`) so the show enters
   the rotation at the back, like Offshore North did; the first real
   review happens once there are episodes to review.
