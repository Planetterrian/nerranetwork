# Blaine Mathieu's interview: why it scored 5, and what moves the score

Run `43ff31a6`, Nov 4 2026, 36 minutes of 45 planned. Graded 5 overall
(listening 6, questions 7, pacing 4, turn taking 5, warmth 6) at 17:18 UTC,
before the retrack (20:02 UTC) that fixed Mira's drifting track.

## What cost the points

1. **The close (room).** He asked to end at 35:01 ("I think we probably got
   enough here ... do a final ending comment you can make it now"), again at
   35:53 ("let's wrap it up.") and once more after ("we ended it"). None
   matched `GUEST_STOP_RE`, so the room cut two goodbyes mid-sentence
   (the cut-outs he heard), she asked a new question, and the scheduled
   note started the closing round after his goodbye. He left at 1/7.
2. **Typed messages (room).** "you still there" (25 min, after a silence)
   and "lets wrap it" (30 min; no "up", so not `TYPED_WRAP_UP_RE`) were
   steered as topics: "This is something you wanted to get to."
3. **The grade read misaligned audio.** Mira's track ran 17 to 59 s late in
   the second half; the 7 self-answered turns, 10 overlaps and negative
   gaps the grader cited were partly artifacts.
4. **The label before the question (craft).** 16 of about 26 question turns
   were one short label line, then the question. Her best turns (07:35
   Ford, 12:13 her own view, 18:24 McKinsey) were built from a fact or a
   view; research supplied eight facts in the hour.
5. **The pitch ran (craft).** Two long plugs went unredirected and she
   repeated the URL; an evasive answer at 29:57 was accepted.

## Fixed Nov 5 (room, rehearsal plus a listen before a real guest)

The stop shapes above, the typed wrap-up without "up", a presence check
that is a message, and `roundDueOnTheClock` so the clock never starts a
round after a stop. Rehearse with the `early_wrap` input.

## Still open

- Regrade Blaine (and retrack and regrade Priyanka, Nov 4) on retracked audio.
- Lessons crowded out by `PROMPT_LESSONS_MAX`: ask for the case on a vague
  answer, ask the uncomfortable question once. Move them into the brief by
  shape, after Luke Miler's room reads the Nov 4 brief cleanly.
- A shorter open; a bridge built from a research finding when one is in hand.
- The grader marks the room's ~4.5 s turn-gap floor as her dead air.
