# Listener-feedback quality pass — 2026-07-25

Operator listened to Fascinating Frontiers Ep142, SpaceX Daily Ep44, and
Modern Investing Ep117. This pass fixes the confirmed defects and several
dashboard regressions from recent Mission Control work.

## Fixes shipped

### 1. "Ep141" / letter-soup episode refs (FF Ep142, SpaceX Ep44)

**Symptom.** FF Ep142 said "on Ep141" three times (Whisper: "on EP 141").
SpaceX used the same `EpN` form from narrative memory.

**Root cause.** `build_narrative_status_block` in `engine/show_memory.py`
and `engine/tesla_memory.py` injected `Ep{N}` and seeded a callback template
the model echoed per program. `replace_episode_numbers` only matched
`episode \d+`, not `Ep141`.

**Fix.**
- Memory blocks: speak-friendly `episode {N}` + date; **CONTINUITY BUDGET ≤1**
  callback/episode; ban `EpN` abbreviations.
- Digest/podcast prompts (FF + SpaceX): same budget + ban.
- TTS defense: `\b[Ee]p\.?\s*\d+\b` → `episode {words}` in
  `assets/pronunciation.py`.

⚠️ **A/B-listen required** — prompt + TTS path changes.

### 2. SpaceX booster vs Ship landing blur (Ep44)

**Symptom.** Episode treated "the landing" / splashdown / tower-catch as one
blurred outcome; Super Heavy booster vs Ship upper stage were not kept distinct.

**Fix.** HARD RULE — NAME THE STAGE in `spacex_digest.txt` +
`spacex_podcast.txt` (validation checklist too).

⚠️ **A/B-listen required**.

### 3. Modern Investing Ep117 — silent scoreboard / NaN benchmark

**Symptom.** Spoken: "Index levels are unavailable… Portfolio… alpha…
unavailable." Tracker had `benchmark.current_close: NaN` (invalid JSON that
Python accepts). Matched-window alpha (~+6.6%) was healthy but the early-exit
in `_build_benchmark_block` hid it.

**Fix.**
- `_fetch_nasdaq_close` rejects non-finite closes.
- `_compute_benchmark_state` never persists NaN; clears poisoned alpha/YTD.
- `_build_benchmark_block` still emits MATCHED-WINDOW scoreboard when the
  live quote is missing.
- Scrubbed `investment_tracker.json` NaN → `null`.

⚠️ **A/B-listen** when the quote gap path fires (scoreboard wording changes).

### 4. Mission Control / `management.html`

| Bug | Fix |
|-----|-----|
| Show links used `{slug}.html` → 404s (`dp_pod.html`, `modern_investing.html`) | Canonical `_SHOW_PAGE_BY_SLUG` + `network_meta` overlay |
| Monday-only shows flagged `stale` after 72h | Cadence thresholds (Mon: 8d/10d; Age of AI: never) |
| Portfolio YTD tile showed `+0.00%` when both sides null/NaN | `sumOrDash` — require finite numbers; show "—" |
| Matched-window alpha invisible on dashboard | New tile when `matched_window_alpha_pct` present |

No audio impact.

## Suggested follow-ups (not in this PR)

1. **Digest ceiling / length A/B** — still the durable lever for FF/PT/UC
   chronic under-length (deferred behind the network four-show A/B).
2. **Transcript source** — publish from pre-pronunciation text so word-guides
   never leak (June M&A class).
3. **Age of AI bootstrap** — external (Supabase / Voximplant / Worker / Cal.com);
   code path is ready; keep topic queue empty.
4. **MIT live quote resilience** — optional second index source when yfinance
   returns NaN on a trading day (matched-window path already softens the miss).
5. **Cover-map DRY** — `management.html` `coverFor` map vs `network_meta`
   podcast images could share one source.
6. **safe-commit-push recovery hatch** — landmine #23 still only on run-show /
   multilingual; extend the composite if large nightly commits keep racing.

## Drift guards

`tests/test_quality_pass_2026_07_25.py` plus updates in
`test_pronunciation.py`, `test_show_memory.py`, `test_tesla_quality_pass.py`,
`test_network_quality_pass.py`.
