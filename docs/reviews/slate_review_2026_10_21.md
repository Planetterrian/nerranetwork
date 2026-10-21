# Slate review — Oct 21 2026

Operator ask: review the shows and workflows of the last 24 hours and say what
would make them better for listeners. Window: Oct 20 10:45 to Oct 21 10:45 UTC.
Three reviewers read every Oct 21 transcript against its script, digest,
chapters and metrics; every finding below that led to a change was re-checked
against the committed files or the run log before anything was edited.

Register: `slate-2026-10-21`. Guards: `tests/test_slate_2026_10_21.py`.

## 1. What ran

| Item | Result |
|---|---|
| Scheduled shows | 16 published, Eastern slots to the minute (04:08 to 06:21 ET) |
| Regional desks | Four skipped as designed (`no_member_demand`); North America produced for its member |
| Nerra Daily Ep062 | 15 segments, nothing missing, built 06:42 ET |
| Spoken-text gate | 16 of 16 pass, no tag leaks |
| Video job | 9 rendered; UC and Planetterrian/FPD long-forms skipped by policy tier |
| Main | green (`Run Tests` on the last merge) |

UC and Models & Agents for Beginners shipped no Short: both sit in the
dead-Shorts weekly-probe tier, so that is the policy working. Two Age of AI
workflow failures in the window (a post-interview cut that ran before its
editorial package existed; the new rehearsal harness) belong to the parallel
Age of AI work and were left to it.

## 2. Fixed in code (no audio change except where marked)

1. **Bare clock times gained an invented "A M"** (`assets/pronunciation.py`
   `replace_times`). AI Chips Ep030 aired "four fifty-three A M in the
   afternoon"; every bare `H:MM` before noon had been read as morning, and
   "11:15 tonight" read "A M tonight". Now a day-part phrase after the time
   ("in the afternoon", "tonight", "local time", a zone) adds nothing, a
   zero-padded 24-hour time keeps its A M, and a bare single-digit hour is
   said plainly. ⚠️ AUDIO on any script with a bare time.
2. **Chapters.** (a) The first chapter now starts at 0 s — it had started on
   the identity line, so the hook played under no chapter (17.6 s on M&A
   Ep210). (b) No chapter after the first starts on the identity line or the
   map sentence: the map names the stories, so headline anchoring put the
   lead chapter on it on six episodes. The line after the identity line is
   treated as a map only when it reads as one (no digit, a sequencing word, a
   list comma): 0 of 187 pre-map lead lines of Oct 10-19 read as maps, 28 of
   30 Oct 20-21 maps do. Replayed on the Oct 21 slate: FF
   10.7 → 21.5 s, MAB 7.3 → 15.5 s, Top World 12.2 → 21.8 s, Prediction
   Markets 10.9 → 23.6 s; every other episode is unchanged. (c) A bold-wrapped
   title (`**# Models & Agents**`) is never an item title — M&A Ep210 shipped a
   chapter named "# Models & Agents".
3. **A structural retry may not drop the story it was asked to fold**
   (`engine.story_clusters.dropped_clusters`, `_cluster_retry_worse`). Tesla
   Ep641's first digest told the Tesla–SpaceX merger committees as two items;
   the retry folded them into nothing and the retold count read 0, so it was
   kept. The day's biggest Tesla story — the lead on SpaceX and MAG 7 — never
   aired on Tesla. A retry that loses a retold story now keeps the original.
   Metric `story_clusters_dropped_by_retry`.
4. **A shared link is not a shared story** (`engine/digest_overlap.py`). The
   shared-URL test counted the URL's own words (https, www, the host, the path)
   as story words whenever a Source sat at the end of a sentence, and a short
   item was a duplicate by link alone. MAG 7 Ep029 dropped its Joel Kaplan item
   from Also Today for citing the same page as the merger item, and the combined
   script still told it — an aired item with no Source behind it. The test now
   reads the items' words without their links, and two titled items whose
   headlines share no subject are never one story by link alone.
5. **Modern Investing gave two start dates for one record.** The NASDAQ line
   said "since this practice record began on March 16"; the record the show
   scores itself on began August 18. The line now says "since the practice
   portfolio opened on March 16, 2026" — what it measures. ⚠️ AUDIO.
6. **The Also Today readout could not see the flagships.** The Oct 19 metrics
   sat inside the opt-in absence filter, and the counter wanted a bold title
   alone on its line, so Planetterrian's, Omni View's and Models & Agents' runs
   read 0. `also_today_items` counts every bold-headed block;
   `story_item_count` counts numbered, bold-headed sourced and Omni View heading
   items; both record on every show.

7. **A date-bound guard** (`tests/test_live_ticker_2026_10_19.py`) pinned its
   clock to Oct 19 and failed on clean main once newer quotes were committed;
   it now renders on the newest committed bar date, like the Oct 20 brand
   guard.

## 3. Prompt changes (⚠️ AUDIO — A/B-listen the first episode of each)

- **The map sentence** (`engine/intros.py`): news shows name at most three
  stories and no length word (the North America desk listed six and called an
  eight-minute episode "the hour"); the two narrative shows get their own map
  that names the parts of the one story and never a segment label (First
  Principles Ep137 invented "a First Principles Spotlight").
- **One outlet, one naming per run** (`_shared/content_discipline.txt`): M&A
  Ep210 named arXiv on ten papers in a row and turned every opener inside out
  to vary it; Planetterrian named Phys.org about ten times. A shared outlet or
  preprint server is named once for the run.
- **"Also today" is never wedged after a subject** ("Dario Amodei also today
  published…", three shows).
- **UC's cold open comes from the sources** — Ep149 opened on a 2009
  radio-collared wolf no source describes — and a hook number keeps its unit
  and period ("24 percent each year" was a one-time drop).
- **Longevity says the evidence level once per intervention**, not on tissue
  studies or every story (about 12 disclaimers in Ep005's seven minutes).
- **Omni View's teaser** is a story's next step, never a fact already told
  (Ep212 teased the Storm Austen warning it had just read in Also Today).
- **Tesla has no Counterpoint when its briefing has no Short Spot**: Ep641
  mapped a Counterpoint and built it by re-telling the Quebec fire ruling.

## 4. Corrections filed (`digests/<show>/corrections.yaml`)

| Episode | What was wrong | Where |
|---|---|---|
| UC Ep149 | 63× compared a year's savings with decades of payments; "24 percent each year" | both |
| First Principles Ep137 | The Apple II needed an RF modulator to use a television | both |
| SpaceX Ep137 | The ship catch does use engines (landing burn); invented tolerances | audio |
| Modern Investing Ep207 | Delta arithmetic (≈75 shares long, not 75 long + 25 short); two start dates | both |
| AI Chips Ep030 | 4:53 p.m., not "A M in the afternoon"; no Tainan item yesterday | audio |
| Fascinating Frontiers Ep229 | NGC 7129 is in Cepheus, not Orion (heading and chapter amended) | digest |

The audio is not re-synthesized: each page carries the correction box and the
next episode's show notes carry the line. Re-synthesis is the operator's call.

## 5. Read and not changed (operator decisions or later passes)

- **Every closing carries three to six asks** (share, rate, YouTube, a sibling
  plug, the site, a page). This is the open "one ask, topical sibling"
  decision held since Oct 10; it is a spoken-closing change.
- **Tesla and SpaceX have carried no Also Today run on any day since it
  shipped**, while 60 articles reach each prompt. Read the corrected metric for
  a week before touching their prompts.
- **Deep dives retell the lead** on Fascinating Frontiers (the magnetar paper
  three times) and Planetterrian (the spheroid story in item 2, the Spotlight
  and the deep dive). The Sep 5 essay-vs-item note was measured and rejected;
  this wants a selection rule, not a filter.
- **Content**: SpaceX's deep dive stated tolerances its digest invented under
  the licensed-knowledge clause; MIT taught covered calls two days running;
  Prediction Markets read 33% of its digest verbatim with long dollar strings;
  AI Chips ran 40% over its promise and leaned on an "X, not Y" frame; SpaceX
  said the stock "finished lower" before the open; North America aired a
  release that Hubbard's same-day freedom had overtaken; Top World's Jackdaw
  chapter starts 38 s late (Whisper wrote "Jack -Daw") and its lead chapter is
  titled "The Ten".
- **SpaceX Ep137's lead item has no title** (one occurrence in October).
