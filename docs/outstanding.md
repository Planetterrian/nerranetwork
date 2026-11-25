# Outstanding: the one tracker for operator and follow-up items

Started 2026-11-04 from the Cowork status handoff
(`Claude outputs/claude_code_status_2026_11_04.md`, on Patrick's Mac, not
committed). Cowork and Claude Code both read and update this file; nothing
else keeps a parallel list. One row per item: **owner**, **status**, the
**date** it was last checked, and the **evidence** that status rests on.
When an item closes, move it to "Closed" with the date and the proof.

Owners: **Patrick** (only he can see or do it), **Claude** (code or docs in
this repo), **Rehearsal** (a prompt or room change: ships only on a passing
rehearsal plus one operator listen, per CLAUDE.md "The Age of AI").

## Patrick

| Item | Status | Checked | Evidence / next step |
|---|---|---|---|
| `nerra-personal-batch`: set `NOTIFICATION_WEBHOOK_URL` | open | 2026-11-06 | Its failure alert step has printed "no NOTIFICATION_WEBHOOK_URL set" on every failed run. The daily audit now pages on stale private feeds too (`scripts/check_personal_feeds.py`). |
| Apple stats cookies expired | open | 2026-11-25 | `api/apple_stats.json` last fetched 2026-07-25. Refresh the Apple Podcasts Connect cookies secret (Patrick only; the built-in browser is not signed in to Apple). |
| `REVIEW_PR_TOKEN` repo secret | open | 2026-11-25 | Fine-grained token on this repo, Contents and Pull requests read/write, so review-agent PRs run checks (PR #1736). Only Patrick can create and paste it. |
| Stripe Radar rule on the one-time donate link | open | 2026-11-25 | `Block if :card_country: != :billing_address_country:`. Dashboard only (no API). |
| `STRIPE_LINK_DONATE_ONCE` repo variable still holds the retired link | open | 2026-11-25 | Set it to `https://donate.stripe.com/7sY6oIc9Q0iK2zUbwb0Ba04` or delete it (workflows fall back to that link). |
| Remove the RSS-ingested podcast copies on the EN YouTube channel | open | 2026-11-25 | ~9 duplicate long-forms a day (`docs/reviews/youtube_growth_review_2026_11_24.md`). The browser on Patrick's Mac is signed in to a different channel (no podcasts listed), so it has to be done from the Nerra channel. Record the Podcasts-tab play counts first. |
| Gate 1: Gary Amaral (NV) and Surendra Goel (AoAI) | waiting on Patrick's yes | 2026-11-25 | Both edits read on their review pages; recommendation: approve both, with a note to Surendra that the end of his call dropped. |
| xAI monthly spending limit in console.x.ai, above one slate's spend | open | 2026-11-04 | Auto-reload works ($25 Grok receipts about daily Oct 15 to Nov 4). |
| "Probe audio chain" (legacy and glue) | open | 2026-11-25 | The first `rehearse: true` show runs happened Nov 24 (Tesla Ep676, SpaceX Ep173, PR #1747), so only the probe is left. |
| GA4: two custom dimensions and three key events | open | 2026-11-25 | `api/ga4_stats.json` (Nov 25) `conversions: []`, so no key event is marked yet. |
| Google Ads: campaign and ad-group names for `scripts/funnel_link.py` | open | 2026-11-04 | |
| Search Console: submit `news-sitemap.xml` | open | 2026-11-04 | The file is live (200, 18 KB). |
| Buttondown: is a welcome email on? | answered: no (Patrick, Nov 6); draft in `engine/nerra_welcome_email.py`, sender not chosen | 2026-11-06 | |
| Buttondown: send the "Nerra Daily email" test draft | open | 2026-11-04 | None has reached the inbox, so `BUTTONDOWN_WRAPPER_BYTES` is unknown. |
| YouTube Studio: banners, descriptions, RU/FR trailers, end screens (note the start date) | open | 2026-11-04 | RSS-podcast removal is the Nov 16 item. |
| YouTube: podcast playlists for AI Chips and MAG 7 | open | 2026-11-04 | Both shows upload to the EN channel from their next run once the PR merges (`docs/reviews/youtube_audit_2026_11_04.md`). Run `python3 scripts/create_youtube_playlists.py <client_secrets.json> en`; it writes `podcast_playlist_id` into both YAMLs. |
| YouTube: RU SpaceX and RU FF long-forms come back on tonight | decide | 2026-11-04 | `api/youtube_policy.json` (Nov 3): both compute tier A on the four-video read, night 1 of 2. Turn on `DUB_LONG_RELATIVE_ENABLED` (C17) if dub longs should stay off. |
| Label the seven closed review PRs | open | 2026-11-04 | Only `rejected` writes `do_not_retry`. |
| Decisions list and dated items (Nov 10, 16, 17, 18) | unchanged | 2026-11-04 | |
| Podcast Index: add the four unindexed feeds at podcastindex.org/add | open | 2026-11-25 | `api/op3_stats.json` (Nov 25): `omni_view_north_america`, `env_intel:fr`, `first_principles:fr`, `models_agents:fr` still unresolved. `nerra_voices` and `offshore_north` now resolve. |
| Apple: publish Offshore North (draft; artwork now 3000 px) and submit Nerra Voices | open | 2026-11-25 | `shows/offshore_north.yaml` still has no `apple_show_id`. `docs/podcast_directories.md`. |
| Spotify: Nerra Daily's show id (Spotify for Creators) | open | 2026-11-25 | `shows/network_meta.yaml` nerra_daily `spotify_url: null`. Longevity and Collingwood have no Spotify id either. |
| Spotify: SpaceX Daily is listed in Russian | open, needs Patrick's yes | 2026-11-25 | `api/spotify_stats.json` (Nov 25) reads `language: ru` for show 033xHlNZZy4OVq1T2CkDNp while `spacex_podcast.rss` says `en-us`. Fix in Spotify for Creators (show settings, language English). |
| `docs/listens.md`: the Mira-brief listen line | not written | 2026-11-04 | The handoff proposed a line saying Patrick listened to rooms 115ba095 and 036ea51e. It was never committed and is not added here; add it yourself once you have listened. |
| Re-master the quiet back catalogue (Actions "Re-master Episodes", one listen first) | open | 2026-11-04 | UC Ep161 is −25.7 LUFS. New episodes are in spec: Tesla Ep655 −16.2, Vancouver Ep043 −16.2, UC Ep163 −16.6. Collingwood Ep006 −24.9; its Nov 6 episode is the check. |
| Interview pages: run `vtt_backfill`, then `refresh_post` for AoAI Ep12–14 and NV Ep3–4 | backfill dispatched | 2026-11-24 | Nov 24: `vtt_backfill` run on main; `refresh_post` only for an episode its log lists as skipped. Was: | Neither `age_of_ai_podcast.rss` (15 items) nor `nerra_voices_podcast.rss` (4) carries `podcast:transcript`. |
| First Principles: restock opportunity_area topics | open | 2026-11-04 | 27 open concrete_example, 0 open opportunity_area. If the next restock adds none, rerun "Restock Topic Queues" with force. |
| Close Stuart Berkowitz's duplicate application 4484f810 | open | 2026-11-04 | The chase job now closes such rows itself (see Closed); this one can wait for the next chase run or be closed by hand. |
| Re-run the Pyvot correction for Michael Kamins' episode | open | 2026-11-04 | `scripts/apply_corrections.py --show age_of_ai --episode <n> --apply` now also amends `episode_records` (the record was fixed by hand today). |

## Nov 24 2026: Age of AI and Nerra Voices

| Item | Owner | Status | Evidence / next step |
|---|---|---|---|
| Blaine Mathieu: his Nov 9 cut requests (4 lines) | Patrick | new cut sent Nov 24; auto-approves Nov 30 | Listen to the new cut, then press "Changes made: send the guest the new cut" on his review page. Was stuck because the assemble never re-ran after Nov 9. |
| John Ossipinsky (NV) | Claude | publish dispatched Nov 24 | Approved by Patrick Nov 13 and the guest Nov 20; produced Nov 20; publishing is a manual dispatch. |
| Gary Amaral (NV, Nov 13), Surendra Goel (AoAI, Nov 20) | Patrick | gate 1, see the Patrick table | Both graded 4/10; listen and approve from the review emails. |
| Tahir Rauf: invite back, drop the 6-minute edit | Patrick | email sent Nov 24 | Re-record as a fresh interview; the 6-minute piece is not publishable. |
| Tamara Laine, Animesh Alang: rebook | Patrick | emails sent Nov 24 | Booking link `cal.com/patrick-novak-lkcqo4/age-of-ai-interview`. |
| Rejoin after a mid-interview drop | Claude | scoped, with the Dec 9 batch | A 3-minute in-room wait is impossible (Voximplant ends an empty session at 60 s). Reopening a room past 5 minutes would overwrite its recordings, so a rejoin is a continuation session spliced onto the first edit, like the closing session (`splice_closing`), with its own prompt: a room change, rehearsed. |
| Latency: hold and release her server turn | Claude | next | Every turn is cancelled and re-requested today (4–4.6 s median gap). |
| Producer model drafts her bridge and next question | Claude | next | Label openers 0.33–0.80 after four brief rewrites. |

## Rehearsal (prompt or room; not shipped, needs a PASS plus one listen)

| Item | Status | Checked | Note |
|---|---|---|---|
| Mira's opening says the AI part twice and in the third person | superseded | 2026-11-24 | PR #1738 (two-turn opening: hello, then who she is in two sentences and the first question); two-arm rehearsals adrian + vincent on Nov 24. Was: | Step 2 today lands as "I'm Mira, the AI who hosts The Age of AI, and on this show an AI asks the questions while the guest decides…". Proposal: step 2 says she is Mira, the AI who hosts {{show_name}}, and that the guest sees the transcript first and decides what is published; the claim stays in WHAT YOU ARE. |
| A standing lesson contradicts the beat rule | proposed | 2026-11-04 | The adopted lesson "Most turns go straight to the next question" (in `show_lessons`, not the repo) contradicts the CRITICAL line asking for one sentence after a real answer. Retire or reword the lesson; lessons are retired by the metric, so cite `bare_question_rate` from the three Nov 4 rooms. |
| The beat is mostly an echo label | measured | 2026-11-04 | Most reactions in the three rooms were 2–4 of the guest's own words. `question_turn_shape` counts these as `label`, never `reaction` (guard `tests/test_handoff_2026_11_04.py::TestEchoLabelsAreNeverReactions`), so read `label_open_rate` beside `bare_question_rate` before calling the beat fixed. |
| Mira's reply after an answer is the same short summary line every turn (Patrick, Blaine Mathieu's room) | shipped, not fixed | 2026-11-24 | Shipped Nov 4 (register `mira-react-builds-2026-11-04`); label openers were still 47–80% in the Nov 13–23 rooms. Next: the producer model in the Nov 24 plan. Was: | HOW TO REACT rewritten so she builds on one thing said and leads into the question; the three lessons that kept her short (6c89834c, 8c69e55d, 1d5a5f84) and the stale two-closing-questions lesson (854dfc33) stay out of the prompt via `learning.SUPERSEDED_BY_BRIEF`. Rehearse the branch (`arms: both`, fixture `adrian`), read `one_liner_rate` beside label and bare, one listen, then merge; retire the four rows after it ships. Supersedes the "standing lesson contradicts the beat rule" row above. |
| The close skips the site and guest-application line, and says "Take care, Roddy" after "you can hang up now" | proposed | 2026-11-04 | All three rooms. |

## Claude (code and docs)

| Item | Status | Checked | Note |
|---|---|---|---|
| `api/voices_metrics.json` on main | expected tonight | 2026-11-04 | Written by the nightly. |
| tzdata on runners and Cloudflare | watch | 2026-11-04 | Vancouver times are right only where the runtime has tzdata 2026c (B.C. permanent UTC−7). The test `test_vancouver_is_not_called_pacific_after_bc_left_dst` skips, rather than fails, on older tzdata; if it starts skipping in CI, emails are an hour off. |

## Closed

| Item | Closed | Evidence |
|---|---|---|
| Deploy `workers/scheduler` (Daily Audit dispatch) | 2026-11-25 | Patrick reports the Workers deployed (Nov 25). |
| Deploy `workers/voices` and `workers/gallery` | 2026-11-25 | Patrick reports the Workers deployed (Nov 25). |
| Rotate `PERSONAL_ADMIN_TOKEN` | 2026-11-08 | `api/personal_feed_health.json` read 2 of 2 members built. |
| Deploy `workers/gallery` for `/api/admin/personal-feed-health` | 2026-11-08 | `feeds_error: null`. |
| Unlock @nerranetwork on X | 2026-11-25 | Every "Post queued X posts" run on Nov 25 succeeded (latest 45635781973). UC stays off X (PR #1711). |
| Buttondown open and click tracking | 2026-11-25 | On since Nov 8: `api/buttondown_stats.json` shows opens on every send from Nov 9. |
| Stripe: `STRIPE_SECRET_KEY` | 2026-11-25 | `api/member_metrics.json`: `stripe_configured: true`. |
| Google Calendar time zone | 2026-11-25 | The primary calendar is America/Vancouver. |
| Cal.com hello event types: retired | 2026-11-25 | The two-turn opening (PR #1738) does the hello's job; `HELLO_INVITES` stays "0". |
| Worker vitest: `backup_clock.test.ts` "the half-hour jobs read the slot" failed on main | 2026-11-10 | The test now checks the inbox at :30 and the fire tick at the top of the hour; the voices lockfile is regenerated (`npm ci` refused it); new `workers-test.yml` runs both Workers' vitest and `tsc` on every Worker change (project audit PR). |
| Mira's Nov 3 brief (beat line + spoken self-description) rehearsed | 2026-11-04 | Fixture roddy: rooms 894eacef (old) / 115ba095 (new), then candidate room 036ea51e; Patrick reports PASS; text-mode A/B on grok-voice-3.0, 6 sessions, no regression. |
| Hold regex: "I'll hold the silence better" put the room on hold | 2026-11-04 | Commit 0cee8259, deployed 15:25 UTC; guard `test_only_the_waiting_senses_are_a_hold`. |
| Apple: the 13 launch-cohort shows are live | 2026-11-04 | iTunes Search API (handoff); IDs now `apple_show_id` in each show YAML, Nerra Daily's 6805616718 in `shows/network_meta.yaml`. |
| "Pacific Time" label on guest and operator emails | 2026-11-04 | Now "Vancouver time" (`pipelines/voices/common.py`, `workers/voices/src/index.ts`); the Worker side needs the deploy above. |
| Rehearsal `current` arm greeted the fixture by the last real guest's name | 2026-11-04 | `rehearsal.rebind_guest`. |
| Candidate scenario upload was not proven | 2026-11-04 | `voximplant_client.read_back_scenario` reads it back and fails the step when the account copy differs. |
| Producer chased a guest after his interview | 2026-11-04 | `chase.recorded_elsewhere` closes a row whose person (same email) has a recorded interview. |
| A correction did not reach `episode_records` | 2026-11-04 | `scripts/apply_corrections.py` amends the record's text columns for the interview shows. |
| `test_offsets_come_from_the_session_trace` red | 2026-11-04 | Green in CI (Python 3.14); red only on an interpreter before 3.11, where one-digit fractions did not parse. `room_offsets` pads the fraction now. |
| xAI auto-reload | 2026-11-04 | Daily $25 receipts. |
