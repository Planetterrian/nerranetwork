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
| Deploy both Workers (`workers/voices` with `GMAIL_SERVICE_ACCOUNT_JSON` + `GMAIL_DELEGATED_USER`; `workers/gallery`) | unconfirmed | 2026-11-04 | `/voices/health` does not report a version and no gate-2 email has gone out since the copy changed. The Nov 4 "Vancouver time" label in booking emails also needs the voices Worker deployed. |
| Rotate `PERSONAL_ADMIN_TOKEN` (Worker secret and GitHub secret) | open | 2026-11-04 | |
| xAI monthly spending limit in console.x.ai, above one slate's spend | open | 2026-11-04 | Auto-reload works ($25 Grok receipts about daily Oct 15 to Nov 4). |
| First "Run Podcast Show" with `rehearse: true`, and "Probe audio chain" (legacy and glue) | open | 2026-11-04 | |
| GA4: two custom dimensions and three key events | open | 2026-11-04 | |
| Google Ads: campaign and ad-group names for `scripts/funnel_link.py` | open | 2026-11-04 | |
| Search Console: submit `news-sitemap.xml` | open | 2026-11-04 | The file is live (200, 18 KB). |
| Buttondown: is a welcome email on? | answered: no (Patrick, Nov 6); draft in `engine/nerra_welcome_email.py`, sender not chosen | 2026-11-06 | |
| Buttondown: turn on open and click tracking (off by default; every send reads 0) | open | 2026-11-06 | api/buttondown_stats.json |
| Buttondown: send the "Nerra Daily email" test draft | open | 2026-11-04 | None has reached the inbox, so `BUTTONDOWN_WRAPPER_BYTES` is unknown. |
| Stripe: set `STRIPE_SECRET_KEY` | open | 2026-11-04 | `api/member_metrics.json` (Nov 3 22:23 UTC): `stripe_configured: false`. |
| YouTube Studio: banners, descriptions, RU/FR trailers, end screens (note the start date) | open | 2026-11-04 | RSS-podcast removal is the Nov 16 item. |
| YouTube: podcast playlists for AI Chips and MAG 7 | open | 2026-11-04 | Both shows upload to the EN channel from their next run once the PR merges (`docs/reviews/youtube_audit_2026_11_04.md`). Run `python3 scripts/create_youtube_playlists.py <client_secrets.json> en`; it writes `podcast_playlist_id` into both YAMLs. |
| YouTube: RU SpaceX and RU FF long-forms come back on tonight | decide | 2026-11-04 | `api/youtube_policy.json` (Nov 3): both compute tier A on the four-video read, night 1 of 2. Turn on `DUB_LONG_RELATIVE_ENABLED` (C17) if dub longs should stay off. |
| Label the seven closed review PRs | open | 2026-11-04 | Only `rejected` writes `do_not_retry`. |
| Decisions list and dated items (Nov 10, 16, 17, 18) | unchanged | 2026-11-04 | |
| Podcast Index: add the six unindexed feeds at podcastindex.org/add | open | 2026-11-04 | `api/op3_stats.json` (Nov 3): `nerra_voices`, `offshore_north`, `omni_view_north_america` unresolved; plus `env_intel:fr`, `first_principles:fr`, `models_agents:fr`. |
| Apple: publish Offshore North (draft; artwork now 3000 px) and submit Nerra Voices | open | 2026-11-04 | `docs/podcast_directories.md`. |
| Spotify: Nerra Daily's show id (Spotify for Creators) | open | 2026-11-04 | |
| Cal.com: create the 5-minute `age-of-ai-hello` and `nerra-voices-hello` event types, or retire the hello feature | open | 2026-11-04 | The link 404'd for five guests; `HELLO_INVITES: "0"` in the fire workflow until the pages exist. |
| Google Calendar is on America/Los_Angeles | open | 2026-11-04 | It shows an hour behind a Vancouver clock since Nov 1. Settings → Time zone → Vancouver. |
| `docs/listens.md`: the Mira-brief listen line | not written | 2026-11-04 | The handoff proposed a line saying Patrick listened to rooms 115ba095 and 036ea51e. It was never committed and is not added here; add it yourself once you have listened. |
| Re-master the quiet back catalogue (Actions "Re-master Episodes", one listen first) | open | 2026-11-04 | UC Ep161 is −25.7 LUFS. New episodes are in spec: Tesla Ep655 −16.2, Vancouver Ep043 −16.2, UC Ep163 −16.6. Collingwood Ep006 −24.9; its Nov 6 episode is the check. |
| Interview pages: run `vtt_backfill`, then `refresh_post` for AoAI Ep12–14 and NV Ep3–4 | open | 2026-11-04 | Neither `age_of_ai_podcast.rss` (15 items) nor `nerra_voices_podcast.rss` (4) carries `podcast:transcript`. |
| First Principles: restock opportunity_area topics | open | 2026-11-04 | 27 open concrete_example, 0 open opportunity_area. If the next restock adds none, rerun "Restock Topic Queues" with force. |
| Close Stuart Berkowitz's duplicate application 4484f810 | open | 2026-11-04 | The chase job now closes such rows itself (see Closed); this one can wait for the next chase run or be closed by hand. |
| Re-run the Pyvot correction for Michael Kamins' episode | open | 2026-11-04 | `scripts/apply_corrections.py --show age_of_ai --episode <n> --apply` now also amends `episode_records` (the record was fixed by hand today). |

## Rehearsal (prompt or room; not shipped, needs a PASS plus one listen)

| Item | Status | Checked | Note |
|---|---|---|---|
| Mira's opening says the AI part twice and in the third person | proposed | 2026-11-04 | Step 2 today lands as "I'm Mira, the AI who hosts The Age of AI, and on this show an AI asks the questions while the guest decides…". Proposal: step 2 says she is Mira, the AI who hosts {{show_name}}, and that the guest sees the transcript first and decides what is published; the claim stays in WHAT YOU ARE. |
| A standing lesson contradicts the beat rule | proposed | 2026-11-04 | The adopted lesson "Most turns go straight to the next question" (in `show_lessons`, not the repo) contradicts the CRITICAL line asking for one sentence after a real answer. Retire or reword the lesson; lessons are retired by the metric, so cite `bare_question_rate` from the three Nov 4 rooms. |
| The beat is mostly an echo label | measured | 2026-11-04 | Most reactions in the three rooms were 2–4 of the guest's own words. `question_turn_shape` counts these as `label`, never `reaction` (guard `tests/test_handoff_2026_11_04.py::TestEchoLabelsAreNeverReactions`), so read `label_open_rate` beside `bare_question_rate` before calling the beat fixed. |
| Mira's reply after an answer is the same short summary line every turn (Patrick, Blaine Mathieu's room) | proposed, on a draft PR | 2026-11-04 | HOW TO REACT rewritten so she builds on one thing said and leads into the question; the three lessons that kept her short (6c89834c, 8c69e55d, 1d5a5f84) and the stale two-closing-questions lesson (854dfc33) stay out of the prompt via `learning.SUPERSEDED_BY_BRIEF`. Rehearse the branch (`arms: both`, fixture `adrian`), read `one_liner_rate` beside label and bare, one listen, then merge; retire the four rows after it ships. Supersedes the "standing lesson contradicts the beat rule" row above. |
| The close skips the site and guest-application line, and says "Take care, Roddy" after "you can hang up now" | proposed | 2026-11-04 | All three rooms. |

## Claude (code and docs)

| Item | Status | Checked | Note |
|---|---|---|---|
| Worker vitest: `backup_clock.test.ts` "the half-hour jobs read the slot" fails on main | open | 2026-11-04 | Expects `fire-tick` at :31; the Nov 3 change made the fire-tick catch-all hourly. Pre-existing, unrelated to the handoff; no workflow runs this suite. |
| `api/voices_metrics.json` on main | expected tonight | 2026-11-04 | Written by the nightly. |
| tzdata on runners and Cloudflare | watch | 2026-11-04 | Vancouver times are right only where the runtime has tzdata 2026c (B.C. permanent UTC−7). The test `test_vancouver_is_not_called_pacific_after_bc_left_dst` skips, rather than fails, on older tzdata; if it starts skipping in CI, emails are an hour off. |

## Closed

| Item | Closed | Evidence |
|---|---|---|
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
