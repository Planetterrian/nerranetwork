July-18 realignment still holds on tabloid/Both-sides-family ceilings in most eps, but Aug-23 proposals never shipped: deep-dive openers remain 8–9/10 stock, Progress Watch shipped a disaster (Ep158) and skipped once (Ep157), banned 'Both sides agree' and 'advocates on each side' reappeared, EXAMPLE-bleed risk is still in the prompt, and median length fell further (~1411) — escalate digest depth only.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1347**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| verbatim podcast-EXAMPLE lines in _tts/transcripts (e.g. compliance-deadlines what-happens-next) | partial | Exact Ep145 compliance-deadlines line absent Ep150–159; EXAMPLE rewrite never shipped; Ep153 still uses compliance-shaped what-happens-next; seed remains in podcast prompt |
| episodes (last 10) opening Understanding deep-dive with exact 'something most coverage leaves out' + 'Most coverage treats' | miss | Still 8–9/10 in Ep150–159 (snapshot 8/10 + 8/10); de-seed never shipped |
| Progress Watch slots that are disasters/accidents/deaths (last 10) | miss | Ep158 Progress = stopped Nepal-border rescue after lake overflow; Ep154 Hawk-fire containment after 30+ homes; expected 0 |
| episodes with Progress Watch chapter (last 10) | miss | 9/10 — chapters_ep157.json has no Progress Watch (expected 10/10) |
| "strongest argument for/against" dual-scaffold uses per episode (last 10 max) | partial | Exact strongest-argument phrase quiet; successors shipped — Ep151 case-for/case-against; Ep152 interpretations-split; Ep159 advocates-on-each-side; Ep155 Both-sides-agree regression |
| median _tts.txt words (last 10) — observation only, no new podcast lever | miss | Median ≈1411 on Ep150–159 (baseline ≈1449); 5/10 under 1400; no digest-depth lever shipped |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/omni_view_podcast.txt`** (prompt) — Ep145 verbatim EXAMPLE bleed; seed still in prompt; Ep153 near-shape compliance closer. De-seed by rewriting the quotable line + explicit anti-paste rule (shape ban, no new quotable stock closer).
```diff
- Host: What happens next: the first compliance deadlines land in six months, and regulators say the earliest enforcement cases will show how strictly the rules bite.
- Host: Now, turning to a developing story in the Middle East...
+ Host: What happens next: member states have eighteen months to stand up national regulators, and the first enforcement actions will show whether the high-risk rules have teeth in practice.
+ Host: Now, turning to a developing story in the Middle East...
+ 
+ (Add nearby rule, not spoken:) NEVER paste sentences from this EXAMPLE into a different story. Every "what happens next" line must be specific to the story just told — dates, actors, and mechanisms from the briefing only. Stock closers from the EXAMPLE are a critical failure (Ep145 shipped the old compliance-deadlines line onto a North Korea troop lead).
```

**`shows/prompts/omni_view_podcast.txt`** (prompt) — Snapshot 8/10 on both stock phrases across Ep150–159; Aug-23 de-seed never applied. De-seed by shape + verbatim ban + rotation MEMORY; coordinate with yaml pattern broaden so markers do not die.
```diff
- (Understanding deep-dive openers currently converge on the chapter-anchor pair seeded implicitly via yaml patterns and habit:) 'Now, to really understand this story' + 'something most coverage leaves out' / 'Most coverage treats…'
+ UNDERSTANDING THE ISSUE — OPENER ROTATION (do not read aloud): Open the deep dive with a story-specific bridge, not a stock cold open. BANNED verbatim openers (shipped 8–10/10 recently): "something most coverage leaves out"; "Most coverage treats"; "Most coverage assumes"; the fixed pair "Now, to really understand this story, there's something most coverage leaves out." Rotate across ≥3 shapes per week, e.g. (a) name the mechanism listeners are missing in one clause then unpack it; (b) name the primary-document check that changes the reading; (c) calibrate with one historical parallel then the present mechanism. Do not reuse the same opener shape as the previous two episodes (see RECENT DEEP-DIVE OPENERS memory when injected). Keep one short in-body phrase the chapter detector can still hear — prefer varied anchors already listed in yaml ("to understand … more fully", "here's the thing that changes") rather than the banned stock pair.
```

**`shows/omni_view.yaml`** (config) — If podcast openers rotate off the old stock pair, chapter detection must accept new shapes in the same change set (PT dead-marker class). Audio-adjacent → A/B-listen.
```diff
- - pattern: to really understand|to understand .{1,80}? more fully|most coverage leaves out|here's the thing that changes
-     title: Understanding the Issue
+ - pattern: to really understand|to understand .{1,80}? more fully|most coverage leaves out|here's the thing that changes|what most reports skip|the mechanism underneath|the primary (document|check|figure) that changes|a clearer way to read this|what the (process|timeline|licensing|surveillance) actually looks like
+     title: Understanding the Issue
```

**`shows/prompts/omni_view_podcast.txt`** (prompt) — Ep158 disaster-as-progress and Ep157 skip; podcast layer must block audio from reframing tragedies as progress even if digest mis-picks.
```diff
- Open the progress story with ONE of these transitions (rotate; do not invent a different one — it anchors the chapter marker): "Now, some progress worth knowing about." / "Here's what's actually being done about a problem we've covered." / "One development pushing in the right direction."
+ Open the progress story with ONE of these transitions (rotate; do not invent a different one — it anchors the chapter marker): "Now, some progress worth knowing about." / "Here's what's actually being done about a problem we've covered." / "One development pushing in the right direction."
+ 
+ PROGRESS WATCH ELIGIBILITY (script stage — mirror the briefing): Named actors, ≥1 number, main complication in one clause. INELIGIBLE for this slot (cover a fourth world story instead, and do not announce the skip): disasters, accidents, deaths, obituaries; stopped or failed rescues; wildfire/earthquake/flood containment-only updates with no structural fix; court dismissals without a reform; pure entertainment/box-office trends; corporate PR; any item already covered earlier in this episode. Manufacturing "progress" from a tragedy is a critical failure (Ep144 earthquake; Ep158 stopped Nepal-border rescue shipped as Progress Watch).
```

**`shows/prompts/omni_view_digest.txt`** (prompt) — Digest is where Ep144/Ep158-class mis-picks start; tighten eligibility with negative shapes (no quotable 'good' example that becomes the next tic).
```diff
- PROGRESS WATCH (instruction — do not echo): one concrete, verifiable "what's being done" development from today's sources — a measure passed, a disease indicator falling, infrastructure or technology actually deployed, a negotiation producing real terms. Name the actors, include at least one number, and acknowledge the main complication in one clause. NEVER corporate PR, never a cute story, never a silver lining invented for a tragedy — this segment earns trust by being as rigorous as the hard news. If nothing in today's sources clears this bar, cover a fourth world story in this slot instead (do not write a sentence announcing the absence).
+ PROGRESS WATCH (instruction — do not echo): one concrete, verifiable "what's being done" development from today's sources — a measure passed, a disease indicator falling, infrastructure or technology actually deployed, a negotiation producing real terms, a verified deployment or funding commitment with a named complication. Name the actors, include at least one number, and acknowledge the main complication in one clause. NEVER corporate PR, never a cute story, never a silver lining invented for a tragedy, never entertainment/box-office as progress, never disaster/accident/death coverage, never a stopped rescue or containment-only wildfire/flood update, never a duplicate of a story already used above. This segment earns trust by being as rigorous as the hard news. If nothing in today's sources clears this bar, cover a fourth world story in this slot instead (do not write a sentence announcing the absence).
```

**`shows/prompts/omni_view_podcast.txt`** (prompt) — Banned frames partially returned (Ep155 Both-sides, Ep159 advocates-on-each-side) and successors saturated (Ep151 case-for/against, Ep152 interpretations-split). Extend bans by shape + verbatim caps; ledger watches next successor.
```diff
- - VARY HOW YOU INTRODUCE THE SIDES ... use the literal phrase "the strongest case" at most once per episode.
- - DO NOT ESCAPE ONE TEMPLATE INTO ANOTHER ... anonymous "one side / the other side / advocates on each side" frame is BANNED ... anonymous "position" variants ... BANNED ...
+ - VARY HOW YOU INTRODUCE THE SIDES ... "the strongest case" AND "the strongest argument for/against" combined at most ONCE per episode.
+ - DO NOT ESCAPE ONE TEMPLATE INTO ANOTHER: anonymous "one side / the other side / advocates on each side" is BANNED (Ep159 regressed: "Even advocates on each side note…"). Anonymous "position" variants BANNED. ALSO BANNED as every-contested-story skeletons: dual openers "The case for X rests on… / The case against Y rests on…" (Ep151); "Both sides agree…" (Ep155 regression — still banned verbatim); the shared-facts skeleton "undisputed fact / shared factual ground … interpretations split / views diverge / they differ on whether" used on consecutive contested stories. State shared facts in fresh words each time; name who holds each view; if two consecutive stories share any sentence skeleton, rewrite the second.
```

## Code/metadata-only proposals (no A/B needed)
- **`tests/test_omni_view_quality_pass.py`** (code): Every behavioral fix needs a drift-guard per playbook; pins bans and chapter-pattern broaden without weakening hard guardrails.

## Deferred (carried forward)
- Chronic under-length: operator decision only — audit last-10 digest word counts vs min_digest_words 1500 and deepen-expansion hit rate before any digest-depth config change; do NOT re-propose podcast_expand_below_target, min_podcast_words hikes, or prompt word-pressure (multiple misses; network do_not_retry class)
- Reuters/AP Google News proxy label attribution still cosmetic (July-18 carry)
- BBC Latin America feed low-volume monitor (July-18 carry)
- Network tooling: mechanical digest lint for template-saturation counts (interpretations-split / case-for-case-against / shared-facts family)
- Watch fourth-generation steel-man / deep-dive opener convergence next pass after proposed bans ship (successor-tic prediction recorded)
- OP3 volatility as network-funnel topic (42/7d cooled from 133; not OV-only editorial blocker)

## Drift-guard status
```
============================= test session starts ==============================
collected 35 items

tests/test_omni_view_quality_pass.py ................................... [100%]

============================== 35 passed in 1.14s ==============================
```

<sub>tokens: 48375 in / 6323 out</sub>