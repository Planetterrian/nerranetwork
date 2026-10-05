10/10 scripts still under the digest ceiling; almanac/sky-highlights and anniversary filler still reach audio (ep211–213); Keep-an-eye teaser is no longer saturated but successors are rising; new high-yield issue is spoken digest section headers; escalate multi-miss almanac backstop + teaser de-seed + Cosmic Deep Dive depth rather than re-filing identical prompt levers.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1735**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| ephemeris/sky-almanac/this-day-in-history items in FF Top-15 digests (shower peak guides, pure anniversaries, viewing calendars, zodiacal-light windows) | miss | ep211 snapshot leakage + NASA October night-sky chapter (Saturn opposition, Orionids, Moon–Pleiades); ep212 V2 1942; ep213 Sputnik 1957; filter+backstop never merged |
| occurrences of verbatim teaser opener 'Keep an eye on' in next 10 _tts.txt | partial | Ep211 still keep-an-eye; Ep212–213 use Next-time-watching/watch-for; snapshot no cross-ep keep-an-eye above threshold — desaturated but de-seed never merged |
| successor teaser-tic openers ('Before we go, we'll be watching for' / 'Next time, watch for' / 'Next time we'll be watching for' / 'The thing to watch next') count in next 10 _tts.txt | hit | Ep212–213 successor shapes present but keep-an-eye no longer saturates; no single successor verified ≥6/10 |
| Episodes missing spoken identity line and/or shipping <3 chapter entries | hit | ep204–213 chapter files include Introduction; ep211–213 speak identity line; no Ep193-class 2-entry map |
| episodes below 1700-word floor (digest-ceiling trajectory; no podcast-side lever) | hit | 10/10 ep204–213 _tts.txt under 1700w (1078–1495); ceiling still digest-side |
| presence of Closing as last semantic chapter marker on new episodes | partial | Most end Teaser→Closing; Ep209 chapters_ep209.json has no Tomorrow Teaser (body→Closing only) |
| 0 market-action items / 0 launch false-drops (June-16 lineage holding) | hit | No SPCX/IPO/funding ticker in ep211–213 EN audio; Falcon/Starship/Dragon mission coverage retained |
| deep dive restating a covered story's facts (manual) | miss | Ep211 body lunar-pit cave study re-stated in deep-dive block before debris-laser segment |
| prompt example transition in a shipped transcript | hit | No 'Now, on a completely different note…' in ep211–213 EN transcripts |
| digest_cross_section_dupes_removed | partial | Density copied-section labels common (Top 15 / Cosmic Deep Dive); same-story cross-section dupes less dominant than label echo |
| source_integrity_claims median | miss | n/a-lever-not-scored: claims counts absent from this snapshot bundle — cannot confirm ≥4 median |
| episodes with more than half the items source-less after the retry | miss | n/a-lever-not-scored: digests not in bundle; lint opted-in in YAML but unverified this pass |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/fascinating_frontiers_podcast.txt`** (prompt) — Density audit shows copied section labels on most of ep204–213 (Top 15 / Cosmic Deep Dive headers spoken). Existing skip line is too weak; verbatim ban targets the shipped failure without adding length pressure.
```diff
- WHAT TO SKIP (do NOT read aloud):
- - Daily Inspiration quotes — skip entirely
- - Section headers and separators — skip entirely
- - "Quick scan" lines — skip entirely
+ WHAT TO SKIP (do NOT read aloud):
+ - Daily Inspiration quotes — skip entirely
+ - Section headers and separators — skip entirely
+ - "Quick scan" lines — skip entirely
+ - Digest section LABELS as spoken titles — never read aloud forms like "Top 15 Space and Astronomy Stories", "Cosmic Spotlight", "Cosmic Deep Dive: [Topic]", or bare "Fascinating Frontiers" as a mid-episode section header. Flow straight into the substance; the chapter markers and show notes carry structure, not your voice.
```

**`shows/prompts/fascinating_frontiers_podcast.txt`** (prompt) — Ep211 told the Planetary Science Institute lunar-pit cave study in the body then re-stated the same selection/investigation in the deep-dive block (Sep-5 rule miss). Hardens entity check without podcast length levers.
```diff
- - It is a second story, not a second pass: if the deep dive grows out of a story already covered, nothing from that story's body is restated — only the mechanism and the numbers the body did not use.
+ - It is a second story, not a second pass: if the deep dive grows out of a story already covered, nothing from that story's body is restated — only the mechanism and the numbers the body did not use. Before writing the dive, list named missions, teams, and findings already spoken in the body; if the dive would re-introduce the same named investigation (e.g. the same NASA-selected lunar-pit team), switch to an adjacent concept or keep only unused mechanism/numbers — never re-open with the same proposal/team/finding sentence.
```

**`shows/prompts/fascinating_frontiers_digest.txt`** (prompt) — Ep212 spent multiple items on Reddit career/YouTube-channel meta and a thin sports-appearance beat — off-brand for a space-science briefing and weak substrate for the podcast.
```diff
- - **Curation**: Prefer concrete mission updates, discoveries, research results, and instrument/launch milestones. Avoid "year in review", listicles, awards, or opinion pieces unless you truly cannot fill 15 without them.
+ - **Curation**: Prefer concrete mission updates, discoveries, research results, and instrument/launch milestones. Avoid "year in review", listicles, awards, or opinion pieces unless you truly cannot fill 15 without them. Drop pure Reddit/career/meta threads (job loss, "starting a YouTube channel", ask-for-job posts) and amateur-channel launches unless they carry a concrete research result or mission fact; sports or celebrity PR appearances are at most one clause and only when tied to a named mission milestone.
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/fascinating_frontiers.yaml`** (config): Incremental residual title tighten for ep211-class NASA monthly sky-highlights / planet-at-opposition / named-shower-peak packages still reaching digests. No bare planet names, no bare 'passes near' (June-16 Falcon-9 lesson). Full digest almanac backstop escalated separately after multi-pass non-merge misses.

## Deferred (carried forward)
- OPERATOR DECISION (escalate since 2026-06-12): Cosmic Deep Dive digest licensed-knowledge thin-day floor (~12–16 sentences / ~250–320w) with --test before/after, OR kill and accept ~1100–1500w podcasts — only sanctioned length path; no podcast-side word pressure (do_not_retry)
- OPERATOR DECISION (escalate after Aug-9→Sep-16 identical dual-layer filings missed while never merging): full NO SKY-ALMANAC / NO THIS-DAY-IN-HISTORY digest backstop beside NO STOCK — drop viewing calendars, shower-peak guides, pure anniversaries, monthly night-sky packages; keep space-based eclipse science and real mission milestones
- OPERATOR DECISION (escalate after multi-pass prompt-only teaser de-seed misses): remove quoted Keep-an-eye / Next-time-watching-for examples; prefer data-side teaser-frame memory (extend frame_memory to sign-off teasers) over a third identical prompt-only filing; monitor successor shapes ≥6/10
- Align min_podcast_words down to ~1500 to silence every-episode script_below_target — cosmetic ops choice
- Mid-section digest-driven chapter titles (network lever)
- Theme residual 'science nasa' (low harm)
- Curated narrative-tracker status pass (operator task: scripts/update_tesla_narrative.py --slug fascinating_frontiers)
- review_snapshot.py missing-Introduction AND missing-Teaser-before-Closing detector (Ep147/166/193/209 classes) — network tooling owner
- Aggressive brand-level telescope product title bans — try digest curation first
- Routine comsat/Falcon cadence de-prioritization vs SpaceX Daily (editorial monitor)
- Score Sep-24 source_integrity_claims median and items_without_source with digest sidecars next pass
- Ep209 missing Tomorrow Teaser — monitor; if ≥2/10 recur, broaden teaser chapter pattern + drift-guard

## Drift-guard status
```
============================= test session starts ==============================
collected 17 items

tests/test_fascinating_frontiers_quality_pass.py .................       [100%]

============================== 17 passed in 0.36s ==============================
```

<sub>tokens: 66698 in / 6686 out</sub>