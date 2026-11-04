# Covered means aired, and a story catalog (Oct 21 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Covered means aired, and a story catalog (Oct 21 2026)

Operator-directed (review
[`docs/reviews/content_lake_and_story_catalog_2026_10_21.md`](docs/reviews/content_lake_and_story_catalog_2026_10_21.md);
design [`docs/story_catalog.md`](docs/story_catalog.md); register
`story-catalog-2026-10-21`; guards `tests/test_story_catalog_2026_10_21.py`).
Measured first: the tracker recorded the whole PROMPT list (up to 60
articles) as covered — 63-75% of ALREADY-COVERED notes cited stories that
never aired, about one tracker URL in five had aired, and an unused article
was blocked for 45 days; the lake CI rebuilds held no headlines, so the
cross-show block read "none" on all 23 prompts every day. Rules that bind:
**`engine/aired_items.py` is the one reader of "the stories a digest told"**
(the shapes `story_item_count` counts; a narrative episode is one `essay`) —
the tracker, the lake and the catalog all use it. **The tracker records what
aired**: `record_episode(record_aired=False)` on the first draft records its
sections and the listed articles (`listed_urls`, blocked
`LISTED_URL_BLOCK_DAYS` = 2); the aired stories are recorded once the final
digest is on disk; a pre-Oct-21 tracker migrates itself once from the
committed digests (`migrate_to_aired`, `aired_schema: 2`). **Story ids come
from `engine/story_catalog.py`**, deterministic (date, show, episode, item),
strict across shows (three shared words; network- and show-common words
ignored; a core check stops drift; an essay is its own story); the lake
stores them in an `items` table (`rebuild_story_ids`, `query_items`,
`story_timeline`, `search_items`). **The cross-show block names only today's
articles a sibling told in two days and asks for this show's angle, never
silence** (`engine/cross_show.py`, metric `cross_show_matches`). **The story
catalog is `catalog_*` in the nerra-voices Supabase** (`engine/catalog.py`,
migration applied Oct 21): a show run writes its episode and every article it
fetched after the audio-first publish (`story_catalog` metric; never blocks);
Actions "Story Catalog" (05:23 UTC; `full` for the first fill) re-copies three
days from the lake, prunes unaired articles past 90 days and writes
`api/story_catalog.json` (multi-show and developing stories, retelling by
show, corrections with the other episodes that told the story, and
`missed_stories` — null when unreadable, never 0). **Books never print a
corrected error** (`validate_chapter_corrections` in `build_epub`); themed
material comes from `scripts/catalog_dossier.py`; specials get a
`prior_coverage.md` (never a source). Word matching misses synonyms — embeddings
are the next step and a new model call (operator). ⚠️ AUDIO — the digest input
changes on every news show: A/B-listen Tesla, SpaceX and one desk. Operator:
dispatch "Story Catalog" with `full: true` after merge.
