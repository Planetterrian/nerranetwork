# Slate review — Monday 2026-10-12

The first full slate after the four Oct 11 review PRs merged, and after
eleven shows' script stage moved to a pinned grok-4.6/4.7 call. Inputs:
every committed `metrics_ep*.json`, credit file, `_tts.txt`, digest,
chapters and claims file of the day; the Actions runs since 2026-10-11
19:00 UTC; three per-show transcript reviews (flagship 4.6 scripts,
narrative and Monday shows, the grok-4.7 cohort); and the experiment
readouts due 10-12..14. Register `slate-2026-10-12`; guards
`tests/test_slate_2026_10_12.py`.

## 1. Did it run

- 28 of 28 expected shows published (06:28-12:30 UTC), no failed show
  run, `Run Tests` green on main.
- Every pinned script arm served its own model, with no fallback, read from the credit files'
  per-call `model`: UC and FPD on grok-4.7, Tesla, SpaceX, FF,
  Planetterrian, MIT, M&A, MAB, Omni View and DP Pod on grok-4.6. Script
  calls took 164-363 s; the longest run was M&A at 2,137 s of a 3,000 s
  budget.
- Structural regenerations: 6 of 25 (Omni View hook 154 chars; MAB 3 of
  4 items without Source; North America and Prediction Markets WYNTK
  sentence 1 off the hook's story; Africa & Middle East Progress Watch
  fragment; Привет a missing HOOK line).
- **P0 — multilingual translation hang.** SpaceX's FR translation call
  went silent at 09:57; the client's 3,600 s default timeout expired at
  10:57, the SDK retried twice, and the job was cancelled at its 120-minute
  limit at 11:55. SpaceX has no FR or RU track for Ep128, and therefore no
  @NerraRU/@NerraFR dubs today. M&A's translate step took 77 min against
  a normal 6-18. Fixed: the translation call carries its own timeout
  (`NERRA_TRANSLATION_TIMEOUT_SECONDS`, default 600) with the SDK's retries
  off, so the tenacity loop is the only retry (worst case ~30 min a
  language, inside the job). `grok_generate_text` gained `max_retries`.

## 2. How the Oct 11 changes performed

| Change | Read on this slate |
|---|---|
| 4.6 script stage, Tesla/FF/MIT/M&A | Digest-verbatim share fell (MIT 50-58% → 6%, Tesla 12-72% → 27%, Planetterrian ~77% → 10%); MIT reached its 1,800 target for the first time. Repeated facts Tesla 4 → 0. New defects below (stop token, teaser leftovers, meta lines). |
| 4.7 script stage, UC/FPD | UC 2,355 words at 21.5% verbatim — on its own prompt's 2,200-2,800 target, which 4.3 never reached — but `script_repeated_facts` 6 (was 0-1) from a "fact, then a 'Not …' fragment" restatement habit, plus one wrong chronology from the digest. FPD prose better, numbers weaker. |
| Streaming network default | No transport failure on any show. |
| DP Pod chapter fix (#1417) | Cold Open chapter present, no speaker-line titles, "club email" wording. |
| Both Sides optional (desks) | Held on the desks; Vancouver still ran one with no second side (its own prompt was never ported) — fixed. |
| SpaceX/AI Chips teaser rule | AI Chips teaser did not restate the calendar. |

FF (1,008 / 1,700) and Planetterrian (997 / 1,600) are short because of
the digest (2 items / 648 words; 6 items / 933 words), not the script:
both scripts are longer than their digests. Not a script-side lever
(banned network-wide).

## 3. Defects found and fixed in this PR

1. **`<|eos|>` reached the spoken script and the blog** (MIT Ep198; DP Pod
   Ep055 and Ep075 earlier; five translated tracks since June). The model
   wrote the closing's first sentence, emitted the stop token and ended;
   the missing-closing guard then appended the whole block, so the
   sentence aired twice. `engine.utils.strip_model_special_tokens` runs on
   every completion in `engine.generator._call_grok` and in both
   `digests/xai_grok` paths; `engine.pipeline.trim_partial_closing` drops a
   last line that is only the closing's opening before the guard appends.
2. **"Source: [kalkine.ca]" spoken on Финансы Просто Ep087.** A fifth
   source-tag shape (label + markdown bracket) joins the scrub.
3. **"Daily" on weekly shows.** Three prompts' cross-promo line called
   Env Intel daily and aired on UC; FP's called Привет daily; the network
   promo's frame 1 called the network "a family of daily podcasts" on DP
   Pod, and frame 4 offered "another sharp weekly briefing" from a daily
   show. Frames now read the speaking show's own cadence; a daily show
   plugging a daily show is byte-identical. A guard sweeps every prompt's
   cross-promo lines against the weekly shows' names.
4. **Lead chapters titled with a clipped hook** on five desks ("Sixteen
   people drowned in Bihar while collecting festival"). The desks' bold
   `Title: Outlet` lead headlines run 70-100 chars and were dropped as if
   they were the bold hook; a line that carried an outlet tail now may run
   to 110. A hook is a lead-chapter title only when it fits whole.
5. **Africa & Middle East aired two stories the digest had dropped.** One
   multi-story podcast page (The National) was the Source for a Riyadh
   strike, 139 migrants dead off Djibouti and an Australian leaving Iraq;
   the same-URL rule deleted two from the digest after the combined script
   had told them, so they aired with no ledger entry. A shared URL now
   counts only when the items also share the story (two salient title
   words, or a fifth of the body's).
6. **Self-narration the filter missed** — LatAm 11 sentences ("The published
   note gives…", "the paper's characterization"), Prediction Markets'
   "…in the material here.", North America's "Progress Watch: the day had
   none." Three narrow patterns, swept against every committed script;
   "on the page", "in that text" and "the written note" are prose
   elsewhere and are not matched.
7. **MAG 7 has never had an On the Calendar chapter** (Ep018-020 never said
   the phrase). The prompt now requires "on the calendar" in the
   calendar's first sentence (a digest-section anchor was tried: the
   calendar is five short lines in the closing window and cannot clear the
   anchor thresholds). ⚠️ AUDIO.
8. **Env Intel's "Science & Technical" chapter** fired on "The science here
   is…" over an empty section (the M&A `open.source` class). The marker is
   the spoken section label; the digest heading is the fallback, and an
   empty section anchors nothing.
9. **Vancouver Both Sides** was still mandatory and still seeded "the fact
   both sides accept"; the Oct 11 desk rule is ported (prompt + validator),
   Collingwood loses the seed too. ⚠️ AUDIO.
10. **Narrative restatement** — UC/FPD prompts gain ONE TELLING PER FACT
    (no "Not …" fragment restating a figure; nothing the brief does not
    state). ⚠️ AUDIO.
11. **Teaser leftovers** on 6 of 8 4.6 scripts (a fact held back from its
    story, or one already spoken) and raw domains spoken ("according to
    ad-hoc-news.de"): the shared content-discipline snippet now says the
    teaser never carries a held-back fact and the source is the outlet's
    name, never its address. ⚠️ AUDIO (17 shows).
12. **Prediction Markets read its checklist aloud** ("Comments on
    proposals. Not a final rule. U.S. federal jurisdiction.") — the rule is
    reworded by shape. ⚠️ AUDIO.
13. **Offshore North named the Route du Rhum village as the campaign's
    next milestone** four days after the team announced (8 Oct, own site)
    that Scott Shawyer will not start. The record (`rhum_entry`
    `not_starting`, dated, sourced), standing facts, field guide and
    countdown entries are updated, and a race EMIRA IV is not in is never
    the status block's next milestone.
14. **Привет, Русский! closes in Russian** (operator-directed). Three
    simple Russian closings; the YouTube call-out and the platform ask
    follow the closing's language; the lesson stays English-taught. The
    Closing chapter pattern matches the Cyrillic forms on a word boundary.
    ⚠️ AUDIO.

## 4. Experiments read (due 10-12..14)

| id | verdict | note |
|---|---|---|
| dead-shorts-weekly-probe | HIT | probe Shorts 7 at age 3 vs 8 for the same shows' daily Shorts; EN hook median held |
| offshore-north-read-the-article | PARTIAL | position/Boat-first held; one-Dan-reference 2/4, full text ≥ 8 1/4 |
| library-blend-own-scenes | INCONCLUSIVE | EN long AVP 15.8 → 11.8, but RU/FR longs (untouched by the blend) fell as much — common cause; not reverted |
| long-form-speech-cuts | INCONCLUSIVE → 10-27 | same shared metric |
| shorts-fact-cards | INCONCLUSIVE | mix change + breakout weighting; per-video arm median up 54.5 → 57.2 |
| shorts-punch-frame | INCONCLUSIVE | arm 57.4 vs other EN 52.1 |
| hook-short-motion | PARTIAL | lands on 97%, ~$24/mo; reach unscorable without a stills holdout |
| spoken-open-shape | INSUFFICIENT → 10-27 | n=1 curve per arm; 10-11 script-model moves confound both arms; the hook gate works (over-length 1/61 arm vs 35/66 control) |
| launch-cohort-schedule | PARTIAL | one missed slot day in two weeks |
| freshness-dating | PARTIAL (early) | 0 same-URL recurrences in 811; one >3-day Source shipped |
| frame-memory | PARTIAL (early) | OV/MAB hit; FF/PT miss; the desks' frames are required anchors — the target needs rescoping |

## 5. Open — not fixed here

- **SpaceX FR/RU for 10-12**: re-run "Multilingual" for spacex once this
  merges (the old client could hang again).
- **Content errors to correct** (corrections.yaml is the operator's): UC
  Ep140 dates sodbuster/swampbuster after the CRP (both 1985) and
  misreads Uchida's 14%/25%; Env Intel Ep072 says SARA protection attaches
  only with a critical-habitat order (s.32/33 prohibitions apply on
  listing); FP Ep087 says a TFSA withdrawal reduces room; M&A Ep201 put
  AutoIndexer's code "on arXiv" (GitHub).
- **MIT** recites two prompt lines ("Reproducibility is the product…") and
  builds an empty Tools segment from repeated items; its pick-before-review
  reordering gives a 6 s "Trade Review" chapter.
- **SpaceX** still has no news chapters (eight stories in "Introduction",
  three episodes running).
- **Top World**'s "names the country and the region" rule became the
  "In X, in <region>" frame (7 times).
- **grok_leads** found 0 on all four shows (6.8 s NO_LEADS each): x_search
  restricted to @grok may not return reply threads; needs a keyed probe.
- **Hook-short motion**: add a stills holdout if reach is to be scored.
