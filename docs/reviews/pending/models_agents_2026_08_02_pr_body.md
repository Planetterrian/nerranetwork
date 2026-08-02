Prior length and teaser-tic predictions both missed (8/10 scripts still under 1500w; “keep an eye on” still ~8/10); chapters are not actually clean (sparse/auto-titles, ep127 first marker at 4min, ep128 missing Under the Hood when the host skipped “pop the hood”), and continuity still speaks episode numbers—propose digest floor raise, shape-ban teaser de-seed, and episode-number ban only.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1151**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes below min_podcast_words (1500) in last 10 | miss | 8/10 ep120–129 still under 1500w (only ep126=1592, ep129=1501); min_digest_words=1300 + digest_expand already live |
| "keep an eye on" occurrences as Tomorrow Teaser opener, last 10 | miss | Still ~8/10 teasers (ep120–127); July-19 shape de-seed never applied (shipped:[]) |
| verbatim-doubled sentence pairs in shipped _tts.txt scripts | hit | No paraphrase-doubled sentence pairs in ep120–129 transcripts after expansion-strip |
| custom voice still reads CUDA cleanly (Whisper of post-merge CUDA episode) | hit | No koo-dah/letter-split in ep120–129; prior July-19 hit stands |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/models_agents_podcast.txt`** (prompt) — De-seed the 8/10 teaser tic by shape + verbatim ban with no quotable replacement (meta-rule). Same edit hard-bans spoken episode-number callbacks seen in ep120. A/B-listen required.
```diff
- AVOID EDITORIAL PADDING (this is the #1 reason episodes feel like commentary rather than AI news):
- The following sentence patterns are how a script drifts from reporting into editorializing. Use them sparingly — AT MOST ONCE per item:
- - "The practical shift is that..." / "What this means for developers is..."
- - "Developers who already use [X] may find..."
- - "Builders can apply this today to..." (when not naming a specific concrete capability)
- - "This fits into a bigger trend of..."
- - "This development sits within the ongoing..." (June 2026: this exact connector appeared in episode after episode, always attached to "maturation of autonomous agents" — it masks thin analysis. Name the SPECIFIC prior development it builds on, or cut the sentence.)
- - "The competition shifts attention toward..."
- - "This changes how teams approach..."
- - "It is worth noting that..." (when followed by a paraphrase, not a new fact)
+ AVOID EDITORIAL PADDING (this is the #1 reason episodes feel like commentary rather than AI news):
+ The following sentence patterns are how a script drifts from reporting into editorializing. Use them sparingly — AT MOST ONCE per item:
+ - "The practical shift is that..." / "What this means for developers is..."
+ - "Developers who already use [X] may find..."
+ - "Builders can apply this today to..." (when not naming a specific concrete capability)
+ - "This fits into a bigger trend of..."
+ - "This development sits within the ongoing..." (June 2026: this exact connector appeared in episode after episode, always attached to "maturation of autonomous agents" — it masks thin analysis. Name the SPECIFIC prior development it builds on, or cut the sentence.)
+ - "The competition shifts attention toward..."
+ - "This changes how teams approach..."
+ - "It is worth noting that..." (when followed by a paraphrase, not a new fact)
+ 
+ CONTINUITY CALLBACKS (hard cap):
+ - At most ONE spoken continuity callback per episode.
+ - Never speak episode numbers or IDs (ban shapes: "episode 119", "episode one nineteen", "Ep086", "since episode N").
+ - Prefer "yesterday", "earlier this week", or the specific prior development/lab name only.
+ 
+ TOMORROW-TEASER OPENER — SHAPE BAN (not a rotation menu):
+ - Do NOT open the teaser with the frozen template family that shipped in 8+/10 recent episodes.
+ - Verbatim ban (never write these strings): "keep an eye on", "Keep an eye on", "Tomorrow keep an eye on", "Tomorrow, keep an eye on", "Before we go, keep an eye on", "Before we go keep an eye on".
+ - Required shape: lead with the concrete lab, model, paper, or artifact, then the watch-action (availability, benchmark, or follow-up). Do not substitute a single new stock opener every night — vary the lead entity.
+ - If narrative memory lists recent teaser phrasings, do not reuse them.
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/models_agents.yaml`** (config): July-19 length prediction missed with 1300+expand still yielding 8/10 podcast scripts under 1500. Meta-review allows digest-substrate levers only; this is the next step before an Under-the-Hood floor or accepting a lower podcast floor. Do not touch podcast_expand_below_target.
- **`tests/test_models_agents_quality_pass.py`** (code): Drift-guard the config floor and the two prompt bans so a later edit cannot silently drop them (pattern from test_models_agents_quality_pass.py / network quality passes).

## Deferred (carried forward)
- Digest-driven / position-aware mid-section chapter titles (carried; ep120/121 ellipsis auto-titles, ep127 first chapter at 240s, ep128 lost Under the Hood when host skipped pop-the-hood — markers remain brittle)
- Under the Hood licensed-knowledge sentence/fact floor in digest prompt — operator option B if min_digest_words=1600 still leaves >=7/10 podcast scripts under 1500
- Accept ~1200–1400w natural length and lower min_podcast_words (operator option C) so health dashboards stop false-alarming
- Signature opener "okay let's pop the hood on" (8/10) — intentional chapter signal; revisit only with A/B evidence
- Network-wide: blog/RSS transcript sourced from pre-pronunciation text or Whisper (LoRA/RAG/JAXA class leaks) — collision-unsafe for lone-token restore
- July-2 selection rebalance A/B (lab product/feature announcements outrank preprints; arXiv items <= 40%) — still not applied
- Recap must synthesize, not splice dailies' sentences (Sunday weekly_summary_segment) — carried
- OP3 7d drop 173→88 — watch one more cycle before product changes; no metadata root cause found this pass

## Drift-guard status
```
============================= test session starts ==============================
collected 7 items

tests/test_models_agents_quality_pass.py .......                         [100%]

============================== 7 passed in 0.13s ===============================
```

<sub>tokens: 44407 in / 4386 out</sub>