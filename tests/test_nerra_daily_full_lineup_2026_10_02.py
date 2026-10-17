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
    def test_the_cohort_is_in_once_each(self):
        # Order is the operator's (re-set 2026-10-13, pinned in
        # tests/test_daily_edition.py); this guard checks membership.
        # Oct 17 2026: 25 — Vancouver keeps its local Pacific slot and left
        # the 7 AM Eastern edition (operator).
        assert len(SPEC.lineup) == len(set(SPEC.lineup)) == 25
        for slug in ("omni_view_world", "mag7", "ai_chips", "prediction_markets",
                     "collingwood", "longevity", "peptides"):
            assert slug in SPEC.lineup, slug
        assert "vancouver" not in SPEC.lineup

    def test_the_regional_desks_follow_omni_view(self):
        # 2026-10-13: Top World moved up to sixth (operator); Omni View and
        # the five regional desks close the edition in region order.
        i = SPEC.lineup.index("omni_view")
        assert SPEC.lineup.index("omni_view_world") < i
        assert SPEC.lineup[i + 1:i + 6] == (
            "omni_view_north_america", "omni_view_europe", "omni_view_asia_pacific",
            "omni_view_africa_mideast", "omni_view_latam")

    def test_the_friday_roster_matches_todays_slate(self):
        # 2026-10-02 was a Friday: Collingwood in, Longevity/Peptides and the
        # Monday weeklies out.
        exp = D.expected_slugs(SPEC, dt.date(2026, 10, 2))
        assert "collingwood" in exp
        assert not {"longevity", "peptides", "env_intel", "offshore_north", "dp_pod"} & set(exp)
        assert len(exp) == len(SPEC.lineup) - 5

    def test_the_personal_vocabulary_is_the_roster_plus_vancouver(self):
        # Oct 17 2026: Vancouver left the edition but members may still
        # choose it — it is the one extra beyond the roster.
        from engine.personal_edition import PERSONAL_EXTRA_SHOW_SLUGS, PERSONAL_SHOW_SLUGS
        assert PERSONAL_EXTRA_SHOW_SLUGS == ("vancouver",)
        assert set(PERSONAL_SHOW_SLUGS) == set(SPEC.lineup) | {"vancouver"}


# The ready gate's clock moved to a fixed 07:50 Pacific release on Oct 8
# 2026 and to 06:35 Eastern on Oct 17 2026; its tests live in
# tests/test_nerra_daily_8am_pacific_2026_10_08.py and
# tests/test_seven_am_eastern_2026_10_17.py.


class TestTheLinksBudget:
    def test_the_links_budget_scales_with_the_rundown(self):
        src = (ROOT / "scripts" / "build_daily_edition.py").read_text(encoding="utf-8")
        assert "max_tokens=max(2500, 900 + 140 * handoff_count)" in src
