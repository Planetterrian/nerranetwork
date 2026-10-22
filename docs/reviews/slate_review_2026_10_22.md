# Slate review — Oct 22 2026

Operator ask: review how the shows and workflows did with the last 24 hours of
changes (the Oct 21 slate fixes and the story catalog, PRs #1509-#1513), and
keep improving them. Window: Oct 21 10:45 to Oct 22 12:30 UTC. Every finding
that led to a change was checked against the committed digest, script,
transcript, chapters or run log before anything was edited.

Register: `slate-2026-10-22`. Guards: `tests/test_slate_2026_10_22.py`, plus
new classes in `tests/test_story_catalog_2026_10_21.py` and
`tests/test_mit_benchmark_integrity.py`.

## 1. What ran

| Item | Result |
|---|---|
| Scheduled shows | 17 published (16 public + the North America desk for its member) |
| Regional desks | Four skipped as designed (`no_member_demand`) |
| Nerra Daily | Built 06:49 ET |
| Multilingual | Every show swept except SpaceX: its job died twice in `setup-python` (apt install, exit 124), so SpaceX has no FR/RU track or dub today |
| Story catalog | Backfill filled 2,536 episodes, 18,541 items, 15,974 stories, 6,235 claims, 12 corrections. **Every runtime write from a show run failed**, so `catalog_articles` holds 0 rows |

## 2. Scoring the Oct 21 changes

- **Times, chapters at 0 s, dropped-cluster rejection, shared-link dedupe:**
  held on every episode where they applied. No "A M in the afternoon"
  readings, and every first chapter starts at 0.
- **The aired tracker** recorded what aired, but it missed the lead story on
  every show that writes it as a prose section. On Models & Agents, AI Chips
  and Prediction Markets that is `### Top Story`; on MAB it is
  `### The Big Story`. Deep dives were missed too. The recurrence notes
  therefore could not see that the story the hook sold had already aired.
  Fixed (§3.2).
- **The story catalog runtime write** failed on every run with HTTP 400 (code
  23502, NOT NULL). PostgREST runs an upsert as an INSERT first, so the
  partial row that set the episode's links was rejected before the merge.
  Because the episode write sat in the same `try` as the article write, the
  article write was never reached either. Fixed (§3.1); the day's fetched
  articles are lost.

## 3. Fixed in code

1. **Catalog runtime writes** (`engine/catalog.py`). The episode's links are
   now written with a PATCH, and the article write runs on its own, so one
   failed write never drops another. A partial failure returns
   `status: partial` with its errors instead of failing silently.
2. **The aired record keeps a story told in a prose section**
   (`engine/aired_items.py`, new kind `section`). The lead section takes the
   hook as its title, and a `Name: subtitle` section takes its subtitle. A
   section is not counted when it schedules, lists or argues about another
   section's story (`_STRUCTURAL_SECTIONS`), when it is under 40 words, or
   when it is a bullet list. `AIRED_SCHEMA` 3 makes every tracker re-read its
   committed digests once.
3. **Modern Investing's record is averaged per trade, never compounded**
   (`shows/hooks/modern_investing.py`). Every position is its own parallel
   $1,000 trade, so compounding 34 of them read as a −33% portfolio. The
   honest figure is −0.97 points of alpha per trade, or −$328.50 in total.
   The prompt now says "average per trade" and states the dollar total. The
   compounded figure stays in the summary as `era_compounded_alpha_pct` for
   the performance page. The reviewed trade is labelled by when it closed:
   "Earlier …, N later trades have closed since" replaces "Last …" whenever a
   newer trade has closed. ⚠️ AUDIO (the spoken record).
4. **Model names are not ranges** (`assets/pronunciation.py`).
   A model name like "Llama-3.1-8B" was read as a number range. A digit group
   glued to a letter, or a decimal, no longer reads as a range. A sentence's
   closing period after a range is kept.
5. **SpaceX's pre-market quote** (`shows/hooks/spacex.py`). Ep136-138 said
   "closed higher" in the body and "is trading at" in the closing for the
   same price. At 05:50 ET, `fast_info`'s last price is the prior session's
   close and its `previous_close` is the session before that, so
   `_no_trade_yet` cannot see it. Outside the regular session, a last price
   equal to history's last close is now spoken as that close.
6. **13F holdings filings are not news** (`engine/utils.py`). SpaceX Ep138
   aired three MarketBeat "Shares Bought by … LLC" notices. Three title
   shapes now drop them network-wide. Berkshire, SoftBank and ordinary share
   news still pass.
7. **Article dating** (`engine/article_dates.py`, `engine/url_utils.py`). An
   Elsevier PII URL carries its year (`S0012821X21…` is 2021), so a
   years-old paper resurfaced by an index can no longer be dated today.
   Parentheses in URLs are percent-encoded, because a bare `)` cut every
   markdown link around a PII.
8. **The map sentence carries no chapter** (`engine/chapters.py`). Three
   phrasings were added to the map cues: "From there it's …", "… are the run
   from here" and "… come next". These map shapes on MAB, FF and SpaceX had
   titled a chapter at the open.
9. **Top World chapter titles lose their item number**
   (`engine/grok_imagine.py`). Top World writes `**1. Title: Outlet**`, with
   the number inside the bold, so every chapter title and scene prompt opened
   with "1.". A headline that opens on a figure ("1.5 million …") keeps it.
10. **`setup-python` apt install** retries up to four 300 s attempts within
    900 s, instead of one 600 s wait that killed the job. That single wait is
    what lost SpaceX's translations today.

## 4. Read and not changed

- **Peptides' map named five stories.** The spec allows recurring segments
  after the stories, so trimming in code cannot tell a story from a segment
  without risking the spoken text. Noted as a model slip.
- **MAG 7 "1.25 million … 999"** (daily-audit flag) is correct speech: 999 is
  the UK emergency number.
- **For a later pass:**
  - Models & Agents' Also Today ran 27 arXiv one-liners.
  - Whisper's low-probability standalone tokens ("Georgia.", p = 0.003)
    survive into captions; `drop_echo_words` only drops repeats.
  - FF's Deep Dive was built from a Reddit self-post.
  - Nerra Daily handoffs repeat the next segment's headline.
  - The Board lists one question once per venue.

## 5. Operator

- Re-dispatch the SpaceX multilingual sweep after this merges.
- Dispatch "Story Catalog" with `full: true` after this merges. The story ids
  change with the reader; the articles table starts filling from the next
  show runs.
- ⚠️ A/B-listen the first Modern Investing episode after this merges (the
  record wording).
