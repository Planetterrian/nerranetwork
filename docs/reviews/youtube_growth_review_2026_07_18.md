# YouTube pipeline — post-change review + growth pass (2026-07-18)

Operator request: review how the recent changes worked out on YouTube,
then further improvements to increase subscribers and reach and deliver a
great short- and long-form product. Operator decisions confirmed before
implementation: NO scheduled publishing (keep immediate), YES auto-comments,
YES punch-text thumbnails, YES raised RU long-form bar.

## Part 1 — how the Jul 14–16 changes worked out (evidence through Jul 17-18)

**Working as designed:**
- Adaptive policy tier gating is exact: all 6 EN C-tier shows skip the
  long-form render (quota 3,800 → 1,700 units/episode) while Shorts + the
  shared thumbnail still ship. Hysteresis is stable — one clean promotion
  (omni_view C→B, coinciding with its editorial realignment), UC demoted
  B→C, RU fascinating_frontiers promoted C→A and shipping RU longs.
- The RU title fix (PR #833) cut over cleanly: since Jul 18 all @NerraRU
  uploads carry translated, optimized headlines (the "Эп. N: …"
  truncation is gone).
- The analytics loop is LIVE (retention flows; `title_hint` populated for
  every show; `gallery_retention.json` populated).

**The data:**
- RU Shorts are the network's growth engine: 7,028 views/90d across 83
  videos; spacex-RU alone 677 views in 7 days (short_vpd 30).
- EN Shorts beat EN long everywhere (Tesla 306 vs 157 views/7d; FF Shorts
  75% average retention). The C-tier longs the policy cut were earning
  6-13% retention and single-digit weekly views — the cut cost nothing.

**Open issues found:**
1. "Requests 2 Shorts, ships 1" persisted — FF shipped 1-of-2 on EVERY
   July episode (its calm science prose rarely beats the kicker-phrase
   scoring threshold; the selector returned nothing and the 10-second
   voice fallback shipped one Short), SpaceX 1-of-2 on 3 of 4.
2. Subscribers were tracked NOWHERE (the metric the operator wants to
   grow).
3. RU long-form is near-worthless (435 views / 68 videos, ~9% retention)
   yet FF-RU's promotion started daily RU long renders.
4. `gallery_retention.json` tag summaries were EMPTY (manifest tags are
   boilerplate; the style signal lives in the prompt field).
5. The Monday long-form probe first fires Jul 20 (untested — observe).

## Part 2 — what shipped

1. **Shorts volume fix** (the best format was under-shipped):
   - `pick_top_n_engaging_windows(fill_to_n=True)`: when fewer than the
     requested N windows beat the threshold, fill remaining slots with
     the best non-overlapping sub-threshold windows (score ≥ 0; negative
     boring-opener windows never ship), marked `qualified=False`. The
     requested count is a policy decision — the selector ranks, it
     doesn't veto. Metric: `shorts_fill_modes` per Short.
   - FF gets `shorts_min_score_threshold: 3.5` (Tesla/SpaceX parity).
   - RU multi-Shorts: the policy may now raise RU Shorts to 2 (hard cap;
     `smart_mode=True` in ru_dub's policy call — the old False silently
     capped every RU show at 1). Second RU Short gets its own window,
     captions, and a distinct title from its window's opening text.
2. **Subscriber tracking**: analytics fetch (schema v2) adds per-video
   `subscribersGained/Lost` + per-channel statistics snapshot + 30-day
   day-series + daily history (`api/youtube_channel_history.json`);
   dashboard gains a "YouTube channels" card (subs, 7d delta, top
   subscriber-driving videos); the title-hint ranking now blends
   retention with subs gained and quotes converting titles.
3. **Punch-text thumbnails** (operator-approved brand change): one Grok
   call (`generate_title_bundle`, replacing the titles-only call at the
   same cost) also returns a 2-4 word ALL-CAPS punch text rendered as
   the thumbnail's dominant element (~2× font base) + a punchy ≤60-char
   title per Short window. Empty fields fall back to exact legacy
   behavior. Opt-outs: `thumbnail_punch_text`, `optimized_titles`.
4. **Auto-comments** (operator-approved): `post_video_comment` posts a
   channel comment on every upload — long-form gets the pinned-comment
   template (now shared via `build_pinned_comment_text`), Shorts get
   "▶ Full episode: <link> / 🔔 Subscribe", RU Shorts the Russian
   equivalent (only when a RU long exists — never link an English video
   from a Russian Short). The API cannot pin; the operator pins manually
   in Studio. 403 = graceful no-op. Opt-out: `auto_comment`.
5. **RU long-form floor** (operator decision): `LONG_VPD_FLOOR` is
   channel-specific — en 1.0, ru 2.0. FF-RU (long_vpd 1.39) will demote
   back to shorts-only after the standard 2-run hysteresis; the Monday
   probe still generates the data to re-earn it.
6. **Gallery retention style tags**: tags are now mined from the image
   PROMPT field (comma-split phrases; per-show >50%-document-frequency
   boilerplate auto-excluded — no hand-curated stoplist). Verified on
   live data: 1,420 images labeled across 13 shows. The
   auto-feedback into `grok_image_descriptor` is deliberately NOT wired
   yet (thin sample sizes; revisit after 2-3 weeks of labeled data).

Drift guards: `tests/test_youtube_growth_pass.py` (22 tests),
`tests/test_shorts_selector.py::TestFillToRequested`, updated
`tests/test_ru_dub.py` parity test.

## Rollout verification (check after 2-3 days of episodes)

- FF + SpaceX metrics: `shorts_count_uploaded == shorts_count_requested`;
  `shorts_fill_modes` distribution (FF should mix qualified/filled at the
  3.5 threshold; no more `[10.0]` fallbacks).
- spacex-RU: 2 Shorts/day in `youtube_videos.ru.json`; watch short_vpd
  for cannibalization (holding ≥ ~20 = healthy).
- `api/youtube_channel_history.json` gaining one row/channel/day; the
  dashboard subs card fills in (7d delta needs a week of rows).
- Auto-comments visible on new uploads (operator: pin the good ones); no
  403 warnings in the run logs.
- Thumbnails: eyeball the punch text on 2-3 episodes — revert per show
  via `thumbnail_punch_text: false` if the style reads wrong.
- Policy log Jul 20-22: Monday probe fires; FF-RU long demotes after the
  2-run streak under the new ru floor.

## Deferred

- publishAt golden-hour scheduling (operator declined — keep immediate).
- Chapter-anchored fill phase for the selector (only if score≥0 fill
  proves insufficient).
- Visual-style-hint auto-feedback into image prompts (data too thin).
- RU punch-text thumbnails (needs translation; legacy rendering kept).
- Subs-gained in policy velocity (too sparse for tier flips at current
  volume).
- YouTube native multi-audio tracks + localizations API metadata (multi-
  audio is not publicly available; localizations worth revisiting once
  the FR/ES/ZH tracks have audiences).
