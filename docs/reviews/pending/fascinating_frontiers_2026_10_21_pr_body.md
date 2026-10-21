10/10 scripts remain under the digest ceiling; spoken section labels and thin heritage/off-beat items still reach audio; missing Tomorrow Teaser chapters recur (Ep221/222/226/227/229)—escalate multi-miss almanac/teaser/CDD levers and propose only residual high-yield fixes (section-label ban, deep-dive entity harden, heritage curation, teaser chapter pattern).

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1971**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| spoken digest section labels in next 10 _tts.txt (Top 12/15, Cosmic Spotlight, Cosmic Deep Dive, bare Fascinating Frontiers as headers) | miss | Density copied-section rows on ep220/223/226; WHAT-TO-SKIP harden never merged |
| deep dive restating a body-covered named mission/team/finding (manual, next 10) | miss | Ep226 Enceladus body→deep-dive second pass; Ep229 NS-merger magnetar lead→deep-dive same Kelvin–Helmholtz folding |
| title-pattern hits for night-sky-highlights / reaches-opposition / first-photos-of-moon residual classes in next 10 digests | hit | Snapshot fetch-filter leakage 0 hits on last 10 digests |
| pure birthday / personality-profile / award-ceremony / amateur-tool-meta items in Top-12 digests | miss | Ep226 Hawking Medal; Ep227 Armstrong house purchase; Ep229 Bayeux Tapestry — curation never merged |
| successor teaser-tic single-shape rate in next 10 _tts.txt | hit | No single successor ≥6/10; keep-an-eye desaturated; Ep228/229 varied forward-looking closes |
| episodes below 1700-word floor (digest-ceiling trajectory; no podcast-side lever) | hit | 10/10 ep220–229 under 1700w (1003–1630); ceiling still digest-side |
| Episodes with Introduction present and Tomorrow Teaser immediately before Closing | miss | 5/10 missing Teaser (Ep221/222/226/227/229); Ep222 sparse Intro+Closing only |
| ephemeris/sky-almanac/this-day-in-history items in FF Top-15 digests | partial | Title-pattern 0 hits; heritage/anniversary-adjacent still air via body (Ep227 Armstrong house, Ep229 Bayeux) |
| occurrences of verbatim teaser opener 'Keep an eye on' in next 10 _tts.txt | hit | Desaturated; snapshot no cross-ep keep-an-eye above threshold |
| 0 market-action items / 0 launch false-drops (June-16 lineage holding) | hit | No SPCX/IPO/funding ticker in ep226–229 EN; mission coverage retained |
| prompt example transition in a shipped transcript | hit | No 'Now, on a completely different note…' in ep226–229 EN transcripts |
| source_integrity_claims median | miss | n/a-lever-not-scored: claims counts absent from snapshot bundle |
| episodes with more than half the items source-less after the retry | miss | n/a-lever-not-scored: digests/Source lines not in bundle; lint opted-in in YAML |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/fascinating_frontiers_podcast.txt`** (prompt) — Density audit shows copied section labels on ep220/223/226; prior Ep220 EN spoke 'Cosmic deep dive, house-based craft…'. Existing skip line is too weak; verbatim ban targets the shipped failure without adding length pressure.
```diff
- WHAT TO SKIP (do NOT read aloud):
- - Daily Inspiration quotes — skip entirely
- - Section headers and separators — skip entirely
- - "Quick scan" lines — skip entirely
+ WHAT TO SKIP (do NOT read aloud):
+ - Daily Inspiration quotes — skip entirely
+ - Section headers and separators — skip entirely
+ - "Quick scan" lines — skip entirely
+ - Verbatim digest section labels — NEVER speak these as headers or openers (cover the science; do not read the label): "Top 12", "Top 15", "Top 12 Space", "Top 15 Space", "Cosmic Spotlight", "Cosmic Deep Dive", "Also Today", or bare "Fascinating Frontiers" used as a section title. If the digest line is "Cosmic Deep Dive: Ice giant migration", start mid-thought with the scale comparison or the question — do not say "Cosmic Deep Dive" or "Cosmic Spotlight".
```

**`shows/prompts/fascinating_frontiers_podcast.txt`** (prompt) — Ep226 Enceladus plume salts told in body then continued in deep-dive; Ep229 NS-merger magnetar lead then deep-dive re-entered same field-folding (Sep-5 rule miss). Hardens entity check without podcast length levers.
```diff
- - It is a second story, not a second pass: if the deep dive grows out of a story already covered, nothing from that story's body is restated — only the mechanism and the numbers the body did not use.
+ - It is a second story, not a second pass: if the deep dive grows out of a story already covered, nothing from that story's body is restated — only the mechanism and the numbers the body did not use.
+ - ENTITY HARD GATE before the deep dive: list every named mission, team, moon, instrument, object, or finding that already received two or more concrete facts in the body. None of those names may re-enter the deep dive. If the digest deep-dive topic collides, pivot to an adjacent concept or a different article's mechanism the body never used (e.g. body told Enceladus plume salts → deep dive may not re-open Enceladus; body told NS-merger magnetar amplification → deep dive may not re-fold the same Kelvin–Helmholtz sheet). Prefer a truly second concept over a deeper pass on the lead.
```

**`shows/prompts/fascinating_frontiers_digest.txt`** (prompt) — Ep226/227/229 spent real runtime on medal ceremony, boyhood-house fundraising, and Bayeux Tapestry omen panel — off-brand for a space-science briefing and weak podcast substrate. Selection ban already named awards/profiles; not sticky on heritage-real-estate.
```diff
- - **News**: At most 12 items, and only items that pass the INTERESTING FIRST tests below — a strong day carries 10 to 12, a thin day 8, and a weaker item is cut rather than kept to reach a number (Oct 10 2026: the fixed fifteen put a birthday, a six-month-old satellite image and two profiles on air). Group similar angles into one item. A qualifying story the twelve leave out is not cut: it goes to Also Today as one sentence. Never pad with listicles, year-in-reviews, awards, anniversaries, birthdays, profiles, or an image or dataset first published weeks ago.
+ - **News**: At most 12 items, and only items that pass the INTERESTING FIRST tests below — a strong day carries 10 to 12, a thin day 8, and a weaker item is cut rather than kept to reach a number (Oct 10 2026: the fixed fifteen put a birthday, a six-month-old satellite image and two profiles on air). Group similar angles into one item. A qualifying story the twelve leave out is not cut: it goes to Also Today as one sentence. Never pad with listicles, year-in-reviews, awards, anniversaries, birthdays, profiles, or an image or dataset first published weeks ago.
+ - **NO HERITAGE / CEREMONY / OMEN FILLER**: Exclude as Top-12 items — heritage-property purchases or restorations (astronaut boyhood homes, museum acquisitions), medal/award ceremonies without a new mission fact, tapestry/omen/history-of-astronomy panels, pure personality profiles, and amateur-channel meta. A mission-tied human beat is allowed only when it carries new mission, instrument, or science facts. If truly notable, at most one sentence in Also Today — never a multi-paragraph Top-12 item (Ep226 Hawking Medal, Ep227 Armstrong house, Ep229 Bayeux Halley panel).
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/fascinating_frontiers.yaml`** (config): 5/10 episodes in ep220–229 missing Tomorrow Teaser (Ep221/222/226/227/229); Ep229 teases via 'decision next month' and Ep227 via house 'due to close' without stock openers, so where:end never fires. Metadata-only broaden; mid-body still protected by end window. Prior pass said broaden at ≥3/10 — now 5/10.

## Deferred (carried forward)
- OPERATOR DECISION (escalate since 2026-06-12): Cosmic Deep Dive digest licensed-knowledge thin-day floor enforcement (prompt already says 450–550w / Oct 14 — verify expansion lands with --test before/after, OR kill and accept ~1000–1600w podcasts). Only sanctioned length path; no podcast-side word pressure (do_not_retry).
- OPERATOR DECISION (escalate after Aug-9→Oct-12 identical dual-layer filings missed while never merging): full NO SKY-ALMANAC / NO THIS-DAY-IN-HISTORY / NO HERITAGE-ANNIVERSARY digest backstop beside NO STOCK — drop viewing calendars, shower-peak guides, pure anniversaries, monthly night-sky packages, heritage-property and tapestry/omen panels; keep space-based eclipse science and real mission milestones.
- OPERATOR DECISION (escalate after multi-pass prompt-only teaser de-seed misses): prefer data-side teaser-frame memory (extend frame_memory / sign-off ban list) over another prompt-only Keep-an-eye filing; monitor successor shapes ≥6/10. This pass only broadens the chapter pattern (metadata), not the spoken teaser prompt.
- Align min_podcast_words down to ~1500 to silence every-episode script_below_target — cosmetic ops choice, does not add facts.
- Mid-section digest-driven chapter titles (network lever; Spotlight/Deep Dive markers rarely fire because prompt forbids announcing them).
- Theme residual 'science nasa' (low-harm adjacency / bare science.nasa.gov).
- Curated narrative-tracker status pass (operator task: scripts/update_tesla_narrative.py --slug fascinating_frontiers).
- review_snapshot.py missing-Introduction AND missing-Teaser-before-Closing AND sparse-Intro+Closing detector (Ep147/166/193/209/219/221/222/226/227/229 classes) — network tooling owner. Snapshot '10/10 clean' is false this window.
- Aggressive brand-level telescope product title bans — try digest curation first.
- Routine comsat/Falcon cadence de-prioritization vs SpaceX Daily (editorial monitor).
- Score Sep-24 source_integrity_claims median and items_without_source with digest sidecars next pass.

## Drift-guard status
```
============================= test session starts ==============================
collected 17 items

tests/test_fascinating_frontiers_quality_pass.py .................       [100%]

============================== 17 passed in 0.41s ==============================
```

<sub>tokens: 75947 in / 7535 out</sub>