"""The room researches quietly on its own (Oct 28 2026).

Patrick's test room, Oct 28: asked whether she could look something up, Mira
said she has no live search, and she was right. The search behind her
research notes (Sept 26) ran only when she called ``fact_check_claim``, and
that tool has been off her list since Oct 21, so no room had researched
anything since. He asked for her to do a little research during the
conversation and bring in what she finds without interrupting the flow or
the guest. The room now starts the lookups itself, scoped: one on the guest
after her first line, then one per substantial answer at most every two and
a half minutes, eight a room. A finding reaches her as one sourced note she
may use or let go; it never starts a turn.

These run the real scenario in a node vm (tests/fixtures/room_sim.js) with
the xAI search stubbed.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
SCENARIO_PATH = ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js"
SCENARIO = SCENARIO_PATH.read_text(encoding="utf-8")
SIM = ROOT / "tests" / "fixtures" / "room_sim.js"
WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


def sim(which: str) -> dict:
    out = subprocess.run([NODE, str(SIM), str(SCENARIO_PATH), which],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout)


@pytest.fixture(scope="module")
def room():
    return sim("auto_research")


@needs_node
class TestTheRoomLooksThingsUp:
    def test_the_guest_is_looked_up_after_her_first_line(self, room):
        assert room["afterOpening"]["lookups"] == 1
        first = room["lookups"][0]
        assert first["model"] == "grok-latest"
        assert first["tools"] == ["web_search", "x_search"]
        assert "Ada Lovelace, Chief Scientist at Analytical Engines" in first["prompt"]
        assert "Not their biography" in first["prompt"]
        assert room["guestIdentity"] == "Ada Lovelace, Chief Scientist at Analytical Engines"

    def test_a_substantial_answer_is_looked_up_and_a_short_one_is_not(self, room):
        assert room["afterShort"] == 1
        assert room["afterLong"]["lookups"] == 2
        prompt = room["lookups"][1]["prompt"]
        assert "Northwind Insurance" in prompt          # the answer it read
        assert "Tell me about the looms." in prompt     # the question it answered
        assert "Never their own story, experience or opinion" in prompt
        assert "would contradict them, found is false" in prompt

    def test_one_answer_lookup_per_gap_and_none_in_a_hold(self, room):
        assert room["insideGap"] == 2
        assert room["afterGap"] == 3
        assert room["inHold"] == 3
        assert room["researchLookups"] == 3

    def test_a_finding_never_starts_a_turn(self, room):
        assert room["afterOpening"]["creates"] == 0
        assert room["afterLong"]["creates"] == 0

    def test_each_finding_reaches_her_as_one_sourced_note(self, room):
        research = [n for n in room["notes"] if n.startswith("[RESEARCH NOTE")]
        assert len(research) == 3
        guest, answer = research[0], research[1]
        assert "Recent news on your guest or their work" in guest and "(Source: Source 1)" in guest
        assert "(Topic 2)" in answer and "(Source: Source 2)" in answer
        for note in research:
            assert "never say you searched" in note
            assert "never use it to correct or contradict them" in note
            assert "let it go" in note

    def test_the_trace_never_carries_the_guests_words(self, room):
        lines = [x["d"] for x in room["trace"] if x["e"] == "research"]
        assert lines and not any("Northwind" in d or "Halifax" in d for d in lines)
        assert "started (answer): an answer of 36 words" in lines

    def test_what_she_was_handed_is_reported(self, room):
        notes = room["researchNotes"]
        assert [n["kind"] for n in notes] == ["guest", "answer", "answer"]
        assert all(n["delivered"] for n in notes)
        assert notes[1]["subject"] == "Topic 2"       # the topic, never the answer
        assert all(len(n["finding"]) <= 300 for n in notes)


@needs_node
class TestWhenItStaysQuiet:
    def test_a_run_row_can_turn_it_off(self):
        out = sim("auto_research_off")
        assert out["researchLookups"] == 0 and out["afterGap"] == 0

    def test_never_in_a_hello_session(self):
        out = sim("auto_research_hello")
        assert out["researchLookups"] == 0

    def test_a_finding_that_lands_in_the_closing_round_is_kept_back(self):
        out = sim("auto_research_late")
        assert out["lateNotes"] == 0
        assert out["researchNotes"] and not any(n["delivered"] for n in out["researchNotes"])
        assert any(x["d"] == "found, not delivered (closing round)"
                   for x in out["trace"] if x["e"] == "research")


class TestTheLimits:
    def test_scoped_and_bounded(self):
        assert int(re.search(r"const AUTO_RESEARCH_MAX = (\d+);", SCENARIO).group(1)) <= 8
        assert int(re.search(r"const AUTO_RESEARCH_GAP_MS = (\d+);", SCENARIO).group(1)) >= 120000
        assert int(re.search(r"const AUTO_RESEARCH_MIN_WORDS = (\d+);", SCENARIO).group(1)) >= 20
        assert "RESEARCH_MAX_IN_FLIGHT = 2" in SCENARIO

    def test_off_in_closing_and_hello_sessions(self):
        body = SCENARIO[SCENARIO.index("function autoResearchOn("):]
        body = body[:body.index("\n}\n")]
        assert "isHelloSession()" in body and "isClosingSession()" in body
        assert "auto_research === false" in body

    def test_a_missing_key_never_throws_into_the_room(self):
        body = SCENARIO[SCENARIO.index("function researchInBackground("):]
        body = body[:body.index("\n}\n")]
        assert 'try { auth = "Authorization: Bearer " + getSecret("XAI_API_KEY"); }' in body
        assert "researchInFlight -= 1;" in body

    def test_the_tool_path_is_unchanged(self):
        assert 'researchInBackground(String(args.claim || ""), String(args.context || ""));' in SCENARIO


class TestTheRecord:
    def test_the_room_reports_its_research(self):
        assert "research_lookups: researchLookups," in SCENARIO
        assert "research_notes: researchNotes," in SCENARIO

    def test_the_worker_keeps_it_bounded(self):
        body = WORKER[WORKER.index("export function roomCountersOf("):]
        body = body[:body.index("\n}\n")]
        assert '"research_lookups"' in body
        assert "payload.research_notes.slice(0, 12)" in body
        assert '["guest", "answer", "request", "claim"]' in body

    def test_the_rehearsal_log_shows_it(self):
        import rehearsal
        trace = [{"e": "room", "d": "opened", "t": "2026-10-28T17:00:00Z"},
                 {"e": "research", "d": "started (guest): Ada", "t": "2026-10-28T17:00:30Z"},
                 {"e": "research", "d": "found: something", "t": "2026-10-28T17:00:50Z"}]
        log = rehearsal.room_log(trace)
        assert [x["line"] for x in log["research"]] == ["started (guest): Ada", "found: something"]
