# The DP Pod — show notes and quality passes (Jul 2026 – Sep 4 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

- **DP** (The DP Pod: The Do Positive Podcast) runs via `run_show.py` +
  `shows/dp_pod.yaml`; the network's **two-host dialogue** show (July 2026
  launch) — Dan Perra + Patrick Novak, weekly (Monday) ~10 min of good news in
  science/tech plus one individual action with honest numbers ("The Lever"). Segments:
  Cold Open → The Positive Papers → The Lever → Do Positive Dispatch →
  sign-off "Do something about it." **WEEKLY on Monday since 2026-09-21** (operator-directed; was daily all 7
  days). It is in `ALT_CADENCE_SHOWS` in `tests/test_schedule.py`, never
  `DAILY_SHOWS`, and carries no Sunday recap. The cadence lives in six
  places that must agree — CRON_MAP, the scheduler Worker's SLOTS,
  `review_episodes.py`'s registry, daily-audit's RSS freshness limit,
  `engine.daily_edition`'s `monday_only`, and the public `schedule` string
  — and `tests/test_dp_pod_weekly_2026_09_21.py` pins all six.
  First show on the **two-voice dialogue TTS path**: `tts.dialogue_mode: true`
  + `tts.dialogue_voices` (`PATRICK: kdif6sqjcyiq`, `DAN: 0vscf8u8yrxc`) make
  the pipeline preserve `DAN:`/`PATRICK:` speaker labels (three legacy
  prefix-strippers are gated on the flag — `engine/generator.py`
  `_sanitize_podcast_script`, run_show's `_clean_podcast_script` + final
  defense strip) and synthesize per-speaker via `engine/tts_dialogue.py`
  (turn-group parsing, per-group Grok calls, pause padding, shared WAV
  crossfade → single MP3 encode). Dialogue mode NEVER applies the `<fast>`
  wrap (per-turn wraps are the landmine-#17 leak shape ×30 handoffs) and
  supersedes section-TTS. An unlabeled script falls back to single-voice
  `tts.voice_id` with a loud warning + `dialogue_fallback_single_voice`
  metric. Show page is `thedppod.html` (registered via
  `shows/network_meta.yaml` `show_page` override). RSS + site only at launch
  (X/YouTube/newsletter/multilingual off). Drift guards:
  `tests/test_tts_dialogue.py` (engine; existing shows pinned to
  `dialogue_mode is False`), `tests/test_dp_pod_show.py` (launch shape).
  Prompt edits change shipped audio — A/B-listen per landmine #17; the first
  episodes are the calibration set for `dialogue_pause_ms` handoff pacing.
  **Aug 10 2026 quality pass** (review:
  [`docs/reviews/dp_pod_review_2026_08_10.md`](docs/reviews/dp_pod_review_2026_08_10.md);
  drift guards: `tests/test_dp_pod_show.py::TestLeverRotationMemory`): The
  Lever had converged into week-long identical runs (heat-pump assessment
  ×7 straight, Ep24–30) — the July-9 PREVIOUS LEVER injection was the only
  lever the model saw and both prompts named quotable examples. Fixed with
  data-side rotation memory (`_recent_levers()`, 15-episode window) + full
  de-seed by shape; do NOT reintroduce example actions into the lever/
  dispatch prompt text. Scripts also pasted the brief verbatim (Ep22 65%
  shingle overlap) with zero exclamations in 27/30 episodes, so dp_pod is
  the network's first `llm.podcast_model: grok-4.5` script-stage A/B
  (experiment `dp-pod-script-model-45`, readout 2026-08-24; digest stays
  grok-4.3; revert = delete the line). Digest format spec was raised
  (Papers 6–8 sentences, Lever 6–9) because 2–3×4–6 arithmetically capped
  digests below their own 1100-word floor. **Same-day operator follow-up
  (Aug 10):** `newsletter.enabled: true` (daily briefing now real; email
  replies are the Dispatch submission channel, named on air, on the club
  page, and in the join fine print — "two honest sentences count"), and
  the catalogue was PRUNED 30 → 11 episodes (operator-directed): all
  repeated-lever episodes and high-verbatim-paste episodes removed from
  RSS/summaries/blog/site (kept 1, 2, 3, 8, 9, 11, 15, 19, 21, 24, 30 —
  each with a distinct lever; Ep30 stays partly because RSS `<itunes:
  episode>` max pins `get_next_episode_number` at 31, so the purge can
  never renumber future episodes into published GUIDs). R2 MP3s of
  deleted episodes were NOT removed (no credentials in the session;
  harmless — unreferenced). `metrics_ep*/credit_usage_*` files kept as
  real spend accounting. Still open: `dispatches.json` is empty until a
  real listener/host dispatch is seeded.
  **Sep 4 2026 naturalness pass** (review:
  [`docs/reviews/dp_pod_review_2026_09_04.md`](docs/reviews/dp_pod_review_2026_09_04.md);
  drift guards: `tests/test_dp_pod_show.py::TestSep4NaturalnessPass`):
  the Aug-10 renewal scored 3 hits / 1 miss on 26 shipped episodes
  (verbatim paste ~30% → ~3% median; the grok-4.6 script stage adopted
  Sep 1). Successor tics, all fixed data-side: the Lever converged on
  the "Open your <website> today…" SHAPE (13/26; 21/26 screen lookups) —
  `_recent_levers()` now collapses fuzzy re-skins and computes BANNED
  OPENING VERBS + REAL-WORLD ACTION DUE from the last six levers; the
  prompt's own comedy examples calcified ("checklist" 23/26, "steel-man"
  23/26) — `_recent_banter_phrases()` mines RETIRED BITS from the last
  six scripts (furniture-excluded) and the comedy/dynamic examples were
  removed by shape; the founders' notes went unused (Yukon 0/26) —
  `_founders_detail_nudge()` fires only after five real-material-free
  episodes. Episodes ran 11–14 min against a ten-minute promise → HARD
  CEILING 1,750 words. Two closings double-asked for dispatches (one
  claimed "we read every dispatch" with zero ever received) → mission
  lines instead. **YouTube ON, Shorts-only** (experiment
  `dp-pod-youtube-shorts`; long-form waits on the adaptive policy).
  `review_snapshot.py` crashed on any show without
  `exclude_title_patterns` — fixed. Do NOT re-add example actions,
  example jokes, or example concession phrases to either prompt: three
  generations of this show's tics came from exactly that.
