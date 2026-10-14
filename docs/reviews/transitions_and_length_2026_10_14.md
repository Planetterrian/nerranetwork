# Natural story transitions, and shows that reach their length (Oct 14 2026)

Operator brief: review and improve the new shows significantly; the new
pause between stories sounds forced and unnatural; many shows are short of
their time targets — add deep dives or expanded content so they reliably
reach them with informative content.

Method: the shipped audio was measured, not described; three independent
reviews read the last 5-7 episodes of all thirteen new shows plus the short
established shows; every claim below was checked against the committed
files or code before anything changed. Register entries
`story-transitions-natural-2026-10-14` and `shows-reach-their-length-2026-10-14`;
ledger `network` 2026-10-14; guards
`tests/test_transitions_and_length_2026_10_14.py`.

## 1. The pause

**What a listener heard.** Vancouver Ep021 (no theme music), silencedetect
at -50 dB on the final mix:

| | Seconds |
|---|---|
| Median gap between sentences | 0.35 |
| 90th percentile gap | 0.47 |
| Every story change | 1.59-1.69 |

The Oct 13 change ADDED 1.2 s to the voice's own ~0.45 s pause. Mid-episode
there is no music under the voice (the opening bed is gone by ~48 s), so a
story change was 1.6-1.7 s of digital silence, almost five times the normal
gap. The module docstring's claim that "the sidechain lets the bed come up a
little in the gap" was true only in the first 48 s. Placement was also wrong
in places: two beats 7 s apart, one before "He asked Albertans to vote…" (the
premier's own quote, same story), one between a weather reading and its
forecast.

**What changed.**

- `story_break_seconds` is now the TOTAL pause at a story change (1.0 s).
  `plan_breaks` measures the voice's pause and splices only the difference,
  so every story change sounds the same length whatever Grok left there.
- A soft swell of the show's own theme sits under each pause
  (`audio.story_break_cue`). It rides the music track, so the existing
  sidechain shapes it: it blooms as the last word ends and tucks under the
  first words of the next story. Each cue is a different bar from the
  theme's steady body (`breather_offsets`), faded in and out, about 12 dB
  under the voice. Cues inside the opening bed are skipped; shows with no
  music file (Vancouver, Collingwood, Unintended Consequences) get the
  shorter pause alone.
- No beat within 20 s of the previous one; a line that opens on a pronoun or
  connective never starts a story; short items under one heading are one
  block.
- The spoken turn: the shared rule's quotable attribution specimen
  ("…, Reuters reports") is gone — 16 of 18 Vancouver stories and 28 LatAm
  sentences ended on that tag — and consecutive stories must open on
  different shapes. The fixed segment openers ("Across the region," 24 of 25
  desk scripts; "At the top of the tape," 7 of 7 MAG 7; "On the board today,"
  6 of 7) are now optional, never the opening words, with digest-section
  chapter fallbacks so the chapters survive.

Previews from the shipped Top World Ep021 and Prediction Markets Ep021
(before/after) were sent to the operator on 2026-10-14. ⚠️ AUDIO — A/B-listen.

## 2. Length

| Show | Script / old target (last 7) | Minutes | Promise |
|---|---|---|---|
| LatAm | 66% | 5.9 | 10-12 |
| Asia Pacific | 72% | 6.3 | 10-12 |
| North America | 72% | 6.1 | 10-12 |
| Africa & Middle East | 79% | 6.9 | 10-12 |
| Europe | 84% | 6.8 | 10-12 |
| Top World | 108% | 7.8 | 11-13 |
| AI Chips | 91% | 7.8 | 8-10 |
| MAG 7 | 89% | 6.7 | 7-9 |
| Prediction Markets | 87% | 7.1 | 8-10 |
| Vancouver | 86% | 6.5 | 8-9 |
| Collingwood | 72% | 4.5 | 9-10 |
| Fascinating Frontiers | 69% | 7.9 | — |
| Planetterrian | 68% | 8.3 | — |
| Tesla | 78% | 8.1 | — |

**Why.**

1. The digest is the ceiling: scripts tell 55-97% of the digest.
2. The digest-side expansion never fired. `generate_digest` measured
   `len(text.split())` before the fenced claims ledger was split off, and a
   grok-4.7 ledger is 480-1,100 words, so Africa & Middle East Ep021's
   720-word digest read as ~1,400 against its 1,100 floor. No credit file
   shows `x_thread_generation_expansion` on AI Chips since Ep007, MAG 7
   since Ep008, PM since Ep002.
3. The formats capped the digests: two Across items and two to four
   one-liners on the desks; 220-320-word deep dives on AI Chips, MAG 7 and
   PM (with a rule that starved the Teardown of sourced numbers); FF/PT deep
   dives of 140-210 words; Tesla's spoken essay capped at six sentences.
4. Some targets could not produce the promised minutes at the hosts'
   measured spoken rate (~160 wpm Patrick, 171-185 Mira, 185 Dan).

**What changed (all digest-side; the podcast-side length retry stays banned).**

- `digest_prose_word_count` drives the expansion check; the retry may
  explain a mechanism in general terms but takes every figure from the
  supplied material.
- Desks, format v3: **The Closer Look** (300-420 words, one story told at
  length from fetched text or a multi-outlet cluster: what happened, how it
  got here, who it changes things for), Across 2-3, Also Today 3-5, Lead 5-8
  sentences. Full text 20 × 5,000 characters, ranked cluster members and
  preferred publishers first; `preferred_domains` (wires and papers of
  record) — the desks had none, so the 40-article cap was a newest-first
  slice.
- Deep dives doubled and sourced: AI Chips Teardown 450-600 (built from one
  fetched article not used as news, with a worked example), MAG 7 Thread
  400-550, PM How It Works 450-600 (abstracts 5 + 3), validator rules for the
  Teardown and Thread.
- Vancouver and Collingwood: their own Closer Look. Top World: items 1-3 at
  six to nine sentences and a 900-1,150-word Saturday story.
- Fascinating Frontiers and Planetterrian: deep dives 450-550 words, figures
  from fetched text only. Tesla: First Principles 400-500 words with five
  sourced figures, and the six-sentence spoken cap removed (Ep633 spoke ~110
  words of a 387-word essay). Offshore North's contradictory "lengthen Plain
  Sailing" line resolved toward the 300-word cap.
- Targets sized from the promise and the measured rate; every skip floor
  pinned at its old 60% line (`min_podcast_publish_words`), so a longer
  target cannot cost an episode.

Collingwood is supply-limited (25-74 articles a week); it is set to 1,150
words, about 7-8 minutes, and its prompt now says so. More town and county
sources are the lever there.

## 3. Content defects fixed with it

- Six absence and rule-narration shapes the filter missed (20 matches
  across 2,321 scripts, all narration).
- Prediction Markets' New and Notable is omitted on an empty day instead of
  announcing the absence.
- Peptides and Longevity speak a point estimate with who was studied, never
  a confidence interval, and state the evidence level positively.
- AI Chips no longer lists the specifications an announcement left out.
- Desk Both Sides is the region's own question, never the Lead's or the
  Closer Look's story; Progress Watch is never a sports score.

## 4. Not done, with reasons

- A Vancouver civic-explainer curriculum (official pages fetched per
  subject) and a Collingwood council-agenda reader: both need new sources
  probed from a runner first.
- Daily DriveBC new-versus-continuing state: needs a small state file; the
  Closer Look now carries the length that Getting Around used to pad.
- The Omni View flagship prompt keeps its own attribution example; it is the
  control of the Oct 13 spoken-open readout.

⚠️ AUDIO — A/B-listen one desk, AI Chips, Vancouver, Fascinating Frontiers and
Tesla on the first post-merge slate.
