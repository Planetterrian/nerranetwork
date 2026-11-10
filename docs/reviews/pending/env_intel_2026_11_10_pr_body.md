Post-Sep-21 window still ships absence-of-section lines, Nerra→Narin garble, malformed/non-Closing chapters (ep74 ends on Deep Dive), and chronic under-length (7/10 <900); host-experience filter partially landed but first-person deep-dive claims and invented careers still leak in ep72–75.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1533**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| transcripts containing spoken absence-of-section lines ('No qualifying… appeared today' / 'No major… appeared' / 'No new peer-reviewed…'), last 10 | miss | ep73 and ep75 EN transcripts still speak 'No qualifying industry announcements… appeared in today's sources' (ep75 also deadline absence) despite absence_sentence_filter: true |
| deep-dive openers using 'Consider a…' OR 'Picture a…' OR 'A client…' (or close paraphrase), last 10 transcripts | partial | exact Consider-a/Picture-a/A-client phrases cleared in ep72–76, but replaced by bare scene + 'The mistake I see most often' / 'The common mistake is' career-claim frame |
| successor deep-dive opener tic prediction (fifth-generation watch) | hit | ep72–75 converged on mistake-I-see / common-mistake / experienced-assessor shapes; watch fired on the career-claim class |
| chapters_ep*.json titles outside the known section-title set, last 10 | miss | ep67 sentence fragment; ep68 dual story headlines; ep72 cold-open truncation; ep73 COP17 headline; ep74 Compliance Brief parenthetical + story headlines; ep76 Practice Spotlight digest heading |
| episodes whose LAST chapter is Closing, last 10 | miss | ep74 chapters end on Practitioner Deep Dive with no Closing title; 9/10 — regression from prior 10/10 |
| Whisper garble of Kincardine / Ksi Lisims / Nerra / CEPA-as-see-EPA / Terrace / Kamloops in post-merge transcripts | partial | Nerra→Narin/Narrow/Naren in every ep72–76 closing promo; EPEA spoken as EPA on ep75; Kincardine/Ksi Lisims/Terrace/Kamloops not present in this window |
| episodes below min_podcast_words:900 among ep62+ (carry; lever-gated) | miss | scored n/a against unshipped levers per Sep-21 rule, but raw window is 7/10 under 900 (ep74=788, ep76=642); operator escalation still open — recorded miss on the measurable floor, not on a podcast-side proposal |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/env_intel_podcast.txt`** (prompt) — Locks three verified P0/P1 classes still shipping: (1) absence-of-section lines in ep73/75 despite YAML filter; (2) first-person career-claim deep dive in ep72–75 after Nov-3 filter; (3) opener convergence. De-seed by shape + verbatim ban + MEMORY per July 2026 ledger rule; no quotable replacement (do_not_retry). A/B-listen required (landmine #17).
```diff
- (deep-dive / empty-section region — reinforce existing NEVER INCLUDE and deep-dive guidance)
+ DEEP DIVE — DOCUMENT VOICE ONLY (no career claims):
+ - Build the Practitioner Deep Dive from one regulation or guidance document whose full text was in the briefing, with section numbers traced to that source. If no such document was fetched, OMIT the deep dive entirely — do not invent a practice scene.
+ - NEVER speak first-person professional-experience claims. Verbatim bans (any tense/person): "the mistake I see most often", "the common mistake I see", "in my experience", "experienced assessors", "when I was on site", "a client calls", "you arrive at a". Describe the document's rule and the failure mode it implies, not a career the host does not have.
+ - De-seed by SHAPE, not example: do not open on a scene-with-client, a monitoring-well vignette, or a "picture/consider a…" frame. Open on the instrument ("CCME guidance on X states…" / "Alberta directive N section…") or skip the section.
+ - Rotation MEMORY: do not reuse the opener shape of the last 3 episodes.
+ 
+ EMPTY SECTIONS — OMIT, NEVER NARRATE:
+ - If Science & Technical, Industry & Practice, or Week Ahead has no qualifying item, skip it silently. NEVER speak "No qualifying… appeared today/in today's sources", "No specific upcoming deadlines…", "No major… appeared", or any paraphrase that announces an empty section or describes the show's filters/selection criteria.
```

**`shows/prompts/env_intel_digest.txt`** (prompt) — Podcast faithfully echoes digest deep-dive openers and empty-section placeholders (June-15 through Sep-21 lineage). Digest is the seed surface; de-seed + empty-section omit here or the podcast ban alone loses. Aligns with Nov-3 sourced-deep-dive lint already in YAML. No quotable replacement example. A/B-listen required.
```diff
- (Practitioner Deep Dive + LOW-CONTENT empty-section region)
+ PRACTITIONER DEEP DIVE — sourced document only:
+ - Build from ONE regulation, guidance, directive, or protocol whose full text is in the prompt (CCME / AER / provincial protocol / Gazette instrument). Cite section/schedule/threshold from that text. If none was fetched, leave the section out (no heading, no placeholder).
+ - NEVER write first-person experience: no "the mistake I see most often", "in my practice", "experienced assessors", client-call or site-arrival scenes. The authority is the document.
+ - De-seed by shape + recent-MEMORY of the last 3 deep-dive openers (no quotable replacement menu item).
+ 
+ EMPTY SECTIONS: a section with no qualifying item is LEFT OUT — heading and all. Never write "No qualifying… appeared", "nothing met the criteria", or describe selection filters. On thin days one story anchors at most TWO sections; diversify with forward calendar or the sourced deep dive.
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/hooks/env_intel.py`** (code): Highest-yield category (~100% hit historically, deterministic, no A/B). Nerra→Narin/Narrow ships in every ep72–76 closing; Kincardine/Ksi Lisims/Terrace/Kamloops/Simpcw/Tyee still unprotected because Aug-10/Sep-21 hook extensions never applied. Extend existing hook channel only — never phonetic injection (landmine #17).
- **`shows/env_intel.yaml`** (config): Metadata-only. ep68 story-headline chapters and ep74 digest-heading leaks come from body-prose keyword hits when the script never announces the section. Tighten Science/Industry to announce shapes; keep digest_section fallback. Closing-first order and Deep Dive digest_section anchor untouched. Also ensure Compliance Brief / Practice Spotlight digest H2s are not used raw as chapter titles (sanitize parentheticals in the chapter builder or pin explicit markers).
- **`engine/host_experience.py`** (code): Nov-3 filter is on but ep72–75 still speak the career-claim beat — pattern set misses the variants the podcast stage actually emits. Code-only; deterministic; matches the existing host_experience_removed metrics. Re-run committed replay before any further widen (CLAUDE.md rule).
- **`engine/absence_sentences.py`** (code): YAML flag is true but lines still reach Whisper — filter is digest-only or paraphrase-blind. Garble/filter class historically ~100% hit, no A/B. A lint is true of the text that ships (Oct 2026 rule).
- **`tests/test_env_intel_quality_pass.py`** (code): Every behavioral fix gets a drift-guard per playbook. Pins length-lever policy so a future pass cannot reintroduce podcast_expand_below_target. Guards that read today's data must tolerate today (judge episodes ≥1 day old).

## Deferred (carried forward)
- ESCALATE to operator decision (Sep-21 + this pass; two post-lever misses): raise min_digest_words above 950 and/or licensed-knowledge section floors for Regulatory Calendar + Practice Spotlight on thin Mondays — do NOT re-file podcast-side length levers
- Digest-driven / position-aware mid-section chapter titles (shared engine; carried since 2026-06-10) — local marker tighten this pass is a patch only; ep74 missing Closing and ep67/68/72/74/76 malformed titles are symptoms
- Numbers/dates spell-out drift (PM 2.5 comma pause; phase one slash two; digit dates) — landmine #17; A/B before any repair layer; never phonetic injection
- French-language / QC-SK-Atlantic source coverage gap vs Phase-4 web_search_queries promise (operator/editorial)
- OP3 download flatline/decline (7d=12, WoW −56%, first-week median=7) + YouTube paused — distribution/discoverability operator review (Apple/Spotify/@nerranetwork clip since Oct-24), not a prompt change
- Thin-news blog <title> intelligence re-score — HOOK-level absence banned since June-11; residual is section-level absence lines (P0 this pass)
- Digest-verbatim paste rate 67–72% on fat days with copied section headers — monitor; reinforce content_discipline only if elevated post de-seed; no length pressure; density threshold is not a prediction

## Drift-guard status
```
============================= test session starts ==============================
collected 23 items

tests/test_env_intel_quality_pass.py .......................             [100%]

============================== 23 passed in 0.40s ==============================
```

<sub>tokens: 53373 in / 7755 out</sub>