July-2 brand/comma fixes held, but 6/10 episodes still speak the malformed closer “TSLA closed at down…”, every recent script remains under the 2000-word floor despite digest-side expand, and the tomorrow-teaser/CTA pools have collapsed into single tics.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.0902**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes whose spoken intro says "Tesla Shorts Time Daily" | hit | Ep550-559 snapshot phrase list has identity as "i'm patrick in vancouver"; no "Daily" / "Tesla Shorts Time Daily" recurrence in last 10. |
| comma-number hook garbles ("dollars,990"-class) in new _tts.txt | hit | No dollars,NNN / zeroth / comma-number class in last-10 snapshot phrases; formatter fix holding. |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/hooks/tesla.py`** (code) — Snapshot: 'tsla closed at down' in 6/10 shipped transcripts — listener-facing garble in the final seconds of the show. Same function also explains the 6/10 'a rating or review' CTA collapse.
```diff
- closing variants that can render as 'TSLA closed at down …' / 'TSLA closed at up …' when price-words drop out or direction is substituted into the price slot (see _pick_closing / closing_block)
+ Every publishable closer MUST emit price first, then direction: 'TSLA closed at {price_words}, {up|down} {change_words} on the day.' (or pre/after-hours 'is trading at {price_words}…'). Never 'closed at up/down'. When not is_price_publishable(price, change_str), omit the price sentence entirely and use a price-free rotated closer. Rotate ≥4 CTA tails (rating ask at most 1-in-4). Add regression assert: re.search(r'(?i)closed at (up|down)\b', closing) is None.
```

**`shows/prompts/tesla_podcast.txt`** (prompt) — 8/10 episodes open the teaser with the same 'keep an eye on' tic — dead rotation. De-seed by shape + verbatim ban per playbook (no quotable exemplar that becomes the next tic).
```diff
- (teaser guidance that permits or examples the stock phrase 'keep an eye on' / relies on an undirected 'tomorrow teaser' instruction — chapter marker in tesla.yaml also lists keep an eye on as a valid end-section cue)
+ TOMORROW TEASER (shape rules, zero tolerance for stock openers):
+ - Ban verbatim: 'keep an eye on', 'we'll be watching', 'before we go' as the teaser opener (chapter matcher may still catch paraphrases — that is fine).
+ - Open with one of these SHAPES (describe, do not quote an example sentence): (1) callback to a tracked open question from narrative memory by program name; (2) a named catalyst tied to a time window; (3) an unresolved regulatory or product fork the listener should notice.
+ - The teaser must contain at least one concrete proper noun or program name from today's digest. One or two sentences max. No CTA inside the teaser.
```

## Code/metadata-only proposals (no A/B needed)
- **`tests/test_tesla_quality_pass.py`** (code): Drift-guard pattern from prior Tesla quality passes; locks P0 closer fix and CTA rotation without touching audio settings.

## Deferred (carried forward)
- Operator length decision (ESCALATE — third miss): (a) full-text fetch for primary Tesla feeds, (b) accept grok-4.3 plateau and lower min_podcast_words + RSS '15 focused minutes' to match ~11-12 min reality, or (c) hard First Principles word floor on the digest. Do not re-enable podcast_expand_below_target.
- Digest-driven chapter titles + engine/chapters.py long-Introduction auto-split when editorial markers alone hit min_chapters (network-scoped; June-10/20/July-2 carry).
- Narrative-tracker curated status lag — scripts/update_tesla_narrative.py operator curation.
- July-2 A/B not applied: recap hardening (one story once; no Title-Case headline readbacks / patent-hex minutiae); dateline-filler ban; counterpoint enforcement; SpaceX/xAI corporate never as Tesla hook/lead.
- June-23 double-publish forensics (operator).
- RSS listing minute-count copy — only after operator length decision so store text is not edited twice.

## Drift-guard status
```
============================= test session starts ==============================
collected 47 items

tests/test_tesla_quality_pass.py ....................................... [ 82%]
........                                                                 [100%]

============================== 47 passed in 1.04s ==============================
```

<sub>tokens: 32407 in / 4236 out</sub>