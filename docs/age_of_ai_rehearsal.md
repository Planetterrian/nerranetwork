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

Actions → **Nerra Voices — rehearsal** → fixture, minutes (10), rooms per
arm (3), arms (both), and for the proposed arm an optional end-of-turn
silence, reasoning effort and tools setting. The run attaches every room's
JSON (metrics, config, listen link, transcript) as an artifact and prints
the verdict table in the step summary. Nightly runs happen only while the
repo variable `VOICES_REHEARSAL_NIGHTLY` is `true`.

Locally:

```
python pipelines/voices/rehearsal.py run --arm current  --fixture roddy --minutes 10 --repeat 3
python pipelines/voices/rehearsal.py run --arm proposed --fixture roddy --minutes 10 --repeat 3 \
    --turn-silence-ms 1300 --reasoning-effort low
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

## What PASS means

The report takes the median of each metric over an arm's rooms and prints
**PASS** only when the proposed arm:

| metric | rule |
|---|---|
| `overlap_events` | lower than current |
| `self_answered_turns` | lower than current |
| `guest_words_per_answer_median` | higher than current |
| `mira_turn_sec_median` | not further from the 12–20 s band than current |

Anything else is **FAIL**; a missing arm or metric is **INCONCLUSIVE**,
never a pass. The CLI exits non-zero on anything but PASS.

**The rule that binds:** a change to the prompt, the end-of-turn setting,
the reasoning effort or the rotation policy ships to a real guest only on a
PASS *and* after the operator has listened to one room of each arm (the
listen links are in the report). A measurement is not a listen — the Oct 20
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
