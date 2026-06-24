# Fascinating Frontiers — Quality Review (June 24, 2026)

Third scheduled-agent review of Fascinating Frontiers (FF). Scores the June 16
pass ([`fascinating_frontiers_review_2026_06_16.md`](fascinating_frontiers_review_2026_06_16.md))
against the episodes shipped since (Ep104–111) and attacks the next tier.
Snapshot: `scripts/review_snapshot.py fascinating_frontiers`.

/ TLDR /
- **June-16 stock-filter predictions: one HIT, one PARTIAL.** The deterministic
  fetch-time filter works perfectly on **dailies** — Ep104/105/106/107/109/110/111
  digests all carry **0** market-action items, and no launch/mission story was
  false-dropped (HIT). But the **Sunday weekly recap Ep108 (June 21)** re-surfaced
  the SPCX `$85.7B` funding round, greenshoe option, and `$2.5T market cap` —
  spoken aloud on a science show — because the recap synthesizes from the
  **content lake**, which still held the pre-filter Ep103 (June 16) content. The
  fetch filter never sees recap content (PARTIAL). Self-healing next cycle
  (Ep103 leaves the 7-day window June 22) — deferred with a scored prediction
  rather than touching the shared recap module.
- **New P0 (this pass's headline): the orphan-Closing chapter bug.** The snapshot
  reports "10/10 clean chapters" but its `chapter_issues` check only flags
  duplicate/too-few titles — it never checks for a **missing Closing**. Direct
  inspection of the committed `chapters_ep*.json` shows **Ep110 and Ep111 shipped
  with NO Closing chapter** (both ended on "Tomorrow Teaser"), and **Ep109 shipped
  a spurious, out-of-order "Cosmic Deep Dive" chapter after the sign-off**. Fixed
  deterministically (metadata-only, no audio change) — the exact orphan-closing /
  marker-ordering class every other show pass has fixed (EI June-11, SpaceX
  June-18, First Principles June-23).

---

## Scoring the June-16 pass (predictions)

| Prediction | Verdict | Evidence |
|---|---|---|
| 0 market-action items in any FF digest after merge | **partial** | Dailies clean (Ep104–111 daily digests: 0 stock hits). **Ep108 (Sunday recap)** spoke the `$85.7B` funding round + greenshoe + `$2.5T market cap` (`Fascinating_Frontiers_Ep108_20260621.md:7-13`) — pulled from the content lake's pre-filter Ep103 content, which the fetch filter doesn't touch. |
| 0 launch/mission/Dragon/contract titles false-dropped | **hit** | Ep111 kept Falcon 9, the SpaceX microgravity vehicle, the Boeing satellite contract, and Starliner; no recent daily is missing legitimate SpaceX mission coverage. The bare `nasdaq` pattern was removed pre-merge; no false-positive launch drop observed. |

The `science nasa` theme residual (carried since June 12) **persists** — still
deferred (generic adjacency / bare `science.nasa.gov` domain; filtering risks
real content).

---

## P0 — orphan-Closing + marker-ordering chapter bug *(shipped, metadata-only)*

**Evidence (committed chapter JSONs):**

| Episode | `chapters_ep*.json` titles (tail) | Problem |
|---|---|---|
| Ep108 | `… 'Closing'` | OK |
| Ep109 | `'Introduction','Tomorrow Teaser','Closing','Cosmic Deep Dive'` | **Cosmic Deep Dive after the sign-off** — out of order |
| Ep110 | `… 'Tomorrow Teaser'` | **NO Closing chapter** |
| Ep111 | `… 'Tomorrow Teaser'` | **NO Closing chapter** |

**Root cause** (parser mechanics in `engine/chapters.py:152-174`: line-by-line
scan, first marker per line wins, each title once, chapters ordered by script
position):

1. **The sign-off line is "…I'll *see you next time*"** — present in every
   episode's closing block. The Tomorrow Teaser pattern was `Before we go|Next
   time`, so `Next time` matches the sign-off line. With Tomorrow Teaser listed
   **before** Closing in the YAML, the sign-off line was titled "Tomorrow Teaser"
   and the Closing chapter was lost (Ep110/Ep111).
2. **6 of the last 8 teasers open "Keep an eye on…" / "Watch for…"** (podcast
   prompt line 122) — neither matched the old pattern, so the *real* teaser line
   never got a chapter; the only "Tomorrow Teaser" chapter was the stolen
   sign-off line.
3. **The bare `deep dive` pattern** (in the Cosmic Deep Dive marker
   `cosmic deep dive|deep dive|under the hood`) only ever matched the
   network-family cross-promo *"your daily **deep dive** into everything Tesla"*
   (Ep109) — the podcast prompt forbids announcing the section aloud (line 118),
   so it never fires legitimately (0/8 episodes). That produced a spurious,
   post-sign-off "Cosmic Deep Dive" chapter.

**Fix (`shows/fascinating_frontiers.yaml`, chapters block — deterministic, no audio/prompt change):**
- **List Closing before Tomorrow Teaser** so Closing wins the shared sign-off
  line (the EI June-11 / SpaceX June-18 / First-Principles June-23 ordering rule;
  chapter order is by script position, so this only changes which *title* the
  sign-off line gets, never chronology).
- **Broaden the Tomorrow Teaser pattern** to `Before we go|Next time|^Keep an eye
  on|^Watch for` — the two new openers are **line-anchored (`^`)** so mid-body
  forward-looking phrasing ("…as we *watch for*…", "*Watch for* the next Ariane 6
  mission" in the news body, Ep105) can't claim the title; the `where: end`
  window already restricts to the sign-off region.
- **Drop the bare `deep dive` + `under the hood`** from the Cosmic Deep Dive
  marker, keeping only the literal `cosmic deep dive` label.

**Verification against the real shipped scripts** (re-parsed Ep108–111 `_tts.txt`
with the new markers):

```
Ep108: … 'Tomorrow Teaser', 'Closing'   (was: … 'Closing')
Ep109: … 'Tomorrow Teaser', 'Closing'   (was: …'Tomorrow Teaser','Closing','Cosmic Deep Dive')
Ep110: … 'Tomorrow Teaser', 'Closing'   (was: … 'Tomorrow Teaser'   ← no Closing)
Ep111: … 'Tomorrow Teaser', 'Closing'   (was: … 'Tomorrow Teaser'   ← no Closing)
```

All four now end `Tomorrow Teaser → Closing` in correct order; the Ep109 spurious
Cosmic Deep Dive chapter is gone.

**Guards:** `tests/test_fascinating_frontiers_quality_pass.py::TestChapterClosingOrdering`
— Closing precedes Tomorrow Teaser in YAML; the bare-`deep dive`/`under the hood`
cross-promo doesn't open a Cosmic Deep Dive chapter (literal label still does);
a realistic ~1600-word "Keep an eye on…" + sign-off script yields both Tomorrow
Teaser and Closing in order; a "Next time…" teaser + Tesla "deep dive" cross-promo
ends on Closing with no orphan chapter.

> The mid-section chapters remain raw auto-segment fragments
> ("Infrared observations pierce thick lanes of dust to map…") because the
> Cosmic Spotlight / Cosmic Deep Dive markers don't fire (the prompt forbids
> announcing the sections). That is the network-wide **digest-driven chapter
> titles** lever (Tesla/M&A/SpaceX-deferred) and is unchanged here — this pass
> only repairs the head (Introduction) and tail (Teaser + Closing) anchors.

---

## P1 — chronic under-length *(carried forward, still deferred)*

Snapshot: Ep102–111 all below the 1700 floor (1317–1678w, median ~1470). This is
the same digest-ceiling problem the June-12 pass verified and the `do_not_retry`
ledger entry bars attacking via prompt pressure. The only legitimate lever
(expanding the **Cosmic Deep Dive**, the one section licensed to use the model's
own astrophysics knowledge) remains deferred behind the operator's four-show
length A/B. **New supporting evidence this pass:** the LLM already pads by
*duplicate-covering single digest items* — Ep111 covered the digest's #14
(Embry-Riddle) twice (`_tts.txt:137-145` generic, then `147-153` named, the second
pass inventing "integrates propulsion hardware testing with avionics software
validation") and #15 (Space Coast manifest) twice (`155-163`, then `165-167`),
violating the prompt's own "NEVER retell a story you already covered" rule (line
76). Tightening that rule would shorten episodes further, so it stays tangled with
the deferred length lever — flagged, not fixed, to avoid confounding the A/B.

---

## P1 — Sunday weekly-recap stock leak *(deferred with scored prediction)*

The June-16 fetch filter is fetch-time only; `engine/weekly_recap.py` synthesizes
the Sunday episode from the **content lake** (past 7 days of committed digests),
which the filter never touches. Ep108 (June 21 recap, window June 15–21) therefore
re-surfaced the SPCX funding round from the pre-filter Ep103 (June 16). Going
forward, dailies filter stock at fetch, so the lake stops accumulating stock
content and **the next FF Sunday recap (Ep115, ~June 28, window June 22–28 —
excludes Ep103) should be stock-clean with no code change**. Deferred rather than
patching the shared recap module on a self-healing single event; scored below. If
Ep115 still carries market-action content, the next pass attacks the recap path
directly (a scope guard in the recap host-framing, or honoring the show's
`exclude_title_patterns` against episode bodies).

---

## P2 — growth / discoverability

No new action. Hook-led X teaser, per-episode blog title, value-prop RSS
description verified holding. The chapter fix above *improves* discoverability
indirectly (podcast apps that surface chapters now show a proper Closing on every
episode).

---

## Meta — snapshot chapter check is too loose *(recommendation, not shipped)*

`scripts/review_snapshot.py:chapter_issues` flags only duplicate titles, multiple
Introductions, and too-few chapters. It missed this entire orphan-Closing class
("10/10 clean" while two episodes had no Closing and one was out of order). A
future `network` pass should add a check: when a show's markers declare a
`where: end` "Closing"-class title, flag any episode whose chapter list lacks it
or whose last chapter isn't the closing. That would have caught this mechanically
across every show. Left for the network/playbook owner (shared tooling change).

---

## Findings checked and dismissed (for the record)

- **"NAIR-uh NET-work" in the spoken closing** (`_tts.txt`, the network-family
  block) — a pre-existing, intentional brand respelling in
  `assets/pronunciation.py:341` (`Nerra Network → NAIR-uh NET-work`). Whisper
  hears "NARA Network" (≈ the intended /ˈnɛrə/), i.e. it's working. NOT a
  landmine-#17 violation to remove — it's an operator-blessed pronunciation, and
  removing it would *regress* the brand pronunciation. Left untouched.
- **Mid-body "watch for" / "keep an eye"** (Ep104 line 143, Ep105 lines 13/61) —
  forward-looking news phrasing, not teasers. Handled by line-anchoring the new
  teaser patterns + the `where: end` window (verified: the broadened pattern does
  not claim these lines).

## Shipped this pass

| Change | File | A/B needed? |
|---|---|---|
| Chapter markers: Closing before Tomorrow Teaser; broaden teaser to `^Keep an eye on`/`^Watch for`; drop bare `deep dive`/`under the hood` | `shows/fascinating_frontiers.yaml` | **No** (metadata-only; no audio/prompt change) |
| Drift guards | `tests/test_fascinating_frontiers_quality_pass.py::TestChapterClosingOrdering` | — |

## ⚠️ A/B-listen required (landmine #17)

**None.** The chapter-marker change is metadata-only — it alters the
`chapters_ep*.json` navigation file, not the spoken audio, the script, or any
prompt. Verified by re-parsing the four real shipped scripts (no script text
changes).

## Tests

`pytest tests/test_fascinating_frontiers_quality_pass.py tests/test_prompt_fidelity.py
tests/test_episode_validity.py tests/test_four_show_quality_pass.py
tests/test_network_quality_pass.py tests/test_schedule.py` — **169 passed, 1
failed**. The single failure (`test_queue_has_runway[first_principles-7-3.0]`,
2.9 vs 3.0 weeks) is an **unrelated** First Principles topic-queue restock item
(no FF file touched); flagged for the operator, out of scope for this review.
Plus a live re-parse of Ep108–111 against the new markers (above).
</content>
</invoke>
