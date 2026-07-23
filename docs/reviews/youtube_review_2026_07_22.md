# YouTube pipeline + analytics review — 2026-07-22

Four days after the July 18 growth pass merged, this pass scores its
rollout-verification list against live Jul 19-22 data and ships the next
round of performance/subscription levers. All changes are render/metadata/
policy-side — no audio (outside landmine #17).

## Channel state (first read with subscriber tracking live)

| Channel | Subs | Total views | Videos | Notes |
|---|---|---|---|---|
| @NerraNetwork (en) | 207 | 58,849 | 1,875 | Jul 18: 1,242 views + 10 subs gained (2× baseline, growth-pass merge day) |
| @NerraRU (ru) | 61 | 25,749 | 501 | Views ramping hard: 1,254 → 1,398 → 2,009 over Jul 17-19 |

Subs gained by surface (90d, per-video attribution): EN long 24, EN short
15, RU short 10, RU long 7. **EN long-form is the best subscriber
converter despite lower views** — supports the conservative 1.0 EN
long-form floor and the Monday probe; long-form cuts should stay
velocity-gated, never blanket.

## Scoring the July 18 rollout-verification list

- **Fill-to-requested — HIT.** Tesla Ep546-549, FF Ep136-139, SpaceX
  Ep37-41 all ship `shorts_count_uploaded == 2 == requested` (FF Ep135
  was the last pre-fix 1-of-2).
- **Monday long-form probe — HIT.** MIT Ep112 (Mon Jul 20) is the only
  C-tier episode in the window with `yt_policy_long_skipped: False`.
- **FF-RU long-form demotion under the ru 2.0 floor — HIT.** FF-RU now
  tier C (long_vpd 0.94 < 2.0); the wasteful daily RU longs stopped.
- **spacex-RU 2 Shorts/day — MISS (design flaw, fixed this pass).**
  `shorts_per_episode` was emitted from `TIER_SETTINGS[active_tier]`, so
  a shorts-only (C) show was pinned to 1 Short regardless of data — the
  computed "-> 2 Short(s)" in the reason string was discarded. RU
  spacex/tesla/FF sat at short_vpd 45.5/18.0/45.1 (the network's hottest
  surface) while shipping half the allowed Shorts.
- **`api/youtube_channel_history.json` accruing — MISS (commit-path gap,
  fixed this pass).** `fetch_youtube_analytics.py` wrote the file on the
  runner every night, but the nightly `safe-commit-push` path whitelist
  never included it — 4 nightly runs silently dropped the snapshot.
- **Auto-comments + punch thumbnails — UNVERIFIABLE from the repo
  (observability gap, fixed this pass).** `record_youtube_outcomes` was
  never extended for the three new result keys, so `shorts_fill_modes`,
  `thumbnail_punch_text`, and `yt_comments_posted` were dropped before
  metrics. The layers may well be working; the repo just couldn't see
  them. Operator eyeball on recent uploads still worthwhile.

## New findings + fixes shipped this pass

1. **Policy: Shorts count follows the data, not the tier letter**
   (`scripts/update_youtube_policy.py`). When `short_vpd` is confident
   (≥4 in-window Shorts), `shorts_per_episode = 2 if short_vpd >= 4.0
   else 1` — regardless of tier. A data-thin dimension still holds the
   active tier's count. No extra hysteresis: the 14-day vpd average is
   already smoothed and a 1↔2 flip is cheap. Regenerated
   `api/youtube_policy.json`: RU spacex/tesla/FF/MIT now get their 2nd
   Short. Drift guards:
   `tests/test_youtube_policy.py::TestShortsCountFollowsData`.
2. **Smart Shorts start network-wide.** 7 YouTube-enabled shows
   (omni_view, models_agents, env_intel, planetterrian,
   unintended_consequences, finansy_prosto, privet_russian) never got
   `shorts_start_mode: smart` — every Short opened on the 10 s
   intro/branding beat (6/6 fallback rate each), and the adaptive policy
   could never raise them to 2 Shorts (the raise requires smart mode).
   All now pin `smart` + the fleet threshold 3.5.
3. **MAB + First Principles smart mode was dead** — smart configured but
   the 5.0 default threshold fell back to the intro on 6/6 recent
   episodes each (educational/narrative transcripts lack the digit-dense
   kickers the scorer rewards). Both now pin 3.5 (the proven
   Tesla/SpaceX/FF setting; MIT pinned too for consistency). Drift
   guards: `tests/test_youtube_growth_pass.py::TestSmartShortsNetworkWide`
   (every enabled show: smart + threshold ≤3.5).
4. **Channel-history persistence**: `api/youtube_channel_history.json`
   added to the nightly commit whitelist; the file is seeded with the
   Jul 22 snapshot (en 207 subs / ru 61) so accrual starts today.
5. **Dashboard subs delta fallback**: `_delta_7d` now falls back to the
   Analytics `day_series` net gain (last 7 rows) while the history file
   is younger than 7 days — the card shows a real number immediately
   instead of null until late July.
6. **Recorder observability**: `record_youtube_outcomes` persists
   `shorts_fill_modes`, `thumbnail_punch_text`, `yt_comments_posted`.
   Drift guards in `tests/test_youtube_feedback_loop.py`.

## Watch next (score by ~Aug 1)

- RU dub sweeps ship 2 Shorts/day for spacex/tesla/FF/MIT
  (`youtube_videos.ru.json` rows); watch short_vpd for cannibalization
  (holding ≥ ~20 on spacex-RU = healthy).
- Newly-smart shows: `shorts_start_mode_resolved: smart` with non-10.0
  offsets on omni_view/models_agents/planetterrian/UC/env_intel + the RU
  natives; MAB/FPD fallback rate drops below ~3/6. RU-language transcripts
  may still fall back often (the kicker phrases are English) — digits
  still score, so partial improvement expected, fallback harmless.
- `thumbnail_punch_text` / `yt_comments_posted` / `shorts_fill_modes`
  appear in metrics from Jul 23 onward — then actually verify the punch
  and comment layers fired (they were unverifiable this pass).
- Channel history accrues 1 row/channel/day; dashboard 7d delta flips
  from the day_series fallback to true snapshot deltas around Jul 29.
- omni_view sits at long_vpd 0.989 — hairline under the 1.0 floor; it
  will demote to shorts-only after one more C computation and the Monday
  probe becomes its re-earn path. Expected behavior, not a bug.

## Deferred (unchanged from Jul 18)

publishAt scheduling (operator declined), visual-style auto-feedback
(data thin), RU punch-text translation, subs-gained in policy velocity,
multi-audio tracks / localizations API.
