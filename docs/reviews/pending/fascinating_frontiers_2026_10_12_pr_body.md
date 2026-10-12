10/10 scripts remain under the digest ceiling; spoken digest section labels and anniversary/almanac filler still reach audio; Keep-an-eye is desaturated but successor teasers and missing Teaser chapters recur—escalate multi-miss almanac/teaser levers and propose only high-yield residual fixes (section-label ban, deep-dive entity harden, thin off-beat curation).

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1795**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| spoken digest section labels in next 10 _tts.txt (verbatim 'Top 15 Space', 'Cosmic Deep Dive:', 'Cosmic Spotlight' as headers) | miss | Density copied-section rows on ep211-213/215-216/219-220; Ep220 speaks 'Cosmic deep dive, house-based craft…'; Ep217 reuses Shapiro/FRB in deep-dive |
| title-pattern hits for night-sky-highlights / reaches-opposition residual classes in next 10 digests | miss | ep211 snapshot sky-highlights/opposition/meteor-peak hits + audio chapter; ep215 Luna-3 1959 anniversary pattern hit; YAML tighten never merged |
| deep dive restating a body-covered named mission/team/finding (manual, next 10) | miss | Ep217 body Shapiro dwarf galaxies + JWST FRB z=2.148 re-stated/expanded in deep-dive block |
| pure Reddit career / amateur-channel-meta / thin sports-PR items in Top-15 digests | partial | ep218 birthday/profile/medal/amateur-Claude beats still ship; ep212-class Reddit career less dominant this window |
| successor teaser-tic single-shape rate in next 10 _tts.txt | hit | keep-an-eye only ep217-218; ep219-220 Next-week/Watch-for; no single successor ≥6/10 |
| episodes below 1700-word floor (digest-ceiling trajectory; no podcast-side lever) | hit | 10/10 ep211-220 _tts.txt under 1700w (1025-1495); ceiling still digest-side |
| Episodes with Introduction present and Tomorrow Teaser immediately before Closing | partial | 9/10 Teaser→Closing; Ep219 chapters_ep219.json body→Closing only (Ep209-class recurrence) |
| ephemeris/sky-almanac/this-day-in-history items in FF Top-15 digests | miss | ep211 NASA October night-sky package; ep215 Luna-3 1959 + APOD; ep218 Schwarzschild 1873; dual-layer backstop never merged |
| occurrences of verbatim teaser opener 'Keep an eye on' in next 10 _tts.txt | partial | ep217-218 keep-an-eye; ep219-220 shifted; snapshot no cross-ep keep-an-eye above threshold — desaturated, de-seed never merged |
| 0 market-action items / 0 launch false-drops (June-16 lineage holding) | hit | No SPCX/IPO/funding ticker in ep217-220 EN audio; Falcon/Starship/Dragon mission coverage retained |
| prompt example transition in a shipped transcript | hit | No 'Now, on a completely different note…' in ep217-220 EN transcripts |
| source_integrity_claims median | miss | n/a-lever-not-scored: claims counts absent from snapshot bundle |
| episodes with more than half the items source-less after the retry | miss | n/a-lever-not-scored: digests/Source lines not in bundle; lint opted-in in YAML |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/fascinating_frontiers_podcast.txt`** (prompt) — Density audit shows copied section labels on most of ep211-220; Ep220 EN transcript speaks 'Cosmic deep dive, house-based craft match orbits…'. Existing skip line is too weak; verbatim ban targets the shipped failure without adding length pressure.
```diff
- WHAT TO SKIP (do NOT read aloud):
- - Daily Inspiration quotes — skip entirely
- - Section headers and separators — skip entirely
- - "Quick scan" lines — skip entirely
+ WHAT TO SKIP (do NOT read aloud):
+ - Daily Inspiration quotes — skip entirely
+ - Section headers and separators — skip entirely
+ - "Quick scan" lines — skip entirely
+ - Verbatim digest section labels — never speak "Top 12", "Top 15", "Top 15 Space", "Cosmic Spotlight", "Cosmic Deep Dive", or bare "Fascinating Frontiers" as a header or chapter announcement. Cover the science those sections hold; do not read the label aloud (shipped failure: scripts opening a block with "Cosmic deep dive," or echoing "Top 15 Space & Astronomy").
```

**`shows/prompts/fascinating_frontiers_podcast.txt`** (prompt) — Ep217 told Shapiro I-III and the JWST FRB at z=2.148 in the body then re-stated both in the deep-dive block (Sep-5 rule miss). Hardens entity check without podcast length levers.
```diff
- - It is a second story, not a second pass: if the deep dive grows out of a story already covered, nothing from that story's body is restated — only the mechanism and the numbers the body did not use.
+ - It is a second story, not a second pass: if the deep dive grows out of a story already covered, nothing from that story's body is restated — only the mechanism and the numbers the body did not use.
+ - Entity check before the deep dive: if a named mission, team, object, or finding already received two or more concrete facts in the body (instrument, distance, redshift, principal investigator, sample size), do not re-enter it in the deep dive — pick an adjacent mechanism or a different concept. Shipped failure shape: body tells Shapiro dwarf galaxies + farthest FRB, then deep dive re-uses both.
```

**`shows/prompts/fascinating_frontiers_digest.txt`** (prompt) — Ep218 spent multiple beats on Schwarzschild's birthday, a Zubrin profile, a Musk medal, and amateur-Claude meta — off-brand for a space-science briefing and weak podcast substrate.
```diff
- - **Curation**: Prefer concrete mission updates, discoveries, research results, and instrument/launch milestones. Avoid "year in review", listicles, awards, or opinion pieces — never to reach a count.
+ - **Curation**: Prefer concrete mission updates, discoveries, research results, and instrument/launch milestones. Avoid "year in review", listicles, awards, or opinion pieces — never to reach a count.
+ - **NO PURE BIRTHDAY / PROFILE / META FILLER**: Drop items whose only news is a historical birthday, a personality profile without a new mission or result, an award ceremony, or amateur-tool meta with no instrument/mission finding (shipped failure: Karl Schwarzschild born-on, Economist engineer profile, medal presentations, "amateur used Claude to flag a planet"). Keep mission-tied human stories when they carry new operational facts (crew timelines, instrument owners, PI quotes on a result).
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/fascinating_frontiers.yaml`** (config): Incremental residual title tighten for ep211-class NASA monthly sky-highlights / planet-at-opposition packages and ep215-class 'first photos of the Moon' / pure born-on anniversary headlines still reaching digests. No bare planet names, no bare 'passes near' (June-16 Falcon-9 lesson). Full digest almanac backstop escalated separately after multi-pass non-merge misses.

## Deferred (carried forward)
- OPERATOR DECISION (escalate since 2026-06-12): Cosmic Deep Dive digest licensed-knowledge thin-day floor (~12–16 sentences / ~250–320w) with --test before/after, OR kill and accept ~1000–1500w podcasts — only sanctioned length path; no podcast-side word pressure (do_not_retry)
- OPERATOR DECISION (escalate after Aug-9→Oct-5 identical dual-layer filings missed while never merging): full NO SKY-ALMANAC / NO THIS-DAY-IN-HISTORY digest backstop beside NO STOCK — drop viewing calendars, shower-peak guides, pure anniversaries, monthly night-sky packages; keep space-based eclipse science and real mission milestones
- OPERATOR DECISION (escalate after multi-pass prompt-only teaser de-seed misses): prefer data-side teaser-frame memory (extend frame_memory / sign-off ban list) over another prompt-only filing; monitor successor shapes ≥6/10
- Align min_podcast_words down to ~1500 to silence every-episode script_below_target — cosmetic ops choice, does not add facts
- Mid-section digest-driven chapter titles (network lever; Spotlight/Deep Dive markers rarely fire because prompt forbids announcing them)
- Theme residual 'science nasa' (low-harm adjacency / bare science.nasa.gov)
- Curated narrative-tracker status pass (operator task: scripts/update_tesla_narrative.py --slug fascinating_frontiers)
- review_snapshot.py missing-Introduction AND missing-Teaser-before-Closing detector (Ep147/166/193/209/219 classes) — network tooling owner
- Aggressive brand-level telescope product title bans — try digest curation first
- Routine comsat/Falcon cadence de-prioritization vs SpaceX Daily (editorial monitor)
- Score Sep-24 source_integrity_claims median and items_without_source with digest sidecars next pass
- Ep209/Ep219 missing Tomorrow Teaser — if ≥3/10 next window, broaden teaser chapter pattern (^Next week) + drift-guard (metadata-only)

## Drift-guard status
```
============================= test session starts ==============================
collected 17 items

tests/test_fascinating_frontiers_quality_pass.py .................       [100%]

============================== 17 passed in 0.39s ==============================
```

<sub>tokens: 69365 in / 6797 out</sub>