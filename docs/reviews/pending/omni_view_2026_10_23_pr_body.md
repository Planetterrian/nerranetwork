Understanding still opens ~10/10 on the stock “To really understand…” skeleton (de-seed never shipped across three passes), EXAMPLE compliance-deadlines seed remains electable, and “everything turns on whether” (prompt-seeded) hit 5/10 — while digest-verbatim median fell to ~17.5% (hit via grok-4.6 restore) and Progress/chapters stay structurally clean.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1868**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| digest-verbatim % median (last 10 _tts vs digest) after anti-paste/CONTENT DISCIPLINE tighten ships | hit | Ep205–214 median ≈17.5% (8–26% except ep206 56%); baseline was ≈54%; grok-4.6 restore primary driver |
| episodes (last 10) opening Understanding with stock 'To really understand how [NP]' skeleton after de-seed+MEMORY+yaml broaden | miss | Still ~10/10 on To-really-understand family in Ep205–214 transcripts; de-seed never shipped |
| verbatim EXAMPLE compliance-deadlines closer in any _tts/transcript (last 10) after EXAMPLE rewrite | partial | 0 exact paste in Ep205–214; compliance-deadlines sentence still present in omni_view_podcast.txt EXAMPLE |
| Progress Watch slots that are lifehacks/buybacks/pure-security-interdictions without deployment-or-indicator rigor (last 10) after eligibility tighten | partial | No buyback/lifehack; soft picks remain Ep206 X suspensions, Ep209 fire containment, Ep214 Macron meeting |
| episodes with Progress Watch chapter (last 10) | hit | chapters_ep205–214.json all include Progress Watch (10/10 held) |
| audible 'both sides accept' / 'strongest case\|argument for/against' scaffold uses per episode (last 10 max) | partial | both-sides-accept quiet; strongest case on Ep207/211/213; new everything-turns-on-whether on 5/10 |
| successor Understanding opener tic after this de-seed (watch) | hit | Same tic still ≥5/10 and named; no replacement third-gen opener because de-seed never shipped |
| median _tts.txt words (last 10) — observation only unless operator ships digest-depth change | miss | Median ≈1555 on Ep205–214 (was ≈1470); still ≪1700; no digest-depth lever shipped |
| episodes (last 10) with _tts.txt ≥1400 — observation only | partial | 9/10 ≥1400 (ep206=1334 only miss); improved from Sep-28 6/10 |
| lead-story tellings per episode (manual: hook + body + deep dive + go-deeper + teaser) | partial | Deep dive still routinely lead mechanism (Ep205/210/214); full 4–5 body-retell quieter than Ep164/165 |
| source_integrity_claims median | partial | Sep-24 floor still in omni_view.yaml; claim-count field not in this context pack |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/omni_view_podcast.txt`** (prompt) — Ep145 shipped this EXAMPLE closer on an unrelated North Korea lead; seed still in-tree through Aug-23/29/Sep-28. De-seed the quotable line + explicit anti-paste rule; no new stock closer to elect.
```diff
- Host: What happens next: the first compliance deadlines land in six months, and regulators say the earliest enforcement cases will show how strictly the rules bite.
- Host: Now, turning to a developing story in the Middle East...
+ Host: What happens next is the first enforcement wave — regulators have said those early cases will show how strictly the rules bite.
+ Host: Now, turning to a developing story in the Middle East...
+ 
+ ANTI-PASTE (do not echo): Never copy EXAMPLE sentences onto a different story. The EXAMPLE is depth and cadence only — if a closer does not come from today's briefing facts, write a fresh next-step from those facts or stop on the last fact. Do not invent stock closers (no recycled deadline/enforcement boilerplate).
```

**`shows/prompts/omni_view_podcast.txt`** (prompt) — Prompt item (b) literally quoted “everything turns on whether…” and Ep205/207/208/213/214 elected it (5/10). strongest-case residual on Ep207/211/213. De-seed by shape; no quotable menu examples.
```diff
- Rotate at least three structures across a single episode: (a) lead with the empirical ground both sides accept, then the divide; (b) lead with the MECHANISM that splits them ("everything turns on whether…"); (c) lead with one side's best argument in its advocate's own framing, then the other's. Never use the same opening structure on two consecutive stories, and use the literal phrase "the strongest case" at most once per episode.
+ Rotate at least three structures across a single episode: (a) state the shared factual ground in fresh words, then where named advocates split; (b) lead with the single mechanism or decision-point the disagreement turns on — described in that story's own nouns, never a stock clause; (c) lead with one named advocate's best argument in their own framing, then the other's. Never use the same opening structure on two consecutive stories. BANNED verbatim scaffolds (they became audible tics): "everything turns on whether", "the strongest case", "both sides accept", "advocates on each side", "one side frames". Prefer zero uses; if a near-shape slips through, at most one strongest-case-family phrase per entire episode and never on two stories.
```

**`shows/prompts/omni_view_podcast.txt`** (prompt) — Ep206 X suspensions / Ep209 fire containment / Ep214 meeting show soft eligibility after disaster-as-progress cooled. Podcast layer must block audio reframes even if digest mis-picks; negative shapes only.
```diff
- The progress story's first sentence must contain one of these anchor phrases — "progress worth knowing", "what's actually being done", or "pushing in the right direction" — because podcast-app chapters key off them. Build your own sentence around the phrase each day; the anchor is a marker, not a line to recite.
+ The progress story's first sentence must contain one of these anchor phrases — "progress worth knowing", "what's actually being done", or "pushing in the right direction" — because podcast-app chapters key off them. Build your own sentence around the phrase each day; the anchor is a marker, not a line to recite.
+ 
+ PROGRESS ELIGIBILITY AT SCRIPT STAGE (do not echo): Only speak a Progress segment when the briefing item is a concrete measure, deployment, verified indicator, or completed compensation/enrollment with at least one number. Do NOT reframe as progress: disasters/accidents/deaths, stopped rescues, pure security interdictions or account suspensions without a structural reform, fire/flood containment alone, scheduled meetings/talks without a signed measure, corporate buybacks, or household lifehacks. If the briefing's Progress slot is off-bar, cover it as an ordinary world beat without progress anchors — or skip to the next eligible story — and never announce that progress was unavailable.
```

**`shows/prompts/omni_view_podcast.txt`** (prompt) — Ep205–214 still ~10/10 on To-really-understand family; three prior passes proposed de-seed and never shipped. Shape ban + verbatim stock list; keep a path for chapter anchors without electing one quoted opener.
```diff
- - The Understanding the Issue deep dive: 250-300 words.
+ - The Understanding the Issue deep dive: 250-300 words. Open on the mechanism or misunderstanding itself in fresh nouns from today's lead — do NOT open with the stock skeletons "To really understand how…", "To really understand [topic]…", "You need to really understand…", "something most coverage leaves out", or "Most coverage treats/assumes…". Those phrases saturated 8–10/10 episodes and became audible scaffolding. One short clause may still use a chapter-anchor token from the allowed set only if it sits inside a fact-bearing sentence (see delivery anchors); never as a cold stock gate. Do not restate the lead's full body; explain the mechanism the lead did not have room for. If recent scripts (frame memory / prior openers) already used a shape, pick a different shape.
```

**`shows/omni_view.yaml`** (config) — If podcast openers rotate off the stock To-really-understand pair, chapter detection must accept new shapes in the same change set (PT dead-marker class). Audio-adjacent → A/B-listen.
```diff
-   - pattern: to really understand|to understand .{1,80}? more fully|most coverage leaves out|here's the thing that changes
-     title: Understanding the Issue
+   - pattern: to really understand|to understand .{1,80}? more fully|most coverage leaves out|here's the thing that changes|what changes the reading|the mechanism underneath|the part most summaries skip|here's the constraint that actually binds|look at the .{1,40}? not the .{1,40}
+     title: Understanding the Issue
```

**`shows/prompts/omni_view_digest.txt`** (prompt) — Digest is where Ep144/Ep158/Ep206/Ep209/Ep214-class mis-picks start; tighten with negative shapes only.
```diff
- PROGRESS WATCH (instruction — do not echo): one concrete, verifiable "what's being done" development from today's sources — a measure passed, a disease indicator falling, infrastructure or technology actually deployed, a negotiation producing real terms. Name the actors, include at least one number, and acknowledge the main complication in one clause. NEVER corporate PR, never a cute story, never a silver lining invented for a tragedy — this segment earns trust by being as rigorous as the hard news. If nothing in today's sources clears this bar, cover a fourth world story in this slot instead (do not write a sentence announcing the absence).
+ PROGRESS WATCH (instruction — do not echo): one concrete, verifiable "what's being done" development from today's sources — a measure passed with force, a disease or environmental indicator moving with a number, infrastructure or technology actually deployed, enrollment/compensation delivered, or a negotiation that produced signed terms. Name the actors, include at least one number, and acknowledge the main complication in one clause. NEVER corporate PR, never a cute story, never a silver lining invented for a tragedy, never a scheduled meeting or talk alone, never pure security interdictions/account suspensions without structural reform, never disaster containment or stopped-rescue updates dressed as progress, never buybacks or household lifehacks. If nothing in today's sources clears this bar, cover a fourth world story in this slot instead (do not write a sentence announcing the absence). Describe eligibility with negative shapes only — do not give a quotable "good example" story the model can elect as next tic.
```

**`shows/prompts/omni_view_digest.txt`** (prompt) — Digest still seeds spoken strongest-case / mechanism scaffolds; remove prompt's own recommended stock phrases that became tics (empirical-ground-both-sides-accept and strongest-case rotation copy).
```diff
- CRITICAL — NAME WHO HOLDS EACH POSITION, AND DO NOT FALL INTO A TEMPLATE: Attach every steel-manned position to the actual people, parties, institutions, or schools of thought who hold it ("Treasury officials argue…", "civil-liberties groups counter…", "free-market economists contend…") — NEVER anonymous "one side" / "the other side" / "advocates on each side", and equally NEVER the anonymous "position" variants "one position holds…" / "a competing position maintains…" / "another position holds…" (July 2026: these became the new anonymous scaffold as the older frames were banned — up to twice per episode — and they violate this same name-the-advocate rule). Every position names who actually makes the case. Equally important: VARY how you introduce the sides from story to story. Do NOT open every story's steel-man with the same stock sentence frame. The phrase "the strongest case" may appear AT MOST ONCE in the entire digest — recent digests opened nearly every story with "The strongest case for X rests on… / The strongest case for Y rests on…" until the scaffolding drowned out the ideas. Rotate the structure: sometimes lead with the empirical ground both sides accept and then the divide; sometimes lead with the single mechanism the whole disagreement turns on; sometimes lead with the named advocate's own framing of their best argument.
+ CRITICAL — NAME WHO HOLDS EACH POSITION, AND DO NOT FALL INTO A TEMPLATE: Attach every steel-manned position to the actual people, parties, institutions, or schools of thought who hold it ("Treasury officials argue…", "civil-liberties groups counter…", "free-market economists contend…") — NEVER anonymous "one side" / "the other side" / "advocates on each side", and equally NEVER the anonymous "position" variants "one position holds…" / "a competing position maintains…" / "another position holds…". Every position names who actually makes the case. VARY how you introduce the sides from story to story — do NOT open every contested story with the same stock sentence frame. BANNED verbatim frames (they recur as every-story scaffolding): "Both sides agree…", "both sides accept…", "the strongest case", "everything turns on whether", "advocates on each side". State shared facts in fresh words each time; name who splits and on what mechanism, using that story's own nouns. Prefer zero uses of the banned frames in the entire digest.
```

## Code/metadata-only proposals (no A/B needed)
- **`tests/test_omni_view_quality_pass.py`** (code): Every behavioral fix needs a drift-guard per playbook; pins bans and chapter-pattern broaden without weakening hard guardrails; wiring through real load_config.

## Deferred (carried forward)
- Chronic under-length: operator decision only — audit last-10 digest word counts vs min_digest_words 1500 and deepen-expansion hit rate before any digest-depth config change; do NOT re-propose podcast_expand_below_target, min_podcast_words hikes, or prompt word-pressure (multiple misses; network do_not_retry class)
- Operator decision: Understanding de-seed + yaml broaden + EXAMPLE rewrite proposed on Aug-23, Aug-29, and Sep-28 with shipped:[] each time — apply the paired bundle or explicitly reject and accept stock openers as permanent chapter anchors
- Reuters/AP Google News proxy label attribution still cosmetic (July-18 carry)
- BBC Latin America feed low-volume monitor (July-18 carry)
- Network tooling: mechanical digest lint for template-saturation counts (strongest-case / everything-turns-on-whether / shared-facts family)
- Sep-05 closing pool pin (three essay-style closings; 6/10 identical heavy-news essay this window) — after flagship A/B readout
- Sep-24 source_integrity_claims median readout once metrics expose the field
- Confirm ep206 actual llm_script_model in credit_usage (56% verbatim / 1334w / 1.6 commas looks like 4.3 fallback day under the 4.6 pin)
- OP3 / YouTube long-form retention as network-funnel topics (long retention 11.3%) — not OV-only editorial blockers this pass
- Watch fourth-generation Understanding opener convergence next pass after proposed bans finally ship (successor-tic prediction recorded)

## Drift-guard status
```
============================= test session starts ==============================
collected 35 items

tests/test_omni_view_quality_pass.py ................................... [100%]

============================== 35 passed in 1.73s ==============================
```

<sub>tokens: 69365 in / 8007 out</sub>