"""Mira researches in the background and speaks only about what she found.

Sept 26 2026. In Chad Law's interview Mira said "I cannot verify that
specific announcement from the sources I have", twice, about things he had
just told her and that were true. The fact-check tool never searched: the
Worker echoed an instruction to search with grounding she does not have and
to "say plainly if it cannot be verified". Patrick's rule: keep researching,
mention it only when it substantiates or adds to what the guest said, and
never mention the searching or the not-finding.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCENARIO = (ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js").read_text(encoding="utf-8")
FIRE = (ROOT / "pipelines" / "voices" / "fire_interviews.py").read_text(encoding="utf-8")
WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")


def _handler() -> str:
    start = SCENARIO.index('} else if (name === "fact_check_claim") {')
    return SCENARIO[start:SCENARIO.index("} else {", start)]


class TestTheToolNeverBlocksHer:
    def test_it_answers_at_once_and_searches_on_the_side(self):
        body = _handler()
        assert "researchInBackground(" in body
        assert "await" not in body, "a search must never hold up the conversation"
        assert "Carry on" in body

    def test_it_no_longer_asks_the_worker_to_tell_her_to_shrug(self):
        assert "/fact-check" not in _handler()
        assert "say plainly if it cannot be verified" not in WORKER


class TestTheSearchIsReal:
    def test_it_asks_grok_with_web_and_x_search(self):
        assert 'const RESEARCH_MODEL = "grok-latest";' in SCENARIO
        assert '"https://api.x.ai/v1/responses"' in SCENARIO
        assert '{ type: "web_search" }, { type: "x_search" }' in SCENARIO

    def test_only_a_positive_finding_reaches_her(self):
        body = SCENARIO[SCENARIO.index("function parseFinding("):SCENARIO.index("function researchInBackground(")]
        assert "obj.found === true" in body
        research = SCENARIO[SCENARIO.index("function researchInBackground("):SCENARIO.index("// Tool dispatch")]
        # Nothing found, a failed request, a non-200: all silent.
        assert research.count("(silent)") >= 3
        assert "[RESEARCH NOTE" in research
        # The note is added to the conversation without making her speak.
        assert "responseCreate" not in research

    def test_it_does_not_pile_up(self):
        assert "RESEARCH_MAX_IN_FLIGHT = 2" in SCENARIO
        assert "researchSeen[key]" in SCENARIO


class TestSheIsToldWhatTheToolDoes:
    def test_the_tool_description_says_to_say_nothing(self):
        assert "carry on talking and say nothing about it" in FIRE
        assert "mention the search" in FIRE
