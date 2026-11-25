Oct-8 chapter/Cold-Open/cadence fixes partially landed in YAML and later episodes, but speaker-label scrubber titles still ship (ep77), residual daily writer/on-air copy remains, Dispatch wall is empty on fifth filing, and downloads stay flat despite clean levers and length.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1456**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| chapter titles matching ^(DAN\|PATRICK): or <4-word dialogue fragments, next 8 weekly episodes | miss | chapters_ep077.json still has DAN: Minus eighty and DAN: Strongest version of that…; sanitizer not shipped |
| Cold Open present as first chapter (title Cold Open or equivalent) when chapters enabled, next 8 episodes | partial | ep79–85 have Cold Open after YAML This is The DP Pod marker; ep76–78 still lack it |
| writer-facing prompts/system copy claiming the show is daily | miss | system.txt still day's developments; digest day's good news; transcripts still daily email / tomorrow's good news |
| Lever segment present in digest and script, next 8 weekly episodes | hit | 10/10 levers present in ep76–85 transcripts |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/dp_pod_podcast.txt`** (prompt) — On-air daily furniture survived writer-note fixes; listeners hear weekly show claim daily email/tomorrow. Touches spoken script stage → A/B-listen landmine #17.
```diff
- Dispatch / closing guidance that allows or echoes 'reply to the daily email' and sign-offs like 'subscribe … so tomorrow's good news finds you' / network outro 'family of daily podcasts' (verified spoken in ep76, ep78, ep82, ep85, ep79, ep83 transcripts).
+ Dispatch invitation must say reply to the club email (or the show's email), never 'daily email'. Closings must not promise tomorrow's episode or call the network a family of daily podcasts unless naming a specific daily sister show. Prefer: reply to the club email; subscribe so the next episode finds you; this show is part of the Nerra Network — short briefings on tech, science, and markets.
```

**`engine/intros.py`** (code) — Transcripts show the daily phrases in closing blocks copied verbatim; fixing the podcast prompt alone may not clear pool-sourced lines.
```diff
- DP Pod closing/Dispatch pool lines that still contain 'daily email', 'tomorrow's good news', or 'family of daily podcasts' if present in the intro/closing pools used for {closing_block}.
+ Replace with weekly-safe furniture: club email; next episode; Nerra Network short briefings — without promising a daily DP Pod drop. Only edit dp_pod-specific pools.
```

## Code/metadata-only proposals (no A/B needed)
- **`engine/chapters.py`** (code): P0 listener-facing scrubber pollution still shipping after Oct-8 proposal; metadata-only fix; ep77 proves the defect class is live.
- **`tests/test_dp_pod_show.py`** (code): Playbook requires drift-guard per behavioral fix; pin P0 scrubber + Cold Open latch.
- **`shows/prompts/dp_pod_system.txt`** (prompt): Show is Monday-only since 2026-09-21; writer system prompt still day-scopes the brief and fights public weekly schedule (Oct-8 prediction miss).
- **`shows/prompts/dp_pod_system.txt`** (prompt): Keep Monday framing; avoid implying a daily dispatch reading habit the empty wall cannot support; align wording with weekly cadence.
- **`shows/prompts/dp_pod_digest.txt`** (prompt): Digest still day-scopes after weekly move; Oct-8 daily-copy prediction missed.

## Deferred (carried forward)
- Seed one real host Dispatch into dispatches.json (operator decision — fifth filing; Dan solar payback in founders notes is ready material) OR stop club-page / on-air wall promises until one exists
- Deterministic script-quality re-roll on paste/short days if rate rises above ~2/10 — code gate, not prompt pressure (not firing in ep76–85)
- Optional: widen banned-opening-verb window so repeats across ~10 weekly levers trip a ban (last-6 alone can miss under weekly cadence)
- Operator listen only: historical Whisper 'liver' for Lever (ep30/ep56); not observed in ep76–85
- Weekly Lever-of-the-Week + collective counter (blocked on real Dispatch receipts)
- YouTube long-form (waits on adaptive policy; Shorts-only continues)
- Additional founders biography (Yukon, WestJet, cockpit, daughters) — operator-supplied notes only
- Checklist word: do not ban-list; leave to RETIRED BITS shape mining (prior miss, escalated past ban)
- Backfill Cold Open into pre-YAML-fix chapter JSON (ep76–78) — operator taste only

<sub>tokens: 59599 in / 4402 out</sub>