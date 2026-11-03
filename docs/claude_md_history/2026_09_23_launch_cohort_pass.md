# Launch-cohort pass, PR A (2026-09-23)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

- **Launch-cohort pass, PR A (2026-09-23; plan
  `/root/.claude/plans/staged-brewing-hanrahan.md`, guards
  `tests/test_launch_cohort_pass_2026_09_23.py`).** The per-show review of
  all 13 new shows found rules the prompts state and the model breaks, so
  they are code now. **`engine/digest_lint.py`** is a closed vocabulary of
  digest checks a show opts into with `digest_lints:` — WYNTK sentence 1
  must be the hook's story (`wyntk_hook_match`; MAG 7 Ep1 scored 0.08), a
  lead item is never sourced only to X, a desk's Progress Watch is a result
  or the explicit one-sentence none, MAG 7's Counterpoint engages the lead,
  AI Chips' data-centre items carry a build state + MW, the health shows'
  study sentences name their rung and never a dose. A finding rides the
  EXISTING one-shot structural regeneration; nothing here blocks or strips.
  **X posts credit the article they link** (`fetch_x_posts` asks for
  `POST_LINK`; the post URL moves to `x_url`), and `x_posts_as_sources`
  (`any` = legacy | `linked_only` | `secondary`) says how a show may use
  posts — Africa & Middle East Ep1 had credited 6 of 6 sources to x.com,
  BBC Africa and Al Jazeera posting their own stories. The committed
  Ep1s were re-sourced the same day with `scripts/resource_x_citations.py`
  (X's public syndication endpoint → the post's outbound link → the
  publisher URL; a tag / topic / mirror page is never a citation; dry-run
  default): 8 of 16 lines resolved, the rest were posts that linked
  nothing. `preferred_domains` (per-show list; `engine/preferred_sources.py`)
  gives a show's primary publishers — regulators, courts, journals, the
  city's own newsroom — a relevance bonus and a `[preferred primary source]`
  tag in the prompt listing (metric `articles_preferred_in_prompt`). **The claims ledger
  has an item coverage floor**: every grok-4.3 episode had recorded 0–1
  claims against 8–13 on 4.7 because the appendix called an empty array
  "valid and normal"; `attempt_item_coverage_repair` spends the existing
  repair pass on sourced items no verified entry covers and can only ADD
  entries. **Local shows carry `region_allowlist`** (word-boundary match on
  title + opening text; hook articles always pass; metric
  `articles_dropped_off_region`). **Top World's desk intake parsed zero
  items on Ep1** — `desk_items` matched only `**Title:** body` and the desks
  write `**Title: Outlet**`; fixed, and an X URL is never a publisher URL
  there. A syndicated wire copy is credited to the wire its dateline names
  (`credit_wire_datelines` — "The Mighty 790 KFGO" carried Reuters).
