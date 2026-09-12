Eight of ten recent dailies still sit under 1300w, required Counterpoint/Market Watch chapters keep dropping on rotated openers, AI no-news placeholders and host-ID garbles remain on air, and Sep delivery gates only partially moved density metrics—length and price-once stay escalated operator decisions.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1843**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| non-special dailies with mid-body SPCX tape/price line and no Market Watch chapter (incl. note-on-the-tape / moved-lower-on-the-session forms) | miss | Ep091 quick-note-on-the-tape + no MW chapter; Ep097 note-on-the-tape shares-moved-higher + no MW; YAML pattern still incomplete |
| non-special dailies missing Counterpoint chapter and/or Engineering Angle chapter (or missing required anchor strings in _tts.txt) | miss | Ep090 no Engineering chapter; Ep092/093/095 no Counterpoint; Ep093 also no AI chapter |
| AI & Compute no-news placeholder spoken as a full sentence (hand-count) | miss | Ep092 and Ep094 Whisper still read full no-new-developments + live-threads placeholder |
| Whisper/transcript hits for identity garble "patrick and vancouver" in next 10 | miss | Still present Ep090/093/094/096 (I'm Patrick and Vancouver) |
| Engineering Deep Dive listed in script_copied_sections, last 10 | miss | Copied-sections flags Engineering on Ep089,090,091,096,098 (5/10) vs expected ≤3/10 |
| closings saying "is trading at" on episodes generated outside a NY session (weekday 04:00-20:00 ET), last 10 | partial | Ep090-093 prefer closed-at; Ep089/094/096/097 still is-trading-at — incomplete without run timestamps |
| closings saying "up/down zero percent" | hit | Ep094 unchanged on the session; no up/down zero percent in Ep089-098 Whisper |
| EN Shorts whose stored hook/title is the SPCX price line (youtube_videos.json) | partial | No youtube_videos.json slice in bundle; Sep-04 shorts_selector ban not re-verified here |
| Top News items whose publisher URL path is dated older than lookback (stale re-surfaced articles) | partial | No dated-path stale hit in Ep089-098 digests; undated-URL stale class still open |
| script_digest_overlap_pct, median of last 10 | miss | digest-verbatim still 56-71% on Ep089-091/096/098; only Ep092-095/097 under 25% |
| script_repeated_facts per episode | miss | facts×2 still 1-4 (Ep090=4) vs expected ≤1 |
| script_filler_pct | partial | mixed 0-10%; several eps ≤3% but Ep089/090/094/098 at 6-10% |
| Deep Dive numbers not spoken earlier in the episode (manual count) | miss | Engineering still flagged copied_sections on 5/10; density not cleared network-wide |
| closing text identical across episodes | miss | multiple CTA/sign-off packs still rotate across Ep089-098 |
| script_entity_retention_pct, last 10 | miss | names-kept ≥80% on only ~2/10; Ep091 56%, Ep097 53% |
| version/model names in the cold open also spoken in the body (hand-count), 3 episodes | miss | Ep093 hook Raptor v3 not kept as V3 in body |
| Ep081-class same-episode full retell of one mega-story’s key figures across Engineering + body + AI in next 10 transcripts | miss | Ep090 Memphis outage multi-section retell with MEGA-STORY prompt already shipped |
| laundered SEO / sports-fixture / video-ID junk titles in digests | hit | review_snapshot fetch-filter leakage: 0 hits on last 10 spacex digests |
| digests with leaked "Title:" heading labels (snapshot Digest heading integrity section) | hit | Digest heading integrity: 0 leaked heading labels on last 10 spacex digests |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/spacex_podcast.txt`** (prompt) — P1: Ep092/Ep094 still read the full no-news placeholder on air (Sep-09/Sep-10 miss). Shape-only skip rule; no new quotable example sentence (de-seed-by-shape). A/B-listen landmine #17.
```diff
- REQUIRED: open the segment with "On the AI front" — podcast-app chapters key off this phrase. If the digest has no AI & Compute material today, give it one sentence on the live threads to watch and move on.
+ REQUIRED: open the segment with "On the AI front" — podcast-app chapters key off this phrase — ONLY when the digest's AI & Compute section contains at least one sourced item. If the digest marks AI & Compute as quiet / no sourced items, OMIT the entire AI & Compute segment (no chapter anchor, no placeholder sentence, no laundry list of live threads). Skipping is correct; reading a no-news template aloud is not.
```

**`shows/prompts/spacex_digest.txt`** (prompt) — Digest substrate marker so podcast skip-when-empty is unambiguous; avoids seeding a spoken laundry-list the model reads verbatim (Ep092/094). A/B-listen.
```diff
- If there is genuinely no sourced AI/compute news today, write ONE sentence noting the quiet and the live threads to watch (orbital data centers, direct-to-cell, xAI compute, Cursor/Grok distribution) — never pad and never fabricate to fill the section.
+ If there is genuinely no sourced AI/compute news today, write exactly: `### AI & Compute\n(none today)` — nothing else in that section. Do NOT list live threads, do NOT write a prose quiet-day sentence the podcast might read aloud. Never pad and never fabricate to fill the section.
```

**`shows/hooks/spacex.py`** (code) — P0 listener-facing host-ID garble on multiple transcripts in the window. Structural pause only; must A/B-listen identity line.
```diff
- Identity line path that yields spoken forms Whisper hears as “I'm Patrick and Vancouver” / “Patrick and Vancouver”.
+ Disambiguate the host identity line so TTS cannot collapse “Patrick in Vancouver” into “Patrick and Vancouver” (e.g. structural comma/pause: “I'm Patrick, in Vancouver.” or equivalent hook-owned exact string already used by intro_line). Must remain a single short identity line; no phonetic respelling (landmine #17).
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/spacex.yaml`** (config): P0/P1: Ep091 spoke “A quick note on the tape, SPCX moved lower on the session” and Ep097 “A quick note on the tape shows the shares moved higher” with no Market Watch chapter — pattern had look-at-the-tape and note-on-the-market but not note-on-the-tape / moved-lower / shares-moved forms. Metadata-only; Closing must remain listed BEFORE Market Watch with where:end.
- **`engine/generator.py`** (code): P0: Ep090/092/093/095 dropped required chapters; Aug-27 prompt reinforcement missed; Sep-04 already deferred to deterministic code-side validator — escalate off third prompt-only re-seed.
- **`tests/test_spacex_show.py`** (code): Code-only locks for P0 chapter/pattern regressions so Ep091-tape and Ep090-anchor classes cannot return unnoticed.
- **`engine/script_audit.py`** (code): P1: Sep-06 found section-level Deep Dive paraphrase under the whole-script gate; Ep089–091/096/098 still flag Engineering copied_sections while median overlap stays high on other days. Telemetry prevents silent fire-and-miss (length-retry lesson).

## Deferred (carried forward)
- OPERATOR DECISION (repeated misses): accept grok-4.3 daily length plateau vs further digest-substrate only (min_digest_words / full-text fetch / licensed section floors) — do not re-propose podcast expand, podcast word floors, or conditional 7+/10 if lever ships predictions
- OPERATOR DECISION (since 2026-06-13): SPCX price-once — Market Watch qualitative + single precise quote only in closing_block; coupled A/B-listen; or accept double price as brand and close
- OPERATOR DECISION (mega-story retell, prompt lever missed on Ep090): data-side exclusion of headlines already used in AI/Counterpoint/Deep Dive from Top News — do not file a third MEGA-STORY prompt rule
- Q2/special path: richer spacex_deep_dive.txt briefs so specials clear deep_dive.min_podcast_words 2400; do not stack time-critical specials on the daily publish day
- Entity-discipline prompt (xAI/SpaceX Memphis/Colossus operator) — regression guard only; A/B; carried while window stays clean
- Stale articles with undated URLs — article:published_time at fetch or refuse record/first claims below memory last-known figure
- api/shorts_ab.json still collecting after experiment ended 2026-08-14 — report builder should mark ended (non-audio)
- NASA public-domain b-roll pool vs retired shorts_ab generated motion — render-side follow-up, not audio
- Scheduler forensics for any missed Sunday weekly_summary_segment run (June-28 class) — operator
- Pin single closing CTA pack network-wide (Sep-05 identical-closing miss) — separate from market verb; A/B if audio-affecting

<sub>tokens: 69275 in / 7623 out</sub>