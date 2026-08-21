Almanac/anniversary leakage still ships in digests (ep156/159/163/164), the prompt-seeded “Keep an eye on” teaser remains ~9–10/10, and 8/10 scripts stay under the 1700 floor—escalate Cosmic Deep Dive digest depth rather than re-filing banned podcast length levers.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1469**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| ephemeris/sky-almanac/this-day-in-history items in FF Top-15 digests (shower peak guides, pure anniversaries, viewing calendars) | miss | ep156 Hipparcos-1989, ep159 Perseid peak guide, ep163 Big Ear 1977, ep164 Phoebe 1898 still in digests; Aug-16 filter+backstop not applied |
| occurrences of verbatim teaser opener 'Keep an eye on' in next 10 _tts.txt | miss | 9/10 Ep156–165 teasers still use keep-an-eye-on (Ep164 used Next-time-watching-for); podcast prompt example unchanged |
| successor teaser-tic openers ('Before we go, we'll be watching for' / 'Next time, watch for' / 'The thing to watch next') count in next 10 _tts.txt | hit | Only Ep164 used a successor shape once; keep-an-eye still saturates — no third-generation convergence yet |
| episodes below 1700-word floor (digest-ceiling trajectory; no podcast-side lever) | hit | 8/10 ep156–165 under 1700w (only ep158=1939, ep165=1717 clear); ceiling still digest-side |
| presence of Closing as last semantic chapter marker on new episodes | hit | chapters_ep156–165.json all end Tomorrow Teaser → Closing |
| 0 market-action items / 0 launch false-drops (June-16 lineage holding) | hit | No SPCX/IPO/funding in ep156–165; Falcon 9/Starlink/mission coverage retained |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/fascinating_frontiers_digest.txt`** (prompt) — Digest-side scope backstop (same dual-layer pattern as June-16 stock fix). Fetch title filters miss re-headlined guides, web-search bodies, and anniversary features paraphrased into item text (ep156/159/163/164/165).
```diff
- - **NO STOCK / MARKET ITEMS**: This is a space-and-astronomy SCIENCE show, not a markets show. EXCLUDE pure stock-market or corporate-finance stories — share-price moves, market cap, funding rounds, IPO proceeds, index inclusion/rebalancing, and merger/acquisition valuations. Those belong to the sister shows SpaceX Daily and Modern Investing; covering them here is off-brand and redundant. DO cover a space company's *missions, launches, hardware, science results, and NASA/ESA contracts* (e.g. a Dragon cargo return or a Starship test) — just not its ticker. If a single funding/IPO event has already appeared, never restate it as a second "shares rose" or "merger" item.
+ - **NO STOCK / MARKET ITEMS**: This is a space-and-astronomy SCIENCE show, not a markets show. EXCLUDE pure stock-market or corporate-finance stories — share-price moves, market cap, funding rounds, IPO proceeds, index inclusion/rebalancing, and merger/acquisition valuations. Those belong to the sister shows SpaceX Daily and Modern Investing; covering them here is off-brand and redundant. DO cover a space company's *missions, launches, hardware, science results, and NASA/ESA contracts* (e.g. a Dragon cargo return or a Starship test) — just not its ticker. If a single funding/IPO event has already appeared, never restate it as a second "shares rose" or "merger" item.
+ - **NO SKY-ALMANAC / NO THIS-DAY-IN-HISTORY**: EXCLUDE pure viewing calendars, evening/morning planet columns, shower-peak "how to watch" guides, meteors-per-hour charts, and anniversary/on-this-day features whose only news is that a date rolled around (Hipparcos 1989 lift-off anniversaries, Big Ear 1977 retellings, Phoebe 1898 discovery anniversaries, helium-line 1868 eclipse anniversaries). Those dilute a science-news show. DO keep: space-based eclipse science and new instrument results, meteor/sample analyses with a new measurement, real mission milestones, and any anniversary only when paired with a genuinely new scientific result or hardware development announced today.
```

**`shows/prompts/fascinating_frontiers_podcast.txt`** (prompt) — De-seed by shape + verbatim ban + rotation (playbook July 2026 rule). Prompt-example 'Keep an eye on...' is a 9/10 tic across ep156–165; prior passes predicted persistence while no prompt change shipped. Predict successor tics for next review.
```diff
- [Tomorrow Teaser — one sentence before the closing]
- Patrick: Before we go — briefly tease something listeners should watch for in the next episode based on developing stories from today's news. Keep it specific and forward-looking: "Next time, we'll be watching for..." or "Keep an eye on..." This builds habitual listening.
+ [Tomorrow Teaser — one sentence before the closing]
+ Patrick: Before we go — one concrete forward-looking sentence naming a specific upcoming data point, decision, launch window, or mission step from today's stories (e.g. a named instrument's next observation, a scheduled burn, a data-release date). Shape only — do NOT open with the stock phrases "Keep an eye on", "Keep an eye on the", "Keep an eye on upcoming", "Before we go, keep an eye on", or "Next time, we'll be watching for" (those became every-episode tics). Vary syntax against the last several episodes' teasers; never reuse the same opener two days running. This builds habitual listening without template echo.
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/fascinating_frontiers.yaml`** (config): Deterministic fetch-time tighten for residual shower-peak / how-to-watch / anniversary classes still leaking in ep156/159/163/164 without bare planet names or bare 'passes near' (June-16 Falcon-9 false-drop lesson).

## Deferred (carried forward)
- OPERATOR DECISION (escalate after carrying since 2026-06-12): Cosmic Deep Dive digest licensed-knowledge length lever — ship enforced thin-day floor (~12–16 sentences / ~250–320w) with --test before/after, OR explicitly kill and accept ~1400–1600w podcasts. Only sanctioned length path; do not re-file podcast-side pressure (do_not_retry).
- Align min_podcast_words down to ~1500 to silence every-episode script_below_target — cosmetic ops choice, does not add facts.
- Mid-section digest-driven chapter titles (network lever; Spotlight/Deep Dive markers rarely fire because prompt forbids announcing them).
- Theme residual 'science nasa' (low-harm adjacency / bare science.nasa.gov).
- Curated narrative-tracker status pass (operator task: scripts/update_tesla_narrative.py --slug fascinating_frontiers).
- review_snapshot.py sparse-chapter / missing-Introduction detector (Ep147 false 'clean') — network tooling owner.
- Aggressive brand-level telescope product title bans — try digest curation bullet first to avoid false drops.
- Routine comsat/Falcon cadence de-prioritization vs SpaceX Daily beat (editorial; monitor only this pass).

## Drift-guard status
```
============================= test session starts ==============================
collected 17 items

tests/test_fascinating_frontiers_quality_pass.py .................       [100%]

============================== 17 passed in 0.34s ==============================
```

<sub>tokens: 58268 in / 5056 out</sub>