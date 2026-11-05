# What the guests typed, and why it did not steer Mira (Nov 5 2026)

Read from `interview_runs.grok_session_log.guest_feedback` and
`scenario_trace` for the two rooms that used the studio panel, against each
room's transcript.

## What they sent

| Room | Minute | Press | Acked | What Mira did |
|---|---|---|---|---|
| Blaine Mathieu `43ff31a6` | 25 | typed "you still there" | applied | Treated it as a subject he wanted to reach |
| Blaine Mathieu | 30 | typed "lets wrap it" | applied | Treated it as a subject; the round did not start |
| Priyanka Sharma `ea81618b` | 22 | Move on | applied | Kept following up on formulation for three more turns |
| Priyanka Sharma | 29 | Move on | applied, on a dead-air nudge | Re-asked the board-of-pharmacy question |
| Priyanka Sharma | 30 | typed "I'd like to talk about the entrepreneurship in the industry" | applied, on a dead-air nudge | Asked "Has any legislator changed their mind", then "Has any board of pharmacy said no to you?" |
| Priyanka Sharma | 30 | Move on | applied | Moved only after Priyanka said the subject aloud ("Let's try to talk about entrepreneurship") |
| Priyanka Sharma | 35 | Move on | applied, on a dead-air nudge after a hand-over | She left 15 s later |

Then at 33:58 she said "I'd like to wrap up the interview now". The room
did not hear a stop, cut Mira's goodbye twice mid-sentence ("a sign-off
with the closing round not yet run"), and Mira asked three more questions.
She also asked twice, out loud, for a question to be repeated.

## Why

1. **A guest who presses is quiet.** They are reading or typing, so the
   request waited for her next turn, and in a silence that turn is the
   dead-air nudge 20 s later. The nudge posts a conversation note, "put your
   last question to them again, more simply", and the steer rode the same
   turn as the response's instructions. Two instructions that disagree; the
   note in the conversation won three times out of three.
2. **The move-on named nothing to leave.** "A different subject from your
   brief" after a long brief read as a different angle on the same one.
3. **Blaine's two messages** were the shapes fixed in
   [`blaine_mathieu_2026_11_05.md`](blaine_mathieu_2026_11_05.md)
   (presence check, typed wrap-up without "up").
4. **"wrap up the interview now"**: the interview as the verb's object broke
   every stop shape in `GUEST_STOP_RE`.

## Fixed (room; rehearsal plus a listen before a real guest)

- `steerWhenTheFloorIsFree`: 1.5 s after a press, if nobody is talking, her
  line has played out and no turn decision is pending, the request takes her
  turn now. Anyone talking keeps the floor; the request rides their pause.
- A queued request replaces the dead-air nudge's note.
- Move on and the new Repeat hand her her own last question in words.
- The studio: **New subject**, **Repeat the question**, **Good question**,
  **Let's wrap up** (a second press within 5 s confirms; it starts the
  closing round through the typed wrap-up path). Two by two on a phone.
- `GUEST_STOP_RE` takes "the interview / the conversation / the recording"
  as the object; "end the interview with a story" is still no stop.

Guards `tests/test_guest_steers_2026_11_05.py`.

## Not fixed here

- The ack "Mira has it now" means the request reached her turn, not that
  she followed it. A check that her next line left the subject would need
  the guest's words in the room, which the live room does not have.
