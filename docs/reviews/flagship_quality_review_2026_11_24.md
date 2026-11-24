# Flagship quality pass: SpaceX Daily and Tesla Shorts Time (Nov 24 2026)

Operator-directed. The two shows carry about 55% of the network's downloads.
This pass read Tesla Ep660-675 and SpaceX Ep157-172 as a listener would
(script, digest, chapters, feed title, closing) and checked SpaceX Ep172
against its own sources. It asks one question: what would stop a listener
recommending the show?

Register `flagship-quality-2026-11-24`; guards
`tests/test_flagship_quality_2026_11_24.py`.

## 1. What a listener heard wrong, ranked

### 1.1 The share price moved a lot and the show never said why

Both shows speak their company's share price in every closing.

| Episode | Spoken | Reason given on air |
|---|---|---|
| Tesla Ep660 / Ep661 | up 4.2%, up 5.5% | none |
| Tesla Ep672, Ep673, Ep674 | down 7.6% (three mornings, one Friday close) | none |
| Tesla Ep675 | up 11.5% | none |
| SpaceX Ep157 | up 5.8% | none |
| SpaceX Ep170, Ep171 | down 7.7% | none |
| SpaceX Ep172 | up 4.4% | none |

A Tesla show that says "up eleven point five percent" and moves to the
sign-off has skipped the day's most-asked question. The cause is by design:
the Tesla digest prompt rejects "pure price commentary" as news, the SpaceX
prompt routes investor items to Market Watch, and nothing fetched the reason.

Tesla's Monday episodes (Ep667, Ep674) also said "closed at" for a Friday
close; only Saturday and Sunday carried the day word, and neither show knew
a market holiday.

**Built.** `engine/market_move.py`: when the hook's close-to-close move is 4%
or more, the run makes ONE web search for reporting dated on that session or
the day after, merges what it finds into the ordinary article list (so it is
fetched, cited and claims-checked like any story), and hands the digest
prompt a fact block. The pipeline never writes a reason. When the search
finds nothing dated, the block says so and the prompt's rule is to give no
reason. `engine/market_calendar.py`: the NYSE calendar by rule; "closed
Friday at" on a Monday before the open, "closed Wednesday at" on
Thanksgiving and the day after.

### 1.2 SpaceX Ep172 told three things its sources do not say

Checked on Nov 24 by reading the two pages the episode cites.

- **The lead and the whole deep dive.** The KeepTrack page says the satellite
  "lost about 12 km of altitude over three months" near 477 km and that "the
  data does not show which" cause. The episode said a "sudden" drop from 550
  km caused by "a burst of atmospheric drag", recovered "without requiring
  immediate ground intervention", and built a five-minute engineering
  segment and the feed title on it.
- **"Britain Seeks Answers on Starshield Service Changes."** The cited
  article never mentions Britain. It is about a US congressman.
- **One story three times.** The same Himes story was Top News 4, Top News 8
  and the Counterpoint.

The claims gate passed the episode 9 of 9. Each ledger quote is in its page;
nothing compares an item's names, its adjectives or its causes with the page.
Earlier deep dives carried the same class from memory (Ep171 "Raptor uses
pintle injectors"; Ep170's Atlas alloy history).

**Built.** A measure, `item_names_sourced_measure` (both shows): the names an
item carries that its own fetched source does not. Replayed on Ep172 it
returns "British, Britain". It records and never fires, because fetched page
text is not committed and it cannot be calibrated on past episodes.
**Prepared for rehearsal (prompt):** the deep dive names hardware, design
details and causes only where a fetched source states them; the Counterpoint
is a different story from every Top News item.

### 1.3 Tesla's Counterpoint is missing from most episodes

The Short Spot (spoken as the Counterpoint, the show's one honest bearish
segment) had text in 11 of the 30 digests Ep646-675. On 19 it shipped empty
or without its header. The cross-section dedupe removes a later item that
repeats an earlier one, the Short Spot is a single item that often re-uses a
Top 12 story, and so the segment was the thing removed.

**Built.** `digest_overlap_claiming_sections: [Short Spot]` on Tesla: the
Short Spot keeps its story and the earlier item is removed instead, so the
story is still told once. The lead item is never given up. This changes what
is spoken, so it rides the rehearsal.

### 1.4 The SpaceX deep dive reads equations aloud

Ep171 and Ep172 speak multi-step arithmetic with constants. This came from
the Nov 14 "show the working" rule. **Prepared for rehearsal:** the rule is
rewritten for the ear (no equations or chains of constants, at most two
derived numbers, each said as a comparison).

### 1.5 Chapters point at the wrong story

- SpaceX Ep172: a one-sentence second telling of the Himes story took a
  chapter, and the min-gap rule then dropped the next story's chapter, so
  "Himes Warns…" sat over forty seconds of the Mexico debris story.
  **Fixed** in `engine/chapters.py`: a start whose own telling is shorter
  than the gap yields. The replay now shows the Profepa chapter.
- Tesla Ep674: the hook said "a Space X takeover of Tesla" and the bare
  `takeover` marker opened the episode on "Tesla X Takeover" ahead of
  Introduction. **Fixed**: only the full section name fires.

### 1.6 Smaller, prepared for the same rehearsal

- SpaceX Community Buzz carried posts with no fact about SpaceX (a slogan,
  opinions on Tesla FSD, a fundraiser). The prompt now excludes them.
- "Not confirmed" was spoken about NASASpaceflight reporters' posts. A news
  outlet's or its reporter's post is tier 2.
- The SpaceX prompt promised 11-14 minutes; the show runs 7.3-8.7. The
  prompt now says 9-12 and gains no length lever.
- Tesla First Principles (Ep675) was a run of one-clause sentences and the
  prompt asked for 60-90 seconds against a structural rule of about two and
  a half minutes. One instruction now.

## 2. Found and not changed here

- **Tesla feed titles.** 18 of the last 22 are the hook sentence clipped
  with an ellipsis; SpaceX, on the same shared title instruction, has had a
  real short title since about Ep164. It does not follow the expansion retry
  or the structural regeneration (checked per episode in the metrics), so
  the model is simply omitting the `**TITLE:**` line on Tesla. A repair
  needs a decision: one small title-only call when the line is missing, or
  re-using the YouTube title the video stage already writes.
- **The closing runs 84-94 seconds**, about 18% of a 7.8-minute SpaceX
  episode. The outro rotation belongs to another open PR (#1741); reported,
  not touched.
- **Stories retold across days.** Dragon's return led SpaceX Ep169 and Ep170
  and was retold in Ep171; the Semi Megacharger ran in Tesla Ep669, 670 and
  672. `engine/story_recurrence.py` exists and was not rebuilt.
- **"Patrick and Vancouver"** in SpaceX transcripts is a Whisper artifact:
  every `_tts.txt` says "in". The operator withdrew the same item for MAG 7
  on Nov 2. It is `do_not_retry` for SpaceX too; the review agent has filed
  it three times.
- Tesla "Tomorrow Teaser" chapters of 5-7 seconds, and First Principles
  landing mid-body on Ep670 and Ep674.

## 3. Predictions (to score Dec 8)

1. On every episode of either show whose close-to-close move is 4% or more,
   `market_move_pct` is recorded; on at least half of them
   `market_move_reports` is 1 or more and the episode gives the reported
   reason with a Source line.
2. No episode states a reason for a move on a day `market_move_reports` is 0.
3. Tesla's Short Spot has text in at least 11 of 14 digests (baseline 11 of
   30).
4. No SpaceX or Tesla chapter title names a story other than the one spoken
   under it, on a replay of the 14 episodes.
5. `item_names_unsourced` is 0 on at least 10 of 14 SpaceX digests; any
   episode above 2 is read by hand before a firing form is proposed.

## 4. do_not_retry

- A pipeline-written reason for a stock move, of any shape.
- A firing names lint before 14 readings.
- The "Patrick and Vancouver" fix (Whisper only).
- An outro change from this pass (owned by #1741).
