# The story catalog

Built on Oct 21 2026 from the review in
[`reviews/content_lake_and_story_catalog_2026_10_21.md`](reviews/content_lake_and_story_catalog_2026_10_21.md),
with the catalog placed in the Nerra Voices Supabase project at the operator's
direction.

It answers three questions:
- What did the network tell, item by item?
- Which of those items are the same story, across days and across shows?
- What did each run fetch and not tell?

## Layers

| Layer | Where | What it holds | Rebuilt from |
|---|---|---|---|
| Aired items | `engine/aired_items.py` | The one definition of a story item in a digest: numbered, bold-headed with a link, Omni View `### N) Title`, Also Today; a narrative episode is one `essay` | the digest |
| Content tracker | `digests/<show>/<slug>_content_tracker.json` | 45 days of what each show **aired** (`headlines`, `urls`) and what its prompt only **listed** (`listed_urls`, blocked for 2 days) | migrates itself once from the committed digests (`aired_schema: 2`) |
| Story ids | `engine/story_catalog.py` | `StoryAssigner`: same story = shared salient words, ignoring words common to the network or to the item's own show, with a core check against drift | deterministic, canonical order |
| Content lake | `data/content_lake.db` (SQLite, gitignored) | episodes, plus an `items` table with story ids and full-text search | `scripts/backfill_content_lake.py` in every CI job |
| Story catalog | Supabase `nerra-voices`, `catalog_*` tables | episodes, items, stories, claims, corrections, and **every article a run fetched** | everything but `catalog_articles` from the lake (`sync_story_catalog.py --full`) |

The committed digests stay the record. Every layer except
`catalog_articles` can be rebuilt from them. Losing `catalog_articles` loses
a measurement, never an episode.

## Rules that bind

1. **Covered means aired.** The tracker, the recurrence notes, the hook gate,
   the "RECENTLY COVERED" list and the lake read only what a digest told.
   - The prompt's other articles are `listed_urls`, kept out of the next
     prompts for `LISTED_URL_BLOCK_DAYS` (2) and nothing else.
   - The 45-day URL block is for aired pages only. It exists so the 2013
     Teslarati page cannot air a third time.
2. **The draft is not the episode.** `run_show` records the first draft
   (`record_aired=False`) for its sections and the listed articles, and
   records what aired only after the final digest is on disk.
3. **One reader of a digest.** A new consumer that needs "the stories this
   episode told" calls `extract_aired_items`. It never writes a fifth
   headline regex.
4. **Story ids are deterministic.** The order is date, then show, then
   episode, then item. A full rebuild gives every past item the same id. Two
   rules keep cross-show merges strict, because a false merge across shows is
   worse than a missed one:
   - a cross-show match needs three shared words;
   - an `essay` is always its own story.
5. **A run never waits on the catalog.**
   - Unconfigured is a logged no-op.
   - The runtime write happens after the audio-first publish and is
     time-boxed.
   - The nightly `Story Catalog` workflow re-copies the last three days from
     the lake, so a failed write heals.
6. **The cross-show block asks for an angle, never silence.** It names only
   today's articles a sibling told in the last two days. A listener who
   follows one show still needs the story.
7. **Books never print a corrected error.**
   - `validate_chapter_corrections` (in `build_epub`) refuses a volume whose
     chapter carries a text correction that has no replacement text, or one
     that was filed but never applied.
   - Fix the digest with `scripts/apply_corrections.py --apply`; never edit
     the EPUB.
   - Audio-only corrections never block, because the audiobook is narrated
     from the digest.

## Uses

### Books

The book compiler reads committed digests, one show per volume. The catalog
adds three things:
- **The corrections gate** above.
- **Themed and year-in-review volumes start from a query.** Run
  `python scripts/catalog_dossier.py --search "<subject>" --since 2026-01-01 --out <file>.md`
  to get every aired item on a subject across all shows, in date order, with
  its sources and the verified claims behind it. This is the material for a
  cross-show anthology or a news-show yearbook ("the lake makes themed
  compilation a query", `product_opportunities_2026_08.md` B6).
  - The compiler still builds from one show's digests.
  - A cross-show volume type is a separate change: it needs per-chapter
    provenance and art.
- **A story's full timeline** for an essay chapter's "what happened next"
  note: `catalog_dossier.py --story <id>` or `--like "<headline>"`.

### Members-only specials

`produce_special.py` writes `prior_coverage.md` beside each episode's dossier:
what the network has already aired on the subject. It is for the operator's
edit. It is never a source and never prompt input, because only pages the
research read are sources.

### Every morning (`api/story_catalog.json`)

- stories several shows told;
- stories told on three or more days;
- retelling share by show;
- each recent correction, with the other episodes that told the same story;
- stories that three or more outlets carried and no show aired
  (`missed_stories`; null when the catalog cannot be read, never 0).

### Ready for

These are named in the product docs, and the catalog holds the data each
needs:
- **Story pages:** one evergreen page per developing story, from
  `catalog_stories` plus `story_timeline`.
- **Beat Chronicle and search API (B2):** `catalog.search` uses the
  `catalog_items.fts` index, and `catalog.story` returns a story's items.
- **Nerra Personal and Nerra Daily repeat notes by story id** instead of
  re-matching headlines (`engine/personal_stories.py` still matches on its
  own).
- **Corrections that follow a story:** flag every episode with the same story
  id for review.
- **Corpus licensing (D1):** a dated, sourced, claim-checked item corpus.

## Not built yet (deliberately)

- **Embeddings.** Word matching misses synonyms: "boards examining a
  combination" and "committees to study a merger" are one story. pgvector
  0.8 is available on the project, and an `embedding` column can be added
  when an embedding provider is chosen. That is a new model call per item,
  so it is the operator's decision.
- **Members-only digests** (`digests/<show>/members/`) are not in the lake.
  The lake feeds public site search.
- **The four story matchers** (recurrence, clusters, digest overlap,
  Personal) still match on their own. The catalog's assigner is a fifth
  that is used only for ids. Consolidating them changes every annotation,
  so it is its own pass.

## Operator

- **First fill:** dispatch Actions "Story Catalog" with `full: true` once this
  is merged. After that, the nightly run at 05:23 UTC keeps it current.
- The migration `supabase/migrations/20261021_story_catalog.sql` was applied
  to `nerra-voices` on Oct 21 2026.
- **Credentials:** `CATALOG_SUPABASE_URL` / `CATALOG_SUPABASE_KEY`, or the
  existing `VOICES_SUPABASE_*` and `X_QUEUE_SUPABASE_*` names, which already
  reach every show run. No new secret is needed.
