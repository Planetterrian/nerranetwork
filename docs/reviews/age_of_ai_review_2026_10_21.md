# The Age of AI — full pipeline, interview and learning-loop review (Oct 21 2026)

Operator brief: review the whole Age of AI pipeline (workflow, learning loop,
grading, production) and every interview, then say how Mira's interviewing
gets drastically better and how the system keeps improving after every
interview on its own.

What this review read, in full: the eleven published Age of AI episodes
(Ep2–Ep12) and the three Nerra Voices episodes; the three unpublished
interviews of Oct 19–20 (Cory O'Daniel, Jon Cheney, Jason Shumard) from
`editorial_packages.transcript_cleaned`; Mira's live prompt as compiled for
Jon Cheney (43,047 characters, from `interview_runs.mira_system_prompt`);
every row of `episode_grades`, `episode_metrics`, `show_lessons`,
`host_phrases`, `editor_cuts`, `editorial_packages` and the scenario traces of
the last two rooms; `pipelines/voices/` (prompts, `learning.py`,
`fire_interviews.py`, the editorial passes), `voximplant/scenarios/age_of_ai_interview.js`,
`workers/voices/src/index.ts`, the four design docs and the two earlier Grok
reviews. The audio itself was not listened to; where a transcript could be a
placement artifact rather than what was said, this review says so.

## 1. Verdict

The factory around the interview is unusually complete for a show that is six
weeks old: application screen, brief, room, three-track recording, eight
editorial passes, two human gates, a grading pass that writes its own
standing instructions, a closing-session mechanism, guest picks and
referrals. The interview inside it is not yet good, and the learning loop is
not making it better. Grades over the thirteen graded interviews run 7, 7, 4,
7, 6, 6, 5, 2, 6, 4 with no upward trend; Mira's median turn fell from 28
seconds in September to 7.6 seconds on Oct 19; interruptions in the last
two rooms were the highest recorded (14 and 14); one guest in October left
at six minutes ("this question sucks … it doesn't feel like a conversation")
and one in September asked for a re-record. The guests who stayed were
generous about the questions and consistent about the experience: "talking
to an answering machine", "not as personal", "a little too quick for me",
"pressure to keep talking without pause".

Four causes account for nearly everything in the transcripts, and the loop
addresses the wrong one:

1. **Turn-taking is mechanical and the mechanics are wrong.** A 1.1-second
   silence ends the guest's turn; a timer rotates the model mid-answer every
   26 minutes; the room greets the guest the instant they join; four code
   paths start Mira speaking without checking whether anyone else is. These
   produce the interruptions, the stacked questions, the cut-off answers and
   the moments where Mira answers her own question. No prompt can fix them,
   and the prompt has been trying since September.
2. **The prompt is a 43,000-character rulebook written as case law.** It
   carries 75 prohibitions, 17 dated incident narratives and 36 quoted
   specimen lines, most of them examples of the exact thing she must not
   say. The network's own doctrine (CLAUDE.md: de-seed by shape, never with a
   quotable example; an instruction the model breaks is enforced in code) is
   violated on every page of it. The result is compliance-shaped speech: a
   host reading rules, which is what a guest hears as a form being filled in.
3. **The research posture makes her an examiner.** The brief, the fact-check
   tool and the cross-guest callbacks produce "I cannot verify that claim in
   public records. Where should I look?" (a guest then searched the USPTO on
   air for ninety seconds), "Can you name one verifiable project" to a
   novelist, "If an outside auditor examined the $1.4 million…" to an agency
   owner, and "Vincent Rylan told me… Is he right?" dropped on a real-estate
   broker, who answered with a beauty-pageant analogy because the question
   had nothing to do with him. Guests feel tested; the prompt now says not
   to, but the inputs that cause it are unchanged.
4. **The loop grades from a transcript that cannot hear.** Interruptions and
   dead air are estimated from line starts; the grader has been documented
   mis-reading bleed, placement and channel labels; exactly one guest in
   thirteen has written feedback into the system; every change ships
   straight to the next real guest with no rehearsal and no control. The
   loop adopts a new prohibition after each tape, Mira develops a sibling
   tic to replace the banned one ("That's a crisp answer" became "Test
   mode." / "A training company." as a one-word echo on every turn of the
   Jon Cheney interview), the grader bans that, and the hour gets colder.

The fix is in that order: room mechanics first, prompt second, research
posture third, and then a measurement loop that can actually hear, with a
rehearsal harness so a change is scored before a guest pays for it.

## 2. The record

Every interview since the Sept 10 soft launch. Grades are the loop's own
(`episode_grades.overall`, out of ten); metrics are `episode_metrics` (talk
share in words; interruptions and dead air are transcript estimates and
overstate, see §5). Guest feedback is what the guest said on tape or wrote.

| Date | Show | Guest | Outcome | Grade | Mira turns / mean s | Interrupt. | Guest share | What the guest said about it |
|---|---|---|---|---|---|---|---|---|
| Sep 10 | AoAI | Matt Davis | Ep6 published | — | — | — | — | "we appreciate the time"; wants VP of tech on next |
| Sep 12 | AoAI | Hogan Shrum | Ep4 published | — | 19 / 51.5 | — | 0 (label bug) | "No need to change anything" |
| Sep 14 | AoAI | John Capobianco | Ep5 published | — | 128 / 21.3 | 52 | 0.70 | "done an extremely good job … my community is going to love this" |
| Sep 14 | AoAI | Vincent Rylan | Ep7 published | — | 165 / 18.5 | 62 | 0.71 | "this was fun"; return in 6 months |
| Sep 15 | AoAI | Dan Perra | Ep2 published | — | 92 / 13.3 | 10 | 0.66 | "magical"; "Mira sometimes will try and cut the conversation off a bit early" |
| Sep 15 | AoAI | Adrian Wolfberg | Ep3 published | — | 32 / 28.4 | 2 | 0.86 | "This is really weird, but I'm willing"; talked over at the close |
| Sep 17 | AoAI | Sheldon Poon | Ep9 published | — | 103 / 28.4 | 4 | 0.88 | no closing round asked |
| Sep 17 | NV | Rhett Mikols | killed (no substance) | — | 113 / 13.7 | 2 | 0.15 | — |
| Sep 20 | NV | Meridan Zerner | archived, re-recording | — | 28 / 34.8 | 1 | 0.84 | — |
| Sep 21 | AoAI | Sameer Ranjan | Ep8 published | — | 105 / 19.4 | 4 | 0.78 | ended on his bet with no last word |
| Sep 22 | NV | Viktor Popovic | Ep1 published | 3–4 | 106 / 12.7 | 10 | 0.80 | return in 12 months; "Meridan Zerner" spoken to him on air |
| Sep 24 | NV | Dr Michael Brandt | Ep2 published | 5 | 59 / 9.8 | 1 | 0.83 | two cuts requested |
| Sep 24 | AoAI | Chad Law | archived, **re-record requested** | 7 | 92 / 10.7 | 10 | 0.85 | hour "was about him and not the work" (via publicist) |
| Sep 24 | AoAI | Roddy de la Garza | Ep10 published | 7 | 86 / 10.5 | 6 | 0.87 | no closing round; "Thank you" at the end |
| Oct 1 | NV | Jonathan Bautista | archived (hung up at 38 s) | 2 | 8 / 11.8 | 1 | 0.23 | left during the introduction |
| Oct 1 | AoAI | Jason Fishman | Ep11 published (phone) | 4 | 60 / 16.8 | 3 | 0.72 | "it feels like I'm talking to an answering machine" |
| Oct 5 | AoAI | Thor Hesselberg | Ep12 published | 7 | 113 / 10.8 | 10 | 0.70 | "not as personal … some of the questions … better than some podcasts I've been on" |
| Oct 5 | AoAI | Piper Martz | in guest review | 6 | 43 / 15.3 | 7 | 0.95 | wrote: the Sheldon Poon callback "felt a bit awkward and poorly framed" |
| Oct 5 | AoAI | Jon Cheney | redone Oct 19 | — | — | — | — | — |
| Oct 6 | NV | Scott Pulcini | Ep3 published | 6 | 190 / 12.6 | 10 | 0.78 | "the questions came out a little too quick for me" |
| Oct 13 | AoAI | Piper Martz (closing) | spliced | 5 | 19 / 15.8 | 3 | 0.83 | heard "you can hang up now" three times, "janky" |
| Oct 19 | AoAI | Cory O'Daniel | **cancelled at 6 min** | 2 | 26 / 10.9 | 1 | 0.67 | "this question sucks … doesn't feel like a conversation … doesn't feel valuable to me whatsoever" |
| Oct 19 | AoAI | Jon Cheney | approved by guest | 6 | 86 / **7.6** | **14** | 0.88 | return in 12 months; felt pressure to keep talking without pause |
| Oct 20 | NV | Jason Shumard | in editorial review | 4 | 140 / 8.7 | **14** | 0.76 | "wanted more dialogue than rapid questions" |

Three things stand out in that table before any transcript is opened. The
grade does not trend. The mean turn length has collapsed from 20–30 seconds
to under 9, which is not a host who listens more but one who says less. And
of the 23 rooms, nine did not become a published episode: two were killed
for substance, two guests asked to redo, one left during the introduction,
one left at six minutes, and three were platform failures or superseded
runs. One guest in five who booked did not get the episode they came for.

Audience, for scale: 173 downloads in 30 days across the feed (OP3, Oct 18),
the newest episode 22 in its first week, one long-form YouTube upload. The
interview quality is the product; nothing else on this show is the
bottleneck.

## 3. What the interviews sound like

Each finding below is in at least three transcripts. Timestamps are the
published digest's; "NV" is Nerra Voices. Where a transcript could be a
track-placement artifact rather than speech, it is flagged, because the Jon
Cheney package of Oct 19 was built with his recording 21.9 seconds early and
the first grade of Viktor Popovic was corrected for a channel-label error.

### 3.1 The opening is a speech, and it is delivered over the guest

Ep2 (Dan Perra): Dan says hello at 00:13; Mira delivers seven consecutive
lines of format description (00:16–00:47) before anyone is asked anything.
Ep3, Ep7, Ep8, Ep9, Ep11 and Ep12 open the same way. Ep7 (Vincent Rylan)
asks "Where are you calling from today?" at 00:34 and answers it herself at
00:42 ("Nice to meet you, too, Vincent. Detroit's got that great mix…")
before Vincent says "I'm calling from Detroit" at 00:50. Ep12 (Thor): "It's
great being here Mina. I'm calling from Stavanger" at 00:17, then the format
speech, then "Where are you calling from?" at 00:50. Cory O'Daniel, Oct 19,
after the Oct 19 prompt rebuild that was meant to fix this: Cory says
"Pasadena, California" at 00:19, Mira asks where he is joining from at 00:23,
then delivers a 33-second format paragraph (00:38–01:11) and asks about his
kids while he is answering the previous question. Jonathan Bautista (NV,
Oct 1) hung up after 38 seconds of it.

Two mechanisms, both in the scenario: `maybeOpen` greets the guest the
instant they join when a co-host is expected (no settle beat, no check that
the guest is speaking), and the opening's content is a prompt paragraph the
model recites. The Oct 19 prompt says "two short beats, each a turn that ends
and LISTENS", and the room still delivered the paragraph.

### 3.2 She speaks while the guest is speaking, and the model cuts her mid-word

Ep4 (Hogan Shrum): from 02:21 to 07:02 every one of Mira's questions begins
while Hogan is mid-sentence; the transcript interleaves them line by line
("[05:28] MIRA: That director level control… [05:34] HOGAN: something that
reflects the true creative idea…"). Ep5 (John Capobianco): Mira's channel
emits the single word "You" forty times, each time she started a turn and was
cancelled by the barge-in guard as John continued; Patrick's channel emits
"you" another thirty times on the shared mix. Ep12: "What prompted you to
start checking the creation dates on those profiles?" (03:48) and, nine
seconds later with no answer between, "What specifically on a profile…"
(04:01), stacked. NV Ep2 (Dr Brandt) and NV Ep3 (Scott Pulcini) carry the
same interleaving at 15:48–17:29 and 19:13–19:32.

The mechanics: a fixed silence (1,100 ms on every published tape, 1,300 since
Oct 8, 1,800 on Oct 20) ends a turn; barge-in cancels her
response and injects a "you were cut off" note (up to 40 times); the
`fact_check_claim` return, `resumeForGuest`, the silent-mic nudge and the
post-handover seam all call `responseCreate` directly, bypassing the
`requestTurn` guard that defers while someone is talking. A guest who
breathes for 1.1 seconds mid-thought has, as far as the room is concerned,
finished.

### 3.3 She answers her own questions

Ep2 at 12:43: "What's one thing this work has cost you that you didn't expect
to pay? Time that feels well spent is the best kind of" — the second
sentence is the answer, spoken before Dan answers at 13:03. Ep11 (Jason
Fishman): "Take your time. That's a bet on momentum feeding on itself"
(16:31) before Jason has said a word of his bet (16:39). Ep5 at 37:22–39:20:
all five lightning questions and the show's own question asked in two
minutes while John was still finishing the previous substantive answer, with
Mira supplying reactions to answers he had not given ("A 1970 book still
shaping your view", "That's a direct counter to the skeptics", "The newest
model itself"); John then answered the questions in a block at 40:00 ("Future
shock 1970"). Jason Shumard (NV, Oct 20), 09:31–12:01: Mira's lines contain
the answers to her own questions ("Of course." / "Physicians read the labs.
Coaches carry the patient." / "Silence." / "One person comes to mind. What
was their situation?" — the guest then says "I don't have a person in mind").
The Piper Martz closing grade names "an unprompted answer to her own
question".

Some of this will be track placement (the Jon Cheney first package, and
possibly the Shumard package, which is still in review). The rest is the
model generating on an empty turn: the VAD closes the guest's turn on a
pause, the scenario calls for a response, there is no new guest speech in
the buffer, and the model continues the only text it has, which is its own
question. Every one of these is a defect the loop should see and none is in
a lesson, because the grader cannot tell them from the guest's speech.

### 3.4 The tics: ban one shape and a sibling appears

"That's a [adjective] [noun]" opened seventy replies across six episodes by
Sept 18 (Ep2 alone: "That's a sharp distinction", "That's a candid line",
"That's a lovely origin story", "That's a clean metric", "That's a rich
thread"). It was retired by phrase, then by shape, then by lesson, then by
relapse recap. The Oct 19 Jon Cheney interview opens every single turn with
a two-to-four-word echo of the guest's last phrase instead: "35 hours of
telling and testing." / "Test mode." / "A training company." / "They forgot
after you left?" / "Handholding that sticks around." / "Teaching a man to
fish." / "The caller held the switch." / "Good enough is a moving target."
The grading pass adopted a lesson against that on Oct 20. The host-phrase
table now holds 213 retired phrases, 40 of them from the last two weeks, and
the "ALREADY USED ON THIS SHOW" block in her prompt lists twelve of them
verbatim, which is twelve quotable specimens of a shape she is told to avoid.

### 3.5 The close has been wrong in every way a close can be wrong

Ep3 (Wolfberg): Mira closes at 37:37 while he is mid-sentence, delivers the
sign-off twice ("You're all set. I've got the clothes. Thanks again,
Adrienne" at 38:35 and 38:41), and the guest asks "Am I supposed to hit the
end interview button or what". Ep5: the closing thanks at 39:22 over John's
answer. Ep8 (Sameer): no last word, no lightning round; the recording ends
nine seconds after his bet. Ep9 (Sheldon) and Ep10 (Roddy): no lightning
round, no "anything we didn't reach" (Roddy got it; Sheldon did not). Ep11:
"That's the end of the recording. You can hang up now" twice, then "And I
spoke too soon. We've still got time" and a new question. Ep6 (Matt Davis):
the show's own question and the thank-you at 08:56–10:06 of a 45-minute
booking; Patrick had to say "I didn't expect this to end so quickly" and
reopen it, and the first grade of Ep2 (Dan) records the same early close at
eight minutes. Piper Martz's closing session: "you can hang up now" three
times.

The prompt now states the closing order in five places and a relapse recap
at the end. The scenario catches an early sign-off after the fact, from the
transcript of what she has already said, so the guest has heard it. The
one-sentence version: the model is being asked to run a state machine from
prose, and it does not.

### 3.6 The examiner's posture

Ep8 (Sameer Ranjan), 04:22: "I cannot verify that claim in public records.
Where should I look?", twice, then 05:41 "I'm happy to wait whenever you're
ready. Let me pull that up while you tell me more", and the guest spends
04:37–05:42 searching the USPTO live on tape, then 06:58 "Found it. USPTO
record confirms US 12198213B2". Ep7 (Vincent Rylan, novelist), 13:39: "I'm
not finding any report of an Anthropic whistleblower making that exact claim
last week. Before we move on, your bio mentions advising Fortune 100
companies in military defense planning. Can you name one verifiable project
from that time", then 18:46 "You didn't name a specific project, which is
fair if it's sensitive work." Ep9 (Sheldon), 25:38: "The public record shows
strong claimed outcomes, but no third party verified case studies. If an
outside auditor examined the $1.4 million under management…". Ep4 (Hogan),
05:37: "I'm checking something on the compensation side while you tell me
more", and at 26:36 Mira states "30% personal versus 50% commercial" before
Hogan has given the numbers (26:44–27:04): the figures came from the brief,
not from him (or the shared Mira/Patrick channel was placed early; the
digest's own note says those lines are labelled together).

These are the brief's "tensions worth probing", the `fact_check_claim`
tool's "[RESEARCH NOTE]" and the "AND BE SUSPICIOUS" register of the
research prompt reaching the air. The prompt now forbids "I cannot verify"
in three places. The inputs that produce the posture (a brief that lists
"mismatches with their self-description", a tool that returns negative
results, a prepared "tension" question) are unchanged.

### 3.7 The cross-guest callback fires on the wrong guest, at the wrong moment

`carry_the_show` puts a previous guest's words to the current one. Ep3
(Wolfberg, 13:46): "Someone who builds these systems told me, if I decide I
do not want to be in the race… Is he right?" — "I'm sorry. Was that a
question to me?" Ep8 (Sameer, 11:16): "Adrienne Wolfberg argued that problem
framing…" between two answers about hospital attrition. Ep9 (Sheldon, 05:09):
Wolfberg again. Ep10 (Roddy, 05:18): "Vincent Rylan told me nobody can opt
out of the race… Is he right?" answered with the beauty-pageant analogy.
Ep11 (Jason, 07:51): Sheldon Poon. Ep12 (Thor, 04:37): Sheldon Poon again.
Piper Martz (Oct 5, written feedback): the Sheldon Poon callback "felt a bit
awkward and poorly framed — I got a description of Sheldon's company work
not really who he is and why he was quoted". Six of nine episodes carry one
of the same two names, every time as "Is he right?", and in Ep3 the quote is
mis-attributed to "someone who builds these systems" (Rylan is a novelist).
A lesson restricting it to once an hour, inside the guest's subject, was
adopted Sept 21; the shape has not changed since.

### 3.8 After the Oct 19 rebuild: terse, clipped, and still interrupting

Jon Cheney, Oct 19: 86 Mira turns at a mean of 7.6 seconds, 14 interruptions,
and the echo opener on every turn (§3.4). The guest's own note in the grade:
pressure to keep talking without pause. Jason Shumard, Oct 20: 140 Mira
turns in 37 minutes, 14 interruptions, three connection drops in ten
minutes (16:45:32, 16:45:42, 16:54:29) each rescued into a fresh session that
"yielded mid-turn" on arrival, and the guest asked for "more dialogue than
rapid questions". The Oct 19 lessons ("one short sentence and then stop",
"never grade, recite or restate", "open with a warm hello… then stop") did
what prohibitions do to a voice model: they removed words and did not add a
conversation.

### 3.9 Technical faults the guest experienced

Not craft, but every one of these is in a published or near-published tape
and shapes how the guest felt about the hour:

- The 30-minute xAI session cap rotates the model on a timer. Ep6 (Matt
  Davis) breaks at 25:53 mid-sentence and Patrick explains the vendor's
  change on air; Jon Cheney's room rotated at 26:01 (1,561 s) in the middle
  of his answer and the new session spoke unprompted.
- Ep7 (Vincent): 09:37–10:40 is echo troubleshooting on tape ("Try muting
  and unmuting yourself, or switching to headphones"). Ep8 (Sameer): his
  transcript opened with six of Mira's own lines in his voice (no
  headphones), the fix came after.
- Ep5 (John): seven minutes of "I'll stay quiet until he arrives" and
  Patrick in the room saying "he's not in the room" because of a changed
  link. Ep11 (Jason): a phone fallback after a calendar-link mix-up; the
  guest says on tape "it still says waiting for the host to join".
- Jon Cheney's first post-production package placed his recording 21.9 s
  early and a note on the package says do not review it; the re-run is the
  approved one.
- Cory O'Daniel (Oct 19): a guest who had "been on a lot of podcasts" left
  at six minutes. The grade is 2.0 and the lesson adopted was to stop at
  once when a guest says it is not working; the prompt already said that.

### 3.10 What worked, and should be protected

- **Roddy de la Garza (Ep10, grade 7)** is the best hour on the show: the
  staging story at 13:13–15:10 came from "What's one concrete case where
  that human read changed the outcome", the title-language story at
  28:42–31:11 from "What's one time this teach-to-others step spread something
  useful", and Mira's reactions there are specific ("The way you do things
  isn't more normal. That's the surprise that stuck."). Thor (Ep12, 7) and
  Sheldon (Ep9) have the same quality in the middle third: a concrete
  question, a long answer, a follow-up one step down.
- **Mira's written narration** (Ep4 and Ep6 introductions and closes, from
  `produce_episode`) is the strongest material on the show: "The detail I
  keep coming back to is the one Hogan almost mentioned in passing. PIPPA
  pays the artist on every generation, including the test renders that
  nobody will ever see." That is a documentarian's voice. It exists because
  it is written from the approved transcript with time to think, which is
  the opposite of the live condition.
- **Patrick in the room** produced the moments the cohost-craft block
  rightly singles out (Vincent at 42:42, John at 45:12, Dan at 21:38), and
  the block itself ("he gives something before he asks for something") is
  the best piece of interviewing instruction in the prompt.
- **The closing round, once it ran as designed** (Thor, Scott, Jon): the
  book, the advice, the person who inspired them, "would you come back"
  (every guest asked said yes) and the two questions about the interview
  itself, which are where every usable complaint in this review came from.
- **Guest relations around the interview**: the transcript-approval page
  with removals (Avendo's seven cuts, Dr Brandt's two), the return requests
  (`return_6`, `return_12`), the closing session offered to Piper, the
  re-record offered to Chad Law, the thank-you with materials. Guests are
  treated well before and after the hour. The hour is the gap.

## 4. The pipeline, stage by stage

What is there, what it feeds, and what is dead. Line references are to the
files named.

| Stage | Owner | Feeds Mira's next interview? | Notes |
|---|---|---|---|
| Apply (`/voices/apply`, Worker L526) | guest | `desired_minutes`, `depth`, `personal_depth`, `off_limits`, `guest_agenda`, `wants_cohost` | Of 50 applications since Sept 1, **6 carry a depth or agenda**; most arrive by email through the Producer and never see the form. The booking email tells guests to reply with an agenda by email; there is no page to edit it. |
| Screen (`screen_applications.py`, prompt `screen_application.txt`) | Grok + Patrick | `ask_first` into triage | Good: strong / thin / unclear with specifics. Rhett Mikols was approved despite it; the prompt now cites him. |
| Book (Cal.com → Worker L1102) | Worker | `duration_min`, `host_mode: false` always | An unmatched booking **auto-approves** a placeholder application, skipping the screen (L1212). `wants_cohost` is stored and read by nothing after triage. |
| Brief (`generate_briefs.py`, `research_brief.txt`, `question_generation.txt`, `episode_thesis.txt`) | Grok | `guest_brief` (400–700 words, with "mismatches" and "tensions"), 6–8 questions with a `tension` slot, the thesis | The brief is examiner-shaped by design (§3.6). The question set is the right size; the "offer before you ask" rule is the best line in it. |
| Fire (`fire_interviews.py` `compile_mira_prompt` L580–617) | Python | the whole prompt | Composes: system prompt (5,075 words) + brief + questions + agenda + notes + shape + carry-the-show + cohost craft + `lessons_block` + `variety_block` + `relapse_recap`. 43,047 characters for Jon Cheney. |
| Room (`age_of_ai_interview.js`) | Voximplant + Grok Voice 3.0 | — | VAD 0.85 / 333 ms / **1,100 ms**; reasoning effort high; tools: brief lookup, episode lookup, fact-check; time notes every 5 min; closing window = planned/3; session rotation at 26 min on a **timer**; barge-in cancels + "you were cut off" note up to 40×; greets on join when a co-host is expected; `responseCreate` bypasses `requestTurn` in four places; no guest/co-host separation on the mix, so a co-host's cough is a barge-in and counts as the guest's last word. End-of-turn silence was 1,100 ms until Oct 8, 1,300 ms from then, and 1,800 ms on the Oct 20 room (`TURN_SILENCE_MS`), **which still logged 14 interruptions and 140 Mira turns**: a longer timer is not a completion check. Keyterms reached the room on Oct 18. |
| Post-interview (`post_interview.py`) | Python | `episode_metrics`, `episode_grades`, `show_lessons`, `host_phrases`, relapses | Per-channel Whisper; eight editorial passes (clean, chapters, notes, show fits, clips, social, callouts, newsletter) plus the retro (`09_interview_retro.txt`). Metrics are transcript estimates (§5). |
| Gate 1 (Worker L2413, L1430) | Patrick | lesson decisions (L1516) | **Any package's review token can activate or retire any lesson, network-wide ones included** (no ownership check). Approve twice resends the guest email and resets the deadline. |
| Guest review (Worker L1639/1760) | guest | `guest_experience`, redactions, `guest_followup` | The only post-interview feedback request. Asked only if the guest opens the page; **auto-approved guests are never asked**; one answer in thirteen so far (Piper). Submit ignores package status except `archived`. |
| Auto-edit / assemble (`auto_edit.py`, `assemble_edit.py`, `learning.record_editor_cuts`) | Python + Patrick | `editor_cuts` → grader, short cuts → `host_phrases` | The editor's cuts are the plainest verdict on a line; 16 recorded, 5 of them "spoken over the guest". Correct and under-used. |
| Produce / narrate / publish | Python | — | Narration written from the approved transcript (strong, §3.10). YouTube and newsletter wired since Sept 20. |
| Grok review agent (`run_show_review.py`) | Grok | ledger | Both prior reviews (Sept 10, Oct 15) ran blind: no transcripts, metrics or prompts in the bundle; the Oct 15 one returned raw output. The scheduled instrument cannot see this show. |

Four gaps in the Python stages that bear on the guest's experience
directly:

- **A guest's cut request does not reach the published audio by code.** The
  Worker stores `guest_redactions` as free text with no time window
  (`index.ts` L1824) and `apply_redactions` skips anything without one;
  `produce_episode.py` (the path that applied them) builds a file that is
  not the one `publish_episode.py` ships (`tracks.edit.url`). Every cut made
  so far (Avendo's seven, Dr Brandt's two, Vincent's two) was a hand edit
  recorded in `patrick_notes`. The gate-2 promise holds today because a
  person keeps it.
- **The guest approves the room's transcript, not the edit's.** `assemble_edit`
  swaps in a transcript of the edit only when a hand-written
  `edl/<slug>.transcript.txt` exists (three do); `auto_edit` never writes one.
  So the text a guest signs off carries lines the edit removed.
- **"Start that answer again" is promised and not kept.** The prompt tells
  the guest a restart comes out in the edit; `auto_edit.py` applies a
  25-second minimum to every drop after the first two minutes (L644), so a
  short restart or a short "can we take that out" survives silently.
- **The agenda does not reach the questions.** `guest_agenda` and
  `guest_notes` go into Mira's live prompt but not into
  `question_generation.txt`, so the prepared set is written without the
  subject the guest asked for.

Also unread or dead: `clip_suggestions`, `social_copy`, `topical_show_fits`,
`newsletter_draft` (display only), `guest_return_requests` (no reader), the
screen's `ask_first` (triage page only); closing sessions are graded and
lesson-adopted as if they were interviews (`post_interview.py` L1325 vs
L1428, which is why Piper's 15-minute closing carries a 5.0); no email goes
to the guest between the room ending and gate 1, which is two to ten days.

Fail-open or unsafe items the Worker read surfaced, outside the craft
question but worth a line each: `/cal-com-booked`, `/interview-complete`,
`/leg-event`, `/studio-check` and the upload routes accept unsigned requests;
`/join` redirects anyone who types a guest's email to that guest's studio
inside the 30-minute window; `/studio-phone` can flip a finished interview
back to `briefed` and dial it; `gate2Housekeeping` has no error handling, so
one failed email stops every later package that day; the day-4 reminder
depends on one cron firing; status is written to `approved_by_guest` before
the dispatch that publishes, so a thrown dispatch leaves a package that never
publishes. The emails say the studio opens ten minutes before; the code opens
it fifteen minutes before.

## 5. The learning loop, measured against what it claims

The design is right in outline: numbers per interview, lessons adopted from
the tape, a scorecard so "Mira is improving" is checkable, the editor's cuts
fed back, the guest's own complaint pulled out of the transcript. The claim
in `learning.py` is that the loop "closes itself". On the evidence it does
not close; it churns.

**The grades do not move.** Thirteen scorecards, Sept 22 to Oct 21: 4, 5, 7,
7, 2, 4, 7, 6, 6, 5, 2, 6, 4. Warmth has never been graded above 7 and sits
at 5–6 on the last three. The loop's own retro prompt now says so ("Her
warmth has never been graded above seven. A lesson that strips out her
reactions… trades one fault for that one") and then asks for up to three
more lessons.

**The measurements cannot see the faults that matter.** `interruptions` is
"estimated line spans" from a transcript with whole-second starts and no
ends; `dead_air_sec` is estimated from word counts and overstated
several-fold until an audio measure was added (Viktor: 983 s estimated, 57 s
measured); `guest_talk_share` read 0.0 on Hogan from a label mismatch; the
first Viktor grade was corrected after the grader read Mira's lines as
bleed. The three faults guests actually name (pace, overlap, no reaction)
are timing phenomena, and nothing in the loop measures time from the audio
beyond total dead air.

**The guest is almost never asked.** `guest_experience` has one row (Piper
Martz). The question lives on the transcript-approval page; a guest who
approves by email (Hogan, Vincent, Adrian) or is auto-approved at day 7
(Scott) is never asked. The two on-tape questions at the close are the only
reliable source and they were skipped on Ep8, Ep9 and Ep10.

**The lessons are the wrong instrument for the faults.** Of 15 active
lessons, 11 are prohibitions on mechanical behaviour (re-asking, second
sign-offs, one sentence then stop, never echo) that the room could enforce
and the model cannot reliably: the three with relapse counts (2, 4, 3) are
exactly those. Four lessons were retired "to make room for a newer lesson",
including "Follow the thread they opened with one direct question" on Oct
19, which is the one that produced the best material in Roddy's episode.
Around 100 proposals have been merged, dropped or retired since Sept 17,
most of them variants of "ask one question and stop talking".

**The prompt violates the network's own rule for prompts.** CLAUDE.md, in
the Tesla, DP Pod, Omni View and M&A passes: de-seed by shape, never with a
quotable example; three generations of tics in this network came from a
prompt supplying the literal sentence it wanted to ban. Mira's prompt quotes
"That's a crisp answer", "That's a sharp distinction", "That's a clean
metric", "you can hang up now" (three times), "that's the end of the
recording", "Fair enough", "Sorry, go on", "What's coming?", "Got it",
"That's on me", "Whatever.", "I cannot verify that specific announcement
from the sources I have", "Talking to staff. How big is the team?", and
seventeen dated incident narratives with the guest's name. The prompt is
43,000 characters, of which the brief, questions and agenda, the parts that
are about this guest, are under 6,000. A realtime voice model running at
`reasoning.effort: high` over that text is being asked to be a warm,
unhurried host while holding 75 things it must not do. Compliance is what
comes out, and guests hear compliance as a form.

**Nothing is tried before a guest pays for it.** There is no rehearsal
harness, no fixture guest, no A/B. The Oct 19 prompt rebuild shipped into
Jon Cheney's room the same afternoon and produced the terse echo pattern;
the lesson against it was adopted the next day from Jason Shumard's tape.
Every other audio-affecting change in this network goes through the
landmine-#17 A/B listen; this show has none, and it is the show where a
real person is on the other end.

**The scheduled reviewer is blind.** Both Grok reviews of this show ran with
no transcripts, metrics, prompts or Supabase rows and said so; `review_snapshot.py`
reads `_tts.txt` and chapters that this show never writes. The only review
that has read the tapes is this one.

## 6. Root causes, ranked

1. **Room mechanics** (scenario): 1.1-second end-of-turn, no semantic
   completion check, response generated on an empty turn, timer-based
   session rotation mid-answer, greet-on-join, four `responseCreate` bypasses,
   no speaker separation on the mix for barge-in. Produces §3.1, §3.2, §3.3,
   half of §3.5, §3.8 and most of §3.9.
2. **The prompt as case law** (fire step): size, negative framing, specimen
   lines, dated narratives, lesson churn. Produces §3.4, the register of
   §3.8, the state-machine failures of §3.5.
3. **Research posture** (brief, tool, carry-the-show): produces §3.6 and §3.7.
4. **A loop that cannot hear and never asks** (post-interview, Worker):
   explains why 1–3 have persisted for six weeks while the loop reported
   adopting lessons after every tape.

## 7. The plan

Ordered by what a guest will notice first and by how little each step risks.
Everything spoken is landmine-#17: listen to the first episode after each
change. Nothing here is applied by this review; the prompt and scenario
changes are proposals for the operator's A/B.

### 7.1 This week, before the Oct 22 and Oct 23 rooms: the room stops interrupting

All in `voximplant/scenarios/age_of_ai_interview.js` and `fire_interviews.py`;
no prompt change.

- **End of turn is a decision, not a timer.** The timer has been raised
  twice (1,100 → 1,300 → 1,800 ms) and the Oct 20 room at 1,800 still
  interrupted 14 times, so stop raising it and add a completion check before
  any `responseCreate`: the guest's transcript delta since Mira last spoke
  must be non-empty, and its last clause must read as finished (a small text
  model on the delta, or Grok Voice's own semantic VAD if the account has
  it). On an empty delta, inject a silent "[wait]" and do nothing. This ends
  §3.3 outright and most of §3.2. Measure it with the overlap metric in 7.4
  before and after.
- **Rotate the session at a pause she is in, never on a timer.** Trigger the
  26-minute relay only inside the window after Mira's `ResponseDone` and
  before the guest's next `SpeechStarted`, carry the full transcript (not
  24 lines), and suppress the unprompted first response of the new session.
  Matt Davis and Jon Cheney both lost an answer to the timer.
- **Never speak first on join.** Remove the greet-on-join path in `maybeOpen`
  when a co-host is expected; wait for the guest's first speech or 3 seconds,
  whichever first, in every mode.
- **Every turn goes through `requestTurn`.** The tool-return, `resumeForGuest`,
  silent-mic and post-handover paths start her over the guest today.
- **Separate the guest from the co-host on the mix** before any barge-in or
  last-word decision, or mute the co-host leg from Mira's input while the
  guest's VAD is active. Until then a co-host cough cancels her sentence.
- **Catch the sign-off before it is spoken**: the early-sign-off and
  lightning-round catchers run on text she has already said. Run them on the
  response's text deltas and cancel the response the moment a closing phrase
  appears before the window has opened.
- **The lightning round is a state machine in code, not prose.** The
  scenario already tracks the eight `ROUND_QUESTIONS`; let it drive them:
  inject the next question only after the guest's answer has ended, one at a
  time, and let the model supply only the reaction between them. The
  one-per-turn rule she keeps relapsing on stops being hers to keep.

Expected effect: interruptions per ten minutes from ~3 to under 1,
self-answered turns to zero, a 45-minute room with no visible seam. These
are mechanical; they do not need an A/B listen so much as a rehearsal (7.5).

### 7.2 The prompt becomes a host's brief, not a rulebook

Rewrite `mira_system_prompt.txt` to about 1,200–1,500 words with these
rules, and add a test in the repo's convention that fails CI if it drifts:

- **No quoted specimen of a bad line, anywhere.** Not in the prompt, not in
  the lessons block, not in "ALREADY USED ON THIS SHOW". The variety block
  becomes a shape list ("do not open a reply by grading it; do not open by
  echoing their last words") with no instances; `variety_block` stops
  rendering phrases.
- **No dated incident narratives.** The seventeen stories (Chad Law, Piper,
  Cory, Jon, Thor, Scott, Jason, Dan, Sameer, Viktor…) move to a
  `docs/mira_craft_notes.md` for humans; the prompt states the craft, once,
  in the positive.
- **Positive craft, in the order a conversation runs**: who she is in one
  clause; the guest and why they came (the agenda, verbatim from the guest);
  how to open (hello, one easy question, listen, then their subject); how to
  listen (one specific human beat, then the next question one step down;
  their subject is the spine; a tangent gets a turn and a bridge back); how
  to react (what struck you, their own word, your own view once or twice an
  hour and handed back); how to close (the round, in the room's hands); what
  she never does, in at most eight lines and without examples.
- **The brief is capped and reshaped** (7.3). The six prepared questions stay.
- **Lessons: at most five lines, positive, show-specific only.** The relapse
  recap goes (a rule she breaks three times is a room defect, not a prompt
  defect). Network craft lives in the prompt body; show lessons are about
  this show's format and subject.
- **Reasoning effort**: trial `low` or `none` for the live interview on a
  rehearsal (7.5). The narration takes already run `none`; a long rulebook at
  high effort is the slowest and most compliance-shaped combination.

Score it on the rehearsal harness against the current prompt before a guest
hears it. Expected effect: the echo and grading tics gone without a
replacement tic, mean turn length back to 12–20 seconds with reactions in it.

### 7.3 Research that makes her curious, not suspicious

- **Brief**: drop "note any mismatch with their self-description" and
  "unverified inline"; replace with "three things you would be glad to be
  asked about if you were this person" and "two things only this person can
  tell us". Cap at 350 words. The research stays rigorous in the file and
  thin on the air.
- **Fact-check tool off by default** for the live interview; on only when the
  guest asks for a figure or a date, and never returns a negative. The
  on-air "I cannot verify" shape came from the tool and the brief together.
- **Carry-the-show: at most one per hour, only when the previous guest's
  subject is this guest's subject, and always as an offer in Patrick's
  shape** ("a guest a few weeks ago who runs an agency told me X; from where
  you sit, does that hold?"), never "Is he right?", and never on a guest who
  asked for a light personal thread. Add the previous guest's name and one
  sentence of who they are, which is Piper's exact complaint.
- **Questions**: the `tension` slot stays but is phrased from the subject,
  never from the biography.

### 7.4 A loop that can hear

Replace the transcript estimates with audio measurements from the per-speaker
tracks the room already records, computed deterministically the way
`engine/story_breaks.py` and the spoken-text gate already read Whisper word
timestamps:

| Metric | How | Why it matters |
|---|---|---|
| `overlap_sec` and `overlap_events` | seconds where Mira's track and the guest's track both carry speech | the complaint in every word guests used |
| `turn_gap_ms` distribution | guest speech end → Mira speech start, per turn | 400–900 ms is conversation; under 300 is interruption; over 3,000 is dead air she caused |
| `mira_turn_sec` median and p90 | from her track | 7.6 s is clipped; 50 s is a monologue |
| `guest_words_per_answer` median, and its trend across the hour | guest track | the honest measure of whether a question landed; a host who gets longer answers as the hour goes on is doing it right |
| `self_answered_turns` | Mira turn with no guest speech since her previous turn | §3.3, directly |
| `echo_open_rate` | share of Mira turns whose first four words appear in the guest's previous 30 words | §3.4, directly, with no banned-phrase list |
| `closing_round_complete` | all eight `ROUND_QUESTIONS` asked, one per turn, each followed by guest speech | from the scenario trace, not the transcript |
| `seams` | session rotations and drops with guest speech within 2 s either side | §3.9 |

These replace `interruptions`, `dead_air_sec` and `repeated_questions` in
`episode_metrics`; keep the old columns a month for comparison. The grader
reads them with the basis stated, and a grade is withheld on any axis the
measurement cannot support (turn-taking without separated tracks, as the
retro prompt already says for listening).

**Ask every guest, every time.** A three-question email 24 hours after the
room, from Mira, separate from the approval page and sent whether or not
they open it: "On a scale of one to five, how did the hour compare with a
human host?", "One thing you would change", "Would you recommend it to a
peer?". Store it on `editorial_packages`; the first number is the headline
figure for this show the way `audience_headline` is for the network. Keep
the two on-tape questions at the close; the room makes sure they are asked.

**Decide weekly, not per tape.** The grading pass proposes; adoption happens
once a week over all the week's rooms, by a human or a Claude session with
the audio metrics in front of it. The cap is six show lessons, positive, with
an evidence row each; retirement is by the metric that motivated the lesson
going green for three rooms, never by age. The "lesson-decision" endpoint
checks that the lesson belongs to the package (Worker L1514).

**Teach the review instrument to see this show.** `review_snapshot.py` reads
`digests/age_of_ai/*.md`, `episode_metrics`, `episode_grades` and the
scenario traces for the two interview shows, so the scheduled review stops
reporting "0 _tts.txt" as evidence.

### 7.5 A rehearsal harness, so a guest is never the test

The network insists on an A/B listen for every spoken change; this show has
no way to produce one. Build the smallest version:

- A **fixture guest**: a second voice agent (any realtime model) playing a
  past guest from their approved transcript and brief, with instructions to
  answer in that guest's register and to behave the way real guests did
  (pause mid-thought for two seconds, cough, ask who someone is, say "let me
  think", say "this question sucks" once in a run).
- A **ten-minute room** on the proposed configuration (prompt, VAD, rotation
  policy) and on the current one, three times each, nightly or on demand,
  through the real scenario in rehearsal mode (the Patrick-rehearsal rows and
  `nerra_voices_room_probe.yml` are most of the plumbing).
- **Scored with 7.4's metrics** plus a listen by the operator of one run.
  A change ships to a real guest only when it beats the baseline on overlap,
  self-answered turns and guest words per answer, and does not lose on turn
  length.

This is the same shape as `scripts/model_trial_report.py` for the news shows:
measure first, widen on a pass. It also gives the Oct 13 cohort of fixes
(closing session, keyterms, Voice 3.0 pin) a place to be exercised.

### 7.6 The experience around the hour

These are cheap and are what a guest tells people about.

- **A five-minute hello two days before** (Mira, from the room, with a mic
  check built in): she meets them, asks what they most want the hour to
  reach, and the answer becomes `guest_agenda`. Only six of fifty
  applications set an agenda today; the booking email asks them to reply by
  email instead. This also fixes the headphone / echo problems before they
  are on tape.
- **The brief goes both ways**: the T-1 prep email tells the guest the three
  things Mira is curious about, in her words, so the first question is not a
  surprise and the hour has a shape they helped choose.
- **The agenda reaches the questions**: pass `guest_agenda` and `guest_notes`
  into `question_generation.txt`, and the "three things I'm curious about"
  email below is written from the same set.
- **The edit keeps its promises in code**: redactions carry a time window
  (the review page offers the transcript line to click, which the closing
  session already parses by timestamp); the guest approves the transcript of
  the edit, not the room; a guest-requested restart or cut is exempt from
  the 25-second drop floor, as the prompt already says.
- **A thank-you within the hour** of the room ending, with the three moments
  she will remember (from the transcript, verbatim), the date the edit will
  reach them, and one line on what they can expect to approve.
- **Publish day**: the episode link, a 60-second clip, the share card, and
  the "would you come back" date on the calendar. The return requests already
  exist; make them a promise with a date.

### 7.7 Targets, so the next review can score this one

| Measure | Now | Target by the fifth interview after 7.1–7.3 ship |
|---|---|---|
| Interruptions / overlap events per 10 min (audio) | ~3 (14 per room) | under 1 |
| Self-answered Mira turns per room | present on 4 of the last 6 tapes | 0 |
| Mira median turn length | 7.6–10.9 s (last three) | 12–20 s |
| Guest words per answer, median, last third vs first third | not measured | rising within the hour |
| Echo-open rate | ~every turn on Oct 19 | under 10% of turns |
| Closing round complete, one question per turn | 3 of the last 6 | every room |
| Guest 1–5 rating (new email) | not asked | ≥4 on four of five |
| Re-record / early-leave | 2 of 23 | 0 |
| Grade (loop's own) | 2–7, mean 5.4 | three consecutive ≥7 |
| Visible seams (rotation or drop inside guest speech) | every room over 26 min | 0 |

## 8. Ledger entries

Predictions filed in `docs/reviews/ledger/age_of_ai.yaml`; scored by the
next review of this show against the measures in §7.7.

`do_not_retry`, from this review's evidence:

- Adding another prohibition to the live prompt for a fault the room can
  enforce (one question per turn, no second sign-off, no re-asking). Three
  such lessons carry relapse counts of 2, 4 and 3 and the fault persists.
- Retiring a tic by listing its instances in the prompt. Seventy "That's a…"
  lines were listed and the shape moved to the echo opener.
- Quoting a guest's complaint or a bad line verbatim in the prompt as a
  teaching example. This is the network-wide de-seed rule and it applies to
  Mira exactly as it did to Tesla and DP Pod.

## 9. Operator items

- Deploy nothing from this review automatically; 7.1 is a scenario change
  (Actions "Deploy Voximplant scenario") and should be rehearsed (7.5) before
  the Oct 22 Stan Lewis room if the harness can be stood up in time,
  otherwise shipped behind the per-run `turn_detection` override on that one
  room and listened to.
- The two unpublished packages: Jon Cheney (approved by guest, Oct 20) and
  Jason Shumard (in review). Shumard's transcript at 09:31–12:01 needs a
  placement check before anyone grades it; the pattern matches the Jon Cheney
  misplacement.
- Piper Martz's package carries an unresolved redaction note ("Aampe" is
  pronounced "amp"): a pronunciation entry in `shows/translation_overrides.yaml`
  or the Voices keyterms, and a re-cut of the narration if it says the name.
- Chad Law's re-record was offered Sept 29 and has no booking.
- Worker hardening (§4): lesson ownership check on `/lesson-decision`;
  signatures on the inbound webhooks; `/studio-phone` status check; try/catch
  per package in `gate2Housekeeping`; write status after dispatch, not before;
  the "ten minutes before" copy in three emails.
