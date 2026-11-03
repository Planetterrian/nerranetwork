# Oct 9 2026, afternoon — review items 9–13, and the slate that followed

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Oct 9 2026, afternoon — review items 9–13, and the slate that followed the
morning's merges** (register `structural-regen-2026-10-09`,
`probe-tier-imagery-2026-10-09`, `x-accounts-rotation-2026-10-09`,
`x-on-spacex-daily-aoai-2026-10-09`; guards
`tests/test_review_items_9_13_2026_10_09.py`, `tests/test_sdk_httpx_2026_10_09.py`).
**P0 first: the stream reader imports the SDK's own HTTP module**
(`engine.generator.sdk_httpx` — `openai` 3.26+ is built on `httpx2`, a
different import name, and `httpx` had only ever arrived as a transitive
dependency; when `tokenizers` 0.23.3 landed at 10:00 UTC nothing pulled it
any more and all seven `llm.stream` shows from 10:08 died at their first
digest call). No production module imports `httpx` by name. **A
regeneration the pipeline cannot repair is not a structural defect**: 35%
of episodes (107/304, Sep 25–Oct 8) regenerated their digest — 43 on a hook
over 150 characters, every one on a prompt that supplied its own over-limit
specimen (the shows including `_shared/hook_shape.txt` ran 0–1 in 14). The
two narrative prompts (UC, FPD — 15 of the 43) include it now and their
Example specimens are gone (⚠️ AUDIO, the hook is the spoken open);
omni_view, models_agents, modern_investing and env_intel were the CONTROL
of the Sep 22 spoken-open experiment and waited for its readout; it was
ended unscored on Oct 24 and they include the snippet now, specimens gone
(`TestStructuralRegen::test_former_control_shows_carry_the_shape_and_no_specimen`);
23 on an empty section —
Tesla's Short Spot is `optional` because the cross-section dedupe empties
it BEFORE the validator and the retry's Short Spot was deduped again (6 of
8 shipped empty anyway), a present optional section with 0 items is not an
issue (MIT's one-sentence Listener Challenge), and FF's Space Stories
pattern accepts the numbered list under the hook rule (the header was the
only thing missing). `digest_structural_regen_reasons` is recorded;
`digest_structural_regen_share_7d` is the readout. **The probe tier draws
two portrait scenes** (`PROBE_PORTRAIT_SCENES`, keyed on the plan's
`shorts_probe`, never a show list; the 16:9 set on tier-B longs is a live
surface and stays). **Review item 11 named the wrong knob**: the cohort's
7–9 search calls were per-account X fetches, not web queries —
`x_accounts_per_run: 4` on vancouver / ai_chips / mag7 / peptides /
longevity reads four accounts a day on a date-seeded rotation
(`engine.fetcher.rotate_x_accounts`); Offshore North is untouched (weekly,
$0.07/week). **X is on for SpaceX** (the `X_` app, @teslashortstime),
**Nerra Daily and The Age of AI post from the network account** through
`engine.x_post` (`NERRANETWORK_X_*` secrets — operator item; unset is a
logged skip recorded as `x_post_skipped: no_credentials`), run_show records
`x_posted` / `x_post_skipped` (`x_posted_share_7d`), and the edition
metrics carry the outcome. **The grok-4.6 script arms on SpaceX and Omni
View never ran** (444 s drop, 660 s timeout, both fell back to 4.3 — read
an arm from the credit file's per-call `model`): both shows now
`llm.stream: true` per playbook rule 7. The multilingual resolve step
treats an EMPTY successful jobs read as "nothing published" (a gate-only
schedule run had swept all seven). Item 12 is an operator step in
`docs/podcast_directories.md`: the three French-only feeds go to Podcast
Index before their $11/mo is decided.
