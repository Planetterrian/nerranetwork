# Slate review — Saturday 2026-10-24

Every show due today published or skipped by design, every video rendered, and
nothing failed. The listener-facing problems are in what the episodes say:
one invented figure, two internal contradictions, a pipeline instruction read
on air, and repetition at the close of four shows. Two of the causes are code,
and both are fixed here.

## 1. How the day ran

| | |
|---|---|
| Show runs | 39, all green (19 late GitHub fallback crons dropped by the duplicate guard) |
| Published | 15 public episodes + Omni View North America (members-only) |
| Skipped | Europe, Asia Pacific, Africa & Middle East, LatAm: `no_member_demand`, by design |
| Spoken-text gate | 15/15 pass |
| Videos | 10/10 handoffs rendered and published |
| Nerra Daily Ep065 | built 10:41 UTC (06:41 ET; release 06:35); 14 segments, `missing_expected` empty, 13/13 handoffs introduce the right show |
| Multilingual | 6 runs, all green |
| Story catalog | written on every run; 174 of 994 of today's articles marked aired |
| X | 7 posted, 6 queued for later slots at 15:30 UTC |
| Main | green; the one red Run Tests was a feature branch, green on its re-run |

The Oct 23 Daily Audit is red because it counted that day's missed episodes
(the xAI billing stop). All of them were re-run the same day.

## 2. Oct 23 fixes, scored

- **Catalog aired flag:** works (219 of 1,314 on Oct 23; 174 of 994 today).
- **Nerra Daily waits for re-runs:** untested today, because nothing re-ran. The edition built at the release.
- **apt fallback, video sweep restart:** untested; the mirror answered and no video run died.

## 3. Fixed in this PR

1. **A roundup article made three Tesla stories one "retold" story** (`engine/story_clusters.py`).
   - The cluster's lead was a Stocktwits roundup. Its teaser touched the merger committees, Optimus output and Japan's V2L adapter. `retold_clusters` matched each member to whichever headline shared three words with it, and "tesla", "2026" and "000" counted.
   - The retry it triggered cut the digest from 1,591 to 1,210 prose words and left the count where it was. It was kept because it was no worse. The script shipped at 1,037 of 1,400 words.
   - This is the third false positive in seven Tesla episodes (Ep638 Korea/Slovakia, part of Ep642, Ep644).
   - Now a cluster is retold only when ONE member's core (the words it shares with the lead) appears in two items. The show's furniture words (≥50% of item headlines, from 8 titles) and bare numbers never count.
   - A retry run only for clusters must lower the count or the original ships (`_cluster_retry_worse(must_improve=)`).
2. **Modern Investing read its own instruction aloud** (`shows/hooks/modern_investing.py`).
   - The Oct 22 trade-review label ended "call it an earlier hold, never the last one". The model copied it into the published digest.
   - The label now states the fact: "Earlier Weekly Hold, closed <date> (3 later trades closed since)".
3. **13F holdings notices by URL** (`engine/utils.NETWORK_EXCLUDE_URL_PATTERNS`).
   - SpaceX aired "Brookstone Capital Management increases its holdings". Neither that headline nor "24,777 Shares in SpaceX $SPCX Purchased by …" matched the Oct 22 title patterns.
   - MarketBeat files every such notice under `/instant-alerts/filing-`: 81 of 81 tracker URLs. Its analyst, price and insider alerts use other prefixes and still pass.
4. **Parentheses inside a URL the model wrote** (`engine.url_utils.encode_url_parens_in_text`, first step of `transform_daily_body`).
   - Planetterrian Ep223's Cell Metabolism link was cut at `(26`. The Oct 22 fix encodes URLs the pipeline fetches, not URLs the model types.
   - 17 committed digests carry such a URL (Wiley DOIs, Lancet and Cell PIIs, Wikipedia).
   - Ep223's digest, summary entry and blog post are repaired here.
5. **A guard read a rolling file** (`tests/test_top_world_sources_2026_09_24.py`). The Top World summaries file keeps 30 episodes, and today's Ep32 rolled Ep2 out of it, so the next main test run would have failed. The summary check now runs only while the entry exists; the digest check still holds the record.

## 4. Corrections filed

| Episode | Where | What |
|---|---|---|
| Fascinating Frontiers Ep232 | both | "thousands of oddly colored remnants": at 3.3% of the Milky Way's ~10 billion white dwarfs it is hundreds of millions; the source says "a lot" |
| First Principles Ep140 | both | Hook "perhaps five dollars of copper" against the episode's own 250 g × $8/kg ≈ $2; a universal motor has a wound armature with a commutator, not squirrel-cage bars |
| Unintended Consequences Ep152 | digest | Agan & Starr's gaps are relative (7% → 43%), not percentage points, and the advantage grew about sixfold, not "more than doubling" |

FF232 and FPD140 need the audio re-synthesized after merge.

## 5. Found and not fixed

**Operator decision: the spoken-open experiment's control costs a digest a day.**
- Omni View regenerated its whole digest for an over-long hook on 7 of 8 days, and Modern Investing on 6 of 8.
- Both are CONTROL shows of `spoken-open-shape-2026-09-22`, so their prompts are held back without the hook-shape include until the readout.
- The Oct 12 read was n=1 per arm, because retention curves are fetched for only five long-form videos a night. The 10-27 re-read will be no larger.
- Ending the experiment and adding the include to the four control prompts would stop the daily regeneration. ⚠️ AUDIO.

**Content, prompt-side (⚠️ AUDIO), recurring:**
- **The close re-tells told stories** on four shows:
  - M&A: OpenAI's offline training is told three times.
  - AI Chips: On the Horizon repeats TSMC and Arm, and the teaser repeats Umatilla.
  - MAG 7: the teaser repeats the Apple court story.
  - Prediction Markets: the teaser restates the lead.
- **The map promises a segment that isn't there:**
  - Tesla's map promises a Counterpoint.
  - AI Chips' map names four stories and ends mid-phrase.
  - Vancouver's map names four stories.
- **Self-narration and hedging on Top World:** "That is background. It is not a call on Sunday", "each a claim, not a verdict". The digest prose is worse ("no outlet in today's file predicts the result").
- **Unsupported additions:**
  - Top World made Khmara "defence minister".
  - SpaceX gave a reason for an upgrade that no source states.
  - Tesla's essay tied LFP cells to the Semi and AI5 to the Semi budget.
  - AI Chips claimed Trainium's "eighty thousand physical cores".
- **A dropped number makes a claim wrong:** MIT's $500/month at 6.9% needs the ~$87,000 principal, which the Listener Challenge then cites unheard.
- **Starlink at "above four hundred kilometres per hour"** on Omni View and Top World reads as a data speed. It is a vehicle-speed limit on terminals.

**Single episodes:**
- MAG 7 aired an orphan sentence ("those bugs") from a digest item with a headline and no body.
- FF's deep dive re-told the lead; the script was 49% digest-verbatim.
- UC ran to 196% of its target.
- Vancouver aired a What's On item that is not in the notes and has no source.

**Unverified:** AI Chips' Micron "$44 billion operating cash flow" in one quarter is sourced only to shattered.io, which also fed Tesla's lead today. Worth an operator check before it is cited again.

**Rejected after measuring:** dropping a bold item headline with nothing under it (MIT's empty "Coinbase vs. PayPal") also removed real lines on 31 committed digests: disclaimers, "Read more (sources):", "Grammar Spotlight". It happened in 3 of 290 October digests.
