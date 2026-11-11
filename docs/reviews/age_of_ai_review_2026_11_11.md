# The Age of AI and Nerra Voices: review, Nov 11 2026

Operator brief: *"Please review age of Ai and Nerra Voices shows and Mira
interview setup in depth. I would like to have the best interview show with
Mira for guests and audience alike such that we have great interviews to
share. Make any changes to improve these shows and how Mira conducts the
interviews."*

Read: the nerra-voices Supabase record (every `episode_grades` row, every
guest survey and guest-experience note, every interview's status and cancel
reason), the live brief (`pipelines/voices/prompts/mira_system_prompt.txt`,
1,599 of 1,600 words), the room scenario's opening, the studio page, the
two-hour reminder and publish-day emails, the social pass, both feeds and
`api/op3_stats.json` / `api/voices_metrics.json`. Built on the earlier
threads (interview plan #1629, steers #1625/#1632, opening #1638, parts
ahead #1663) and not repeating them.

## What the record says

**The rooms.** 20 graded rooms since Sep 24: overall median 5, pacing median
4. How many of the 20 grade notes name each fault (a keyword count over the
`why` text, so read it as rough):

| fault | rooms |
|---|---|
| answers summarised, echoed or labelled before the next question | 13 |
| a question repeated | 13 |
| dead air or long gaps | 10 |
| a long scripted opening or format speech | 9 |
| a broken or repeated close | 9 |

Two guests left during an opening speech (Oct 1, 38 s; Oct 26, 106 s) and
one ended the room six minutes in because it "did not feel like a
conversation" (Oct 19). The opening speech got LONGER on Nov 6 (#1638, at
Patrick's request: patience, the pause, steering, skipping, the transcript,
the closing questions) and on Nov 9 (#1663, the parts ahead). Both
rehearsals read FAIL; both are live on main.

**The guests.** One survey answered (Blaine Mathieu, 2/10, would not
recommend): the lag between his answer and her next line, and questions that
"hit the same point over and over"; "a human questioner would have got the
hint that it was time to move on." Turn gap median across ten rooms: 4.5 s
(p90 6.0 s). The room waits 1.8 s of silence, decides (0.5 s, +1.5 s when
the clause reads unfinished), then the voice API's first audio
(`docs/reviews/turn_cues_2026_10_28.md`).

**No real guest has been in a room since Nov 4.** Every room change since
#1629 is rehearsed by fixture only, and the deployed scenario is still
#1632's (Nov 5). Today's Nerra Voices room (Nov 11 21:30 UTC), Rania (Nov 12
12:15 UTC) and the two Nov 13 rooms will be the first real read of the
interview plan and the steering fixes, on the brief that is on main.

**Bookings.** Of 69 interview bookings, 20 were cancelled and 4 missed or no
show. One cancel says it plainly: "I need a business hours time frame, as I
thought I was setting it for 1 pm CST." Today's 08:45 UTC Nerra Voices room
was missed with the reminder sent.

**The audience.** Age of AI: 31 downloads a week (141 in 30 days); Nerra
Voices: 5. Neither feed carried a single `podcast:transcript` until today's
backfill. Ep12 to Ep15 and Nerra Voices Ep3 to Ep4 carry titles clipped
mid-sentence with an ellipsis (published before `fit_first_clause`). The
publish-day email gives the guest a link, a clip, a card and their links,
but nothing written for them to post.

## What changed today

Safe to merge before the booked rooms (nothing the room or the brief reads):

1. **How the hour goes, written down** (`engine.brand.MIRA_HOUR_PARTS`): the
   studio's pre-join card and the two-hour reminder email now say, in six
   lines, what the guest otherwise only heard in Mira's opening speech: a
   hello and then their subject; she waits a few seconds; the buttons and
   notes, and that any question can be skipped; an answer can be started
   again (cut by `auto_edit.RESTART_RE`); a short closing round with the
   last word theirs; the transcript terms. Every line is the room as built.
2. **A post in the guest's own words**: the social pass drafts `guest_post`,
   first person, from the transcript, ending on the episode link; the
   publish-day email carries it as a draft to change. A guest who shares is
   the show's best distribution, and the guest who must write the post first
   mostly does not.
3. **Transcripts on both interview feeds**: the `vtt_backfill` run.

Drafted, NOT for a booked room until rehearsed and listened to:

4. **A short spoken opening.** With item 1 live, beat 2 of HOW TO OPEN can
   be two or three sentences: who she is, the one-clause claim, the parts
   ahead, that it is their hour to steer and the page has the rest. It keeps
   Patrick's "still learning, ask their patience". It needs a two-arm
   rehearsal (`arms: both`, fixture `adrian`), a read of the opening's
   seconds, and one listen.

## The decision this bears on

Patrick's open call on #1638 and #1663 (keep both, revert #1663, revert
both) is his. What this review adds: the opening speech is named in 9 of the 20 graded rooms and is the only
fault guests have walked out on, and #1638 and #1663 both made it longer. Item 1 makes most of that
speech redundant before any brief change.

## Next, ranked

1. Read today's Nerra Voices room and Rania's room as the first real test of
   the plan and steers: grades, `plan reached k/n`, the presses.
2. Ship item 4 after its rehearsal and a listen.
3. The turn gap: measure first-audio latency per turn (deferred in the
   Nov 3 review), then trial `reasoning_effort: medium` in a two-arm
   rehearsal; an adaptive end-of-turn wait only after both.
4. Re-fit the six clipped feed titles (same GUIDs) with `fit_first_clause`.
5. Booking: show the slot in the guest's own zone on the Cal.com page and
   the confirmation (the CST cancel).

## Appendix: item 4, the proposed beat 2

Today (about 110 words of instruction, spoken as a speech of five or six
sentences):

> 2. How the hour works, in a few short sentences: you are Mira, the AI who
> hosts {{show_name}}, still learning, and ask their patience;
> {{mira_spoken_claim}}; you pause after they finish, so nothing gets cut
> off; two or three parts ahead, from the prepared questions, a phrase each;
> this is their hour: they can steer any time, aloud or with the studio's
> buttons and notes, any question can be skipped, anything can come out
> afterwards, and they will see the transcript before anything goes out; the
> hour ends with closing questions, where to reach them, and anything not
> covered. Then ask if that sounds good.

Proposed (the rest is on the page in front of them):

> 2. How the hour works, in two or three sentences, never a list: you are
> Mira, the AI who hosts {{show_name}}, still learning, and ask their
> patience; {{mira_spoken_claim}}; two or three parts ahead, from the
> prepared questions, a phrase each; it is their hour to steer, aloud or
> from the studio page, which has the rest. Then ask if that sounds good.

The room's own opening note ("beat 2 of HOW TO OPEN: how the hour works, in
a few short sentences") stays true, so the scenario does not change and no
deploy is needed; the change is live the moment it merges, which is why it
waits for the rehearsal and the listen.
