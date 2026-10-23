# The Age of AI — rehearsal harness

*Oct 21 2026, from §7.5 of
[`docs/reviews/age_of_ai_review_2026_10_21.md`](reviews/age_of_ai_review_2026_10_21.md).*

Every other audio-affecting change in this network goes through an A/B
listen before a listener hears it. The interview show had no way to make
one: the only person who could sit on the other end of a rehearsal was a
real guest, and the Oct 19 prompt rebuild went into Jon Cheney's room the
same afternoon. This harness gives the show a guest who is not a guest, a
room that runs the real scenario, and a report that says whether a change
is better on the numbers that matter before anyone books it against a
person.

## What it is

- **A fixture guest.** `voximplant/scenarios/age_of_ai_fixture_guest.js` is
  a second Voice Agent that joins an interview room exactly the way a human
  leg does (`callConference("room-<run id>")`, role `guest`, the path the
  room probe already took) and plays a PAST guest. Its persona is rendered
  by `pipelines/voices/rehearsal.py` from the guest's published episode in
  `digests/age_of_ai/` (`pipelines/voices/prompts/fixture_guest.txt`: the
  About section, "What we talked about", and the guest's own transcript
  lines as a register sample — never Mira's lines). It records its leg and
  reports it through `/voices/leg-event` as a guest leg, so post-production's
  transcription reads it like any guest.
- **Three fixtures**, chosen for three registers
  (`pipelines/voices/fixtures/rehearsal_guests.yaml`): `roddy` (Roddy de la
  Garza, a warm storyteller who gives long answers), `vincent` (Vincent
  Rylan, terse, answers in a sentence and waits, says hello before the
  opening), `adrian` (Adrian Wolfberg, analytical, long arcs with pauses
  inside them). A change must hold up on all three.
- **Scheduled behaviours**, the same in every room, so two arms differ only
  in Mira's configuration: at minute two the fixture stops mid-sentence for
  two full seconds; at 3.5 it coughs (a clip played into the leg, repo
  variable `REHEARSAL_COUGH_CLIP`); at five it says "let me think" and
  waits; at 6.5 it pushes back on a question once; at eight it asks who
  someone is when a name is dropped. It never speaks first unless the
  fixture says so, never hosts, answers only the last of two questions, and
  stops when talked over.
- **Two arms.** `proposed` is what `fire_interviews.compile_mira_prompt`
  writes today on the fixture's real application, brief and lessons;
  `current` is the prompt the last completed real interview actually ran on
  (read from `interview_runs`, never from the repo). The proposed arm can
  carry an end-of-turn override, a `reasoning_effort` and a tools setting.
- **The measurement** is `pipelines/voices/audio_metrics.measure_audio` on
  per-speaker Whisper words placed on the room clock with
  `post_interview.room_offsets`: overlap, turn gaps, Mira's turn length, the
  guest's words per answer, self-answered turns, echo-open rate, the
  closing round, seams.

## Running it

Actions → **Nerra Voices — rehearsal**. The defaults are one room of the
proposed arm, twelve minutes long, on `roddy` (Oct 23 2026). A twelve-minute
room opens the closing round at minute eight, so one room exercises the
opening, the turn decisions, the scheduled behaviours and the whole round.
Tick `candidate_scenario` to rehearse this branch's room code beside the
live one; `with_hold` adds the phone call at minute four. Choose `both` and
more rooms only for a prompt or setting change, where the two-arm
comparison below is the question.

Before any room is placed the job sends xAI one tiny text request
(`rehearsal.py preflight`): a 401/403, or a 429 that names credit, stops the
run with an error and no room is placed. During the run, a room in which xAI
refused every session (and Mira never answered) is recorded as refused, is
not transcribed, and no further room is placed.

The run attaches every room's JSON (metrics, room log, config, listen link,
transcript) as an artifact and prints the report in the step summary.
Nightly runs happen only while the repo variable `VOICES_REHEARSAL_NIGHTLY`
is `true`; with the defaults that is one room of the live configuration a
night.

Locally:

```
python pipelines/voices/rehearsal.py preflight
python pipelines/voices/rehearsal.py run --arm proposed --fixture roddy
python pipelines/voices/rehearsal.py run --arm proposed --fixture roddy --scenario candidate
python pipelines/voices/rehearsal.py report outputs/rehearsals/<day>
```

`--prompt-file` rehearses a prompt from disk instead of compiling or looking
one up. Results go under `outputs/rehearsals/` (gitignored).

One-time setup: the deploy workflow (**Deploy Voximplant scenario**) uploads
the fixture scenario beside the interview scenario and creates its rule
(`age-of-ai-fixture-guest`, pattern `^fixture-guest-never-dialled$`, so it
can never catch an inbound call). The runner creates a `guest_applications`
+ `interviews` pair per fixture with status `rehearsal` and
`session_kind: rehearsal`, which the fire cron, the screen, the briefs and
the reminders never select.

## What it costs

Every room runs two Voice Agent sessions, Mira and the fixture guest. The
report prints the room minutes and an estimate at
`XAI_VOICE_COST_PER_MIN` (default $0.05 per session minute; check the
voice line in the xAI console). One default room is about 25 session
minutes. The Oct 22-23 pattern (two arms, two or three rooms each, 22
minutes) was 90-130 session minutes per check, and 34 rooms in two days
came to about 870.

## The room log

Each room's report section is read from the room's own trace and Mira's
transcribed words (`rehearsal.room_log`):

- the room's length against its plan, how it ended, sessions started,
  refused and rescued;
- the turn decisions (server turns rerouted, unfinished-clause waits,
  dead-air nudges) and holds entered and left;
- the closing round line by line as the room traced it, and a table of
  each closing question: when the room handed it and when her words first
  carried it. A question her words carry after the next one was handed, or
  more than 45 s after it was handed, is a turn behind; a question her
  words never carry is lost (the match uses the room's own patterns, so a
  reworded question reads as lost: listen before calling it).

Every fault the rehearsals found on Oct 22-23 (the silent hold exit, dead
air after a rescue, the repeated welcome, the round a turn behind) was
read here, not from the medians.

## What PASS means

**One arm (the default).** Every room is held to the checks a room can be
held to, from the review's §7.7 targets:

| check | rule |
|---|---|
| room ran | at least 75% of its planned length, not refused |
| self-answered turns | none |
| talking over | under one overlap event per ten minutes |
| closing round | complete (each question once, none said late, none repeated, all answered) and every question in her words, none a turn behind |
| dropped session | none rescued, none given up |

A failed check is **FAIL**; a check a room cannot answer (the round never
began) is **INCONCLUSIVE**, never a pass.

**Two arms** (`both`). The report takes the median of each metric over an
arm's rooms and prints **PASS** only when the proposed arm:

| metric | rule |
|---|---|
| `overlap_events` | lower than current |
| `self_answered_turns` | lower than current |
| `guest_words_per_answer_median` | higher than current |
| `mira_turn_sec_median` | not further from the 12–20 s band than current |

Read it with care: the same configuration's guest words per answer ran 31
to 84 across rooms, so a two-room median moves on the fixture, not only on
the change.

**The rule that binds:** a change to the room, the prompt, the end-of-turn
setting, the reasoning effort or the rotation policy ships to a real guest
only on a PASS *and* after the operator has listened to the room (the
listen link is in the report). A measurement is not a listen — the Oct 20
`[breath]` tag measured cleanest and was heard as too prominent.

## What it cannot do

- A fixture is a model playing a person: it will not be surprised, bored or
  moved. It tests turn-taking, pace, echo and the closing round; it does
  not grade warmth or whether a question landed with a human.
- The cough is a clip; without `REHEARSAL_COUGH_CLIP` that beat is skipped.
- The co-host is never in a rehearsal room.
- The Worker must treat a `session_kind: rehearsal` run as one to record and
  leave alone (no editorial passes, no gate-1 email, no guest email). Until
  it does, a rehearsal room's completion webhook would dispatch
  post-interview processing like a real one.
