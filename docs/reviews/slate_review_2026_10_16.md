# Slate review — October 16, 2026

Operator brief: review every show and change from the last 24 hours, decide
what can still be improved, and look hardest at the break between stories.

## The slate

The Oct 16 slate published 16 shows, and the Nerra Daily edition went out at
about 8 AM Pacific. All five regional desks skipped with
`member_demand_unknown`, because they ran before the `PERSONAL_DEMAND_TOKEN`
GitHub secret existed. The spoken-text gate passed on every episode.

| Show | Words vs target | Script model | Claims (flagged) | Breaks found / placed |
|---|---|---|---|---|
| Tesla Ep636 | 1,300 / 1,400 | grok-4.6 | 6 (2) | 15 / 11 |
| SpaceX Ep132 | 1,445 / 1,300 | grok-4.6 | 0 | 10 / 7 |
| Omni View Ep207 | 1,740 / 1,400 | grok-4.6 | 1 | 9 / 8 |
| Fascinating Frontiers Ep224 | 1,219 / 1,700 | grok-4.6 | 9 (3) | **1 / 1** |
| Planetterrian Ep215 | 1,187 / 1,600 | grok-4.6 | 9 (4) | 12 / 11 |
| MAB Ep198 | 873 / 1,200 | **grok-4.3** (fell back) | 1 | 5 / 4 |
| Unintended Consequences Ep144 | 1,636 / 1,300 | grok-4.7 | 4 (4) | 8 / 3 |

The other nine shows ran within normal ranges.

Main had been red since 02:18 UTC. Seven tests failed, all hidden behind the
first failure CI stops on. They are fixed in PR #1448. That PR also makes the
Oct 16 publish guards safe: replayed over the October record, they would have
stopped 98 of 334 episodes, including Привет, Русский! after its feed was
updated.

## Story breaks — measured in the shipped audio

I measured five episodes: Tesla, Vancouver, Omni View, MAG 7 and SpaceX. I
decoded each MP3, located every break from the committed transcript, and read
the level frame by frame.

- **Pause length.** Shows without music get 1.02–1.06 s at a break, against a
  0.48 s median between other lines. On the music shows the cue fills the
  pause at roughly 13–16 dB under the voice. Calibration aimed for about 12 dB
  under. An ordinary sentence gap mid-episode is near silence (40–55 dB under).
- **Where breaks were lost.** The audio itself behaved as designed. The losses
  were in detection and placement:
  1. **13% of story changes never reached the audio.** 362 of 2,721 in
     October had no anchor. The opening was matched letter for letter against
     Whisper, which writes "the early 2000s", "1,500 kilometres", "Columbia's",
     "Helisco" and "La Nassion". Unintended Consequences placed 3 of 8 breaks;
     the Asia Pacific desk placed 2 of 8.
  2. **Fascinating Frontiers got one beat for seven stories (Ep222, Ep224).**
     Each item's Source sat at the end of its paragraph, under the hook rule,
     so the whole news block read as front matter.
  3. **Omni View paused inside its lead.** The Read-more list under a numbered
     story heading counted as a separate story.
  4. **Adjacent beats.** Two beats on consecutive lines play only the first,
     and in 97 October cases that sometimes put the pause a sentence early.

Fixes, all in `engine/story_breaks.py`:
- Accent folding.
- Years and decades spoken the same way on both sides.
- A fuzzy fallback for the anchor: the first letter must match, the ratio must
  be at least 0.72, and the search stays within ±150 words of the line's
  expected position.
- A link in a paragraph counts as its source.
- A numbered heading counts as one story.
- A pair of adjacent beats settles on the line that names a digest section
  (what's on, both sides, progress, the board, the deep dive). Otherwise it
  settles on the story start.

Replay results:
- Unplaced breaks fell from 362 to 32.
- All 304 recovered anchors start on the line's first word.
- Four exact anchors moved, each from one word early onto the line's first
  word.
- Outside Fascinating Frontiers and Omni View, only the 97 adjacent pairs
  change.

⚠️ AUDIO — A/B-listen one Fascinating Frontiers and one Omni View episode.

**Not changed:** the 1.0 s total pause and the 0.09 cue level. Both are
operator listening items (#69). The measurements above are the basis for that
listen.

## Other findings acted on (checked against the committed text)

- **Nerra Daily handoffs.** Three editions in two weeks (Ep049, 055, 057)
  introduced the wrong show from mid-edition on: 39 handoffs on air. The model
  wrote one handoff too few and padded the end, so the count check passed.
  `realign_handoffs` moves each handoff to the segment it describes and gives
  any unmatched segment the one-line fallback. Replayed, it changes exactly
  those three editions. The field note now also avoids the last three
  editions' lineup headlines; Ep057's note repeated the Perseverance record
  FF had led with the day before.
- **"MoM" read "mom" as "month over month".** This aired as "a month over
  month-and-pop buyer" on Vancouver Ep024 and as "my month over month" in four
  Привет, Русский! lessons. MoM, YoY, QoQ, ROE, ATH, AR and ML now match only
  in their own case.
- **Vancouver's Both Sides aired with an empty heading on the blog.** The
  overlap dedupe matched it to the lead by a shared roundup URL and emptied it
  after the script was written. Both Sides is now exempt on Vancouver,
  Collingwood and Top World.
- **AI Chips aired a sponsored interview as news.** The source was
  DCD MarketWatch, a paid section. `NETWORK_EXCLUDE_URL_PATTERNS` now drops
  paid sections by URL path at fetch.
- **Modern Investing.**
  - "since inception" is now "since the practice record began on March 16,
    2026".
  - The teaser names the next trading session instead of "tomorrow" (a
    Friday teaser had promised a session on Saturday). ⚠️ AUDIO.
- **Prediction Markets' Friday Week's Board read 18 percentages in a row.**
  It named no outcome and listed one market twice. The question had been cut
  at the reading time's colon, so it carried the day's price. Fixes:
  - The question now ends before the price, and the leading outcome is
    carried with the reading.
  - Reworded questions on the same venue are matched as one market.
  - Questions with a single reading are counted in one sentence, not read out.
- **Top World's intake line.** "No regional desk had filed by press time" is
  now a neutral "no desk edition was available". The edition note's item
  lengths now agree with the format (items 1–5 developed). ⚠️ AUDIO.
- **Omni View named outlets for stories they did not cover.** Its prompt
  required at least two outlets per story, so Al Jazeera's video on AI coding
  tools was credited as G7 coverage on Ep207, and the same happened on Ep204
  and Ep205. An outlet is now named only for its own story, and the quotable
  Go-deeper template was replaced by a description of its shape. ⚠️ AUDIO.
- **Unintended Consequences cross-promo.** The prompt supplied a stock
  sentence that aired on 4 of the last 5 episodes. The prompt now describes
  the plug by its shape instead. ⚠️ AUDIO.

## Found, not acted on here

- **The Tesla Roadster unveiling was told as about nine items.** The story
  clusters annotated it and the model ignored the notes. Merging cluster
  members into one item is a digest-design change, so it gets its own pass.
- **FF and Planetterrian deep dives re-told the lead.** This is a large part
  of why both shows ran short. Fixing it needs a deep-dive vs item overlap
  check; that is the next length lever.
- **Every show keeps talking after its goodbye.** About 100–160 words follow
  the farewell: the platform ask, the YouTube line and the network plug. This
  is audio, so the operator decides.
- **Two empty claims ledgers.** SpaceX's ledger was empty (0 of 8 items) and
  Omni View verified 1 of 7. Treating zero coverage as a gate failure is a
  policy decision.
- **Whisper near-echo tokens survive into captions.** Examples are
  "circus." after "caucus" and "securities." after "liabilities". This needs
  a calibration sweep before the filter is widened.
- **Modern Investing mixes record scopes.** The lifetime win rate and best
  trade sit beside the era alpha. This is an era-scoping change in
  `_build_portfolio_summary`.
