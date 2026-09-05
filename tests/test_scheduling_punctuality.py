"""Drift guards for the June 2026 scheduling-punctuality pass.

GitHub delivers `schedule` events 1-6 h late (Tesla's 11:00 cron observed
starting 13:54). The fix is three-layered: off-peak cron minutes
(:07/:37), an exact-time Cloudflare Worker dispatcher
(workers/scheduler), and a same-day duplicate guard in the gate so the
two drivers never double-publish. These tests pin all three AND that the
Worker's SLOTS table stays in sync with the workflow's CRON_MAP.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_WF = (_ROOT / ".github" / "workflows" / "run-show.yml").read_text(encoding="utf-8")
_TS = (_ROOT / "workers" / "scheduler" / "src" / "index.ts").read_text(encoding="utf-8")


def _cron_map() -> dict:
    """Parse CRON_MAP entries: "M H ..." -> (show, day_filter|None)."""
    entries = {}
    for m in re.finditer(
        r'"(\d+) (\d+) [^"]*":\s*\("(\w+)",\s*(?:"(\w+)"|None)\)', _WF,
    ):
        minute, hour, show, day_filter = m.groups()
        entries[show] = (int(hour), int(minute), day_filter)
    return entries


def _worker_slots() -> dict:
    entries = {}
    for m in re.finditer(
        r'\[(\d+),\s*(\d+),\s*"(\w+)",\s*(?:"(\w+)"|null)\]', _TS,
    ):
        hour, minute, show, day_filter = m.groups()
        entries[show] = (int(hour), int(minute), day_filter)
    return entries


def test_cron_minutes_off_peak():
    """Crons are staggered to avoid bunching on the same minute. The
    original :07/:37 design avoided top-of-hour contention but capped at
    2 slots/hour (13 shows, 12 hours min). For 10 daily shows in 3 hours,
    :01/:16/:31/:46 spacing is used instead (same anti-bunch principle,
    tighter packing). GitHub fallback crons are no longer on the
    historically-off-peak :07/:37 marks, but the Cloudflare Worker (primary,
    minute-accurate dispatch) is unaffected and the duplicate guard still
    prevents double-publishing."""
    crons = re.findall(r"- cron: '(\d+) ", _WF)
    assert crons, "no crons parsed"
    assert set(crons) <= {"1", "7", "16", "31", "37", "46"}, f"unexpected cron minutes: {crons}"


def test_worker_slots_match_cron_map():
    cron_map = _cron_map()
    slots = _worker_slots()
    assert len(cron_map) == 15, f"CRON_MAP parse drift: {sorted(cron_map)}"
    assert slots == cron_map, (
        "workers/scheduler SLOTS desynced from run-show.yml CRON_MAP:\n"
        f"  worker-only/changed: { {k: v for k, v in slots.items() if cron_map.get(k) != v} }\n"
        f"  cron-map-only/changed: { {k: v for k, v in cron_map.items() if slots.get(k) != v} }"
    )


def test_worker_trigger_covers_all_slots():
    toml = (_ROOT / "workers" / "scheduler" / "wrangler.toml").read_text(encoding="utf-8")
    assert '"1,7,16,31,37,46 6-12 * * *"' in toml


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
        if day_filter == "monday":
            assert info.get("schedule") == "monday", (
                f"{show}: CRON_MAP is Monday-only but review_episodes "
                f"says {info.get('schedule')!r} — the audit will flag "
                "phantom missed episodes and dispatch off-schedule runs"
            )
        else:
            assert info.get("schedule") != "monday", (
                f"{show}: review_episodes says Monday-only but the cron "
                "has no Monday day-filter"
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
        if day_filter == "monday":
            assert limit >= 192, (
                f"{show}: Monday-only cadence but audit limit is {limit}h "
                "(<192h) — pages every week for an on-schedule feed"
            )
        else:
            assert limit <= 120, (
                f"{show}: daily cadence but audit limit is {limit}h "
                "(>120h) — a real outage would go unnoticed for days"
            )


def test_edition_dispatch_slot():
    """Nerra Daily's force-build must have an exact-time driver (Aug 2026
    land-by-6am-Pacific pass): the Worker dispatches nerra-daily.yml at
    12:07 UTC — a minute the existing cron trigger already covers — and
    the edition's force hour sits just before it. Deliberately NOT a
    SLOTS row (those parse as shows above)."""
    m = re.search(
        r"EDITION_DISPATCH = \{ hour: (\d+), minute: (\d+), "
        r'workflow: "([\w.-]+)" \}', _TS)
    assert m, "EDITION_DISPATCH missing from workers/scheduler"
    hour, minute, workflow = int(m.group(1)), int(m.group(2)), m.group(3)
    assert workflow == "nerra-daily.yml"
    # The wrangler cron ("1,7,16,31,37,46 6-12 * * *") must cover the slot.
    toml = (_ROOT / "workers" / "scheduler" / "wrangler.toml").read_text(
        encoding="utf-8")
    cron = re.search(r'crons = \["([^"]+)"\]', toml).group(1)
    minutes, hours = cron.split()[0], cron.split()[1]
    assert str(minute) in minutes.split(",")
    lo, hi = hours.split("-")
    assert int(lo) <= hour <= int(hi)
    # The force hour precedes the dispatch, so the dispatched run builds.
    build_src = (_ROOT / "scripts" / "build_daily_edition.py").read_text(
        encoding="utf-8")
    force = int(re.search(r"FORCE_BUILD_UTC_HOUR = (\d+)", build_src).group(1))
    assert force <= hour
    # 6am Pacific is 13:00 UTC in summer; force + ~30 min build must beat it.
    assert force <= 12, "force hour past 12 UTC cannot land by 6am PDT"
    # The GitHub sweep fallback for the force hour exists.
    edition_wf = (_ROOT / ".github" / "workflows" / "nerra-daily.yml"
                  ).read_text(encoding="utf-8")
    assert f"- cron: '23 {force} * * *'" in edition_wf


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
