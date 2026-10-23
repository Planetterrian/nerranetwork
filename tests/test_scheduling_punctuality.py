"""Drift guards for the June 2026 scheduling-punctuality pass.

GitHub delivers `schedule` events 1-6 h late (Tesla's 11:00 cron observed
starting 13:54). The fix is three-layered: off-peak cron minutes
(:07/:37), an exact-time Cloudflare Worker dispatcher
(workers/scheduler), and a same-day duplicate guard in the gate so the
two drivers never double-publish. These tests pin all three AND that the
Worker's SLOTS table stays in sync with the workflow's CRON_MAP.

Oct 17 2026: the Worker's SLOTS are EASTERN wall time (SLOT_TZ =
America/New_York) so Nerra Daily is out by 7:00 AM New York and the clock
changes move nothing. The GitHub fallback crons are UTC and cannot follow
daylight saving, so each is the slot's EST equivalent (ET + 5 h); the
Worker-vs-CRON_MAP check compares them at that offset.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_WF = (_ROOT / ".github" / "workflows" / "run-show.yml").read_text(encoding="utf-8")
_TS = (_ROOT / "workers" / "scheduler" / "src" / "index.ts").read_text(encoding="utf-8")


#: Eastern Standard Time is UTC-5: a fallback cron's UTC hour minus this is
#: the Worker's Eastern slot hour.
EST_OFFSET_HOURS = 5


def _cron_map() -> dict:
    """Parse CRON_MAP entries: "M H ..." -> (UTC hour, minute, day_filter|None)."""
    entries = {}
    for m in re.finditer(
        r'"(\d+) (\d+) [^"]*":\s*\("(\w+)",\s*(?:"(\w+)"|None)\)', _WF,
    ):
        minute, hour, show, day_filter = m.groups()
        entries[show] = (int(hour), int(minute), day_filter)
    return entries


#: Weekly day filters (Sep 2026): any named weekday, not only Monday.
WEEKLY_FILTERS = {"monday", "tuesday", "wednesday", "thursday", "friday",
                  "saturday", "sunday"}


def _worker_slots() -> dict:
    # One parser for the test and the nightly deploy-drift check
    # (scripts/check_scheduler_deploy.py) — Sep 24 2026.
    from engine.scheduler_slots import worker_slots
    return worker_slots(_TS)


def test_scheduled_handler_honours_the_launch_date():
    """Sep 24 2026: Peptides Ep2 was dispatched a week before its FIRST_RUN
    because only nextSlot() (the status page) called launched(); the
    scheduled() handler checked the day filter and dispatched. A
    workflow_dispatch bypasses the workflow's FIRST_SCHEDULED_RUN gate by
    design, so the Worker is the only place the launch date can bind."""
    body = _TS.split("async scheduled(", 1)[1]
    assert "launched(" in body, "scheduled() never consults FIRST_RUN"
    assert body.index("launched(") < body.index("await dispatch(env, show)")


def test_cron_minutes_off_peak():
    """Crons are staggered so no two shows share a minute. Oct 17 2026: the
    slots are Eastern wall time on five-minute marks (04:00-06:10 ET for
    the edition shows, 08:15 for Vancouver) because the Worker's one
    trigger fires every five minutes; the GitHub fallbacks inherit those
    minutes. The Cloudflare Worker (primary, minute-accurate dispatch) is
    unaffected by GitHub's top-of-hour contention, and the duplicate guard
    still prevents double-publishing."""
    crons = re.findall(r"- cron: '(\d+) (\d+) ", _WF)
    assert crons, "no crons parsed"
    assert all(int(m) % 5 == 0 for m, _h in crons), f"unexpected cron minutes: {crons}"
    assert len({(m, h) for m, h in crons}) == len(crons), "two crons share a minute"


def _est_to_eastern(cron_map: dict) -> dict:
    """CRON_MAP converted to the Worker's clock: the UTC fallback cron at the
    EST offset (UTC-5) is the Eastern slot."""
    return {show: (h - EST_OFFSET_HOURS, m, f) for show, (h, m, f) in cron_map.items()}


def test_worker_slots_match_cron_map():
    cron_map = _cron_map()
    slots = _worker_slots()
    # Count is derived, not pinned: every `- cron:` line must parse into a
    # CRON_MAP entry, so a new show that adds one without the other fails.
    crons = re.findall(r"- cron: '([^']+)'", _WF)
    assert len(cron_map) == len(crons), f"CRON_MAP parse drift: {sorted(cron_map)}"
    eastern = _est_to_eastern(cron_map)
    assert slots == eastern, (
        "workers/scheduler SLOTS (Eastern) desynced from run-show.yml CRON_MAP "
        "(UTC at the EST offset, ET + 5 h):\n"
        f"  worker-only/changed: { {k: v for k, v in slots.items() if eastern.get(k) != v} }\n"
        f"  cron-map-only/changed: { {k: v for k, v in eastern.items() if slots.get(k) != v} }"
    )


def test_worker_slots_are_eastern_wall_time():
    from engine.scheduler_slots import SLOT_TZ, worker_slot_tz
    assert SLOT_TZ == "America/New_York"
    assert worker_slot_tz(_TS) == SLOT_TZ
    # The handler converts the firing to the slot clock and the day filters
    # read the Eastern calendar, never getUTC*.
    body = _TS.split("async scheduled(", 1)[1]
    assert "wallClock(now)" in body
    assert "getUTCHours" not in _TS and "getUTCDay" not in _TS and "getUTCDate" not in _TS


def test_every_slot_stays_inside_one_utc_day():
    """04:00-08:15 ET is 08:00-13:15 UTC under EDT and 09:00-13:15 under EST:
    the gate's UTC weekday filter and the Worker's Eastern one agree."""
    for show, (h, m, _f) in _worker_slots().items():
        assert 0 <= h + 4 and h + EST_OFFSET_HOURS <= 23, (show, h, m)


def _trigger_fires(utc_hour: int, utc_minute: int) -> bool:
    toml = (_ROOT / "workers" / "scheduler" / "wrangler.toml").read_text(encoding="utf-8")
    crons = re.findall(r'^crons = \[(.*)\]', toml, re.M)[0]
    for cron in re.findall(r'"([^"]+)"', crons):
        minute, hour = cron.split()[:2]
        if minute.startswith("*/"):
            mins = set(range(0, 60, int(minute[2:])))
        elif minute == "*":
            mins = set(range(60))
        else:
            mins = {int(x) for x in minute.split(",")}
        if hour == "*":
            hrs = set(range(24))
        elif "-" in hour:
            lo, hi = (int(x) for x in hour.split("-"))
            hrs = set(range(lo, hi + 1))
        else:
            hrs = {int(x) for x in hour.split(",")}
        if utc_minute in mins and utc_hour in hrs:
            return True
    return False


def test_worker_trigger_covers_all_slots():
    # Oct 17 2026: one trigger, every five minutes. Every Eastern slot must
    # be a firing minute under BOTH offsets (EDT = UTC-4, EST = UTC-5); the
    # edition clock itself is pinned in
    # tests/test_seven_am_eastern_2026_10_17.py.
    toml = (_ROOT / "workers" / "scheduler" / "wrangler.toml").read_text(encoding="utf-8")
    assert 'crons = ["*/5 * * * *"]' in toml
    for show, (h, m, _f) in _worker_slots().items():
        for offset in (4, 5):
            assert _trigger_fires((h + offset) % 24, m), (show, h, m, offset)


def test_gate_has_duplicate_guard():
    assert "Duplicate guard" in _WF
    assert "Auto-generated: {slug} {today_str}" in _WF
    # The guard must be best-effort: API failure → run the show anyway.
    assert "proceeding without it" in _WF


def test_run_job_has_post_concurrency_duplicate_recheck():
    """The gate's guard runs at queue time and can be stale by the time
    the per-show concurrency lock releases (FF double-published June 12
    2026). The run job must re-check after the lock + fresh checkout."""
    assert "Post-concurrency duplicate re-check" in _WF
    assert "Duplicate re-check" in _WF


def test_review_schedules_match_cron_day_filters():
    """July 21 2026: review_episodes.py believed env_intel ran on odd
    weekdays while the production CRON_MAP is Monday-only — so the daily
    audit flagged a phantom "missed episode" every non-Monday odd weekday
    AND dispatched an off-schedule episode via the retry path (the July 18
    network review's open P0; FP/PR had the same drift as "even"). Any
    show whose cron carries a Monday day-filter must be "monday" in the
    reviewer registry so the audit's cadence beliefs track production.
    """
    import review_episodes

    cron_map = _cron_map()
    for show, (_h, _m, day_filter) in cron_map.items():
        info = review_episodes.SHOW_REGISTRY.get(show)
        if info is None:
            continue  # not all shows are audited (e.g. age_of_ai)
        if day_filter in WEEKLY_FILTERS:
            assert info.get("schedule") == day_filter, (
                f"{show}: CRON_MAP is {day_filter}-only but review_episodes "
                f"says {info.get('schedule')!r} — the audit will flag "
                "phantom missed episodes and dispatch off-schedule runs"
            )
        else:
            assert info.get("schedule") not in WEEKLY_FILTERS, (
                f"{show}: review_episodes says weekly but the cron "
                "has no weekday day-filter"
            )


def _audit_rss_limits() -> dict:
    """Parse the daily-audit RSS-freshness FEEDS dict: feed file -> limit."""
    audit = (_ROOT / ".github" / "workflows" / "daily-audit.yml").read_text(
        encoding="utf-8"
    )
    entries = {}
    for m in re.finditer(r'"([\w.]+\.rss)":\s*\("[^"]+",\s*(\d+)\)', audit):
        entries[m.group(1)] = int(m.group(2))
    return entries


def test_audit_rss_limits_match_cron_cadence():
    """Aug 15 2026: env_intel/finansy_prosto/privet_russian moved to
    Monday-only cadence but the daily audit's RSS staleness limits kept
    their old daily/alt-cadence values (96-120h), so the audit paged the
    operator every Saturday for feeds that were exactly on schedule. The
    limit must follow the cadence CRON_MAP declares: a Monday-only show
    needs headroom past one full week (>=192h), and a daily show must
    stay tight enough (<=120h) that a real outage still pages within a
    few missed cycles."""
    cron_map = _cron_map()
    limits = _audit_rss_limits()
    assert limits, "no FEEDS limits parsed from daily-audit.yml"
    for show, (_h, _m, day_filter) in cron_map.items():
        feed = "podcast.rss" if show == "tesla" else f"{show}_podcast.rss"
        assert feed in limits, (
            f"{show}: scheduled in CRON_MAP but missing from the daily "
            "audit's RSS freshness FEEDS — a dead feed would never page"
        )
        limit = limits[feed]
        if day_filter in WEEKLY_FILTERS:
            assert limit >= 192, (
                f"{show}: weekly cadence but audit limit is {limit}h "
                "(<192h) — pages every week for an on-schedule feed"
            )
        else:
            assert limit <= 120, (
                f"{show}: daily cadence but audit limit is {limit}h "
                "(>120h) — a real outage would go unnoticed for days"
            )


def test_edition_dispatch_slot():
    """Nerra Daily has an exact-time driver: the Worker dispatches
    nerra-daily.yml on EASTERN wall time (06:35 release and 06:50 end of
    the straggler hold, Oct 17 2026 — 07:50/09:01 Pacific from Oct 8,
    13:07 UTC before that). Deliberately NOT a SLOTS row (those parse as
    shows above). The clock itself is pinned in
    tests/test_seven_am_eastern_2026_10_17.py."""
    m = re.search(
        r'EDITION_DISPATCH = \{\s*tz: "America/New_York",\s*times: \[(.*?)\] as '
        r'Array<\[number, number\]>,\s*workflow: "([\w.-]+)",', _TS, re.S)
    assert m, "EDITION_DISPATCH missing from workers/scheduler"
    assert m.group(2) == "nerra-daily.yml"
    # Oct 9 2026: ONE cron trigger. The account was then on Workers Free
    # (five cron triggers in total, the Voices Worker held three; Workers
    # Paid since Oct 23) and a second
    # trigger here was refused at deploy, so the edition dispatch never went
    # live. One expression covers every Eastern minute the handler needs;
    # the handler decides from the exact firing minute.
    toml = (_ROOT / "workers" / "scheduler" / "wrangler.toml").read_text(
        encoding="utf-8")
    crons = re.findall(r'^crons = \[(.*)\]', toml, re.M)
    assert crons and crons[0].count('"') == 2, (
        "the scheduler holds exactly one cron trigger: the handler decides "
        "from the firing minute, so a second one is never needed")
    assert crons[0] == '"*/5 * * * *"', crons
    # The edition and the show slots are independent dispatches now, but a
    # slot on an edition minute would still be a scheduling mistake.
    times = {(int(h), int(mi)) for h, mi in re.findall(r"\[(\d+),\s*(\d+)\]", m.group(1))}
    slot_times = {(h, mi) for h, mi, _f in _worker_slots().values()}
    assert times and not times & slot_times, times & slot_times


_VOICES_TS = (_ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")


def test_cron_workers_trim_the_dispatch_token():
    """Aug 31 2026: both cron Workers were deployed yet neither reached
    GitHub. A token pasted into `wrangler secret put` with a trailing
    newline authenticates as `Bearer <token>\\n` and gets a silent 401 in
    the Worker while the operator's clean curl test passes. Both Workers
    now trim the secret before use."""
    assert 'GITHUB_DISPATCH_TOKEN || "").trim()' in _TS, "scheduler must trim the token"
    assert 'GITHUB_DISPATCH_TOKEN || "").trim()' in _VOICES_TS, "voices must trim the token"
    assert "Bearer ${env.GITHUB_DISPATCH_TOKEN}" not in _TS
    assert "Bearer ${env.GITHUB_DISPATCH_TOKEN}" not in _VOICES_TS


def test_cron_workers_expose_read_only_health_probes():
    """A deploy must be verifiable from a browser, not by waiting for a
    slot: the scheduler serves GET /health and voices GET /voices/health,
    each with a live read-only GitHub auth probe that never dispatches."""
    assert 'url.pathname === "/health"' in _TS
    assert "githubSelfTest" in _TS
    assert "actions/workflows/${WORKFLOW}`" in _TS, "scheduler probe must test the Actions permission"
    assert 'path === "/voices/health"' in _VOICES_TS
    assert "handleHealth" in _VOICES_TS
    # The probes are read-only: no dispatch endpoint is exposed over HTTP.
    fetch_body = _TS.split("async fetch(")[1].split("async scheduled(")[0]
    assert "dispatchWorkflow(" not in fetch_body


def test_scheduler_retries_transient_dispatch_failures():
    assert "attempt <= 2" in _TS
    assert "res.status < 500 && res.status !== 429" in _TS, (
        "4xx is configuration — retrying must not mask a bad token")


def test_edition_wakes_the_personal_build():
    """Sep 14 2026: Nerra Personal's private batch repo relied on its own
    12:30 UTC GitHub cron, which GitHub delivered 4-5 h late every day
    (16:30-18:09 UTC, Sep 7-14) — subscribers got Monday's edition at
    lunchtime while Nerra Daily, which the scheduler Worker dispatches at
    12:07 sharp, was out for hours. The edition workflow now wakes the
    personal build the moment it publishes. Pin the two things that make
    that safe: the dispatch is gated on the edition being published BY
    THIS RUN (a --when-ready no-op must never wake a build that would
    splice a day without Nerra Daily and then lock the date), and it
    soft-no-ops without the cross-repo token so the batch repo's fallback
    cron still ships the edition, late."""
    import yaml

    wf = yaml.safe_load(
        (_ROOT / ".github" / "workflows" / "nerra-daily.yml").read_text(encoding="utf-8"))
    steps = {s.get("name"): s for s in wf["jobs"]["build"]["steps"]}
    post = steps["Did this run publish the edition?"]
    wake = steps["Wake the Nerra Personal build"]
    assert post["id"] == "postgate"
    assert "summaries_nerra_daily.json" in post["run"]
    assert wake["if"].strip() == "steps.postgate.outputs.published == 'true'"
    assert "nerra-personal-batch/actions/workflows/personal-feeds.yml/dispatches" in wake["run"]
    assert "PERSONAL_BATCH_DISPATCH_TOKEN" in wake["env"]["PERSONAL_BATCH_DISPATCH_TOKEN"]
    # Missing token: warn and exit 0, never fail the edition run.
    assert 'if [ -z "$PERSONAL_BATCH_DISPATCH_TOKEN" ]' in wake["run"]
    assert "exit 0" in wake["run"]
    # The dispatched build gets the edition's date, not "today UTC" on the
    # runner, so a late sweep for yesterday wakes yesterday's build.
    assert '\\"date\\":\\"$EDITION_DATE\\"' in wake["run"]
