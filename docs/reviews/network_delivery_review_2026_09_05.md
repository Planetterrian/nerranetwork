# Network delivery review — 2026-09-05

**Operator brief:** "The new flagships seem very narrative driven with some
repetition that seems redundant. Ideally I would like the flagships and all
shows to be more content, interesting information and useful information
driven with a pleasant, engaging, informative, consistent and alluring
delivery that has the audience wanting to come back for more of the podcast,
blogs and accompanying videos."

**Scope:** SpaceX Daily, Tesla Shorts Time, Models & Agents (the three shows
carrying >50% of downloads), plus a four-show sample (Omni View, Fascinating
Frontiers, Planetterrian, Modern Investing) to establish whether the pattern
is network-wide. Evidence: the six most recent transcripts per flagship, the
two most recent per sample show, the matching `_tts.txt` scripts and `.md`
digests, and every prompt that feeds them. Drift guards:
`tests/test_delivery_pass_2026_09_05.py`.

## Verdict

The complaint is accurate, it is network-wide, and it is mostly not what it
sounds like. "Narrative-driven" turned out to be **four mechanical
mechanisms**, none of them a matter of the host's taste:

| # | Mechanism | Evidence | Fix (this pass) |
|---|---|---|---|
| 1 | **The script stage copies the digest.** On the worst days 62–78% of a script's 8-word phrases appear verbatim in the digest (SpaceX Ep089/090, Tesla Ep592/594, M&A Ep161). The model is de-markdowning, not writing — so every duplicate and every written-register sentence in the digest ships as audio. | `engine.script_audit.digest_overlap`; SpaceX Ep090 lines 17–25 = digest line 9 word for word | Shared CONTENT DISCIPLINE block (digest is source, not draft; no 8-word carry-over); metric per episode |
| 2 | **The digest repeats itself across sections and nothing enforces the "ZERO OVERLAP" rule.** Tesla Ep592: all five X Takeover items were Top 12 items 4/3/6/11/7 re-headlined (no Source lines, so URL checks could not see them); Ep594 Short Spot ≡ story 11, First Principles ≡ story 3 (~24% of body words re-told). SpaceX Ep090: the Memphis outage spoken six times across Top News, AI & Compute and the Deep Dive. M&A Ep163: HARNESSEVO in four sections. | 33 duplicate items in 160 recent digests, every one a true duplicate on inspection | `engine.digest_overlap` drops the later item (URL, headline, or body-vocabulary match) before the validator and again after any regeneration; metric `digest_cross_section_dupes_removed` |
| 3 | **The deep dive re-tells a story already covered.** M&A 5 of 6 episodes (the one exception, Ep162, was the densest of the six); Omni View's "Understanding the Issue" re-narrated the lead for 16 lines with the prompt's own transition sentence; Planetterrian Ep172 re-told the tension-wood story; SpaceX's 467-word Deep Dive carried two numbers, both already spoken. | Section-by-section word maps in the four audits | Every deep-dive spec now: a second story, not a second pass — nothing from a covered body may be restated; a numbers floor (SpaceX 5, M&A 4, Tesla 3) |
| 4 | **Prompts demanded framing and supplied the sentences.** The memory composer injected *MANDATORY CONTINUITY: add 1-2 natural sentences of where today's development fits in the ongoing arc* on every story of every memory show while the status block said "at most ONE"; Tesla's prompt had a whole STORYTELLING LAYER and a "binge-worthy chronicle" mandate; digest prompts required a "why it matters" and a "what to watch next" sentence on every item (12 items = 24 framing sentences), so Ep590 spent four sentences saying figures were not provided. Worked example sentences shipped verbatim: FF Ep182 L2 and PT Ep173 L2 are the prompts' example transitions; PT Ep172 L5 and OV Ep164/165 are the supplied deep-dive openers; Tesla Ep594's "There is a challenge worth discussing" is prompt line 145. | Filler 7–15% of sentences; 5/5 M&A callbacks pure re-tells; 4 "What happens next is…" in OV Ep164 | Memory is background for accuracy with one delta-bearing callback; every worked example replaced by a described shape; per-item framing lines removed from six digest prompts |

Two smaller findings complete the "consistent delivery" half of the brief:
the **closing rotated through 3–4 registers** per show (SpaceX: warm / clipped /
"that's a wrap" across six episodes; M&A's Ep163 switched outro and dropped
every transition at once), and **Modern Investing read its full portfolio
record twice** ninety seconds apart because the Market Pulse spec required
the alpha "in the same breath" while Portfolio Performance was "the ONLY
segment that reports running portfolio stats".

What was NOT the problem: continuity callbacks are rare (SpaceX 0–1 per
episode, Tesla 4 across six) — the memory system produces almost nothing
audible, and what it produces is a re-tell. The fix is to stop asking for
narration, not to add more.

## Density baseline (engine.script_audit, last four episodes per show)

| show | digest-verbatim | filler | repeated numeric facts |
|---|---|---|---|
| SpaceX Ep087–090 | 61–71% | 6–10% | 0–4 |
| Tesla Ep591–594 | 10–78% | 2–9% | 0–1 |
| Models & Agents Ep160–163 | 29–62% | 2–7% | 0–3 |
| Omni View Ep162–165 | 32–68% | 3–10% | 0 |
| Modern Investing Ep157–160 | 27–41% | 4–8% | 3–4 |
| Planetterrian Ep170–173 | 19–77% | 3–11% | 0–2 |

The verbatim share is bimodal within a show (Tesla 10% one day, 78% the
next): the model either rewrites or transcribes, and nothing told it which.
The manual audits counted more repetition than the numeric-phrase detector
does (SpaceX Ep090: six tellings of Memphis vs four numeric repeats) because
they counted claims; the metric counts numbers. It is a floor, not a census.

## Shipped

**Data-side (no A/B needed — deterministic, read-only or removal-only):**

- `engine/digest_overlap.py` — cross-section duplicate strip: same Source
  URL, headline sharing ≥50% of salient words (≥3 shared), or body sharing
  ≥50% of salient vocabulary (≥8 shared tokens). Blocks are split at
  numbered items AND header lines (Tesla's X Takeover items ship with no
  blank lines between them and the `### Top 12` header sits under the hook
  with no blank line — the first parser draft saw zero items). The preamble
  hook is never an item. Wired into `run_show` before validation and after
  the structural regeneration. 160-digest sweep: 33 removals, no false
  positives on inspection. A section emptied by the strip is a correct
  outcome (it triggers the existing one-shot structural regeneration), not
  a bug to soften.
- `engine/script_audit.py` — per-episode density audit: digest-verbatim
  8-gram share, near-duplicate sentence pairs, numeric facts spoken more
  than once, filler-shape sentences (ten skeletons: spectator, underscores,
  meaning, big-picture, takeaway, watch-for, nothing-to-say, announcing,
  advisory, frame), hook restated. Metrics `script_*` per episode;
  `::warning::` above thresholds (verbatim ≥50%, filler ≥12%, ≥3 duplicate
  pairs, ≥6 repeated facts); `review_snapshot.py` tabulates the last N.
- `engine/show_memory.py` — the composed section no longer says MANDATORY;
  one callback, only with a delta. Both status blocks (`show_memory`,
  `tesla_memory`) drop the three "bigger arc / open questions / what to
  watch next" prompts and the Tesla block's quotable "Remember, we covered…"
  example (the shared block lost it on Sep 4; Tesla's bespoke copy had not).
- `assets/pronunciation.py` — "VS Code" spelled out before the versus rule
  ("Cursor versus versus Code", SpaceX Ep090); `r/teslamotors` spoken as
  "the teslamotors subreddit" ("according to our slash Tesla motors" ×3,
  Tesla Ep590).
- `run_show._collapse_duplicate_tail_lines` — a line repeated inside the
  closing eight is dropped (MIT Ep159 spoke the gallery plug before and
  after the disclosure).

**Prompt-side (⚠️ A/B-listen per landmine #17 — every item changes shipped
audio):**

- `shows/prompts/_shared/content_discipline.txt`, included in the nine
  English news-show podcast prompts (SpaceX, Tesla, M&A, OV, FF, PT, MIT,
  EI, MAB): digest is source material not a draft; sentences follow facts
  (2–6 per story, cut below two, never "no details were provided"); one
  owner per fact; a story ends on its last fact; transitions carry
  information or are dropped; source named once; memory for accuracy with
  one delta-bearing callback; the same voice every day. Shape only — no
  specimen sentence.
- Tesla podcast: STORYTELLING LAYER and MANDATORY NARRATIVE CONTINUITY
  removed; the memory block is accuracy background; "5–7 sentences each"
  becomes sentence-count-follows-fact-count; the Counterpoint enters on the
  concern's first fact (its supplied transitions had shipped verbatim);
  First Principles and Counterpoint may not restate the body.
- SpaceX podcast: Deep Dive density floor (≥5 numbers not spoken earlier)
  and no re-telling of the Top News item it grows out of; the Counterpoint
  anchor sentence must carry the concern's first fact; Buzz items that
  repeat Top News are skipped.
- Models & Agents podcast: the spoken "What You Need to Know" rundown is
  gone (the top story was the first thing heard three times over); Under
  the Hood is a second technical story with ≥4 numbers and may not restate
  any news item; Things to Try may not restate the deep dive; the "just when
  you thought you'd caught up" and "If you've been using X…" specimens are
  described shapes now.
- Omni View / Fascinating Frontiers / Planetterrian podcast: the worked
  example blocks and supplied transitions are described shapes; chapter
  anchors ("progress worth knowing", "to really understand", "something
  most people get wrong") stay as phrases the writer builds a sentence
  around; each deep dive explains the mechanism only and may not restate
  the lead's body; "End with what happens next" and "Close with the
  practical takeaway" removed.
- Modern Investing podcast + digest: "STORYTELLING over lecturing", the
  sports-season NASDAQ arc and "make the NASDAQ race feel alive" are
  replaced by worked-example-over-abstraction and reported-once; the Market
  Pulse speaks the NASDAQ level and YTD only — portfolio numbers belong to
  Portfolio Performance alone; one mechanic taught once per episode.
- Digest prompts (Tesla, SpaceX, M&A, FF, PT): fixed sentence counts
  replaced by sentence-count-follows-fact-count with an explicit ban on the
  restatement sentence and on "figures were not provided"; per-item "why it
  matters" only when the source explains it; per-item "what to watch next"
  replaced by a dated next step only when the source names one; Tesla's X
  Takeover placeholders ("What this means and why it's interesting", "Why
  this matters") replaced by facts and every Takeover item now carries its
  Source line; M&A gains ONE STORY = ONE ITEM and Under the Hood must avoid
  every news item, not only the Top Story.
- Closings: one sign-off per show for SpaceX, Tesla, Models & Agents and
  Modern Investing (the sibling plug and website surface still rotate after
  it). This reverses the Sep 4 M&A pool expansion on purpose: the operator's
  ask is a consistent voice, and the closing is the signature.

## Predictions (scored by the next review of each show)

- **SpaceX / Tesla / M&A digest-verbatim share** (script_audit, last 10):
  baseline medians 66% / 49% / 44% → expected ≤25% on every episode.
- **Cross-section duplicates**: `digest_cross_section_dupes_removed` is
  expected to fall toward 0 as the digest prompts stop producing them (the
  strip still catches the rest); Tesla baseline 1.6/episode over the last
  20.
- **Filler share**: baseline 6–10% on SpaceX, ≤5% expected; the
  "underscores" and "spectator" shapes at 0 on 8 of 10 episodes.
- **Repeated numeric facts**: SpaceX ≤1 per episode (baseline 0–4).
- **M&A Under the Hood subject** distinct from every news item on 10/10
  (baseline 1/6).
- **Closing register**: one sign-off text on 10/10 episodes per flagship.

## Not done (deliberately)

- No change to the `<fast>` wrap, voice, or audio chain — outside this
  brief and landmine #17.
- The digest-verbatim rule is a prompt instruction, not a rewrite pass; if
  the metric does not move, the next lever is a data-side paraphrase
  check that rejects a script over the threshold and re-runs the script
  stage once (cost: one podcast call). Not shipped now because it spends
  credits on a guess.
- Blog and video surfaces are downstream of the digest and the script:
  the duplicate strip removes the doubled X Takeover items from the blog
  directly; video descriptions and chapter titles come from the same
  digest headlines. No surface-specific change was needed.

## Same-day readout — Tesla Ep595 (old prompts, 07:21 UTC) vs Ep596 (new prompts, manual re-run 15:44 UTC)

The operator re-ran Tesla after the merge, which gives one paired
comparison on the same day. Caveat first: a same-day re-run works from a
depleted pool — the morning's 17 stories sit in the recently-covered
exclusion list and the fetch found 34 articles against 69 — so Ep596's
digest collapsed to ONE Top 12 item plus five X Takeover items (1,178 words
against 2,145) and the episode ran 7.8 minutes against 9.7. Thinness is the
re-run, not the prompts. What the pair does show:

| | Ep595 (old) | Ep596 (new) |
|---|---|---|
| digest-verbatim 8-grams | 63% | 51% |
| filler-shape sentences | 3 (4%) | 0 |
| cross-section duplicates left in the digest | 0 | 0 (strip active) |
| closing text | pinned | pinned |
| same story told twice | NHTSA audit: body then Counterpoint (lines 65–73 vs 127–135) | NHTSA audit: body then First Principles (self-certification essay restates "no steering wheel", "standards written for conventional controls" ×3) |
| within-item restatement | "The next step will show whether this chemistry moves into other lines" restates line 13 | lines 41/43 restate 37/39 (unboxed line, recycled panels) |
| dangling references | "The ad drew attention…" with no antecedent | none |

Verdict: real but partial. The filler shapes, the "watch for" tails, the
varying closings and the digest-side duplicates are gone; the script is
tighter sentence by sentence. Two things did not move enough:

1. **Verbatim copying** fell 63 → 51 percent against a 25 percent target.
   Shipped the same evening: a **script rewrite gate**
   (`engine.pipeline._script_rewrite_gate`, `llm.script_rewrite_gate_overlap_pct`
   = 40 on the nine English news shows). When the finished script carries
   ≥40% verbatim 8-grams, the script stage re-runs ONCE with the copied
   sentences named; the rewrite is kept only when it copies less and is at
   least 70% of the original length. Metrics
   `script_rewrite_gate_{fired,before_pct,after_pct,accepted}`. Cost: one
   extra script call on days it fires (~$0.03). It is a rewrite gate, not
   a length lever — it never fires on word count.
2. **The essay re-tells a covered story** on both episodes (Counterpoint in
   Ep595, First Principles in Ep596). The digest prompt chose the essay
   subject from the day's lead; the podcast prompt's "take only the
   mechanism" instruction was half-obeyed. Shipped: Tesla First Principles
   gains the TOPIC DISTINCTNESS rule Models & Agents' Under the Hood already
   has (FF and PT already had "choose the CONCEPT, not the story"). A
   mechanical essay-vs-item overlap note was prototyped and NOT shipped:
   salient-token overlap between an essay and the item it re-tells sits at
   0.26–0.42 while unrelated pairs reach 0.30, so there is no threshold
   that does not misfire.

Not detectable mechanically: the Ep596 restatements are semantic
paraphrases ("molded exterior panels… remove the conventional paint shop" /
"recycled-content panels eliminate the need for a traditional paint booth")
sharing three salient tokens of eight; the sentence-pair detector cannot
see them and the prompt's restatement ban is the only lever.

Other shows: no post-merge episode existed yet at this readout (every
other show ran its scheduled slot before the 12:53 UTC merge), so the
network verdict waits for the 2026-09-06 slate. The re-run finding that
transfers now is the gate: every English news show copied 27–78% on its
last four episodes, so the threshold is set network-wide rather than for
Tesla alone.
