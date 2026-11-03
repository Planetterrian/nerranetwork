# Landmine 20 — YouTube quota cap (May 2026; expansions June 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

20. **YouTube quota cap (May 2026; four-show expansion June 2026)** —
    the YouTube Data API quota is 10,000 units/day **per channel**;
    each `videos.insert` costs 1,600 units (plus thumbnail 50 /
    playlist 50 / caption 400 on the paper model in
    `engine/youtube_quota.py`). The May 2026 schedule overhaul had
    disabled YouTube on every English show except Tesla and MAB
    (long-form + 2 Shorts each). **June 2026 expansion (operator
    decision, quota-increase request submitted and pending):**
    - Tesla + MAB dropped from 2 Shorts to 1 each.
    - Fascinating Frontiers + Modern Investing enabled **Shorts-only**
      (`publish_long_form: false`) on `@NerraNetwork`. Flip
      `publish_long_form: true` per show once the increase is granted.
    - Финансы Просто + Привет, Русский! enabled **full format** on
      `@NerraRU` (`channel: ru`, its own 10k/day quota; both run even
      days only ≈ 7,600 paper-units). Requires the
      `YOUTUBE_REFRESH_TOKEN_RU` secret — uploads no-op with a logged
      warning until it's set.
    EN channel paper-math now projects 11,000/day — the SAME paper
    level as the previous Tesla+MAB 2-Shorts config, which ran in
    production without quota failures (the documented-cost model is
    conservative vs. actual charging), so the daily preflight
    `::error::` annotation is expected until the increase lands.
    `estimate_network_daily_units` groups per channel since June 2026
    (a RU show never counts against the EN budget). Drift guards:
    `test_only_tst_and_mab_enable_youtube` pins the exact enabled set,
    `test_youtube_expansion_quota_shape` pins the 1-Short /
    Shorts-only / ru-channel shape so a partial revert fails CI.
    - **June 14 2026 — SpaceX Daily swapped in for MAB.** SpaceX Daily
      took MAB's EN-channel **full-format** slot (long-form + 1 Short);
      MAB's `youtube.enabled` flipped to `false` (rest of its block
      retained for a one-line re-enable). Same per-episode EN footprint,
      so the 11,000/day paper-math and the expected preflight `::error::`
      are unchanged. The EN full-format pair is now **Tesla + SpaceX**;
      FF + MIT stay Shorts-only; RU shows unchanged. `YOUTUBE_ENABLED_SHOWS`
      in `tests/test_schedule.py` updated accordingly. **All YouTube-enabled
      shows now generate imagery with Grok Imagine** (FF/MIT/RU previously
      inherited the `pexels` default → stock Shorts; now `image_provider:
      grok` is pinned, guarded by `test_all_youtube_shows_use_grok_imagine`).
      Operator one-time setup pending: create the SpaceX podcast playlist in
      Studio + flag it (landmine #15); uploads publish without it (warned).
    - **June 26 2026 — quota raised 10k → 200k; full-network rollout.** The
      @NerraNetwork quota increase landed, so the constrained shape above is
      undone (full rollout doc:
      [`docs/youtube_rollout_2026_06_25.md`](docs/youtube_rollout_2026_06_25.md)).
      `DEFAULT_DAILY_QUOTA` is now **200k**, env-overridable per channel
      (`YOUTUBE_DAILY_QUOTA[_EN|_RU]`, `resolve_daily_quota()`). **All 13 shows**
      publish to YouTube: FF + MIT flipped back to long-form, FPD added Shorts,
      MAB un-paused, and the 6 disabled shows (env_intel, planetterrian,
      omni_view, models_agents, models_agents_beginners, unintended_consequences)
      enabled with `image_provider: grok`. Tesla + SpaceX back to **2
      Shorts/episode**. EN steady state ≈ **24 uploads/day, ~45k units** (vs
      200k). Quota is no longer the constraint — **cadence is**: the preflight
      now warns (never blocks) above `SAFE_DAILY_UPLOADS_PER_CHANNEL` (default
      30, env `YOUTUBE_SAFE_DAILY_UPLOADS`), since YouTube's inauthentic-content
      policy penalises mass posting. Mitigations shipped same-day: LLM-optimized
      long-form titles separate from the spoken hook
      (`engine/youtube_titles.py`, `youtube.optimized_titles`) and the
      slideshow still-hold cap lowered 25 → 15 s for more motion network-wide
      (commit `6559b3a9`). None of these touch audio (outside landmine #17).
      **The hybrid Grok video-clip pilot on Tesla + SpaceX has since been
      REMOVED network-wide (commit `72d81cce`, June 29 2026): the Ep526 pilot
      showed ~1/3 clip success at ~$0.35/ep for the weakest payoff and pushed
      the render toward the 40-min pipeline timeout — the most expensive
      component for the least value (full Grok Video was already disabled
      June 23, commit `08021ebe`, as ~$40-50/ep). `video_clips_enabled` is
      `false` everywhere; motion now comes entirely from slideshow crossfades
      + varied Ken Burns over Grok Imagine stills. Recovery scripts
      (`scripts/recover_grok_video.py` et al.) still exist for any
      already-generated clips.** Enabled-set + 200k + 15 s cap pinned by
      `tests/test_schedule.py`, `tests/test_youtube_quota.py`,
      `tests/test_youtube_quality_pass.py`, `tests/test_config.py`. Operator
      one-time tasks: create/flag the 6 new shows' podcast playlists (landmine
      #15), confirm quota scope + set the env budget if EN-only, and enable
      Studio Title/Thumbnail "Test & Compare" (the runner stashes 3 title
      candidates).
