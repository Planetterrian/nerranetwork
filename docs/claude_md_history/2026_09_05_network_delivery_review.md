# Network delivery review — content density over narration (Sep 5 – Sep 12, 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Network delivery review — content density over narration (Sep 5, 2026)

Operator brief: the flagships read as "narrative driven with redundant
repetition"; the ask is content- and information-driven episodes with a
consistent, engaging delivery across podcast, blog and video. Canonical
writeup:
[`docs/reviews/network_delivery_review_2026_09_05.md`](docs/reviews/network_delivery_review_2026_09_05.md);
ledger entries (predictions to score) in eight per-show ledgers + `network`;
experiment `network-content-discipline-2026-09` (readout 2026-09-26). Drift
guards: `tests/test_delivery_pass_2026_09_05.py`. Four audits agreed the
cause was mechanical, not the host's taste, and the rules below bind:

- **The script stage must WRITE, not de-markdown.** On the worst days 62–78%
  of a script's 8-word phrases were verbatim digest text, so every digest
  duplicate shipped as audio. `engine/script_audit.py` measures it per
  episode (`script_digest_overlap_pct`, `script_repeated_facts`,
  `script_filler_pct`, `script_hook_restated`; `::warning::` above
  thresholds; `review_snapshot.py` tabulates it). It is a READ-ONLY
  instrument — a review re-reads the baseline before moving a threshold,
  and a rule that changes the script belongs in the prompt or in a gate,
  never in the audit.
- **The digest's "ZERO STORY OVERLAP" rule is enforced by code, not prose.**
  `engine/digest_overlap.py` drops a later item that repeats an earlier
  one (same Source URL; headline sharing ≥50% of salient words; body
  sharing ≥50% of salient vocabulary — Tesla Ep592's five re-headlined
  X Takeover items carried no Source lines, so URL matching alone was
  blind). Runs before the validator and again after the structural
  regeneration; a section it empties triggers the existing one-shot
  regen, which is the correct outcome. Blocks split at numbered items AND
  header lines — the templates put `### Top News` directly under the hook.
- **Memory is for accuracy, never narration.** `show_memory`'s composed
  section used to inject *MANDATORY CONTINUITY: add 1-2 natural sentences
  of where today's development fits in the ongoing arc* on every story of
  every memory show, contradicting the status block's "at most ONE" — the
  model obeyed the mandatory line. Now: one audible callback, only with a
  delta (what changed since prior coverage); no arc sentences, no
  open-question recaps. Tesla's bespoke `tesla_memory` block still carried
  the quotable "Remember, we covered…" example the shared block lost on
  Sep 4 — gone.
- **`shows/prompts/_shared/content_discipline.txt`** is included in the nine
  English news-show podcast prompts: digest is source material not a
  draft; sentences follow facts (2–6 per story, cut below two, never "no
  details were provided"); one owner per fact; a story ends on its last
  fact; transitions carry information or are dropped; source named once;
  the same voice every day. It is shape-only. **Every worked example
  sentence was removed from seven podcast prompts** (FF Ep182 L2, PT
  Ep172/173, OV Ep164/165 and Tesla Ep594 all shipped a prompt's own
  specimen line) — "described shape, never a quotable line" now applies to
  the EXAMPLE OF IDEAL STORY COVERAGE blocks too, not only to tics.
- **A deep dive is a second story, not a second pass.** M&A's Under the
  Hood re-explained a news item in 5/6 episodes (the exception was the
  densest episode); OV's Understanding the Issue re-narrated the lead;
  SpaceX's Deep Dive carried two numbers, both already spoken. Every
  deep-dive spec now forbids restating a covered body and carries a
  numbers floor (SpaceX 5, M&A 4, Tesla 3). Chapter anchor phrases stay
  as phrases the writer builds a sentence around.
- **Digest items: sentence count follows fact count.** Fixed "4–5 / 5–7
  sentences" produced a fifth sentence restating the first and generic
  consequence prose ("Buyers gain a clearer picture…"). Per-item "what to
  watch next" became a dated next step only when the source names one;
  "why it matters" only when the source explains it. Tesla's X Takeover
  items must carry Source lines; M&A gained ONE STORY = ONE ITEM.
- **One closing per flagship** (SpaceX, Tesla, M&A, MIT) — the rotating
  pool read as register drift. This reverses the Sep 4 M&A pool expansion
  on purpose; the sibling plug and website surface still rotate after it.
  MIT's Market Pulse speaks index levels only; portfolio numbers belong to
  Portfolio Performance alone (Ep160 read the record twice).
- Bugs from the transcripts: "VS Code" is spelled out before the versus
  rule ("versus versus Code"); `r/teslamotors` is spoken as a subreddit
  name; a line repeated inside the closing eight is collapsed (MIT Ep159's
  doubled gallery plug).
- **Same-day readout (Tesla Ep595 old prompts vs Ep596 new):** filler
  3 → 0, digest duplicates 0, one pinned closing — but digest-verbatim
  only 63% → 51% and the essay still re-told a covered story. So:
  `llm.script_rewrite_gate_overlap_pct` (40 on the nine English news
  shows, 0 = off) re-runs the script stage ONCE with the copied sentences
  named when the finished script carries ≥40% verbatim 8-grams; the
  rewrite is kept only when it copies less and is ≥70% of the original
  length (`engine.pipeline._script_rewrite_gate`; metrics
  `script_rewrite_gate_*`). It is a REWRITE gate, never a length lever —
  it does not fire on word count, so it is not the banned podcast-side
  retry class. Tesla's First Principles gained the TOPIC DISTINCTNESS
  rule M&A's Under the Hood has. A mechanical essay-vs-item overlap note
  was prototyped and rejected (no threshold separates re-tells from
  unrelated essays).
- **Sep 6 readout (first full slate with prompts + gate live; the
  "Sep 6 readout" section of the review doc):** OV/FF/MIT clearly
  better, SpaceX/M&A/MAB/Tesla mixed, PT worse. Three defects the
  whole-script number could not see, all fixed in
  `engine/script_audit.py` + `engine/pipeline.py`: (1) **the gate threw
  away a clean rewrite** — Tesla Ep597 went 61 → 2% verbatim and was
  rejected because the floor was pinned to an over-long draft; the floor
  is now 70% of **min(draft, target)** and `script_rewrite_gate_reasons`
  / `_reject_reason` / `_rewrite_words` are recorded — a silent rejection
  is the silent-number class. (2) **Sections were read aloud under the
  threshold** — SpaceX Ep092 sat at 24% overall with its Engineering
  Deep Dive 10/13 digest sentences (word-swap paraphrase, 59% 8-grams);
  the deep-dive block was 78–100% verbatim on 72 of the last 90 episodes
  across nine shows. `copied_sections` scores each digest header block
  (≥100 words; ≥80% 8-grams, or ≥70% sentences near-matched with ≥25%
  verbatim) and the gate fires on it, naming the section. It WILL fire
  on most episodes at first; `script_rewrite_gate_copied_sections_after`
  says whether the retry clears it. (3) **An orphaned hook** — PT Ep175
  opened on a story the body never told; `hook_coverage` (share of the
  opener's salient words the body speaks; PT 0.09, everything healthy
  0.33–1.0) fires the gate below 0.3. Also: the headline-echo tic
  (Tesla ×6, M&A ×9 — a spoken headline then the body restating it) and
  attribution-only sentences are named in the shared snippet; MIT's three
  prompt-supplied lines aired verbatim and are de-seeded; `US$95` had no
  pronunciation handler ("USninety-five dollars" on air) — the `C$` path
  now handles `US$`/`USD$`; MAB keeps every number the briefing gives.
  Guards: `TestSep6*` in `tests/test_delivery_pass_2026_09_05.py`.
- **Sep 7 readout (first slate with the section/hook gate live; "Sep 7
  readout" in the review doc):** the gate fired on all nine gated shows
  and every rewrite was accepted — first drafts still copy 42–66% daily
  and the retry brings them to 0–5%, so **the gate, not the prompt, is
  what keeps scripts written**; budget one extra script call per gated
  episode. Two side effects, both fixed: (1) **rewrites paraphrased the
  NAMES** — "Megapack 3" became "the latest version of the large battery
  packs", "Raptor V3" was never spoken in the body; `script_audit.
  entity_retention` (share of the digest's capitalised mid-sentence
  tokens the script speaks) fell Tesla 73→53%, M&A 81→52%, OV 100→65%.
  The gate now rejects a rewrite more than 15 points under its draft
  (`reject_reason=names_lost`, `REWRITE_GATE_MAX_ENTITY_DROP`) and the
  appendix says names are never paraphrased. (2) **Rewrites shrank to
  the stated floor** (Tesla 985 words on a 1,400 target) — the appendix
  now anchors on the draft's length and records
  `script_rewrite_gate_original_words`. Also: the section test had read
  zero sections everywhere because run_show's podcast digest strips the
  `#` markers — the RAW digest is passed as `section_digest`; a glued
  `Nk` tail is a name ("Nutritionfive thousand" aired), GPU model numbers
  speak as pairs ("RTX fifty ninety"), the subreddit handler no longer
  doubles "the". Guards: `TestSep7*`.
- **Sep 9 readout (Sep 8 slate; "Sep 9 readout" in the review doc): the
  rewrites stopped copying and started DROPPING.** First drafts are now
  under the 40% threshold on 5 of 9 shows before any retry, but a new
  measure — `script_audit.digest_coverage`, the share of the digest's
  sentences the script tells in any wording (`script_digest_coverage_pct`,
  warn < 50, snapshot column) — read 77–95% on copied scripts and 43–65%
  on the rewritten week (Tesla Ep599: two stories skipped, 8 of 17
  numbers, 915 words on 1,400). **Read overlap and coverage together:
  the goal is overlap ≤ 15% AND coverage ≥ 70%; either alone is gamed by
  the other.** The "two to six sentences" rule read as a cap and now
  says every digest fact is spoken ("the floor, not a menu"); the gate
  rejects a rewrite 15 points thinner than its draft (`facts_lost`);
  a rewrite that copies less overall with no new copied section ships
  even if a flagged section persists (M&A Ep167's better rewrite was
  thrown away); `llm.script_rewrite_gate_attempts` (default 1, Tesla 2 —
  its Sep 8 rewrite copied MORE and the draft aired) takes bounded
  attempts each judged against the draft. Also: `_lint_digest_placeholders`
  warns when the digest carries a placeholder-shaped number ("2xxt/s"
  became "half those rates" on air — `digest_placeholder_tokens`), and
  a digit glued to a letter is a model number, not a range ("Xeon Efive
  to two thousand six hundred ninety-six" aired for E5-2696). Two of the
  three short Sep 8 scripts were not thinning: SpaceX's digest had two
  items from 14 articles (a fetch-famine day) and M&A's 1,044 words were
  the headline-echo padding removed with 33 numbers kept — coverage
  tells them apart where word count cannot. Guards: `TestSep9*`.
- Every prompt-side item above is landmine-#17 A/B; the engine modules are
  removal-only or read-only and are not.
- **Sep 12 2026 — the rewrite gate is GONE.** Measured Sep 9–12 across
  the nine gated shows: fired on 30/35 episodes, accepted 11, rejected
  17 (`facts_lost` / `names_lost` / `copies_more`). A two-pass script
  could be written (1–4% verbatim, 40–60% coverage) or complete (55–77%
  verbatim, 85–97% coverage), never both, because the script stage
  re-told a finished document; every patch since Sep 5 moved the tension
  and none resolved it. Do not re-add a script retry of any shape — the
  fix is the generation design (next section). `engine/script_audit.py`
  stays as the read-only instrument.
