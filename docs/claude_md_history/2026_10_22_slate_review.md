# The Oct 22 slate: the catalog writes, lead stories stay in the record (Oct 22 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### The Oct 22 slate: the catalog writes, lead stories stay in the record (Oct 22 2026)

Review [`docs/reviews/slate_review_2026_10_22.md`](docs/reviews/slate_review_2026_10_22.md);
register `slate-2026-10-22`; guards `tests/test_slate_2026_10_22.py`. Rules
that bind:

- **A catalog write that sets only some columns is a PATCH, never an upsert.**
  PostgREST runs an upsert as an INSERT first, so NOT NULL is checked before
  the merge, and every runtime write failed (HTTP 400, 23502). Each write in
  `record_run` stands alone; the articles never ride on another write's
  success.
- **A section told as one prose story is an aired item** (`kind: section`):
  `### Top Story`, `### The Big Story` and every deep dive. The lead section
  is titled by the hook. `_STRUCTURAL_SECTIONS` lists the sections that
  schedule, list or argue about another story, and those are never stories.
  `AIRED_SCHEMA` 3 re-migrates every tracker.
- **MIT's era record is the AVERAGE trade** (parallel $1,000 positions, never
  compounded). It is spoken with its dollar total. A reviewed trade is called
  "earlier" when a newer one has closed.
- **A model name is not a range** (`Llama-3.1-8B`).
- **Outside 09:30-16:00 ET, SpaceX's `fast_info` price equal to history's last
  close is that close.**
- **13F holdings notices never reach a prompt.**
- **An Elsevier PII dates its article; URL parentheses are percent-encoded.**
- **A numbered bold headline loses its number** before it becomes a chapter
  or a scene.
- **`setup-python`'s apt install retries inside 900 s.**

Operator: re-dispatch SpaceX multilingual, then "Story Catalog" `full: true`.
⚠️ AUDIO: MIT's record line.
