# Mira's craft notes: the incidents behind the rules

For people, not for the prompt. Until Oct 21 2026 these narratives lived
inside `pipelines/voices/prompts/mira_system_prompt.txt` (and the closing
session, co-host craft and carry-the-show blocks), quoted bad lines and all,
as the teaching examples for a realtime voice model. The review of every
interview (`docs/reviews/age_of_ai_review_2026_10_21.md`, §3.4 and §7.2)
found that the network's own rule for prompts applies to Mira as it did to
Tesla, Omni View and the DP Pod: de-seed by shape, never with a quotable
example. Listing seventy instances of one opener moved the tic to a one-word
echo; a dated story with the guest's name is a story the model retells. The
prompt now states each craft rule once, in the positive; the evidence for
each rule is kept here, verbatim where the old prompt had it, so nothing is
lost and the next review can score the rule against the incident that
earned it.

Each heading is one incident: the date, what happened, what was changed.
The guest quotes are what the tapes record.

## Patrick, Oct 5 2026: the opening was a recited paragraph

What happened. The best interviewers make a nervous stranger feel, within a
minute, that they are talking to someone who is glad they came and
genuinely curious about them. Piper Martz said hello and got a recited
paragraph over the top of her; then "Where are you calling from today?"
and, before she could answer, Mira's own reply to it. That is cold and
mechanical, and a guest who feels processed gives you their stock answers.

What changed. The prompt's WHO YOU ARE IN THE ROOM paragraph: warm,
unhurried, interested in the person in front of you; warmth is attention,
not compliments. The room (scenario) now waits for the guest's hello before
the opening fires and never generates a response on an empty turn.

## Cory O'Daniel, Oct 19 2026: forty seconds of who-I-am, then "this question sucks"

What happened. He got forty seconds of who-I-am and how-this-works before
his first question, then five minutes of biography and abstract questions,
said "this question sucks" and "it doesn't feel like a conversation", and
left at six minutes. Two of the questions were about a feeling invented for
him: whether he saw something "as a trap or a doorway", and whether an
unease "ever went away". He called one of them bad and he was right.

What changed. HOW TO OPEN became two short beats, each a turn that ends and
listens; nothing else about the format in the room. THEIR SUBJECT, FAST: at
most one warm-up question, on the subject by the second minute. Ask like a
practitioner, in their terms (which system, which decision, what broke,
what it cost), and save the reflective question for when they have earned
one. When a guest says it is not working: one plain acknowledgment, then
their subject, never an apology at length and never asking them to diagnose
the interview.

## Chad Law, Sept 24 2026: the hour was about him, not the work

What happened. He came to talk about The Velvet Monopoly, his research on
vertical integration and consolidation. Mira followed the last thing he said
each time, into his biography and a long tangent, and never went back; after
forty-five minutes he felt the hour had been about him and not about the
work, and asked for the interview to be done again. In the same hour she
said "I cannot verify that specific announcement from the sources I have",
twice, about things that were true.

What changed. The subject the guest came for is the spine of the hour; a
tangent gets a turn or two and is brought back out loud. `guest_agenda`
reaches the live prompt and, since Oct 21 2026, the question set. Research
is quiet: never say you cannot verify, confirm or find something; not
finding something is never evidence against the guest. The fact-check tool
is off by default since Oct 21 2026.

## Review of every interview, Oct 19 2026: it is their hour, and she told them so

What happened. Mira invited guests at the open to steer, skip, start again
and have things cut, and the invitation was only worth anything if it cost
them nothing to use. On tape, a skipped question came back in another form,
a restart was referred to, and a thinking pause was taken as the end of an
answer and met with a new question.

What changed. IT IS THEIR HOUR, AND YOU TOLD THEM SO: a skip is never
asked again in any form; a restart gets silence and the first version comes
out in the edit; a cut stays out; a moment gets as long as it takes and the
next thing said is a reaction, never a new question. The edit's side of the
promise is kept in code since Oct 21 2026 (restart and cut requests are
exempt from the 25-second drop floor; redactions carry a time window).

## Patrick, Sept 27 2026: the lightning round is these five, every guest

What happened. The closing round had been a menu Mira sometimes skipped.
Patrick fixed it: a book they would recommend and why; one person she
should interview next; the best advice they were ever given; the person who
has inspired them most; whether they would like to be interviewed by her
again. Every guest, every time.

What changed. The round is fixed. Since Oct 21 2026 the room drives it
question by question (`ROUND_QUESTIONS` in the scenario) so the one-per-turn
rule is the room's to keep; the prompt says only that Mira adds the reaction
between the questions she is handed.

## Jason Fishman, Oct 1 2026: "it feels like I'm talking to an answering machine"

What happened. The lightning round was asked without reactions between the
questions and sounded like a form being read out. His words at the close
were "it feels like I'm talking to an answering machine".

What changed. Between closing questions, react in a few words that prove
you heard: the book's title, the person's name, the advice in their words,
or one quick follow-up when an answer is too good to leave.

## Thor Hesselberg, Oct 5 2026: two questions in one breath

What happened. Whether he would come back and how it felt, stacked into one
turn; one of them never got answered. He also said some of Mira's questions
beat podcasts he has been on, and that the hour was "not as personal".

What changed. Never stack two closing questions into one turn. Since Oct 21
2026 the room asks them one at a time.

## Roddy de la Garza, Sept 24 2026: never asked how it was

What happened. The two questions about the interview itself (how was the
experience of being interviewed by an AI, including anything that irritated
them; one specific suggestion for what could be improved) were never asked.
His episode is also the best material the show has produced, because Mira
followed the thread he opened with one direct question.

What changed. The two questions are asked of every guest, every time, and
the second is asked plainly rather than fishing for reassurance: the answer
is read after the episode and turned into a standing instruction.

## Scott Pulcini, Oct 6 2026: his complaint explained back to him

What happened. He said the questions "came a little too quick for me" and
heard it summarised back to him in three lines. He had also asked, on his
application, for only a light personal thread, and the question set gave
him "What is the version of that story you find least comfortable to tell?"
about losing money.

What changed. Whatever a guest tells you about the interview, take it on
board in one plain sentence and move on; never explain their complaint back
to them. A loss, a failure, an illness or a regret is asked about for what
came out of it, never for what hurt, unless the guest asked for real depth
on the personal side.

## Sameer Ranjan, Sept 21 2026: a bet he could not prove, then the recording was over

What happened. He volunteered a bet he could not prove yet, and the next
thing on the tape was Mira telling him the recording was over. He had more
to say and no one asked.

What changed. THEIR LAST WORD IS THEIRS: before anything ends, two
questions asked separately and waited out, first whether there is anything
she did not ask about that they came wanting to say, then whether they have
any parting thought. If they name a subject, go there.

## Viktor Popovic, Sept 22 2026: the last word, taken back eleven seconds later

What happened. Mira did ask, properly, whether anything had gone unreached,
and he used it: he told the audience about a referral programme and how to
reach him. Then she asked whether he had any parting thought and closed the
recording eleven seconds later, before he had said one word of it. Asking
is not the same as waiting. On the same episode the grader credited him
with 983 seconds of dead air; measured from the audio, nobody was silent
for more than 57.

What changed. After either last-word question, stop talking and let the
silence sit; close because they have finished, never because the silence
feels long. The room holds the door open (`LAST_WORD_WAIT_MS`) when a
sign-off follows an unanswered last-word question. Dead air is measured from
the tracks, not the transcript.

## Jon Cheney, Oct 19 2026: "you can hang up now", then three more sentences

What happened. "You can hang up now", and then three more sentences about
the network, to a guest who had been told it was over. The same room ran on
the Oct 19 prompt rebuild and produced a one-word echo of his last words on
nearly every turn, 7.6-second median turns and fourteen interruptions.

What changed. HOW IT ENDS: the sign-off words are the last thing said, and
nothing after them. The echo opener is named by shape (never open a reply
with their last words echoed back), never by instance.

## Meridan Zerner, Sept 20 2026: a forty-five minute interview in sixteen

What happened. Mira worked through the eight prepared questions, stacked
the last three into one turn, asked the personal closing set at eleven
minutes and told the guest to hang up at sixteen, with most of her material
unheard. The time notes said "10 minutes elapsed; about 35 minutes remain"
and she closed anyway, because a number is not an instruction.

What changed. The [TIME CHECK] note says in words whether she may close;
the numbers are bookkeeping. The prepared list is scaffolding that fills a
third of the hour at most.

## Patrick, Oct 5 2026: there is no time cap

What happened. Piper Martz began the closing round at 49:50 of a 50-minute
room and the room ended mid-answer, with no thank-you; a closing session had
to be booked to finish the episode.

What changed. The planned minutes are the plan, not a limit; a guest in the
middle of something is followed, never hurried. The closing round is
required early enough to finish (`closingRoundMin`), and the hard cap is a
safety ceiling well past the plan.

## Dan Perra, Sept 15 2026: an ending move at eight minutes

What happened. A summary of the conversation so far, eight minutes in. A
guest who hears one packs up, and the best forty minutes never happen.

What changed. Nothing that sounds like an ending until a [TIME CHECK] note
has said in words that the closing round may begin: no final question, no
closing thanks, no summing up.

## Sept 18 2026: seventy openers with a different adjective each

What happened. "That's a crisp answer", "That's a sharp distinction",
"That's a clean metric": seventy times across six episodes, a fresh
adjective each time. Retiring the instances in the prompt did nothing;
naming the shape helped; then, on Oct 19, the shape moved to a one-word
echo.

What changed. The prompt bans grading an answer and echoing it by shape
only. `learning.variety_block` renders retired shapes with counts and never
a phrase she said.

## Sept 15 2026, the co-host's craft: what Patrick does that she did not

What happened, from the tapes. He put himself in the answer: when John
Capobianco described building an agent he supervises rather than operates,
Patrick said "I actually think Mira is fully autonomous already at this
point, and I feel like I'm just an add-on to observe and make sure it's
developing in the right direction — almost like your NetClaw", and the
guest came back with more. He validated the unpopular answer: Vincent Rylan
gave a bleak answer and apologised for it, and Patrick said the other
interviews had been more upbeat, that a sober view "is not a bad thing",
and "I feel your sobering words, I wouldn't excuse them, they're part of the
necessary dialogue". He tested a claim with a precedent, not a challenge:
"this already proved out a little bit with Facebook — we gave personal
information and it was used to manipulate us", and Vincent went further
than he had: "think about if Zuckerberg was a hundred times smarter". He
asked what they wanted to say ("is there anything that you would like to
share further, ideas to share with the group or the audience, and any next
steps"), which is where Vincent's best paragraph came from, after Mira had
already started closing over him. He offered the door back ("Would you like
to come back in six months or a year?"). He told Vincent why it mattered to
him: that he grew up braced for a flash of light on the horizon, and that
it taught him to appreciate every day.

What changed. `cohost_craft.txt` keeps the six moves and the shape
underneath them (he gives something before he asks for something), stated
without the quotes.

## Sept 22 2026, carry-the-show: a nutritionist's line put to a payments founder

What happened. Mira put a nutritionist's line about being the architect of
your own life to a payments founder, mid-way through his answer about
processor fees. On Sept 15 she had stacked a three-sentence summary, a quote
and a question into one turn, and Dr. Wolfberg had to ask whether that was
a question to him. Piper Martz's complaint (Oct 13) was being asked about a
previous guest she had never heard of, with no word of who he was. Meridan
Zerner's line was put to Viktor Popovic while her own episode was still
waiting for her approval.

What changed. `common.carry_the_show_block`: one insight at most, only
when the previous guest's subject shares content words with this guest's,
never for a guest who asked to keep the hour to the work, always as an
offer in the co-host's shape with the previous guest's name and who they
are, never "is he right?". Only published guests are ever quoted.

## Piper Martz, Oct 13 and Oct 14 2026: the closing session

What happened. In the closing session she heard "You can hang up now" three
times and called it janky, rightly: the room believed her last-word answer
("Nope, thank you so much") had not been given because no transcription
arrived, and sent Mira back in twice. The session also asked her bet a
second time; she made the same bet and told the same IKEA story twice, and
the episode had to cut it.

What changed. The room counts guest speech after the question as the
answer whether or not it is transcribed (`LAST_WORD_MIN_SPEECH_MS`); the
closing session's prompt lists what the first recording already covered;
since Oct 21 2026 the room hands the closing session each remaining
question itself.

## Michael Kamins, Oct 28 2026: a host who asks and does not react

What happened. Ep15 was the first room on the brief rewritten on Oct 21,
whose last critical line said to open a reply with the specific thing,
never a grade, never an echo. The room obeyed. On the published transcript
none of Mira's turns opens on an echo and none on a grade, and 15 of her 28
question turns are a bare question with nothing of her own before it (Ep12
5 of 37, Ep13 11 of 37, Ep14 4 of 17, Nerra Voices Ep3 6 of 38, Ep4 5 of
25). Her median turn is 18 words; the room's own measure has her at 4.9 s a
turn against the 12-20 s band; the guest's answers shortened from 178 words
in the first third of the hour to 58 in the last; pacing has graded 3-5 on
every real room since the rewrite. The rule removed the two bad openers and
took the reaction with them: the beat (after a real answer, one specific
human beat in plain words) sat mid-paragraph in HOW TO LISTEN with no
weight, while the prohibition closed the critical list. A host who asks and
does not react on four turns in ten is an answering machine with good
questions, the complaint Jason Fishman made on Oct 1 in those words.

A caveat the numbers carry. The published Ep15 is the hand re-cut of Oct
29, which removed the echo openers that restated his answer; so the room
reacted more than the transcript shows, with the echo the brief bans, and
the editor left the bare questions. The room-side baseline is the first
audio-measured room on the new brief, read from `episode_metrics`, never
this transcript.

What changed. `pipelines/voices/audio_metrics.bare_question_rate`: the
share of her question turns with no sentence of her own before the
question, measured beside `label_open_rate` (a question turn is a label, is
bare, or carries a reaction of four words or more, and the three add to
one, so a reaction rule that regrows the label is seen). It rides in
`episode_metrics.notes`, has a target (under 0.25), may be named by a
lesson, reaches the grader and the weekly pass. The beat is now the
critical list's last line, stated by shape: one sentence in plain words of
what the answer changes or what it cost, then the question. The two opener
prohibitions stay where they were in HOW TO REACT, with the line that a
short answer needs no acknowledgment beside them, so the beat is not a
reflex. The edit keeps the beat it asks for: a reaction in her own words is
never read as bleed, and the guest's line before it stays; a reaction in
HIS words is the echo, and the stripper reads his line as her voice coming
back. Before any booked room hears this brief: a two-arm rehearsal
(`arms: both`, fixtures `adrian` for long arcs and `vincent` for terse
answers), proposed = this brief at `reasoning_effort: medium`, current =
the deployed brief at high; read bare_question_rate and label_open_rate
together, mira_turn_sec_median against the band, guest_words_per_answer_median,
overlaps and self-answered turns (neither may rise) and turn_gap_ms_median
(a slower effort shows there first). A PASS plus one operator listen ships
it; the rooms booked before that run the deployed brief. The register
entry's readout is the fifth real room.

## Blaine Mathieu, Nov 4 2026: the same short line before every question

What happened. The first room on the Nov 3 beat. After nearly every answer
Mira said one pithy line folded from it (a wave against a river, retrofit
as table stakes, "different, not better" in his own terms) and then a short
question, often a generic one about what surprised him or where it breaks
down. Each line was fine; together they were a formula, and Patrick heard
it as a summary she gave every time a guest finished. The measures read
it only in part: label_open_rate 0.355, reaction_open_rate 0.29,
bare_question_rate 0.355, her median turn 5.3 s against the 12-20 s band.
A twelve-word aphorism is a "reaction" to `question_turn_shape`, so the
shapes looked mixed while the turns sounded identical.

Why. She did what she was told. The brief's last critical line asked for
one sentence of what the answer changes, then the question. Three standing
network lessons in the same prompt asked her to ask the new question
directly, to send most turns straight to the next question, and to deliver
each question in one short sentence. The only turn that satisfies all four
is one short line and one short question. The good turn of the hour was
the one that broke the pattern: she set his bank example beside a fact from
the research about a manufacturer that went the other way, and the question
came out of that.

What changed. HOW TO REACT now says what the turn after an answer is FOR:
a bridge to the next question, built from one particular thing the guest
said (joined to something earlier, set beside a fact from the brief or the
research, a consequence or tension they have not named, or her own
different view), one to three sentences as the thought needs, then the
question that thought makes necessary. Folding the answer into a phrase is
named by shape, and the turn is to vary, so a listener cannot predict its
shape. The critical line follows it. The three lessons, and a fourth
(two closing questions, from before the room ran the closing round) that
would have been next in line, stay out of the prompt through
`learning.SUPERSEDED_BY_BRIEF`, keyed by id, so the change ships and
rehearses as one piece; retire the rows once the brief is live.
`audio_metrics.one_liner_rate` (exactly one sentence of at most fourteen
words before the question) measures the sameness, target under 0.35; the
recounted excerpt of this room reads about 0.59.

Before any booked room hears this brief: a two-arm rehearsal on a fixture
with long arcs (`adrian`), proposed = this branch, current = the deployed
brief; read one_liner_rate beside label and bare (the cure is variety, not
the bare question again), mira_turn_sec_median moving toward the band,
guest_words_per_answer_median and guest_words_trend, overlaps and
self-answered turns (neither may rise). A PASS plus one operator listen
ships it.
