Aug-26 chapter allowlist and mega-story prompt ships held on Ep073–082 surfaces, but Ep082 dropped both Counterpoint and Engineering Angle chapter anchors (P1), 9/10 dailies remain under 1300w, and SPCX price-twice stays an escalated operator decision.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1465**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| chapters_ep*.json titles outside known section set (Introduction\|Counterpoint\|AI & Compute\|The Engineering Angle\|Market Watch\|Tomorrow Teaser\|Closing) in next 10 spacex episodes | hit | Ep073–082 committed chapters use only known section titles; spacex.yaml known_sections_only: true (Aug 27); Ep077 headline-chapter spam absent from current chapters_ep077.json |
| same-episode multi-section full retell of one mega-story (same dollar figure + pad/site count restated in Engineering + AI + body) in next 10 transcripts | partial | MEGA-STORY rules present in digest/podcast prompts; Ep081 still multi-retells Louisiana $100B/10-pad across segments; Ep082 has no equivalent full multi-section retell |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/spacex_podcast.txt`** (prompt) — P1: Ep082 Whisper/chapters dropped Counterpoint + Engineering anchors while still speaking those segments under Introduction (~5 min). Shape + verbatim required anchors + injected {engineering_anchor}; no new quotable example sentence (de-seed-by-shape). A/B-listen landmine #17.
```diff
- [The Counterpoint]
- Cover the digest's skeptical or challenging item honestly: what the concern is, why it's reasonable, and what would resolve it. Direct and constructive, never dismissive, never alarmist. REQUIRED: open the segment with the words "One thing worth watching" or "Worth keeping an eye on" — podcast-app chapters key off this phrase.
+ [The Counterpoint]
+ Cover the digest's skeptical or challenging item honestly: what the concern is, why it's reasonable, and what would resolve it. Direct and constructive, never dismissive, never alarmist. REQUIRED: open the segment with the words "One thing worth watching" or "Worth keeping an eye on" — podcast-app chapters key off this phrase.
+ 
+ MANDATORY CHAPTER ANCHORS (emit each exactly once per daily episode; omitting any breaks podcast chapters): (1) Counterpoint — one of the two openers above as the segment’s first words; (2) Engineering Deep Dive — the first sentence MUST contain this exact hook-supplied anchor and no substitute synonym: {engineering_anchor}; (3) AI & Compute — opens with "On the AI front". Busy mega-story days still emit all three anchors; anchors are not optional transitions. Do not invent alternate engineering or counterpoint lead-ins.
```

## Code/metadata-only proposals (no A/B needed)
- **`tests/test_spacex_show.py`** (code): Code-only guard so Ep082-class missing section anchors cannot return unnoticed; pairs with prompt reinforcement; no audio change.

## Deferred (carried forward)
- OPERATOR DECISION (repeated misses): accept grok-4.3 daily length plateau vs further digest-substrate only (min_digest_words / full-text fetch / licensed section floors) — do not re-propose podcast expand, podcast word floors, or conditional 7+/10 if lever ships predictions
- OPERATOR DECISION (since 2026-06-13): SPCX price-once — Market Watch qualitative + single precise quote only in closing_block; coupled A/B-listen; or accept double price as brand and close
- Q2/special path: richer spacex_deep_dive.txt briefs so specials clear deep_dive.min_podcast_words 2400; do not stack time-critical specials on the daily publish day
- Entity-discipline prompt (xAI/SpaceX Memphis/Colossus operator) — regression guard only; A/B; carried while window stays clean
- api/shorts_ab.json still collecting after experiment ended 2026-08-14 — report builder should mark ended (non-audio)
- NASA public-domain b-roll pool vs retired shorts_ab generated motion — render-side follow-up, not audio
- Scheduler forensics for any missed Sunday weekly_summary_segment run (June-28 class) — operator

<sub>tokens: 62704 in / 3511 out</sub>