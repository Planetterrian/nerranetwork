"""Drift guards for the automated topic-queue restock (July 24 2026).

scripts/restock_topic_queues.py + restock-topic-queues.yml keep the
narrative shows' queues filled via trigger-gated Grok generation, so the
runway floors in test_network_quality_pass.py::TestNarrativeQueueRunway
become the alarm of last resort instead of a recurring manual chore.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import restock_topic_queues as rq  # noqa: E402


class TestConfigRegistry:
    def test_both_narrative_shows_registered(self):
        assert set(rq.RESTOCK_CONFIGS) == {
            "first_principles", "unintended_consequences"}

    def test_age_of_ai_never_registered(self):
        # Its queue is DELIBERATELY empty (Nerra Voices pipeline; the empty
        # queue makes an accidental run_show invocation a clean skip).
        assert "age_of_ai" not in rq.RESTOCK_CONFIGS

    @pytest.mark.parametrize("slug", sorted(rq.RESTOCK_CONFIGS))
    def test_files_exist(self, slug):
        cfg = rq.RESTOCK_CONFIGS[slug]
        assert (ROOT / cfg.queue_file).exists()
        assert (ROOT / cfg.prompt_file).exists()

    @pytest.mark.parametrize("slug", sorted(rq.RESTOCK_CONFIGS))
    def test_trigger_sits_above_alarm_floor(self, slug):
        # The alarm floors in TestNarrativeQueueRunway are 3.0 (FPD) and
        # 4.0 (UC) weeks — the restock trigger must fire comfortably
        # earlier so the alarm only means "automation broken".
        floors = {"first_principles": 3.0, "unintended_consequences": 4.0}
        cfg = rq.RESTOCK_CONFIGS[slug]
        assert cfg.trigger_weeks >= floors[slug] + 1.0
        assert cfg.target_weeks > cfg.trigger_weeks

    @pytest.mark.parametrize("slug", sorted(rq.RESTOCK_CONFIGS))
    def test_categories_match_live_queue(self, slug):
        cfg = rq.RESTOCK_CONFIGS[slug]
        q = yaml.safe_load((ROOT / cfg.queue_file).read_text())["queue"]
        live_cats = {e.get("category") for e in q if not e.get("produced")}
        assert live_cats <= set(cfg.allowed_categories) | {"debut"}

    @pytest.mark.parametrize("slug", sorted(rq.RESTOCK_CONFIGS))
    def test_prompt_placeholders(self, slug):
        text = (ROOT / rq.RESTOCK_CONFIGS[slug].prompt_file).read_text()
        for token in ("{existing_topics}", "{needed}", "{category_guidance}"):
            assert token in text, f"{slug} restock prompt missing {token}"
        # The honesty rule is load-bearing — generated briefs feed episodes.
        assert "never invent" in text.lower() or "never invent or embellish" in text.lower()


class TestRunwayMath:
    def test_no_restock_above_trigger(self):
        cfg = rq.RESTOCK_CONFIGS["first_principles"]
        assert rq.topics_needed(int(cfg.trigger_weeks * 7) + 1, cfg) == 0

    def test_restock_fills_to_target(self):
        cfg = rq.RESTOCK_CONFIGS["first_principles"]
        needed = rq.topics_needed(10, cfg)  # 10/7 ≈ 1.4 weeks — well below
        assert needed == min(int(cfg.target_weeks * 7) - 10, cfg.max_new_per_run)

    def test_backstop_cap(self):
        cfg = rq.RESTOCK_CONFIGS["first_principles"]
        assert rq.topics_needed(0, cfg) <= cfg.max_new_per_run


class TestValidation:
    def _cfg(self):
        return rq.RESTOCK_CONFIGS["unintended_consequences"]

    def _queue(self):
        return [{"id": "cobra-effect", "title": "The Cobra Effect",
                 "brief": "x" * 100, "category": "classic", "produced": True}]

    def _cand(self, **over):
        c = {"title": "The Bridge That Moved the Traffic",
             "brief": "b" * 120, "category": "infrastructure"}
        c.update(over)
        return c

    def test_accepts_valid_novel_topic(self):
        out = rq.validate_and_dedupe([self._cand()], self._queue(), self._cfg(), 5)
        assert len(out) == 1
        assert out[0]["produced"] is False
        assert out[0]["id"] == "the-bridge-that-moved-the"

    def test_rejects_duplicate_and_near_duplicate(self):
        dup = self._cand(title="The Cobra Effect")
        near = self._cand(title="The Cobra Effect Bounty Story")
        out = rq.validate_and_dedupe([dup, near], self._queue(), self._cfg(), 5)
        assert out == []

    def test_rejects_bad_category_and_thin_brief(self):
        bad_cat = self._cand(category="gossip")
        thin = self._cand(title="Another Real Case", brief="too short")
        out = rq.validate_and_dedupe([bad_cat, thin], self._queue(), self._cfg(), 5)
        assert out == []

    def test_caps_at_needed(self):
        titles = ["The Dam That Salted the Delta",
                  "Antibiotics on the Feedlot Floor",
                  "The Scrappage Scheme Price Spiral",
                  "Helmets and the Risk Thermostat",
                  "The Quota That Emptied the Nets"]
        cands = [self._cand(title=t) for t in titles]
        out = rq.validate_and_dedupe(cands, self._queue(), self._cfg(), 3)
        assert len(out) == 3

    def test_never_mutates_existing_queue(self):
        q = self._queue()
        before = [dict(e) for e in q]
        rq.validate_and_dedupe([self._cand()], q, self._cfg(), 5)
        assert q == before

    def test_parse_tolerates_fences_and_prose(self):
        text = 'Here you go:\n```json\n[{"title": "T", "brief": "b", "category": "tech"}]\n```'
        assert rq.parse_topics_json(text) == [
            {"title": "T", "brief": "b", "category": "tech"}]


class TestWorkflowWiring:
    def test_workflow_exists_and_gated(self):
        wf = (ROOT / ".github/workflows/restock-topic-queues.yml").read_text()
        assert "restock_topic_queues.py" in wf
        assert "GROK_API_KEY" in wf
        # Post-restock validation must run BEFORE the commit step.
        assert wf.find("TestNarrativeQueueRunway") < wf.find("safe-commit-push")
        # Both queue files whitelisted for commit (the history-file landmine).
        assert "shows/topic_queues/first_principles.yaml" in wf
        assert "shows/topic_queues/unintended_consequences.yaml" in wf

    def test_runway_alarm_comment_updated(self):
        src = (ROOT / "tests/test_network_quality_pass.py").read_text()
        assert "restock-topic-queues.yml" in src
