P0 Title:-prefixed chapters remain in Ep58/Ep60 (sanitizer still unshipped), engineering-anchor tic is still 10/10, 5/10 dailies under 1300w with Ep61 at 863w, and length/price-once stay escalated operator decisions after repeated unshipped proposals.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1568**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| chapters_ep*.json titles matching /^Title:\s*/ or bare truncated headline chapters outside known section set in next 10 spacex episodes | miss | Sanitizer never applied; Ep58 six Title: chapters and Ep60 three Title: + one bare headline still committed; Ep61–67 clean |
| exact phrase 'from an engineering standpoint' in next 10 daily (non-special) transcripts | miss | Ep58–67 Whisper: phrase still 10/10; Aug-05/07 anchor-rotation prompt never applied |
| Market Watch chapter present when script contains SPCX/S P C X + trading/closed price line (non-special dailies) | miss | Pattern widen never shipped; YAML still lacks bare trading at / tape openers; Ep67 also fired Market Watch mid-body on an early closed-at line |
| on-air xAI facility attributed as SpaceX (Memphis/Colossus/'SpaceX AI' datacenter operator) in next 10 transcripts | partial | 0 clear mis-attrs in Ep58–67 window; entity prompt never shipped so Ep53-class regression risk remains |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/spacex_podcast.txt`** (prompt) — P1: 10/10 monoculture on one required phrase across Ep58–67; de-seed by shape + finite rotation set + MEMORY per July 2026 meta-review; no new quotable full-sentence example; successor-tic prediction logged for 'the engineering angle' convergence.
```diff
- REQUIRED: the segment's first sentence must contain "from an engineering standpoint" or "the engineering angle" — podcast-app chapters key off this phrase. Vary everything after it daily.
+ REQUIRED CHAPTER ANCHOR (first sentence of this segment only): the opening sentence MUST include exactly one of these anchor shapes so podcast-app chapters fire — (1) the words "engineering standpoint" used inside a fresh clause, (2) the words "engineering angle", (3) the words "engineering reality", or (4) the words "engineering deep dive". Rotate across the set; do NOT reuse the same anchor wording as the immediately previous episode (treat recent openers as a do-not-reuse MEMORY list). VERBATIM BAN: never open with the exact six-word run "from an engineering standpoint" if that run already appeared as the opener in a recent episode — rephrase the clause while keeping one allowed anchor shape. Do not copy any example sentence from this prompt. Vary everything after the anchor daily.
```

**`shows/prompts/spacex_podcast.txt`** (prompt) — P1 regression guard: Ep53 on-air 'SpaceX AI added another data center building in Memphis' class; window Ep58–67 clean but prompt never shipped; A/B-listen.
```diff
- Cover the digest's AI & Compute section: the SpaceX↔AI thread where rockets, satellites, and the Musk compute ecosystem meet — orbital data centers and "AI satellites", Starlink + on-orbit compute and direct-to-cell, notable xAI / Grok / X developments (new Grok capabilities, xAI datacenters like Colossus, how X and xAI tie into the Starlink/SpaceX stack and the IPO's AI-infrastructure spend), AND Cursor / Anysphere when the digest covers it
+ Cover the digest's AI & Compute section: the SpaceX↔AI thread where rockets, satellites, and the Musk compute ecosystem meet — orbital data centers and "AI satellites", Starlink + on-orbit compute and direct-to-cell, notable xAI / Grok / X developments (new Grok capabilities, xAI datacenters like Colossus, how X and xAI tie into the Starlink/SpaceX stack and the IPO's AI-infrastructure spend), AND Cursor / Anysphere when the digest covers it. ENTITY DISCIPLINE (hard rule): Colossus, Memphis turbines, and xAI training/inference clusters are xAI facilities unless the digest explicitly states SpaceX owns or operates that building; never say "SpaceX AI" as a company or facility name; never fuse into "SpaceXAI". Cross-company compute deals, capex flowing through SpaceX, and Starlink backhaul ties are fine when attributed as deals/ties — not as SpaceX owning xAI's datacenter.
```

**`shows/prompts/spacex_digest.txt`** (prompt) — Digest is the substrate the podcast is licensed to read; fix conflation at source so podcast cannot re-emit it.
```diff
- IN SCOPE: SpaceX's own AI/compute push (orbital data centers, "AI satellites", Starlink + on-orbit compute, Starshield); xAI / Grok / X developments — new Grok models or features, xAI datacenters and compute (e.g. Colossus), funding/compute deals, and how the X platform and xAI tie into the Starlink/SpaceX stack
+ IN SCOPE: SpaceX's own AI/compute push (orbital data centers, "AI satellites", Starlink + on-orbit compute, Starshield); xAI / Grok / X developments — new Grok models or features, xAI datacenters and compute (e.g. Colossus), funding/compute deals, and how the X platform and xAI tie into the Starlink/SpaceX stack. ENTITY DISCIPLINE: label Colossus/Memphis/xAI clusters as xAI unless a source states SpaceX ownership; never invent "SpaceXAI"; attribute cross-company deals as deals. Digest is the substrate the podcast is licensed to read — correct attribution here prevents on-air conflation.
```

## Code/metadata-only proposals (no A/B needed)
- **`engine/chapters.py`** (code): P0 listener-facing metadata bug still on Ep58 and Ep60; deterministic garble/filter class with ~100% hit rate per meta-review; no A/B; third review still unshipped.
- **`shows/spacex.yaml`** (config): P0/P1 chapter miss class: bare 'trading at' and tape openers never match; metadata-only. Closing where:end must remain listed BEFORE Market Watch so sign-off-only price lines stay Closing (Ep3/Ep62–64 class).
- **`tests/test_spacex_show.py`** (code): Drift-guards for P0 chapter sanitizer, Market Watch pattern widen, and intro/closing regressions; code-only.

## Deferred (carried forward)
- OPERATOR DECISION (escalation after repeated misses): accept grok-4.3 daily length plateau vs further digest-substrate only (min_digest_words / full-text fetch) — do not re-propose podcast expand, word floors in podcast prompt, or '7+/10 if deep-dive ships' predictions
- OPERATOR DECISION (escalation since 2026-06-13): SPCX price-once — Market Watch qualitative + single precise quote only in closing_block; coupled A/B-listen; stop carrying the same unshipped fix as a silent proposal
- Q2/special path: enforce richer spacex_deep_dive.txt briefs so specials clear deep_dive.min_podcast_words 2400 (Ep59 shipped 1778) — digest/brief substrate only
- Tomorrow-teaser rotation (P2; Watch for the first/next <test> no longer dominant in Ep58–67)
- Scheduler forensics for any missed Sunday weekly_summary_segment run (June-28 class) — operator
- NASA public-domain b-roll pool vs retired shorts_ab generated motion — render-side follow-up, not audio

<sub>tokens: 60858 in / 5844 out</sub>