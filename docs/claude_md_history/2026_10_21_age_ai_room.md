# The Age of AI: the room, the brief, and a loop that can hear (Oct 21 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### The Age of AI: the room, the brief, and a loop that can hear (Oct 21 2026)

Operator-directed, from the full review of the interview show (review
[`docs/reviews/age_of_ai_review_2026_10_21.md`](docs/reviews/age_of_ai_review_2026_10_21.md);
ledger `age_of_ai` 2026-10-21; register `age-of-ai-room-and-loop-2026-10-21`;
guards `tests/test_room_mechanics_2026_10_21.py`,
`tests/test_mira_prompt_is_a_brief_2026_10_21.py`,
`tests/test_audio_metrics_2026_10_21.py`, `tests/test_loop_hears_2026_10_21.py`,
`tests/test_voices_worker_hardening_2026_10_21.py`,
`tests/test_edit_keeps_its_promises_2026_10_21.py`, `tests/test_guest_hour_2026_10_21.py`,
`tests/test_rehearsal_harness_2026_10_21.py`). Thirteen grades ran 2-7 with no
trend, Mira's median turn fell from ~28 s to 7.6 s, the last two rooms
interrupted 14 times each, and the loop reported adopting a lesson after
every tape. The three faults guests named were the ROOM's, and the rules
that bind now:

- **End of turn is a decision, not a timer** (`voximplant/scenarios/age_of_ai_interview.js`).
  The silence timer was raised 1,100 → 1,300 → 1,800 ms and the Oct 20 room
  still interrupted 14 times, so it is never raised again: `turn_detection`
  sends `create_response: false`, the server VAD finds the pause, and the
  room's `decideTurn` gives her the turn only when someone has spoken since
  her last line and the last clause reads finished (one extra wait for a
  late transcription, one for an unfinished clause). A turn the server starts
  with nobody having spoken is cancelled at once (`self_answers_blocked`).
  **`requestTurn` is the one way to a turn** and parks a request while the
  guest is talking — the opening, a tool's return, a rescue, a rejoin, the
  mic nudge and the hand-over all go through it; the only other
  `responseCreate` is the narration take. **She never speaks first on join**
  (the guest's first words or three seconds). **The hand-over happens at a
  pause she is in** (due six minutes before the session ceiling, forced only
  in the last 90 s, the whole kept transcript carried, no unprompted first
  line). **Per-leg `MicStatusChange`** tells the room who is talking: a
  co-host-only voice is neither the guest's barge-in nor the guest's answer.
  **A sign-off before the window is cancelled on the response's transcript
  deltas**, mid-sentence. **The closing round is a state machine in the
  room**: it hands her each of the eight `ROUND_QUESTIONS` one at a time
  after the previous answer ends (trace `round: asked n/8`, `answered n/8`),
  then the last word, then the thanks; a question she asks herself once
  permitted hands the round to the room. `reasoning.effort` comes from
  `interview_runs.reasoning_effort` (default high). Every request the room
  makes to the Worker carries `X-Voices-Signature` (hex HMAC-SHA256 of the
  body; a self-contained SHA-256 checked against the standard vectors) when
  `VOICES_WEBHOOK_SECRET` is deployed to both; unset, nothing changes. The
  end-of-room webhook reports `barge_ins`, `server_turns`,
  `self_answers_blocked`, `closing_round_complete`. A `hello` session (below)
  opens without the show and never runs the round.
- **The prompt is a host's brief, not a rulebook.** `mira_system_prompt.txt`
  is ~1,500 words of positive craft in the order a conversation runs, with
  **no quoted specimen of a bad line and no dated incident narrative** — the
  network's de-seed-by-shape rule applied to Mira (seventy "That's a …" lines
  were listed and the shape moved to a one-word echo opener). The seventeen
  incident stories live in [`docs/mira_craft_notes.md`](docs/mira_craft_notes.md)
  for humans. `lessons_block` renders at most five positive show lessons,
  `relapse_recap` is empty (a rule she breaks three times is a room defect),
  `variety_block` is a shape list with no phrase instances, `fact_check_claim`
  is off the tool list by default, `carry_the_show_block` offers at most one
  previous guest an hour, named with a sentence of who they are, only inside
  this guest's subject and never as "is he right?"; the brief asks what this
  person would be glad to be asked, the question set reads the guest's
  agenda, and the T-1 prep email tells the guest the three things Mira is
  curious about. **Never add a prohibition to the live prompt for a fault the
  room can enforce** (ledger `do_not_retry`).
- **The loop can hear** (`pipelines/voices/audio_metrics.py`). `episode_metrics`
  carries `overlap_sec`/`overlap_events`, the `turn_gap_ms` distribution,
  `mira_turn_sec` median/p90, `guest_words_per_answer_median` and its trend
  across the hour, `self_answered_turns`, `echo_open_rate`,
  `closing_round_complete` and `seams`, measured from the per-speaker Whisper
  words and the room trace (`metrics_basis: audio`; the old transcript
  estimates stay a month for comparison). The retro pass PROPOSES lessons
  with a metric and evidence; **adoption is weekly**
  (`adopt_lessons_weekly.py`, Mondays), at most six show lessons, retirement
  by the motivating metric going green for three rooms, never by age; closing
  sessions are neither graded nor adopted from. **Every guest is asked**: a
  three-question survey email 24 h after the room (`guest_survey.py`,
  `/voices/survey/<token>`), sent whether or not they opened the review page;
  `survey_rating` is this show's headline number. `review_snapshot.py` reads
  the interview shows. Targets in review §7.7.
- **A guest is never the test.** `docs/age_of_ai_rehearsal.md`: a fixture
  guest (`age_of_ai_fixture_guest.js`, a second voice agent playing a past
  guest from their approved transcript, pausing mid-thought, coughing, asking
  who someone is) runs a room through the real scenario. **Since Oct 23 2026
  a rehearsal is ONE fifteen-minute room of the proposed arm** (the room
  reads a planned length under 15 as 45, so a shorter room never opens the
  round; at 15 it is required at minute 10), judged on the room's own checks (ran, no self-answered
  turns, under one overlap per ten minutes, the closing round complete with
  every question in her words and none a turn behind, no dropped session)
  and reported with its ROOM LOG (`rehearsal.room_log`: sessions, turn
  decisions, holds, the round line by line, each question handed vs heard).
  34 rooms in two days (~870 Voice Agent minutes) found four faults, every
  one from the log, none from the medians (guest words per answer ran 31-84
  on one configuration). `arms: both` keeps the two-arm comparison for a
  prompt or setting change. `rehearsal.py preflight` stops the job before
  any room when xAI refuses requests (Oct 23: six rooms placed on an account
  out of credit), and a room xAI refused stops the rest. **A scenario or
  prompt change ships to a real guest only on a PASS plus one operator
  listen.** `closing_round_complete` (live rooms too) is false on a "said
  late" or "asked again" line; it had read complete on a round that lost
  three questions.
- **The edit keeps its promises in code.** A guest's "start that again" or
  "take that out" is found in the transcript and exempt from the 25 s drop
  floor; `edit_transcript` (the transcript of the EDIT, re-stamped on its
  clock) is what the guest approves; redaction windows marked on the review
  page are cut from the SHIPPED file and `publish_episode` refuses to ship a
  file built before the windows were stored; a thank-you from Mira goes
  within the hour of the room ending with three of the guest's own lines; the
  publish-day mail carries the link, a 60-second moment, the share card and a
  return month; a five-minute **hello** two days before (`hello_sessions.py`,
  on the closing-session pattern) writes `guest_agenda` for guests who set
  none. Worker: lesson decisions check ownership, `/studio-phone` never
  redials a finished interview, gate-2 housekeeping survives one failed
  email, status is written after the dispatch, the studio copy says fifteen
  minutes, `/join` needs a token.

Operator: deploy the scenario (Actions "Deploy Voximplant scenario", which
now ships the fixture guest too), `wrangler deploy` in `workers/voices`, apply
the two migrations, set `VOICES_WEBHOOK_SECRET` on both sides, and run the
rehearsal before the next booked room. ⚠️ AUDIO on every interview.
