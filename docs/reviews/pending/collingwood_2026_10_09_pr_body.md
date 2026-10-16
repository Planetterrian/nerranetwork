After three episodes, Collingwood Weekly is on-cadence Fridays with clean region/weather sourcing, but runtime and Both Sides launch predictions have already missed, Ep2 shipped heavy same-fact restatement, Ep3 looks evergreen-free despite slow_news, and every transcript hears the town name as “calling wood.”

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.0728**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| skip rate on insufficient_articles over the first 4 scheduled Fridays | partial | 0 insufficient_articles skips across Ep2–Ep3 (2 of 4 scheduled Fridays); window still open |
| episodes (first 4) with an item outside the south Georgian Bay and no stated local consequence | partial | Ep1–3 rundowns stay bay/Simcoe/Grey-shaped in transcripts; 0 clear no-consequence off-region leads; window open |
| Roads & Weather Ahead sentences not supported by the Ontario 511 / Environment Canada hook articles | partial | Ep1–3 weather/roads passages match EC forecast + 511 closure shape; full first-4 window not closed |
| episode run time | miss | Chapter endTimes 267.6s / 441.6s / 214.1s — 0/3 ≥8:00; cannot reach 3/4 |
| episodes carrying a labelled Both Sides | miss | Both Sides chapter only in chapters_ep002.json (1/3); Ep4 cannot reach ≥3/4 |
| episodes published on a Friday (or a dated exception) | partial | Ep2 2026-10-02 and Ep3 2026-10-09 are Fridays (2/2 since schedule); 2 remain for 4/4 |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/collingwood_podcast.txt`** (prompt) — Ep2 Whisper shows multi-pass restatement of fire, impaired crashes, and Beachwood facts; Oct 3 only lowered the word target. Shape ban (no example phrase) attacks the pad-by-repeat path without a podcast length lever.
```diff
- COVERAGE: every item in the briefing is told, each with all of its facts — the briefing is the floor, not a menu. The week's news is not a list of headlines.
+ COVERAGE: every item in the briefing is told, each with all of its facts — the briefing is the floor, not a menu. The week's news is not a list of headlines.
+ 
+ ONE TELLING PER EVENT: if two outlets cover the same crash, fire, vote or charge sheet, speak it once. Fold net-new facts from the second outlet into that telling. Never restart the same event from a second outlet's wording, and never add a meta sentence about how the people are described.
```

**`shows/prompts/collingwood_digest.txt`** (prompt) — Stops multi-outlet local incidents from arriving as separate digest items that the script stage then double-walks (Ep2 pattern).
```diff
- ZERO STORY OVERLAP: each story appears in exactly ONE section. Several articles about one decision or event become ONE item with the best facts from all of them.
+ ZERO STORY OVERLAP: each story appears in exactly ONE section. Several articles about one decision or event become ONE item with the best facts from all of them. Two local outlets on the same incident are still ONE item — merge facts and keep a single Source line (primary URL); do not emit parallel items that the podcast will read as two tellings.
```

## Code/metadata-only proposals (no A/B needed)
- **`tests/test_collingwood_quality_pass.py`** (code): Every behavioral fix needs a drift-guard; wiring guards must use real load_config (frame-memory lesson). Restatement guard pins the Ep2 failure mode without asserting on today's unfinished Friday run.
- **`shows/collingwood.yaml`** (config): Show is Friday weekly local, not daily; category2 already Places & Travel. Metadata-only, no audio.
- **`digests/collingwood/ (audit Ep003 digest + slow_news path)`** (code): Length meta-rule: digest-substrate only. Ep3 under-floor with no spoken evergreen is the highest-yield length lever if wiring is dark.

## Deferred (carried forward)
- Local music theme (voice-only at launch; plan §5c) — carry
- Re-grade feed list from a runner (check_feeds.py collingwood) — carry
- Enable x_fetch only after verified local handles + first-run per-handle counts — carry
- Phonetic respelling or SSML for Collingwood/Wasaga/Simcoe — landmine #17; do not retry
- Operator decision: keep honest short thin-week runtime vs bulk the evergreen library / max_segments — escalate after runtime prediction miss; no third podcast-side length filing
- Operator decision: Both Sides hard weekly lint-floor vs explicit omit-OK and retire ≥3/4 KPI — escalate after Both Sides prediction miss
- YouTube enable for Collingwood Weekly
- Confirm snapshot '0 km/h gusting to 0' against raw _tts.txt before any local_conditions change

<sub>tokens: 23915 in / 4156 out</sub>