"""Oct 8 2026 — Nerra Daily goes out at 8:00 AM Pacific, after every show.

Operator direction: publish the edition only after all the shows have
finished, at 8am Pacific. Before this the gate built the moment the last
expected show landed, or at a 13:00 UTC force hour (09:47-13:36 UTC across
Sep 23 - Oct 7). On Oct 7 it built at 13:36 UTC without Fascinating
Frontiers, First Principles and SpaceX, whose pushes were stranded in
recovery branches by a blog-post rebase conflict (fixed in
scripts/push_show_artifacts.sh, guarded in tests/test_push_show_artifacts.py).

What binds (Oct 17 2026: the release moved to 7:00 AM EASTERN — the same
rules on the Eastern clock; the new guards are in
tests/test_seven_am_eastern_2026_10_17.py):
* ``ready_decision`` reads EASTERN wall time: it waits until 06:35 ET
  whatever has landed (a build takes 6-7 minutes, so the edition is live
  by ~6:45), builds once every expected show is accounted for, holds for a
  straggler until 06:50 ET, then builds with whatever exists.
* The release does not move on the daylight-saving changes: 06:35 ET is
  10:35 UTC under EDT and 11:35 UTC under EST.
* Every lineup show's slot starts before the release.
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
ET = ZoneInfo("America/New_York")
SUMMER = dt.date(2026, 10, 8)    # EDT
WINTER = dt.date(2026, 11, 9)    # EST (DST ends Nov 1 2026)


def _et(day: dt.date, hour: int, minute: int = 0) -> dt.datetime:
    return dt.datetime.combine(day, dt.time(hour, minute), tzinfo=ET).astimezone(UTC)


def _decide(now: dt.datetime, day: dt.date, *, landed: int, skipped: int = 0,
            expected: int = 23):
    return D.ready_decision(now_utc=now, target_date=day, expected=expected,
                            landed=landed, skipped=skipped, min_segments=4)


class TestTheReleaseClock:
    def test_constants(self):
        # Oct 17 2026: Eastern (was America/Los_Angeles, 07:50 / 09:00).
        assert D.EDITION_TZ == "America/New_York"
        assert D.RELEASE_EASTERN == (6, 35)
        assert D.HOLD_UNTIL_EASTERN == (6, 50)
        src = (ROOT / "engine" / "daily_edition.py").read_text(encoding="utf-8")
        assert "RELEASE_PACIFIC" not in src and "HOLD_UNTIL_PACIFIC" not in src

    def test_the_release_is_eastern_wall_time_in_both_seasons(self):
        rel, hold = D.release_window(SUMMER)
        assert (rel.hour, rel.minute, hold.hour, hold.minute) == (10, 35, 10, 50)
        rel, hold = D.release_window(WINTER)
        assert (rel.hour, rel.minute, hold.hour, hold.minute) == (11, 35, 11, 50)

    def test_the_old_force_hour_is_gone(self):
        src = (ROOT / "engine" / "daily_edition.py").read_text(encoding="utf-8")
        for name in ("FORCE_BUILD_UTC_HOUR", "FORCE_BUILD_MIN_SHARE",
                     "HARD_DEADLINE_UTC_HOUR"):
            assert f"{name} =" not in src, name


class TestReadyDecision:
    def test_a_complete_slate_still_waits_for_the_release(self):
        v, why = _decide(_et(SUMMER, 6, 20), SUMMER, landed=22, skipped=1)
        assert v == "wait" and "06:35 Eastern release" in why

    def test_the_release_builds_a_complete_slate(self):
        for day in (SUMMER, WINTER):
            v, _ = _decide(_et(day, 6, 35), day, landed=22, skipped=1)
            assert v == "build", day

    def test_oct_7_would_have_waited_instead_of_shipping_without_three_flagships(self):
        # The old gate built the moment the last show landed; on the Eastern
        # clock an incomplete slate before 06:35 ET (10:35 UTC under EDT)
        # still waits.
        day = dt.date(2026, 10, 7)
        v, _ = _decide(dt.datetime(2026, 10, 7, 10, 20, tzinfo=UTC), day, landed=20)
        assert v == "wait"

    def test_a_straggler_is_waited_for_inside_the_hold(self):
        v, why = _decide(_et(SUMMER, 6, 40), SUMMER, landed=22)
        assert v == "wait" and "06:50 Eastern" in why and "22/23" in why

    def test_the_straggler_landing_builds_at_once(self):
        v, _ = _decide(_et(SUMMER, 6, 44), SUMMER, landed=23)
        assert v == "build"

    def test_the_hold_ends_and_the_edition_builds_with_what_exists(self):
        for day in (SUMMER, WINTER):
            v, why = _decide(_et(day, 6, 50), day, landed=21)
            assert v == "build" and "hold ended" in why, day

    def test_a_past_edition_date_builds(self):
        v, _ = _decide(dt.datetime(2026, 10, 9, 3, tzinfo=UTC), SUMMER, landed=10)
        assert v == "build"

    def test_skipped_shows_count_as_finished(self):
        v, _ = _decide(_et(SUMMER, 6, 35), SUMMER, landed=20, skipped=3)
        assert v == "build"


class TestTheShowsFinishFirst:
    def test_every_lineup_slot_starts_before_the_release(self):
        """Oct 17 2026: the slots are Eastern wall time (the scheduler
        Worker's SLOTS), so the margin is the same in both seasons. The
        audio lands ~15-20 minutes after a run starts (shows publish their
        episode before rendering video), so every lineup slot must start at
        least 25 minutes before the 06:35 ET release. Was two hours on the
        8am-Pacific release."""
        from engine.scheduler_slots import worker_slots
        slots = [(h * 60 + m, slug) for slug, (h, m, _f) in worker_slots().items()
                 if slug in SPEC.lineup]
        assert len(slots) == len(SPEC.lineup), "a lineup show has no Worker slot"
        latest, slug = max(slots)
        release_min = D.RELEASE_EASTERN[0] * 60 + D.RELEASE_EASTERN[1]
        assert release_min - latest >= 25, (
            f"{slug} is dispatched at {latest // 60:02d}:{latest % 60:02d} ET, "
            "less than 25 minutes before the release")


class TestTheClockAgreesEverywhere:
    TS = (ROOT / "workers" / "scheduler" / "src" / "index.ts").read_text(encoding="utf-8")
    TOML = (ROOT / "workers" / "scheduler" / "wrangler.toml").read_text(encoding="utf-8")
    WF = (ROOT / ".github" / "workflows" / "nerra-daily.yml").read_text(encoding="utf-8")

    def _worker_times(self):
        m = re.search(r'EDITION_DISPATCH = \{\s*tz: "([^"]+)",\s*times: \[(.*?)\] as', self.TS, re.S)
        assert m, "EDITION_DISPATCH missing or reshaped in workers/scheduler"
        times = [(int(h), int(mi)) for h, mi in re.findall(r"\[(\d+),\s*(\d+)\]", m.group(2))]
        return m.group(1), times

    def test_the_worker_dispatches_at_the_release_and_at_the_hold(self):
        tz, times = self._worker_times()
        assert tz == D.EDITION_TZ
        assert D.RELEASE_EASTERN in times
        at_or_after_hold = [t for t in times if t >= D.HOLD_UNTIL_EASTERN]
        assert at_or_after_hold and min(at_or_after_hold) <= (
            D.HOLD_UNTIL_EASTERN[0], D.HOLD_UNTIL_EASTERN[1] + 5)

    def test_the_worker_reads_eastern_wall_time_not_a_utc_hour(self):
        # Oct 17 2026: one wall clock for slots, edition and X queue.
        assert 'const SLOT_TZ = "America/New_York"' in self.TS
        assert "wallClock(now)" in self.TS
        assert "timeZone: tz" in self.TS
        assert "pacificHourMinute" not in self.TS
        assert "EDITION_DISPATCH.hour" not in self.TS

    def test_the_cron_trigger_fires_at_each_dispatch_in_both_seasons(self):
        crons = re.search(r"crons = \[(.*?)\]", self.TOML).group(1)
        triggers = re.findall(r'"([^"]+)"', crons)

        def fires(utc: dt.datetime) -> bool:
            for cron in triggers:
                minutes, hours = cron.split()[0], cron.split()[1]
                if minutes.startswith("*/"):  # Oct 17 2026: every five minutes
                    mins = set(range(0, 60, int(minutes[2:])))
                else:
                    mins = {int(x) for x in minutes.split(",")}
                if hours == "*":  # Oct 11 2026: every hour (X queue)
                    hrs = set(range(24))
                elif "-" in hours:
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
                utc = _et(day, h, m)
                assert fires(utc), f"no cron trigger at {utc:%H:%M} UTC ({h:02d}:{m:02d} ET, {day})"

    def test_the_github_fallbacks_cover_both_offsets(self):
        crons = re.findall(r"- cron: '(\d+) (\d+) \* \* \*'", self.WF)
        utc = {(int(h), int(m)) for m, h in crons}
        for day in (SUMMER, WINTER):
            rel, hold = D.release_window(day)
            assert any(rel <= dt.datetime.combine(day, dt.time(h, m), tzinfo=UTC) < hold
                       for h, m in utc), f"no fallback inside the release window on {day}"
            assert any(dt.datetime.combine(day, dt.time(h, m), tzinfo=UTC) >= hold
                       for h, m in utc), f"no fallback after the hold on {day}"
