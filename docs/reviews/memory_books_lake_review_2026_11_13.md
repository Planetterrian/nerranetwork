# Memory, books and the content lake — review, Nov 13 2026

Requested by Patrick: review the memory system, the book building system and
the content lake, find what is slow, wasteful, broken or underused, and fix
what can be fixed safely.

**How the three names were read.** "Memory" is the shows' own memory: the
per-show narrative memory (`engine/show_memory.py`, `engine/tesla_memory.py`:
tracked programs, audience signals, recurring themes), plus the repetition
memories beside it (`engine/content_tracker.py`, `engine/frame_memory.py`,
`engine/story_recurrence.py`). "Book building" is the anthology pipeline
(`engine/book_compiler.py`, `scripts/build_book.py`, `build-book.yml`). The
"content lake" is `data/content_lake.db` (`engine/content_lake.py`), the
SQLite store rebuilt from the committed digests on every CI checkout.

**They are connected, so they are one review.** The lake is rebuilt from the
same digests the memory files are mined from; the lake's aired items carry
the story ids that the cross-show block and the story catalog use to stop
repeats; the books read the same digests and their verified claims ledgers.

Everything below marked **measured** was run or read from the committed
record; **inferred** is reasoning from code.

## Findings

### 1. The theme memory fed junk into 21 shows' prompts (measured) — fixed

Every memory-enabled show injected a `RECURRING THEMES (last ~30 days)`
block into BOTH its digest and podcast prompts. The committed
`*_theme_history.json` files show what it said:

| Show | Top "themes" sent to the model |
|---|---|
| Omni View | happened neutral (610), context perspectives (597), nikkei asia (117), read details (112) |
| OV North America | york times (212), globe mail (146) |
| Models & Agents | simon willison (231) |
| Fascinating Frontiers | space astronomy (279) |
| Planetterrian | health discoveries (314), phys researchers (76) |
| Modern Investing | canadian investors (230), investing techniques (224) |
| AI Chips | semiconductor digest (52) — a publisher |

These are section labels, outlet names and show-name fragments. The counts
are all-time (the `lookback_days` argument was never read), so "appeared in
~610 recent episodes" was false on its face. And the block's one
instruction — "consider whether it deserves extra depth or a connection back
to the larger conversation" — is the arc-framing that the memory section's
own rules forbid three paragraphs later. Repetition and repeated framing
were the main findings of this week's Fascinating Frontiers and Omni View
reviews; this block pushed every show the same way every day.

**Fix:** `engine.tesla_memory.THEME_BLOCK_IN_PROMPT = False`; neither memory
module puts the block in a prompt. Mining continues, so an honest windowed
version can return later. It removes ~500 characters of prompt per call on
21 shows. ⚠️ AUDIO: prompt context — A/B-listen one episode on two shows.

### 2. The monthly book build fails after building, every month (measured) — fixed

`Build Book` run 31 (Nov 1, cron) planned two new 60-chapter volumes
(`first_principles_volume2`, episodes 61-120; `unintended_consequences_volume2`,
81-140) with blank chapter titles, then spent **1 h 48 min** on cover art,
chapter art and narration (the UC volume alone: 62 tracks, 7.2 h of audio,
~$6.45 TTS estimate; the audiobook says bare "Chapter 34"), uploaded the
files to R2, and then failed `test_all_current_volumes_have_full_title_coverage`
— which runs BEFORE the commit step. Result: nothing published, the planned
volume files were never committed, and `--plan-preview` today shows both
series "ready", so every 1st of the month would repeat the whole build and
fail again. The test's own docstring says planner-fresh volumes may be
untitled; its assertion disagreed.

**Fix:** in planner mode `build_book.py` builds a volume only when every
chapter has a curated title (`_drop_untitled`, using the new
`engine.book_compiler.untitled_episodes`). An untitled volume is planned,
named in a `::warning::`, costs nothing, and its YAML is committed so the
titles can be written into it. `verify_book_catalog.py --require-all` treats
such a volume as pending, not broken, and the title-coverage test applies to
BUILT volumes. An explicit `--volume` build is never dropped.

**Still needed (Patrick):** 120 curated chapter titles (60 per volume). See
decision B.

### 3. The lake rebuild cost ~43 s on every show run, twice (measured) — fixed

The lake is gitignored, so `scripts/backfill_content_lake.py` rebuilds it on
every show run (before generation) and again in the finalize job, plus the
nightly. Measured locally: **2,918 episodes, 25,410 aired items, 210 MB,
43 s** (the workflow comment said "~5 s for ~50 episodes"). Profile: 8.5 s
in 5,848 separate commits (a connection, an `init_db` and a commit per
episode), ~9 s in case-insensitive topic regexes, 12.5 s assigning story ids,
3.7 s loading show YAML.

**Fix:** one connection and one transaction (`content_lake.bulk_writer`,
`store_episode(conn=)`; a SAVEPOINT per record keeps the old behaviour that
one bad record rolls back alone) and the topic patterns compiled once against
the lowered text. **43 s → 18 s, with every episode, item, story id and FTS
row identical** (compared row by row against the old build). That is ~25 s
off the critical path of every show run (before the digest call) and every
finalize, about 13 times a day each.

Not done: story-id assignment (12 s) could be made faster, but the ids are
shared with the Supabase story catalog and must not change; a speed-up there
needs its own equivalence run.

### 4. Narrative memory statuses are seed text that never updates (measured) — decision

22 of 23 narrative trackers have **never** had a status written
(`last_major_update_episode` is null on every program); only Tesla has (5 of
11). The statuses are evergreen seed sentences ("Flight-test campaign
ongoing at Starbase…") written when each show enabled memory, and the
section tells the model "a status is never contradicted". Today that is
harmless because the text says almost nothing; the risk is the day a seed
sentence goes stale. Meanwhile the automatic "last covered on air" date
works (every tracker updated this week), but on SpaceX all 11 programs read
"last covered 2026-11-12" because the program names appear daily, so it
carries no signal there. About 3.5-4.5 KB of memory text reaches each
prompt. See decision A.

### 5. Other things checked and fine (measured)

- Content trackers prune to 14 days; ~400 KB per show, bounded.
- Theme histories: ~400 KB total; narrative and performance trackers ~90 KB.
- The lake is used: search index, topic hubs, weekly recap segment,
  cross-show block, story dossier, story catalog sync and the dashboard
  all read it.
- Books on sale: both collected editions carry Payhip, audiobook and
  Books2Read links.

## Decisions for Patrick

**A. Narrative memory statuses — Patrick chose (1), shipped Nov 13** (`show_memory.update_statuses_from_ledger`; register `memory-statuses-from-claims-2026-11-13`). A replay of the last 14 ledgers per show writes 39 of 117 programs: a claim must carry two of a program's keywords, because one shared word wrote off-topic facts.

**A. Narrative memory statuses.** (1) Let the run write the status: after
each episode, replace a program's status with one sourced sentence from that
episode's verified claims ledger (no new model call), dated. (2) Drop the
status line and keep only the open questions and the "last covered" date.
(3) Leave as is. Recommendation: (1) — it turns memory into the accuracy tool
its rules describe, and it reuses the ledger the network already trusts.
⚠️ AUDIO either way.

**B. The two volume-2 books.** They need 120 chapter titles. I can draft
them from the episodes for you to edit (titles are curated, never the hook),
or you write them. Until then the monthly run plans and skips them cleanly.
The UC volume-2 narration from Nov 1 sits on R2 under the audio cache; a
titled rebuild re-narrates only the tracks whose text changed.

**C. A windowed theme block.** If you want themes back in prompts: counts
over the last 30 days only, section labels and outlets filtered, and phrased
as "already covered often — do not reframe", not "connect back". Not built.

## Not changed

- No data deleted. Theme histories keep being written.
- Story-id assignment, the Supabase catalog, published books: untouched.
- CLAUDE.md has 38 bytes of headroom under its size guard, so this pass adds
  no lines there; the rules live in this doc and the guards.

Guards: `tests/test_memory_books_lake_2026_11_13.py`,
`tests/test_book_compiler.py::TestPlannerNeverBuildsUntitled`.
Register: `memory-books-lake-2026-11-13`.
