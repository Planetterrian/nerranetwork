# Natural transitions, and shows that reach their length (Oct 14 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Natural transitions, and shows that reach their length (Oct 14 2026)

Operator listen: the Oct 13 beat "sounds forced and unnatural", and many
shows ran short (review:
[`docs/reviews/transitions_and_length_2026_10_14.md`](docs/reviews/transitions_and_length_2026_10_14.md);
register `story-transitions-natural-2026-10-14`,
`shows-reach-their-length-2026-10-14`; guards
`tests/test_transitions_and_length_2026_10_14.py`). The Oct 13 value was ADDED
to the voice's ~0.45 s pause and mid-episode there is no music: 1.6-1.7 s of
dead air against a 0.35 s sentence gap. **`audio.story_break_seconds` is now
the TOTAL pause (1.0)** — `plan_breaks` splices only the difference — and
**`audio.story_break_cue` lays a soft swell of the show's own theme under each
pause on the music track** (`engine.audio.breather_offsets`, steady bars, a
different one per break, ~12 dB under the voice, skipped inside the opening
bed and on shows without music). No beat within 20 s of the last; a line
opening on a pronoun or connective never starts a story; short items under one
heading are one block. **The digest length floor counts PROSE**
(`engine.generator.digest_prose_word_count`): it had counted the fenced claims
ledger (480-1,100 words), so the digest expansion never fired on the cohort's
daily shows; the retry takes every figure from the supplied material. Length
is digest-side: desk format v3 (**The Closer Look**, 300-420 sourced words;
Across 2-3; Also Today 3-5; Lead 5-8 sentences; preferred publishers; full
text ranks cluster members first), doubled deep dives (AI Chips Teardown, MAG 7
Thread, PM How It Works, FF/PT deep dives, Tesla's essay — each built from a
fetched article), a Closer Look on Vancouver and Collingwood, a longer Top
World. Targets come from the promised minutes and each host's measured spoken
rate; **every skip floor stays at its old 60% line**
(`min_podcast_publish_words`) — never raise a target without pinning it. Fixed
segment openers ("Across the region,", "At the top of the tape,", "On the
board today,") are optional now, with `digest_section` chapter fallbacks.
⚠️ AUDIO — A/B-listen.

**Oct 14 2026, evening — the first slate, scored** (§5 of the review doc;
register `slate-readout-2026-10-14`; guards
`tests/test_slate_readout_2026_10_14.py`). The desks went to 9.3-12.6
minutes and AI Chips / PM / MAG 7 / Vancouver landed inside their promises;
the breaks sat in the voice's own silence (0.99-1.19 s on Vancouver). Four
corrections: **the cue is `BREATHER_VOLUME` 0.09** — 0.22 played 2-5 dB
under the voice on the shipped mixes because loudnorm lifts an exposed gap;
calibrate a cue level on a REAL voice through `_final_mix_cmd`, never on a
preview by ear (0.22 → 4.7 dB under, 0.12 → 10, 0.08 → 13.4). **The digest
expansion is judged in prose** — it had compared prose to prose-plus-ledger
and accepted Tesla's +80-word pass as +630; the retry prompt names each
section's prose length against the format's own specs, and
`llm.digest_expansion_attempts: 2` (Tesla, FF, MIT, OV) allows a second pass
only under 90% of the floor. **A sourced item under the hook is a story**
(`story_breaks.story_units`; a `---` rule splits paragraphs) and FF's
validator accepts an unnumbered bold list — Ep222 got one beat and burned
its structural retry on a header. **Market-research press releases never
reach a prompt**: `engine.utils.NETWORK_EXCLUDE_TITLE_PATTERNS`
("… Market Forecast to 2035: 11% CAGR") at all three fetch sites, after 19
aired as headlines on eight shows in 40 episodes. Top World's floor is
1,900 with items 1-5 at 7-10 sentences (Mira speaks a developed item in
~80% of its words). **Prediction Markets' Sep 23 curriculum restock had
re-added eleven subjects the show had already taught** (same titles) —
pruned, thirteen new subjects added; a restock checks PRODUCED titles.
**A narrative pick re-interleaves the queue** (`engine.topic_queue.
resequence_unproduced`, now called by `mark_topic_produced`): the Oct 11
thin-research skip takes the topic BEHIND the head and leaves two
same-category briefs adjacent (UC Ep142 — the runway guard went red on
main with nothing wrong in the restock's data).
⚠️ AUDIO — A/B-listen one music show for the cue.

**Oct 14 2026, night — an outside review of the Oct 13 slate, checked**
(register `external-review-2026-10-14`; guards
`tests/test_external_review_2026_10_14.py`). True and fixed: **one budget
for every headline-derived chapter title** — `engine.chapters.HEADLINE_TITLE_MAX`
is `engine.titles.HEADLINE_CHAPTER_TITLE_MAX` (80); the Oct 8 clip ran at 60
and shipped "…halts the number" while most desk lead headlines run 60-80, and
every hook runs over 60, so the lead chapter existed on 9 of 20 episodes; when
the hook is too long for a title and no headline matches, the lead chapter
takes the digest's own section name (`lead_section_name`: "Lead", "Top
Story" — a story heading never is). **A line that is only a URL becomes a
`Source: [domain](url)` line** (`engine.newsletter_body.linkify_bare_url_lines`,
in `transform_daily_body`; 49 such lines in seven days on the desks and the
Board). **The hook's item leads its list** (`engine/hook_item.py`,
`hook_item_first: true` on FF / Planetterrian / Tesla; the item sharing ≥ 3
salient words with the hook and beating item one by 2 moves to the top and the
section renumbers; metric `hook_item_promoted_from`; the replay moved nothing
on SpaceX, M&A, the desks or MAG 7). **The narrative shows list their research
pages** (`engine/research_sources.py` appends a `### Sources` section the blog
card and show notes already read; `READER_ONLY_EXACT_SECTIONS` keeps it out of
the script). **The correction box renders above the headline**, and a
correction may carry `amend_headline: true` (the page title gains "Corrected:";
feed title and audio untouched) — UC Ep139's switch is the operator's. Not
true, not acted on: Top World's Both Sides is a named disagreement, never the
lead's counterpoint; Vancouver's source says 20 per cent; Nerra Daily's rundown
links each show's post.
