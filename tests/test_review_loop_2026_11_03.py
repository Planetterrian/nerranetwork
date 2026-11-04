"""The review loop closes (Nov 3 2026, efficiency-3 + efficiency-6).

The network wrote more experiments and predictions than it read: 74 register
entries past their readout with nothing reading them, 70 of the network
ledger's 94 predictions pending because the Grok agent could not reach the
``network`` target (every slate review's ledger write advanced it), seven
closed review PRs recorded nowhere, and the model-upgrade playbook's latency
instrument run by no workflow while SpaceX's script stage read p95 over the
request timeout. These guards pin the machine on the reading side:

* ``scripts/readout_register.py`` — the nightly register readout and its
  ``--strict`` rule; the CI readability rule it shares with
  ``tests/test_dashboard_growth.py``;
* ``scripts/run_show_review.gather_network_context`` carries the network
  ledger's pending predictions in full;
* ``scripts/review_pr_outcomes.py`` — one comment per unlabelled closed
  review PR, a text-splice into ``do_not_retry`` on ``rejected``, bytes
  elsewhere untouched;
* ``scripts/model_trial_report.py`` — ``--out``, a rolling ``--since``, the
  digest dir from the show YAML; the dashboard's
  ``script_stage_p95_s_14d_<show>`` live metric;
* the nightly wiring (steps, add-paths — the youtube_channel_history
  silent-drop class) and the Mission Control card.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

NIGHTLY = ROOT / ".github" / "workflows" / "nightly-maintenance.yml"
TODAY = dt.date(2026, 11, 4)


def _load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# readout_register.py
# ---------------------------------------------------------------------------

FIXTURE_REGISTER = {"experiments": [
    {"id": "metric-overdue", "title": "Metric-bearing, 20 days overdue",
     "area": "quality", "shipped": dt.date(2026, 9, 20), "readout": dt.date(2026, 10, 15),
     "status": "reading", "metric": "widget_share_7d", "baseline": 0.1, "target": ">= 0.5"},
    {"id": "human-overdue", "title": "Human read, 20 days overdue, no outcome",
     "area": "reach", "shipped": dt.date(2026, 9, 20), "readout": dt.date(2026, 10, 15),
     "status": "reading", "target": "Blog sessions up 20% in api/ga4_stats.json"},
    {"id": "human-overdue-with-outcome", "title": "Human read, overdue, outcome drafted",
     "area": "reach", "shipped": dt.date(2026, 9, 20), "readout": dt.date(2026, 10, 15),
     "status": "reading", "target": "x", "outcome": "READ 2026-11-01: HIT"},
    {"id": "human-recent", "title": "Human read, 3 days overdue",
     "area": "funnel", "shipped": dt.date(2026, 10, 20), "readout": dt.date(2026, 11, 1),
     "status": "decide", "target": "y", "criteria": "z",
     "readout_plan": "python scripts/build_funnel.py"},
    {"id": "not-due", "title": "Not due yet", "area": "quality",
     "shipped": dt.date(2026, 11, 1), "readout": dt.date(2026, 11, 20),
     "status": "reading", "metric": "widget_share_7d"},
    {"id": "finished", "title": "Done", "area": "quality",
     "shipped": dt.date(2026, 9, 1), "readout": dt.date(2026, 9, 15),
     "status": "done", "outcome": "kept"},
    {"id": "new-note", "title": "Shipped after the rule, no readout path",
     "area": "quality", "shipped": dt.date(2026, 11, 4), "readout": dt.date(2026, 11, 20),
     "status": "reading", "target": "something"},
]}


class TestRegisterReadout:
    LIVE = {"widget_share_7d": 0.42}

    def _doc(self):
        rr = _load_script("readout_register")
        return rr, rr.build_readouts(FIXTURE_REGISTER["experiments"], self.LIVE, TODAY)

    def test_due_entries_split_by_whether_a_machine_can_read_them(self):
        _, doc = self._doc()
        assert [r["id"] for r in doc["with_metric"]] == ["metric-overdue"]
        assert [r["id"] for r in doc["needs_human_read"]] == [
            "human-overdue", "human-overdue-with-outcome", "human-recent"]
        assert doc["due_count"] == 4 and doc["overdue_count"] == 4

    def test_metric_entry_carries_the_live_value_beside_baseline_and_target(self):
        _, doc = self._doc()
        row = doc["with_metric"][0]
        assert row["live"] == 0.42 and row["baseline"] == 0.1 and row["target"] == ">= 0.5"
        assert row["days_overdue"] == 20

    def test_human_read_carries_days_overdue_target_and_plan(self):
        _, doc = self._doc()
        recent = next(r for r in doc["needs_human_read"] if r["id"] == "human-recent")
        assert recent["days_overdue"] == 3
        assert recent["readout_plan"] == "python scripts/build_funnel.py"
        assert recent["target"] == "y"

    def test_strict_names_only_the_unread_fourteen_day_entries(self):
        """>= 14 days past readout with neither outcome nor metric. An
        entry with a metric reads itself; one with an outcome was read."""
        _, doc = self._doc()
        assert doc["strict_failures"] == ["human-overdue"]

    def test_unmeasured_live_value_is_none_never_zero(self):
        rr = _load_script("readout_register")
        doc = rr.build_readouts(FIXTURE_REGISTER["experiments"], {"widget_share_7d": None}, TODAY)
        assert doc["with_metric"][0]["live"] is None

    def test_new_entry_with_no_readout_path_is_listed_as_a_note(self):
        _, doc = self._doc()
        assert [r["id"] for r in doc["notes_not_experiments"]] == ["new-note"]
        assert "note, not an experiment" in doc["notes_not_experiments"][0]["defect"]

    def test_main_writes_the_file_and_strict_exits_one(self, tmp_path, monkeypatch):
        rr = _load_script("readout_register")
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "experiments.yaml").write_text(
            yaml.safe_dump(FIXTURE_REGISTER, sort_keys=False), encoding="utf-8")
        monkeypatch.setattr(rr, "live_metrics", lambda root: dict(self.LIVE))
        out = tmp_path / "api" / "register_readouts.json"
        rc = rr.main(["--root", str(tmp_path), "--out", str(out), "--strict",
                      "--today", "2026-11-04"])
        assert rc == 1
        doc = json.loads(out.read_text(encoding="utf-8"))
        assert doc["strict_failures"] == ["human-overdue"]
        assert doc["today"] == "2026-11-04"
        # Without --strict the same register exits 0 — the nightly's warning
        # comes from --strict, never from a crash.
        assert rr.main(["--root", str(tmp_path), "--out", str(out),
                        "--today", "2026-11-04"]) == 0

    def test_the_script_never_edits_the_register(self, tmp_path, monkeypatch):
        rr = _load_script("readout_register")
        (tmp_path / "docs").mkdir()
        reg = tmp_path / "docs" / "experiments.yaml"
        reg.write_text(yaml.safe_dump(FIXTURE_REGISTER, sort_keys=False), encoding="utf-8")
        before = reg.read_bytes()
        monkeypatch.setattr(rr, "live_metrics", lambda root: dict(self.LIVE))
        rr.main(["--root", str(tmp_path), "--out", str(tmp_path / "o.json"),
                 "--today", "2026-11-04"])
        assert reg.read_bytes() == before

    def test_committed_register_is_read_in_full(self, tmp_path):
        """Every open entry whose readout has arrived is in the file, and the
        metric-bearing ones carry a live value — the acceptance read."""
        rr = _load_script("readout_register")
        entries = rr.load_register(ROOT / "docs" / "experiments.yaml")
        today = dt.date.today()
        doc = rr.build_readouts(entries, rr.live_metrics(ROOT), today)
        expected = {e["id"] for e in entries
                    if e.get("status") in rr.OPEN_STATUSES
                    and rr._as_date(e.get("readout")) is not None
                    and rr._as_date(e.get("readout")) <= today}
        listed = {r["id"] for r in doc["with_metric"]} | {r["id"] for r in doc["needs_human_read"]}
        assert listed == expected
        assert all("live" in r for r in doc["with_metric"])
        if doc["with_metric"]:
            assert any(isinstance(r["live"], (int, float)) for r in doc["with_metric"]), (
                "no metric-bearing due entry carries a number — the live read is broken")
        out = tmp_path / "register_readouts.json"
        rc = rr.main(["--out", str(out), "--today", today.isoformat()])
        assert rc == 0 and json.loads(out.read_text(encoding="utf-8"))["due_count"] == len(listed)


class TestReadabilityRule:
    """An entry shipped on/after the rule's date carries a computable metric
    OR criteria + a readout_plan naming what answers it; otherwise it is a
    note, not an experiment. The rule binds new entries only."""

    def _entry(self, **kw):
        base = {"id": "x", "title": "x", "area": "quality", "status": "reading",
                "shipped": dt.date(2026, 11, 4), "readout": dt.date(2026, 11, 18)}
        base.update(kw)
        return base

    def test_neither_is_a_defect(self):
        rr = _load_script("readout_register")
        assert rr.readability_defect(self._entry(target="t"), {"m"}) is not None

    def test_computable_metric_passes_and_unknown_metric_fails(self):
        rr = _load_script("readout_register")
        assert rr.readability_defect(self._entry(metric="m"), {"m"}) is None
        assert "does not compute" in rr.readability_defect(self._entry(metric="typo"), {"m"})

    def test_criteria_plus_readout_plan_passes_and_either_alone_fails(self):
        rr = _load_script("readout_register")
        assert rr.readability_defect(
            self._entry(criteria="c", readout_plan="python scripts/x.py"), set()) is None
        assert rr.readability_defect(self._entry(criteria="c"), set()) is not None
        assert rr.readability_defect(self._entry(readout_plan="p"), set()) is not None

    def test_the_rule_binds_new_entries_only(self):
        rr = _load_script("readout_register")
        old = self._entry(shipped=dt.date(2026, 10, 1), target="t")
        assert rr.readability_defect(old, set()) is None


# ---------------------------------------------------------------------------
# The network target: reachable, and with its predictions in view
# ---------------------------------------------------------------------------

class TestNetworkContextCarriesPendingPredictions:
    def test_committed_network_ledger_has_pending_predictions_to_score(self):
        mod = _load_script("run_show_review")
        pending = mod.pending_predictions(ROOT / "docs" / "reviews" / "ledger" / "network.yaml")
        assert pending and all(p["metric"] for p in pending)
        assert all(p["date"] for p in pending)

    def test_context_leads_with_every_pending_prediction(self):
        mod = _load_script("run_show_review")
        pending = mod.pending_predictions(ROOT / "docs" / "reviews" / "ledger" / "network.yaml")
        ctx = mod.gather_network_context()
        head = ctx.split("## LEDGER ", 1)[0]  # before the truncated ledger dumps
        assert f"{len(pending)} PENDING PREDICTIONS" in head
        assert "scored_prior_predictions" in head
        for p in pending:
            assert p["metric"][:60] in head

    def test_broken_yaml_falls_back_to_a_line_scan(self, tmp_path):
        mod = _load_script("run_show_review")
        ledger = tmp_path / "x.yaml"
        ledger.write_text(
            "reviews:\n"
            "  - date: '2026-06-30'\n"
            "    summary: broken: unquoted: colons: everywhere\n"
            "    predictions:\n"
            "      - metric: first thing\n"
            "        baseline: 1\n"
            "        expected: 2\n"
            "        verdict: hit\n"
            "      - metric: second thing\n"
            "        baseline: 3\n"
            "        expected: 4\n"
            "        verdict: pending\n", encoding="utf-8")
        with pytest.raises(yaml.YAMLError):
            yaml.safe_load(ledger.read_text(encoding="utf-8"))
        pending = mod.pending_predictions(ledger)
        assert pending == [{"date": "2026-06-30", "metric": "second thing",
                            "baseline": "3", "expected": "4"}]


# ---------------------------------------------------------------------------
# review_pr_outcomes.py
# ---------------------------------------------------------------------------

PR_BODY = (
    "Grok review pass for tesla.\n\n"
    "## ⚠️ A/B-listen required — NOT applied (landmine #17)\n"
    "These prompt/audio changes are **proposals only**.\n\n"
    "**`shows/prompts/tesla_podcast.txt`** (prompt) — drop the closing tic\n"
    "```diff\n- old\n+ new\n```\n\n"
    "## Code/metadata-only proposals (no A/B needed)\n"
    "- **`shows/tesla.yaml`** (config): raise min_articles_skip to 7\n"
)


def _pr(number, branch, merged=None, labels=(), body=PR_BODY, closed="2026-10-28T10:00:00Z"):
    return {"number": number, "title": f"[show-review] pr {number}", "headRefName": branch,
            "mergedAt": merged, "closedAt": closed,
            "labels": [{"name": n} for n in labels],
            "url": f"https://github.com/x/y/pull/{number}", "body": body}


class FakeGh:
    def __init__(self, prs, asked=()):
        self.prs = prs
        self.asked = set(asked)
        self.comments = []
        self.calls = []

    def __call__(self, args):
        self.calls.append(args)
        if args[:2] == ["pr", "list"]:
            return json.dumps(self.prs)
        if args[:2] == ["pr", "view"]:
            marker = "<!-- review-pr-outcomes:ask -->"
            return marker if int(args[2]) in self.asked else "unrelated comment"
        if args[:2] == ["pr", "comment"]:
            self.comments.append((int(args[2]), args[args.index("--body") + 1]))
            return ""
        raise AssertionError(f"unexpected gh call {args}")


class TestReviewPrOutcomes:
    def _ledger_dir(self, tmp_path):
        d = tmp_path / "ledger"
        d.mkdir()
        for name in ("tesla.yaml", "dp_pod.yaml"):  # a populated and an empty do_not_retry
            (d / name).write_bytes((ROOT / "docs" / "reviews" / "ledger" / name).read_bytes())
        return d

    def test_unlabelled_closed_pr_gets_one_comment_asking_for_the_label(self, tmp_path):
        mod = _load_script("review_pr_outcomes")
        gh = FakeGh([_pr(901, "agent/review-tesla-20261027")])
        ledgers = self._ledger_dir(tmp_path)
        before = (ledgers / "tesla.yaml").read_bytes()
        out = mod.process(gh, ledgers, days=3650, today=TODAY)
        assert [o["action"] for o in out] == ["unlabelled"]
        assert len(gh.comments) == 1 and gh.comments[0][0] == 901
        body = gh.comments[0][1]
        assert mod.ASK_MARKER in body and "`rejected`" in body
        assert "closed PR without a label is unknown" in body
        assert (ledgers / "tesla.yaml").read_bytes() == before  # nothing written

    def test_the_ask_is_never_repeated(self, tmp_path):
        mod = _load_script("review_pr_outcomes")
        gh = FakeGh([_pr(901, "agent/review-tesla-20261027")], asked={901})
        out = mod.process(gh, self._ledger_dir(tmp_path), days=3650, today=TODAY)
        assert out[0]["note"] == "label already requested" and gh.comments == []

    def test_merged_superseded_and_stale_write_nothing(self, tmp_path):
        mod = _load_script("review_pr_outcomes")
        gh = FakeGh([
            _pr(1, "agent/review-tesla-20261001", merged="2026-10-02T00:00:00Z"),
            _pr(2, "agent/review-tesla-20261010", labels=("superseded",)),
            _pr(3, "agent/review-dp_pod-20261011", labels=("stale",)),
            _pr(4, "recovery/tesla-123", labels=()),  # not a review branch
        ])
        ledgers = self._ledger_dir(tmp_path)
        before = {p.name: p.read_bytes() for p in ledgers.glob("*.yaml")}
        out = mod.process(gh, ledgers, days=3650, today=TODAY)
        assert [o["action"] for o in out] == ["merged", "superseded", "stale"]
        assert gh.comments == []
        assert {p.name: p.read_bytes() for p in ledgers.glob("*.yaml")} == before

    def test_rejected_pr_splices_do_not_retry_and_touches_no_other_byte(self, tmp_path):
        mod = _load_script("review_pr_outcomes")
        gh = FakeGh([_pr(902, "agent/review-tesla-20261027", labels=("rejected",))])
        ledgers = self._ledger_dir(tmp_path)
        path = ledgers / "tesla.yaml"
        before = path.read_text(encoding="utf-8")
        out = mod.process(gh, ledgers, days=3650, today=TODAY)
        assert out[0]["action"] == "rejected" and out[0]["added"] == 2
        after = path.read_text(encoding="utf-8")
        # Text-splice: the whole prior file is a byte-prefix of the result.
        assert after.startswith(before.rstrip("\n") + "\n")
        appended = after[len(before.rstrip("\n")) + 1:]
        assert "PR #902" in appended and "drop the closing tic" in appended
        assert "shows/tesla.yaml (config): raise min_articles_skip to 7" in appended
        data = yaml.safe_load(after)
        prior = yaml.safe_load(before)
        assert data["reviews"] == prior["reviews"]
        assert len(data["do_not_retry"]) == len(prior["do_not_retry"]) + 2
        assert data["do_not_retry"][-1]["evidence"].startswith("PR #902")

    def test_rejected_pr_is_recorded_once(self, tmp_path):
        mod = _load_script("review_pr_outcomes")
        gh = FakeGh([_pr(902, "agent/review-tesla-20261027", labels=("rejected",))])
        ledgers = self._ledger_dir(tmp_path)
        mod.process(gh, ledgers, days=3650, today=TODAY)
        once = (ledgers / "tesla.yaml").read_bytes()
        out = mod.process(gh, ledgers, days=3650, today=TODAY)
        assert out[0]["added"] == 0 and out[0]["note"] == "already recorded"
        assert (ledgers / "tesla.yaml").read_bytes() == once

    def test_empty_do_not_retry_list_is_opened_in_place(self, tmp_path):
        mod = _load_script("review_pr_outcomes")
        gh = FakeGh([_pr(903, "agent/review-dp_pod-20261027", labels=("rejected",))])
        ledgers = self._ledger_dir(tmp_path)
        path = ledgers / "dp_pod.yaml"
        before = path.read_text(encoding="utf-8")
        assert "do_not_retry: []" in before
        mod.process(gh, ledgers, days=3650, today=TODAY)
        after = path.read_text(encoding="utf-8")
        head_before = before.split("do_not_retry: []", 1)[0]
        assert after.startswith(head_before)
        data = yaml.safe_load(after)
        assert len(data["do_not_retry"]) == 2
        assert data["reviews"] == yaml.safe_load(before)["reviews"]

    def test_dry_run_posts_and_writes_nothing(self, tmp_path):
        mod = _load_script("review_pr_outcomes")
        gh = FakeGh([_pr(901, "agent/review-tesla-20261027"),
                     _pr(902, "agent/review-tesla-20261028", labels=("rejected",))])
        ledgers = self._ledger_dir(tmp_path)
        before = (ledgers / "tesla.yaml").read_bytes()
        out = mod.process(gh, ledgers, days=3650, today=TODAY, dry_run=True)
        assert gh.comments == [] and (ledgers / "tesla.yaml").read_bytes() == before
        assert out[1]["would_add"] and len(out[1]["would_add"]) == 2

    def test_proposed_items_read_both_shapes_the_pr_body_writes(self):
        mod = _load_script("review_pr_outcomes")
        items = mod.proposed_items(PR_BODY)
        assert items == [
            "shows/prompts/tesla_podcast.txt (prompt): drop the closing tic",
            "shows/tesla.yaml (config): raise min_articles_skip to 7",
        ]


# ---------------------------------------------------------------------------
# model_trial_report.py — nightly, rolling, written out
# ---------------------------------------------------------------------------

class TestModelTrialNightly:
    def test_since_defaults_to_a_rolling_window(self):
        from scripts.model_trial_report import ROLLING_WINDOW_DAYS, rolling_since
        assert ROLLING_WINDOW_DAYS == 14
        assert rolling_since(dt.date(2026, 11, 4)) == dt.date(2026, 10, 21)

    def test_show_dir_comes_from_the_yaml_output_dir(self):
        from scripts.model_trial_report import show_dir_for
        assert show_dir_for("tesla") == ROOT / "digests" / "tesla_shorts_time"
        assert show_dir_for("spacex") == ROOT / "digests" / "spacex"
        assert show_dir_for("no_such_show") == ROOT / "digests" / "no_such_show"

    def test_out_writes_the_record_the_dashboard_reads(self, tmp_path):
        from scripts.model_trial_report import main
        out = tmp_path / "model_trial.json"
        main(["--shows", "spacex,tesla", "--timeout-seconds", "600", "--out", str(out),
              "--since", "2026-10-21"])
        doc = json.loads(out.read_text(encoding="utf-8"))
        assert doc["since"] == "2026-10-21" and doc["timeout_s"] == 600.0
        assert doc["gate"] in ("PASS", "FAIL", "no_data")
        for slug in ("spacex", "tesla"):
            stage = doc["shows"][slug]["stages"]["generate_podcast_script"]
            assert stage["n"] >= 1 and stage["p95"] is not None
            assert stage["llm_stage"] is True and "p95_timeout_share" in stage
        assert "tests/test_review_loop_2026_11_03.py" in doc["consumers"]

    def test_a_future_since_still_reports_nothing_and_exits_zero(self, tmp_path):
        from scripts.model_trial_report import main
        out = tmp_path / "t.json"
        assert main(["--since", "2099-01-01", "--out", str(out)]) == 0
        assert json.loads(out.read_text(encoding="utf-8"))["gate"] == "no_data"


class TestScriptStageLiveMetric:
    SHOWS = ("spacex", "tesla", "models_agents", "modern_investing",
             "fascinating_frontiers", "planetterrian")

    def test_every_script_arm_show_has_a_live_key(self):
        from scripts import generate_dashboard as gd
        live = gd._experiment_live_metrics(ROOT)
        for slug in self.SHOWS:
            assert f"script_stage_p95_s_14d_{slug}" in live

    def _root(self, tmp_path, durations, date="20261101"):
        d = tmp_path / "digests" / "x"
        d.mkdir(parents=True)
        (tmp_path / "api").mkdir()
        for i, dur in enumerate(durations, start=1):
            (d / f"metrics_ep{i}.json").write_text(json.dumps({"stages": [
                {"name": "generate_digest", "duration_s": 5.0, "success": True},
                {"name": "generate_podcast_script", "duration_s": dur, "success": True}]}),
                encoding="utf-8")
            (d / f"Show_Ep{i:03d}_{date}.md").write_text("digest", encoding="utf-8")
        return tmp_path

    def test_p95_is_nearest_rank_dated_by_the_sibling_digest(self, tmp_path, monkeypatch):
        from scripts import generate_dashboard as gd
        monkeypatch.setattr(gd, "_SCRIPT_ARM_SHOWS", ("x",))
        root = self._root(tmp_path, [100, 200, 300, 400, 500, 600])
        m = gd._script_stage_p95_metrics(root, dt.date(2026, 11, 4))
        assert m["script_stage_p95_s_14d_x"] == 600.0

    def test_episodes_older_than_the_window_do_not_count(self, tmp_path, monkeypatch):
        """Dated by the digest FILENAME: a file written today but named for
        September is September's (mtime would say today)."""
        from scripts import generate_dashboard as gd
        monkeypatch.setattr(gd, "_SCRIPT_ARM_SHOWS", ("x",))
        root = self._root(tmp_path, [100, 200, 300, 400, 500, 600], date="20260901")
        m = gd._script_stage_p95_metrics(root, dt.date(2026, 11, 4))
        assert m["script_stage_p95_s_14d_x"] is None

    def test_null_under_five_episodes_never_zero(self, tmp_path, monkeypatch):
        from scripts import generate_dashboard as gd
        monkeypatch.setattr(gd, "_SCRIPT_ARM_SHOWS", ("x", "absent"))
        root = self._root(tmp_path, [100, 200, 300, 400])
        m = gd._script_stage_p95_metrics(root, dt.date(2026, 11, 4))
        assert m["script_stage_p95_s_14d_x"] is None
        assert m["script_stage_p95_s_14d_absent"] is None


# ---------------------------------------------------------------------------
# Wiring: nightly steps, add-paths, the card, the playbook
# ---------------------------------------------------------------------------

def _nightly_steps():
    data = yaml.safe_load(NIGHTLY.read_text(encoding="utf-8"))
    return data["jobs"]["generate-artifacts"]["steps"]


def _nightly_add_paths():
    for step in _nightly_steps():
        raw = (step.get("with") or {}).get("add-paths")
        if raw:
            return {ln.strip() for ln in raw.splitlines() if ln.strip()}
    return set()


class TestNightlyWiring:
    def test_the_three_reads_run_after_the_dashboard_and_before_the_commit(self):
        names = [s.get("name") or "" for s in _nightly_steps()]
        i_dash = names.index("Generate Management Dashboard")
        i_commit = next(i for i, s in enumerate(_nightly_steps())
                        if (s.get("uses") or "").endswith("safe-commit-push"))
        for name in ("Read the experiments register", "Read the script-arm latency gate",
                     "Record review PR outcomes"):
            assert i_dash < names.index(name) < i_commit, name

    def test_register_readout_is_strict_but_never_fails_the_nightly(self):
        step = next(s for s in _nightly_steps() if s.get("name") == "Read the experiments register")
        run = step["run"]
        assert "scripts/readout_register.py --strict --out api/register_readouts.json" in run
        assert "|| echo \"::warning::" in run

    def test_latency_gate_runs_rolling_on_the_six_script_arm_shows(self):
        step = next(s for s in _nightly_steps() if s.get("name") == "Read the script-arm latency gate")
        run = step["run"]
        assert "scripts/model_trial_report.py" in run and "--since" not in run, (
            "the nightly read is a ROLLING window — never a fixed --since date")
        assert "--timeout-seconds 600" in run and "--out api/model_trial.json" in run
        for slug in TestScriptStageLiveMetric.SHOWS:
            assert slug in run
        assert "::warning::script-arm latency gate FAIL" in run

    def test_pr_outcomes_step_carries_the_token_and_the_permission(self):
        step = next(s for s in _nightly_steps() if s.get("name") == "Record review PR outcomes")
        assert step["env"]["GH_TOKEN"] == "${{ secrets.GITHUB_TOKEN }}"
        assert "scripts/review_pr_outcomes.py" in step["run"]
        perms = yaml.safe_load(NIGHTLY.read_text(encoding="utf-8"))["permissions"]
        assert perms["pull-requests"] == "write"

    def test_every_new_nightly_file_is_in_add_paths(self):
        """The youtube_channel_history class: a file written nightly and
        missing from the whitelist is rebuilt and thrown away."""
        paths = _nightly_add_paths()
        for p in ("api/register_readouts.json", "api/model_trial.json",
                  "docs/reviews/ledger/*.yaml"):
            assert p in paths, p


class TestSurfacesAndPlaybook:
    def test_mission_control_renders_the_readouts_card_from_its_own_file(self):
        html = (ROOT / "management.html").read_text(encoding="utf-8")
        assert "Readouts due" in html
        assert 'fetch("api/register_readouts.json"' in html
        block = html.split("Readouts due", 1)[1][:6000]
        for key in ("with_metric", "needs_human_read", "strict_failures", "days_overdue"):
            assert key in block, key

    def test_playbook_says_a_bare_close_is_unknown_and_rejected_is_the_signal(self):
        text = (ROOT / ".claude" / "commands" / "review-show.md").read_text(encoding="utf-8")
        assert "closed WITHOUT a label is unknown" in text
        assert "`rejected` is the" in text and "review_pr_outcomes.py" in text
        assert "NOT automatically rejections" not in text
        readme = (ROOT / "docs" / "reviews" / "ledger" / "README.md").read_text(encoding="utf-8")
        assert "WITHOUT a label is unknown" in readme and "review_pr_outcomes.py" in readme

    def test_model_playbook_records_the_nightly_instrument(self):
        text = (ROOT / "docs" / "model_upgrade_playbook.md").read_text(encoding="utf-8")
        assert "api/model_trial.json" in text and "script_stage_p95_s_14d_<show>" in text
