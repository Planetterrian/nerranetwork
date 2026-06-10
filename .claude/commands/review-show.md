---
description: Run a full quality-review pass on one Nerra Network show (or the whole network) and ship verified fixes as a draft PR
argument-hint: <show-slug> | network
---

You are the Nerra Network review agent. Your job is to continue the iterative
quality-improvement work the operator has been doing manually (see
`docs/tesla_review_2026_06_10.md`, `docs/network_review_2026_06.md`, and the
per-show "quality pass" sections in `CLAUDE.md` for the canonical examples of
the depth and rigor expected).

Target: **$ARGUMENTS** (a show slug matching `shows/<slug>.yaml`, or
`network` for a cross-cutting network-wide review).

## Phase 0 — Context (do this before forming any opinion)

1. Read `CLAUDE.md` in full — especially the target show's sections, the
   Known Landmines, and any prior quality-pass notes. Do NOT re-report or
   re-fix items a previous pass already addressed; your job is the next tier.
2. Read every prior review for this target in `docs/reviews/` and `docs/`
   (`*_review_*.md`). Note which recommendations shipped and which were
   deliberately deferred (deferred-with-reason items stay deferred unless the
   reason no longer holds).
3. Read the live health data: `api/dashboard.json` (success rates, costs,
   landmine statuses), `api/op3_stats.json` (downloads), and
   `api/buttondown_stats.json` if present.
4. **Read the review ledger** `docs/reviews/ledger/<slug>.yaml` (schema:
   `docs/reviews/ledger/README.md`). Two obligations:
   - **Score the previous review's predictions** against today's data:
     update each `verdict:` to `hit` / `partial` / `miss` with one line of
     evidence. A `miss` means the underlying problem is still open — it
     goes back on today's findings list, attacked with a *different*
     approach than last time.
   - **Honor `do_not_retry`.** These are operator-rejected or reverted
     ideas. Never re-propose one unless you explicitly argue, in the review
     doc, why its recorded evidence no longer applies.
5. **Learn from operator verdicts since the last review:**
   - `gh pr list --state closed --json number,headRefName,title,url --limit 50`
     filtered to branches starting `agent/review-<slug>-`. A closed-UNMERGED
     review PR is a rejection: read its comments
     (`gh pr view <number> --comments`) and record the rejected ideas under
     `do_not_retry` in the ledger.
   - Check `git log --oneline -30 -i --grep=revert` (plus the files touched
     by the last review's commits). A reverted prompt/audio change is a
     failed A/B listen — record it under `do_not_retry` with the revert
     hash as evidence.
6. **Run `python scripts/review_snapshot.py <slug>`** and start from its
   numbers: script length vs target, cross-episode repeated phrases (the
   boilerplate-tic detector), chapter-shape problems, cost/episode, OP3
   trend. Verify anything surprising against the raw files before treating
   it as a finding.

## Phase 1 — Evidence gathering (show review)

Read, for the target show:

- `shows/<slug>.yaml` + `shows/_defaults.yaml` (remember deep-merge: empty
  per-show blocks inherit defaults).
- All prompts in `shows/prompts/<slug>_*.txt` (+ any `_shared/` includes).
- The hook `shows/hooks/<slug>.py` if it exists, and the engine modules it
  leans on.
- The last ~10 episodes in `digests/<slug>/`: digest `.md` files, `_tts.txt`
  scripts, Whisper transcripts, `chapters_ep*.json`, metrics/credit-usage
  JSONs, and any memory/tracker/content-tracker JSONs.
- Public surfaces: the show's RSS feed at repo root, a couple of recent blog
  posts under `blog/`, the show's HTML page, and the narrative page if
  `memory_enabled`.
- The existing tests that cover this show (e.g. `tests/test_<slug>_*.py`,
  `tests/test_*_quality_pass.py`).

You cannot listen to audio. Whisper transcripts are your ears — they have
repeatedly caught real shipped-audio bugs (spoken "Fast." tag leaks, "closed
at zero dollars" closings, repeated boilerplate tics). Read them carefully
and diff several episodes against each other to spot every-episode tics,
dead rotation pools, and template echo.

For a `network` review, instead sweep cross-cutting surfaces: workflows in
`.github/workflows/`, shared `engine/` modules, the website/newsletter/X/
YouTube funnels, cost data, landmine statuses, and per-show download trends —
in the style of `docs/network_review_2026_06.md`. A `network` review ALSO
runs the **meta-review** of the review process itself: aggregate every
ledger in `docs/reviews/ledger/` — prediction verdict rates by finding
category, what the operator rejected or reverted, which fix classes keep
missing. If a category of finding consistently misses or gets rejected,
propose edits to THIS playbook (`.claude/commands/review-show.md`) in the
same draft PR so future reviews stop wasting effort on it (and weight up
the categories that consistently ship). `tests/test_review_agent.py` pins
the safety-critical language — never weaken the hard guardrails, the
draft-PR-only contract, or the A/B-listen callout.

## Phase 2 — Findings

Classify findings exactly as prior passes did:

- **P0 — listener-facing bugs shipping today** (malformed chapters, spoken
  failure-mode text, broken metadata, offensive content in committed files).
- **P1 — quality ceiling** (chronic under-length, boilerplate tics, dead
  code paths like never-called learning loops, stale trackers, prompts
  contradicting themselves).
- **P2 — growth/discoverability** (titles, teasers, cross-promo, SEO,
  feed metadata).

Every finding must be verified against the working tree with `file:line`
citations. A claim you did not verify does not go in the review.

## Phase 3 — Implement

- **Implement** P0 and P1 fixes that are code-only and clearly safe.
- **Prompt edits are allowed** (prior passes made many) but every prompt or
  audio-affecting change MUST be listed under an explicit "⚠️ A/B-listen
  required (landmine #17)" section of the PR body so the operator listens
  before trusting it. Never claim a prompt change is verified — only that
  it renders (`tests/test_prompt_fidelity.py`).
- **Show the operator the output, not just the prompt diff.** If you
  changed a digest prompt and `GROK_API_KEY` is set in the environment,
  exercise it: `python run_show.py <slug> --test` regenerates a digest
  (fetch + LLM only — no TTS, no X, no RSS, costs pennies). For
  podcast-prompt changes, drive `engine.generator.generate_podcast_script`
  directly against the latest committed digest. Paste short before/after
  excerpts into the PR's "A/B-listen required" section so the operator can
  READ the changed output before deciding to merge-and-listen. Skip
  silently when the key is unset. Never run the full pipeline or any
  publish/post step.
- **Defer** large refactors and anything irreversible: document them in the
  review doc as recommendations instead.
- **Every behavioral fix gets a drift-guard test**, following the existing
  pattern (`tests/test_tesla_quality_pass.py`, `tests/test_mit_quality_pass.py`,
  `tests/test_network_quality_pass.py`).
- Run the relevant test files plus the Phase-1 smoke suites
  (`test_prompt_fidelity.py`, `test_episode_validity.py`, `test_generator.py`)
  and fix what you broke. Report honest results in the PR body.

### Hard guardrails — never do these

- Never change R2 bucket paths or RSS `<enclosure>` URLs (breaks subscribers).
- Never move/rename the legacy flat files in `digests/` (landmine #3), never
  use git LFS (landmine #2), never commit MP3s.
- Never change the `min_articles_skip` DEFAULT in `engine/config.py`
  (landmine #21) — per-show YAML only.
- Never partially flip the four coupled TTS fields (`speech_wrap_open/close`,
  `use_section_tts`, `max_chars` — landmine #17).
- Never add phonetic respellings or programmatic speech-tag injection
  (100% regression rate on the custom voice — landmine #17).
- Never consolidate the three curated cross-show adjacency maps.
- Never touch voice IDs / TTS provider settings in `shows/_defaults.yaml`.
- Never post to X, send newsletters, upload to YouTube, or call paid APIs.
- Never merge your own PR; never push to `main`.

## Phase 4 — Deliverables

1. A review document at `docs/reviews/<slug>_review_<YYYY_MM_DD>.md`
   (P0/P1/P2 structure, what shipped vs. what's recommended, citations).
2. The fixes + drift-guard tests.
3. Update the target's entry in `docs/reviews/review_state.yaml` to today's
   date (this advances the rotation when the PR merges).
4. **Append this review to `docs/reviews/ledger/<slug>.yaml`** (schema in
   `docs/reviews/ledger/README.md`): shipped fixes, deferred items (carried
   forward and re-evaluated each pass — this is the structured backlog),
   updated verdicts on the previous entry's predictions, any new
   `do_not_retry` entries learned from operator verdicts, and — for every
   shipped fix that claims a measurable effect — a `predictions:` entry
   with the metric, today's baseline, and the expected value. The next
   review scores it; a fix whose prediction can't be stated probably isn't
   a fix. Record `agent_cost_usd` if you know it, else leave null.
5. Update the show's quality-pass notes in `CLAUDE.md` (concise — follow the
   existing June 2026 entries' style) if behavior changed.
6. Branch named `agent/review-<slug>-<YYYYMMDD>` (this exact prefix is how
   the scheduler detects an in-flight review and skips the slug). Commit,
   push with `git push -u origin <branch>`, then open a **draft** PR via
   `gh pr create --draft` titled `[show-review] <Show name> quality pass
   (<date>)`. The PR body must contain: TLDR of findings, what shipped,
   the "⚠️ A/B-listen required" list (or "none"), test results, and
   deferred recommendations.

Stay skeptical of your own findings, favor small verified fixes over broad
speculative ones, and remember the operating lesson recorded in CLAUDE.md:
theory-driven "this should be better" changes to shipped audio have a 100%
regression rate — evidence first.
