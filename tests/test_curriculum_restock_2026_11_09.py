"""Curriculum auto-restock (Nov 9 2026).

Prediction Markets Daily's curriculum drained to 20 subjects, under the
21-subject runway floor, and the `curriculum` check went red on main and on
every PR. scripts/restock_curricula.py + restock-curricula.yml refill it
the way the topic-queue restock refills the narrative queues, with one
difference that matters: a subject is grounded on its OWN research query
(engine.research_papers.papers_for), the call the hook makes on air day.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import restock_curricula as rc  # noqa: E402

CFG = rc.CURRICULUM_CONFIGS["prediction_markets"]


def _cand(**kw):
    base = {
        "title": "Quadratic Voting and the Price of a Vote",
        "category": "theory",
        "brief": ("How quadratic voting lets people buy additional votes at a rising "
                  "cost, what the mechanism-design research argues it reveals about "
                  "the intensity of preferences, and where it has been tried."),
        "search": "quadratic voting",
        "require": ["quadratic voting"],
        "arxiv": 'abs:"quadratic voting"',
    }
    base.update(kw)
    return base


def _queue():
    return [{"id": "calibration", "title": "Calibration: What It Means for a Forecast to Be Right",
             "brief": "b" * 90, "category": "mechanism", "produced": True}]


class TestRegistry:
    def test_prediction_markets_is_registered_and_the_weeklies_are_not(self):
        assert set(rc.CURRICULUM_CONFIGS) == {"prediction_markets"}

    def test_files_exist(self):
        assert (ROOT / CFG.queue_file).exists()
        assert (ROOT / CFG.prompt_file).exists()

    def test_trigger_sits_above_the_alarm_floor(self):
        # The alarm (test_curriculum_restocked) fires under 21 subjects.
        assert CFG.trigger_weeks * CFG.episodes_per_week > 21
        assert CFG.target_weeks > CFG.trigger_weeks

    def test_categories_cover_the_live_curriculum(self):
        q = yaml.safe_load((ROOT / CFG.queue_file).read_text(encoding="utf-8"))["queue"]
        live = {e["category"] for e in q} - {"debut"}
        assert live <= set(CFG.allowed_categories)

    def test_prompt_placeholders_and_no_quotable_example(self):
        text = (ROOT / CFG.prompt_file).read_text(encoding="utf-8")
        assert "{needed}" in text and "{existing_topics}" in text
        assert "NO quotation marks" in text and "NO statistics" in text


class TestValidation:
    def test_accepts_and_shapes_a_valid_subject(self):
        out = rc.validate_candidates([_cand()], _queue(), CFG)
        assert len(out) == 1
        e = out[0]
        assert e["id"] == "quadratic-voting-and-the-price"
        assert e["brief"].endswith(CFG.posture)
        assert e["exclude"] == ["cortical"]
        assert e["produced"] is False
        assert list(e)[:6] == ["id", "title", "brief", "category", "search", "require"]

    def test_posture_is_never_doubled(self):
        brief = _cand()["brief"] + " " + CFG.posture
        out = rc.validate_candidates([_cand(brief=brief)], _queue(), CFG)
        assert out[0]["brief"].count("never a recommendation") == 1

    @pytest.mark.parametrize("bad", [
        {"category": "debut"},
        {"brief": "too short"},
        {"brief": _cand()["brief"] + ' The host says "buy".'},
        {"brief": _cand()["brief"] + " Studies find a 12% gap."},
        {"search": ""},
        {"require": []},
        {"title": "Calibration: What It Means for a Forecast to Be Right"},
    ])
    def test_rejects(self, bad):
        assert rc.validate_candidates([_cand(**bad)], _queue(), CFG) == []

    def test_dedupes_within_the_batch_and_never_mutates_the_queue(self):
        q = _queue()
        before = [dict(e) for e in q]
        assert len(rc.validate_candidates([_cand(), _cand()], q, CFG)) == 1
        assert q == before


class TestGrounding:
    def test_keeps_only_subjects_their_own_query_can_source(self):
        a, b = rc.validate_candidates([_cand(), _cand(title="Mechanism Design for Honest Reports",
                                                      search="mechanism design", require=["mechanism"])],
                                      _queue(), CFG)
        found = {a["id"]: [{"url": "u1"}, {"url": "u2"}], b["id"]: [{"url": "u1"}]}
        kept = rc.ground_in_papers([a, b], 5, papers=lambda e: found[e["id"]])
        assert [e["id"] for e in kept] == [a["id"]]

    def test_a_failed_search_drops_the_subject(self):
        def boom(_e):
            raise RuntimeError("503")
        assert rc.ground_in_papers(rc.validate_candidates([_cand()], _queue(), CFG), 5, papers=boom) == []


class TestFlow:
    def _write(self, tmp_path, unproduced):
        q = _queue() + [{"id": f"t{i}", "title": f"Subject number {i} on topic {i * 7}",
                         "brief": "b" * 90, "category": ("risk", "theory")[i % 2],
                         "search": "x", "require": ["x"], "produced": False}
                        for i in range(unproduced)]
        p = tmp_path / CFG.queue_file
        p.parent.mkdir(parents=True)
        p.write_text(yaml.safe_dump({"queue": q}, sort_keys=False), encoding="utf-8")
        prompt = tmp_path / CFG.prompt_file
        prompt.parent.mkdir(parents=True, exist_ok=True)
        prompt.write_text((ROOT / CFG.prompt_file).read_text(encoding="utf-8"), encoding="utf-8")
        return p

    def test_above_trigger_never_calls_the_model(self, tmp_path):
        self._write(tmp_path, 40)

        def never(_p):
            raise AssertionError("model called above the trigger")
        r = rc.restock_curriculum(CFG, dry_run=False, force=False, root=tmp_path, generate=never)
        assert r["needed"] == 0

    def test_restock_appends_grounded_subjects_and_keeps_produced(self, tmp_path, monkeypatch):
        p = self._write(tmp_path, 20)
        monkeypatch.setattr(rc.rq, "ROOT", tmp_path)
        r = rc.restock_curriculum(CFG, dry_run=False, force=False, root=tmp_path,
                                  generate=lambda prompt: ([_cand()], "grok-4.3"),
                                  papers=lambda e: [{"url": "a"}, {"url": "b"}])
        assert r["needed"] == 36 and r["added"] == 1
        q = yaml.safe_load(p.read_text(encoding="utf-8"))["queue"]
        assert q[0]["id"] == "calibration" and q[0]["produced"] is True
        assert "quadratic-voting-and-the-price" in {e["id"] for e in q}
        assert sum(1 for e in q if not e.get("produced")) == 21

    def test_dry_run_writes_nothing(self, tmp_path, monkeypatch):
        p = self._write(tmp_path, 20)
        before = p.read_text(encoding="utf-8")
        monkeypatch.setattr(rc.rq, "ROOT", tmp_path)
        rc.restock_curriculum(CFG, dry_run=True, force=False, root=tmp_path,
                              generate=lambda prompt: ([_cand()], "grok-4.3"),
                              papers=lambda e: [{"url": "a"}, {"url": "b"}])
        assert p.read_text(encoding="utf-8") == before


class TestWorkflowWiring:
    def test_workflow_verifies_before_it_commits(self):
        wf = (ROOT / ".github/workflows/restock-curricula.yml").read_text(encoding="utf-8")
        assert "scripts/restock_curricula.py" in wf and "GROK_API_KEY" in wf
        assert wf.find("test_curriculum_restocked") < wf.find("safe-commit-push")
        assert "TestCurriculum" in wf
        assert "shows/curricula/*.yaml" in wf
        assert 'recovery-on-failure: "true"' in wf
        assert "runs-on: ubuntu-26.04" in wf


class TestCheck:
    def test_lists_only_unproduced_subjects_their_query_cannot_source(self, tmp_path):
        q = [{"id": "aired", "produced": True},
             {"id": "thin", "produced": False}, {"id": "fine", "produced": False}]
        p = tmp_path / CFG.queue_file
        p.parent.mkdir(parents=True)
        p.write_text(yaml.safe_dump({"queue": q}), encoding="utf-8")
        found = {"thin": [{"url": "a"}], "fine": [{"url": "a"}, {"url": "b"}]}
        assert rc.check_curriculum(CFG, root=tmp_path, papers=lambda e: found[e["id"]]) == ["thin"]
