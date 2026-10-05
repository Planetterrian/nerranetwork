# Network review — Monday slate, 2026-10-05

Operator request: review every episode and workflow from the last 24 hours,
judge how things perform, and fix what warrants it. Register
`slate-review-2026-10-05`; guards `tests/test_slate_review_2026_10_05.py`.

## 1. How the slate ran

- **25 of 25 scheduled episodes published** (every Monday show plus the
  dailies), each run-show job green; Nerra Daily Ep046 built at 12:43 UTC
  with all 23 English shows, no misses, 2 h 55 min.
- **Spoken-text gate 25/25 pass.** Финансы Просто failed attempt 1 (a
  415-word passage the script does not contain, at 58%) and passed after
  one re-synthesis — the Ep605 class, caught before publish.
- **No model fallback on the digest stage**; one script-stage fallback
  (Omni View, §2). Prediction Markets' 4.7 digest took 363 s (61% of the
  timeout); five structural retries ran 100-343 s.
- **Workflows:** 37 Run Podcast Show runs (25 episode jobs; the rest
  gate-skipped duplicates), 12 Nerra Daily runs (1 build), 12 multilingual
  runs (1 cancelled, 2 still running at read time). The repeated
  "Multilingual: tesla" commits are bookkeeping (scheduled comments, the
  claims page's 30-day window), not re-translation.

## 2. Findings, and what shipped

**Omni View's grok-4.7 script arm never ran (P0 for the record).** The
credit files' per-call model shows grok-4.3 wrote all 14 Omni View
scripts since 09-22: every 4.7 call timed out (the request does not
stream; Ep196's took 621 s) and fell back. `llm_script_model` recorded
the configured model, so two register readings (09-30 "9/9 on 4.7",
10-04 "17.6% verbatim") described 4.3 and 4.6 episodes. On grok-4.6
(09-10..21) the script copied a median 8-17% of the digest at 76-85%
coverage; on the 4.3 fallback ~59%. **Shipped:** Omni View back on
grok-4.6; `llm_script_model` records the SERVED model and
`llm_script_model_fallback` the reason; register and CLAUDE.md corrected.
⚠️ AUDIO — A/B-listen the next Omni View.

**Offshore North aired a February article as this week's news.** IMOCA's
Charal refit page has no meta date and prints `2/10/26` (US order, which
the same page's cards prove) under the headline; xAI's search read it as
2 October and the page probe could not read it. Network-wide the probe
dated 102 of 150 fetchable cited pages; two misses were a 200k-character
search limit on 1.1-1.4 MB pages. **Shipped:** the date search reads
1.5M characters, a LABELLED visible date ("Submitted on", "Published",
"Posted", "Date:" — never "Updated") is the fallback after the structured
fields, and imoca.org's header date is read month-first. Replay: 127 of
150 dated, the Charal page as 2026-02-10, no previously dated page
changed.

**The Mira phone claim was still live in five places** — the Nerra Daily
links prompt, its reflection rotation (`engine/daily_edition.py`), the
registry's `about_host`, and both Age of AI system prompts. Ep046's
sign-off aired "When I phone people for The Age of AI". **Shipped:** all
five corrected; a guard sweeps prompts, registry, edition code and
templates (the old guard read only the promo rotation). ⚠️ AUDIO — Mira's
self-description.

**Финансы Просто's newsletter had not sent in eight episodes.** Its
`brand_color_dark` (#DB2777) is lighter than its brand colour and reads
4.39:1 on the featured card, so the contrast check refused every send.
**Shipped:** #9D174D; a guard checks every show's eyebrow colour (31/31
clear 4.5:1).

**MIT had two picks that could never close.** HPS.A (TSX class A) went to
Yahoo verbatim and 404'd daily for 40 days on a one-session flash
horizon; BMWYY has no Yahoo data at all. The evaluator's own comment
promised to void a dead pick and nothing did. **Shipped:** dotted share
classes map to Yahoo's form (HPS-A.TO, BRK-B; exchange suffixes untouched),
and an open pick with no bars 14 days after its date is voided as
`market_data_unavailable`. HPS.A closes on real bars at the next
evaluation; BMWYY voids on 10-14.

**Env Intel on a thin day.** It used the prompt's own low-content format,
failed "Lead Story missing" (that format has no such heading), spent the
structural regeneration, dropped the Compliance Brief, and narrated three
empty sections for ~200 words. **Shipped:** the validator accepts the
low-content Deep Dive as the lead; the prompt leaves an empty section out
and keeps the Compliance Brief (⚠️ AUDIO); the absence filter is on for
Env Intel and Offshore North (replay: it removes exactly the "nothing
appeared" sentences and Offshore North's banned "no new posts in the past
seven days").

**Nerra Daily's title fell back** to the lead show's clipped hook for the
first time in 20 editions; nothing logged why. **Shipped:** the rejected
title (or its absence) is logged.

## 3. Read, not changed

- **Claims coverage floor (shipped 10-04): working.** It added verified
  claims on 7 of 12 shows it ran on (M&A +10, FF +4, PT +4, OV +2, EI,
  MIT, Tesla +1). Tesla verified 1 of 10: most of its items cite Reddit
  threads whose text holds no quotable claim — a sourcing question.
- **Script copying:** the 4.3 two-pass flagships copy 56-79% of the
  digest (9 shows warned); the 4.7 combined cohort 2-15%. Unchanged
  finding; the Omni View correction removes the one data point that
  pointed at a 4.7 script pin as the fix.
- **Hook leads the body:** median ~23 on the nine English news shows
  (target 40, readout 10-24); MIT 0 (disclaimer placement — operator).
- **19 shows under their script word target** — the digest ceiling, not a
  podcast-side lever (banned).

## 4. Operator items surfaced

1. **X posting returns 402 Payment Required on the @planetterrian app**
   (Fascinating Frontiers, Planetterrian, Unintended Consequences);
   @teslashortstime posts normally. Check that app's credits/billing in
   the X developer portal.
2. **Ten launch-cohort newsletters refuse to send**: their Buttondown tags
   do not exist yet (a tag exists only once someone subscribes with it).
   Creating the tags in Buttondown makes the sends go out (to zero
   subscribers until signups arrive).
3. **The weekly newsletter catch-up** has not been run (Tesla, SpaceX,
   Planetterrian and UC still have no Oct 4 weekly).
4. `PERSONAL_BATCH_DISPATCH_TOKEN` is still unset (Nerra Personal waits for
   its fallback cron).
