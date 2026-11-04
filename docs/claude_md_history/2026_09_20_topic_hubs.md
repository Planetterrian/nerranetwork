# Sep 20 2026 — /topics/ hubs: engine/topic_hubs.py owns the subject vocabulary

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Sep 20 2026 — `/topics/` hubs: `engine/topic_hubs.py` owns the subject
vocabulary.** The site had 1,952 sitemap URLs and 20 organic sessions in 28
days because 1,880 of those URLs are DATED news articles — the right shape on
the day, useless as a landing page three weeks later. Twelve evergreen hubs
(`topics/<id>.html` + `topics/index.html`, `generate_topic_hub_pages`) answer
the durable query instead. Rules that bind:

- **The vocabulary is CURATED (`picker_tags.topics` from the registry), never
  the search index's auto-mined `topics`** — those put `regulation` on 1,708 of
  1,886 episodes (91%) and `finance` on 1,263, so a hub named for one is a
  keyword artifact. Adding a show to a hub is a registry edit, not a code edit.
- **Episode lists read the COMMITTED `site/data/search-index.json`, never
  `data/content_lake.db`** (gitignored, rebuilt from the repo). A generator on
  the lake would render empty hubs on any checkout that had not backfilled —
  exactly how the public search index shipped zero episodes ~13×/day until July
  2026. A missing or empty index writes **no pages at all**.
- **Every intro is hand-written.** A hub whose prose is assembled from its own
  episode titles is thin content, which ranks worse than no page.
- **A hub under `MIN_EPISODES_FOR_HUB` (12) is not built**, is not in the
  sitemap, and is never linked from a post. `interviews` and `sailing` sit
  below it today and name the page that already serves the subject
  (`/mira.html`, the Offshore North dashboard); they turn themselves on when the
  archive grows. The sitemap lists hubs from `renderable_hubs`, never a glob,
  so a skipped hub can never be advertised as a page that exists.
- **Every blog post links its subjects** (`topic_hubs` in the post context).
  That link is why the hubs can rank; without it they are orphans reachable
  only from the nav. Committed posts pick it up on their next per-show regen,
  per the Sep 3 source-only convention.
- `topics/*.html` is in nightly's add-paths, and the blog `<title>` lead now
  reads `engine.titles.WEB_TITLE_LEAD_MAX` instead of a literal 62. Per-episode
  blog titles were ALREADY shipped (the Sep 3 deferred item) — 25/25 distinct
  on Tesla; `TestTitleLimitHasOneOwner` pins both.
