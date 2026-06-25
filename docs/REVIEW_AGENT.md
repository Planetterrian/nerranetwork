# Show Review Agent

Automates the iterative quality-review work previously done manually (the
June 2026 Tesla pass #573/#576, Modern Investing pass #574, network-wide
pass #575). A scheduled review job reviews one target per run, writes a review
doc + ledger entry, and opens everything as a **draft PR** for the operator to
approve — preserving the human A/B-listen gate for anything that changes
shipped audio (landmine #17).

> **Runs on Grok-4.3 (June 2026).** The scheduled job used to drive Claude
> Opus 4.8 through the Claude Code GitHub Action (~$6-9/run, ~$1,500-2,000/yr —
> dominated by cache-reads of the 125 KB `CLAUDE.md`, and amplified by the
> daily-audit dispatches). It now runs
> [`scripts/run_show_review.py`](../scripts/run_show_review.py) on Grok-4.3
> (xAI; `GROK_API_KEY`) for ~$0.30/run — a >95% cost cut, no Anthropic spend.
> One deliberate difference from the Claude agent: the Grok script **proposes**
> prompt/audio changes in the PR body (under "⚠️ A/B-listen required — NOT
> applied") rather than auto-editing them, which *strengthens* the landmine #17
> gate. For a deeper, fully-autonomous pass (multi-file root-causing, written
> drift-guard tests), run `/review-show <slug>` manually in a Claude Code
> session — that path still exists and is the occasional, operator-initiated
> escape hatch.

## Moving parts

| File | Role |
|---|---|
| [`.claude/commands/review-show.md`](../.claude/commands/review-show.md) | The playbook — the codified review methodology (evidence sources, P0/P1/P2 classification, hard guardrails, deliverables). This is the file to edit when you want the agent to review differently. |
| [`docs/reviews/review_state.yaml`](reviews/review_state.yaml) | Rotation state: target → last-reviewed date. 13 targets = 12 shows + `network` (cross-cutting review). |
| [`scripts/pick_review_target.py`](../scripts/pick_review_target.py) | Deterministic picker: least-recently-reviewed target, alphabetical tie-break, `--exclude` for in-flight reviews. |
| [`.github/workflows/show-review.yml`](../.github/workflows/show-review.yml) | The scheduler: Thu 07:00 UTC (+ dispatch), runs `scripts/run_show_review.py` on Grok-4.3. |
| [`scripts/run_show_review.py`](../scripts/run_show_review.py) | The Grok-powered runner: gathers context (snapshot + ledger + transcripts), makes one Grok-4.3 call using the playbook as the system prompt, writes the review doc + ledger entry, advances rotation, opens the draft PR. |
| [`docs/reviews/ledger/`](reviews/ledger/) | The agent's memory: per-target ledgers with shipped fixes, deferred backlog, measurable predictions, and operator-rejected `do_not_retry` ideas. Schema in the [README](reviews/ledger/README.md). |
| [`scripts/review_snapshot.py`](../scripts/review_snapshot.py) | Deterministic per-show quality snapshot (script length vs target, cross-episode boilerplate-tic detector, chapter-shape problems, cost/episode, OP3 trend). Run it yourself: `python scripts/review_snapshot.py tesla`. |
| [`scripts/dispatch_quality_reviews.py`](../scripts/dispatch_quality_reviews.py) | Event-driven trigger: the Daily Audit dispatches an out-of-rotation review when a show ships editorial-critical issues (max 1/day; skips shows with an open review PR). |
| [`tests/test_review_agent.py`](../tests/test_review_agent.py) | Drift guards: rotation covers every show, picker semantics, playbook keeps its safety language, ledger schema, snapshot + dispatcher logic, workflow wiring. |

## The recursive loop

What makes this *iterative development* rather than isolated reviews:

1. **Predictions are scored.** Every shipped fix that claims a measurable
   effect gets a ledger `predictions:` entry (metric, baseline, expected).
   The next review of that show starts by scoring them `hit`/`partial`/
   `miss` — a `miss` reopens the problem with a different approach.
2. **Your verdicts are learned.** Before reviewing a show, the agent reads
   closed-unmerged `agent/review-<slug>-*` PRs (rejections) and checks git
   for reverts of prior review commits (failed A/B listens). Both land in
   the ledger's `do_not_retry` list and are never re-proposed without an
   explicit argument that the evidence no longer applies.
3. **Deferred items are a structured backlog**, carried in the ledger and
   re-evaluated every pass instead of being lost in prose.
4. **The playbook improves itself** — on `network` runs the agent
   meta-reviews the ledgers (which finding categories ship vs. get
   rejected) and proposes playbook edits in the same draft PR. The drift
   guards pin the safety language, so it can sharpen its method but cannot
   loosen its leash; your merge gates playbook changes like everything else.
5. **Reviews are event-driven too.** The Daily Audit dispatches an
   out-of-rotation review when a show ships editorial-critical issues —
   review when something breaks, not only when the calendar says so.

## One-time setup (operator)

1. **Install the Claude GitHub App** on `Planetterrian/nerranetwork`
   (https://github.com/apps/claude, or run `/install-github-app` from a
   local Claude Code session). This is what lets the agent's draft PRs
   trigger CI — PRs created with the default `GITHUB_TOKEN` would NOT run
   the test workflow.
2. **Add the `ANTHROPIC_API_KEY` repo secret** (Settings → Secrets and
   variables → Actions). Alternative if you're on a Claude Pro/Max plan:
   run `claude setup-token` locally, store the result as
   `CLAUDE_CODE_OAUTH_TOKEN`, and swap the workflow's `anthropic_api_key:`
   input for `claude_code_oauth_token:`.

Optional secrets (clean no-ops when unset):

- **`GROK_API_KEY`** (already set for the shows): lets the agent regenerate
  a digest in `--test` mode when it edits a prompt, so the PR shows
  before/after *output* excerpts — you read the changed output before
  deciding to merge-and-listen. No TTS, no publish; pennies per use.
- **`NOTIFICATION_WEBHOOK_URL`** (already used by `post_run_summary.py`):
  pings you when a review PR opens.

That's it — everything else is committed to the repo.

## How a run works

1. Cron fires (Tue/Fri 07:00 UTC — after nightly maintenance has refreshed
   `api/dashboard.json` + `api/op3_stats.json`, before the day's shows).
2. The picker chooses the least-recently-reviewed target, skipping any
   target that already has an open `agent/review-<slug>-*` PR.
3. Claude Code runs `/review-show <slug>`: reads CLAUDE.md + prior reviews
   + dashboard/OP3 data + the last ~10 episodes (digests, TTS scripts,
   Whisper transcripts, chapters) + prompts/YAML/hooks/tests, classifies
   findings P0/P1/P2, implements the safe fixes with drift-guard tests,
   runs pytest, and writes `docs/reviews/<slug>_review_<date>.md`.
4. It pushes branch `agent/review-<slug>-<YYYYMMDD>` and opens a draft PR
   titled `[show-review] …` whose body separates plain code fixes from the
   **"⚠️ A/B-listen required"** list (prompt/audio changes).
5. The PR also bumps the target's date in `review_state.yaml`, so the
   rotation advances **only when you merge** — close a bad PR and the show
   stays at the head of the queue.

## Operator review loop (your part)

- Treat the draft PR like the manual passes you used to write yourself:
  skim the review doc first, then the diff.
- Anything under "A/B-listen required": merge, then listen to the next
  1–2 episodes against recent ones before trusting it (landmine #17).
  Revert via git if quality dips — same contract as the manual passes.
- Don't let review PRs pile up: an unmerged PR blocks that show from being
  re-reviewed but other shows keep rotating.

## Forcing / tuning

- **Review a specific show now:** Actions → "Show Review Agent" →
  Run workflow → enter the slug (or `network`). Note: a forced target is
  skipped (with a warning) if it already has an open review PR — close
  that PR first to force a fresh pass.
- **Run it yourself interactively:** open a Claude Code session in the repo
  and type `/review-show tesla` — the same playbook drives both paths, so
  manual and scheduled reviews stay methodologically identical.
- **Cadence:** edit the cron. Two runs/week ≈ every target reviewed every
  ~6–7 weeks; `0 7 * * 1-5` would make it ~2.5 weeks.
- **Model / cost:** `claude_args` in the workflow (`--model`, optionally
  `--max-turns`); `timeout-minutes: 90` caps a runaway run. A full review
  pass is deliberately allowed to be expensive relative to episode
  generation — it's two deep sessions a week, not a per-episode cost.
- **Methodology changes:** edit the playbook. The drift guards in
  `tests/test_review_agent.py` only pin the safety-critical language
  (draft-only, A/B-listen, rotation update, branch naming), so the rest of
  the playbook is freely editable.

## Safety model

The agent is allowed to: edit code/prompts/tests/docs on its own branch,
run pytest, push the branch, open a draft PR.

It is instructed never to: merge or push to `main`, touch R2 paths / RSS
enclosure URLs / legacy flat files / voice settings / the coupled TTS
fields, add phonetic respellings or speech-tag injection, change the
`min_articles_skip` default, post to any external service, or call paid
APIs. The hard backstop is structural, not just prompt-level: review PRs
are drafts on a non-default branch, branch protection on `main` (if
enabled) and your merge click are what actually ship changes.
