# CI/CD Workflow Review — Efficiency, Reliability, Manageability (June 10, 2026)

Review of all 11 GitHub Actions workflows + 4 composite actions, prompted by
the operator's run-log review. Drift guards: `tests/test_workflow_efficiency.py`.

## The estate (for orientation)

| Workflow | Trigger | Role |
|---|---|---|
| run-show.yml | 12 staggered crons (06:00–11:30 UTC) | The pipeline: one matrix job per show + a finalize job for shared pages |
| daily-audit.yml | 16:15 UTC | Quality review of the day's episodes, missed-episode sweep + auto-retry, GitHub issue |
| nightly-maintenance.yml | 16:45 UTC | Audience stats, performance trackers, dashboard, content lake, gallery/search, heavy pages |
| build-gallery-manifest.yml | dispatch + builder-code pushes | Manual/dev rebuilds (see consolidation below) |
| weekly-newsletter.yml | Sun 14:00 | Weekly synthesis newsletters |
| feed-audit (Sun), source-discovery (monthly), monthly-report, data-retention, buttondown-tag-subscriber, test.yml | various | Periodic upkeep |

## Implemented

### Efficiency
1. **Shallow clones** (`fetch-depth: 0` → `1` in run-show's run + finalize jobs
   and nightly-maintenance). The repo carries 2.2 GB of legacy MP3 history
   (landmine #1); ~13 jobs/day were each cloning the full history for
   pipelines that never read git history. `git pull --rebase` works fine from
   a depth-1 clone. This is the single largest per-run time/bandwidth saving.
2. **Whisper model cache** (`actions/cache` on `~/.cache/huggingface`).
   faster-whisper re-downloaded ~150 MB from Hugging Face unauthenticated on
   every episode (the run log shows the rate-limit warning) — an HF hiccup
   degrades transcripts → captions → Shorts. The model is pinned, so a static
   key is safe.
3. **Gallery-manifest consolidation**: `build-gallery-manifest.yml`'s
   `workflow_run` trigger spun up a fresh runner (checkout + pip install)
   after EVERY Run Podcast Show completion (~13/day) to run one script.
   The run-show **finalize** job now rebuilds the manifest on the runner it
   already has (R2 read creds added to its env); nightly remains the safety
   rebuild; the standalone workflow keeps dispatch + builder-code-push
   triggers for development.

### Reliability
4. **Smoke suite extended** with the June 2026 drift guards
   (`test_chapters`, `test_tesla_quality_pass`, `test_four_show_quality_pass`,
   `test_russian_shows_quality_pass`) — the guards that pin the
   listener-facing fixes now gate every episode, not just PR CI.
5. **@TeslaAIBot removed from Tesla's X accounts** — the pasted Ep505 log
   shows its fetched "posts" were emoji spam and a slur one-liner, polluting
   the digest prompt (and previously the public content tracker). Also saves
   one Grok x_search call per episode.
6. **Secrets as env vars, not a .env file**: the `Create .env` heredoc + `sed`
   indentation strip was replaced by an `env:` block on the pipeline step —
   same semantics (`load_dotenv` never overrides existing env), no secrets
   written to disk, no shell hack.

### Manageability
7. **Audit targets follow the YAMLs**: `review_episodes.py`'s hardcoded
   `min_tts_words` registry desynced from `llm.min_podcast_words` every time
   a quality pass retargeted a show (the June 9 audit flagged Tesla against
   2200 while the enforced floor was 1600). The reviewer now reads the YAML
   floor and falls back to the registry only if the config can't load.
8. **Content-lake backfill noise**: the script loaded `_defaults.yaml`,
   `_blocked_sources.yaml`, `network_meta.yaml`, etc. as "shows" (the log's
   `Loaded config for ''` lines). Meta YAMLs are now skipped.
9. **Stale comment fix** in daily-audit.yml (claimed a workflow_run trigger
   that had already been removed).

## Reviewed and deliberately NOT changed

- **The 12 staggered crons**: superficially consolidatable into fewer matrix
  triggers, but the stagger is load-bearing — it spreads publish times across
  the morning, keeps per-show concurrency groups simple, and (most
  importantly) limits concurrent `git push origin main` races between matrix
  jobs, which are the source of the `commit_refs` transients (landmine #23).
  Clustering shows into one matrix would *increase* push contention.
- **daily-audit vs nightly-maintenance** stay separate: 30 minutes apart but
  different concerns (paging gate vs heavy idempotent builds), different
  permissions (issues:write vs contents:write), and the audit's auto-retry
  must not share a failure domain with the artifact builds.
- **Per-show requirements files** (`requirements_fascinating_frontiers.txt`,
  `requirements_planetterrian.txt`) look redundant but isolate two shows'
  extra deps from the other ten jobs/day.
- **The finalize job running per workflow-run** (~13/day): it's the shared-
  pages race-avoidance mechanism and now also carries the gallery rebuild —
  each instance is cheap and the alternative (a single deferred build) would
  delay episode pages for hours.
- **pip caching** — already handled by the `setup-python` composite.

## Future candidates (not done; revisit when they hurt)

- **History rewrite to drop the 2.2 GB of legacy MP3 blobs** (landmine #1).
  Follow-up measurement (June 10 2026): HEAD is already clean — zero episode
  MP3s tracked, all enclosures serve from R2, and a shallow CI clone is
  ~115 MB packed — so the rewrite buys GitHub-storage headroom and faster
  *full* clones only, not faster CI. Playbook when scheduled:
  1. Pick a quiet window and disable the 12 run-show crons + nightly/audit
     (a concurrent matrix-job push during the force-push can resurrect the
     old history).
  2. Fresh mirror clone; `git filter-repo --path-glob 'digests/**/*.mp3'
     --path-glob 'digests/*.mp3' --invert-paths` (NEVER touch
     `assets/music/` — the pipeline mixes those at runtime).
  3. Force-push; re-enable crons; everyone re-clones (or
     `git fetch && git reset --hard origin/main` on clean clones).
  4. Accept that commit SHAs referenced in docs/ and old PRs dangle;
     GitHub Support can run a server-side gc to reclaim space sooner.
  Not urgent: with MP3s out of HEAD, growth is text-only
  (~50 MB/month), leaving years of headroom under the 10 GB limit.
  Interim for humans: `git clone --filter=blob:none`.
- **safe-commit-push recovery escape hatch** for nightly + the 8 other
  callers (landmine #23 notes only run-show has the recovery-PR path; the
  other callers' outputs are regenerable, so risk is low).
- **HF_TOKEN secret** for authenticated Hugging Face pulls — moot while the
  cache holds, useful if more Whisper models are ever used.

## Addendum — scheduling punctuality (June 10, 2026)

Shows were publishing hours later than planned: GitHub delivers `schedule`
events best-effort, observed **1–6 h late** (Tesla's `0 11 * * *` cron
started at 13:54 on June 9; daily-audit had already been moved to 16:15 to
cope). Three-layer fix, drift guards in
`tests/test_scheduling_punctuality.py`:

1. **Off-peak cron minutes** — all twelve crons moved from :00/:30 (the
   most contended slots in GitHub's scheduler) to :07/:37. Helps the
   fallback path; does not fix systemic delay by itself.
2. **Exact-time dispatcher** — `workers/scheduler/` (Cloudflare Worker;
   Cron Triggers fire to the minute) dispatches each show via
   `workflow_dispatch` at its intended slot. One trigger
   (`7,37 6-11 * * *`) maps firing time → show, mirroring the gate's
   CRON_MAP (CI fails on drift). **Operator setup required once**: create
   a fine-grained PAT (Actions: write on this repo), `wrangler secret put
   GITHUB_DISPATCH_TOKEN`, `wrangler deploy` — see
   `workers/scheduler/README.md`. Until deployed, behaviour is unchanged.
3. **Same-day duplicate guard** — the gate drops a *scheduled* show when
   today's `Auto-generated: <show> <date>` commit already exists (the
   Worker published on time; the delayed GitHub cron arrives later and
   must no-op). Best-effort: if the API check fails, the show runs — a
   duplicate is annoying, a missing episode is worse. Manual
   `workflow_dispatch` reruns are never blocked.

GitHub crons stay enabled as the fallback: if the Worker is down,
episodes ship late exactly as today — never not at all.
