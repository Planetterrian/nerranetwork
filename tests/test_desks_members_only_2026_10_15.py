"""Oct 15 2026: the Omni View regional desks are members-only.

Operator direction: the five desks publish only when a paying Nerra Personal
member has them in their lineup. They are the first shows gated through
engine.access (built Oct 13). Three things had to hold for that to be safe:

* An UNREADABLE demand skips the desk instead of producing it for nobody
  (``access.unknown_demand: skip``). On Oct 15 the gallery Worker answered 404
  on /api/admin/show-demand, so with the Oct 13 default the desks would have
  kept running every day into the private bucket.
* Top World News still reads the desks. A members episode's text sits in
  ``members/``; Top World takes headlines and original publisher URLs from it,
  as it did from the public file.
* A day no member carries a desk is the gate working: the audit stays quiet
  about ``no_member_demand`` and still warns about ``member_demand_unknown``.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from engine import access as A

ROOT = Path(__file__).resolve().parent.parent
DESKS = ("omni_view_europe", "omni_view_asia_pacific", "omni_view_africa_mideast",
         "omni_view_latam", "omni_view_north_america")


def _load(slug):
    from engine.config import load_config
    return load_config(ROOT / "shows" / f"{slug}.yaml")


class TestTheDesksAreMembersOnly:
    @pytest.mark.parametrize("slug", DESKS)
    def test_setting(self, slug):
        cfg = _load(slug)
        assert A.access_mode(cfg) == "members_only"
        assert A.min_members(cfg) == 1
        assert A.unknown_demand(cfg) == "skip"
        assert not A.is_public_on(cfg, dt.date(2026, 10, 19))

    @pytest.mark.parametrize("slug", DESKS)
    def test_no_public_distribution_left_on(self, slug):
        cfg = _load(slug)
        assert cfg.newsletter.enabled is False
        assert cfg.youtube.enabled is False
        assert cfg.publishing.x_enabled is False
        assert not getattr(cfg.multilingual, "enabled", False)

    def test_members_can_select_every_desk(self):
        from engine.personal_edition import PERSONAL_SHOW_SLUGS
        ts = (ROOT / "workers/gallery/src/personal.ts").read_text(encoding="utf-8")
        for slug in DESKS:
            assert slug in PERSONAL_SHOW_SLUGS, slug
            assert f'"{slug}"' in ts, slug

    def test_top_world_stays_public(self):
        assert A.access_mode(_load("omni_view_world")) == "public"

    def test_no_show_plugs_a_desk_on_air(self):
        from engine.network_promo import ENGLISH_ORDER, pick_featured_show
        for slug in ENGLISH_ORDER:
            for i in range(40):
                assert pick_featured_show(slug, dt.date(2026, 10, 15) + dt.timedelta(days=i)) not in DESKS


def _cfg(unknown="produce", minimum=1):
    return SimpleNamespace(slug="x", access=SimpleNamespace(
        mode="members_only", public_weekday=0, min_members=minimum, unknown_demand=unknown))


class TestUnknownDemand:
    def test_default_is_the_oct_13_behaviour(self):
        assert A.unknown_demand(SimpleNamespace(access=SimpleNamespace())) == "produce"
        d = A.demand_decision("x", None, 1)
        assert d.run and d.reason == "demand_unknown"

    def test_skip_closes_the_gate_when_demand_is_unknown(self):
        d = A.demand_decision("x", None, 1, unknown="skip")
        assert not d.run and d.reason == "demand_unknown_skip"

    def test_known_demand_decides_either_way(self):
        assert A.demand_decision("x", {"x": 1}, 1, unknown="skip").run
        assert not A.demand_decision("x", {}, 1, unknown="skip").run
        assert A.demand_decision("x", {}, 1, unknown="skip").reason == "no_member_demand"

    def test_min_members_zero_still_overrides(self):
        assert A.demand_decision("x", None, 0, unknown="skip").run

    def test_a_typo_stops_the_run(self):
        with pytest.raises(ValueError):
            A.unknown_demand(_cfg(unknown="skipp"))

    def test_config_reads_the_field(self):
        from engine.config import AccessConfig
        assert AccessConfig().unknown_demand == "produce"

    def test_run_show_passes_it_and_skips_with_its_own_reason(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "unknown=_access.unknown_demand(config)" in src
        block = src[src.index('if _decision.reason == "demand_unknown_skip":'):][:900]
        assert '"member_demand_unknown"' in block


def _top_world():
    spec = importlib.util.spec_from_file_location(
        "ovw_hook", ROOT / "shows/hooks/omni_view_world.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DESK_DIGEST = """# Omni View Europe
> **Brussels agrees the budget.**

### Lead
**EU leaders agree the seven-year budget: Reuters**
The deal was struck after two days. Source: https://www.reuters.com/world/europe/eu-budget-2026-10-15/

### Across the Region
1. **Poland opens a new rail line: Notes from Poland**
The line links Warsaw and Gdansk. Source: https://notesfrompoland.com/2026/10/15/rail/
"""


class TestTopWorldReadsMembersDigests:
    def test_a_members_episode_is_read(self, tmp_path):
        mod = _top_world()
        desk = next(d for d in mod.DESKS if d.slug == "omni_view_europe")
        members = tmp_path / "digests" / desk.slug / "members"
        members.mkdir(parents=True)
        (members / f"{desk.prefix}_Ep030_20261015.md").write_text(DESK_DIGEST, encoding="utf-8")
        got = mod.todays_desk_digests(tmp_path, dt.date(2026, 10, 15))
        assert [d.slug for d, _ in got] == ["omni_view_europe"]
        payload = mod.build_payload(tmp_path, dt.date(2026, 10, 15))
        assert payload["metrics"]["desks_live_at_publish"] == 1
        assert all("reuters.com" in a["url"] or "notesfrompoland" in a["url"]
                   for a in payload["articles"])

    def test_a_skipped_desk_is_absent(self, tmp_path):
        mod = _top_world()
        desk = next(d for d in mod.DESKS if d.slug == "omni_view_europe")
        ddir = tmp_path / "digests" / desk.slug
        (ddir / "members").mkdir(parents=True)
        (ddir / ".skip_20261015.json").write_text('{"reason": "no_member_demand"}', encoding="utf-8")
        (ddir / "members" / f"{desk.prefix}_Ep030_20261015.md").write_text(DESK_DIGEST, encoding="utf-8")
        assert mod.todays_desk_digests(tmp_path, dt.date(2026, 10, 15)) == []

    def test_the_intake_line_does_not_say_published(self):
        # Oct 17 2026: a day with no desk edition carries no intake line at
        # all (the sentence told public readers about a members-only show).
        line = _top_world().intake_line(0, 5)
        assert line == "" and "published" not in line


class TestTheAuditReadsTheGateAsWorking:
    def _issues(self, tmp_path, monkeypatch, reason):
        import review_episodes as R
        info = R.SHOW_REGISTRY["omni_view_europe"]
        out = tmp_path / info["output_dir"]
        out.mkdir(parents=True)
        day = dt.date(2026, 10, 15)
        (out / f".skip_{day:%Y%m%d}.json").write_text(
            '{"reason": "%s", "detail": "x"}' % reason, encoding="utf-8")
        monkeypatch.setattr(R, "PROJECT_ROOT", tmp_path)
        return R.check_missed_episodes(day, [], show_filter="omni_view_europe")

    def test_no_member_demand_is_not_an_issue(self, tmp_path, monkeypatch):
        assert self._issues(tmp_path, monkeypatch, "no_member_demand") == []

    def test_unknown_demand_still_warns(self, tmp_path, monkeypatch):
        issues = self._issues(tmp_path, monkeypatch, "member_demand_unknown")
        assert [i.severity for i in issues] == ["warning"]
        assert "member_demand_unknown" in issues[0].title
