"""Guards for the Nov 24 2026 review-loop pass.

The review loop produced findings faster than anything acted on them:
102 of 103 due register readouts were overdue, the review rotation spent its
week on shows with a handful of downloads while SpaceX and Tesla waited, the
daily audit flagged 68% of episodes, and SpaceX shipped three episodes
without its share price that no check named. This pass:

* ``scripts/readout_register.py`` scores every metric entry that states a
  ``target_rule`` (hit / miss / unmeasured), and lists the misses;
* ``scripts/pick_review_target.py`` ranks targets by audience share x
  staleness x problems;
* ``scripts/check_show_contracts.py`` + ``shows/contracts/must_haves.yaml``
  check every published episode for its must-haves in the Daily Audit and
  list boolean counter flips;
* ``scripts/dispatch_quality_reviews.py`` dispatches on a must-have miss, or
  on criticals only when a show is above its own critical rate.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# 1. Readouts are scored
# ---------------------------------------------------------------------------

class TestReadoutVerdicts:
    rr = _load("readout_register")

    @pytest.mark.parametrize("rule,live,want", [
        (">= 0.9", 1.0, "hit"),
        (">= 0.9", 0.5, "miss"),
        ("<= 0.22", 0.34, "miss"),
        ("<= 0.22", 0.2, "hit"),
        ("> 35", 19.5, "miss"),
        ("> 2.2", None, "unmeasured"),   # null is unmeasured, never a miss
        ("> 2.2", True, "unmeasured"),   # a bool is not a number
        (None, 3.0, "no_rule"),
        ("above 2", 3.0, "bad_rule"),
    ])
    def test_verdict(self, rule, live, want):
        assert self.rr.verdict_for(rule, live) == want

    def test_rows_carry_verdicts_and_misses_are_listed(self):
        entries = [
            {"id": "a", "status": "reading", "shipped": "2026-10-01", "readout": "2026-10-10",
             "metric": "m1", "target_rule": ">= 0.9"},
            {"id": "b", "status": "reading", "shipped": "2026-10-01", "readout": "2026-10-10",
             "metric": "m2", "target_rule": "<= 0.2"},
            {"id": "c", "status": "reading", "shipped": "2026-09-01", "readout": "2026-09-10"},
        ]
        doc = self.rr.build_readouts(entries, {"m1": 1.0, "m2": 0.5}, dt.date(2026, 11, 24))
        verdicts = {r["id"]: r["verdict"] for r in doc["with_metric"]}
        assert verdicts == {"a": "hit", "b": "miss"}
        assert doc["misses"] == ["b"] and doc["hits"] == ["a"]
        assert doc["stale_no_path"] == ["c"]

    def test_a_new_metric_entry_must_state_a_rule(self):
        e = {"id": "x", "shipped": "2026-11-24", "metric": "m"}
        assert "target_rule" in self.rr.target_rule_defect(e)
        assert self.rr.target_rule_defect(dict(e, shipped="2026-11-01")) is None
        assert self.rr.target_rule_defect(dict(e, target_rule=">= 1")) is None
        assert self.rr.target_rule_defect({"id": "y", "target_rule": ">= 1"})

    def test_the_committed_register_has_no_rule_defects(self):
        entries = self.rr.load_register(ROOT / "docs" / "experiments.yaml")
        defects = [(e["id"], self.rr.target_rule_defect(e)) for e in entries
                   if self.rr.target_rule_defect(e)]
        assert defects == []

    def test_backfilled_rules_restate_the_entry_own_number(self):
        # A rule is copied from the entry's own target text, never invented.
        entries = {e["id"]: e for e in self.rr.load_register(ROOT / "docs" / "experiments.yaml")}
        ruled = {i: e for i, e in entries.items() if e.get("target_rule")}
        assert len(ruled) >= 7
        for i, e in ruled.items():
            number = e["target_rule"].split()[-1]
            assert number in str(e.get("target")), i


# ---------------------------------------------------------------------------
# 2. Review targets are ranked by audience and problems
# ---------------------------------------------------------------------------

class TestRankedRotation:
    pick = _load("pick_review_target")
    TODAY = dt.date(2026, 11, 24)

    def test_the_big_show_outranks_the_small_one_at_equal_age(self):
        dates = {"big": "2026-11-03", "small": "2026-11-03"}
        signals = {"share": {"big": 0.4, "small": 0.001}}
        ranked = self.pick.rank_targets(dates, signals, self.TODAY)
        assert [r[0] for r in ranked] == ["big", "small"]

    def test_a_falling_score_raises_priority(self):
        dates = {"steady": "2026-11-03", "falling": "2026-11-03"}
        signals = {"share": {"steady": 0.1, "falling": 0.1},
                   "scores": {"steady": [7.0] * 28, "falling": [8.0] * 21 + [6.0] * 7}}
        assert self.pick.rank_targets(dates, signals, self.TODAY)[0][0] == "falling"

    def test_contract_misses_raise_priority(self):
        dates = {"a": "2026-11-03", "b": "2026-11-03"}
        signals = {"share": {"a": 0.1, "b": 0.1}, "contract_misses": {"b": 3}}
        assert self.pick.rank_targets(dates, signals, self.TODAY)[0][0] == "b"

    def test_a_recent_review_waits_and_a_long_gap_goes_first(self):
        dates = {"fresh": "2026-11-20", "huge": "2026-11-01",
                 "forgotten": (self.TODAY - dt.timedelta(days=self.pick.MAX_GAP_DAYS)).isoformat()}
        signals = {"share": {"fresh": 0.9, "huge": 0.5, "forgotten": 0.0}}
        ranked = [r[0] for r in self.pick.rank_targets(dates, signals, self.TODAY)]
        assert "fresh" not in ranked
        assert ranked[0] == "forgotten"

    def test_no_signals_is_neutral_not_zero(self):
        ranked = self.pick.rank_targets({"a": "2026-11-01"}, {}, self.TODAY)
        assert ranked and ranked[0][1] > 0

    def test_live_signals_load_from_the_committed_files(self):
        signals = self.pick.load_signals(ROOT)
        assert "share" in signals and "scores" in signals

    def test_the_workflow_logs_the_ranking(self):
        wf = (ROOT / ".github" / "workflows" / "show-review.yml").read_text(encoding="utf-8")
        assert "pick_review_target.py --explain" in wf


# ---------------------------------------------------------------------------
# 4. Must-haves
# ---------------------------------------------------------------------------

SPCX_OK = "### Market Watch\nSPCX is at $141.70, +3.2% vs the previous close.\n"
SPCX_MISSING = "### Market Watch\nNo SPCX quote was provided in the briefing.\n"


class TestContracts:
    cc = _load("check_show_contracts")

    def test_the_contracts_file_loads(self):
        contracts = self.cc.load_contracts()
        assert {"spacex", "tesla", "modern_investing"} <= set(contracts)

    def test_every_contract_names_a_registered_show(self):
        from review_episodes import SHOW_REGISTRY
        assert set(self.cc.load_contracts()) <= set(SHOW_REGISTRY)

    def test_the_contracts_file_is_not_a_show_config(self):
        # A dozen loaders glob shows/*.yaml as show configs.
        assert not (ROOT / "shows" / "must_haves.yaml").exists()
        assert all(p.parent.name == "shows" for p in (ROOT / "shows").glob("*.yaml"))
        assert (ROOT / "shows" / "contracts" / "must_haves.yaml").exists()

    def test_spacex_share_price_line(self):
        checks = self.cc.load_contracts()["spacex"]
        assert self.cc.check_text(checks, SPCX_OK, {})[0]["ok"] is True
        assert self.cc.check_text(checks, SPCX_MISSING, {})[0]["ok"] is False
        # The Ep169 shape: no Market Watch line at all.
        assert self.cc.check_text(checks, "### Market Watch\n\n", {})[0]["ok"] is False

    def test_a_deep_dive_special_is_skipped(self):
        checks = self.cc.load_contracts()["spacex"]
        res = self.cc.check_text(checks, SPCX_MISSING, {"deep_dive_mode": True})
        assert res[0]["ok"] is None and "deep_dive_mode" in res[0]["skipped"]

    def test_a_bad_file_raises(self, tmp_path):
        bad = tmp_path / "c.yaml"
        bad.write_text("spacex:\n  - id: x\n    what: y\n    pattern: '('\n")
        with pytest.raises(ValueError):
            self.cc.load_contracts(bad)
        bad.write_text("spacex:\n  - id: x\n    what: y\n    pattern: 'a'\n    severity: loud\n")
        with pytest.raises(ValueError):
            self.cc.load_contracts(bad)

    def test_counter_flips(self):
        prior = [{"hook_failed": False, "fired": True}] * 10
        flips = self.cc.counter_flips(prior, {"hook_failed": True, "fired": True})
        assert [f["counter"] for f in flips] == ["hook_failed"]
        assert self.cc.counter_flips(prior[:3], {"hook_failed": True}) == []
        mixed = [{"x": True}] * 5 + [{"x": False}] * 5
        assert self.cc.counter_flips(mixed, {"x": True}) == []

    def test_report_pages_today_and_counts_14_days(self, tmp_path):
        out = tmp_path / "digests" / "spacex"
        out.mkdir(parents=True)
        for ep, day, text in [(1, "20261119", SPCX_OK), (2, "20261120", SPCX_MISSING),
                              (3, "20261121", SPCX_MISSING)]:
            (out / f"SpaceX_Daily_Ep{ep}_{day}.md").write_text(text)
            (out / f"SpaceX_Daily_Ep{ep}_{day}_reader.txt").write_text("x")
        members = out / "members"
        members.mkdir()
        (members / "SpaceX_Daily_Ep4_20261121.md").write_text(SPCX_MISSING)
        registry = {"spacex": {"output_dir": "digests/spacex", "prefix": "SpaceX_Daily"}}
        doc = self.cc.build_report(tmp_path, self.cc.load_contracts(), registry,
                                   dt.date(2026, 11, 21))
        assert doc["shows"]["spacex"]["misses_14d"] == 2
        assert [e["episode"] for e in doc["shows"]["spacex"]["today"]] == [3]
        assert len(doc["page"]) == 1 and "Ep3" in doc["page"][0]

    def test_the_daily_audit_runs_it_strict_and_commits_it(self):
        wf = (ROOT / ".github" / "workflows" / "daily-audit.yml").read_text(encoding="utf-8")
        assert "check_show_contracts.py --strict --out api/show_contracts.json" in wf
        persist = wf.split("Persist Audit Artifacts", 1)[1]
        assert "api/show_contracts.json" in persist
        # It runs before the dispatcher that reads it.
        assert wf.index("check_show_contracts.py") < wf.index("dispatch_quality_reviews.py")

    def test_the_review_snapshot_prints_them(self):
        src = (ROOT / "scripts" / "review_snapshot.py").read_text(encoding="utf-8")
        assert "## Must-haves and audit trend" in src


# ---------------------------------------------------------------------------
# 5. Dispatch on change, not presence
# ---------------------------------------------------------------------------

def _rows(show, flags):
    return [{"show": show, "date": f"2026-10-{i + 1:02d}", "episode": i,
             "critical": int(f)} for i, f in enumerate(flags)]


class TestDispatchBaseline:
    dq = _load("dispatch_quality_reviews")
    TODAY = {"episodes": [{"show": "noisy", "critical": 2}, {"show": "rising", "critical": 1}]}

    def test_a_show_always_flagged_is_not_news(self):
        history = _rows("noisy", [1] * 35) + _rows("rising", [0] * 28 + [1] * 7)
        assert self.dq.pick_review_candidate(self.TODAY, history) == "rising"

    def test_no_rise_means_no_dispatch(self):
        history = _rows("noisy", [1] * 35) + _rows("rising", [1] * 35)
        assert self.dq.pick_review_candidate(self.TODAY, history) is None

    def test_a_short_history_keeps_the_old_rule(self):
        history = _rows("noisy", [1] * 8)
        assert self.dq.pick_review_candidate(
            {"episodes": [{"show": "noisy", "critical": 2}]}, history) == "noisy"

    def test_a_must_have_miss_wins(self):
        contracts = {"shows": {"spacex": {"today": [{"episode": 169, "checks": [
            {"id": "share_price", "ok": False, "severity": "page"}]}]}}}
        history = _rows("noisy", [0] * 28 + [1] * 7)
        assert self.dq.pick_review_candidate(self.TODAY, history, contracts) == "spacex"

    def test_a_warn_miss_does_not_dispatch(self):
        contracts = {"shows": {"models_agents": {"today": [{"episode": 1, "checks": [
            {"id": "under_the_hood", "ok": False, "severity": "warn"}]}]}}}
        assert self.dq.contract_page_shows(contracts) == {}


def test_claude_md_names_the_pass():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "test_review_loop_automation_2026_11_24.py" in text
    assert re.search(r"target_rule", text)
