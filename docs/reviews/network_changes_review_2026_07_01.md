# Three-Week Change Review — June 10 → July 1, 2026

**Scope:** every substantive change merged to `main` in the last three weeks
(~1,800 commits; ~180 substantive after filtering auto-generated episode /
multilingual / shared-pages commits), reviewed against the shipped code,
workflows, git history, live output artifacts, and a full test-suite run
(3,314 passed / 3 skipped / 0 failed at `1937bd37`).

**Major systems shipped in the window:** multilingual translation tracks
(FR/RU/ZH feeds + R2 audio), RU YouTube dubs to @NerraRU + RU Shorts parity,
the six-phase YouTube rollout (200k quota, all 13 shows, LLM-optimized titles,
Grok video clips built → piloted → retired, retention→titles feedback loop),
the push-contention/recovery hardening after three stranding incidents,
the Grok show-review runner + Grok daily health checks, the SpaceX Daily
launch + data dashboards, the brand refresh, and five scheduled show-review
passes (EI, UC, FF ×2, M&A, MAB, FP, PT, SpaceX ×2, Tesla).

**Headline:** the *pipelines* are in good shape — pushes have been clean for
3 days, tests are green, and no landmine regressed on the audio side. The
systemic problem is that **almost every alerting / feedback loop built in the
window is silently dead**: recovery-PR alerting never fires, the review agent
has been piling unmerged branches with its proposals discarded, the daily
health check writes a file nobody commits or reads, and the analytics loop
can't see the new multilingual surface. Everything failed *quiet*. This PR
revives those loops and fixes the highest-value correctness gaps; the rest is
catalogued below with owners.

---

## P0 — dead safety loops (fixed in this PR where code-side)

### 1. Stranded-episode alerting never fires
`scripts/create_recovery_pr.sh` reads `NOTIFICATION_WEBHOOK_URL`, but the
run-show "Commit and push output" step never passed that secret into its env —
and since the script deliberately exits 0 ("data preserved"), the job goes
green and the `failure()`-gated notify step never runs. Separately,
`gh pr create` is blocked org-side ("GitHub Actions is not permitted to create
or approve pull requests" — verified: **zero** recovery or agent-review PRs
exist, only orphan branches). Net effect: a stranded episode today = green
job, orphan branch, no PR, no page — the exact silent mode the June 28 fixes
were meant to end. Eleven orphan `recovery/*` branches sit on origin.

**Fixed here:** the secret is now passed to the commit step (and to the
pipeline step — `run_show.py:_alert_webhook`'s newsletter-failure alert had
the same missing-env bug, meaning a repeat of the June 19–28 Buttondown
9-day outage would again be silent). Drift guards added.
**Operator required:** flip *Settings → Actions → General → "Allow GitHub
Actions to create and approve pull requests"* — this single toggle unblocks
recovery PRs AND the review-agent loop. Confirm the `NOTIFICATION_WEBHOOK_URL`
secret is actually set. Triage/delete the 11 orphan `recovery/*` branches
(the two June-25 ones — models_agents, tesla — are probably *duplicates* of
episodes later re-run, see P1-4; the June 27/28 ones were merged by hand).

### 2. Show-review loop silently degraded since the Grok migration
The Grok runner works — it produced five reviews since June 26 — but every
terminal step depends on the blocked `gh pr create`: five orphan
`agent/review-*` branches (FF June 26/27/30 + July 1, env_intel June 29),
**no PRs**, rotation state frozen on main since June 25, and the PR body —
the only copy of the proposed A/B prompt edits — was written to a temp file
and unlinked in `finally`, so five runs' proposals are **gone**. Worse, both
the rotation picker and the daily-audit dispatcher dedupe on *open PRs*, so
Fascinating Frontiers was re-reviewed four times in six days.

**Fixed here:** dedupe is branch-aware (an existing `agent/review-<slug>-*`
branch counts as in-flight); the PR body is committed into the review branch
(`docs/reviews/pending/`) *before* attempting the PR so proposals survive;
`gh` failure now fires the webhook with the branch name.
**Operator required:** same Actions setting as above; then triage the five
stale review branches (keep the newest FF one, review its pending proposals).

### 3. "Grok Tier 1 daily health checks" — the loop was dead on arrival
`nightly-maintenance.yml` runs `scripts/grok_show_check.py --out
api/daily-show-health.json` every night, but the safe-commit-push
`add-paths` list omitted the file — generated and discarded with the runner
since June 25 (last committed June 24). Zero consumers read it. The promised
escalation ("score >0.6 triggers weekly Claude deep-dive") was never
implemented — scores print to stderr and the script exits 0. It also can't
catch the incident class that motivated it (a stranded episode produces no
`_tts.txt` in the checkout → no finding at all), flags the **correct**
spelling "Hassabis" as a garble (the garble was "Hah-sah-biss"), and has an
unreachable word-count branch. It's also named "Grok" but makes no LLM call.

**Fixed here:** the output file is committed nightly; the Hassabis pattern
and dead branch are fixed; escalation now POSTs to `NOTIFICATION_WEBHOOK_URL`
when a show crosses the threshold.
**Deferred (operator decision):** whether this layer should exist at all vs
folding its checks into daily-audit, and adding the check that would actually
catch strandings ("expected show missing from main today").

---

## P1 — correctness / money / reliability (fixed in this PR unless noted)

### 4. Stranded episode + audit retry = duplicate public YouTube videos
The duplicate guard and in-pipeline re-check only look at `main`; a stranded
episode is invisible to them, and `dispatch_audit_retries.py` re-dispatches
"missed" shows via `workflow_dispatch`, which bypasses the re-check by
design. Verified this already happened June 25: recovery branches hold
10:38/11:47 UTC episode commits for models_agents/tesla while main has
*second* same-day runs from 12:45/13:22 — and uploads precede the commit in
run_show.py, so both shows most likely shipped duplicate YouTube videos that
day. **Fixed here:** the audit retry now skips (and alerts on) shows with a
same-day `recovery/<show>-*` branch — a stranded episode needs a merge, not a
re-run.

### 5. Latent re-trigger of the June 28 mass-stranding
The June 28 incident (7 Sunday recaps stranded at once) was self-inflicted:
the June 27 aggregate-exclusion fix left regenerated aggregate files dirty and
every rebase aborted. The follow-up fix (`git checkout HEAD -- blog.rss
network.rss blog/index.html`) is correct today but **all-or-nothing**: if any
one path ever stops matching HEAD, the whole restore silently no-ops
(verified experimentally) and the mass-stranding mode returns instantly.
**Fixed here:** per-file restores. Note: the first real Sunday-load test of
the June 28 fix is **July 5** — watch for recovery branches that morning.

### 6. Multilingual sweep churn: 764 pure-churn commits in 16 days
Every language-feed rebuild stamps a fresh `<lastBuildDate>`, so every sweep
commits a 1-line diff per show (~35–42 commits/day; only ~7 carry content).
The workflow also fires on completion of *every* show's run (including the 6
non-multilingual shows) and fans out to all 7 multilingual shows every time
(~2–3 wasted CI-hours/day), and the noise commits add push-retry contention
against episode pushes (landmine #23 class). **No duplicate LLM/TTS spend in
steady state** — the skip-if-recorded logic works. **Fixed here:** feed writes
are skipped when content is unchanged modulo `lastBuildDate`; the
`workflow_run` fan-out is scoped to the triggering show (crons remain the
catch-all sweep).

### 7. RU-dub duplicate-upload risk on lost push
The only dedupe record for @NerraRU uploads is a git-committed index, and the
multilingual workflow's push loop **discards the commit and exits 0** after 8
failed attempts ("next sweep will retry (idempotent)" — untrue for uploads:
the videos are already public; the next sweep re-uploads them as duplicates
and re-pays translation). Same landmine-#23 transient class run-show already
hardened against. **Fixed here:** push exhaustion now takes the
recovery-PR escape hatch instead of dropping the index; a failed Short is now
recorded durably in the index (`_already_done` checked `kind == "long"` only,
so a Short failure was invisible forever). A true short-only retry needs a
skip-long path in `engine/ru_dub.py` — deferred, noted in-code.

### 8. Latent per-sweep LLM respend
In `engine/multilingual.py` the translation LLM call ran *before* the
`english_url` check, and `rejected` validation outcomes recorded nothing — so
an episode with no audio URL or a persistently-failing ZH validation would
pay 1–2 full-script translation calls on every sweep (~6/day) while inside
the `--latest 3` window. Not currently firing (verified), but ZH rejection is
a designed-for failure mode. **Fixed here:** check reordered; rejections are
recorded with an attempt cap.

### 9. Language feeds bypass OP3 — the new surface is invisible to analytics
EN enclosures are wrapped with the OP3 prefix; FR/RU/ZH feeds emitted raw R2
URLs, so every translated-track play is uncounted in the dashboard, popular
episodes, and performance trackers — exactly the surface this quarter's work
created. **Fixed here** (enclosure URLs change once; GUIDs are stable so
clients won't duplicate episodes — the feeds are young, do it now).

### 10. RU-channel quota accounting misses the dubs entirely
`estimate_network_daily_units` buckets by `youtube.channel`; the 4
`ru_dub_enabled` shows are `channel: en`, so their ~13.4k units/day of
@NerraRU uploads are invisible to preflight (which reports 7.6k/day for a
channel actually doing ~21k on even days). The RU channel's real granted
quota is still an open operator task (landmine #20). **Fixed here:** dub
uploads count into the `ru` bucket + drift guard.

### 11. Topic-queue runway treadmill — CI red July 2 without action
The runway floor test runs in the PR-blocking suite with `-x`; First
Principles hits 2.86 wk (< 3.0 floor) with tomorrow's episode, blocking all
PRs — the third manual restock in six days. Unintended Consequences runs 7
days/week but the test models 5/wk, understating burn (breach ~July 4).
**Fixed here:** both queues restocked (preserving the alternation/editorial
format), UC's `per_week` corrected. **Deferred (operator):** the durable fix —
a scheduled restock-by-draft-PR job or a pre-floor webhook alert instead of
red CI on unrelated PRs — is an editorial-process call.

### 12. Landmine #1 regression: 219 end-card PNGs (78.5 MB) tracked, ~140 MB/month
`.gitignore` covers youtube_tmp mp4/jpg/srt/ass but not `*.png`; `git add -A
digests/` sweeps in every episode's end-card PNG (79 added in the last 7 days
alone since the June 26 all-shows rollout). Nothing consumes them from git —
the card is composited at run time and burned into the Short. **Fixed here:**
ignored + untracked + drift guard (same pattern as the June 25 video-clip
untracking, commit `76779bac`).

### 13. "Model Why" ships in published blog transcripts
`WORD_PRONUNCIATIONS` still respells `Model 3 → Model Three` / `Model Y →
Model Why` at script-save time, so they flow into `_tts.txt` → the published
blog (tesla ep528: "Model Why" ×9). Same class as the June 21 `koo-dah` leak.
**Fixed here:** moved to `shows/pronunciation_map.yaml` (the audio-only layer)
— TTS input is byte-identical, transcripts get real product names. Spot-check
audio anyway per landmine #17 convention.
**Deferred (durable fix, already on the books):** blog/RSS transcripts still
source from post-pronunciation `_tts.txt`, so the 147 letter-spellings
("T S L A", "A I", `SaaS→"sass"`, `mRNA→"messenger R N A"`, …) all remain
reader-visible. Sourcing transcripts from pre-pronunciation or Whisper text
closes the whole class at once.

### 14. A/B title candidates were never persisted
`youtube_title` / `youtube_title_variants` were set on the run result but
recorded nowhere — the operator task "enable Studio Test & Compare, the
runner stashes 3 candidates" (landmine #20) was impossible to perform from
repo state. **Fixed here:** recorded via `record_youtube_outcomes` into the
committed per-episode metrics.

### 15. Feedback loop mixes RU-dub retention into EN title hints
The analytics fetcher merges `youtube_videos.ru.json` rows into the same
per-show stats without a channel field, so `_build_hint` could quote Russian
dub titles as "highest-retention titles" inside the EN title prompt. Loop is
still dormant (little data), so zero blast radius today. **Fixed here:**
channel propagated; hints are EN-only.

### 16. daily-audit artifacts have never been committed
The "Persist Audit Artifacts" step does a bare `git push origin main ||
echo non-blocking` from a job-start checkout — always non-fast-forward on
this push-busy repo; `api/daily-review.json` has zero commits ever.
**Fixed here:** uses the `safe-commit-push` composite like every other
workflow.

### 17. Stale multilingual defaults + un-gated ZH
`_defaults.yaml` shipped `multilingual: enabled: true, auto: true,
languages: [fr, ru, es, zh]` — any newly scaffolded show silently inherits
auto-on all-four-languages (this already bit env_intel, June 23), and the
workflow passed `--zh-approved` unconditionally for every show. **Fixed
here:** default off (verified resolved config identical for all 13 shows —
every live show already pins its own block; only the scaffold-inherited
default changed), ZH gated per-show via `multilingual.zh_approved`
(tesla/spacex/FF).

---

## P2 — smaller items

**Fixed in this PR:** duplicated echo in `create_recovery_pr.sh` (splice
artifact); dead `newsletter.weekly_prompt_file` key in modern_investing.yaml
(warned on every config load network-wide); stale "hybrid video clips" comment
in `engine/video.py`; `engine/translate.py` `apply_overrides`
docstring/behavior mismatch; stale `optimized_title` comment + title-LLM call
moved below the YouTube credentials check (no more paying for titles in
cred-less runs); CLAUDE.md corrections (Grok clips retired June 29;
Привет, Русский! is Grok Olya, not ElevenLabs; 12→13 shows ×3; new sections
documenting multilingual tracks, RU dubs, and the feedback loop — none of
which were in the operator doc at all).

**Noted, not fixed (with reasons):**
- **Translated tracks skip the broadcast audio chain** — no `normalize_voice`
  EQ, no music, no −16 LUFS loudnorm, while native shows on the same @NerraRU
  channel are fully mastered. Real listener-facing inconsistency on
  Apple/Spotify-facing feeds, but running dubs through the master chain
  **changes shipped audio → landmine #17 A/B-listen gate**. Recommended next
  audio decision for the operator.
- **RU dubs ship static-cover videos** — the dub step reads the checked-out
  gallery manifest, which is rebuilt by a separate workflow after the
  episode; the "later sweep picks up real scenes" comment is defeated by the
  dedupe index (first scene-less upload is final). Fix is easy (fetch
  manifest fresh, or defer dub until scenes exist) but changes publish timing
  — flagging for a deliberate call.
- **RU Shorts smart-start is English-cued** — on RU audio most Shorts will
  fall back to offset 0 (the intro greeting, the least engaging beat).
  Consider RU cue words or a lower threshold once dub Shorts have data.
- **`optimized_title` never reaches Shorts** — plausibly intentional
  (multi-Shorts want per-window headlines); comment corrected, param left.
- **Grok video clip retirement has no drift guard** (the `video_provider`
  retirement got one, `video_clips_enabled` didn't) — cheap to add next pass.
- **Duplicate-guard commit scan reads only 100 commits since midnight** —
  multilingual noise pushed main to ~40+/day; headroom is shrinking. The
  churn fix in this PR relieves it; paginate if daily volume grows again.
- **Date-bomb tests:** `test_modern_investing_hooks.py` hardcodes
  `{today.year}-02-10`/`-03-15` trades — future-dated during Jan–Mar; rewrite
  relative before the New Year. `test_content_lake.py` fixtures pinned to
  2026 — flag for the December pass.
- **`channel_i18n.json` leftovers** for 4 multilingual-disabled shows —
  harmless.
- **Feed-audit JSONs accumulate** (14 so far) — confirm `data-retention.yml`
  covers them.
- **Tesla still opens "Tesla Shorts Time Daily"** in Ep527/528 `_tts.txt`
  despite the June 20 normalizer fix claiming otherwise — and the FR/RU
  translations propagate it. Hand to the next Tesla review cycle (the
  rotation will catch it once P0-2 unblocks).

---

## Operator checklist (nothing here is doable from code)

1. **Flip the Actions setting**: Settings → Actions → General → *Allow GitHub
   Actions to create and approve pull requests*. Single highest-leverage
   action — revives recovery PRs and the entire review-agent loop.
2. Confirm the `NOTIFICATION_WEBHOOK_URL` secret is set (all the alerting
   revived in this PR posts there).
3. Triage the 11 `recovery/*` and 5 `agent/review-*` orphan branches
   (June 25 recovery branches are likely duplicate episodes to discard; keep
   the newest FF review branch and read its recovered proposals).
4. Confirm the @NerraRU channel's real granted quota (landmine #20 open item)
   — preflight now counts dub uploads against it.
5. Watch Sunday **July 5** (first full-load test of the June 28 stranding
   fix) for recovery branches.
6. Decide: run translated tracks through the mastering chain (A/B-listen
   gate); keep-or-fold the daily health check layer; automate topic-queue
   restocks.
7. Confirm the Buttondown account is re-enabled post the June 19–28
   suspension (the code carries no signal either way).

## Scorecard for the three weeks

What went well: the stranding root causes were each correctly diagnosed and
fixed within a day; the Grok review-runner migration cut ~95% of review cost
and its output quality held; the YouTube rollout's staged phases + the fast
retreat on Grok Video (disabled within 6 days of the pilot when the economics
failed) were disciplined; landmine #17 was respected everywhere (no
un-gated audio changes found); the test suite stayed green throughout.

What to change: **every new loop needs its "does the output land anywhere?"
check on day one** — four separate systems this window (recovery alerting,
review PRs, health-check output, audit artifacts) shipped with a terminal
step that silently failed, and all four were only caught by this review.
A cheap standing guard: any workflow step that writes a repo artifact or
calls `gh`/webhook gets a drift test asserting the env/permission it needs,
and the daily audit should assert "yesterday's expected artifacts exist on
main" for every scheduled producer.
