"""Oct 5 2026 — the item coverage floor reads the item's OWN source.

The floor had added one verified claim across 24 flagship episodes: it
asked the model to name a fetchable page for each uncovered item from
memory, and a truthful model answered ``[]`` (Tesla Ep624 and SpaceX
Ep120 logs, 2026-10-04) while every item already cited its Source and the
run held the fetched copy. It also ran only on a passing gate, so a flag
mode episode with one unrelated unverified claim got no floor at all.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.claims import (
    GateResult,
    attempt_item_coverage_repair,
    normalize_source_url,
    run_source_integrity_gate,
)

ROOT = Path(__file__).resolve().parent.parent

REUTERS = "https://www.reuters.com/business/energy/ohio-plant-2026-10-04/"
AP = "https://apnews.com/article/council-levy-vote"

DIGEST = (
    "# Show\n**HOOK:** Hook.\n\n### Top News\n"
    "**Ohio plant expands: Reuters**\n"
    "The plant in Ohio will add two hundred megawatts of capacity by March, "
    "the company said on Tuesday.\n"
    f"Source: [reuters.com]({REUTERS})\n\n"
    "**Council approves levy: AP**\n"
    "The city council voted seven to two to approve the school levy on "
    "Monday night after a long hearing.\n"
    f"Source: [apnews.com]({AP})\n"
)

REUTERS_TEXT = (
    "Ohio plant expansion. The operator said on Tuesday that the plant in "
    "Ohio will add 200 megawatts of capacity by March next year. Shares "
    "rose two percent in early trading on the news."
)
AP_TEXT = (
    "Council approves levy. The city council voted 7-2 on Monday night to "
    "approve the school levy after a hearing that ran past midnight."
)
LOCAL = {normalize_source_url(REUTERS): REUTERS_TEXT,
         normalize_source_url(AP): AP_TEXT}


def _no_http(url):
    return 404, ""


def _passing_gate():
    gate = run_source_integrity_gate(DIGEST, [], fetch=_no_http, local_texts=LOCAL)
    assert gate.passed and gate.claims_verified == 0
    return gate


def _reply(*entries):
    return lambda prompt: json.dumps(list(entries))


class TestGroundedOnTheItemsOwnSource:
    def test_the_prompt_carries_the_item_url_and_its_fetched_passage(self):
        seen = []

        def llm(prompt):
            seen.append(prompt)
            return "[]"
        attempt_item_coverage_repair(DIGEST, _passing_gate(), [], llm,
                                     fetch=_no_http, local_texts=LOCAL)
        assert len(seen) == 1
        prompt = seen[0]
        assert REUTERS in prompt and AP in prompt
        assert "will add 200 megawatts of capacity by March" in prompt
        assert "voted 7-2 on Monday night" in prompt
        # The grounded request never asks for a page from memory.
        grounded = prompt.split("These sentences have no readable source")[0]
        assert "The source_url is fixed" in grounded

    def test_a_verbatim_quote_from_the_passage_is_added_on_the_items_url(self):
        llm = _reply({
            "id": "cov1", "claim": "The Ohio plant adds 200 MW by March",
            # The model tried to swap the source; the item's own URL wins.
            "source_url": "https://example.com/elsewhere",
            "supporting_quote": "the plant in Ohio will add 200 megawatts of capacity by March",
        })
        gate = _passing_gate()
        g2, c2, info = attempt_item_coverage_repair(DIGEST, gate, [], llm,
                                                    fetch=_no_http, local_texts=LOCAL)
        assert g2 is not gate and g2.passed
        assert g2.claims_verified == 1 and info["coverage_repair_added"] == 1
        assert info["coverage_repair_grounded"] == 2
        assert c2[0]["source_url"] == REUTERS
        assert c2[0]["episode_span"].startswith("The plant in Ohio")
        assert info["item_coverage_pct"] == 50.0

    def test_a_quote_absent_from_the_source_adds_nothing(self):
        llm = _reply({
            "id": "cov1", "claim": "The Ohio plant adds 200 MW by March",
            "supporting_quote": "Ohio plant will add two hundred megawatts by March, officials said",
        })
        gate = _passing_gate()
        g2, c2, info = attempt_item_coverage_repair(DIGEST, gate, [], llm,
                                                    fetch=_no_http, local_texts=LOCAL)
        assert g2 is gate and c2 == []
        assert info["coverage_repair_offered"] == 1
        assert info["coverage_repair_added"] == 0

    def test_a_verbatim_but_unrelated_quote_is_rejected(self):
        llm = _reply({"id": "cov1", "claim": "Ohio plant adds capacity",
                      "supporting_quote": "Shares rose two percent in early trading on the news"})
        gate = _passing_gate()
        g2, _, info = attempt_item_coverage_repair(DIGEST, gate, [], llm,
                                                   fetch=_no_http, local_texts=LOCAL)
        assert g2 is gate and info["coverage_repair_offered"] == 0

    def test_one_bad_answer_no_longer_discards_a_good_one(self):
        llm = _reply(
            {"id": "cov1", "claim": "Ohio plant adds 200 MW",
             "supporting_quote": "the plant in Ohio will add 200 megawatts of capacity by March"},
            {"id": "cov2", "claim": "Council approved the levy",
             "supporting_quote": "the council approved the levy unanimously on Monday night"},
        )
        g2, c2, info = attempt_item_coverage_repair(DIGEST, _passing_gate(), [], llm,
                                                    fetch=_no_http, local_texts=LOCAL)
        assert g2.passed and g2.claims_verified == 1
        assert [c["id"] for c in c2] == ["cov1"]
        assert info["coverage_repair_offered"] == 2 and info["coverage_repair_added"] == 1

    def test_an_item_with_no_readable_passage_is_asked_the_old_way(self):
        seen = []

        def llm(prompt):
            seen.append(prompt)
            return "[]"
        g2, _, info = attempt_item_coverage_repair(DIGEST, _passing_gate(), [], llm,
                                                   fetch=_no_http, local_texts={})
        assert info["coverage_repair_grounded"] == 0
        assert info["coverage_repair_targets"] == 2
        assert "These sentences have no readable source passage" in seen[0]
        assert "fetched_passage" not in seen[0]

    def test_the_page_is_fetched_when_the_run_holds_no_copy(self):
        pages = {REUTERS: (200, f"<html><body><p>{REUTERS_TEXT}</p></body></html>")}
        llm = _reply({"id": "cov1", "claim": "Ohio plant adds 200 MW",
                      "supporting_quote": "the plant in Ohio will add 200 megawatts of capacity by March"})
        g2, _, info = attempt_item_coverage_repair(
            DIGEST, _passing_gate(), [], llm,
            fetch=lambda u: pages.get(u, (404, "")), local_texts={})
        assert info["coverage_repair_grounded"] == 1
        assert g2.claims_verified == 1


class TestRunsOnAFlaggedGate:
    def test_a_gate_failing_on_an_unrelated_claim_still_gains_coverage(self):
        bad = {"id": "c1", "claim": "The levy passed",
               "episode_span": "The city council voted seven to two to approve the school levy",
               "source_url": "https://example.com/missing",
               "supporting_quote": "a quote that appears on no page anywhere"}
        gate = run_source_integrity_gate(DIGEST, [bad], fetch=_no_http, local_texts=LOCAL)
        assert not gate.passed and len(gate.failed_verifications) == 1
        llm = _reply({"id": "cov1", "claim": "Ohio plant adds 200 MW",
                      "supporting_quote": "the plant in Ohio will add 200 megawatts of capacity by March"})
        g2, c2, info = attempt_item_coverage_repair(DIGEST, gate, [bad], llm,
                                                    fetch=_no_http, local_texts=LOCAL)
        assert g2.claims_verified == 1 and info["coverage_repair_added"] == 1
        # The failing entry is untouched and still fails.
        assert c2[0] is bad and len(g2.failed_verifications) == 1

    def test_run_show_runs_the_floor_in_flag_mode(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert ('if _si_gate.passed or (_si_enforce and _si_on_failure == "flag"):'
                in src)
        assert src.index('_si_on_failure == "flag"):') < src.index(
            "attempt_item_coverage_repair(")

    def test_a_covered_digest_spends_no_call(self):
        verified = [
            {"id": "1", "claim": "Ohio plant adds 200 MW by March",
             "episode_span": "The plant in Ohio will add two hundred megawatts of capacity by March"},
            {"id": "2", "claim": "Council approved the levy 7-2",
             "episode_span": "The city council voted seven to two to approve the school levy"},
        ]
        gate = GateResult(passed=True, claims_total=2, claims_verified=2,
                          verified_claims=verified)

        def llm(prompt):
            raise AssertionError("no call expected")
        g2, _, info = attempt_item_coverage_repair(DIGEST, gate, verified, llm)
        assert g2 is gate and info["coverage_repair_attempted"] is False
