# Environmental Intelligence — quality review (2026-06-15)

Third pass on **env_intel**, scoring the two prior passes
([`2026-06-10`](env_intel_review_2026_06_10.md),
[`2026-06-11`](env_intel_review_2026_06_11.md)) against the first genuinely
post-merge, normal-news episode (**Ep045**, 2026-06-15) and attacking the
next tier: a boilerplate-tic in the Practitioner Deep Dive that the chapter /
cadence / length passes never touched.

Snapshot baseline (`scripts/review_snapshot.py env_intel`): 9/10 episodes
below the 900-word target (but the misses are thin-news days with the
intentional 450-word floor); 4/10 with duplicate chapter titles (all *pre*
June-10 fix); cost ~$0.077/ep; OP3 9 dl/7d, 27 dl/30d.

## Scoring the prior predictions

| Prediction (source) | Verdict | Evidence |
|---|---|---|
| 0 episodes shipping with no Closing chapter (Jun 11) | **hit** | Ep045 (first true post-merge episode) chapters: `[Introduction, Science, Reg, Action Items, Week Ahead, Tomorrow Teaser, Closing]` — Closing present and last. The Jun-11 marker reorder (Closing before Tomorrow Teaser) works. (Ep039/042/043/044 lack it but all predate the merged fix.) |
| 0 absence-of-news digest HOOKs (Jun 11) | **hit** | Ep045 hook = "Newfoundland advances 25-year fish sauce site remediation requiring 200 dump-truck trips in St. Mary's." A real story, not an absence statement. No thin-day episode shipped post-fix to stress-test, but the mechanism is live. |
| Thin-news blog `<title>` reads as intelligence (Jun 11) | **partial** | No post-fix thin-news day to observe; Ep045 was a normal day. Carry forward. |
| 0/10 duplicate/misordered chapter titles (Jun 10) | **hit** | Ep041–045 all clean; the 4 duplicate-title episodes in the snapshot (036/037/038/040) all predate the Jun-10 anchors. |
| median `_tts.txt` words ≥ 900 (Jun 10) | **partial** | Last-10 median 814.5 — dragged down by thin-news days (Ep037=493, Ep043=594) that ship intentionally short under the 450 floor. Normal-news days now clear it: Ep042=922, Ep045=958. The chronic shortfall on thin days is the deferred digest-ceiling issue (same root cause as FF/UC), not a regression. |

## P0 — listener-facing bugs shipping today

None. Ep045 shipped clean: correct chapter shape with a Closing chapter, a
real forward-looking hook, cadence-neutral spoken closing ("We'll be back
with the next briefing"), 958 words.

## P1 — quality ceiling

### 1. Practitioner Deep Dive opens with the same "You arrive at a…" scenario every episode
The single strongest cross-episode tic the snapshot surfaced ("you arrive at
a" in 8/10 transcripts). Verified: the Deep Dive opened with the verbatim
construction **"You arrive at a…"** in **9 of the last 10** episodes
(Ep036–045, every one except the short Ep043) —

- Ep044: *"You arrive at a former industrial site in southern Ontario…"*
- Ep045: *"You arrive at a former fish-processing facility on the Newfoundland coast…"*
- Ep042: *"you arrive at an oilsands lease…"*
- Ep041: *"you arrive at a mid-sized Alberta municipality…"*

Root cause is the **digest** prompt, not the podcast prompt:
`shows/prompts/env_intel_digest.txt:173` seeded the literal example
*"You arrive at a former gas station site…"*, so the digest's Deep Dive
section opened "You arrive at a…" in 6/6 recent digests and the podcast —
told to use only the briefing — faithfully echoed it. Confirmed by render:
even with a reworded *podcast* prompt, the regenerated script still opened
"You arrive at a former fish-processing facility…" because the digest seeded
it. This is exactly the Omni View "strongest case" tic class (the Jun-10
network pass's root cause was the DIGEST seeding the literal lead-in).

A second, smaller seed: the podcast prompt offered the verbatim transition
*"here's something I wish someone had told me early in my career"* as its
first example (`env_intel_podcast.txt:145`) — it appeared verbatim in 5/10
transcripts.

**Shipped (prompt edits — A/B-listen):**
- `env_intel_digest.txt` — replaced the seeded "You arrive at a former gas
  station site" example with an instruction to **rotate the entry point**
  across episodes (a sampling result that doesn't reconcile, a closure
  letter under review, a regulator's question, a lab QA flag, a client's
  assumption to correct, a monitoring-dataset anomaly, or — only
  occasionally — a site walk), and names "You arrive at a…" explicitly as
  the tic to avoid. The structural format (scenario → science → most common
  mistake + fix) is the show's intentional B2B signature per the RSS
  description and is **unchanged** — only the verbatim opener rotates.
- `env_intel_podcast.txt` — same rotation guidance in the Deep Dive section;
  bans the repetitive "here's something I wish someone had told me…" lead-in
  and "You arrive at a…" opener.

**A/B evidence (digest prompt, `GROK_API_KEY` present).** Regenerated a fresh
digest via `run_show.py env_intel --test`:

- **Before** (Ep045, old prompt): *"**You arrive at a** former fish-processing
  facility on the Newfoundland coast where 110 vats of concentrated fish
  sauce have sat for 25 years…"*
- **After** (Ep046 test render, new prompt): *"**A Phase I ESA flags** a B.C.
  site within 5 km of a known glacial lake but the client's existing flood
  mapping stops at 100-year riverine events…"*

The opener rotated to a "Phase I ESA flag" framing — one of the menu entry
points — while keeping the same field-knowledge depth and the "most common
mistake / the fix" close. Render only; A/B-listen before fully trusting.

## P2 — growth / discoverability

OP3 remains low (9 dl/7d) and stable; X/YouTube are intentionally disabled
for this show, and the RSS channel description + Compliance Brief positioning
were rewritten in the June network pass. No P2 change this pass — the tic fix
is the higher-leverage work, and it incidentally improves variety for any
listener who samples consecutive episodes.

## Deferred (carried forward)

- **Digest-driven / position-aware mid-section chapters** (carried from Jun
  10/11). Mid-episode markers still match incidental keywords; a robust fix
  derives boundaries from digest section structure. Medium effort, shared
  across shows.
- **Numbers/dates spell-out drift.** Ep045 shipped `screened at 1 meters
  intervals` (grammatically "1 meters" — the digest writes "1 m" and TTS
  reads it as "one metres") and digit dates (`June 13`, `June 20`). Grok's
  server-side `text_normalization` handles ordinary numbers/dates, and
  Ep045 did NOT recur the Ep044 "Phase two and III" Roman-numeral mix
  (Ep045 was consistently "Phase II/two"). Genuine risk is narrow; landmine
  #17 forbids speculative programmatic text transforms without A/B evidence
  on the custom voice. Flag for a listen-check before building a repair
  layer.
- **Chronic under-length on thin-news days.** The digest is the ceiling
  (Ep045 digest 968w → podcast 958w; thin days run 586–654w digests). Same
  root cause + lever as FF/UC — the digest-expansion retry is the deferred
  network lever; the grok-4.3 plateau on a narrow content surface is
  accepted. Re-score median once 2–3 normal-news post-fix episodes exist.

## Tests

`tests/test_env_intel_quality_pass.py` gained `TestDeepDiveOpenerNotTic`
(3 tests): the digest prompt no longer seeds the "You arrive at a former gas
station" example, requires a rotated entry point, and the podcast prompt bans
the repetitive lead-ins. All 15 env_intel tests pass; smoke suites green:
`test_prompt_fidelity`, `test_episode_validity`, `test_generator`,
`test_four_show_quality_pass`, `test_chapters` (197 tests in the combined run).

## ⚠️ A/B-listen required (landmine #17)

Two prompt edits alter generated output:

1. **`shows/prompts/env_intel_digest.txt`** — Deep Dive opener now rotates
   its entry point instead of always "You arrive at a…" (before/after
   rendered above). Confirm the rotated openers read as natural field
   scenarios, not forced.
2. **`shows/prompts/env_intel_podcast.txt`** — same rotation guidance + bans
   the repetitive lead-ins. Confirm the deep dive still flows as an expert
   sidebar.

The structural Deep Dive format and the "most common mistake / the fix"
close are deliberately unchanged (the show's intentional B2B signature).
