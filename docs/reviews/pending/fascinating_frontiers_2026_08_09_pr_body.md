10/10 episodes still under the 1700-word floor (digest ceiling; podcast-side levers remain banned), ephemeris/almanac fetch-filter leakage continues in 4/10 digests including a fully ephemeris-led Ep147 with broken chapters, and the prompt-seeded “Keep an eye on” teaser tic is now 10/10.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1334**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| ephemeris/sky-tonight title leakage count in last 10 digests | miss | 4/10 still leak (ep147 evening-skies cold open, ep148/153 Perseid-sky guides, ep156 Hipparcos 1989 anniversary); expected 0 after tightening that was not effectively applied |
| occurrences of 'keep an eye on the' teaser opener across 10 episodes | hit | 10/10 Ep147–156 transcripts/snapshot still contain keep-an-eye-on teaser openers; prompt example unchanged |
| episodes below 1700-word floor (digest-ceiling trajectory) | hit | 10/10 ep147–156 _tts.txt under 1700w (1168–1503); ceiling still digest-side |
| presence of Closing as last semantic chapter marker on new episodes | partial | Ep148–156 correctly end Teaser→Closing, but Ep147 chapters_ep147.json has ONLY Teaser+Closing at 611s+ (no Intro/body map) |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/fascinating_frontiers_digest.txt`** (prompt) — Digest-side scope backstop (same dual-layer pattern as the June-16 stock fix). Fetch filters miss re-headlined monthly guides and web-search items; Ep147 proves almanac can become the cold open.
```diff
- - **NO STOCK / MARKET ITEMS**: This is a space-and-astronomy SCIENCE show, not a markets show. EXCLUDE pure stock-market or corporate-finance stories — share-price moves, market cap, funding rounds, IPO proceeds, index inclusion/rebalancing, and merger/acquisition valuations. Those belong to the sister shows SpaceX Daily and Modern Investing; covering them here is off-brand and redundant. DO cover a space company's *missions, launches, hardware, science results, and NASA/ESA contracts* (e.g. a Dragon cargo return or a Starship test) — just not its ticker. If a single funding/IPO event has already appeared, never restate it as a second "shares rose" or "merger" item.
- - **NO X POSTS**: Do NOT include any X posts, Twitter posts, or social media references. Only use news articles.
+ - **NO STOCK / MARKET ITEMS**: This is a space-and-astronomy SCIENCE show, not a markets show. EXCLUDE pure stock-market or corporate-finance stories — share-price moves, market cap, funding rounds, IPO proceeds, index inclusion/rebalancing, and merger/acquisition valuations. Those belong to the sister shows SpaceX Daily and Modern Investing; covering them here is off-brand and redundant. DO cover a space company's *missions, launches, hardware, science results, and NASA/ESA contracts* (e.g. a Dragon cargo return or a Starship test) — just not its ticker. If a single funding/IPO event has already appeared, never restate it as a second "shares rose" or "merger" item.
+ - **NO SKY-ALMANAC / NO THIS-DAY-IN-HISTORY FILLER**: EXCLUDE pure viewing-calendar and ephemeris columns — "what to see in the sky tonight/this month", evening/morning planet dominance, dawn pairings, meteor-shower peak/how-to-watch guides, naked-eye conjunction roundups, and on-this-day / N-years-ago anniversaries with no new scientific result (e.g. Hipparcos lifted off in 1989). Those dilute a science-news briefing (Ep147 led on Venus evening skies; Ep153 still bulletied "Perseid meteor shower peaks"). DO cover: a shower or sky event only when tied to a new measurement, mission result, instrument paper, or spacecraft observation; historical missions only when there is new analysis, data re-release, or anniversary science — not the calendar fact alone. Never use an almanac line as the HOOK.
+ - **NO CONSUMER GEAR / ENTERTAINMENT TIE-INS**: Skip telescope/binocular product reviews, toy or movie tie-ins, and shopping guides unless the piece reports a genuine research or mission result. Prefer mission, discovery, and instrument news.
+ - **NO X POSTS**: Do NOT include any X posts, Twitter posts, or social media references. Only use news articles.
```

**`shows/prompts/fascinating_frontiers_podcast.txt`** (prompt) — Ep147 transcript never says 'This is Fascinating Frontiers, episode …'; Introduction chapter marker never fired; chapter file only has Teaser+Closing at 611s+. Hardens post cold-open identity after July-30 cold-open retune.
```diff
- [Identity — one short line, immediately after the cold open]
- Use this exact line (do not rewrite it, do not add a date):
- {intro_line}
+ [Identity — one short line, immediately after the cold open]
+ MANDATORY every episode (Ep147 shipped with NO identity line, which also left chapters_ep147.json with only end markers and no Introduction). Immediately after the cold-open hook, speak this exact line on its own Patrick: turn — do not rewrite it, do not add a date, do not skip it, do not merge it into the hook or the first story:
+ {intro_line}
```

**`shows/prompts/fascinating_frontiers_podcast.txt`** (prompt) — De-seed by shape + verbatim ban + rotation memory (playbook July 2026 rule). Prompt-example 'Keep an eye on...' became a 10/10 tic; prior passes predicted persistence while no prompt change shipped.
```diff
- [Tomorrow Teaser — one sentence before the closing]
- Patrick: Before we go — briefly tease something listeners should watch for in the next episode based on developing stories from today's news. Keep it specific and forward-looking: "Next time, we'll be watching for..." or "Keep an eye on..." This builds habitual listening.
+ [Tomorrow Teaser — one sentence before the closing]
+ One short forward-looking sentence naming a CONCRETE upcoming beat from today's news (a named instrument's next data release, a dated launch window, a scheduled test, a follow-up spectrum). Builds habitual listening.
+ 
+ SHAPE (do not copy example wording): opener variety + specific watch-item + why it matters in a few words. Rotate openers across episodes — do not reuse the same opener as the previous episode.
+ 
+ VERBATIM BANS (template echo — shipped 10/10 Ep147–156): never open with "Keep an eye on", "Keep an eye on the", "Keep an eye on further", or "Keep an eye on updates". Also avoid electing the first menu item every day.
+ 
+ Also ban consecutive-episode reuse of: "Before we go, we'll be watching for…", "Next time, watch for…", "Next time, we'll be watching for…" if that exact shape ran yesterday (successor-tic risk after this de-seed).
+ 
+ Do NOT announce a section title; one spoken sentence, then the closing block.
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/fascinating_frontiers.yaml`** (config): Deterministic fetch-time tightening for the four residual almanac/anniversary leak classes in ep147/148/153/156 without bare 'passes near' or bare planet names (June-16 Falcon-9 false-drop lesson).

## Deferred (carried forward)
- Cosmic Deep Dive digest length lever — ESCALATE to operator yes/no after carrying since June 12; only sanctioned length path left (digest licensed-knowledge floor). Do not re-file podcast word pressure (do_not_retry).
- Align min_podcast_words down to ~1500 to silence every-episode script_below_target — cosmetic ops choice, does not add facts.
- Mid-section digest-driven chapter titles (network lever; Spotlight/Deep Dive markers rarely fire because prompt forbids announcing them).
- Theme residual 'science nasa' (low harm adjacency / bare science.nasa.gov).
- Curated narrative-tracker status pass (operator task: scripts/update_tesla_narrative.py --slug fascinating_frontiers).
- review_snapshot.py sparse-chapter / missing-Introduction detector (Ep147 false 'clean'); network tooling owner.
- Aggressive brand-level telescope product title bans — try digest curation bullet first to avoid false drops.

## Drift-guard status
```
============================= test session starts ==============================
collected 17 items

tests/test_fascinating_frontiers_quality_pass.py .................       [100%]

============================== 17 passed in 0.33s ==============================
```

<sub>tokens: 49309 in / 5794 out</sub>