Almanac/anniversary leakage still ships (ep163/164/170 title hits plus eclipse/meteor filler), the prompt-seeded “Keep an eye on” teaser remains ~8/10, Ep166 regressed to sparse Teaser+Closing chapters with no spoken identity line, and 9/10 scripts stay under the 1700 floor—escalate Cosmic Deep Dive digest depth rather than banned podcast length levers.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1526**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| ephemeris/sky-almanac/this-day-in-history items in FF Top-15 digests (shower peak guides, pure anniversaries, viewing calendars) | miss | ep163 Big Ear 1977, ep164 Phoebe 1898, ep170 Voyager/Neptune 1989 title-pattern leaks + broader transcript almanac; Aug-18 filter+backstop not applied |
| occurrences of verbatim teaser opener 'Keep an eye on' in next 10 _tts.txt | miss | ~8/10 Ep163–172 teasers still use keep-an-eye-on (Ep164/168 used Next-time-watching-for); podcast prompt example unchanged |
| successor teaser-tic openers ('Before we go, we'll be watching for' / 'Next time, watch for' / 'The thing to watch next') count in next 10 _tts.txt | hit | Ep164/168 Next-time-watching-for + Ep171 hybrid once; keep-an-eye still saturates — no third-generation convergence ≥6/10 |
| episodes below 1700-word floor (digest-ceiling trajectory; no podcast-side lever) | hit | 9/10 ep163–172 under 1700w (only ep165=1717 clears); ceiling still digest-side |
| presence of Closing as last semantic chapter marker on new episodes | partial | Ep163–165/167–172 end Teaser→Closing; Ep166 chapters_ep166.json has ONLY Teaser+Closing (no Intro/body) |
| 0 market-action items / 0 launch false-drops (June-16 lineage holding) | hit | No SPCX/IPO/funding in ep163–172; Falcon 9/Starlink/mission coverage retained |
| Episodes missing spoken identity line and/or shipping <3 chapter entries | miss | Ep166 transcript never says identity line; chapters_ep166.json has only 2 entries (Ep147-class regression) |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/fascinating_frontiers_digest.txt`** (prompt) — Digest-side scope backstop (same dual-layer pattern as June-16 stock fix). Fetch title filters miss re-headlined guides, web-search bodies, and anniversary features paraphrased into item text (ep163/164/165/170).
```diff
- - **NO STOCK / MARKET ITEMS**: This is a space-and-astronomy SCIENCE show, not a markets show. EXCLUDE pure stock-market or corporate-finance stories — share-price moves, market cap, funding rounds, IPO proceeds, index inclusion/rebalancing, and merger/acquisition valuations. Those belong to the sister shows SpaceX Daily and Modern Investing; covering them here is off-brand and redundant. DO cover a space company's *missions, launches, hardware, science results, and NASA/ESA contracts* (e.g. a Dragon cargo return or a Starship test) — just not its ticker. If a single funding/IPO event has already appeared, never restate it as a second "shares rose" or "merger" item.
+ - **NO STOCK / MARKET ITEMS**: This is a space-and-astronomy SCIENCE show, not a markets show. EXCLUDE pure stock-market or corporate-finance stories — share-price moves, market cap, funding rounds, IPO proceeds, index inclusion/rebalancing, and merger/acquisition valuations. Those belong to the sister shows SpaceX Daily and Modern Investing; covering them here is off-brand and redundant. DO cover a space company's *missions, launches, hardware, science results, and NASA/ESA contracts* (e.g. a Dragon cargo return or a Starship test) — just not its ticker. If a single funding/IPO event has already appeared, never restate it as a second "shares rose" or "merger" item.
+ - **NO SKY-ALMANAC / NO THIS-DAY-IN-HISTORY**: EXCLUDE pure viewing calendars, "what to see tonight/this week" columns, meteor-shower peak or how-to-watch guides, meteors-per-hour charts, evening-planet pairings with no new science, and pure anniversary / on-this-day features (e.g. "On August 15, 1977, the Big Ear…", photographic-discovery anniversaries, "N years since helium was found"). Those are almanac filler, not news — they have repeatedly diluted Top-15 and even become cold opens. DO keep: space-based eclipse *science results*, new meteor/sample analyses, instrument/mission milestones, and a real discovery that merely happens to fall near an anniversary when the news is the result itself.
```

**`shows/prompts/fascinating_frontiers_podcast.txt`** (prompt) — De-seed by shape + verbatim ban + rotation (playbook July 2026 rule). Prompt-example 'Keep an eye on...' is an ~8/10 tic across ep163–172; prior passes predicted persistence while no prompt change shipped. Predict successor tics for next review.
```diff
- [Tomorrow Teaser — one sentence before the closing]
- Patrick: Before we go — briefly tease something listeners should watch for in the next episode based on developing stories from today's news. Keep it specific and forward-looking: "Next time, we'll be watching for..." or "Keep an eye on..." This builds habitual listening.
+ [Tomorrow Teaser — one sentence before the closing]
+ Patrick: Before we go — one concrete forward-looking sentence naming a specific data point, mission step, decision, or open question from today's stories (instrument, target, date window, or measurement to watch). This builds habitual listening.
+ BANNED verbatim openers (template echo — do not use any of these strings): "Keep an eye on", "Keep an eye on the", "Keep an eye on upcoming", "Keep an eye on whether".
+ Do not lock onto one substitute shape every episode. Rotate syntax naturally — lead with the mission or data name, state the future fact plain, or frame the open question — and do not reuse the same opener shape as the immediately prior episode. Do NOT paste quoted example phrases from this prompt into the script.
```

**`shows/prompts/fascinating_frontiers_podcast.txt`** (prompt) — Ep166 transcript never says 'This is Fascinating Frontiers, episode …'; chapters_ep166.json has ONLY Teaser+Closing (Ep147-class regression returned). Hardens post cold-open identity so Introduction marker fires every episode.
```diff
- [Identity — one short line, immediately after the cold open]
- Use this exact line (do not rewrite it, do not add a date):
- {intro_line}
+ [Identity — one short line, immediately after the cold open]
+ REQUIRED every episode — speak it once, immediately after the cold-open hook and BEFORE any story. If this line is missing, the chapter map breaks (Introduction marker never fires). Use this exact line (do not rewrite it, do not add a date, do not skip it):
+ {intro_line}
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/fascinating_frontiers.yaml`** (config): Deterministic fetch-time tighten for residual shower-peak / how-to-watch / anniversary / meteors-per-hour classes still leaking in ep163/164/170 without bare planet names or bare 'passes near' (June-16 Falcon-9 false-drop lesson).

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

============================== 17 passed in 0.26s ==============================
```

<sub>tokens: 58347 in / 5986 out</sub>