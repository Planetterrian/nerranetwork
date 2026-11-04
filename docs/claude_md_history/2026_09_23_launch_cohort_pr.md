# Launch-cohort PR C — the nine shows on the clock (2026-09-23)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

- **Launch-cohort PR C (2026-09-23; guards
  `tests/test_launch_cohort_schedule_2026_09_23.py`).** The nine hand-launched
  shows are on the clock (plan §6 slots, UTC): Asia Pacific 06:16, Africa &
  Middle East 06:31, Europe 06:46, Collingwood Friday 10:07
  (`FIRST_SCHEDULED_RUN` 2026-10-02 — Ep1 was hand-made on the 23rd from a
  192-hour window), North America 10:16, LatAm 10:31, Prediction Markets
  11:16, Top World 11:31 (after every desk's budget — its intake reads their
  digests), Vancouver 12:16. The six places a cadence lives all moved
  together (CRON_MAP, Worker SLOTS + FIRST_RUN, `review_episodes`
  SHOW_REGISTRY — `PRELAUNCH_SLUGS` is now EMPTY, daily-audit FEEDS,
  `test_schedule` lists; the registry `schedule` strings were already
  right). `CATCH_UP_MAX_PER_RUN` 10 → 16 (sized for 15 shows; 28 run now).
  **All 13 joined `ENGLISH_SHOWS`** (appended; pool 13 → 26, the surface
  pool is unchanged so the stride stays coprime) — until now no established
  show had ever mentioned a new one on air (⚠️ audio — A/B-listen).
  **`/mira.html` gained "Mira also reads the news"** from
  `engine.brand.MIRA_NEWS_SHOW_SLUGS` + `MIRA_NEWS_ROLE`; `MIRA_SHOW_SLUGS`
  (the claim-bearing trio) and the `mira` strand are deliberately untouched
  — the news shows are not the claim's basis. `_mira_shows(slugs=)` is one
  builder for both lists. A show page carries a dated "first scheduled
  episode" line from the registry's `first_run` (Collingwood) while that
  date is ahead — never a typed date. The nine stay OUT of the Nerra Daily
  lineup on purpose (`tests/test_daily_edition.py` EXCLUDED_NEW_SHOWS).
  Operator: `wrangler deploy` the scheduler Worker, then the first
  on-schedule slate is the listen set.
