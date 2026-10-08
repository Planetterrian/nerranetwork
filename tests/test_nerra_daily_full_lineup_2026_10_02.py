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
* (The 13:00 UTC force hour this pass introduced was replaced on Oct 8
  2026 by a fixed 07:50 Pacific release — see
  tests/test_nerra_daily_8am_pacific_2026_10_08.py.)
* The links budget scales with the handoff count.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import daily_edition as D  # noqa: E402

SPEC = D.EDITIONS["en"]


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


# The ready gate's clock moved to a fixed 07:50 Pacific release on Oct 8
# 2026; its tests live in tests/test_nerra_daily_8am_pacific_2026_10_08.py.


class TestTheLinksBudget:
    def test_the_links_budget_scales_with_the_rundown(self):
        src = (ROOT / "scripts" / "build_daily_edition.py").read_text(encoding="utf-8")
        assert "max_tokens=max(2500, 900 + 140 * handoff_count)" in src
