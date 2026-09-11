Seven of ten dailies still sit under 1300w, required Counterpoint/Engineering/Market Watch chapter anchors keep dropping (Ep090/092/093/095), the AI no-news placeholder is still read aloud, and Sep delivery gates only partially moved overlap/copy metrics—length and price-once stay escalated operator decisions.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1824**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| closings saying "is trading at" on episodes generated outside a NY session (last 10) | partial | Ep090–093 use closed-at; Ep087/088/089/094/096 still is-trading-at — clock logic partial without run timestamps |
| closings saying "up/down zero percent" | hit | Ep094 “unchanged on the session”; no up/down zero percent in Ep087–096 Whisper |
| EN Shorts whose stored hook/title is the SPCX price line | partial | No youtube_videos.json slice in bundle; Sep-04 shorts_selector ban not re-verified here |
| non-special dailies with mid-body tape/price line and no Market Watch chapter | miss | Ep087 finished-the-session without MW chapter; Ep091 quick-note-on-the-tape without MW chapter |
| Top News items whose publisher URL path is dated older than lookback | partial | No dated-path stale hit in window; undated-URL stale class still open |
| script_digest_overlap_pct, median of last 10 | miss | digest-verbatim median ~61% (Ep087–091/096 61–71%); only Ep092–095 ≤25% |
| script_repeated_facts per episode | miss | facts×2 still 2–4 on Ep088–091/096 vs expected ≤1 |
| script_filler_pct | partial | mixed 0–10%; several eps ≤3% but Ep087/090/094 at 7–10% |
| Deep Dive numbers not spoken earlier in the episode | miss | Engineering still flagged copied_sections on 5/10; Ep092-class zero-new-number deep dive not cleared network-wide |
| closing text identical across episodes | miss | multiple CTA/sign-off packs still rotate across Ep087–096 |
| script_copied_sections on the Engineering Deep Dive, last 10 | miss | Engineering copied-section flag on Ep087,089,090,091,096 (5/10) vs expected ≤3/10 |
| script_entity_retention_pct, last 10 | miss | names-kept ≥80% on only ~3/10; Ep091 56%, Ep095 67%, Ep096 73% |
| version/model names in the cold open also spoken in the body | miss | Ep093 hook Raptor v3 not kept as V3 in body; computing-facility paraphrase class persists |
| AI & Compute no-news line spoken as a sentence | miss | Ep092 and Ep094 Whisper still read full no-new-developments + live-threads placeholder |
| non-special dailies missing Counterpoint and/or Engineering Angle chapter anchors | miss | Ep090 no Engineering chapter; Ep092/093/095 no Counterpoint; Ep093 also no AI chapter |
| Ep081-class same-episode full retell of one mega-story across sections | miss | Ep090 Memphis outage multi-section retell with MEGA-STORY prompt already shipped |
| laundered SEO / sports-fixture / video-ID junk titles in digests | hit | review_snapshot fetch-filter leakage: 0 hits on last 10 spacex digests |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/spacex_podcast.txt`** (prompt) — P1: Ep092/Ep094 still read the full no-news placeholder on air (Sep-09 miss). Shape-only skip rule; no new quotable example sentence (de-seed-by-shape). A/B-listen landmine #17.
```diff
- [AI & Compute — the dedicated AI segment, ~60–90 seconds]
- Cover the digest's AI & Compute section: ... REQUIRED: open the segment with "On the AI front" — podcast-app chapters key off this phrase. If the digest has no AI & Compute material today, give it one sentence on the live threads to watch and move on.
+ [AI & Compute — the dedicated AI segment, ~60–90 seconds]
+ Cover the digest's AI & Compute section only when it contains at least one sourced development (a concrete claim with a Source). REQUIRED when the segment runs: open with "On the AI front" — podcast-app chapters key off this phrase. If the digest AI section is only a quiet-day stub (no sourced item — the shape that notes no new developments and lists live threads to watch), OMIT the entire AI segment: no anchor, no placeholder sentence, no “threads to watch” read-aloud. Never invent AI items to fill the slot.
```

**`shows/prompts/spacex_digest.txt`** (prompt) — Digest substrate marker so podcast skip-when-empty is unambiguous; avoids seeding a spoken laundry-list the model reads verbatim (Ep092/094). A/B-listen.
```diff
- If there is genuinely no sourced AI/compute news today, write ONE sentence noting the quiet and the live threads to watch (orbital data centers, direct-to-cell, xAI compute, Cursor/Grok distribution) — never pad and never fabricate to fill the section.
+ If there is genuinely no sourced AI/compute news today, write exactly one short stub line under the heading that states there is no sourced AI item today (no thread laundry-list, no fake watch list). The podcast stage will skip speaking this section entirely when the stub has no Source-backed item — keep the stub machine-detectably empty of facts rather than a spoken essay.
```

**`shows/hooks/spacex.py`** (code) — P0 listener-facing host-ID garble on 6/10 transcripts. Structural pause only; must A/B-listen identity line.
```diff
- (identity/closing paths that yield spoken “I'm Patrick in Vancouver” — Whisper 6/10 “Patrick and Vancouver”)
+ Ensure the committed identity string used in intro_line is comma-disambiguated: “I'm Patrick, in Vancouver” (pause before in) so TTS cannot merge in→and; keep show name / disclaimer untouched. No phonetic respelling tables for arbitrary words (landmine #17).
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/spacex.yaml`** (config): P0/P1: Ep091 spoke “A quick note on the tape, SPCX moved lower on the session” with no Market Watch chapter — pattern had look-at-the-tape and note-on-the-market but not note-on-the-tape / moved-lower-on-the-session. Metadata-only; Closing must remain listed BEFORE Market Watch with where:end.
- **`engine/generator.py`** (code): P0: Ep090/092/093/095 dropped required chapters; Aug-27 prompt reinforcement missed; Sep-04 already deferred to deterministic code-side validator — escalate off third prompt-only re-seed.
- **`tests/test_spacex_show.py`** (code): Code-only locks for P0 chapter/pattern regressions so Ep091-tape and Ep090-anchor classes cannot return unnoticed.
- **`engine/script_audit.py`** (code): P1: Sep-06 found section-level Deep Dive paraphrase under the whole-script gate; Ep087–091/096 still flag Engineering copied_sections while median overlap stays high on other days. Telemetry prevents silent fire-and-miss (length-retry lesson).

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

<sub>tokens: 67130 in / 8017 out</sub>