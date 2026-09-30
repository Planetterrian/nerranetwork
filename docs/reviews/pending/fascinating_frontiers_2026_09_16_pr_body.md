Ep193 shipped sparse Teaser+Closing chapters with no Introduction (Ep147/Ep166-class regression); almanac/funding leakage and the prompt-seeded Keep-an-eye-on teaser tic persist while 10/10 scripts stay under the digest ceiling—re-propose dual-layer filters + teaser de-seed + identity harden; escalate Cosmic Deep Dive depth only.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1613**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| ephemeris/sky-almanac/this-day-in-history items in FF Top-15 digests (shower peak guides, pure anniversaries, viewing calendars) | miss | ep194 ICEYE $1B Series F title-pattern hit + transcript almanac/viewing in ep186/187/190/191/192/193; Aug-28 filter+backstop not applied |
| occurrences of verbatim teaser opener 'Keep an eye on' in next 10 _tts.txt | miss | 9/10 Ep186–195 teasers still use keep-an-eye-on (Ep186 Next-time-watching-for; Ep191 hybrid); podcast prompt example unchanged |
| successor teaser-tic openers ('Before we go, we'll be watching for' / 'Next time, watch for' / 'Next time we'll be watching for' / 'The thing to watch next') count in next 10 _tts.txt | hit | Ep186 Next-time-watching-for + Ep191 hybrid once; keep-an-eye still saturates — no third-generation convergence ≥6/10 |
| Episodes missing spoken identity line and/or shipping <3 chapter entries | miss | Ep193 transcript never says identity line; chapters_ep193.json has only 2 entries (Ep147/Ep166-class regression) |
| episodes below 1700-word floor (digest-ceiling trajectory; no podcast-side lever) | hit | 10/10 ep186–195 under 1700w (1076–1538); ceiling still digest-side |
| presence of Closing as last semantic chapter marker on new episodes | partial | Ep186–192/194–195 end Teaser→Closing; Ep193 chapters_ep193.json has ONLY Teaser+Closing (no Intro/body) |
| 0 market-action items / 0 launch false-drops (June-16 lineage holding) | partial | No SPCX/IPO; Falcon/Starship retained; but ep194 spoke ICEYE $1B Series F (funding class YAML already targets) |
| deep dive restating a covered story's facts (manual) | partial | Ep188 deep-dive re-expands Odin protosupercluster already in body; Ep186 white-dwarf binary restated after earlier coverage |
| prompt example transition in a shipped transcript | hit | No 'Now, on a completely different note…' verbatim in ep186–195 transcripts |
| digest_cross_section_dupes_removed | hit | Density table shows copied section labels but not same-story cross-section dupes dominating the window |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/fascinating_frontiers_digest.txt`** (prompt) — Digest-side scope backstop (same dual-layer pattern as June-16 stock fix). Fetch title filters miss re-headlined guides, web-search bodies, funding paraphrases, and anniversary features written into item text (ep186/187/190/191/192/193/194).
```diff
- - **NO STOCK / MARKET ITEMS**: This is a space-and-astronomy SCIENCE show, not a markets show. EXCLUDE pure stock-market or corporate-finance stories — share-price moves, market cap, funding rounds, IPO proceeds, index inclusion/rebalancing, and merger/acquisition valuations. Those belong to the sister shows SpaceX Daily and Modern Investing; covering them here is off-brand and redundant. DO cover a space company's *missions, launches, hardware, science results, and NASA/ESA contracts* (e.g. a Dragon cargo return or a Starship test) — just not its ticker. If a single funding/IPO event has already appeared, never restate it as a second "shares rose" or "merger" item.
+ - **NO STOCK / MARKET ITEMS**: This is a space-and-astronomy SCIENCE show, not a markets show. EXCLUDE pure stock-market or corporate-finance stories — share-price moves, market cap, funding rounds, IPO proceeds, index inclusion/rebalancing, and merger/acquisition valuations. Those belong to the sister shows SpaceX Daily and Modern Investing; covering them here is off-brand and redundant. DO cover a space company's *missions, launches, hardware, science results, and NASA/ESA contracts* (e.g. a Dragon cargo return or a Starship test) — just not its ticker. If a single funding/IPO event has already appeared, never restate it as a second "shares rose" or "merger" item. (Ep194 still spoke an ICEYE $1B Series F body item — drop pure funding rounds even when paraphrased out of the title.)
+ - **NO SKY-ALMANAC / NO THIS-DAY-IN-HISTORY**: EXCLUDE pure viewing calendars, shower-peak / how-to-watch guides, zodiacal-light windows, seasonal-triangle columns, naked-eye conjunction/occultation photo essays, and pure on-this-day / anniversary features with no new science. Those dilute a mission-and-discovery show (ep187 Moon–Jupiter occultation guide, ep190 Vega–Altair–Deneb, ep191 new-moon zodiacal light, ep192 Perseids photo, ep193 Venus–moon pairing, ep186 1618 comet anniversary). DO keep space-based eclipse/occultation science results, new meteor/sample analyses, instrument/mission milestones, and real historical context tied to a fresh finding. Prefer a thinner Top-15 over almanac padding.
```

**`shows/prompts/fascinating_frontiers_podcast.txt`** (prompt) — De-seed by shape + verbatim ban + rotation (playbook July 2026 rule). Prompt-example 'Keep an eye on...' is a 9/10 tic across ep186–195; prior passes predicted persistence while no prompt change shipped. Predict successor tics for next review.
```diff
- [Tomorrow Teaser — one sentence before the closing]
- Patrick: Before we go — briefly tease something listeners should watch for in the next episode based on developing stories from today's news. Keep it specific and forward-looking: "Next time, we'll be watching for..." or "Keep an eye on..." This builds habitual listening.
+ [Tomorrow Teaser — one sentence before the closing]
+ Patrick: Before we go — one concrete forward-looking sentence naming a specific data point, decision date, or mission step from today's news (a launch window, a data release, a conference date, a follow-up observation). Shape only — do NOT open with the stock phrases below.
+ VERBATIM BAN (do not speak): "Keep an eye on", "Keep an eye on the", "Keep an eye on upcoming", "Keep an eye on whether", "Keep an eye on further", "Keep an eye on the next".
+ Also avoid locking onto one successor opener across episodes — rotate syntax naturally; do not reuse the same teaser stem as the prior 3 episodes. (Chapter markers still recognize legacy ^Keep an eye on for old audio; do not emit it.)
```

**`shows/prompts/fascinating_frontiers_podcast.txt`** (prompt) — Ep193 transcript never says 'This is Fascinating Frontiers, episode …'; chapters_ep193.json has ONLY Teaser+Closing (Ep147/Ep166-class regression returned). Hardens post cold-open identity so Introduction marker fires every episode.
```diff
- [Identity — one short line, immediately after the cold open]
- Use this exact line (do not rewrite it, do not add a date):
- {intro_line}
+ [Identity — one short line, immediately after the cold open]
+ REQUIRED every episode — never skip. Speak this exact line once immediately after the cold-open hook and BEFORE any story content (do not rewrite it, do not add a date, do not fold it into the hook). Missing this line breaks the Introduction chapter marker and ships Teaser+Closing-only maps (Ep147/Ep166/Ep193).
+ {intro_line}
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/fascinating_frontiers.yaml`** (config): Deterministic fetch-time tighten for residual how-to-watch occultation / zodiacal-light / seasonal-triangle / shower-photo / on-this-day classes still leaking in ep186–195 without bare planet names or bare 'passes near' (June-16 Falcon-9 false-drop lesson).

## Deferred (carried forward)
- OPERATOR DECISION (escalate after carrying since 2026-06-12): Cosmic Deep Dive digest licensed-knowledge length lever — ship enforced thin-day floor (~12–16 sentences / ~250–320w) with --test before/after, OR explicitly kill and accept ~1100–1500w podcasts. Only sanctioned length path; do not re-file podcast-side pressure (do_not_retry).
- Align min_podcast_words down to ~1500 to silence every-episode script_below_target — cosmetic ops choice, does not add facts.
- Mid-section digest-driven chapter titles (network lever; Spotlight/Deep Dive markers rarely fire because prompt forbids announcing them).
- Theme residual 'science nasa' (low-harm adjacency / bare science.nasa.gov).
- Curated narrative-tracker status pass (operator task: scripts/update_tesla_narrative.py --slug fascinating_frontiers).
- review_snapshot.py sparse-chapter / missing-Introduction detector (Ep147/Ep166/Ep193 false 'clean') — network tooling owner.
- Aggressive brand-level telescope product title bans — try digest curation bullet first to avoid false drops.
- Routine comsat/Falcon cadence de-prioritization vs SpaceX Daily beat (editorial; monitor only this pass).

## Drift-guard status
```
============================= test session starts ==============================
collected 17 items

tests/test_fascinating_frontiers_quality_pass.py .................       [100%]

============================== 17 passed in 0.33s ==============================
```

<sub>tokens: 61042 in / 6538 out</sub>