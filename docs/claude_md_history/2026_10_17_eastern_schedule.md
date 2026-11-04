# The schedule runs on Eastern time; Nerra Daily out by 7am Eastern (Oct 17 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### The schedule runs on Eastern time; Nerra Daily out by 7am Eastern (Oct 17 2026)

Operator-directed (register `nerra-daily-7am-eastern-2026-10-17`; guards
`tests/test_seven_am_eastern_2026_10_17.py`). **The scheduler Worker's
`SLOTS` are EASTERN wall time** (`SLOT_TZ = "America/New_York"`; the handler
converts each firing and the day filters read the Eastern date), so the clock
changes move nothing. Shows run as late as they can: 04:00 ET (UC) to 06:10 ET
(Top World, after every desk), five minutes apart; Vancouver keeps its local
05:15 Pacific slot (08:15 ET) and **is not in the edition** (it stays
choosable in Nerra Personal — `PERSONAL_EXTRA_SHOW_SLUGS`). The edition's
gate is `RELEASE_EASTERN` 06:35 / `HOLD_UNTIL_EASTERN` 06:50
(`engine/daily_edition.py`), dispatched by the Worker at those Eastern minutes;
the X queue dispatches :05/:35, 7:05 AM-10:05 PM ET. **The one cron trigger is
`*/5 * * * *`.** The run-show.yml fallback crons are UTC and cannot follow
daylight saving: **each is the slot's EST equivalent (ET + 5 h)** — in summer
it fires an hour after the Worker and the duplicate guard drops it — and
`test_scheduling_punctuality.py` compares Worker and cron map at that offset.
A new show is scaffolded with `--slot-et HH:MM` (multiple-of-five minute).
`GET /` reports slots as `{"at": "05:45", "tz": "America/New_York"}`; a Worker
still answering `"09:16Z"` predates this and the deploy check says so.
Operator: `wrangler deploy` in `workers/scheduler`.
