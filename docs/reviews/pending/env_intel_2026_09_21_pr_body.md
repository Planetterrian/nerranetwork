Post-Aug-10 proposals never shipped: length lever partially held then relapsed (6/10 under 900; 4/8 post-lever under), deep-dive openers rotated past Consider-a into Picture-a/A-client while absence-of-section lines still ship, and chapters degraded with truncated titles plus missing Deep Dive on thin days.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1430**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| deep-dive openers using 'There's a nuance here worth understanding' OR 'Consider a…' (or close paraphrase), last 10 transcripts | partial | nuance 0/10; Consider-a 4/10 (ep60/62/63/64); de-seed never shipped; Picture-a (ep67) + A-client/scene-open (ep65/66/68/69) already succeeding it |
| episodes below min_podcast_words:900 among episodes generated after digest lever (ep62+) | miss | 4/8 post-lever under 900 (ep66=783, ep67=867, ep68=850, ep69=896); escalate per Aug-10 deferral — no podcast-side re-file |
| transcripts containing spoken absence-of-section lines ('No qualifying… appeared today' / 'No major… appeared') or spoken bare URLs | miss | ep65/66/67 still speak the 'No qualifying peer reviewed… appeared today' failure mode; no bare URL in ep60-69 |
| transcripts reading hyphen/underscore as words ('contaminated underscore/dash/hyphen sites') | hit | 0 instances in ep60-69 Whisper transcripts |
| successor deep-dive opener tic prediction (third-generation watch) | hit | ep67 'Picture a client filing…'; ep65/68/69 A-client/scene-open — watch fired as predicted |
| episodes whose LAST chapter is Closing (chapters_ep*.json) | hit | 10/10 of ep60-69 end with title Closing |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/env_intel_podcast.txt`** (prompt) — Locks three verified P0/P1 classes still shipping: (1) absence-of-section lines in ep65/66/67; (2) 4th/5th-gen deep-dive opener convergence (Consider-a 4/10, Picture-a already live); (3) durable cadence already drifted to 'next briefing' — keep it banned from reverting to Tomorrow. De-seed by shape + verbatim ban + MEMORY per July 2026 ledger rule; no quotable replacement.
```diff
- NEVER INCLUDE (these will be read aloud by TTS and sound terrible):
- - URLs or links of any kind (e.g. https://..., Source: ..., [link])
- - Exact timestamps or datelines (e.g. "22 February, 2026, 11:30 AM PST")
- - Source attribution lines (e.g. "Source: EPA" on its own line)
- - Production notes, editor comments, or metadata (e.g. "[Note: ...]", "Word count:")
- - Emoji characters or unicode symbols
- - Markdown formatting (** bold **, ### headers, bullet markers)
- - Pet names for the audience (e.g. "buddy", "pal", "bro", "friend", "folks", "gang") — use "you" or "listeners"
- Instead: cite sources naturally ("the Alberta government announced", "according to Nature Climate Change", "Ottawa's latest gazette notice"), use natural dates ("today", "yesterday", "earlier this week").
+ NEVER INCLUDE (these will be read aloud by TTS and sound terrible):
+ - URLs or links of any kind (e.g. https://..., Source: ..., [link])
+ - Exact timestamps or datelines (e.g. "22 February, 2026, 11:30 AM PST")
+ - Source attribution lines (e.g. "Source: EPA" on its own line)
+ - Production notes, editor comments, or metadata (e.g. "[Note: ...]", "Word count:")
+ - Emoji characters or unicode symbols
+ - Markdown formatting (** bold **, ### headers, bullet markers)
+ - Pet names for the audience (e.g. "buddy", "pal", "bro", "friend", "folks", "gang") — use "you" or "listeners"
+ - Absence-of-content / empty-section narration — NEVER speak lines like "No qualifying peer reviewed or technical reports appeared today", "No major industry developments appeared today", "No new peer-reviewed studies with direct Canadian regulatory impact appeared today", or any paraphrase that announces a section is empty. If a section has no qualifying item, OMIT the section entirely and move on. Announcing nothing is anti-briefing.
+ - Spoken bare domain names or paths (e.g. "news.gov.bc.ca", "nerranetwork.com slash …") — cite the outlet by name only
+ Instead: cite sources naturally ("the Alberta government announced", "according to Nature Climate Change", "Ottawa's latest gazette notice"), use natural dates ("today", "yesterday", "earlier this week").
+ 
+ DEEP-DIVE OPENER — DE-SEED BY SHAPE (do not replace with a new example phrase):
+ The Practitioner Deep Dive must land the signature mistake+fix beat, but its OPENING frame must rotate and must NOT reuse any of these exhausted templates (verbatim or close paraphrase) — they became every-episode tics across 2026-06→09:
+ - "There's a nuance here worth understanding…"
+ - "Consider a [role/scenario]…" / "Consider an upstream…" / "Consider a phase two…"
+ - "Picture a [client/scene]…"
+ - "A client calls…" / "A client submits…" / "A client with an active…"
+ - "You arrive at a…"
+ Ban those shapes. Open from a concrete artifact the briefing already supports (a lab result, a permit condition, a field note, a clause in a submission) without a stock scene-framing preamble. Do NOT invent a new quotable menu item as the replacement — any example phrase written here will be elected as the next tic. If recent MEMORY lists prior openers, treat that list as do-not-reuse.
```

**`shows/prompts/env_intel_digest.txt`** (prompt) — Podcast faithfully echoes digest deep-dive openers and empty-section placeholders (June-15/July-2/July-27/Aug-10 lineage). Digest is the seed surface; de-seed + empty-section omit here or the podcast ban alone loses. No quotable replacement example.
```diff
- This ensures every episode delivers actionable intelligence even on quiet news days. NEVER produce an empty or thin briefing. On these days the HOOK must still lead with a concrete forward-looking item (nearest deadline, consultation close, effective date, or the deep-dive topic) — never a sentence announcing that nothing happened. AND: one story may anchor AT MOST TWO sections of the briefing. On thin days recent episodes told the SAME story in the hook, the Compliance Brief, the lead story, and the action item (one certificate story appeared six times in a single episode) — a listener hears that as a single item stretched to fill the show. When content is thin, diversify with the forward calendar, a second jurisdiction, or the deep-dive topic instead of re-telling the one story.
+ This ensures every episode delivers actionable intelligence even on quiet news days. NEVER produce an empty or thin briefing. On these days the HOOK must still lead with a concrete forward-looking item (nearest deadline, consultation close, effective date, or the deep-dive topic) — never a sentence announcing that nothing happened. AND: one story may anchor AT MOST TWO sections of the briefing. On thin days recent episodes told the SAME story in the hook, the Compliance Brief, the lead story, and the action item (one certificate story appeared six times in a single episode) — a listener hears that as a single item stretched to fill the show. When content is thin, diversify with the forward calendar, a second jurisdiction, or the deep-dive topic instead of re-telling the one story.
+ 
+ EMPTY SECTIONS ARE OMITTED, NEVER NARRATED: If Science & Technical, Industry & Practice, or any other body section has no qualifying item, delete the section heading entirely. Do NOT write "No qualifying peer reviewed or government technical reports appeared today", "No qualifying industry developments appeared today", or any absence placeholder. The podcast stage has been reading those placeholders aloud (ep57/65/66/67). Silence is correct; announcing a hole is not.
+ 
+ PRACTITIONER DEEP DIVE — OPENER DE-SEED BY SHAPE: The deep dive remains mandatory even on thin days (it is the B2B differentiator). Write it from a concrete artifact (lab result, permit clause, field note, submission gap). Do NOT open with any of these exhausted frames (verbatim or close paraphrase) — each became an every-episode tic when used as a menu example: "You arrive at a…", "There's a nuance here worth understanding…", "Consider a [role/scenario]…", "Picture a…", "A client calls/submits…". Ban those shapes. Do NOT replace them with a new quotable example phrase in this prompt — any example written here will be elected as the next tic. Rotate entry points by shape (artifact-first, clause-first, numbers-first) and treat recent deep-dive openers as a do-not-reuse MEMORY list. Keep the signature "most common mistake → fix" beat so the chapter marker still fires.
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/hooks/env_intel.py`** (code): Highest-yield category (~100% hit, deterministic, no A/B). Current window still ships Kincardine/Ksi Lisims/Nerra/CEPA garble because Aug-10 hook extension never applied; extend the existing hook channel only.
- **`shows/env_intel.yaml`** (config): Metadata-only. ep67 truncated sentence-title and ep68 story-headline chapters come from body-prose keyword hits; tighten Science/Industry to section-announce shapes and extend Deep Dive beat aliases so thin-day mistake+fix still titles correctly. Closing-first order untouched.
- **`tests/test_env_intel_quality_pass.py`** (code): Every behavioral fix gets a drift-guard per playbook; pins the length-lever policy so a future pass cannot reintroduce podcast_expand_below_target, and locks absence-ban / shape-deseed / hook garble set / chapter title set.

## Deferred (carried forward)
- ESCALATE to operator decision (two post-lever misses): raise min_digest_words above 950 and/or full-text article fetch for Gazette/provincial releases and/or licensed-knowledge floors for Regulatory Calendar + Practice Spotlight on thin days — do NOT re-file podcast-side length levers
- Digest-driven / position-aware mid-section chapter titles (shared engine; carried since 2026-06-10) — ep67 truncated sentence-title and ep68 story-headline chapters are the latest symptom; marker tighten this pass is a local patch only
- Numbers/dates spell-out drift (PM, 2.5 comma pause; phase one slash two; digit dates) — landmine #17; needs A/B before any repair layer; never phonetic injection
- French-language / QC-SK-Atlantic source coverage gap vs Phase-4 web_search_queries promise (operator/editorial)
- OP3 download flatline (7d=7, 30d=27, first-week median=3) + YouTube already paused — distribution/discoverability operator review, not a prompt change
- Thin-news blog <title> intelligence re-score — HOOK-level absence banned since June-11; residual is section-level absence lines (P0 this pass)
- Digest-verbatim paste rate 66-67% on ep62/64/68/69 with copied section headers — monitor; reinforce content_discipline only if it stays elevated post de-seed, no length pressure

## Drift-guard status
```
============================= test session starts ==============================
collected 23 items

tests/test_env_intel_quality_pass.py .......................             [100%]

============================== 23 passed in 0.53s ==============================
```

<sub>tokens: 43451 in / 9348 out</sub>