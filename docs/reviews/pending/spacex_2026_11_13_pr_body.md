Host-ID garble still ships on every recent EN close, Ep158 special chapters collapsed to four markers with massive segment-title copy, and density is healthier on dailies under grok-4.6 while length/price-once stay escalated operator decisions.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.2287**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| Whisper/transcript hits for identity garble "patrick and vancouver" in next 10 EN episodes | miss | Ep158–161 EN Whisper all still say "I'm Patrick and Vancouver"; disambiguation never shipped |
| non-special dailies where Counterpoint chapter start is before ≥3 Top News stories are told (Ep121-class early Counterpoint lumping) | hit | Ep159–161 Counterpoint sits after body/Top News; no Ep121-class early lumping in window |
| dailies with sourced AI/compute items in digest or body but no AI & Compute chapter / no On-the-AI-front anchor | hit | Ep156 has AI chapter when segment runs; Ep159/161 correctly omit when empty; no AI-news-without-chapter miss |
| Engineering Deep Dive listed in script_copied_sections, last 10 | partial | Dailies mostly clean under grok-4.6; Ep158 special flags 6 brief-segment copies (special path, not daily Engineering essay) |
| non-special dailies with mid-body tape line using note-on-the-tape / shares-moved forms and no Market Watch chapter | hit | Window dailies fire MW on mid-body tape or correctly omit when price is sign-off-only (Closing wins) |
| editorial_score_14d_spacex (daily-audit mean 1-10 over 14 days by episode date) | miss | No post-Nov-03 14d mean ≥6.3 in bundle; October baseline 5.23/5.38 still the last committed readout — hold numeric re-score next pass with history export |
| source_integrity_claims median, Ep+1..Ep+14 (Sep-24 sourcing) | miss | Claims/sidecar medians not in bundle — cannot confirm ≥4; treat as open/miss for ledger hygiene |
| digests with leaked Title: heading labels / laundered SEO junk titles | hit | review_snapshot: 0 leaked heading labels; 0 fetch-filter hits on last 10 |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/hooks/spacex.py`** (code) — P0 listener-facing host-ID garble on Ep158–161 after three review proposals never applied. Structural wording only. A/B-listen the identity line on the first two merged episodes.
```diff
- identity/close path that yields spoken forms Whisper hears as "I'm Patrick and Vancouver" (exact intro_line / closing assembly in hook — currently allows bare "in Vancouver" adjacent to Patrick)
+ Supply a structural identity string TTS cannot confute: e.g. exact line "I'm Patrick, here in Vancouver." or "I'm Patrick from Vancouver." everywhere intro_line / sign-off identity is injected. No phonetic respelling, no speech-tag injection (landmine #17). Keep show-name portion of intro_line/closing_block verbatim per brand rules.
```

**`shows/prompts/spacex_flight_special_podcast.txt`** (prompt) — P1 Ep158 53% verbatim + 6 copied Segment-* headings. Special path did not inherit daily grok-4.6 density win. A/B-listen next forced flight special only (landmine #17).
```diff
- SCRIPT STRUCTURE lists [Minute by Minute], [Why the Ship Is the Hard Part], etc. without an explicit ban on reading brief segment labels or ### headings aloud.
+ Add shape-only rule in PRODUCTION NOTES + RULES: never speak segment numbers, 'Segment N', or brief markdown headings; rewrite each brief section sentence by sentence (CONTENT DISCIPLINE mirror); chapters key only off required Counterpoint/Engineering anchor phrases already specified. No new quotable full-sentence example (de-seed-by-shape).
```

## Code/metadata-only proposals (no A/B needed)
- **`engine/chapters.py`** (code): P0 public chapter-list entity bleed. Deterministic garble/filter class (~100% hit per meta-review); no A/B.
- **`engine/generator.py`** (code): P0 Ep158 segment-title leak + four-chapter collapse. Stripper is deterministic no-A/B; adding special markers is metadata-only if titles stay listener-facing names.
- **`shows/spacex.yaml`** (config): Metadata-only residual of Ep091/097 class. Current window clean; widen prevents silent regression. No audio change.
- **`tests/test_spacex_show.py`** (code): Code-only locks so Ep158-class, Ep160-title, and host-ID regressions cannot return unnoticed.
- **`digests/spacex/chapters_ep160.json`** (code): One-time archive cleanup so the public chapter surface matches entity truth; pairs with the scrubber guard.

## Deferred (carried forward)
- OPERATOR DECISION (repeated misses): accept grok-4.3/daily length plateau vs further digest-substrate only (min_digest_words / full-text utilization / licensed Engineering floors) — do not re-propose podcast expand, podcast word floors, or conditional 7+/10 if lever ships predictions
- OPERATOR DECISION (since 2026-06-13): SPCX price-once — Market Watch qualitative + single precise quote only in closing_block; coupled A/B-listen; or accept double price as brand and close the ledger item
- OPERATOR DECISION (mega-story retell, prompt lever missed): data-side exclusion of headlines already used in AI/Counterpoint/Deep Dive from Top News — do not file a third MEGA-STORY prompt rule
- Q2/special path: richer spacex_deep_dive.txt briefs so earnings specials clear deep_dive.min_podcast_words 2400; do not stack time-critical flight specials on the daily publish day (Ep059 lesson)
- Entity-discipline prompt (xAI/SpaceX Memphis/Colossus operator) — regression guard only; A/B; carried while body stays clean (chapter-title SpaceXAI scrub is the metadata half proposed this pass)
- Undated-URL stale articles — refuse record/first claims below memory last-known when page date is unknown
- Pin single closing CTA pack network-wide (Sep-05 identical-closing miss) — separate from market verb; A/B if audio-affecting
- Score source_integrity_claims median and editorial_score_14d_spacex when sidecar/dashboard export is in the review bundle
- api/shorts_ab.json status hygiene after experiment end — non-audio
- NASA public-domain b-roll pool vs retired shorts_ab generated motion — render-side
- Scheduler forensics for any missed Sunday weekly_summary_segment run (June-28 class) — operator

<sub>tokens: 96011 in / 6121 out</sub>