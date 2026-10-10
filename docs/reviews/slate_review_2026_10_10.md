# Slate review — October 10, 2026: quality of information and delivery

Operator listen: "I didn't like so many stock prices read in MAG 7 and hearing
how many likes a recent X post received. I want high quality information
presented in the most interesting, credible and entertaining way for all
shows."

Scope: the 27 scripts published from Oct 9 15:00 UTC to Oct 10 12:30 UTC
(every English show that ran), read in full by two independent readers, plus a
mechanical sweep of every script and digest since Sep 10 (1,092 files).
Register `listener-noise-2026-10-10`; guards
`tests/test_listener_noise_2026_10_10.py`.

## 1. The two things the operator named

| Problem | Where it aired (Sep 10 – Oct 10) | Cause |
|---|---|---|
| A post's view, like or reply count read aloud, often with the minute it went up | Tesla 8 sentences (three on Ep629 alone: "…with eighteen views", "…with forty seven views", "…with fifty six views"), Models & Agents 1 ("four point one million views"), SpaceX 2 ("over two hundred replies") | The X search tool returns engagement metadata; the fetch model copied it into the post text, and the Tesla digest's "what's generating buzz" Takeover brief made attention look like news. No layer removed it. |
| A run of closing prices | MAG 7 read all seven closes on 3 of its 18 episodes (Ep001, Ep012, Ep015) | The digest's reader-only "### The Tape" reached the script stage; the prompt said never read it, the model read it anyway. |

Neither appears in the Oct 10 scripts by chance of the day, not by design.

**Fix, in code (no audio rule depends on the model obeying):**
`engine/listener_noise.py`, network-wide.
- `strip_engagement_noise` removes engagement-count clauses, the minute a post
  went up (only right after a posting verb — a launch at 2:37 AM is content),
  and sentences that say only that a post was made on X. Applied to the
  digest before the source-integrity gate, to the script, and to every X post
  at fetch (`engine.fetcher._x_post_entry`), whose prompt now asks for the
  post's own words only.
- `strip_price_tape` drops two or more consecutive closing-price sentences
  about different subjects. One price inside a story, the flagships' single
  quote line, and a repeated price are untouched.
- `strip_reader_only_sections` keeps "The Tape" out of the podcast-facing
  digest altogether.

Calibration on 1,092 committed files: every one of the 25 engagement changes is
a true engagement or metadata sentence; the tape filter catches exactly the
three MAG 7 tape reads and nothing else. Three false positives found during
calibration are pinned as tests (a URL containing "views", a livestream time,
"turning to ChatGPT at 2 a.m.").

## 2. Everything else the readers found, verified against the files

Fixed in this pass (all prompt or config, ⚠️ AUDIO — A/B-listen):

1. **Quotas forced filler on air.** Fascinating Frontiers ran exactly 15 items
   on all 9 October days and Planetterrian 15 on 7 of 10 ("ALWAYS pick 15"),
   which put a birthday, a six-month-old Sentinel image and two profiles on
   FF; Tesla ran 17 (12 + 5) every day, so replies in an X thread and blog
   rewrites filled the Takeover. Now ceilings: FF and Planetterrian at most
   12 and include `interesting_first.txt`; Tesla "up to 12" and "up to 5",
   a reply or a reaction is not an item. Both podcast prompts lost "COVER MORE
   STORIES" (they add depth to the stories they have instead). Validator
   floors are unchanged (Top News 5, Space and Science Stories 8).
2. **Reference numbers read as content.** Vancouver read a tip line and a file
   number, Africa & Middle East a ship's TEU and build year, Tesla a patent
   number, Prediction Markets five rows of price, volume and read time. The
   shared content rule now says a phone, file, case, patent or flight number, a
   list of more than three specifications, a volume or the minute a reading was
   taken is spoken only when the story turns on it. The Board speaks the
   question and the price once with the venue; volume and read time are for
   readers.
3. **Rules spoken aloud.** Europe and LatAm ended on "A sign of progress… is not
   in today's reporting. The day had none." — the desk podcast prompt asked for
   that sentence. On a none day the segment is now skipped. Both Sides is
   skipped when its story was already told or one side has no named person or
   body, and the "fact both accept" tail is gone (Top World spoke the same
   tonnage four times).
4. **Specimens copied.** SpaceX's hedge example ("an observer at Starbase
   posted — unverified") became "according to an unverified post on X" three
   times in one episode; FF's tease specimen ("Keep an eye on…"); MIT's
   pro-tip specimen ("What most retail investors don't realize is…"); M&A's
   benchmark decimals. All replaced by shape. M&A now glosses every unfamiliar
   model, benchmark, library or file format on first mention, two benchmark
   numbers per item at most, each with its comparison.
5. **Modern Investing credibility.** Every Quick Hit had a REQUIRED "Action:"
   line; it produced "Add RAMP to a watchlist" for a private company and
   "Trim exposure to pure AI software names" from one X post. The Action is now
   optional, only about a listed security, fund or account type, and only when
   the item's own source gives the reason. The drawdown tone string ("remind
   listeners this is learning") became "state the record as it is… never
   explain the losses away" (the script had called a −21% era record "the
   learning phase rather than a permanent edge").
6. **Headless sentences.** Tesla opened stories on "The permit filing
   signals…" and "The list ranks…" after dropping the headline. The shared
   rule now requires the first sentence to name its subject.
7. **The narrative essays had no person** (Unintended Consequences and First
   Principles named nobody; UC's hook figure "ten thousand wolf-killed reindeer
   annually" never reappeared). Both prompts gained a STORY SPINE: one named
   person through a dated decision, every hook number sourced in the body,
   causes in time order.
8. **The cold-open stakes sentence** ("Twenty-three million residents are the
   people that budget is supposed to protect.") came from "in the same sentence
   or the very next one" in `engine/intros.py`; it now says the same sentence,
   as `hook_shape.txt` already does.
9. **"Pope Leo XIV" aired as "Pope Elio XIV"** on the North America desk:
   "Leo" matched the LEO (low Earth orbit) acronym. LEO and GEO are
   case-sensitive now.
10. **Collingwood padded its digest** (`digest_expand_below_target`), so ~40% of
    Ep003 restated facts. Off.

Also fixed: a data-driven guard that would have turned main red on the next
push (Top World's Saturday single-story edition cites one publisher; the guard
wanted three on every cohort digest).

## 3. Not changed here, for the operator

1. **The spoken AI disclosure on every Patrick show is not true as worded:**
   "This episode used AI voice synthesis of my voice — editorial selection and
   analysis are my own." The site's AI-disclosure page says the digest and
   script are written by a language model, and Mira's line says so too. Both
   readers ranked it the largest credibility exposure on the network. It is a
   statement in the operator's own voice and name, so the wording is the
   operator's call. A wording that stays true: *"This episode was written and
   voiced with AI, using my voice; I choose the sources and set the rules it
   follows."*
   **Operator decision, 2026-10-10: keep the existing line for now.** The
   proposed wording stays on record here; nothing was changed.
2. **The closing block** runs 100–200 words (8–17% of an episode) with four to
   six asks, and the sibling plug is a date rotation with no topical fit (Tesla
   plugged the Central & South America desk; the North America desk plugged
   Collingwood). Proposal: one ask per episode, sibling picked from the
   registry's `related_show`. This touches `engine/network_promo.py`'s
   rotation guards and the Nerra Daily promo-cut anchors, so it wants its own
   pass.
3. **The script model is the biggest lever on delivery.** Script-to-digest
   verbatim on Oct 10: Planetterrian 77%, UC 71%, First Principles 69%,
   Modern Investing 59% (grok-4.3, which reads the brief aloud) against MAB 4%
   and AI Chips 7% (4.6/4.7). SpaceX's 4.6 arm only started streaming on
   Oct 9 and has not yet completed a run; per the model playbook, widen to
   Planetterrian, UC and First Principles once it has.
4. **Same story, several shows, same day** (Taiwan on Omni View and Asia
   Pacific, Russian diesel on Top World and Europe, the Anthropic agent report
   on M&A, MAB and MIT). Nerra Daily splices all of them, so its listener hears
   each twice. `engine/sibling_coverage.py` exists and is wired only for the
   curricula.
5. **Deep dives that re-tell the lead** (Planetterrian's aspen story three
   times; FF's Cosmic Deep Dive was the lead again; M&A's Under the Hood stated
   unsourced figures). Needs a salient-token check against the lead that rides
   the existing structural regeneration.

## 4. The best of the slate, for calibration

- **Africa & Middle East Ep018** — the flydubai co-pilot story has a person, a
  motive, a timeline and a surprise; sentence rhythm varies.
- **SpaceX Ep126's thermal deep dive** — the network's best segment.
- **MAG 7 Ep018's lead** — the Muse vulnerability, specific, with the
  researcher's own test.
- **AI Chips Ep019** — the most credible show (17 of 21 claims verified).
- **MAB Ep192** — the most entertaining script: a voice, a mechanism, a try-it.
