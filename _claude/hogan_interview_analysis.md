# The Age of AI — Hogan Shrum interview: what the tape shows

Recorded 11 September 2026. Room open 00:26:57 UTC to 01:08:12, 41 minutes.
Hogan joined at 00:32:11 and left at 01:04:57, so the conversation itself
runs about 33 minutes.

## What went right

The infrastructure held. One continuous room, no drop, no reconnect. The
session hand-over at the 26-minute mark worked exactly as designed: fresh
session bridged in 0.7 seconds, old one closed, conversation carried on
without a seam. That is the failure that split Matt Davis's interview in
half the night before, and the fix did its job on its first real outing.

The per-join take id worked too. Hogan's browser track is intact at 33
minutes, yours at 40, nothing overwritten. Under the old code the two
ten-second rejoins at the end would have destroyed both.

And the conversation is good. Hogan spoke 4,250 words to Mira's 558 — an 88
percent guest share, which is what a well-run interview looks like. He gave
specifics rather than talking points: the first artist to sign was a
photographer, not an illustrator, because nobody wanted to be first across
the picket line; the royalty pays on every generation including test renders
that never ship; a named projection of what a 5 percent style share earns at
250,000 users.

## What Mira got wrong

**She performed the opening to an empty room.** At 00:00 she delivered the
full cold open — her name, the show, "where are you calling from" — with
only Patrick present. Hogan arrived five minutes later and she did the whole
thing again. This is the second consecutive episode with this defect; it is
also the single most visible thing a guest experiences.

**She interrupted him 23 times.** Not near-misses: these are places where
she began speaking more than two seconds into an utterance he was still in
the middle of. A sample:

- 08:43 — Hogan mid-sentence about what he wanted from a tool; Mira starts
  "What does that kind of control actually unlock..."
- 09:58 — Hogan still describing his workflow; Mira starts reading out a
  Verge citation about royalty figures
- 27:29 — Hogan explaining the revenue backstop; Mira cuts in with the next
  question
- 37:10 onward — Hogan is still finishing his closing bet when she begins
  wrapping the show, and talks across him four separate times

The 37:10 cluster is the worst of it. She thanked him, handed to Patrick,
and asked for final thoughts, all while he was still answering the question
she had just asked.

**She read citations aloud.** At 09:58 she says "The Verge piece from August
2026 does quote..." on air. Research should inform a question, not be
recited into the microphone.

**She kept talking after he left.** He dropped at 38:00. She was still
saying "Thanks, Hogan, that wraps our conversation" at 39:42 and "great
conversation today" at 39:59, to nobody.

## What I got wrong

The learning loop ran for the first time on this episode and two of its
three numbers were wrong, which is worse than not measuring at all because a
wrong number looks like a finding.

**Guest talk share came back as 0.0.** I passed the guest's first name while
the transcript labelled him GUEST, so the lookup matched nothing. The true
figure is 88 percent.

**Dead air came back as 2,035 seconds** in a 41-minute room, which is
impossible. The cause is the real defect underneath both: the pipeline
merges each speaker's transcript on that speaker's own clock. Every
per-speaker recording starts when that person's leg connects, so Hogan's
track began 5 minutes 14 seconds after Mira's, and the merge put his answers
before her questions. That is why the retro pass concluded she re-asked a
question he had already answered — right conclusion, wrong reasoning, from a
transcript that was lying to it.

This has been wrong for every interview where people did not join at the
same moment. Matt Davis's transcript has the same defect.

**I left interruptions unmeasured**, on the grounds that the data could not
support a number. That was true, but it was true because of the clock bug,
not because the measurement is impossible. Fixed, it is 23 for this episode.

**And the Worker kept the last host leg rather than the first**, so the
ten-second rejoin at 01:07:18 overwrote the URL of the forty-minute leg. The
audio survives only because the browser recording is separate.

## Fixed in code

- Every speaker's transcript is now shifted onto the room clock, using join
  times from the session trace.
- Talk share finds the guest whatever the transcript calls them.
- Interruptions are counted, from line spans estimated at the host's pace,
  labelled in the notes as an estimate rather than a measurement.
- The first host leg wins its recording URL; later legs are kept alongside.

## What needs your decision

Four lessons are sitting as proposals on the gate-1 review pages. Three are
now confirmed by two consecutive episodes and I would promote all of them:
ask one question then stop; let a guest finish a sentence; never perform the
opening to an empty guest chair. The fourth — stop delivering your own
analysis and advice — came from Matt's episode and did not recur here.

Two more I would add from this tape:

- Do not read sources aloud. Research shapes a question; it is not script.
- When the guest leaves, stop talking.

The empty-chair problem is worth fixing in code as well as in instruction.
Mira currently opens after a 20-second timeout whether or not a guest is
present. She should wait for a guest, indefinitely, and greet the co-host in
one line meanwhile.
