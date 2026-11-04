# The Age of AI: a feedback panel and Mira's picture in the studio (Oct 23 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### The Age of AI: a feedback panel and Mira's picture in the studio (Oct 23 2026)

Operator-directed (guards `tests/test_studio_feedback_2026_10_23.py`). The
studio page (`age-of-ai-studio.html`) lets the guest press **Good question**,
**Move on**, one of their own agenda points ("Ask me about…", from
`guest_applications.guest_agenda` via studio-state's `agenda`,
`studioAgenda`, five at most) or type a subject (240 chars). Nothing is said
on the recording. Rules that bind:

- **The page sends `{nn:1, kind, text}` over the call's message channel**. The
  participant session relays it to the room (`relayPageMessages`) and the room
  answers with an ack (`queued` / `applied` / `noted` / `hold` / `closing` /
  `empty` / `full`). The page shows each ack in words. When no ack arrives in
  6 s, it tells the guest to say it out loud.
- **A move-on or a topic is that ONE response's instructions at her next
  turn** (`takeGuestSteer` inside `requestTurn`, after a room turn). It is
  never a conversation note, which is the round's lesson.
- **Typed text is data, fenced in quotes and stripped of quotes, brackets
  and control characters** (`cleanFeedbackText`). The trace never carries it.
- **Never during a hold or the closing round.** A press is acked
  `hold`/`closing`, and a queued one is dropped when either begins
  (`dropGuestSteer`). "Good question" only records the question.
- Every press goes to the end-of-room webhook as `guest_feedback` /
  `guest_steers_applied`, stored by `roomCountersOf`.
- **Mira's picture** (`assets/mira/mira-studio.mp4` + `.jpg`, a muted
  10 s loop) plays while the room's audio is voiced and rests on the still
  when it is quiet. With no audio access it stays still. The page says it is
  an illustration of an AI that cannot see the guest.

Operator: `wrangler deploy` in `workers/voices` (agenda + stored presses).
Deploy the scenario only on a candidate rehearsal PASS plus a listen. The
page is live on merge.
