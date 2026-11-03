# Adaptive YouTube publishing policy (July 2026; growth, scoring and retention passes)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Adaptive YouTube publishing policy (July 2026)

Publish volume/format now adapts to what each channel actually watches
(full doc: [`docs/youtube_feedback_loop.md`](docs/youtube_feedback_loop.md)
"Adaptive publishing policy"). Nightly `scripts/update_youtube_policy.py`
(no secrets; runs right after the title-hint step) turns
`api/youtube_stats.json` into **`api/youtube_policy.json`**: per
show × channel tiers from 14-day views-per-day velocity (A = long + 2
Shorts, B = long + 1, C = shorts-only, D = probe; long on at
`long_vpd ≥ 1.0`, 2 Shorts at `short_vpd ≥ 4.0`, Shorts NEVER 0 — they're
the recovery signal; <4 in-window videos of a kind holds that dimension).
**Hysteresis:** the active tier flips only after the same computed tier on
2 consecutive runs; cold-start actives are `SEED_TIERS` hardcoded from the
2026-07-14 analytics (RU long-form seeded off everywhere). Consumers via
`engine.youtube_policy.resolve_publish_plan`: `run_show._publish_youtube`
(EN + native-RU shows; a shorts-only tier skips the long-form render/upload
while Shorts + the shared thumbnail still ship; Shorts raise to 2 only with
`shorts_start_mode: smart`; metrics `yt_policy_tier` /
`yt_policy_long_skipped` / `yt_policy_shorts`) and
`engine.ru_dub.publish_ru_dub` (@NerraRU dubs; the sweep's done-check now
also counts an uploaded Short). Best-effort by contract: missing policy
file / absent slug / `youtube.adaptive_publishing: false` (new field,
default true) = exact legacy YAML behavior. The policy never edits YAML
files at runtime and never touches audio (outside landmine #17). Drift
guards: `tests/test_youtube_policy.py`.

**July 18 2026 growth pass** (review:
[`docs/reviews/youtube_growth_review_2026_07_18.md`](docs/reviews/youtube_growth_review_2026_07_18.md);
drift guards: `tests/test_youtube_growth_pass.py`,
`tests/test_shorts_selector.py::TestFillToRequested`): post-policy
verification found tier gating exact, RU titles fixed, and RU/EN Shorts
massively outperforming long-form — but tier-A shows chronically
under-shipped Shorts (FF 1-of-2 on EVERY July episode). Shipped:
**fill-to-requested** in the multi-Shorts selector (sub-threshold windows
ship rather than fewer Shorts; `qualified` flag + `shorts_fill_modes`
metric; FF threshold 3.5 parity); **RU multi-Shorts** (policy may raise to
2 — RU Shorts are the network's best surface, spacex-RU short_vpd 30);
**subscriber tracking** (analytics schema v2: per-video subscribersGained,
channel snapshots + `api/youtube_channel_history.json`, dashboard card,
subs-blended title hints — subscribers were previously tracked nowhere);
**title bundle** (one Grok call → long titles + 2-4-word ALL-CAPS
thumbnail punch text + per-window Short titles; empty fields = exact
legacy fallbacks; opt-outs `thumbnail_punch_text` / `optimized_titles`);
**auto-comments** (`engine.youtube.post_video_comment` — long-form posts
the pinned-comment template, Shorts post the full-episode funnel link, RU
only when a RU long exists; API can't pin, operator pins in Studio;
opt-out `auto_comment`); **channel-specific long-form floor**
(`LONG_VPD_FLOOR` en 1.0 / ru 2.0 — RU longs earned ~9% retention);
**gallery-retention style tags** now mined from image prompts (per-show
doc-frequency boilerplate filter). Operator declined publishAt scheduling
(uploads stay immediate). All render/metadata-side — outside landmine #17.

**July 22 2026 scoring pass** (review:
[`docs/reviews/youtube_review_2026_07_22.md`](docs/reviews/youtube_review_2026_07_22.md);
drift guards: `tests/test_youtube_policy.py::TestShortsCountFollowsData`,
`tests/test_youtube_growth_pass.py::TestSmartShortsNetworkWide`): scored the
07-18 rollout list — fill-to-requested HIT (Tesla/FF/SpaceX all 2/2 since
the fix), Monday probe HIT (MIT Ep112, Mon 07-20), FF-RU long demotion HIT;
two MISSes fixed: (1) **`shorts_per_episode` now follows the computed
`short_vpd`, not the tier letter** — `TIER_SETTINGS[active]` had pinned
shorts-only (C) shows to 1 Short, discarding the computed "-> 2 Short(s)"
(RU spacex/tesla/FF sat at short_vpd 18-45, the network's hottest surface,
shipping half the allowed Shorts; policy regenerated, they get the 2nd
Short now); (2) **`api/youtube_channel_history.json` was never committed**
(nightly add-paths whitelist gap — 4 runs silently dropped the snapshot;
path added, file seeded en 207 / ru 61 subs, dashboard `_delta_7d` falls
back to the day_series net gain while history is <7 days old). Also:
**smart Shorts start network-wide** — 7 enabled shows (OV, M&A, EI, PT, UC,
FP, PR) still resolved `voice` (every Short opened on the 10 s intro) and
MAB/FPD's smart mode fell back 6/6 at the 5.0 default threshold; all
enabled shows now pin `smart` + fleet threshold 3.5 (guarded). And
`record_youtube_outcomes` finally persists `shorts_fill_modes` /
`thumbnail_punch_text` / `yt_comments_posted` (the 07-18 layers had shipped
invisibly — verify punch + comments in metrics from 07-23). Subscriber
attribution insight: EN long-form converts subs best (24 vs 15 EN-short /
10 RU-short of 56 tracked) — long-form cuts stay velocity-gated, never
blanket. All policy/metadata-side — outside landmine #17.

**July 30 2026 retention pass** (drift guards:
`tests/test_intros.py`, `tests/test_shorts_selector.py::TestShortsClipLength`,
`tests/test_youtube_policy.py::{TestShortsSupplyLadder,TestMaxShortsCeiling}`,
`tests/test_ru_dub.py::TestClauseTrim`):

- **Every episode now opens on its hook** (AUDIO — A/B-listen per
  landmine #17). Ten seconds of theme music played alone, then
  `build_intro_line` emitted a ~35-word greeting with the date, so the
  first fact arrived around second 28. Long-form median retention was
  10.7% EN / 6.3% RU with average view durations of 18-85 s on 5-13
  minute videos; Shorts, which skip the intro, run ~42% on the same
  audio. `build_intro_line` now emits one short identity line,
  `build_cold_open_spec` injects the shared cold-open rules into all 15
  podcast prompts (no example sentence — de-seed by shape), the prompts
  put `{hook}` before `{intro_line}`, and `voice_intro_delay` is 0 with
  `intro_duration` 3 network-wide. **Music still plays from t=0 and the
  sidechain holds it at the same level under the opening line as
  mid-episode (-31.7 dB either side, verified by render), so this is a
  cold open in structure, not a bare one in sound.** Three shows keep a
  short `identity_tail` / `identity_template` because their line carries
  something load-bearing: DP Pod names both hosts, Age of AI discloses
  its AI host, and the Russian shows would otherwise be handed English.
- **Shorts run 35 s** (was 55 default / 40 on five shows). Median Short
  holds 21 s (n=348, 90-day window), so length mostly decides what
  percentage that is: 38% at 55 s, 60% at 35 s. The dataclass default and
  the four `getattr` fallbacks moved too — `ru_dub` / `lang_dub` /
  `youtube_shorts` each resolve through one, so a stale default would
  ship long Shorts on the dub channels only.
- **Shorts supply ladder gained a 3-Short band** at 20 vpd (`SHORT_VPD_BANDS`
  + `shorts_for_vpd`). RU spacex 62.3 / FF 60.5 had the same supply as
  RU MIT 4.9. Two silent caps had to go first: `build_policy` carried a
  second copy of the threshold rule (logged "-> 3" and wrote 2), and
  `ru_dub`/`lang_dub` each had a local `min(2, ...)` — and the band's
  members are RU dubs, so those literals would have made it a total
  no-op. The ceiling is now `engine.youtube_policy.MAX_SHORTS_PER_EPISODE`,
  enforced in `resolve_publish_plan`.
- **Dub Short titles trim to a clause** (`_clause_trim`). 26% of published
  FR Short titles ended on a dangling preposition (RU 5%, EN 1%) because
  the title is cut from the translated LONG title at 70 chars and French
  runs ~15-20% longer than its English source. Per-language stop-word
  tails, a 55%-of-budget floor, and an unregistered language stays a
  plain word trim.
