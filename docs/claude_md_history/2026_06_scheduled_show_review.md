# Scheduled Show Review Agent (June 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Scheduled Show Review Agent (June 2026)

The manual quality-pass workflow (Tesla #573/#576, MIT #574, network #575)
is now automated and reproducible. A scheduled Claude Code agent
([`.github/workflows/show-review.yml`](.github/workflows/show-review.yml),
Tue + Fri 07:00 UTC) reviews ONE target per run — the least-recently-
reviewed of the 13 shows + a cross-cutting `network` target, per
[`docs/reviews/review_state.yaml`](docs/reviews/review_state.yaml) /
`scripts/pick_review_target.py` — following the codified playbook in
[`.claude/commands/review-show.md`](.claude/commands/review-show.md)
(same P0/P1/P2 method as the manual passes; transcripts as ears; hard
guardrails baked in). Output is always a **draft PR** on branch
`agent/review-<slug>-<YYYYMMDD>` with prompt/audio changes called out
under "⚠️ A/B-listen required" — the operator's merge is the ship gate,
so landmine #17 is preserved. New review docs go to `docs/reviews/`;
merging a review PR advances the rotation. Run `/review-show <slug>` in
any Claude Code session for a manual pass with identical methodology.
The loop is **recursive, not just scheduled**: every review appends to a
per-target ledger ([`docs/reviews/ledger/`](docs/reviews/ledger/)) with
measurable `predictions:` the NEXT review must score (`hit`/`partial`/
`miss` — a miss reopens the problem) and a `do_not_retry` list built from
operator verdicts (closed-unmerged review PRs = rejections; git reverts
of review commits = failed A/B listens — never re-proposed). Reviews
start from `scripts/review_snapshot.py <slug>` (deterministic
length/tic/chapter/cost/OP3 numbers — the cross-episode repeated-phrase
detector finds boilerplate tics mechanically). When the agent edits a
prompt and `GROK_API_KEY` is present it regenerates a digest via
`run_show.py <slug> --test` and pastes before/after OUTPUT excerpts into
the PR. `network` runs additionally meta-review the ledgers and may
propose edits to the playbook itself (drift guards pin the safety
language). The Daily Audit also dispatches an out-of-rotation review via
`scripts/dispatch_quality_reviews.py` when a show ships editorial-
critical issues (max 1/day, skips shows with an open review PR;
`daily-audit.yml` gained `actions: write` + `pull-requests: read` for
this). A review PR opening pings `NOTIFICATION_WEBHOOK_URL` (no-op when
unset). Setup + tuning: [`docs/REVIEW_AGENT.md`](docs/REVIEW_AGENT.md).
Drift guards: `tests/test_review_agent.py` (rotation covers every show —
scaffolded new shows must be added to the state file; playbook keeps its
safety language; ledger schema; snapshot + dispatcher logic).

**June 2026 — scheduled job migrated to Grok (cost).** A token-usage review
found the scheduled review agent was the network's largest Anthropic line item:
~$6-9/run of Claude Opus 4.8 (~$1,500-2,000/yr), dominated by cache-reads of
this 125 KB `CLAUDE.md` replayed across a long agentic loop and amplified by the
daily-audit out-of-rotation dispatches (the podcast pipeline itself has zero
Anthropic spend — all Grok). `show-review.yml` now runs
[`scripts/run_show_review.py`](scripts/run_show_review.py) on **Grok-4.3** (xAI;
`GROK_API_KEY`, already used everywhere else) instead of the Claude Code GitHub
Action — ~$0.30/run, a >95% cut; the `ANTHROPIC_API_KEY` secret is no longer
needed by the scheduled job. The runner gathers context (snapshot + ledger +
last ~10 transcripts), makes ONE Grok call with the playbook as its system
prompt, writes the review doc + ledger entry + advances rotation, and opens the
draft PR. One deliberate behavior change: it **proposes** prompt/audio edits in
the PR body under "⚠️ A/B-listen required — NOT applied" rather than auto-editing
them — which *strengthens* landmine #17 (nothing audio-affecting is
auto-committed). The fully-autonomous Claude path stays on demand: run
`/review-show <slug>` manually in a Claude Code session for a deep, multi-file
pass. The ledger writer appends by **text-splice** (never reserializes the
existing file) because three committed ledgers contain unquoted `: ` inside list
items and `safe_dump` line-wrapping can corrupt long plain scalars.
