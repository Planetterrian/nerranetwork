# The Omni View desks + Top World — show notes and Ep1 review (Sep 23 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

- **The Omni View desks + Top World** (Sep 2026, pre-launch, Mira) — five
  regional daily briefs (Europe, Asia Pacific, Africa & Middle East, Central &
  South America, North America) and Omni View Top World News, which ranks the
  day's ten. **One definition, every surface:** `engine/omni_desks.py` owns
  the desks (sub-regions, seeded arcs, accents, anti-tabloid filters) and the
  intros / first-episode / validation / tracker / memory / cover registries
  loop over it; the prompts share `shows/prompts/_shared/omni_desk_*.txt` and
  the ONLY per-desk prompt text is `shows/prompts/omni_desks/<region>.txt`.
  No `keywords:` on purpose (regional feeds; a title filter would drop
  on-region stories). Sub-region balance is a data-side preference note from
  the last ten digests, never a quota. **Top World verifies against the
  publisher, never a sibling digest:** its hook turns each desk's Lead and
  first regional item into a hook article carrying only the headline and the
  ORIGINAL publisher URL (no desk prose), text-less hook articles are fetched
  first (`engine.article_text`), and the desks' summaries reach the prompt
  only as a ranking note the claims gate never reads. Guards:
  `tests/test_phase3_desks_2026_09_23.py`. **Ep1 review (2026-09-23):**
  grok-4.7 speaks every prompt rule as a sentence — 37 of 305 script
  sentences narrated the briefing, "the item", the desk's rules or the length
  target, and a per-sentence attribution rule produced "The Times reports…"
  ten lines running. `_shared/omni_listener_rules.txt` (desks + Top World)
  describes the shape, and the opt-in absence filter now removes
  self-narration (`is_self_narration_sentence`). Europe died on a grok-4.7
  503 (the pinned-model fallback now covers 5xx and the script stage) after
  its RSS fetch outlived run_show's 120 s wait and was DISCARDED
  (`_await_fetch` grace period). Guards:
  `tests/test_desk_ep1_review_2026_09_23.py`,
  `tests/test_pinned_model_fallback_2026_09_23.py`.
