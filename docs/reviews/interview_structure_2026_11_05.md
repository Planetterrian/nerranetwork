# The shape of the hour: structure for Mira's interviews (Nov 5 2026)

## The ask

Patrick, after Blaine Mathieu's room: *"I think what Mira is lacking is a
little more structure to the interview with more prepared questions versus
just asking a question then repeating a short summary and continuing on the
same thread. A good interviewer usually knows when to move on and change the
subject and have a little more conversation with the interviewee when it is
appropriate."*

## What the record showed

- **Prepared questions mostly went unused.** Across the nine rooms before
  this pass she reached 9 of the 63 prepared questions in their briefs.
- **The rooms were one thread.** Most rooms took the opening question's
  subject and followed it down for half the hour. The turn shape was a label
  phrase for the answer and then a follow-up on the same point.
- **The grades say the same.** The last nine graded rooms averaged overall
  5.1, questions 5.6 and pacing 4.4. The written reasons cite mechanical
  summaries and an hour that never moved.

## Why it happened

Every part of the system pointed down the same thread:

1. **The brief said to.** HOW TO LISTEN told her to ask "the next question
   one step down" after every real answer. When the list ran out she was to
   "go back to the best thing they said and go down from there". The list
   itself was headed "follow the conversation, not the list".
2. **The time checks said it again.** Before the closing round, every
   five-minute note told her to "ask the next question down" from the most
   interesting thing the guest had said.
3. **The questions were written to be dropped.** The question-generation
   prompt said every prepared question she did not need was one she could
   drop.
4. **Nothing in the room ever said a thread had had its turns.** The room
   decides when she speaks, but never what the next subject is. The only
   way to change the subject was the guest's "move on" press, and that asked
   her for "a clearly different subject from your brief" without saying
   which one.

A voice model with no sense of elapsed time, told to go one step down after
every answer, does exactly that for thirty minutes.

## What changed

**The plan travels to the room.** `fire_interviews.interview_plan(brief)`
puts the brief's questions in running order: the opening, then the core
questions, the tension, and the forward look, keeping the written order
within each section. At most 12 go out. The run row carries them as
`grok_session_log.interview_plan`. The prompt lists the same questions,
numbered, in the same order. Hello and closing sessions carry no plan.

**The room moves a thread that has had its turns** (scenario section "The
shape of the hour").

- **Slots.** The time before the closing round opens is split into one slot
  per question. In a 45-minute room with seven questions, a slot is about
  four minutes.
- **When she moves.** After the guest's pause, the move is due if the thread
  has had at least two of her questions and the next slot has started. A
  thread that has had five of her questions moves whatever the clock says.
- **What she is handed.** The room hands her the next question **in words**,
  for that one turn. The direction is: answer anything they just asked her;
  close the thread in one sentence that carries something it gave her,
  never a summary of their answer; say she is turning, differently each
  time; then ask the question.
- **Nothing is skipped or asked twice.** A prepared question she reaches in
  her own words counts as reached (by its content words). The room's next
  hand is always the first question not yet reached.
- **When she runs behind.** Every thread still gets its two questions, and
  the moves simply come closer together.
- **Move on.** With a plan, the guest's "move on" press hands her the next
  prepared question in words. A topic press starts a new thread.
- **The guest and the close outrank the plan.** No move is made during a
  hold, the closing round (or once it is permitted), or after the guest has
  asked to stop. A pending press goes first, and a move never overwrites
  another turn's instructions.
- **Session changes.** The handover note tells the next session which
  numbers have been asked.
- **The record.** The trace carries indices and reasons only, and a summary
  at the end of the room: `reached k/n; room moves m, hers o; longest thread
  t questions`.

**The brief has a shape.**

- The prepared questions are now headed as the running order, the shape of
  the hour.
- In HOW TO LISTEN, two or three steps is a thread. Then she moves on out
  loud, the way an interviewer changes the subject. A thread that is still
  alive may run on; one that is circling has had its turns.
- When the list runs out, she reopens the best thing they said from a new
  side, not further down.
- In HOW TO REACT, once in each part of the hour she has the conversation
  instead of asking the next question: a turn of her own in two or three
  sentences (a view, or a connection to another guest or a fact), handed
  back. When the guest asks her something, she answers it properly first.
- The CRITICAL list keeps seven lines. The subject line now says the hour
  goes "in parts".
- There is no quoted line, and no guest or date appears in the brief.

**The question set is written as a running order.** Each question opens one
part of the hour and must be worth a few minutes. Each one differs in
subject from the question before it.

**A room with no plan is the old room.** The current arm of a rehearsal and
any run row without `interview_plan` behave exactly as before, and keep the
old time-check text.

## How it ships

- The scenario goes only through the candidate rehearsal and then the
  manual "Deploy Voximplant scenario" workflow.
- The brief and question-set changes go live when they merge to main.
  **Merge and deploy together, after a two-arm rehearsal PASS and one
  listen.** Without the room's hands, the brief alone still asks for two or
  three steps and a spoken move, but the structure is the room's job.
- Nothing ships before Luke's room on Nov 5.

The rehearsal report now shows, for each room, a "prepared questions" line
and a "shape of the hour" section. Read those alongside the listen: did she
close each thread with something it gave her, and did the moves sound like
a host changing the subject or like a checklist?

## Readout

Register `interview-plan-2026-11-05`. The readout covers the next five real
rooms:

- **Target:** a median of at least two-thirds of each room's plan reached,
  no thread over six of her questions, and the questions and pacing grades
  each up a point on the baseline above.

## Not done here

- The worker's end-of-room counters do not store the plan summary yet; it
  lives in the trace.
- The slot is even across the plan. Weighting the core questions longer is
  a later change, to make only after a readout.
