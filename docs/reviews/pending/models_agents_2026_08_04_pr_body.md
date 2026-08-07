Prior length and teaser-tic predictions missed again because Aug-2 levers never shipped (7/10 scripts still under 1500w; “keep an eye on” still 6/10); chapters remain brittle (ep127 first marker at 4min, ep128 lost Under the Hood); new UTH body tic “Everyone talks about…” is 8/10 — escalate length to an operator decision and re-propose only the never-applied teaser/UTH de-seeds plus a no-A/B chapter-marker catch.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1256**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes below min_podcast_words (1500) in last 10 | miss | 7/10 ep122–131 still under 1500 (worst ep127=1099, ep124=1135); min_digest_words still 1300 — Aug-2 1600 lever never applied |
| "keep an eye on" / "Tomorrow keep an eye on" / "Before we go, keep an eye on" as teaser opener, last 10 | miss | 6/10 still (ep122–127 verbatim); ep128–131 drifted to Before-we-go without the phrase; Aug-2 shape de-seed never applied |
| successor teaser-opener tic: any single new opener phrase in >=6/10 teasers (convergence watch) | hit | "Before we go" at 5/10 (ep126,128–131) — under the 6/10 threshold; watch next pass |
| spoken episode-number continuity callbacks ("episode N" / "EpN") in last 10 Whisper/_tts.txt | hit | 0 episode-number callbacks in ep122–131; framing is yesterday/prior-episode/tracked-arc instead |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/models_agents_podcast.txt`** (prompt) — "keep an eye on" still opens 6/10 teasers (ep122–127); July-19 and Aug-2 shape de-seeds never applied. Meta-rule: de-seed by shape + verbatim ban, no quotable replacement menu; successor "Before we go" already at 5/10 is on the watch list.
```diff
- [Tomorrow Teaser / before-we-wrap close — current prompt allows free-form teaser openers; live episodes converge on "Tomorrow, keep an eye on …" / "Before we go, keep an eye on …"]
+ TOMORROW TEASER / BEFORE-WE-WRAP OPENER (shape ban — do not read this label aloud):
+ - Do NOT open the teaser with "keep an eye on", "Tomorrow keep an eye on", "Before we go, keep an eye on", or any close paraphrase that uses keep-an-eye-on as the first verb phrase.
+ - Ban is on the SHAPE (imperative watch-phrase as the teaser's first clause), not on mentioning a concrete upcoming release.
+ - Write a fresh one-sentence teaser that names the specific thing to watch (a model, lab, benchmark, or date) without a stock opener.
+ - Do NOT substitute a quotable menu of replacement openers — vary naturally from the day's content.
+ - NEVER reuse a teaser sentence that already appeared in On the Horizon earlier in the same script.
```

**`shows/prompts/models_agents_podcast.txt`** (prompt) — New third-generation tic: "Everyone talks about…" is the UTH body opener in 8/10 recent episodes and is also why ep127/128 lost the pop-the-hood chapter signal. Shape-ban with no replacement menu; keep signature pop-the-hood alone.
```diff
- [Under the Hood deep-dive body — live episodes open with "Okay, let's pop the hood on X. Everyone talks about Y…" in 8/10 of ep124–131; ep127/128 skip pop-the-hood and lead with Everyone-talks-about alone]
+ UNDER THE HOOD BODY OPENER (shape ban — do not read this label aloud):
+ - After the deep-dive topic is named, do NOT open the explanation with "Everyone talks about…", "Most people think…", "The common story is…", or any contrast-cliché that pits a vague public perception against the real engineering in the first sentence.
+ - Ban is on the SHAPE (stock perception-vs-reality throat-clear), not on discussing real tradeoffs.
+ - Start from the concrete mechanism, number, or failure mode. Vary the entry; do not install a replacement catchphrase.
+ - Signature "okay, let's pop the hood on [topic]" remains allowed as the section signal — only the Everyone-talks-about body formula is banned.
```

**`shows/prompts/models_agents_podcast.txt`** (prompt) — ep122–131 already hit 0 episode-number callbacks, but the Aug-2 podcast-side ban never landed. Belt-and-suspenders so the ep120 regression cannot return; matches digest continuity budget.
```diff
- [Continuity — digest already says prefer date/yesterday and never EpN; podcast side has no hard spoken-episode-number ban. ep120 had spoken "episode 119"; ep122–131 are clean but unprotected.]
+ CONTINUITY CALLBACKS (hard rules — do not read this label aloud):
+ - At most ONE continuity callback per episode.
+ - NEVER speak episode numbers ("episode 119", "Ep 119", "back in episode eighty-six", "since episode N").
+ - Prefer calendar anchors ("yesterday", "earlier this week", "last Thursday") or the named prior development — never the episode index.
+ - If no clean non-number anchor exists, skip the callback entirely.
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/models_agents.yaml`** (config): ep128 deep-dive opened "Everyone talks about MCP…" with no pop-the-hood → zero UTH chapter. ep127 same shape. Adding the live formula phrase to section_markers restores the chapter without changing audio. Does not replace deferred digest-driven titles.
- **`tests/test_models_agents_quality_pass.py`** (code): Drift-guard the two prompt bans, the UTH marker alternate, and the no-podcast-expand / digest-floor floor so a later edit cannot silently drop them (pattern from existing quality-pass tests).

## Deferred (carried forward)
- OPERATOR DECISION (escalated after two missed length predictions — July-19 digest-min raise miss + Aug-2 min_digest_words=1600 miss; do not re-file 1600 a third time without an explicit choice): (A) raise min_digest_words to 1600, (B) Under-the-Hood licensed-knowledge sentence/fact floor in digest prompt, or (C) accept ~1200–1400w natural length and lower min_podcast_words. Never re-enable podcast_expand_below_target.
- Digest-driven / position-aware mid-section chapter titles (carried; ep125/130 ellipsis auto-titles, ep127 first chapter at 240s, ep128 lost UTH before marker patch — markers remain brittle)
- Under the Hood licensed-knowledge sentence/fact floor in digest prompt — operator option B
- Accept ~1200–1400w natural length and lower min_podcast_words — operator option C
- Signature opener "okay let's pop the hood on" (8/10) — intentional chapter signal; revisit only with A/B evidence
- Network-wide: blog/RSS transcript sourced from pre-pronunciation text or Whisper (LoRA/RAG/JAXA class leaks) — collision-unsafe for lone-token restore
- July-2 selection rebalance A/B (lab product/feature announcements outrank preprints; arXiv items <= 40%) — still not applied
- Recap must synthesize, not splice dailies' sentences (Sunday weekly_summary_segment) — carried
- OP3 7d 105 vs prior ~170 plateau — recovering from Aug-2 88 trough; watch one more cycle before product changes

## Drift-guard status
```
============================= test session starts ==============================
collected 7 items

tests/test_models_agents_quality_pass.py .......                         [100%]

============================== 7 passed in 0.13s ===============================
```

<sub>tokens: 45395 in / 5797 out</sub>