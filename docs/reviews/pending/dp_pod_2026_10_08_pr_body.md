Lever-segment omission and Sep-4 shape fixes are holding on ep69–78, but podcast chapters are shipping speaker-label/dialogue-fragment titles, the Cold Open marker never matches the spoken intro, cadence copy still says daily after the weekly move, and the empty Dispatch wall remains an escalated operator decision.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1478**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| levers opening with the word Open, next 10 episodes | hit | 1/10 in ep69–78 (ep70 ClinicalTrials only) vs ≤3/10 target and 13/26 baseline |
| screen-lookup levers (open/website/app/portal/search/.gov regex on the first sentence), next 10 episodes | hit | ≤3/10 screen-ish (ep70 ClinicalTrials, ep71 TOU form); rest are calls, workdays, inspections, labs |
| fuzzy-distinct levers (content-word Jaccard < 0.4), next 10 episodes | hit | 10/10 distinct actions ep69–78, 0 near-dup pairs |
| scripts containing the word 'checklist', next 10 episodes | miss | Still present as ops/aviation metaphor in ep70, ep71, ep73+; de-seed reduced catchphrase use but did not retire the word — do not ban-list |
| scripts containing 'steel-man' or 'I'll concede', next 10 episodes | hit | Stock catchphrase form gone in ep69–78; only rare technique phrasing remains |
| median audio duration (chapters end), next 10 episodes | hit | Chapter end times ~9–12 min, median ~10.5; nothing above 13; 1750w ceiling holding |
| episodes airing at least one founders-notes marker, next 10 episodes | hit | Solar and/or Collingwood in ep71, ep74, ep78 (3/10) vs ≥3/10 target; Yukon/WestJet still unused |
| missing Lever segment rate (Sep-21 scored_note class) | hit | 0/10 missing in ep69–78 transcripts vs 4/18 post-Sep-4 before the validation gate |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/dp_pod_podcast.txt`** (prompt) — Remove 'a day' from a line the model may echo; ceiling itself unchanged (Sep-4 duration hit). A/B-listen because podcast prompt touches spoken-script stage.
```diff
- HARD CEILING 1,750 words: the club promises ten minutes a day, and a fourteen-minute episode breaks that promise.
+ HARD CEILING 1,750 words: the club promises about ten minutes, and a fourteen-minute episode breaks that promise.
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/dp_pod.yaml`** (config): Every ep69–78 transcript opens 'This is the DP Pod, episode N' so the Welcome-only marker never fires and Cold Open is missing from all chapter files.
- **`engine/chapters.py (or wherever mid-episode chapter titles are finalised for dialogue shows)`** (code): P0 listener-facing scrubber pollution verified in ep72/73/74/77 chapter JSON; metadata-only, no audio change.
- **`shows/prompts/dp_pod_system.txt`** (prompt): Show is Monday-only since 2026-09-21; writer system prompt still says daily and fights the public schedule + YAML description.
- **`shows/prompts/dp_pod_system.txt`** (prompt): Align mission mechanics copy with weekly cadence; Lever is per-episode on a weekly show, not 'a week' as residual daily framing.
- **`shows/prompts/dp_pod_digest.txt`** (prompt): Digest writer note still calls the brief daily after the weekly move.
- **`tests/test_dp_pod_show.py`** (code): Drift-guard pattern per playbook; pin the two P0 metadata fixes and the daily→weekly copy correction.

## Deferred (carried forward)
- Seed one real host Dispatch into dispatches.json (operator decision — fourth filing; Dan solar payback in founders notes is ready material) OR stop club-page wall promises until one exists
- Deterministic script-quality re-roll on paste/short days (ep69: 1433w + 41% digest overlap) if rate rises above ~2/10 — code gate, not prompt pressure
- Optional: widen banned-opening-verb window so Contact×3 across 10 weekly levers trips a ban (last-6 alone can miss under weekly cadence)
- Operator listen only: historical Whisper 'liver' for Lever (ep30/ep56); not observed in ep69–78
- Weekly Lever-of-the-Week + collective counter (blocked on real Dispatch receipts)
- YouTube long-form (waits on adaptive policy; Shorts-only continues)
- Additional founders biography (Yukon, WestJet, cockpit, daughters) — operator-supplied notes only; code cannot invent
- Checklist word: do not ban-list; leave to RETIRED BITS shape mining (prior miss, escalated past ban)

<sub>tokens: 57917 in / 5321 out</sub>