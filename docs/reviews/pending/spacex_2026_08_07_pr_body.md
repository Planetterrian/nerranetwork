Title:-prefixed headline chapters spread from Ep58 to Ep60 (P0 sanitizer still unshipped), engineering-anchor tic remains 10/10, 7/10 dailies under 1300w with Ep61 at 863w, and length/price-once stay escalated operator decisions after repeated misses.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1468**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| chapters_ep*.json titles matching /^Title:\s*/ in next 10 spacex episodes | miss | Sanitizer never applied; Ep58 still has six Title: chapters; Ep60 added three Title: + one bare headline chapter |
| exact phrase 'from an engineering standpoint' in next 10 daily (non-special) transcripts | miss | Ep53–62 Whisper: phrase still 10/10; Aug-05 anchor-rotation prompt never applied |
| on-air xAI facility attributed as SpaceX (Memphis/Colossus/'SpaceX AI' datacenter) in next 10 transcripts | partial | Ep53 still ships Memphis 'SpaceX AI' mis-attr; Ep60–62 clean on that class (n=3) but entity prompt never shipped |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/spacex_podcast.txt`** (prompt) — P1: 10/10 monoculture on one required phrase across Ep53–62; de-seed by shape + finite rotation set + MEMORY per July 2026 meta-review; successor-tic prediction logged for 'the engineering angle' convergence.
```diff
- REQUIRED: the segment's first sentence must contain "from an engineering standpoint" or "the engineering angle" — podcast-app chapters key off this phrase. Vary everything after it daily.
+ REQUIRED chapter anchor (pick ONE form for the segment's first sentence; podcast-app chapters key off these): rotate across {from an engineering standpoint | the engineering angle | the engineering reality | engineering deep dive}. Do not reuse the exact opener phrase from the previous episode (check MEMORY / recent scripts). Ban shipping the same opener two days running. Describe the turn into first-principles analysis by shape only — never seed a full example sentence the model can copy. Vary everything after the anchor daily.
```

**`shows/prompts/spacex_podcast.txt`** (prompt) — P1: Ep53 on-air 'SpaceX AI added another data center building in Memphis' repeats the July-02 entity conflation; prompt-level hard rule, A/B-listen.
```diff
- Cover the digest's AI & Compute section: the SpaceX↔AI thread where rockets, satellites, and the Musk compute ecosystem meet — orbital data centers and "AI satellites", Starlink + on-orbit compute and direct-to-cell, notable xAI / Grok / X developments (new Grok capabilities, xAI datacenters like Colossus, how X and xAI tie into the Starlink/SpaceX stack and the IPO's AI-infrastructure spend), AND Cursor / Anysphere when the digest covers it
+ Cover the digest's AI & Compute section: the SpaceX↔AI thread where rockets, satellites, and the Musk compute ecosystem meet — orbital data centers and "AI satellites", Starlink + on-orbit compute and direct-to-cell, notable xAI / Grok / X developments (new Grok capabilities, xAI datacenters like Colossus, how X and xAI tie into the Starlink/SpaceX stack and the IPO's AI-infrastructure spend), AND Cursor / Anysphere when the digest covers it. ENTITY HARD RULE: Colossus, Memphis turbines, and xAI compute clusters are xAI's unless the digest explicitly states a SpaceX-owned facility; never say "SpaceX AI" or "SpaceXAI" as a datacenter operator; name cross-company deals as deals between named entities. (Operator-confirmed: Colossus/Anthropic material is real — attribute correctly, do not drop.)
```

**`shows/prompts/spacex_digest.txt`** (prompt) — Digest is the substrate the podcast is licensed to read; fix conflation at source so podcast cannot re-emit it.
```diff
- IN SCOPE: SpaceX's own AI/compute push (orbital data centers, "AI satellites", Starlink + on-orbit compute, Starshield); xAI / Grok / X developments — new Grok models or features, xAI datacenters and compute (e.g. Colossus), funding/compute deals, and how the X platform and xAI tie into the Starlink/SpaceX stack
+ IN SCOPE: SpaceX's own AI/compute push (orbital data centers, "AI satellites", Starlink + on-orbit compute, Starshield); xAI / Grok / X developments — new Grok models or features, xAI datacenters and compute (e.g. Colossus), funding/compute deals, and how the X platform and xAI tie into the Starlink/SpaceX stack. ENTITY HARD RULE: attribute Colossus/Memphis power/turbines/xAI clusters to xAI, not SpaceX, unless a fetched source explicitly states SpaceX ownership of that facility; never coin "SpaceXAI" or "SpaceX AI" as an operator name; keep cross-company deals explicitly cross-company.
```

## Code/metadata-only proposals (no A/B needed)
- **`engine/chapters.py`** (code): P0 listener-facing metadata bug now on Ep58 and Ep60; deterministic garble/filter class with ~100% hit rate per meta-review; no A/B.
- **`shows/spacex.yaml`** (config): P0/P1 chapter miss: Ep56 spoke 'SPC X trading at $114.53' with no Market Watch chapter because pattern required 'is trading'. Metadata-only; Closing where:end must remain listed before Market Watch so sign-off price lines stay Closing.
- **`tests/test_spacex_show.py`** (code): Drift-guards for P0 chapter sanitizer, Market Watch pattern widen, and intro/closing regressions; code-only.

## Deferred (carried forward)
- OPERATOR DECISION (escalation after repeated misses): accept grok-4.3 daily length plateau vs further digest-substrate only (min_digest_words / full-text fetch) — do not re-propose podcast expand, word floors in podcast prompt, or '7+/10 if deep-dive ships' predictions
- OPERATOR DECISION (escalation since 2026-06-13): SPCX price-once — Market Watch qualitative + single precise quote only in closing_block; coupled A/B-listen; stop carrying the same unshipped fix
- Q2/special path: enforce richer spacex_deep_dive.txt briefs so specials clear deep_dive.min_podcast_words 2400 (Ep59 shipped 1778) — digest/brief substrate only
- Tomorrow-teaser rotation (P2; Watch for the first/next <test> no longer dominant in Ep53–62)
- Scheduler forensics for any missed Sunday weekly_summary_segment run (June-28 class) — operator
- NASA public-domain b-roll pool vs retired shorts_ab generated motion — render-side follow-up, not audio

<sub>tokens: 57042 in / 5447 out</sub>