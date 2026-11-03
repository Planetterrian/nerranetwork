# The Age of AI: a server turn, a guest on another call, and a sign-off too soon (Oct 22–24 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### The Age of AI: a server turn, a guest on another call, and a sign-off too soon (Oct 22 2026)

From the Oct 22 room (run c868dac8; guards `tests/test_room_holds_2026_10_22.py`,
behaviour driven through the real scenario in a node vm by
`tests/fixtures/room_sim.js`). Rules that bind:

- **A turn the server starts after the guest spoke goes through the room's
  decision** (`markTurnStarted`): it is cancelled and `scheduleTurnDecision`
  runs, so `decideTurn` (the only path to `roundAnswered`) sees the answer.
  The closing round had stuck at question 1 for 25 minutes because
  `markTurnStarted` reset the flags `decideTurn` reads. Counter
  `server_turns_rerouted` in the end-of-room webhook (Worker `roomCountersOf`).
- **Hold mode.** When the guest's words say they are stepping away or taking
  another call (`HOLD_ENTER_RE`; "let me think" is not one), or Mira says she
  will wait (`MIRA_HOLD_RE`), the room gives her no turns, holds TIME CHECK
  and round prompts, and counts no speech as an answer, until they address
  her again (`turnsBack`: her name, "sorry about that", "I'm back",
  "where were we", "you were asking", or "Back." as its own sentence —
  the fourth rehearsal's guest came back on "Back. … Anyway, you were
  asking …" and was held silent for two and a half minutes) or three
  minutes pass (`HOLD_CHECK_IN_MS`), when she says
  one short line that she is still there, for as long as they are away. Speech
  is the backstop exit: the guest talking ≥ `HOLD_REPLY_MIN_SPEECH_MS` within
  `HOLD_REPLY_WINDOW_MS` of the end of a check-in (`noteHoldSpeech`, fed by
  `noteSpeechEnded`, the one handler for both VAD paths). **The check-in is
  that one response's `instructions` (`response.create`), never a
  conversation note**: as a note it came out as "welcome back" and the
  question again into a guest still away, and on their return her first line
  was the check-in again (third rehearsal, run e08c026c); `exitHold` drops a
  parked one. On return she
  re-asks the closing question in play and any held time note is delivered.
  The trace carries `hold: entered/left`, never the guest's words.
- **The room hears the guest's words.** Grok Voice 3.0 sends them as the
  NAMED event `ConversationItemInputAudioTranscriptionCompleted`, re-sent
  about every second with the whole item so far; the room listened only for
  an Unknown event, so no guest word ever reached it (the Oct 13 "this room
  does not get one" note was this) and every word rule had never run live.
  `noteGuestTranscript` keeps one line per item, updated in place, and runs
  the hold/stop checks on what is new. Read from the session log of a
  candidate rehearsal (Actions "Voximplant session logs").
- **Dead air is broken.** With unrequested server turns cancelled, a silence
  nobody breaks had no end: 20 s after her line with nobody speaking
  (`DEAD_AIR_MS`) she puts her last question again, more simply; at most
  `DEAD_AIR_MAX_NUDGES` (2) per silence, never in a hold or the closing round;
  counter `dead_air_nudges`. The fixture guest reconnects a dropped socket
  (`FIXTURE_RECONNECTS_MAX` 3) — one rehearsal lost it to a 1006 at minute
  two and measured twelve silent minutes.
- **No sign-off while the round is unfinished**, cut mid-sentence on the
  transcript deltas (`signOffBlockedByRound`), unless the guest asked to stop
  (`GUEST_STOP_RE`), the hard cap fired (it closes the round), or the room
  has already blocked `ROUND_CLOSE_BLOCKS_MAX` (3) — a guest is never trapped.
- **The grader** (`09_interview_retro.txt`): replying to, or acting on, a
  conversation the guest is having with someone else is a turn-taking fault,
  never "patience".
- **A candidate room is rehearsed before it is deployed.** The rehearsal
  workflow's `candidate_scenario` input uploads the branch's scenario as
  `age_of_ai_interview_candidate` with `ROOM_PREFIX` rewritten to
  `candroom-` (its own rule `^candroom-.*`; `candidate_source` refuses
  `room-`), and the fixture guest dials that prefix for the proposed arm; the
  live scenario and rule are never written. Either input also re-uploads this
  ref's rehearsal-only fixture guest (the deployed one predates the prefix and
  would quietly dial the live room). `with_hold` adds a phone-call beat to the
  fixture (`HOLD_BEATS`).
- **The rehearsal finds the guest's channel; it never assumes the left.** On
  the fixture guest's leg the stereo sides are the other way round from a real
  guest's, and the first both-arms rehearsal (run 39852548850) transcribed
  Mira's own words, seconds late, as the guest's answers in BOTH arms, so its
  FAIL compared Mira with herself. `pick_guest_channel` takes the side whose
  loudness tracks her recording least (left 0.83 / right 0.12 on that room)
  and the record says which (`guest_channel`). The workflow's `remeasure`
  input (`current:<run id>,proposed:<run id>`) measures rooms that already ran
  without running new ones. Read a rehearsal's transcript before its verdict.
  **Mira is measured from the side the guest HEARD, never her own record**:
  Voximplant stops writing her record through a long silence (the fifth
  rehearsal's three-minute hold vanished, 12:00 against a 14:45 room) and a
  single offset then put every later turn minutes early, read as seven
  self-answered turns. Post-production is unaffected (`align_to_room` places
  her record piece by piece).
- **She never nudges an empty room** (the same rehearsal: two nudges inside
  the rejoin grace after the fixture's leg dropped).
- **A fresh session runs the dead-air clock** (Oct 23, three-room rehearsal
  run 39879256504): her socket dropped just after a line, the rescue bridged
  a new session, and neither side spoke for eight minutes, because the clock
  was armed only when one of her lines ended. `resumeAfterHandover` is the
  one path after any hand-over or rescue: the owed turn, else `armDeadAir()`;
  the rescue clears her audio with the socket (guards
  `tests/test_room_rescue_2026_10_23.py`).
- **The round counts what she ASKED, not what the room handed her** (Oct 23,
  the first 22-minute room on the deployed scenario, run 4729e7b6: eight of
  eight questions, the last word and the thanks, one turn behind from
  question one). A round turn whose line carries no `?` did not ask the
  question in play: the room hands it again when the guest finishes
  (`noteRoundTurnWithoutQuestion`), or at once if they stay silent. A
  question the room handed her is never a repeat the first time her words
  carry it (`roundSpoken`); the room marks a question asked when it hands it
  over, so before this every on-time question drew a false "you asked it a
  second time" note. **Every turn the room drives in the round (each
  question, the re-ask, the last word, the closing thanks) goes as that one
  response's instructions on top of her session instructions** (`roundTurn`,
  `sessionInstructions`), never as a conversation note: the session log of
  rehearsal 0ac88c67 showed a note followed at once by `response.create`
  taking effect a turn late, every time, so each turn asked the previous
  note's question and the book, AI-interview and improvement questions were
  never put to the guest (the hold check-in's Oct 22 lag, again). Guards
  `tests/test_round_in_step_2026_10_23.py`. **A round turn that asks a
  follow-up instead is handed back too** (rehearsal 0dd50fbe: handed "who
  you should interview next", she asked about the guest's book and the
  question was lost): a turn whose question touches neither the handed
  question's pattern nor its subject (`ROUND_TOPICS`) is handed again, once
  per question, so a rewording never loops (guards
  `tests/test_round_follow_up_2026_10_23.py`).
- **She is handed the question's words, never a description of it** (Oct 23,
  rehearsal 39982637152: handed "whether they would be interviewed again" and
  the like, she asked questions of her own on five of seven turns). Each fixed
  `ROUND_QUESTIONS` entry carries its line as a third element, which its own
  pattern must hear, and the turn ends on it. **A transcript delta's words
  are the string `payload.delta`** (`deltaOf`, `noteMiraDelta`): the room
  read `delta.transcript`, so the mid-sentence sign-off cut had never fired
  and she said "you can hang up now" whole, twice, mid-round. **After a
  sign-off in the round the question in play is handed again as that turn's
  instructions** (`rehandAfterSignOff`, with "you spoke too soon" in front of
  it after the fact), never by a note; a sign-off line is never an
  asked-nothing round turn. Guards `tests/test_round_sign_off_2026_10_23.py`.
  **Her briefs never say "lightning"** (rehearsal 39987282078: handed the
  scripted words, she still ran a quickfire of her own, coffee or tea, ocean
  or mountains, in place of the advice and inspiration questions; "the five
  lightning questions" in her brief named a round and left her to fill it).
  The brief says five short closing questions whose words the room gives,
  and that they are the whole round.
- **Her line ends when it has been HEARD, not when it was generated.**
  `response.done` arrives seconds into a line that plays for half a minute
  (the welcome: 87 words generated by 21:10:41.9, playing until ~21:11:05).
  The room had read it as the end of her turn, so the dead-air clock fired
  while she was still talking, its re-ask repeated the welcome, and the guest
  heard 58 s of Mira with the welcome twice (session log of run 1ca8839a).
  `miraAudibleUntil` is estimated from her line's words
  (`MIRA_MS_PER_WORD` 320, measured ~290 on that room's recording, queued
  lines pushed back) and cleared wherever the room clears her audio
  (`miraSilenced` beside every `clearMediaBuffer`); `requestTurn` parks, and
  `decideTurn` and the dead-air clock wait, until it has passed. A cancelled
  server turn IS silent (`response.done status=cancelled` within ~50 ms, no
  audio) — read from the full session log, which the "Voximplant session
  logs" workflow now attaches whole (it had kept a 60 kB tail, the last two
  minutes). The hold check-in note asks for a few spoken words: under
  "Nothing else" it came out as the one word "Silence."

- **Seven closing questions** (Oct 23 2026, Patrick): the show's own
  question, the book, who to interview next, the best advice, who inspired
  them, how being interviewed by an AI was together with one improvement,
  and last a follow-up interview in six months to a year. Asked separately at
  the end, the two interview questions read to her as the end of the show
  (rehearsal 39991520039: three goodbyes in their place). The scenario,
  `fire_interviews.CLOSING_ROUND` (same order, without the show's question)
  and both briefs change together. **A question whose words never reached the
  guest is not answered by what they say next**: the room hands it again, at
  most `ROUND_UNHEARD_REHANDS_MAX` (2) times; each round turn says how many
  questions are still to come; after her closing thanks she has one goodbye
  and no turn to an empty room (`AFTER_CLOSE_TURNS_MAX`); no time notes once
  the round is over. `audio_metrics.closing_round` reads the round's size
  from the room's own `asked n/N` lines. Guards
  `tests/test_round_end_2026_10_23.py`.

- **Her brief names no closing question** (rehearsal 39998790684): told the
  round held "four short closing questions, one about the interview itself",
  she wrote her own ("what did you learn about yourself doing this
  interview?") and spoke its label ("That's the show's own closing
  question"). The room hands her each question's words; both briefs say only
  that, and that there is no thanks or goodbye until the room says to close.
  A turn that asks ANOTHER round question is never this one reworded, and the
  "interview next" topic check no longer takes any word "interview". Spoken
  turns end on "stop talking", never "in silence" or "nothing else" (she says
  "Silence." and "Nothing.").
- **A person can sit in a draft room**: Actions "Nerra Voices — rehearsal"
  with `invite_email` (and `candidate_scenario`) runs `rehearsal.py invite`:
  a rehearsal-only application and interview (status and session_kind
  `rehearsal`, no co-host), Mira's brief compiled from that person's own
  latest application, and an email with a studio link carrying
  `room=candidate`, which dials `mira-candidate` (routed to the candidate
  scenario by `CANDIDATE_ROOM_RULE_PATTERN`). The job waits up to 90 minutes
  for them to join, then measures the room like any rehearsal. The link and
  the address never go in a log (the repository's Actions logs are public).

Operator: deploy the scenario only after the candidate rehearsal reads PASS and
one listen; `wrangler deploy` in `workers/voices` so the new counters are
stored. ⚠️ AUDIO on every interview.
- **The closing round from a real room (Oct 24 2026, run b579faba, read from
  its trace, transcript and full session log; guards
  `tests/test_round_from_stuarts_room_2026_10_24.py`, sim `stuart_room`).**
  "Her turn asked nothing" is decided ONCE, on the final transcription of the
  turn the room asked for (`roundTurnInFlight`, set in `markTurnStarted` for a
  requested turn; a turn with no transcription is taken as asked,
  `roundTurnDone`). **A question is handed again at most once, whatever the
  reason** (`ROUND_REHANDS_MAX` 1, `owedRehand`); then it is taken as asked
  (trace `taken as asked:`, which makes `closing_round_complete` false). **The
  index never moves back** (`roundRehandOwed` re-hands at the same index; no
  `roundIndex -= 1`). Every round turn hands **the words of a whole question,
  last**, after directions with nothing speakable in them (no "silence", no
  "stop talking"); the show's question comes from her brief
  (`showQuestionText`), and a question with no words is skipped, never
  described. A guest who declines a question, or hears "who should I
  interview next" as one about himself, has answered it (`ROUND_DECLINE_RE`).
  **Nothing is taken back on air**: a goodbye heard whole is followed by the
  question in play with no retraction while it can still go again, else the
  interview ends on it (`acceptSignOff`), and a guest's goodbye after it ends
  it too. **No turn with no guest in the room** (`requestTurn`, `roundGuestGone`).
  **The room starts the round when it is DUE** (`closingRequired`, minute 36
  of 45): a show question she asks herself in the window is recorded and
  skipped, and the window note tells her not to begin it. **A round turn
  carries a short brief of its own** (`roundBrief`: who she is and who the
  guest is, plus any hand-over note; never the closing script) and directions
  that never name the end; only the closing thanks carries the whole brief
  (candidate rehearsal 40110915521: with the whole brief she asked "the last
  thing you want to say before we finish" at question three). A goodbye past
  `ROUND_CLOSE_BLOCKS_MAX` ends the interview there, and a guest saying
  goodbye in the round (`GUEST_LEAVING_RE`) gets her closing thanks.
