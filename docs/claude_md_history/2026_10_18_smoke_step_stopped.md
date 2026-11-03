# The smoke step stopped the slate (Oct 18 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### The smoke step stopped the slate (Oct 18 2026)

Slate review; guards `tests/test_slate_2026_10_18.py`. **A per-show smoke
step never runs a test that scans another show's committed content**: one UC
sentence ("Lark et al.,") failed the book-release seam guard, which ran in
every show's smoke step, and every show after UC (SpaceX, AI Chips, MAG 7,
Prediction Markets, Top World, Vancouver, two desks) died before generating —
the guard now exempts ordinary abbreviations and runs only in Run Tests. **An
error event inside a stream is a status error**: xAI's "at capacity" arrives
mid-stream as the bare `openai.APIError`, which no retry set named (FF died);
`_stream_completion` raises it as `RateLimitError` (capacity language) or
`InternalServerError`. **Nerra Daily wakes after a failed show run too** —
every trigger had been skipped and nothing built the edition. **A story
cluster is anchored on its lead**: single-link chaining folded six unrelated
Tesla stories into one item (`engine/story_clusters.py`). **The hook gate
matches at 4 shared words with generic words ignored**
(`RecurrenceIndex.hook_match`, `HOOK_GENERIC`; it had fired on 10 of 20 SpaceX
days and on M&A's {agent, coding, models, real}). **MIT's stop parser reads
spelled numbers and "stop N% below entry"** (5 → 21 of the last 45 picks; it
is read at pick time, so no recorded trade changes). **The run budget is 70
min under an 80-min hard kill** — the audio is pushed first, so the time buys
only the video (the render budget had dropped 5 of 15 long-forms on OV, M&A
and MIT). Milestone notes never repeat the episode number (⚠️ AUDIO on round
episodes). The homepage never calls an earlier day's flagship episode or
edition "this morning's" / "today's". **A killed audio-first checkpoint
leaves no rebase behind**: Top World's checkpoint hit the 300 s timeout inside
`git pull --rebase`, the leftover `.git/rebase-merge` failed every later push
attempt as a "conflict", and the recovery branch carried the half-replayed tree
(a workflow change), which GitHub refused — the episode was lost from git.
`_checkpoint_publish` now kills the whole process group, `_restore_after_checkpoint`
aborts the rebase and un-commits the unpushed checkpoint, and
`push_show_artifacts.sh` clears a stale rebase before each attempt. Operator: the scheduler Worker still
fires on the Oct 9 UTC table (runs at :01/:16/:31/:46) — `wrangler deploy` in
`workers/scheduler`.
