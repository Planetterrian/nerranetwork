Host-ID garble still ships on every recent EN close, 8/10 dailies sit under 1300w, Ep165 retains a SpaceXAI chapter-title bleed, while editorial audit mean recovered to 6.7 and density/chapter defenses mostly held—length and price-once stay escalated operator decisions.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.2156**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| Whisper/transcript hits for identity garble "patrick and vancouver" in next 10 EN episodes | miss | Ep171–174 EN Whisper all still say "I'm Patrick and Vancouver"; disambiguation never shipped |
| Flight/earnings special episodes with copied_sections naming Segment N brief headings or chapters collapsed to <6 section markers | miss | Stripper/special markers never shipped; no new special in Ep165–174 window — item stays open |
| chapters_ep*.json titles matching /SpaceXAI/ (entity bleed) | miss | Ep165 chapter title "SpaceXAI affiliate buys 96 acres near Memphis data centers"; scrub never shipped |
| editorial_score_14d_spacex (dashboard / api/editorial_score_history.json) | hit | Snapshot audit score last 7 = 6.7 (21 before 6.1), clears ≥6.3 expectation |
| non-special dailies with mid-body SPCX tape/price and no Market Watch chapter | hit | Ep165–174 either fire MW on mid-body tape or correctly omit when price is sign-off-only (Closing wins) |
| source_integrity_claims median, Ep+1..Ep+14 (Sep-24 sourcing) | miss | Claims/sidecar medians not in bundle — cannot confirm ≥4 |
| digests with leaked Title: heading labels / laundered SEO junk titles | hit | review_snapshot: 0 leaked heading labels; 0 fetch-filter hits on last 10 |
| episodes >=1300w / conditional length if deep-dive lever ships | miss | only 2/10 (Ep167, Ep171) ≥1300; podcast-side levers banned — do not re-file |

**Merge tier: B (listen)** — see docs/REVIEW_AGENT.md, "Merge tiers".

## Applied in this branch — listen before merging (landmine #17)
These changes are committed on this branch. A rehearsal of the episode was dispatched on this branch (Actions → "Run show", rehearse); listen to its artifact, then merge or close.

**`shows/prompts/spacex_flight_special_podcast.txt`** (prompt) — P1 Ep158-class special path: 53% verbatim + spoken Segment-* headings when daily grok-4.6 density already won. Shape-only ban on segment-label speech + rewrite-not-read rule; no new quotable example sentence (de-seed-by-shape). A/B-listen next forced flight special only (landmine #17).

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes could not be applied by the agent (reason under each). Apply them yourself, render/listen, then merge if they sound right.

**`shows/hooks/spacex.py`** (code) — P0 listener-facing host-ID garble on Ep171–174 after four review proposals never applied. Structural wording only so TTS cannot confute in→and (landmine #17-safe). Apply to every closing_block / identity variant that currently uses 'Patrick in Vancouver'. A/B-listen the identity line on the first two merged episodes.
_Not applied: not_allowed — outside the agent's allowlist (its own show's prompts and YAML)_
```diff
- I'm Patrick in Vancouver
+ I'm Patrick, here in Vancouver
```

## Code/metadata-only proposals (no A/B needed)
- **`engine/chapters.py`** (code): P0 public chapter-list entity bleed on Ep165 (and historically Ep160). Deterministic garble/filter class (~100% hit per meta-review); no A/B. Pair with one-time archive cleanup of chapters_ep165.json.
- **`digests/spacex/chapters_ep165.json`** (code): One-time archive cleanup so the public chapter surface matches entity truth; pairs with the scrubber guard.
- **`tests/test_spacex_show.py`** (code): Code-only locks so Ep171-class host-ID and Ep165-class title bleed cannot return unnoticed.

## Deferred (carried forward)
- OPERATOR DECISION (repeated misses): accept daily length plateau vs further digest-substrate only (min_digest_words / full-text utilization / licensed Engineering floors) — do not re-propose podcast expand, podcast word floors, or conditional 7+/10 if lever ships predictions
- OPERATOR DECISION (since 2026-06-13): SPCX price-once — Market Watch qualitative + single precise quote only in closing_block; coupled A/B-listen; or accept double price as brand and close the ledger item
- OPERATOR DECISION (mega-story retell, prompt lever missed): data-side exclusion of headlines already used in AI/Counterpoint/Deep Dive from Top News — do not file a third MEGA-STORY prompt rule
- Q2/special path: richer spacex_deep_dive.txt / flight briefs so specials clear deep_dive.min_podcast_words 2400; code-side ### Segment N — strip + special section_markers; do not stack time-critical flight specials on the daily publish day
- Entity-discipline prompt (xAI/SpaceX Memphis/Colossus operator naming in body) — regression guard only; A/B; chapter-title SpaceXAI scrub is the metadata half proposed this pass
- Code-side mandatory-anchor / section-order validator for bare Top News lumps (Ep168/Ep174) and missing Counterpoint when digest has the section (Ep170) — escalate off third prompt-only re-seed
- Undated-URL stale articles — refuse record/first claims below memory last-known when page date is unknown
- Pin single closing CTA pack network-wide (Sep-05 identical-closing miss) — separate from market verb; A/B if audio-affecting
- Score source_integrity_claims median when sidecar/gate export is in the review bundle
- api/shorts_ab.json status hygiene after experiment end — non-audio
- NASA public-domain b-roll pool vs retired shorts_ab generated motion — render-side
- Scheduler forensics for any missed Sunday weekly_summary_segment run (June-28 class) — operator
- Monitor share_price must-have only — Ep165/168/169 explained by pre_fetch timeout; Nov-24 hook thread should hold

<sub>tokens: 91417 in / 5467 out</sub>