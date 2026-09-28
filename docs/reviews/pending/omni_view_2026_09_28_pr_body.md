Aug–Sep proposals largely never applied: Understanding still opens 9–10/10 on “to really understand how…”, digest-verbatim paste median ~54% (Sep-05 ≤25% miss), EXAMPLE compliance seed still in the podcast prompt, and 4/10 scripts under the 1400 floor — Progress chapter presence is finally 10/10 and disaster-as-progress is quiet this window.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1789**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes (last 10) opening Understanding with verbatim 'something most coverage leaves out' (after de-seed+MEMORY ships) | partial | Exact phrase rare in Ep180–189; successor stock 'To really understand how…' is 9–10/10; de-seed never shipped |
| Progress Watch slots that are disasters/accidents/deaths/stopped-rescues (last 10, after eligibility ban ships) | hit | 0 Ep158-class disaster-as-progress in Ep180–189 Progress slots (weak picks remain: bags/buybacks/plot stop) |
| episodes with Progress Watch chapter (last 10) | hit | chapters_ep180–189.json all include Progress Watch (10/10) |
| verbatim 'Both sides agree' + 'advocates on each side' in last-10 transcripts | partial | Exact pair quiet; Ep185/186 use 'both sides accept'; Ep182 uses 'strongest case' |
| dual 'case for / case against' story openers per episode (last 10 max) | hit | 0 dual case-for/against openers heard in Ep180–189 window |
| verbatim EXAMPLE compliance-deadlines closer in any _tts/transcript (last 10) | partial | 0 exact paste in Ep180–189; compliance-deadlines sentence still in omni_view_podcast.txt EXAMPLE |
| successor deep-dive opener tic (third-generation stock phrase after de-seed) — watch metric | hit | Named successor: 'To really understand how [topic]…' on 9–10/10 (snapshot 9/10) |
| median _tts.txt words (last 10) — observation only unless operator ships digest-depth change | miss | Median ≈1470 on Ep180–189; 4/10 under 1400; no digest-depth lever shipped; still ≪1700 |
| lead-story tellings per episode (manual: hook + body + deep dive + go-deeper + teaser) | partial | Full 4–5 body-retell quieter than Ep164/165; deep dive still routinely lead-mechanism (Ep180/181/189) |
| 'watch-for' + 'nothing-to-say' filler shapes per episode (script_audit) | hit | Filler 1–7% last 10; no Ep165-class nothing-announced cluster; tomorrow teaser intentional |
| script_digest_overlap_pct median | miss | digest-verbatim median ≈54% (ep183 75%, ep189 71%) vs expected ≤25% |
| source_integrity_claims median | partial | Sep-24 floor shipped in omni_view.yaml (fetch_full_text 12, preferred_domains); claim-count metric not in provided pack |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/omni_view_podcast.txt`** (prompt) — Ep145 shipped the EXAMPLE's compliance-deadlines closer on an unrelated North Korea troop lead; Aug-23/29 flagged it; seed still in-tree. De-seed the quotable line + explicit anti-paste rule (shape ban, no new stock closer to elect).
```diff
- Host: What happens next: the first compliance deadlines land in six months, and regulators say the earliest enforcement cases will show how strictly the rules bite.
- Host: Now, turning to a developing story in the Middle East...
+ Host: What happens next is the Commission's first enforcement wave — which sectors get opened first will show whether the rules have teeth or stay on paper.
+ Host: Now, turning to a developing story in the Middle East...
+ 
+ (ANTI-EXAMPLE-PASTE — do not echo): The EXAMPLE above is a depth/style sample only. NEVER copy its sentences, closers, or “what happens next” lines onto a different story. Every closer must be entailed by THAT story's own briefing facts. If a line could slot unchanged onto another episode's lead, rewrite it.
```

**`shows/prompts/omni_view_podcast.txt`** (prompt) — Snapshot+transcripts: 'to really understand how' 9–10/10. De-seed by shape + verbatim stock ban + rotation MEMORY; keep one anchor token so chapters survive; pair with yaml broaden.
```diff
- - The progress story's first sentence must contain one of these anchor phrases — "progress worth knowing", "what's actually being done", or "pushing in the right direction" — because podcast-app chapters key off them. Build your own sentence around the phrase each day; the anchor is a marker, not a line to recite.
+ - The progress story's first sentence must contain one of these anchor phrases — "progress worth knowing", "what's actually being done", or "pushing in the right direction" — because podcast-app chapters key off them. Build your own sentence around the phrase each day; the anchor is a marker, not a line to recite.
+ - UNDERSTANDING THE ISSUE opener (chapter anchor, not a recited template): the deep-dive's first sentence must contain one chapter-detectable token from this family so podcast-app markers fire — "to really understand", "to understand … more fully", or "here's the thing that changes" — INSIDE a fresh sentence that states the mechanism. BANNED as a stock skeleton (9–10/10 recent episodes): opening with "To really understand how [noun phrase]…" every night. Rotate ≥3 opener shapes across two weeks; never reuse last episode's opener wording. Do NOT restate the lead story's body facts already spoken — mechanism only (Sep-05 CONTENT DISCIPLINE). Never paste digest headers or "Understanding the Issue:" labels.
```

**`shows/omni_view.yaml`** (config) — If podcast openers rotate off the stock 'To really understand how…' pair, chapter detection must accept new shapes in the same change set (PT dead-marker class). Audio-adjacent → A/B-listen.
```diff
-   - pattern: to really understand|to understand .{1,80}? more fully|most coverage leaves out|here's the thing that changes
-     title: Understanding the Issue
+   - pattern: to really understand|to understand .{1,80}? more fully|most coverage leaves out|here's the thing that changes|what most accounts skip|the mechanism underneath|the part the first headlines miss
+     title: Understanding the Issue
```

**`shows/prompts/omni_view_podcast.txt`** (prompt) — Ep183 bags / Ep184 plot-stop / Ep189 buybacks show soft eligibility after disaster-as-progress cooled. Podcast layer blocks audio reframes even if digest mis-picks; negative shapes only (no quotable good example).
```diff
- - NO SIDES ON TRAGEDY OR FACT: disasters, accidents, deaths, scientific results, and culture stories get NO sides framing. Give them context and what happens next instead. Manufacturing a debate over an earthquake or an obituary is a critical failure.
+ - NO SIDES ON TRAGEDY OR FACT: disasters, accidents, deaths, scientific results, and culture stories get NO sides framing. Give them context and what happens next instead. Manufacturing a debate over an earthquake or an obituary is a critical failure.
+ - PROGRESS WATCH ELIGIBILITY (audio must not reframe a mis-pick): the progress beat is a concrete "what's being done" with named actors, ≥1 number, and one complication clause — a measure in force, an indicator moving, infrastructure/tech deployed, or real negotiated terms. INELIGIBLE even if the briefing mis-labeled them: disasters/accidents/deaths, stopped rescues, pure containment-of-tragedy, court dismissals without reform, entertainment box-office, household lifehacks, and corporate share buybacks/PR capital returns. If nothing clears the bar, cover a fourth world story in that beat and never announce the skip.
```

**`shows/prompts/omni_view_digest.txt`** (prompt) — Digest is where Ep144/Ep158/Ep183/Ep189-class mis-picks start; tighten with negative shapes only (no quotable 'good' example that becomes the next tic).
```diff
- PROGRESS WATCH (instruction — do not echo): one concrete, verifiable "what's being done" development from today's sources — a measure passed, a disease indicator falling, infrastructure or technology actually deployed, a negotiation producing real terms. Name the actors, include at least one number, and acknowledge the main complication in one clause. NEVER corporate PR, never a cute story, never a silver lining invented for a tragedy — this segment earns trust by being as rigorous as the hard news. If nothing in today's sources clears this bar, cover a fourth world story in this slot instead (do not write a sentence announcing the absence).
+ PROGRESS WATCH (instruction — do not echo): one concrete, verifiable "what's being done" development from today's sources — a measure passed, a disease indicator falling, infrastructure or technology actually deployed, a negotiation producing real terms. Name the actors, include at least one number, and acknowledge the main complication in one clause. NEVER corporate PR, never a cute story, never a silver lining invented for a tragedy — this segment earns trust by being as rigorous as the hard news. INELIGIBLE shapes (do not use these even when sources are soft-news-hungry): disasters/accidents/deaths as "progress", stopped or failed rescues, pure fire/flood containment after loss, court dismissals without structural reform, entertainment/box-office, household recycling lifehacks, and share buybacks or other capital-return PR. If nothing in today's sources clears this bar, cover a fourth world story in this slot instead (do not write a sentence announcing the absence).
```

**`shows/prompts/omni_view_podcast.txt`** (prompt) — Banned frames partially returned as 'both sides accept' + residual 'strongest case'. Extend bans by shape + verbatim caps; ledger watches next successor.
```diff
- - "Both sides agree that…" / "Both sides face comparable…" — BANNED as a verbatim frame (July 2026: it escalated from the digest into spoken audio, 5× in one episode, manufacturing "sides" on an accidental death and a sports final). State shared facts in fresh words, and never invoke "sides" on a story without a genuine, named disagreement.
+ - "Both sides agree that…" / "Both sides face comparable…" / "The factual ground both sides accept…" / "The empirical ground both sides accept…" — BANNED as verbatim frames (July 2026 Both-sides family; Sep 2026 successor "both sides accept" on Ep185/186). State shared facts in fresh words each time, name who accepts them when it matters, and never invoke "sides" on a story without a genuine, named disagreement.
+ - "The strongest case for/against…" and "The strongest argument for/against…" combined may appear AT MOST ONCE per episode (Ep182 still shipped "strongest case"). Prefer named-advocate leads without a dual scaffold on consecutive contested stories.
+ - Also still BANNED: anonymous "one side / the other side / advocates on each side" and "one position holds / a competing position maintains".
```

**`shows/prompts/omni_view_podcast.txt`** (prompt) — Sep-05 CONTENT DISCIPLINE miss: digest-verbatim median ≈54% with copied-section flags on ep182–189 under grok-4.7 script stage. Teeth on anti-paste without a podcast length lever.
```diff
- - NEVER retell or revisit a story you already covered, even from a different angle. Each news item gets ONE treatment. Once you have covered a story, it is done — move on to the next topic.
- - Do NOT repeat transition sentences. When you write a transition at the end of one story, start the next story with NEW content — do not repeat the transition line.
+ - NEVER retell or revisit a story you already covered, even from a different angle. Each news item gets ONE treatment. Once you have covered a story, it is done — move on to the next topic.
+ - Do NOT repeat transition sentences. When you write a transition at the end of one story, start the next story with NEW content — do not repeat the transition line.
+ - NO DIGEST PASTE (Sep 2026 density: several episodes shipped 60–75% digest-verbatim shingles): do not copy briefing sentences, section headers, numbered "### N)" headlines, or "Understanding the Issue:" labels into spoken lines. Retell facts in spoken cadence (short Host: lines). Understanding explains the mechanism only and must not re-speak the lead's already-told body. If a Host line is unchanged from the briefing prose, rewrite it.
```

**`shows/prompts/omni_view_digest.txt`** (prompt) — Digest still seeds the spoken 'both sides accept' / strongest-case scaffolds. Mirror podcast bans at source; remove the prompt's own 'empirical ground both sides accept' as a recommended structure (it became the tic).
```diff
- CRITICAL — NAME WHO HOLDS EACH POSITION, AND DO NOT FALL INTO A TEMPLATE: Attach every steel-manned position to the actual people, parties, institutions, or schools of thought who hold it ("Treasury officials argue…", "civil-liberties groups counter…", "free-market economists contend…") — NEVER anonymous "one side" / "the other side" / "advocates on each side", and equally NEVER the anonymous "position" variants "one position holds…" / "a competing position maintains…" / "another position holds…" (July 2026: these became the new anonymous scaffold as the older frames were banned — up to twice per episode — and they violate this same name-the-advocate rule). Every position names who actually makes the case. Equally important: VARY how you introduce the sides from story to story. Do NOT open every story's steel-man with the same stock sentence frame. The phrase "the strongest case" may appear AT MOST ONCE in the entire digest — recent digests opened nearly every story with "The strongest case for X rests on… / The strongest case for Y rests on…" until the scaffolding drowned out the ideas. Rotate the structure: sometimes lead with the empirical ground both sides accept and then the divide; sometimes lead with the single mechanism the whole disagreement turns on; sometimes lead with the named advocate's own framing of their best argument.
+ CRITICAL — NAME WHO HOLDS EACH POSITION, AND DO NOT FALL INTO A TEMPLATE: Attach every steel-manned position to the actual people, parties, institutions, or schools of thought who hold it ("Treasury officials argue…", "civil-liberties groups counter…", "free-market economists contend…") — NEVER anonymous "one side" / "the other side" / "advocates on each side", and equally NEVER the anonymous "position" variants "one position holds…" / "a competing position maintains…" / "another position holds…" (July 2026: these became the new anonymous scaffold as the older frames were banned — up to twice per episode — and they violate this same name-the-advocate rule). Every position names who actually makes the case. Equally important: VARY how you introduce the sides from story to story. Do NOT open every story's steel-man with the same stock sentence frame. The phrases "the strongest case" and "the strongest argument" combined may appear AT MOST ONCE in the entire digest. BANNED as every-story skeletons: "Both sides agree…", "The factual ground both sides accept…", "The empirical ground both sides accept…", and dual "The case for X / The case against Y" openers on consecutive contested stories. Rotate the structure: sometimes lead with undisputed facts stated in fresh words (without the both-sides-accept stock line) then the divide; sometimes lead with the single mechanism the whole disagreement turns on; sometimes lead with the named advocate's own framing of their best argument.
```

## Code/metadata-only proposals (no A/B needed)
- **`tests/test_omni_view_quality_pass.py`** (code): Every behavioral fix needs a drift-guard per playbook; pins bans and chapter-pattern broaden without weakening hard guardrails.

## Deferred (carried forward)
- Chronic under-length: operator decision only — audit last-10 digest word counts vs min_digest_words 1500 and deepen-expansion hit rate before any digest-depth config change; do NOT re-propose podcast_expand_below_target, min_podcast_words hikes, or prompt word-pressure (multiple misses; network do_not_retry class)
- Reuters/AP Google News proxy label attribution still cosmetic (July-18 carry)
- BBC Latin America feed low-volume monitor (July-18 carry)
- Network tooling: mechanical digest lint for template-saturation counts (both-sides-accept / strongest-case / shared-facts family)
- Sep-05 closing pool pin (three essay-style closings) — after flagship A/B readout
- Sep-24 source_integrity_claims median readout once metrics expose the field
- Watch fourth-generation steel-man / Understanding opener convergence next pass after proposed bans ship (successor-tic prediction recorded)
- OP3 / YouTube long-form retention as network-funnel topics (47/7d; long retention 14.7%) — not OV-only editorial blockers this pass

## Drift-guard status
```
============================= test session starts ==============================
collected 35 items

tests/test_omni_view_quality_pass.py ................................... [100%]

============================== 35 passed in 1.07s ==============================
```

<sub>tokens: 63553 in / 8630 out</sub>