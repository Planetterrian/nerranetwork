# Mira's rooms of Nov 11 and 12 2026: why the grades stayed at 4 and 5

Operator request (Nov 12): continue to review and improve Mira and the
interviews so that she gets higher grades on future interview reviews.

Two real guests came through, the first since Nov 4.

| room | run | overall | listening | questions | pacing | turn-taking | warmth |
|---|---|---|---|---|---|---|---|
| Nerra Voices, Nov 11 | 01ae5157 | 4 | 3 | 5 | 3 | 4 | 4 |
| The Age of AI, Nov 12 (Rania Esmael) | a6a46957 | 5 | 4 | 6 | 3 | 7 | 6 |

Measured from the tape: label_open_rate 0.333 and 0.325, bare_question_rate
0.367 and 0.40, reaction_open_rate 0.30 and 0.275, one_liner_rate 0.233 and
0.30, her median turn 7.2 s and 6.4 s against the 12 to 20 s band, median
turn gap 4.1 s and 4.5 s. Both rooms reached every prepared question (7 of
7), all of them handed by the room. Rania rated the hour "perfect" from the
studio page; the grader did not.

## What the graders marked down

The same two things in both rooms, and the same two as in thirteen of the
twenty rooms before them.

1. **Every turn opens by folding the answer into a phrase.** A third of her
   question turns open on a fragment of a few words taken from what the guest
   just said, and another third ask with nothing of hers before the question.
   Fewer than three in ten carry a sentence of her own. The brief has said
   not to, by shape, since Nov 4 (HOW TO REACT and the critical list's last
   line). It did not move.
2. **Pacing.** Median gaps over four seconds, and silences the room left
   standing (137 s and 225 s of dead air in total).

## What Rania's trace and transcript showed that no instrument counted

1. **She asked to hear the question again about eight times, aloud.** Earlier
   rooms had none to four. She works in her second language; the prepared
   questions ran 19 to 33 words in one sentence with the setup inside them,
   the room handed each "in these words", and on a repeat Mira said the same
   question again at nearly full length. The room acted on a repeat only when
   it came from the studio button. One question that quoted an earlier guest
   by name needed two repeats and a clarification.
2. **In the closing round "the one what?" was taken as the answer** to the
   show's question. The room handed the book question; Mira, sensibly,
   re-asked the bet; the room logged that as "asked something else" and
   spent the book question's one re-hand on it.
3. **The book question was never asked.** Handed it again, she reacted to
   the previous answer and asked nothing; with the re-hand spent, the room
   took the question as asked and moved on.
4. **A false hold.** The guest said she would email. Mira answered that she
   would be here. The room read a wait, went on hold for 64 seconds with the
   guest present, and Mira then welcomed her back.
5. **A turn that asked nothing, then silence.** In the round a reaction with
   no question was followed by 17 seconds before the room handed the
   question again: it waited for a guest who had been asked nothing.

The prepared questions for the three rooms booked on Nov 13 are the same
shape: 23 to 42 words, most of them one sentence.

## What changed

All of it is in the room, the question writer or the instruments. The brief
gained one clause and one reworded line (1,589 words, under its 1,600
budget) and no prohibition.

**The room (`voximplant/scenarios/age_of_ai_interview.js`; deployed only
after a candidate rehearsal PASS and one operator listen):**

- **The shape of her turn is rotated by the room** (`TURN_SHAPES`,
  `noteOrdinaryTurn`, `takeTurnShape`). On every second ordinary turn after
  a real answer the room hands her the shape of that one turn as that
  response's instructions, a different one each time: join this answer to
  something said earlier; say what it makes harder or where she sees it
  differently; say what she did not expect and ask for one instance. Each
  asks for a full sentence of her own in none of the guest's phrases, then
  one short question. The turns between are hers. A standing brief cannot
  remember what she did on her last turn; the room can, which is why three
  brief rewrites did not move the habit. Never in the opening minutes, the
  closing round, a hold, a hello or closing session, after an answer under
  15 words or a question put to her, or on a turn that already carries a
  plan move, a steer, a repeat or research. Off for one room with
  `grok_session_log.turn_shapes = false`. The trace line is `shape`.
- **A spoken request to hear the question again is the repeat button**
  (`GUEST_REPEAT_RE`, judged on a reply of 25 words or fewer). On an
  ordinary turn her next turn is her own last question, handed back in
  words, to be asked as one short plain sentence and nothing else; asked a
  second time in a row, she is told not to ask it a third time and to ask a
  much simpler question about the same thing. No plan move rides on that
  turn. In the closing round it is not an answer: the same question goes
  again in plainer words (at most twice), and the re-hand allowance is not
  spent on it. Counted as `guest_repeat_asks` in the end-of-room record; the
  trace line carries a count and never the guest's words.
- **A closing turn of hers that asked nothing is followed by its question**
  2.5 seconds after her line has been heard (`continueRoundTurn`), unless
  the guest starts speaking first, in which case they keep the floor as
  before.
- **"I'll be here" is a wait only when it says so**: "right here", "here
  when / whenever / once / until", or after "take your time"
  (`MIRA_HOLD_RE`).
- **A prepared question over 24 words is handed for the ear**
  (`planQuestionLine`): its meaning, said as one short question in everyday
  words, with any setup as its own short sentence first. This is the part
  that reaches the questions already written for the rooms booked this week.

**The brief (`mira_system_prompt.txt`; live on merge):** HOW TO LISTEN asks
for one short question per turn, one idea in everyday words, and for a
shorter, plainer version when asked to hear it again. The critical list's
first line says the same in eight words.

**The prepared questions (`question_generation.txt`,
`generate_briefs.questions_for_the_ear`; live on merge for briefs written
after it):** the writer is told the shape with numbers (the question is one
sentence of at most 22 words; setup is one sentence of at most 16 before
it), a cross-guest callback is a short statement and then its own short
question, and the length is checked in code: a question that misses gets
one rewrite call, kept only when the rewrite passes. A failed rewrite never
costs the brief.

**The instrument (`audio_metrics.guest_repeat_requests`):** counted from the
guest's own track for every room, read by the grader (beside the turn
shapes), the retro email and the rehearsal's "Read beside the verdict"
table. The room's pattern and the metric's are one list of phrases in the
guard.

## What was not changed, and why

- **The reasoning effort.** A trial on main (run 43229324181: adrian, two
  rooms an arm, medium against the deployed high, the brief the same in
  both) reads the turn gap in isolation. Its result is in the PR; changing
  the default is the operator's call after a listen.
- **Dead air between ordinary turns.** The two rooms' long silences sit
  mostly after turns of hers that asked nothing and inside the false hold.
  The round's case is fixed here; the ordinary-turn case is read again once
  the shaped turns (which all end on a question) are in a real room.
- **The questions already written for the rooms booked on Nov 13.** The
  guests were sent them. The room's hand line is what makes them speakable.

## How to read it

Rehearsal first (candidate scenario, both arms, two rooms an arm): in the
proposed arm reaction_open_rate should rise and label_open_rate fall with
bare_question_rate not rising, mira_turn_sec_median should move toward the
band, turn_gap_ms_median must not rise (every shaped turn carries
instructions), and overlaps and self-answered turns must not rise. Then one
listen. Then the register entry `mira-rooms-2026-11-12` reads the third
real room after the deploy.

Guards: `tests/test_mira_rooms_2026_11_12.py`.
