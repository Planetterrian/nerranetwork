July-18 realignment largely held (no Both-sides/question-worth-considering tics, Progress Watch on 9/10, tabloid slots gone) but median length still misses (~1449 vs ≥1700), Ep145 shipped the podcast EXAMPLE’s “compliance deadlines” line onto a North Korea story, Progress Watch keeps accepting disasters/non-progress, and deep-dive openers plus a new “shared facts / interpretations split” scaffold have saturated.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1260**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| tabloid/gossip/celebrity items per episode (Ep115+) | hit | Ep143–152 have no gossip/celebrity slots; snapshot fetch-filter leakage 0; structural July-18 slate held |
| "Both sides agree" family occurrences per 10 episodes | hit | 0 verbatim Both-sides-agree/accept/recognize frames in Ep143–152 transcripts (baseline ~38) |
| "the question worth considering" per 10 episodes | hit | 0 hits in Ep143–152 transcripts (baseline 23) |
| median _tts.txt words (Ep115+) | miss | Ep143–152 median ≈1449 words; expected ≥1700; 4/10 under 1400 floor |
| distinct regions per episode (lead+world) | hit | Window episodes routinely cover ≥3 regions in lead+world (e.g. Ep143, Ep152) |
| episodes with a Progress Watch chapter | hit | 9/10 chapters_ep143–152 include Progress Watch (only ep147 missing) |
| episodes (last 10) with _tts.txt word count >=1400 | miss | 6/10 ≥1400 (snapshot ep143–152); expected 10/10 |
| "Both sides agree" constructions per episode digest | hit | Superseded Jul-18 de-seed; spoken window clean of the family (urgency prediction resolved by shipped realignment) |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/omni_view_podcast.txt`** (prompt) — Ep145 shipped the EXAMPLE's compliance-deadlines closer on a North Korea troop lead — verified transcript bleed. Rewrite the line and add an explicit anti-paste rule (de-seed-by-shape; no quotable stock closer).
```diff
- Host: What happens next: the first compliance deadlines land in six months, and regulators say the earliest enforcement cases will show how strictly the rules bite.
- Host: Now, turning to a developing story in the Middle East...
+ Host: What happens next: member states must designate national regulators within a year, and the first enforcement cases will show how uneven application across twenty-seven countries actually looks.
+ Host: Now, turning to a developing story in the Middle East...
+ 
+ CRITICAL — EXAMPLE IS NOT COPY-PASTE STOCK: The EXAMPLE story above illustrates depth and cadence only. NEVER reuse its sentences, numbers, deadlines, or "what happens next" lines on any other story. If a story lacks a concrete next step in the briefing, say what is still unknown rather than importing a line from this example.
```

**`shows/prompts/omni_view_podcast.txt`** (prompt) — Ep144 used an earthquake as Progress Watch; Ep149 used a thin hotel-CEO/safety item; Ep147 skipped the segment. Mirror digest eligibility at script stage so audio cannot reframe tragedies as progress.
```diff
- - Open the progress story with ONE of these transitions (rotate; do not invent a different one — it anchors the chapter marker): "Now, some progress worth knowing about." / "Here's what's actually being done about a problem we've covered." / "One development pushing in the right direction."
+ - Open the progress story with ONE of these transitions (rotate; do not invent a different one — it anchors the chapter marker): "Now, some progress worth knowing about." / "Here's what's actually being done about a problem we've covered." / "One development pushing in the right direction."
+ - PROGRESS WATCH ELIGIBILITY (podcast layer): same rigor bar as the briefing — named actors, at least one number, main complication in one clause. NEVER put disasters, accidents, earthquakes, deaths, crime, or pure court dismissals in this slot. Corporate executive departures only count if the briefing documents a concrete operational fix already underway with a measurable milestone. If the briefing used the slot for a fourth world story or the item fails this bar, cover that world story here with a normal story transition — do NOT force a progress frame and do NOT announce the skip.
```

**`shows/prompts/omni_view_podcast.txt`** (prompt) — Banned frames cleared, but Ep148 dual 'strongest argument' and recurring 'undisputed fact / interpretations split' are the audible third-generation scaffold. De-seed by shape + verbatim caps; ledger predicts successor watch.
```diff
- - DO NOT ESCAPE ONE TEMPLATE INTO ANOTHER (June 10 2026: when episodes stopped saying "the strongest case" they switched to an equally rigid, equally audible scaffold — "One side frames X as… / The other side frames Y as… / Advocates on each side acknowledge…" on story after story). That anonymous "one side / the other side / advocates on each side" frame is BANNED: it also violates the rule above that every perspective must name a specific outlet, party, official, or group. Also BANNED for the same reason are the anonymous "position" variants "one position holds…" / "a competing position maintains…" / "another position holds…" (July 2026: as the older anonymous frames were banned, these became the replacement scaffold — twice per episode by Ep128/Ep129 — and they strip the listener of who is actually making the case). Always attach the position to who actually holds it ("the Treasury argues…", "the Guardian frames it as…", "Conservative MPs counter…"). If you notice two consecutive stories sharing the same sentence skeleton — whatever the skeleton — rewrite the second one.
+ - DO NOT ESCAPE ONE TEMPLATE INTO ANOTHER (June 10 2026: when episodes stopped saying "the strongest case" they switched to an equally rigid, equally audible scaffold — "One side frames X as… / The other side frames Y as… / Advocates on each side acknowledge…" on story after story). That anonymous "one side / the other side / advocates on each side" frame is BANNED: it also violates the rule above that every perspective must name a specific outlet, party, official, or group. Also BANNED for the same reason are the anonymous "position" variants "one position holds…" / "a competing position maintains…" / "another position holds…" (July 2026: as the older anonymous frames were banned, these became the replacement scaffold — twice per episode by Ep128/Ep129 — and they strip the listener of who is actually making the case). August 2026 successor scaffolds — also BANNED as every-contested-story openers: (1) paired "The strongest argument for X… / The strongest argument against Y…" (Ep148 shipped both; treat "strongest argument for/against" like "the strongest case" — combined cap ONE use of any "strongest case|strongest argument" phrase per episode); (2) the stock two-liner "The shared/undisputed facts are… Outlets/interpretations differ/split on…" used as the spine of multiple stories in one episode. State shared facts in fresh words once, name who interprets them differently, and vary structure across stories. Always attach the position to who actually holds it ("the Treasury argues…", "the Guardian frames it as…", "Conservative MPs counter…"). If you notice two consecutive stories sharing the same sentence skeleton — whatever the skeleton — rewrite the second one.
```

**`shows/prompts/omni_view_podcast.txt`** (prompt) — Snapshot 8/10 on both deep-dive stock phrases; de-seed by shape while preserving one chapter-anchor token so markers do not die (coordinate with yaml pattern broaden).
```diff
- Now, to really understand this story
+ DEEP DIVE OPENER ROTATION (Understanding the Issue): Do NOT open this segment the same way every episode. Ban saturating the pair "Now, to really understand this story" + "there is something most coverage leaves out" / "Most coverage treats…" as the default (it shipped on ~8/10 recent episodes and sounds like a template). Rotate across at least three shapes over a week, for example: (a) lead with the concrete mechanism most explainers skip, named in the first sentence; (b) lead with a historical calibration fact, then the mechanism; (c) lead with the checkable test a listener can apply next time they see the headline. You may still use "most coverage leaves out" at most once per episode and not on consecutive episodes. Chapter audio still needs one of the anchor phrases somewhere in the first three sentences of the deep dive so markers fire: include exactly one of "to really understand", "most coverage leaves out", or "here's the thing that changes" — not all three, and not the full stock paragraph every day.
```

**`shows/omni_view.yaml`** (config) — If podcast openers rotate off the old stock pair, chapter detection must accept the new shapes in the same change set (PT dead-marker class). Metadata/chapter-only risk is audio-adjacent → A/B-listen.
```diff
-   - pattern: to really understand|to understand .{1,80}? more fully|most coverage leaves out|here's the thing that changes
-     title: Understanding the Issue
+   - pattern: to really understand|to understand .{1,80}? more fully|most coverage leaves out|here's the thing that changes|what the headline skips|mechanism most explainers skip|historical calibration|checkable test when you next see
+     title: Understanding the Issue
```

**`shows/prompts/omni_view_digest.txt`** (prompt) — Digest is where Ep144-class mis-picks start; tighten eligibility with negative shapes (no quotable 'good' example that becomes the next tic).
```diff
- PROGRESS WATCH (instruction — do not echo): one concrete, verifiable "what's being done" development from today's sources — a measure passed, a disease indicator falling, infrastructure or technology actually deployed, a negotiation producing real terms. Name the actors, include at least one number, and acknowledge the main complication in one clause. NEVER corporate PR, never a cute story, never a silver lining invented for a tragedy — this segment earns trust by being as rigorous as the hard news. If nothing in today's sources clears this bar, cover a fourth world story in this slot instead (do not write a sentence announcing the absence).
+ PROGRESS WATCH (instruction — do not echo): one concrete, verifiable "what's being done" development from today's sources — a measure passed, a disease indicator falling, infrastructure or technology actually deployed, a negotiation producing real terms. Name the actors, include at least one number, and acknowledge the main complication in one clause. NEVER corporate PR, never a cute story, never a silver lining invented for a tragedy — this segment earns trust by being as rigorous as the hard news. INELIGIBLE for this slot (put these in world/econ with context + what-happens-next only): earthquakes, storms, accidents, mine collapses, wars/attacks, deaths, crime, and court case dismissals or procedural rulings that do not themselves enact a forward reform with a named implementer and milestone. If nothing in today's sources clears this bar, cover a fourth world story in this slot instead (do not write a sentence announcing the absence).
```

## Code/metadata-only proposals (no A/B needed)
- **`tests/test_omni_view_quality_pass.py`** (code): Every behavioral fix needs a drift-guard per playbook; mirrors TestEditorialRealignmentJuly18 style without weakening hard guardrails.

## Deferred (carried forward)
- Chronic under-length: escalate to operator — audit last-10 digest word counts vs min_digest_words 1500 and deepen-expansion hit rate before any further length config; do NOT re-propose podcast_expand_below_target, min_podcast_words hikes, or prompt word-pressure (multiple misses; network do_not_retry class)
- Reuters/AP Google News proxy label attribution still cosmetic (July-18 carry)
- BBC Latin America feed low-volume monitor (July-18 carry)
- Network tooling: mechanical digest lint for template-saturation counts (shared-facts/interpretations-split family)
- Watch third-generation steel-man convergence next pass if dual-scaffold ban ships

## Drift-guard status
```
============================= test session starts ==============================
collected 35 items

tests/test_omni_view_quality_pass.py ................................... [100%]

============================== 35 passed in 1.61s ==============================
```

<sub>tokens: 45841 in / 5715 out</sub>