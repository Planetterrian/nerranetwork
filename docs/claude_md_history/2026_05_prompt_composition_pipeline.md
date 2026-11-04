# Prompt composition + pipeline safety scripts (Phase 1, May 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Prompt composition + pipeline safety scripts (Phase 1, May 2026)

- **Shared prompt snippets.** `engine.generator.load_prompt` resolves
  `<<include: relative/path.txt>>` directives (relative to the including
  prompt's dir, recursive, cycle/depth-guarded) **before** `{placeholder}`
  substitution. Canonical snippets live in `shows/prompts/_shared/`. The
  mechanism is **opt-in**: a prompt with no directive renders byte-for-byte as
  before, so existing prompts are unchanged. Do NOT bulk-rewrite prompts to use
  includes without re-running `test_prompt_fidelity.py` + A/B listening (it
  changes generated output). See `shows/prompts/_shared/README.md`.
- **Fail-loud safety nets** (all *loud-but-non-blocking by default*; pass
  `--strict` to hard-fail in a dedicated guard job):
  - `scripts/backfill_content_lake.py` — evaluates the rebuilt lake and emits a
    GitHub `::error::`/`::warning::` annotation when it's empty/thin (was a
    silent failure mode that broke dedup/recaps/search).
    **July 24 2026 orchestration pass** (drift guards:
    `tests/test_memory_lake_expansion.py::TestLakeOrchestration`): the lake
    ENGINE was healthy (1,200+ episodes, 1.5M words, FTS working) but three
    orchestration bugs hid it. (1) The run-show **finalize job** rebuilt the
    public search index on a fresh checkout WITHOUT backfilling the
    gitignored lake — every episode (~13×/day) committed a zero-episode
    `site/data/search-index.json`, so site search served 0 results most of
    every day (nightly repaired it once; the next morning wiped it again).
    Finalize now backfills before `build_search_index.py`, and the index
    builder additionally REFUSES to overwrite a populated index with an
    empty one (loud `::warning::`, non-blocking). (2) **Nightly built the
    dashboard BEFORE the backfill**, so `api/dashboard.json` reported
    "lake: 0 episodes" every night (the mission-control card showed a
    permanent false empty-lake warning) — steps reordered. (3) Shows that
    don't produce run_show digests (**Age of AI**) never entered the lake;
    the backfill gained a summaries-JSON fallback importer so every
    published episode is searchable. The lake remains a rebuild-from-repo
    cache by design: committed `digests/**` are the durable store, the DB
    is derived — safe to delete, cheap to rebuild (~30 s), reliable for
    future content products via `query_show_range` / `search_content` /
    `query_by_entity`.
  - `scripts/youtube_quota_preflight.py` — sums quota for YouTube-enabled shows
    and annotates when projected over the 10k/day budget (landmine #20). Wired
    as a preflight step in `run-show.yml`.
  - `scripts/post_run_summary.py` — positive heartbeat: composes an all-clear /
    cost / quota / RSS-freshness line from `api/dashboard.json` and POSTs to
    `NOTIFICATION_WEBHOOK_URL` (clean no-op when unset). Wired into the finalize
    job.
  - `scripts/retitle_youtube_videos.py` — repairs transcript-fragment titles on
    ALREADY-PUBLISHED videos. Before the July 18 2026 title bundle, a Short's
    title was the raw opening text of its clip: 11% of Shorts published before
    that date carry a fragment title against 1% after. The pipeline was fixed
    forward; the back catalogue never was, and those videos are still live and
    still the first thing a new viewer sees. Rebuilds the title from the
    episode's DIGEST HEADLINES (the Short's own stored `hook` IS the fragment
    for exactly the videos this repairs, so it can never supply the
    replacement; sibling Shorts take different headlines so one episode does
    not produce four identically-titled clips). **Dry run by default** —
    `--apply` is required to write. Run it from Actions ("Retitle YouTube
    Videos"), not a laptop: the YouTube credentials live there, and a local run
    prints its plan then writes nothing. ~51 quota units per video. 31 fixable
    at last count.
