# Environmental Intelligence — quality review (2026-06-11)

Second pass on **env_intel**, one day after the first dedicated pass
([`env_intel_review_2026_06_10.md`](env_intel_review_2026_06_10.md)). The
June 10 pass shipped the chapter `where` anchors, cadence-neutral spoken
copy, and a realistic length target. This pass scores those predictions
against the first post-fix episode (**Ep044**, 2026-06-11) and attacks the
two issues that survived: an orphaned Closing chapter (a *new* root cause)
and the deferred thin-news-day handling, which manifested in the worst
possible place — the episode headline.

Snapshot baseline (`scripts/review_snapshot.py env_intel`): 8/10 episodes
below the 900-word target; cost ~$0.076/ep; OP3 12 dl/7d, 26 dl/30d
(slightly up from last pass's 11/24). Only Ep044 is post-fix; Ep040–043 are
pre-fix and carry the old chapter/cadence behavior by definition (chapters
are computed at generation time, not retroactively).

## Scoring the June 10 predictions

| Prediction | Verdict | Evidence (Ep044, the only post-fix episode) |
|---|---|---|
| 0/10 duplicate/misordered chapter titles | **partial→hit** | Ep044 chapters clean: `[Introduction, Reg, Science, Action Items, Week Ahead, Tomorrow Teaser]` — zero duplicates. |
| 0 transcripts saying "daily"/"back tomorrow" | **hit** | Ep044 intro "Let's get into the latest…" (no "daily"); closing "We'll be back with the next briefing" (no "tomorrow" in cadence copy). |
| 0 episodes shipping with no Closing chapter | **miss** | Ep044 shipped with **no Closing chapter** — see P0 below. The June 10 fix (widened pattern + `where: end`) is necessary but not sufficient: a *new* root cause (teaser+closing merged into one paragraph) defeated it. Reopened and fixed differently this pass. |
| median `_tts.txt` words ≥ 900 | **pending** | Ep044 = 835 words, but it was a genuine no-news day; one episode is not a median. Re-score next pass. |

## P0 — listener-facing bugs shipping today

### 1. Closing chapter orphaned when Tomorrow Teaser + Closing merge into one paragraph
Ep044 shipped with **no Closing chapter** (last chapter "Tomorrow Teaser",
`chapters_ep044.json`). Root cause verified in
`Env_Intel_Ep044_20260611_tts.txt`: the LLM wrote the Tomorrow Teaser
sentence and the `{closing_block}` as **one paragraph** —

> Tomorrow, watch for any late Canada Gazette postings… **That's
> Environmental Intelligence for today.** If this briefing is useful…

`engine/chapters.py:parse_chapters` scans line-by-line and stops at the
**first** matching marker per line (`engine/chapters.py:168-171`). With
"Tomorrow Teaser" listed before "Closing" in the YAML, that merged line was
titled "Tomorrow Teaser" and the Closing never got its own chapter. This is
distinct from the June 10 orphan-closing bug (pattern coverage) — the
pattern matches fine; it just loses the line-level race.

**Shipped (config-only, no audio change):** reordered the two `where: end`
markers so **Closing precedes Tomorrow Teaser** in
`shows/env_intel.yaml`. On a merged line, Closing now wins → the standard
final chapter is preserved. On separate lines (the normal case) the closing
pattern doesn't match the teaser-only line, so **both** chapters are still
produced. Verified by re-parsing all 10 recent committed scripts: Ep044 now
ends on "Closing"; episodes that already had a Closing chapter (035–038,
041) are unchanged. (Ep039/042/043 still lack a Closing chapter, but those
are *pre-June-10* episodes whose old `"We're back tomorrow."` closing copy
was removed on June 10 — that copy is gone from future episodes, so the
issue can't recur there.)

## P1 — quality ceiling

### 2. Thin-news-day HOOK headlines the *absence* of news
The single most listener-facing defect this pass. Ep044's digest HOOK was:

> **No major Canadian regulatory announcements or enforcement actions
> appeared in today's feed.**

That string propagated to **every derived surface**:
- blog `<title>` + `<h1>`: *"No major Canadian regulatory announcements …
  appeared in today's feed — Episode 44"* (`blog/env_intel/ep044.html`) —
  actively tells a search visitor and a practitioner to skip;
- the chapter/episode title (`chapters_ep044.json`: *"Ep 44: No major…"*);
- the spoken opener (`…_tts.txt`).

The June 10 pass *deferred* thin-news handling, citing landmine #21 (don't
touch `min_articles_skip`). This pass takes a **different lever** that
doesn't touch the skip threshold at all: the digest prompt
(`shows/prompts/env_intel_digest.txt`) now forbids an absence-of-news hook
and steers thin days to lead the hook with the most consequential
forward-looking item the briefing supports (nearest deadline / consultation
close / effective date, or the Practitioner Deep Dive topic framed as
actionable intelligence). The LOW-CONTENT DAY STRATEGY block reinforces it.

**A/B evidence (digest prompt, `GROK_API_KEY` present).** Driving
`generate_digest` against a deliberately thin, non-qualifying news pool (the
Ep044 situation — international + US-state + general-awareness items only):

- **Before** (real Ep044, old prompt): `HOOK: No major Canadian regulatory
  announcements or enforcement actions appeared in today's feed.`
- **After** (new prompt): `HOOK: CCME soil vapour guidelines comment period
  closes in 19 days — vapour-intrusion assessors should review attenuation
  factors.`

The thin-day digest still delivers the same Compliance Brief / Deep Dive /
Week Ahead body; only the headline stops being a turn-off. This is a prompt
change → listen before fully trusting, but the rendered hook above is the
expected behavior.

## P2 — growth / discoverability

OP3 ticked up (11→12 dl/7d, 24→26 dl/30d) but remains low; X/YouTube are
intentionally disabled for this show and the RSS channel description +
Compliance Brief positioning were already rewritten in the June network
pass. The P1 hook fix is itself a discoverability win (it repairs the blog
SEO title on quiet days). No separate P2 change this pass.

## Deferred (carried forward)

- **Digest-driven / position-aware mid-section chapters** (carried from June
  10). Mid-episode markers still match incidental keywords; a robust fix
  derives boundaries from digest section structure. Medium effort, shared
  across shows.
- **Numbers/dates not always spelled out.** Ep044 shipped `O. Reg. 153/04`,
  `Phase two and III` (mixed word + Roman numeral), `1 July`, `22 June`,
  `2026` as digits despite the prompt's spell-out rule. Grok's server-side
  `text_normalization` handles ordinary dates/numbers, so most are safe; the
  genuine risk is the Roman-numeral "II/III" inconsistency. Not fixed —
  landmine #17 forbids speculative programmatic text transforms without A/B
  evidence on the custom voice; flag for a listen-check before building any
  repair layer.
- **Median length ≥ 900 on a normal-news day.** Re-score once 2–3 post-fix,
  non-thin episodes exist.

## Tests

`tests/test_env_intel_quality_pass.py` gained two classes (5 tests):
`TestClosingWinsOverTeaserWhenMerged` (Closing listed before Tomorrow
Teaser; a merged teaser+closing paragraph yields a Closing chapter; separate
lines still yield both) and `TestThinDayHookNotAbsence` (digest prompt
forbids an absence hook + steers thin days forward). All 12 env_intel tests
pass; smoke suites green: `test_prompt_fidelity`, `test_episode_validity`,
`test_generator`, `test_four_show_quality_pass`, `test_chapters` (188 tests
in the combined run).

## ⚠️ A/B-listen required (landmine #17)

One change alters generated output:

1. **`shows/prompts/env_intel_digest.txt`** — thin-news HOOK now leads with
   a forward-looking item instead of "no news today" (before/after rendered
   above). Confirm the new hook reads as genuine intelligence, not a
   stretched calendar note, on a real quiet day.

The chapter-marker reorder (`shows/env_intel.yaml`) is **config-only and
does not change audio** — it only changes which chapter title a merged
final paragraph receives.
