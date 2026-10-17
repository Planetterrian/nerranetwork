"""Oct 17 2026 — Nerra Daily is out by 7:00 AM Eastern; the schedule runs on
Eastern wall time.

Operator decisions (binding):
* Nerra Daily is live by 7:00 AM New York (4:00 AM Pacific).
* Every show runs as late as it can for freshness; the edition shows start
  between 04:00 and 06:10 ET (Top World last, after the desks), and a show's
  audio lands ~15-20 minutes after its run starts.
* Vancouver Daily News keeps its local 05:15 Pacific slot (08:15 ET — ET
  minus PT is three hours all year) and is NOT in the edition.
* The schedule is anchored to Eastern time, so the 1 November clock change
  moves nothing.

What binds here:
* the release is 06:35 ET and the straggler hold ends at 06:50 ET, on either
  side of a DST change;
* every expected edition show's Worker slot starts by 06:10 ET;
* the Worker's Eastern SLOTS equal run-show.yml's CRON_MAP read at the EST
  offset (the GitHub fallbacks are UTC and cannot follow daylight saving);
* the Worker's one cron trigger fires at every slot, the edition dispatches
  and the X-queue dispatches under BOTH offsets.
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
from engine.scheduler_slots import SLOT_TZ, worker_slot_tz, worker_slots  # noqa: E402

SPEC = D.EDITIONS["en"]
UTC = dt.timezone.utc
ET = ZoneInfo("America/New_York")
TS = (ROOT / "workers" / "scheduler" / "src" / "index.ts").read_text(encoding="utf-8")
TOML = (ROOT / "workers" / "scheduler" / "wrangler.toml").read_text(encoding="utf-8")
WF = (ROOT / ".github" / "workflows" / "run-show.yml").read_text(encoding="utf-8")
EST_OFFSET_HOURS = 5

# 2026: DST ends Sunday 1 November. Saturday 31 October is EDT (UTC-4);
# Monday 2 November is EST (UTC-5).
BEFORE_DST_END = dt.date(2026, 10, 31)
AFTER_DST_END = dt.date(2026, 11, 2)


def _et(day: dt.date, hour: int, minute: int) -> dt.datetime:
    return dt.datetime.combine(day, dt.time(hour, minute), tzinfo=ET)


class TestTheReleaseClock:
    def test_release_at_0635_and_hold_until_0650_eastern(self):
        assert D.EDITION_TZ == "America/New_York"
        assert D.RELEASE_EASTERN == (6, 35)
        assert D.HOLD_UNTIL_EASTERN == (6, 50)
        for day in (BEFORE_DST_END, AFTER_DST_END):
            rel, hold = D.release_window(day)
            assert rel.astimezone(ET).time() == dt.time(6, 35), day
            assert hold.astimezone(ET).time() == dt.time(6, 50), day

    def test_the_release_stays_fixed_across_the_dst_boundary(self):
        rel_edt, hold_edt = D.release_window(BEFORE_DST_END)
        rel_est, hold_est = D.release_window(AFTER_DST_END)
        # Same Eastern wall time, one hour apart in UTC.
        assert (rel_edt.hour, rel_edt.minute) == (10, 35)
        assert (rel_est.hour, rel_est.minute) == (11, 35)
        assert (hold_edt.hour, hold_edt.minute) == (10, 50)
        assert (hold_est.hour, hold_est.minute) == (11, 50)

    def test_the_edition_is_live_by_seven_with_a_build_of_seven_minutes(self):
        build_minutes = 7
        for day in (BEFORE_DST_END, AFTER_DST_END):
            _rel, hold = D.release_window(day)
            live = hold + dt.timedelta(minutes=build_minutes)
            assert live.astimezone(ET).time() <= dt.time(7, 0), day

    def test_the_gate_text_names_the_eastern_clock(self):
        v, why = D.ready_decision(now_utc=_et(AFTER_DST_END, 6, 0).astimezone(UTC),
                                  target_date=AFTER_DST_END, expected=20, landed=20,
                                  skipped=0, min_segments=4)
        assert v == "wait" and "06:35 Eastern" in why
        v, why = D.ready_decision(now_utc=_et(AFTER_DST_END, 6, 50).astimezone(UTC),
                                  target_date=AFTER_DST_END, expected=20, landed=19,
                                  skipped=0, min_segments=4)
        assert v == "build" and "06:50 Eastern" in why


class TestTheEditionShowsStartBy0610:
    def test_every_expected_edition_show_starts_by_0610_et(self):
        slots = worker_slots()
        for day in (BEFORE_DST_END, AFTER_DST_END, dt.date(2026, 10, 19),
                    dt.date(2026, 10, 21), dt.date(2026, 10, 22), dt.date(2026, 10, 23)):
            for slug in D.expected_slugs(SPEC, day):
                assert slug in slots, f"{slug} is in the edition but has no Worker slot"
                h, m, _f = slots[slug]
                assert (h, m) <= (6, 10), f"{slug} starts {h:02d}:{m:02d} ET on {day}"

    def test_top_world_is_the_last_edition_slot_and_follows_every_desk(self):
        slots = worker_slots()
        edition = {s: slots[s][:2] for s in SPEC.lineup}
        assert max(edition.values()) == (6, 10) == edition["omni_view_world"]
        world = edition["omni_view_world"]
        for desk in ("omni_view_europe", "omni_view_asia_pacific",
                     "omni_view_africa_mideast", "omni_view_latam",
                     "omni_view_north_america"):
            h, m = edition[desk]
            # Top World's intake reads the desks' digests: 50-minute budget.
            assert (world[0] * 60 + world[1]) - (h * 60 + m) >= 50, desk


class TestVancouverKeepsItsPacificSlot:
    def test_vancouver_is_not_in_the_edition(self):
        assert "vancouver" not in SPEC.lineup
        for day in (BEFORE_DST_END, AFTER_DST_END):
            assert "vancouver" not in D.expected_slugs(SPEC, day)

    def test_vancouver_runs_at_0515_pacific_all_year(self):
        h, m, flt = worker_slots()["vancouver"]
        assert (h, m, flt) == (8, 15, None)
        pt = ZoneInfo("America/Los_Angeles")
        for day in (BEFORE_DST_END, AFTER_DST_END, dt.date(2027, 3, 15), dt.date(2027, 1, 4)):
            local = _et(day, h, m).astimezone(pt)
            assert (local.hour, local.minute) == (5, 15), day

    def test_members_can_still_choose_vancouver(self):
        from engine.personal_edition import PERSONAL_EXTRA_SHOW_SLUGS, PERSONAL_SHOW_SLUGS
        assert "vancouver" in PERSONAL_EXTRA_SHOW_SLUGS and "vancouver" in PERSONAL_SHOW_SLUGS


def _cron_map_eastern() -> dict:
    out = {}
    for m in re.finditer(
            r'"(\d+) (\d+) \* \* ([*\d])":\s*\("(\w+)",\s*(?:"(\w+)"|None)\)', WF):
        minute, hour, _dow, show, flt = m.groups()
        out[show] = (int(hour) - EST_OFFSET_HOURS, int(minute), flt)
    return out


class TestTheWorkerAndTheGateAgree:
    def test_worker_slots_are_on_the_eastern_clock(self):
        assert SLOT_TZ == "America/New_York" == worker_slot_tz(TS)

    def test_worker_et_slots_equal_cron_map_at_the_est_offset(self):
        assert worker_slots() == _cron_map_eastern()

    def test_slot_minutes_are_unique_multiples_of_five(self):
        times = [(h, m) for h, m, _f in worker_slots().values()]
        assert all(m % 5 == 0 for _h, m in times)
        assert len(times) == len(set(times))

    def test_every_slot_is_inside_one_utc_day_in_both_offsets(self):
        for slug, (h, m, _f) in worker_slots().items():
            for day in (BEFORE_DST_END, AFTER_DST_END):
                assert _et(day, h, m).astimezone(UTC).date() == day, slug

    def test_the_gate_weekday_matches_the_worker_weekday(self):
        """The Worker reads the Eastern weekday; the fallback cron's day-of-week
        field and the gate's UTC weekday must name the same day."""
        names = ["monday", "tuesday", "wednesday", "thursday", "friday",
                 "saturday", "sunday"]
        for m in re.finditer(r'"(\d+) (\d+) \* \* (\d)":\s*\("(\w+)",\s*"(\w+)"\)', WF):
            dow, flt = int(m.group(3)), m.group(5)
            assert names[(dow - 1) % 7] == flt, (m.group(4), dow, flt)


def _trigger_fires(utc: dt.datetime) -> bool:
    crons = re.search(r"^crons = \[(.*)\]", TOML, re.M).group(1)
    for cron in re.findall(r'"([^"]+)"', crons):
        minute, hour = cron.split()[:2]
        if minute.startswith("*/"):
            mins = set(range(0, 60, int(minute[2:])))
        elif minute == "*":
            mins = set(range(60))
        else:
            mins = {int(x) for x in minute.split(",")}
        hrs = set(range(24)) if hour == "*" else {int(x) for x in hour.split(",")}
        if utc.minute in mins and utc.hour in hrs:
            return True
    return False


class TestTheOneTriggerCoversEverything:
    def test_exactly_one_trigger(self):
        crons = re.findall(r"^crons = \[(.*)\]", TOML, re.M)
        assert crons and crons[0] == '"*/5 * * * *"'

    def test_every_slot_fires_in_both_offsets(self):
        for slug, (h, m, _f) in worker_slots().items():
            for day in (BEFORE_DST_END, AFTER_DST_END):
                utc = _et(day, h, m).astimezone(UTC)
                assert _trigger_fires(utc), f"{slug} {h:02d}:{m:02d} ET on {day}"

    def test_the_edition_dispatches_fire_in_both_offsets(self):
        m = re.search(r'EDITION_DISPATCH = \{\s*tz: "([^"]+)",\s*times: \[(.*?)\] as', TS, re.S)
        assert m and m.group(1) == "America/New_York"
        times = [(int(h), int(mi)) for h, mi in re.findall(r"\[(\d+),\s*(\d+)\]", m.group(2))]
        assert times == [(6, 35), (6, 50)]
        assert D.RELEASE_EASTERN in times and D.HOLD_UNTIL_EASTERN in times
        for day in (BEFORE_DST_END, AFTER_DST_END):
            for h, mi in times:
                assert _trigger_fires(_et(day, h, mi).astimezone(UTC)), (day, h, mi)

    def test_the_x_queue_dispatches_fire_in_both_offsets(self):
        # 7:05 AM to 10:05 PM Eastern at :05 and :35 — five minutes after
        # each half-hour X slot (the slot grid is 7:00 AM-10:00 PM ET).
        m = re.search(r'X_QUEUE_DISPATCH = \{.*?tz: "([^"]+)",\s*first: \[(\d+), (\d+)\].*?'
                      r'last: \[(\d+), (\d+)\].*?minutes: \[(\d+), (\d+)\]', TS, re.S)
        assert m, "X_QUEUE_DISPATCH reshaped"
        assert m.group(1) == "America/New_York"
        first = (int(m.group(2)), int(m.group(3)))
        last = (int(m.group(4)), int(m.group(5)))
        minutes = (int(m.group(6)), int(m.group(7)))
        assert (first, last, minutes) == ((7, 5), (22, 5), (5, 35))
        for day in (BEFORE_DST_END, AFTER_DST_END):
            t = _et(day, *first)
            while t <= _et(day, *last):
                assert _trigger_fires(t.astimezone(UTC)), t
                t += dt.timedelta(minutes=30)

    def test_no_slot_shares_an_edition_minute(self):
        times = {(6, 35), (6, 50)}
        assert not times & {(h, m) for h, m, _f in worker_slots().values()}


class TestTheFallbacks:
    def test_edition_fallbacks_cover_both_offsets(self):
        wf = (ROOT / ".github" / "workflows" / "nerra-daily.yml").read_text(encoding="utf-8")
        crons = {(int(h), int(m)) for m, h in re.findall(r"- cron: '(\d+) (\d+) \* \* \*'", wf)}
        for day in (BEFORE_DST_END, AFTER_DST_END):
            rel, hold = D.release_window(day)
            utc = [dt.datetime.combine(day, dt.time(h, m), tzinfo=UTC) for h, m in crons]
            assert any(rel <= t < hold for t in utc), day
            # A summer day still builds by about 7:05 ET if the Worker is down.
            assert any(hold <= t <= hold + dt.timedelta(minutes=15) for t in utc), day

    def test_run_show_fallbacks_are_the_est_equivalents(self):
        for slug, (h, m, flt) in worker_slots().items():
            dow = {"monday": "1", "wednesday": "3", "thursday": "4",
                   "friday": "5"}.get(flt or "", "*")
            assert f"- cron: '{m} {h + EST_OFFSET_HOURS} * * {dow}'" in WF, slug


class TestNoSurfaceStillSaysEightPacific:
    def test_registry_and_docs(self):
        import yaml

        meta = yaml.safe_load((ROOT / "shows" / "network_meta.yaml").read_text(encoding="utf-8"))
        nd = meta["nerra_daily"]
        assert nd["schedule"] == "Daily, 7am Eastern"
        for key, value in nd.items():
            if isinstance(value, str):
                assert "8am Pacific" not in value, key
        doc = (ROOT / "docs" / "nerra_daily.md").read_text(encoding="utf-8")
        assert "7:00 AM Eastern (4:00 AM Pacific)" in doc


class TestScaffoldUsesAnEasternSlot:
    def test_slot_derives_the_est_fallback_and_the_worker_row(self):
        from engine.show_scaffold import ScaffoldSpec, cron_for_et_slot, worker_slot_row
        assert cron_for_et_slot("05:45") == "45 10 * * *"
        assert cron_for_et_slot("04:10", "monday") == "10 9 * * 1"
        spec = ScaffoldSpec(show_name="Probe", slug="probe_show", description="d",
                            audience="a", slot_et="05:05", cron_day_filter="friday")
        assert spec.cron == "5 10 * * 5"
        assert worker_slot_row(spec).strip() == '[5, 5, "probe_show", "friday"],'

    def test_a_slot_off_the_five_minute_grid_is_refused(self):
        import pytest

        from engine.show_scaffold import cron_for_et_slot
        with pytest.raises(ValueError):
            cron_for_et_slot("05:07")
        with pytest.raises(ValueError):
            cron_for_et_slot("21:00")  # would cross into the next UTC day
