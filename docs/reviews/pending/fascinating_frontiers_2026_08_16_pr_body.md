Almanac/anniversary fetch-filter leakage still ships (3+/10 digests including Perseids and 1977 Big Ear), the prompt-seeded “Keep an eye on” teaser remains 10/10, and 9/10 scripts stay under the 1700 floor with only the deferred Cosmic Deep Dive digest lever left—escalate that operator decision rather than re-filing podcast length pressure.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1421**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| ephemeris/sky-almanac/this-day-in-history items in FF Top-15 digests (evening-planet columns, shower peak guides, pure anniversaries) | miss | ep156 Hipparcos-1989, ep159 Perseid peak guide, ep163 Big Ear 1977 still in digests/transcripts; Aug-9 filter+backstop not applied |
| occurrences of verbatim teaser opener 'Keep an eye on' in next 10 _tts.txt files | miss | 10/10 Ep154–163 teasers still use keep-an-eye-on; podcast prompt example unchanged |
| Episodes missing spoken identity line and/or shipping <3 chapter entries | hit | Ep154–163 all speak identity line; chapters_ep154–163.json all have Intro+body+Teaser+Closing |
| presence of Closing as last semantic chapter marker on new episodes | hit | All ten chapter files end Tomorrow Teaser → Closing |
| 0 market-action items / 0 launch false-drops (June-16 lineage holding) | hit | No SPCX/IPO/funding in ep154–163; Falcon 9/Starlink/mission coverage retained |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/fascinating_frontiers_digest.txt`** (prompt) — Digest-side scope backstop (same dual-layer pattern as June-16 stock fix). Fetch title filters miss re-headlined guides, web-search bodies, and anniversary features paraphrased into item text (ep156/159/163).
```diff
- - **NO STOCK / MARKET ITEMS**: This is a space-and-astronomy SCIENCE show, not a markets show. EXCLUDE pure stock-market or corporate-finance stories — share-price moves, market cap, funding rounds, IPO proceeds, index inclusion/rebalancing, and merger/acquisition valuations. Those belong to the sister shows SpaceX Daily and Modern Investing; covering them here is off-brand and redundant. DO cover a space company's *missions, launches, hardware, science results, and NASA/ESA contracts* (e.g. a Dragon cargo return or a Starship test) — just not its ticker. If a single funding/IPO event has already appeared, never restate it as a second "shares rose" or "merger" item.
- - **NO X POSTS**: Do NOT include any X posts, Twitter posts, or social media references. Only use news articles.
+ - **NO STOCK / MARKET ITEMS**: This is a space-and-astronomy SCIENCE show, not a markets show. EXCLUDE pure stock-market or corporate-finance stories — share-price moves, market cap, funding rounds, IPO proceeds, index inclusion/rebalancing, and merger/acquisition valuations. Those belong to the sister shows SpaceX Daily and Modern Investing; covering them here is off-brand and redundant. DO cover a space company's *missions, launches, hardware, science results, and NASA/ESA contracts* (e.g. a Dragon cargo return or a Starship test) — just not its ticker. If a single funding/IPO event has already appeared, never restate it as a second "shares rose" or "merger" item.
+ - **NO SKY-ALMANAC / NO THIS-DAY-IN-HISTORY**: Exclude pure stargazing calendars and filler retrospectives — planet-of-the-evening/morning columns, "what to see tonight/this week" guides, meteor-shower peak/how-to-watch pieces (peak rates, best time to look, new-moon viewing tips), ground-observer eclipse viewing tips with no new scientific result or space-based observation, and on-this-day / N-years-ago anniversaries (e.g. "On August 15, 1977…", "mission lifted off in 1989", museum exhibitions marking an anniversary). Those dilute a science-news show. DO cover: space-based eclipse or Earth-observation science (e.g. a weather satellite imaging an eclipse), new compositional or dynamical results about meteors/comets, and mission milestones with a genuine new development. If an item is only "look up tonight" or "N years ago today" with no new result, drop it.
+ - **NO X POSTS**: Do NOT include any X posts, Twitter posts, or social media references. Only use news articles.
```

**`shows/prompts/fascinating_frontiers_podcast.txt`** (prompt) — De-seed by shape + verbatim ban + rotation (playbook July 2026 rule). Prompt-example 'Keep an eye on...' is now a 10/10 tic across ep154–163; prior passes predicted persistence while no prompt change shipped. Predict successor tics for next review.
```diff
- [Tomorrow Teaser — one sentence before the closing]
- Patrick: Before we go — briefly tease something listeners should watch for in the next episode based on developing stories from today's news. Keep it specific and forward-looking: "Next time, we'll be watching for..." or "Keep an eye on..." This builds habitual listening.
+ [Tomorrow Teaser — one concrete forward-looking sentence before the closing]
+ One short spoken sentence that names a specific upcoming data point, mission step, observation window, or decision drawn from today's stories (so habitual listeners know what to watch for). Describe the SHAPE only — do not copy a stock opener.
+ SHAPE: concrete noun (mission, instrument, dataset, decision) + what changes next; optionally a date or "next" window.
+ VERBATIM BAN (template-echo tics — never use these openers or mid-line crutches): "Keep an eye on", "Keep an eye on the", "Keep an eye on upcoming", "Keep an eye on follow-up".
+ ROTATION: do not reuse the same syntactic opener as the prior episode's teaser; vary the entry (lead with the mission name, the open question, or the date — not a repeated watch-phrase menu).
+ Do NOT label this a "teaser" out loud. Then go straight into the closing block.
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/fascinating_frontiers.yaml`** (config): Deterministic fetch-time tighten for residual shower-peak / how-to-watch / anniversary classes still leaking in ep156/159/163 without bare planet names or bare 'passes near'.

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

============================== 17 passed in 0.32s ==============================
```

<sub>tokens: 54942 in / 5362 out</sub>