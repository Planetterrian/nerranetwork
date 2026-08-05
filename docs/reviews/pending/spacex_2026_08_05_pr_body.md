Seven of ten episodes still under the 1300w floor, the required engineering chapter-anchor has hardened into a 10/10 verbatim tic, SPCX price is still spoken twice every daily, and Ep58 shipped malformed Title:-prefixed story chapters; length and price-once are escalated to operator decisions after repeated misses.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1363**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| exact 'from an engineering standpoint' occurrences in next 10 transcripts | miss | Ep50–59 Whisper: phrase still 10/10; July-30 shape de-seed never applied |
| laundered SEO / sports-fixture / video-ID junk titles in digests | hit | review_snapshot fetch-filter leakage: 0 hits on last 10 spacex digests |
| episodes >=1300w in next 10 | miss | only 3/10 (Ep53/58/59); 7 dailies still 1057–1299w — reconfirm prior misses, no new lever |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/spacex_podcast.txt`** (prompt) — P1: 10/10 monoculture on one required phrase; de-seed by shape + finite rotation set + MEMORY so chapters keep working; successor-tic prediction logged for 'the engineering angle' convergence.
```diff
- REQUIRED: the segment's first sentence must contain "from an engineering standpoint" or "the engineering angle" — podcast-app chapters key off this phrase. Vary everything after it daily.
+ REQUIRED first-sentence CHAPTER ANCHOR (podcast-app chapters key off these — pick exactly one, as the opening words of the segment's first sentence): (1) "From an engineering standpoint" (2) "The engineering angle" (3) "The engineering reality". ROTATION RULE: do not reuse the same anchor choice as the immediately prior episode (consult NARRATIVE MEMORY / recent episodes). After the anchor words, the rest of the sentence must be fresh — never repeat a prior episode's full opening clause. VERBATIM BAN on running the identical full opener two days running. (Do not invent new anchor phrasings outside the three above — off-list openers break chapters.)
```

**`shows/prompts/spacex_podcast.txt`** (prompt) — P1: Ep53 on-air 'SpaceX AI added another data center building in Memphis' repeats the July-02 entity conflation; prompt-level hard rule, A/B-listen.
```diff
- [AI & Compute — the dedicated AI segment, ~60–90 seconds]
- Cover the digest's AI & Compute section: the SpaceX↔AI thread where rockets, satellites, and the Musk compute ecosystem meet
+ [AI & Compute — the dedicated AI segment, ~60–90 seconds]
+ ENTITY DISCIPLINE (hard): Colossus, Memphis turbines/grid work, and xAI training clusters are xAI's unless the digest explicitly says SpaceX owns the facility. Never say "SpaceXAI". Never attribute an xAI datacenter, turbine permit, or Grok training run to SpaceX. Cross-company compute deals are fine when sourced — name both parties. Cursor/Anysphere is not SpaceX.
+ Cover the digest's AI & Compute section: the SpaceX↔AI thread where rockets, satellites, and the Musk compute ecosystem meet
```

**`shows/prompts/spacex_digest.txt`** (prompt) — Digest is the substrate the podcast is licensed to read; fix conflation at source so podcast cannot re-emit it.
```diff
- IN SCOPE: SpaceX's own AI/compute push (orbital data centers, "AI satellites", Starlink + on-orbit compute, Starshield); xAI / Grok / X developments
+ ENTITY DISCIPLINE (hard): Colossus / Memphis power & turbines / xAI training clusters belong to xAI, not SpaceX. Never write "SpaceXAI" or "SpaceX AI datacenter" for an xAI facility. If a source blurs the entities, attribute precisely ("xAI's Memphis cluster, part of the broader Musk compute stack") and keep SpaceX-owned vs xAI-owned distinct.
+ IN SCOPE: SpaceX's own AI/compute push (orbital data centers, "AI satellites", Starlink + on-orbit compute, Starshield); xAI / Grok / X developments
```

## Code/metadata-only proposals (no A/B needed)
- **`engine/chapters.py`** (code): P0 listener-facing metadata bug unique to Ep58 in the window; deterministic, no audio, high yield per meta-review garble/filter class.
- **`tests/test_spacex_show.py`** (code): Drift-guards for P0 chapter sanitizer and intro-chapter regressions; code-only.

## Deferred (carried forward)
- OPERATOR DECISION (escalation after repeated misses): accept grok-4.3 daily length plateau vs further digest-substrate only (min_digest_words / full-text fetch) — do not re-propose podcast expand, word floors in podcast prompt, or '7+/10 if deep-dive ships' predictions
- OPERATOR DECISION (escalation since 2026-06-13): SPCX price-once — Market Watch qualitative + single precise quote only in closing_block; coupled A/B-listen; stop carrying the same unshipped fix
- Q2/special path: enforce richer spacex_deep_dive.txt briefs so specials clear deep_dive.min_podcast_words 2400 (Ep59 shipped 1778) — digest/brief substrate only
- Tomorrow-teaser rotation (P2; 'Watch for the first/next <test>' no longer dominant in Ep50–58)
- Scheduler forensics for any missed Sunday weekly_summary_segment run (June-28 class) — operator
- NASA public-domain b-roll pool vs retired shorts_ab generated motion — render-side follow-up, not audio

<sub>tokens: 54105 in / 4678 out</sub>