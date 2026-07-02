# Network Editorial Review — All 13 Shows, Transcripts 2026-06-18 → 2026-07-02

**Target:** `network` (editorial: fit, interest, content quality, positioning vs
each show's target audience). **Method:** every episode transcript in the
two-week window read in full (~150 episodes: `_tts.txt` scripts + Whisper
transcripts as ears + digests), against each show's YAML/prompts/RSS
positioning, both prior-review ledgers, and `review_snapshot.py` mechanical
numbers. Prior passes' deferred items honored (chronic under-length / digest
ceiling is NOT re-litigated anywhere below); `do_not_retry` respected.
Prediction verdicts from every scoreable ledger are recorded in the per-show
ledger files alongside this review.

## Network verdict

The network's **formats are working**: every show has at least one segment
that genuinely delivers its brand promise (Tesla's First Principles essays,
SpaceX's Engineering Deep Dive, EI's Practitioner Deep Dive, OV's
Understanding the Issue, MAB's analogy craft, MIT's no-trade discipline,
UC's empathy arc, FPD's load-bearing arithmetic, FP's «как подруге» deep
dives, PR's lesson architecture). The problems are concentrated in four
cross-cutting classes, three of which are mechanical and fixed in this PR:

1. **Number/name normalization garbles in flagship positions** — the
   currency/ordinal formatter was comma-blind, so hooks shipped as spoken
   gibberish ("fifty-nine dollars,990", "1,zeroth") on Tesla (4 episodes,
   twice in the HOOK) and SpaceX. Fixed deterministically (June-19
   seconds-fix class).
2. **Guard/retry mechanisms degrading the audio they protect** — the
   missing-closing guard's literal signature match double-spoke the entire
   closing on 5 of 15 MAB episodes (LLM de-contracted "that's"→"that is");
   the expand-below-target retry pads by paraphrase-duplication (M&A Ep087
   shipped verbatim doubled sentences; MAB Quick Bits balloon with
   restatements; UC's "one hundred vehicles… eighty-five vehicles"
   arithmetic filler). Both fixed (fuzzy signature match; near-duplicate
   sentence stripping with fallback-to-original).
3. **Seeded-template convergence, third generation.** The single most
   persistent editorial failure mode network-wide: any literal example
   sentence in a prompt becomes the show's next tic. This window's crop:
   OV's *"Both sides agree X; they differ on whether Y"* at saturation
   (12/12 stories in Ep099 — including manufactured "sides" on a shark
   attack, an earthquake, and Naomi Osaka's outfit); EI's *"There's a
   nuance here worth understanding"* 6/6 (the ledger predicted exactly
   this — MISS scored); MAB's replacement templates ("…stops feeling like
   magic…" 5/6 post-fix; "Here's something that's going to change…" from
   the prompt's own example menu); FP's «не так уж и сложно, правда?» 7/8
   and «Подруга спросила меня вчера» 6/8; MIT's seeded callback sentence
   colonizing 9/10 episodes; SpaceX's memory-echo "…remain the key open
   questions" ×5 in one episode. **These are prompt edits → all listed
   under the A/B gate below, NOT auto-applied.** The meta-lesson is
   recorded for the playbook: de-seed by *shape*, never by quotable
   example; menus of literal phrases just elect the next template.
4. **Same-day sibling overlap / beat encroachment** — Planetterrian
   (life-science show) duplicated Fascinating Frontiers' astronomy stories
   verbatim on 6 consecutive days; Tesla led with SpaceX corporate-finance
   stories (Ep518's first two minutes were "a worse SpaceX Daily");
   FF led with the same SiriusXM launch as SpaceX the same day. Fixed
   deterministically where possible (PT astronomy fetch filter — the
   single highest-leverage fix in this review; FF ephemeris filter +
   lookback), prompt-level beat rules proposed under A/B.

Also in this window: **two same-day double-publishes** (Tesla Ep519+Ep520
June 23; Привет Русский Ep046+Ep047 June 22 — plus OV June 19) that the
landmine-#24 duplicate guard did not stop, and **one silently missed
episode** (SpaceX's June-28 Sunday recap never ran). These are scheduler
forensics → operator items.

## Per-show scorecards (fit / interest / content / positioning, 1-10)

| Show | Fit | Int | Cont | Pos | One-line editorial verdict |
|---|---|---|---|---|---|
| Tesla Shorts Time | 6 | 5 | 4 | 5 | Right breadth, real analysis in First Principles; undermined by hook garbles, "Daily" brand bug, dateline filler, weak recaps, SpaceX drift |
| SpaceX Daily | 7 | 6 | 5 | 7 | Engineering-first identity is real; entity conflation (xAI↔SpaceX) and story re-leads are the quality gap |
| Models & Agents | 7 | 5 | 4 | 7 | Practitioner depth is real; arXiv flood crowded out the fortnight's two biggest builder stories (the *beginner* show caught them) |
| M&A for Beginners | 7 | 7 | 5 | 8 | Genuinely distinct and beginner-followable; double-closing P0 + unnamed "try this" tools |
| Fascinating Frontiers | 7 | 6.5 | 7.5 | 6.5 | Cosmic Deep Dive earns the subscription; slow-day self-recycling and ephemeris filler dilute |
| Planetterrian | 5.5 | 6 | 7.5 | 5 | **Biggest positioning problem in the network**: a longevity/health brand shipping a general-science firehose; health-claim hedging is exemplary though |
| Omni View | 6.5 | 6 | 5.5 | 6 | The neutrality promise HOLDS (3-story audit clean) — but steel-manning is now simulated by formula, applied to stories with no sides |
| Env Intel | 5.5 | 5 | 5 | 6 | Deep-dive substance is the network's best B2B content; orphan-Closing chapters returned (variant 3), thin days triple-tell one story |
| Финансы Просто | 7 | 5 | 5 | 8 | Real niche, real localization; scaffold leak on air, one fabricated tip, template echo |
| Привет, Русский! | 7 | 4 | 4 | 8 | Great pedagogy architecture — but taught ungrammatical Russian as model sentences and looped 3 themes for two weeks |
| Modern Investing | 8 | 6 | 6 | 7 | Most actionable show; **phantom (data-failure) trades narrated as market outcomes** is its worst-possible error class |
| Unintended Consequences | 8 | 6.5 | 8.5 | 6.5 | Empathy discipline + mechanism depth intact; queue category-clustering (8 straight medicine episodes) |
| First Principles Daily | 8.5 | 7.5 | 9 | 7 | Best content accuracy in the network; queue duplicates + one header-leak episode |

## P0s found (and their dispositions)

1. **Tesla/SpaceX comma-number garbles in hooks** — FIXED (deterministic,
   `assets/pronunciation.py`; regression tests for all five shipped forms).
2. **MAB double-spoken closing, 5/15 episodes** — FIXED (fuzzy closing-guard
   signature, `engine/pipeline.py`; the guard still fires on genuinely
   missing closings).
3. **MIT phantom trades spoken as market outcomes** ("ROKU closed flat…",
   "KO closed flat today" — no price was ever fetched; 4 of the spoken "7
   breakeven outcomes" are data failures) — FIXED (voided-trade status,
   excluded from every aggregate/review/lookback; one-time tracker
   migration via the module's own recompute: 41 → 37 trades, breakeven
   7 → 3, win rate 51.2% → 56.8%, avg return 0.64% → 0.71%, cumulative
   P&L and alpha unchanged; each closed trade now reviewed exactly once —
   the MU trade had been "yesterday's flash trade" three times).
4. **PR taught ungrammatical Russian as model sentences** (Ep043: «Я есть
   хлеб», «Моя яблоко») and **fabricated an etymology as fact** (Ep050
   чемодан/valise) — prompt-rule proposals (A/B); the *curriculum loop*
   half is FIXED in code (no-reteach window 3→8, Word-of-the-Day
   never-repeat, theme-gap enforcement — «хлеб» was WOTD 3× in 12 days,
   only 27 of 87 taught word-slots were new).
5. **EI orphan-Closing chapters returned (variant 3)** — 3/5 episodes ended
   on a promo-collision body chapter — FIXED (Closing/Teaser ordered before
   all body markers; bare `deep dive` dropped; `science|technical`
   promo-proofed; re-parsed all five real episodes — all now start
   Introduction / end Closing). Deeper root cause found during
   verification: the June-11 `where: end` window (last 15%) itself
   EXCLUDED the closing on short EI episodes (the ~130-word outro stack
   lands the sign-off at ~82-84% of a 650-870-word episode), so Closing
   now relies on its brand-anchored pattern without the positional window.
6. **SpaceX "Fiorentina versus Genoa" laundered SEO spam + xAI↔SpaceX
   entity conflation** — spam class FIXED at fetch (video-ID/fixture title
   filter, 13F/stock-filter class); entity discipline is a prompt proposal
   (A/B) — not safely mechanical.
7. **FP spoke raw digest scaffold** («Сорс MoneySense…», Ep059) — FIXED
   network-wide (Source-line scrub in the script-save path).
8. **Tesla spoken brand "Tesla Shorts Time Daily" 14/14** — root cause
   found (a second normalizer in `run_show.py` rewriting TOWARD the old
   brand, undoing the June-20 generator fix) — FIXED (completes the
   operator-approved June-10 decision; quick A/B-listen advised).
9. **Double-publishes + missed SpaceX recap** — NOT fixed here (scheduler
   forensics needed) — operator item with dates/evidence below.

## Selected P1s (full details in the six per-show analyses)

- **M&A sourcing drift:** arXiv cs.CL was subscribed TWICE (fixed — duplicate
  feed removed + network-wide no-duplicate-feeds guard); selection-rule
  rebalance (lab releases outrank preprints) proposed under A/B. Evidence:
  Codex Record Replay and Gemini Computer Use (OSWorld 78.4) never aired on
  the builder show but both aired on the beginner show.
- **FF slow-day self-recycling** (Ep116 re-ran 4 of its own week's stories):
  `content_freshness.lookback_days` 2→7 (fixed) + ephemeris title filter
  (fixed, verified zero false drops against the window's titles).
- **PT scope backstop:** astronomy fetch filter (fixed, verified against the
  window's titles — kills the 6-day FF duplication) — the prompt-side scope
  guard + life-science floor and the keywords trim are proposals.
- **OV Ep085 digest regression:** "the strongest case" ×24 in a shipped
  digest 8 days after the ban (script clean — the ban held there). Proposal:
  mechanical digest lint (warn/regen on template saturation), plus the
  "Both sides agree" de-seed + no-manufactured-sides escape hatch (A/B).
- **OV depth vs breadth:** prompt demands 6-7 stories × 6-8 sentences;
  window ships 12-13 × ~5 — steel-manning compressed to one sentence per
  side (A/B proposal to select-and-deepen).
- **Tesla recap quality:** Ep517 covered the Dojo patent three times and
  read raw headlines + "EtherType 0x9AC6" hex on air; Ep525 used nine
  consecutive "From X, Y comes next" transitions (A/B proposals).
- **EI thin-day triple-telling** (Ep047/049 tell one story 4×) + "federal
  register" spoken instead of "Canada Gazette" (Ep051 ×4) + "Tomorrow,
  watch for…" on an every-other-day show — A/B proposals.
- **UC/FPD:** likely-wrong $50/life-saved stat (Ep038); FPD Ep024 spoke its
  digest's creative sub-headings mid-paragraph (header-strip proposal);
  queue hygiene FIXED (UC category interleave + miscategorized entry; FPD
  duplicate pruning + concrete/opportunity alternation restored — Ep020/021
  had shipped back-to-back concrete).
- **MIT two irreconciled alphas** (+11% daily vs −13.1% Sunday) — labeling
  proposal (A/B); the Sunday honesty is a strength to keep.
- **Snapshot tooling blind spots:** the repeated-phrase detector was
  Cyrillic-blind (cleared FP while a template ran 7/8) and the chapter check
  missed missing-final-Closing (cleared EI while 3/5 shipped orphaned) —
  both FIXED so future reviews see what this one had to find by hand.

## ⚠️ A/B-listen required (landmine #17) — proposed, NOT applied

No prompt file was edited in this PR (no GROK_API_KEY in this environment to
render before/after excerpts, and the seeded-template class deserves the
operator's ear). Proposed edits, per show, in priority order:

1. **OV** `omni_view_digest.txt:51` — remove the literal "Both sides agree
   on [X]; they differ on [Y]" seed; cap the construction ≤2/episode; add:
   disasters/tragedies/obituaries/celebrity items get facts + coverage
   framing, never manufactured "sides". Also: select 6-8 stories and deepen
   (resolves the 12-slot digest vs 6-7-story podcast conflict).
2. **EI** — thin-day rule (a 1-2-story day tells the story ONCE; Regulatory
   Watch/Industry come from the forward calendar per the existing
   low-content-day format); remove "There's a nuance here worth
   understanding" from the menu (third-generation tic — prefer rotation
   memory over another menu); "Next briefing, watch for…"; always "Canada
   Gazette", never "federal register"; spoken script must carry cited
   instrument references.
3. **MAB** — rewrite the opener menu with zero quotable strings; ban "…stops
   feeling like magic…" verbatim alongside "not so scary"; "try this" items
   ineligible unless the tool is NAMED in the source; Quick Bits ≤3
   sentences, every sentence a new fact.
4. **FP** — de-seed «не так уж и сложно, правда?» and «Подруга спросила
   меня вчера» (keep the method, fresh phrasing); cap «Коротко и ясно» at
   2-3 sentences + finance-relevance rule; disclaimer line in all closing
   variants; deep-dive may not re-explain the episode's own main topic.
5. **PR** — grammar-correctness rule (model sentences fully
   conjugated/agreeing; never "Я + infinitive"); etymologies must be
   standard/verifiable or hedged; stop narrating plan-field labels ("The
   memory hook notes that…"); English AI disclosure for the
   English-speaking audience.
6. **MIT** — de-seed the "This is the exact scenario where our earlier
   rule…" callback example; retire "closing-price confirmation" as a
   teachable lesson (it's the pipeline describing its own former price-fetch
   bug); label the two alpha metrics whenever spoken; Saturday scripts say
   "Friday's close".
7. **Tesla** — recap hardening (one story once; never speak Title-Case
   headlines or patent/hex minutiae; transition variety); ban standalone
   dateline-filler sentences; require named entities ("One city…" is not a
   story); counterpoint-section enforcement (5/14 misses); SpaceX/xAI
   corporate items are SpaceX Daily's beat — never Tesla's hook/lead.
8. **SpaceX** — entity discipline (Memphis/Colossus is xAI's; ban
   "SpaceXAI"); every hook clause must correspond to a covered story
   (Ep17's hook promised a static fire the episode never covered); Tesla-
   style deep-dive topic history injection (Ep15/Ep19 ran the same deep
   dive); decide the deferred price-once fix (Ep17 spoke "lowest close
   since IPO" and "up 0.3%" 30 seconds apart — the strongest evidence yet).
9. **PT** — the real fix behind the deterministic filter: scope guard +
   ≥8/15 life-science floor in the digest prompt; trim bare
   "science/research/study/discovery" keywords (monitor volume vs
   `min_articles_skip: 2`); preserve the exemplary health-claim hedging
   with an explicit prompt rule so it can't regress.
10. **FF** — de-prioritize routine comsat/cadence launches (SpaceX Daily's
    beat); developing-story discipline (no re-run without a new
    development — Swift reboost ran 4×).
11. **UC/FPD** — cap the restate-percentage-as-count device and "One might
    ask/object" ≤1/episode (UC); forbid absolute cost-effectiveness claims
    without units sanity (the $50/life-saved class); FPD podcast stage must
    not emit markdown headers (plus a code-side header-strip is worth
    considering).
12. **M&A** — continuity-callback cap (≤1 spoken callback/episode, never
    episode numbers — "sits in the ongoing maturation of agent tool use
    tracked since episode eighty six" is the banned phrase reborn);
    selection rule: lab product/feature announcements outrank preprints,
    arXiv items ≤40%; recap must synthesize, not splice (Ep095 reused
    dailies' sentences verbatim; Ep088 proves the model can do it).

## Operator items

1. **Double-publish forensics:** Tesla June 23 (Ep519+Ep520 both in RSS —
   decide whether to pull one), PR June 22 (Ep046+Ep047), OV June 19
   (Ep086+Ep087). The landmine-#24 duplicate guard + Cloudflare dispatcher
   interplay needs a look; PR also skipped June 26/28.
2. **SpaceX June-28 Sunday recap never ran** — no commit, no episode,
   silent.
3. **Verify EI Ep050's "coordinated federal-provincial permitting" claim**
   against its source; if unsupported, it's the strongest argument for a
   grounding rule on Lead-Story regulatory-mechanics claims.
4. **MIT Ep093 "Qualys surged 65%"** — investing.com promo headline
   amplified with invented same-day framing; consider demoting that source
   tier and requiring a second source for >20% single-day move claims.
5. **FP cadence** is stated three contradictory ways (YAML "daily",
   CLAUDE.md table "Monday", ledger "even days"); actual: mixed. Decide and
   align.
6. **Tesla narrative tracker curated `status` texts lag the show's own
   reporting by months** (cybercab still "unveiled at We, Robot") — refresh
   via `scripts/update_tesla_narrative.py`.
7. **EI "all-province" promise vs reality:** QC/SK/Atlantic got ZERO
   mentions in the window despite the Phase-4 queries — try French-language
   sources or soften the RSS promise.
8. **CLAUDE.md says M&A X posting is disabled but the YAML has
   `x_enabled: true`** with the @teslashortstime app prefix — confirm intent.
   Also: the new no-duplicate-feeds guard surfaced a pre-existing BBC
   http/https duplicate in `omni_view.yaml` (allowlisted with a comment —
   collapse it when convenient).
9. Regenerate-or-accept: UC Ep038/039 and other June-23/24 episodes shipped
   the since-reverted "NAIR-uh NET-work" brand garble in audio.

## Ledger prediction verdicts recorded this pass

Tesla June-20: Teslarati **HIT**, 13F **HIT**, brand-"Daily" **MISS**
(root-caused + fixed here). SpaceX June-19: time-garbles **HIT**, recap
Closing **HIT**. M&A June-21: koo-dah **HIT**, length no-regression **HIT**.
MAB June-25: both de-seeds **HIT** (with successor-template caveat recorded).
FF June-24: launch false-drop **HIT**, recap stock-leak **resolved-HIT**,
June-12 garbles **HIT**. OV June-10: strongest-case **PARTIAL** (script 0/15;
digest 24× Ep085), anonymity **HIT**, Closing **HIT**, fragments **HIT**,
length **MISS** (deferred). EI June-17: Introduction **HIT**, nuance-tic
**MISS** (reopened + menu fix proposed), orphan-Closing **reopened as
variant 3** (fixed). FP June-16: five **HITs**, length **MISS** (deferred).
FPD June-23: retry **~HIT**, lesson-template **HIT**, Closing-chapter fix
verified. PT June-18: chapter shape holds. New ledgers created for
privet_russian and modern_investing (previously unscored shows).

## What this pass changes about the review process itself

- `review_snapshot.py` is now Unicode-aware (Cyrillic tics visible) and
  flags missing-final-Closing chapter shapes — two blind spots that let
  shipped defects pass three snapshots in a row.
- Meta-lesson for the playbook (recorded, not yet applied to
  `.claude/commands/review-show.md`): **never put a quotable example phrase
  in a rotation menu** — three separate shows elected the first menu item
  as their next tic. De-seed by describing the shape.
