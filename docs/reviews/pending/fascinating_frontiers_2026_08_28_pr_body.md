10/10 scripts still under the 1700 floor (digest ceiling), almanac/anniversary title leakage continues (ep170 Voyager/Neptune 1989), and the prompt-seeded “Keep an eye on” teaser remains ~9/10—re-propose the dual-layer almanac filter + teaser de-seed; escalate Cosmic Deep Dive depth rather than banned podcast length levers.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1539**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| ephemeris/sky-almanac/this-day-in-history items in FF Top-15 digests (shower peak guides, pure anniversaries, viewing calendars) | miss | ep170 Voyager/Neptune 1989 title-pattern hit + transcript almanac in ep169/170/174/176; Aug-25 filter+backstop not applied |
| occurrences of verbatim teaser opener 'Keep an eye on' in next 10 _tts.txt | miss | 9/10 Ep167–176 teasers still use keep-an-eye-on (Ep168 Next-time-watching-for; Ep171 hybrid); podcast prompt example unchanged |
| successor teaser-tic openers ('Before we go, we'll be watching for' / 'Next time, watch for' / 'Next time we'll be watching for' / 'The thing to watch next') count in next 10 _tts.txt | hit | Ep168 Next-time-watching-for + Ep171 hybrid once; keep-an-eye still saturates — no third-generation convergence ≥6/10 |
| Episodes missing spoken identity line and/or shipping <3 chapter entries | hit | Ep167–176 all speak identity line; chapters_ep167–176.json all have Intro+body+Teaser+Closing (Ep166 regression did not recur) |
| episodes below 1700-word floor (digest-ceiling trajectory; no podcast-side lever) | hit | 10/10 ep167–176 under 1700w (1074–1585); ceiling still digest-side |
| presence of Closing as last semantic chapter marker on new episodes | hit | chapters_ep167–176.json all end Tomorrow Teaser → Closing |
| 0 market-action items / 0 launch false-drops (June-16 lineage holding) | hit | No SPCX/IPO/funding in ep167–176; Falcon/Starship/mission coverage retained |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/fascinating_frontiers_digest.txt`** (prompt) — Digest-side scope backstop (same dual-layer pattern as June-16 stock fix). Fetch title filters miss re-headlined guides, web-search bodies, and anniversary features paraphrased into item text (ep170 Voyager 1989; ep169/176 shower+eclipse viewing; ep174 Mars 2003).
```diff
- - **NO STOCK / MARKET ITEMS**: This is a space-and-astronomy SCIENCE show, not a markets show. EXCLUDE pure stock-market or corporate-finance stories — share-price moves, market cap, funding rounds, IPO proceeds, index inclusion/rebalancing, and merger/acquisition valuations. Those belong to the sister shows SpaceX Daily and Modern Investing; covering them here is off-brand and redundant. DO cover a space company's *missions, launches, hardware, science results, and NASA/ESA contracts* (e.g. a Dragon cargo return or a Starship test) — just not its ticker. If a single funding/IPO event has already appeared, never restate it as a second "shares rose" or "merger" item.
+ - **NO STOCK / MARKET ITEMS**: This is a space-and-astronomy SCIENCE show, not a markets show. EXCLUDE pure stock-market or corporate-finance stories — share-price moves, market cap, funding rounds, IPO proceeds, index inclusion/rebalancing, and merger/acquisition valuations. Those belong to the sister shows SpaceX Daily and Modern Investing; covering them here is off-brand and redundant. DO cover a space company's *missions, launches, hardware, science results, and NASA/ESA contracts* (e.g. a Dragon cargo return or a Starship test) — just not its ticker. If a single funding/IPO event has already appeared, never restate it as a second "shares rose" or "merger" item.
+ - **NO SKY-ALMANAC / NO THIS-DAY-IN-HISTORY**: EXCLUDE pure viewing calendars, evening/morning-sky columns, shower-peak "how to watch" guides, meteors-per-hour charts, and anniversary/on-this-day features whose only news is that a date rolled around (e.g. "Voyager imaged Neptune's rings on August 22, 1989", "Mars at opposition in 2003", "Perseids peak tonight"). Those dilute a science-news show and have repeatedly become cold opens. DO keep: space-based eclipse/occultation science results, new meteorite/sample analyses, active mission milestones, and instrument discoveries — even when they mention an eclipse or shower as context.
```

**`shows/prompts/fascinating_frontiers_podcast.txt`** (prompt) — De-seed by shape + verbatim ban + rotation (playbook July 2026 rule). Prompt-example 'Keep an eye on...' is a 9/10 tic across ep167–176; prior passes predicted persistence while no prompt change shipped. Predict successor tics for next review.
```diff
- [Tomorrow Teaser — one sentence before the closing]
- Patrick: Before we go — briefly tease something listeners should watch for in the next episode based on developing stories from today's news. Keep it specific and forward-looking: "Next time, we'll be watching for..." or "Keep an eye on..." This builds habitual listening.
+ [Tomorrow Teaser — one sentence before the closing]
+ Patrick: Before we go — one concrete forward-looking sentence that names a specific data point, decision, or mission step listeners can actually watch for (a launch window, a data release, a weather gate, a follow-up observation). Shape only — do NOT open with any of these verbatim stems (they became every-episode tics): "Keep an eye on", "Keep an eye on the", "Keep an eye on upcoming", "Keep an eye on whether", "Next time, we'll be watching for", "Next time we'll be watching for", "Next time, watch for", "Before we go, we'll be watching for", "The thing to watch next". Rotate syntax vs the last few episodes' teasers. Still exactly one sentence; still forward-looking; still builds habitual listening.
```

**`shows/prompts/fascinating_frontiers_podcast.txt`** (prompt) — Ep166 (prior window) transcript never said 'This is Fascinating Frontiers, episode …'; chapters_ep166.json had ONLY Teaser+Closing. Ep167–176 recovered, but the failure is intermittent after cold-open retunes. Hardens post cold-open identity so Introduction marker fires every episode.
```diff
- [Identity — one short line, immediately after the cold open]
- Use this exact line (do not rewrite it, do not add a date):
- {intro_line}
+ [Identity — one short line, immediately after the cold open]
+ REQUIRED every episode — speak this exact line once immediately after the cold-open hook and BEFORE any story. Missing it breaks the Introduction chapter marker and ships episodes with only Teaser+Closing (Ep147/Ep166). Do not rewrite it, do not add a date, do not skip it on short days:
+ {intro_line}
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/fascinating_frontiers.yaml`** (config): Deterministic fetch-time tighten for residual shower-peak / how-to-watch eclipse / meteors-per-hour / photographic-discovery anniversary / opposition-anniversary classes still leaking in ep170 (and prior ep163/164) without bare planet names or bare 'passes near' (June-16 Falcon-9 false-drop lesson).

## Deferred (carried forward)
- OPERATOR DECISION (escalate after carrying since 2026-06-12): Cosmic Deep Dive digest licensed-knowledge length lever — ship enforced thin-day floor (~12–16 sentences / ~250–320w) with --test before/after, OR explicitly kill and accept ~1400–1600w podcasts. Only sanctioned length path; do not re-file podcast-side pressure (do_not_retry).
- Align min_podcast_words down to ~1500 to silence every-episode script_below_target — cosmetic ops choice, does not add facts.
- Mid-section digest-driven chapter titles (network lever; Spotlight/Deep Dive markers rarely fire because prompt forbids announcing them).
- Theme residual 'science nasa' (low-harm adjacency / bare science.nasa.gov).
- Curated narrative-tracker status pass (operator task: scripts/update_tesla_narrative.py --slug fascinating_frontiers).
- review_snapshot.py sparse-chapter / missing-Introduction detector (Ep147/Ep166 false 'clean') — network tooling owner.
- Aggressive brand-level telescope product title bans — try digest curation bullet first to avoid false drops.
- Routine comsat/Falcon cadence de-prioritization vs SpaceX Daily beat (editorial; monitor only this pass).

## Drift-guard status
```
============================= test session starts ==============================
collected 17 items

tests/test_fascinating_frontiers_quality_pass.py .................       [100%]

============================== 17 passed in 0.37s ==============================
```

<sub>tokens: 59242 in / 5907 out</sub>