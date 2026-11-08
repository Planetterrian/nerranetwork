8/10 episodes now miss the Tomorrow Teaser chapter marker as varied teaser openers outrun the pattern; almanac/anniversary leakage and spoken section labels persist while 7/10 scripts stay under the digest ceiling—propose metadata teaser-pattern broaden plus narrow residual title filters, and escalate multi-miss almanac/section-label/length levers rather than re-filing identical prompt pressure.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1990**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| spoken digest section labels in next 10 _tts.txt (Top 12/15, Cosmic Spotlight, Cosmic Deep Dive, bare Fascinating Frontiers as headers) | miss | Density copied-section rows on ep239/240/242; WHAT-TO-SKIP harden never merged |
| deep dive restating a body-covered named mission/team/finding (manual, next 10) | partial | ep244–247 EN deep dives mostly concept-led (Enceladus/M30/tidal heating); Oct Shapiro/FRB second-pass less evident; measure lint live |
| title-pattern hits for night-sky-highlights / reaches-opposition / first-photos-of-moon residual classes in next 10 digests | miss | ep242 November Night Sky Highlights chapter; ep240 Lion overnight planets; ep247 David Gill 1882 snapshot pattern hit |
| pure birthday / personality-profile / award-ceremony / amateur-tool-meta items in Top-12 digests | partial | Fewer pure birthdays; ep245 CSC museum expansion + ep247 Port Air Space Day/expo PR still ship |
| successor teaser-tic single-shape rate in next 10 _tts.txt | hit | Varied openers (Before we go / date-led Flight 15 / next hard date / next episode will); no shape ≥6/10 |
| episodes below 1700-word floor (digest-ceiling trajectory; no podcast-side lever) | hit | 7/10 ep238–247 under 1700w (1430–1648 on misses); ceiling still digest-side |
| Episodes with Introduction present and Tomorrow Teaser immediately before Closing | miss | Only ep238+ep244 have Teaser→Closing; 8/10 chapters skip Tomorrow Teaser entirely |
| ephemeris/sky-almanac/this-day-in-history items in FF Top-15 digests | miss | ep240/242 night-sky packages + ep247 1882 Gill anniversary still in digests/audio; dual-layer backstop never merged |
| occurrences of verbatim teaser opener 'Keep an eye on' in next 10 _tts.txt | hit | Snapshot no cross-ep keep-an-eye above threshold; frame_memory desaturation holding |
| 0 market-action items / 0 launch false-drops (June-16 lineage holding) | hit | No SPCX/IPO/funding ticker in ep244–247 EN; mission/launch coverage retained |
| prompt example transition in a shipped transcript | hit | No 'Now, on a completely different note…' in ep244–247 EN transcripts |
| source_integrity_claims median | miss | n/a-lever-not-scored: claims counts absent from snapshot bundle |
| episodes with more than half the items source-less after the retry | miss | n/a-lever-not-scored: per-item Source lines not in snapshot bundle; lint opted-in in YAML |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/fascinating_frontiers_digest.txt`** (prompt) — Ep245 spent a long mid-episode block on California Science Center expansion logistics; Ep247 aired Hancock County Port Air Space Day and KSC expo-rivalry PR — weak substrate and off-brand vs mission/discovery selection (same family as Oct ep218 profile/medal/meta).
```diff
- - **Curation**: Prefer concrete mission updates, discoveries, research results, and instrument/launch milestones. Avoid "year in review", listicles, awards, or opinion pieces — never to reach a count.
+ - **Curation**: Prefer concrete mission updates, discoveries, research results, and instrument/launch milestones. Avoid "year in review", listicles, awards, or opinion pieces — never to reach a count. Drop pure museum-opening / gallery-tourism copy, local STEM open-house or school space-day announcements, and air-show/expo scheduling PR unless the item carries a concrete mission hardware result, instrument finding, or research number; those belong in a travel section, not a science briefing.
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/fascinating_frontiers.yaml`** (config): 8/10 ep238–247 chapters skip Tomorrow Teaser because frame_memory correctly varied openers past June-24 anchors (Ep245 date-led Flight 15; Ep246 'next hard date'; Ep247 'next episode will'). Metadata-only; Closing stays listed before Teaser; where:end retained. Highest-yield deterministic fix this window.
- **`shows/fascinating_frontiers.yaml`** (config): Incremental residual title tighten for ep242-class 'November Night Sky Highlights' packages and ep247-class first-photograph anniversary headlines still reaching digests. No bare planet names, no bare 'passes near' (June-16 Falcon-9 lesson). Full digest almanac backstop escalated separately after multi-pass non-merge misses.

## Deferred (carried forward)
- OPERATOR DECISION (escalate since 2026-06-12): Cosmic Deep Dive thin-day depth enforcement vs accept ~1400–1650w podcasts — digest already specs 450–550w from fetched text; verify shipped section word counts next pass. No podcast-side word pressure (do_not_retry).
- OPERATOR DECISION (escalate after Aug-9→Oct-12 identical dual-layer filings missed while never merging): full NO SKY-ALMANAC / NO THIS-DAY-IN-HISTORY digest backstop beside NO STOCK — drop viewing calendars, shower-peak guides, pure anniversaries, monthly night-sky packages; keep space-based eclipse science and real mission milestones.
- OPERATOR DECISION (escalate after Oct-5 + Oct-12 identical filings): podcast WHAT-TO-SKIP verbatim ban on speaking Top 12/15, Cosmic Spotlight, Cosmic Deep Dive, bare Fascinating Frontiers as headers — do not re-file identical prompt harden.
- OPERATOR DECISION: data-side teaser-frame memory extension if a successor opener later hits ≥6/10 — do not re-file prompt-only keep-an-eye de-seed (desaturation already holding via frame_memory).
- Align min_podcast_words down to ~1500 to silence every-episode script_below_target — cosmetic ops choice, does not add facts.
- Mid-section digest-driven chapter titles (network lever; Spotlight/Deep Dive markers rarely fire because prompt forbids announcing them).
- Theme residual 'science nasa' (low-harm adjacency / bare science.nasa.gov).
- Curated narrative-tracker status pass (operator task: scripts/update_tesla_narrative.py --slug fascinating_frontiers).
- review_snapshot.py missing-Teaser-before-Closing detector (Ep209/219/239–247 false 'clean') — network tooling owner.
- Aggressive brand-level telescope product title bans — try digest curation first.
- Routine comsat/Falcon cadence de-prioritization vs SpaceX Daily (editorial monitor).
- Score Sep-24 source_integrity_claims median and items_without_source with digest sidecars next pass.
- Score deep_dive_distinct_measure / deep_dive_fetched_source firing rates once structural-regen share allows promoting measure→fire.

## Drift-guard status
```
============================= test session starts ==============================
collected 17 items

tests/test_fascinating_frontiers_quality_pass.py .................       [100%]

============================== 17 passed in 0.30s ==============================
```

<sub>tokens: 80150 in / 6449 out</sub>