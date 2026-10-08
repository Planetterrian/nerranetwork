"""Oct 8 2026 — Nerra Daily goes out at 8:00 AM Pacific, after every show.

Operator direction: publish the edition only after all the shows have
finished, at 8am Pacific. Before this the gate built the moment the last
expected show landed, or at a 13:00 UTC force hour (09:47-13:36 UTC across
Sep 23 - Oct 7). On Oct 7 it built at 13:36 UTC without Fascinating
Frontiers, First Principles and SpaceX, whose pushes were stranded in
recovery branches by a blog-post rebase conflict (fixed in
scripts/push_show_artifacts.sh, guarded in tests/test_push_show_artifacts.py).

What binds:
* ``ready_decision`` reads PACIFIC wall time: it waits until 07:50 PT
  whatever has landed (a build takes 6-7 minutes, so the edition is live
  by ~8:00), builds once every expected show is accounted for, holds for a
  straggler until 09:00 PT, then builds with whatever exists.
* The release does not move on the daylight-saving changes: 07:50 PT is
  14:50 UTC under PDT and 15:50 UTC under PST.
* Every lineup show's slot finishes well before the release.
* The Worker dispatch, its cron trigger and the GitHub fallbacks all agree
  with the engine's clock.
"""
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import daily_edition as D  # noqa: E402

SPEC = D.EDITIONS["en"]
UTC = dt.timezone.utc
PT = ZoneInfo("America/Los_Angeles")
SUMMER = dt.date(2026, 10, 8)    # PDT
WINTER = dt.date(2026, 11, 9)    # PST (DST ends Nov 1 2026)


def _pt(day: dt.date, hour: int, minute: int = 0) -> dt.datetime:
    return dt.datetime.combine(day, dt.time(hour, minute), tzinfo=PT).astimezone(UTC)


def _decide(now: dt.datetime, day: dt.date, *, landed: int, skipped: int = 0,
            expected: int = 23):
    return D.ready_decision(now_utc=now, target_date=day, expected=expected,
                            landed=landed, skipped=skipped, min_segments=4)


class TestTheReleaseClock:
    def test_constants(self):
        assert D.EDITION_TZ == "America/Los_Angeles"
        assert D.RELEASE_PACIFIC == (7, 50)
        assert D.HOLD_UNTIL_PACIFIC == (9, 0)

    def test_the_release_is_pacific_wall_time_in_both_seasons(self):
        rel, hold = D.release_window(SUMMER)
        assert (rel.hour, rel.minute, hold.hour) == (14, 50, 16)
        rel, hold = D.release_window(WINTER)
        assert (rel.hour, rel.minute, hold.hour) == (15, 50, 17)

    def test_the_old_force_hour_is_gone(self):
        src = (ROOT / "engine" / "daily_edition.py").read_text(encoding="utf-8")
        for name in ("FORCE_BUILD_UTC_HOUR", "FORCE_BUILD_MIN_SHARE",
                     "HARD_DEADLINE_UTC_HOUR"):
            assert f"{name} =" not in src, name


class TestReadyDecision:
    def test_a_complete_slate_still_waits_for_the_release(self):
        v, why = _decide(_pt(SUMMER, 5, 45), SUMMER, landed=22, skipped=1)
        assert v == "wait" and "07:50 Pacific release" in why

    def test_the_release_builds_a_complete_slate(self):
        for day in (SUMMER, WINTER):
            v, _ = _decide(_pt(day, 7, 50), day, landed=22, skipped=1)
            assert v == "build", day

    def test_oct_7_would_have_waited_instead_of_shipping_without_three_flagships(self):
        # 13:36 UTC on 2026-10-07 = 06:36 PDT: the old gate built here.
        day = dt.date(2026, 10, 7)
        v, _ = _decide(dt.datetime(2026, 10, 7, 13, 36, tzinfo=UTC), day, landed=20)
        assert v == "wait"

    def test_a_straggler_is_waited_for_inside_the_hold(self):
        v, why = _decide(_pt(SUMMER, 8, 20), SUMMER, landed=22)
        assert v == "wait" and "09:00 Pacific" in why and "22/23" in why

    def test_the_straggler_landing_builds_at_once(self):
        v, _ = _decide(_pt(SUMMER, 8, 31), SUMMER, landed=23)
        assert v == "build"

    def test_the_hold_ends_and_the_edition_builds_with_what_exists(self):
        for day in (SUMMER, WINTER):
            v, why = _decide(_pt(day, 9, 1), day, landed=21)
            assert v == "build" and "hold ended" in why, day

    def test_a_past_edition_date_builds(self):
        v, _ = _decide(dt.datetime(2026, 10, 9, 3, tzinfo=UTC), SUMMER, landed=10)
        assert v == "build"

    def test_skipped_shows_count_as_finished(self):
        v, _ = _decide(_pt(SUMMER, 7, 50), SUMMER, landed=20, skipped=3)
        assert v == "build"


class TestTheShowsFinishFirst:
    def test_every_lineup_slot_lands_well_before_the_summer_release(self):
        """The binding season is PDT, when 07:50 PT is 14:50 UTC. A run
        takes 25-45 minutes; every lineup slot must leave at least two
        hours of margin for a slow run or one re-dispatch."""
        wf = (ROOT / ".github" / "workflows" / "run-show.yml").read_text(encoding="utf-8")
        slots = []
        for m in re.finditer(r'"(\d+) (\d+) \* \* ([^"]*)":\s*\("([a-z_0-9]+)",', wf):
            minute, hour, slug = int(m.group(1)), int(m.group(2)), m.group(4)
            if slug in SPEC.lineup:
                slots.append((hour * 60 + minute, slug))
        assert slots, "no lineup slots parsed from CRON_MAP"
        latest, slug = max(slots)
        release, _ = D.release_window(SUMMER)
        release_min = release.hour * 60 + release.minute
        assert release_min - latest >= 120, (
            f"{slug} is dispatched at {latest // 60:02d}:{latest % 60:02d} UTC, "
            "less than two hours before the PDT release")


class TestTheClockAgreesEverywhere:
    TS = (ROOT / "workers" / "scheduler" / "src" / "index.ts").read_text(encoding="utf-8")
    TOML = (ROOT / "workers" / "scheduler" / "wrangler.toml").read_text(encoding="utf-8")
    WF = (ROOT / ".github" / "workflows" / "nerra-daily.yml").read_text(encoding="utf-8")

    def _worker_times(self):
        m = re.search(r'EDITION_DISPATCH = \{\s*tz: "([^"]+)",\s*times: \[(.*?)\] as', self.TS, re.S)
        assert m, "EDITION_DISPATCH missing or reshaped in workers/scheduler"
        times = [(int(h), int(mi)) for h, mi in re.findall(r"\[(\d+),\s*(\d+)\]", m.group(2))]
        return m.group(1), times

    def test_the_worker_dispatches_at_the_release_and_after_the_hold(self):
        tz, times = self._worker_times()
        assert tz == D.EDITION_TZ
        assert D.RELEASE_PACIFIC in times
        after_hold = [t for t in times if t > D.HOLD_UNTIL_PACIFIC]
        assert after_hold and min(after_hold) <= (D.HOLD_UNTIL_PACIFIC[0], 5)

    def test_the_worker_reads_pacific_wall_time_not_a_utc_hour(self):
        assert "pacificHourMinute(now)" in self.TS
        assert 'timeZone: EDITION_DISPATCH.tz' in self.TS
        assert "EDITION_DISPATCH.hour" not in self.TS

    def test_the_cron_trigger_fires_at_each_dispatch_in_both_seasons(self):
        crons = re.search(r"crons = \[(.*?)\]", self.TOML).group(1)
        triggers = re.findall(r'"([^"]+)"', crons)

        def fires(utc: dt.datetime) -> bool:
            for cron in triggers:
                minutes, hours = cron.split()[0], cron.split()[1]
                mins = {int(x) for x in minutes.split(",")}
                if "-" in hours:
                    lo, hi = (int(x) for x in hours.split("-"))
                    hrs = set(range(lo, hi + 1))
                else:
                    hrs = {int(x) for x in hours.split(",")}
                if utc.minute in mins and utc.hour in hrs:
                    return True
            return False

        _, times = self._worker_times()
        for day in (SUMMER, WINTER):
            for h, m in times:
                utc = _pt(day, h, m)
                assert fires(utc), f"no cron trigger at {utc:%H:%M} UTC ({h:02d}:{m:02d} PT, {day})"

    def test_the_github_fallbacks_cover_both_offsets(self):
        crons = re.findall(r"- cron: '(\d+) (\d+) \* \* \*'", self.WF)
        utc = {(int(h), int(m)) for m, h in crons}
        for day in (SUMMER, WINTER):
            rel, hold = D.release_window(day)
            assert any(rel <= dt.datetime.combine(day, dt.time(h, m), tzinfo=UTC) < hold
                       for h, m in utc), f"no fallback inside the release window on {day}"
            assert any(dt.datetime.combine(day, dt.time(h, m), tzinfo=UTC) >= hold
                       for h, m in utc), f"no fallback after the hold on {day}"
