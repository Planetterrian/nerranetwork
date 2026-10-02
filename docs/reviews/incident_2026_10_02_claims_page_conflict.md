# Incident — 2026-10-02: the network claims page diverted eleven episodes

**Severity:** P0 (episodes not on main; duplicate production; a four-show
Nerra Daily). **Cause:** #1330 (merged 2026-10-01 22:47 UTC). **Fix:**
#1345, commit "P0: the per-show regen never writes the network
claims.html". **Owner of the lesson:** the review playbook's hard
guardrails (a per-show regeneration never writes a page every show run
rewrites) and `scripts/push_show_artifacts.sh` `is_regenerable`.

## What happened

`generate_html.py --show <slug>`, which every `Run Podcast Show` job runs
before its commit, rendered the network-wide `claims.html` from #1330 on.
Two show runs minutes apart each carried a different copy; the commit
step's `git pull --rebase` could not three-way merge generated HTML
(`UNRESOLVABLE conflict: claims.html` on all four attempts), and the run
took landmine #23's escape hatch — a recovery branch and a draft PR —
instead of landing on main.

Recovery branches created between 06:46 and 16:30 UTC: `omni_view_europe`,
`omni_view` (07:01 dispatch), `models_agents_beginners`, `modern_investing`,
`tesla` (08:46 dispatch), `spacex` (09:16 dispatch), `omni_view_north_america`
(twice), `fascinating_frontiers`, `tesla` again (the 14:xx cron fallback)
and one multilingual sweep.

## Consequences

1. **Nerra Daily Ep043 shipped at 39 minutes with four segments.** The
   12:00 UTC force hour fired with Models & Agents, Planetterrian, UC and
   First Principles on main and nothing else of the nine expected; a
   built edition cannot grow.
2. **Duplicate production.** GitHub's late `schedule` fallback re-ran the
   shows whose morning commit never landed (the duplicate guard looks for
   the day's `Auto-generated:` commit on main). Omni View (14:30), MAB
   (14:58), MIT (15:24) and SpaceX (16:27) were produced twice: a second
   digest, a second TTS, a second R2 upload under the SAME key (the first
   audio is overwritten), and second YouTube and X posts.
3. **Tesla Ep623 is on main nowhere.** Both Tesla runs went to recovery
   branches; the feed on main has no 2026-10-02 episode.

### Duplicate YouTube uploads (video ids; first run → second run)

| Show | Ep | First run (recovery branch) | Second run (main) |
|---|---|---|---|
| SpaceX Daily | 118 | long `URusYUpURHA`, short `qgEj0DZdGCY` | long `MCinhcrFzcE`, short `NE8yIptD0Ag` |
| Omni View | 193 | long `wd1GI1PUaL4` | long `8nZqwM2a9-Q` |
| Modern Investing | 188 | long `A-IFmrF-hjI`, short `zous257_wlc` | long `5_ZohSj5SvM`, short `vt7WYCwkBD0` |
| MAB | 184 | long `0pidkDS1Jho` | long `cNg5zjZvUZk` |
| Tesla | 623 | long `jhzRkuROmO8`, short `VvqCtm_62N0` (08:46 run) | long `hCCjB85spgg`, short `WEx76pLRgho` (14:xx run, recovery branch too) |

## Operator items

- **Merge the later Tesla recovery PR** (`recovery/tesla-37023929366-1790955816`)
  so Ep623 reaches the feed; its RSS entry points at the R2 key the second
  run uploaded. Close the earlier Tesla recovery PR.
- **Close, do not merge, the other recovery PRs** (SpaceX, Omni View, MIT,
  MAB, the desks, FF): main already carries the same episode numbers from
  the fallback runs, and merging would add duplicate feed GUIDs.
- **YouTube Studio:** one of each pair above is a duplicate upload of the
  same episode number; the first-run videos carry audio that no longer
  matches what the feed serves. Deleting the first-run set is the
  consistent choice; the pipeline cannot do it (no delete path, by design).
- The Nerra Daily Ep043 edition stays as published (the date is the
  idempotency key); the gate change in #1345 is what prevents the shape.

## What binds now

- A per-show regeneration writes only pages that belong to that show.
  Shared pages belong to `--network` (the finalize job, whose commit loop
  keeps origin's copy on conflict), `--static-pages` (nightly) and `--all`.
- A regenerable page goes on `is_regenerable` so a stray conflict picks a
  side instead of diverting the episode.
- The Nerra Daily ready gate no longer ships a four-show edition at the
  force hour (`ready_decision`, 80% floor, 16:00 hard deadline).
