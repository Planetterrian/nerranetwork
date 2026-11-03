# Story breaks that reach the audio, and handoffs that match (Oct 16 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Story breaks that reach the audio, and handoffs that match (Oct 16 2026)

Slate review ([`docs/reviews/slate_review_2026_10_16.md`](docs/reviews/slate_review_2026_10_16.md);
register `story-breaks-reach-the-audio-2026-10-16`,
`nerra-daily-handoffs-aligned-2026-10-16`; guards
`tests/test_slate_2026_10_16.py`). Measured in the shipped MP3s, the beat
itself works (1.02–1.06 s on the no-music shows, the cue ~13–16 dB under the
voice); what failed was DETECTION: **13% of October's story changes never
reached the audio** because a line's opening was matched letter for letter
against Whisper ("the early 2000s", "1,500", "Columbia's", "La Nassion").
`engine/story_breaks.py` now folds accents, speaks years and decades the same
way on both sides, and falls back to a fuzzy anchor (first letter must match,
0.72 ratio, ±150 words of the line's expected place) — 362 unplaced → 32 on
replay, every recovered anchor on the line's first word. A link at the end of
a paragraph makes it a story (FF Ep224 had one beat for seven); a numbered
heading is ONE story (Omni View's Read-more list had split its lead); two beats
on adjacent lines settle on the segment opener or the story start. **A Nerra
Daily handoff must introduce the segment after it** (`realign_handoffs`, metric
`handoffs_realigned` — Ep049/055/057 shifted by one, 39 wrong introductions;
replayed on those three, 42 wrong → 1). **Nerra Personal runs the same repair**
(`scripts/build_personal_feeds.py`, Oct 17 — it had only the count check that
let those editions through) and the same links token budget.
Also: ratio shorthands (MoM, YoY, QoQ, ROE, ATH, AR, ML) match only their own
case ("mom-and-pop" aired "month over month"); paid placements are dropped by
URL path (`NETWORK_EXCLUDE_URL_PATTERNS`); Both Sides is overlap-exempt on
Vancouver, Collingwood and Top World; MIT names the record's start date and
teases the next trading session; the Week's Board tracks a market across
rewordings and counts single readings instead of reading them out.
⚠️ AUDIO — A/B-listen one FF and one Omni View episode.
