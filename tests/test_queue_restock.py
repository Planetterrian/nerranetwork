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
        # The commit whitelist is a glob, not per-show hardcoding: with
        # explicit files listed, a third narrative show's restocked queue
        # would be generated and then silently never committed (Aug 15
        # 2026 audit — same silent-drop class as youtube_channel_history).
        # Age of AI's deliberately-empty queue is not in the restock
        # registry, so the glob can never stage a restock for it.
        assert "shows/topic_queues/*.yaml" in wf

    def test_runway_alarm_comment_updated(self):
        src = (ROOT / "tests/test_network_quality_pass.py").read_text()
        assert "restock-topic-queues.yml" in src


class TestResequenceUnproduced:
    """The first live restock run (2026-07-24) generated valid topics but
    appended them in model order — long same-category runs that failed the
    queue-interleave drift guards, and the workflow's verify-before-commit
    step correctly blocked the commit. The script now re-interleaves the
    whole unproduced tail in place after appending."""

    def _entry(self, i, cat, produced=False):
        return {"id": f"t{i}", "title": f"T{i}", "brief": "b" * 90,
                "category": cat, "produced": produced}

    def test_fpd_shape_alternates_within_imbalance_bound(self):
        # Replicates the failed run: 2 categories, imbalanced (33 C / 23 O
        # style), appended as one big C-block then an O-block.
        queue = [self._entry(0, "concrete_example", produced=True)]
        queue += [self._entry(i + 1, "concrete_example") for i in range(12)]
        queue += [self._entry(i + 20, "opportunity_area") for i in range(8)]
        rq.resequence_unproduced(queue)
        seq = [e["category"] for e in queue if not e["produced"]]
        pairs = sum(1 for a, b in zip(seq, seq[1:]) if a == b)
        imbalance = abs(seq.count("concrete_example") - seq.count("opportunity_area"))
        assert pairs <= imbalance
        # Seam: first unproduced differs from the last produced category.
        assert seq[0] != "concrete_example"

    def test_uc_shape_no_adjacent_repeat_before_overflow(self):
        import itertools
        from collections import Counter
        queue = [self._entry(0, "classic", produced=True)]
        cats = ["economics"] * 10 + ["policy"] * 5 + ["classic"] * 4 + \
               ["medicine"] * 3 + ["infrastructure"] * 2 + ["tech"] * 1
        queue += [self._entry(i + 1, c) for i, c in enumerate(cats)]
        rq.resequence_unproduced(queue)
        seq = [e["category"] for e in queue if not e["produced"]]
        counts = Counter(seq)
        dominant = counts.most_common(1)[0][0]
        head = seq[: len(seq) - counts[dominant]]
        runs = [sum(1 for _ in g) for _, g in itertools.groupby(head)]
        assert max(runs, default=0) <= 1, f"clustered head: {seq}"

    def test_produced_entries_and_positions_untouched(self):
        queue = [self._entry(0, "classic", produced=True),
                 self._entry(1, "policy"),
                 self._entry(2, "classic", produced=True),
                 self._entry(3, "policy"),
                 self._entry(4, "tech")]
        before_produced = [(i, e["id"]) for i, e in enumerate(queue) if e["produced"]]
        before_ids = sorted(e["id"] for e in queue)
        rq.resequence_unproduced(queue)
        after_produced = [(i, e["id"]) for i, e in enumerate(queue) if e["produced"]]
        assert after_produced == before_produced
        assert sorted(e["id"] for e in queue) == before_ids  # nothing lost/duped

    def test_restock_flow_calls_resequence(self):
        src = (ROOT / "scripts/restock_topic_queues.py").read_text()
        assert "resequence_unproduced(queue)" in src
