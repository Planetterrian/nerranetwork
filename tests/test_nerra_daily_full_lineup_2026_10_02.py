"""Oct 2 2026 — Nerra Daily carries every English show, and its ready gate
no longer ships a four-show edition on a bad morning.

What happened: the morning flagship wave was diverted into recovery
branches (claims.html rebase conflicts — a P0 fixed the same day), the
12:00 UTC force hour fired with four of nine expected shows on main, and
Ep043 shipped at 39 minutes while twenty English episodes published later
in the day. Operator direction: all new English shows in the edition.

What binds:
* ``EditionSpec.weekday_only`` names the non-Monday weeklies; the expected
  roster is weekday-aware for every weekly.
* ``ready_decision`` is pure: build when everything has landed or skipped;
  past the force hour (13:00, behind Vancouver's 12:16 slot) only at
  ``FORCE_BUILD_MIN_SHARE``; past the hard deadline with whatever exists.
* The Worker dispatch, the GitHub sweeps and the build script agree on the
  force hour; the links budget scales with the handoff count.
"""
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import daily_edition as D  # noqa: E402

SPEC = D.EDITIONS["en"]
UTC = dt.timezone.utc


def _at(hour: int, minute: int = 0, day: int = 2) -> dt.datetime:
    return dt.datetime(2026, 10, day, hour, minute, tzinfo=UTC)


class TestLineup:
    def test_the_cohort_is_in_and_the_lead_six_and_close_are_untouched(self):
        assert SPEC.lineup[:6] == ("spacex", "tesla", "fascinating_frontiers",
                                   "models_agents", "planetterrian", "omni_view")
        assert SPEC.lineup[-1] == "dp_pod"
        for slug in ("omni_view_world", "mag7", "ai_chips", "prediction_markets",
                     "vancouver", "collingwood", "longevity", "peptides"):
            assert slug in SPEC.lineup, slug

    def test_top_world_leads_the_desks_right_after_omni_view(self):
        i = SPEC.lineup.index("omni_view")
        assert SPEC.lineup[i + 1] == "omni_view_world"
        assert SPEC.lineup[i + 2:i + 7] == (
            "omni_view_north_america", "omni_view_europe", "omni_view_asia_pacific",
            "omni_view_africa_mideast", "omni_view_latam")

    def test_the_friday_roster_matches_todays_slate(self):
        # 2026-10-02 was a Friday: Collingwood in, Longevity/Peptides and the
        # Monday weeklies out.
        exp = D.expected_slugs(SPEC, dt.date(2026, 10, 2))
        assert "collingwood" in exp
        assert not {"longevity", "peptides", "env_intel", "offshore_north", "dp_pod"} & set(exp)
        assert len(exp) == len(SPEC.lineup) - 5

    def test_the_personal_vocabulary_is_the_roster(self):
        from engine.personal_edition import PERSONAL_EXTRA_SHOW_SLUGS, PERSONAL_SHOW_SLUGS
        assert PERSONAL_EXTRA_SHOW_SLUGS == ()
        assert set(PERSONAL_SHOW_SLUGS) == set(SPEC.lineup)


class TestReadyDecision:
    N = 23

    def test_everything_accounted_builds_at_any_hour(self):
        v, _ = D.ready_decision(now_utc=_at(9), target_date=dt.date(2026, 10, 2),
                                expected=self.N, landed=22, skipped=1, min_segments=4)
        assert v == "build"

    def test_before_the_force_hour_a_missing_show_waits(self):
        v, why = D.ready_decision(now_utc=_at(12, 50), target_date=dt.date(2026, 10, 2),
                                  expected=self.N, landed=22, skipped=0, min_segments=4)
        assert v == "wait" and "22/23" in why

    def test_todays_morning_would_have_waited_not_shipped_four_shows(self):
        # 13:10 UTC on 2026-10-02: 16 landed + FF skipped = 17/23 = 74%.
        v, why = D.ready_decision(now_utc=_at(13, 10), target_date=dt.date(2026, 10, 2),
                                  expected=self.N, landed=16, skipped=1, min_segments=4)
        assert v == "wait" and "74%" in why
        # ...and the four-show state the old gate shipped on is a wait too.
        v, _ = D.ready_decision(now_utc=_at(13, 10), target_date=dt.date(2026, 10, 2),
                                expected=self.N, landed=4, skipped=1, min_segments=4)
        assert v == "wait"

    def test_the_share_floor_builds_once_met(self):
        v, why = D.ready_decision(now_utc=_at(15, 30), target_date=dt.date(2026, 10, 2),
                                  expected=self.N, landed=18, skipped=1, min_segments=4)
        assert v == "build" and "83%" in why

    def test_the_hard_deadline_builds_with_whatever_exists(self):
        v, why = D.ready_decision(now_utc=_at(16), target_date=dt.date(2026, 10, 2),
                                  expected=self.N, landed=5, skipped=0, min_segments=4)
        assert v == "build" and "hard deadline" in why

    def test_a_past_edition_date_builds(self):
        v, _ = D.ready_decision(now_utc=_at(3, day=3), target_date=dt.date(2026, 10, 2),
                                expected=self.N, landed=10, skipped=0, min_segments=4)
        assert v == "build"

    def test_below_the_segment_floor_waits_even_past_the_force_hour(self):
        v, _ = D.ready_decision(now_utc=_at(13, 30), target_date=dt.date(2026, 10, 2),
                                expected=4, landed=3, skipped=0, min_segments=4)
        assert v == "wait"

    def test_constants(self):
        assert D.FORCE_BUILD_UTC_HOUR == 13
        assert 0.5 <= D.FORCE_BUILD_MIN_SHARE <= 0.9
        assert D.HARD_DEADLINE_UTC_HOUR > D.FORCE_BUILD_UTC_HOUR


class TestTheClockAgreesEverywhere:
    def test_build_script_reexports_the_engine_hour(self):
        import importlib
        mod = importlib.import_module("scripts.build_daily_edition") if (ROOT / "scripts" / "__init__.py").exists() else None
        src = (ROOT / "scripts" / "build_daily_edition.py").read_text(encoding="utf-8")
        assert "FORCE_BUILD_UTC_HOUR = _FORCE_BUILD_UTC_HOUR" in src
        assert "ready_decision(" in src
        if mod is not None:
            assert mod.FORCE_BUILD_UTC_HOUR == D.FORCE_BUILD_UTC_HOUR

    def test_the_force_hour_is_behind_the_last_expected_slot(self):
        wf = (ROOT / ".github" / "workflows" / "run-show.yml").read_text(encoding="utf-8")
        hours = []
        for m in re.finditer(r'"(\d+) (\d+) \* \* ([^"]*)":\s*\("([a-z_0-9]+)",', wf):
            minute, hour, _dow, slug = int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)
            if slug in SPEC.lineup:
                hours.append(hour + minute / 60)
        assert hours, "no lineup slots parsed from CRON_MAP"
        assert max(hours) < D.FORCE_BUILD_UTC_HOUR, (
            f"a lineup show is scheduled at {max(hours):.2f} UTC, past the force hour")

    def test_worker_dispatch_and_sweeps_sit_on_the_force_hour(self):
        ts = (ROOT / "workers" / "scheduler" / "src" / "index.ts").read_text(encoding="utf-8")
        m = re.search(r"EDITION_DISPATCH = \{ hour: (\d+), minute: (\d+)", ts)
        assert m and int(m.group(1)) == D.FORCE_BUILD_UTC_HOUR
        toml = (ROOT / "workers" / "scheduler" / "wrangler.toml").read_text(encoding="utf-8")
        cron = re.search(r'crons = \["([^"]+)"\]', toml).group(1)
        lo, hi = cron.split()[1].split("-")
        assert int(lo) <= D.FORCE_BUILD_UTC_HOUR <= int(hi)
        wf = (ROOT / ".github" / "workflows" / "nerra-daily.yml").read_text(encoding="utf-8")
        assert f"- cron: '23 {D.FORCE_BUILD_UTC_HOUR} * * *'" in wf
        assert f"- cron: '23 {D.HARD_DEADLINE_UTC_HOUR} * * *'" in wf

    def test_the_links_budget_scales_with_the_rundown(self):
        src = (ROOT / "scripts" / "build_daily_edition.py").read_text(encoding="utf-8")
        assert "max_tokens=max(2500, 900 + 140 * handoff_count)" in src
