Post-July-31 digest length lever is working on the two newest episodes (ep62/63 both >1000w) but the 10-ep window is still 7/10 under floor; the third-generation deep-dive opener tic partially cleared by drift while a 'Consider a…' successor converged; highest-yield fixes are TTS garble/pronunciation (Simpcw, Kincardine, Terrace/Kamloops, spoken underscore/hyphen, The Tyee) plus banning spoken absence-of-news lines that shipped in ep57.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1165**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes below min_podcast_words:900, last 10 | partial | Still 7/10 under floor in ep54–63, but 2/2 post-July-31 digest-lever episodes (ep62=1023w, ep63=1021w) cleared 900+; pre-lever shorts dominate the window. |
| transcripts using 'There's a nuance here worth understanding' as deep-dive opener, last 10 | partial | 4/10 (ep54–57 only; absent ep58–63). July-27 menu-removal never shipped; successor opener 'Consider a…' now 4/10 (ep58/60/62/63). |
| episodes whose LAST chapter is Closing (chapters_ep*.json) | hit | 10/10 of ep54–63 end with title Closing after the July-2 marker reorder. |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/env_intel_podcast.txt`** (prompt) — Locks three verified P0/P1 classes: (1) fourth-generation deep-dive opener convergence on 'Consider a…' after nuance partially cleared by drift; (2) ep57 spoken empty-section failure mode; (3) 'Tomorrow' cadence on an odd-weekday show. De-seed by shape + verbatim ban + MEMORY per July 2026 ledger rule — no quotable replacement example.
```diff
- [Compliance Brief — 20-30 seconds]
- - If the briefing has a "Compliance Brief" section, deliver it crisply as the calendar headline: the top regulatory change (with jurisdiction), the one immediate action, and the deadline. Frame it like "If you only note one thing today for your compliance calendar: …". Don't read the bullet labels aloud — speak it naturally. Then move on; full detail comes in the Lead Story.
+ [Compliance Brief — 20-30 seconds]
+ - If the briefing has a "Compliance Brief" section, deliver it crisply as the calendar headline: the top regulatory change (with jurisdiction), the one immediate action, and the deadline. Frame it like "If you only note one thing today for your compliance calendar: …". Don't read the bullet labels aloud — speak it naturally. Then move on; full detail comes in the Lead Story.
+ 
+ DEEP-DIVE OPENER — DE-SEED BY SHAPE (do not read this header aloud):
+ - NEVER open the Practitioner Deep Dive with any of these verbatim or near-paraphrase frames (banned — they became every-episode tics): "There's a nuance here worth understanding…", "You arrive at a…", "here's something I wish someone had told me…", "Consider a [client/proponent/contractor/facility]…", "Picture a…", "A client calls…".
+ - Open by shape, not example: drop straight into the concrete field situation (jurisdiction + medium + the wrong assumption) in one sentence, with no meta-frame announcing that a nuance/lesson follows. Rotate entry mechanics across episodes (wrong baseline, mismatched certificate vs CSR, consent gate vs sequential consultation, smoke-skewed lab spike, etc.) and do NOT reuse an opener shape from the prior 5 episodes if the briefing memory lists them.
+ - Still land the signature beat later: most-common-mistake + fix (required so chapter markers fire). Do not drop the Deep Dive on thin days — shorten body sections instead.
+ 
+ ABSENCE / EMPTY-SECTION BAN (do not read this header aloud):
+ - NEVER narrate that a section has no content. Forbidden spoken shapes: "No qualifying… appeared today", "No major… appeared", "No peer-reviewed…", "No industry developments…", "With limited additional regulatory developments… the focus shifts to…" as a substitute for substance. If a section is empty, omit it silently and spend the time on the Deep Dive, forward calendar, or a second jurisdiction.
+ - NEVER speak URLs, domain names, or "Source:" lines.
+ 
+ TEASER CADENCE:
+ - Prefer "In the next briefing, watch for…" / "Before we wrap…". Avoid "Tomorrow, watch for…" (this show is every other weekday, not daily).
```

**`shows/prompts/env_intel_digest.txt`** (prompt) — Podcast faithfully echoes digest deep-dive openers (June-15/July-2/July-27 lineage). Digest is the seed surface; de-seed here or the podcast ban alone will lose. Also hardens thin-day double-tell and Canada Gazette / proper-noun spelling at source.
```diff
- (Practitioner Deep Dive / Practice Spotlight seed language that still permits or models framed openers such as nuance-worth-understanding or Consider-a scene frames — exact seeded sentence varies by prior partial edits around the deep-dive section; remove any remaining quotable opener examples.)
+ PRACTITIONER DEEP DIVE / PRACTICE SPOTLIGHT — ENTRY RULES:
+ - Write the deep-dive body as a concrete field situation (jurisdiction, medium, the wrong assumption, the corrected practice). Do NOT open with a meta-frame.
+ - VERBATIM BAN on these openers and close paraphrases (they shipped as every-episode tics): "There's a nuance here worth understanding", "You arrive at a…", "Consider a [client/proponent/…]", "Picture a…", "A client calls…", "here's something I wish someone had told me".
+ - Do not give the model a quotable example opener. Describe only the required ingredients: setting, mistaken assumption, evidence that falsifies it, most-common-mistake sentence, fix sentence.
+ - REQUIRED every episode including thin-news days (Practice Spotlight may carry it): one "most common mistake" + one "fix" beat so the podcast chapter marker still fires.
+ - Thin-day rule (reaffirmed): one story anchors AT MOST TWO sections; diversify with forward calendar / second jurisdiction / deep-dive topic — never re-tell the same certificate or consultation four times.
+ - Always write Canada Gazette (never "Federal Register") for federal instruments; always name provinces/territories with standard spellings (Simpcw, Kincardine, Kamloops, Terrace, The Tyee).
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/hooks/env_intel.py`** (code): Highest-yield category (~100% hit historically). ep58 mangled Simpcw six ways; ep61 Kincardine three ways; ep59 Terrace→terrorists, Kamloops→cam loops; ep54 Tyee→TAE; ep55 Nerra→Narrow. Extend the existing hook channel only — no prompt phonetic injection.
- **`engine/generator.py`** (code): ep54 shipped hyphen/underscore read as words and a spoken URL despite prompt bans. Prompt-only bans have incomplete hit rate on this class; a deterministic sanitizer + drift-guard is the garble-restore pattern that historically hits ~100% and needs no A/B.
- **`tests/test_env_intel_quality_pass.py`** (code): Every behavioral fix gets a drift-guard per playbook; pins the length-lever policy so a future pass cannot reintroduce podcast_expand_below_target (meta-review miss class).

## Deferred (carried forward)
- Digest-driven / position-aware mid-section chapter titles (shared engine; carried since 2026-06-10) — ep56 missing Deep Dive chapter and ep60 collapsed mid-markers are symptoms but full fix is cross-show.
- Numbers/dates spell-out drift (Protocol 4, digit dates, 'PM, 2.5' comma pause) — landmine #17; needs A/B before any repair layer; never phonetic injection.
- If next 5+ post-lever episodes median still <900w: operator decision on raising min_digest_words further and/or full-text article fetch / licensed-knowledge floors — do NOT re-file podcast-side length levers (escalate, don't repeat).
- French-language / QC-SK-Atlantic source coverage gap vs Phase-4 web_search_queries promise (operator/editorial).
- OP3 download collapse [20,21,10,3] — distribution/discoverability operator review (Apple/Spotify/YouTube Shorts), not a prompt change this pass.
- Thin-news blog <title> intelligence re-score — no clean post-fix absence-hook episode observed in ep54–63 window.

## Drift-guard status
```
============================= test session starts ==============================
collected 23 items

tests/test_env_intel_quality_pass.py .......................             [100%]

============================== 23 passed in 0.47s ==============================
```

<sub>tokens: 39187 in / 6360 out</sub>