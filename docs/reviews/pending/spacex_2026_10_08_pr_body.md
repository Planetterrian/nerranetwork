Host-ID garble still ships (Ep122/123 “Patrick and Vancouver”), Engineering remains digest-copied on 8/10, 6/10 dailies sit under 1300w, while Market Watch/Counterpoint/Engineering chapter coverage and Title:/fetch-filter defenses held; length and price-once stay escalated operator decisions.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1983**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| non-special dailies with mid-body SPCX tape/price line and no Market Watch chapter | hit | Ep115–124 chapters include Market Watch on mid-body tape/price lines (Ep121–124 Whisper+JSON); no Ep091/097-class miss in window |
| non-special dailies missing Counterpoint chapter and/or Engineering Angle chapter (or missing required anchor strings) | hit | All Ep115–124 have Counterpoint + Engineering Angle chapters; Ep121–124 transcripts include counterpoint and engineering anchors |
| AI & Compute no-news placeholder spoken as a full sentence | hit | 0 placeholder readings in Ep121–124 EN Whisper; live podcast prompt already has skip-when-empty |
| Whisper/transcript hits for identity garble "patrick and vancouver" | miss | Ep122 and Ep123 Whisper still say "I'm Patrick and Vancouver"; disambiguation never shipped |
| Engineering Deep Dive listed in script_copied_sections, last 10 | miss | Snapshot copied-sections flags Engineering on 8/10 (Ep115–116, 119–124) vs expected ≤3/10 |
| script_digest_overlap_pct / digest-verbatim median ≤25% | miss | digest-verbatim 46–69% on 7/10 episodes; median far above 25% |
| script_repeated_facts per episode ≤1 | miss | facts×2 column 1–11; nine of ten episodes ≥4 |
| script_filler_pct ≤5% | hit | All ten snapshot episodes at 2–5% filler |
| script_entity_retention_pct ≥80% on 8/10 | partial | 8/10 names-kept ≥80%, but Ep117 63% and Ep123 74% still miss |
| closings saying "up/down zero percent" | hit | Ep124 "unchanged on the session"; no up/down zero percent in Ep121–124 Whisper |
| closings saying "is trading at" outside NY session | partial | Mixed trading-at vs session-finished forms remain; no run timestamps in bundle for clean after-hours score |
| digests with leaked Title: heading labels | hit | review_snapshot Digest heading integrity: 0 leaked labels on last 10 |
| laundered SEO / sports-fixture / video-ID junk titles in digests | hit | fetch-filter leakage: 0 hits on last 10 spacex digests |
| source_integrity_claims median, Ep+1..Ep+14 (Sep-24 sourcing) | partial | Claims/sidecar medians not in bundle — cannot confirm ≥4; hold for next pass with gate export |
| Ep081-class same-episode full retell of one mega-story across sections | miss | facts×2 still 4–11 and Engineering/Top News co-copy on most days; data-side exclusion still not shipped |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/hooks/spacex.py`** (code) — P0 listener-facing host-ID garble still on Ep122/123 after two review proposals never applied. Structural wording only (landmine #17-safe). A/B-listen the identity line.
```diff
- Identity line supplied to the podcast prompt as the exact {intro_line} shape that ships as "I'm Patrick in Vancouver" (TTS/Whisper intermittently renders "I'm Patrick and Vancouver" — Ep122, Ep123).
+ Disambiguate the spoken identity without phonetic respellings or speech tags: e.g. supply "I'm Patrick, here in Vancouver." (comma + "here in") or "I'm Patrick from Vancouver." as the locked {intro_line}. Keep show name / episode number handling unchanged. Drift-guard: assert the chosen string is substring of generated scripts and document Whisper regression check.
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/spacex.yaml`** (config): Defense-in-depth metadata widen for Ep091/097 opener class (note-on-the-tape / shares-moved). Current window clean but YAML still incomplete. No audio change.
- **`engine/generator.py`** (code): P0/P1 Ep121 false chapter map; Aug-27 prompt reinforcement already missed historically. Code-side per Sep-04 deferred path and playbook escalate-off-third-prompt rule.
- **`engine/script_audit.py`** (code): P1 highest remaining density bug after prompt content_discipline. Meta-review: garble/filter/code class beats threshold predictions; 8/10 Engineering copy is the measurable baseline.
- **`tests/test_spacex_show.py`** (code): Code-only locks so Ep121-class and Ep091-tape and host-ID regressions cannot return unnoticed.

## Deferred (carried forward)
- OPERATOR DECISION (repeated misses): accept grok-4.3 daily length plateau vs further digest-substrate only (min_digest_words / full-text utilization / licensed Engineering floors) — do not re-propose podcast expand, podcast word floors, or conditional 7+/10 if lever ships predictions
- OPERATOR DECISION (since 2026-06-13): SPCX price-once — Market Watch qualitative + single precise quote only in closing_block; coupled A/B-listen; or accept double price as brand and close the ledger item
- OPERATOR DECISION (mega-story retell, prompt lever missed): data-side exclusion of headlines already used in AI/Counterpoint/Deep Dive from Top News — do not file a third MEGA-STORY prompt rule
- Q2/special path: richer spacex_deep_dive.txt briefs so specials clear deep_dive.min_podcast_words 2400; do not stack time-critical specials on the daily publish day
- Entity-discipline prompt (xAI/SpaceX Memphis/Colossus operator) — regression guard only; A/B; carried while window stays clean
- Undated-URL stale articles — refuse record/first claims below memory last-known when page date is unknown
- Pin single closing CTA pack network-wide (Sep-05 identical-closing miss) — separate from market verb; A/B if audio-affecting
- api/shorts_ab.json status hygiene after experiment end — non-audio
- NASA public-domain b-roll pool vs retired shorts_ab generated motion — render-side
- Scheduler forensics for any missed Sunday weekly_summary_segment run (June-28 class) — operator
- Score Sep-24 source_integrity_claims median when sidecar/gate export is in the review bundle

<sub>tokens: 79484 in / 6550 out</sub>