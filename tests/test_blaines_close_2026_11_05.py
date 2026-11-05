"""What Blaine Mathieu's room taught about the close (Nov 4 2026, reviewed Nov 5).

He asked to end three ways the room did not hear ("I think we probably got
enough here ... if you want to do a final ending comment you can make it
now", "let's wrap it up.", "we ended it"), so it cut two of Mira's goodbyes
mid-sentence and its clock started the seven-question closing round after
his goodbye. He had typed "lets wrap it" at thirty minutes (no "up", so a
topic), and "you still there" after a silence went to her as a subject he
wanted to reach. The grade blamed her pacing for all of it.

These guards hold: the shapes are heard as a stop, the old false positives
stay out, a stop means the clock never starts a round, a typed wrap-up still
gets its round, and a typed presence check is a message, never a topic.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js"
SCENARIO = SCENARIO_PATH.read_text(encoding="utf-8")
SIM = ROOT / "tests" / "fixtures" / "room_sim.js"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


def sim(which: str) -> dict:
    out = subprocess.run([NODE, str(SIM), str(SCENARIO_PATH), which],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout)


def _regex(name: str) -> re.Pattern:
    head = f"const {name} = /"
    rx = SCENARIO[SCENARIO.index(head) + len(head):]
    return re.compile(rx[:rx.index("/i;")].replace("\\u2014", "—"), re.I)


class TestHeAskedToStop:
    STOP = _regex("GUEST_STOP_RE")

    def test_his_words_are_a_stop(self):
        for text in ("hey Mira I think we probably got it got enough here.",
                     "If you want to do a final ending comment you can make it now",
                     "Hey, Mira, let's wrap it up.",
                     "Hey, Mira, we ended it.",
                     "we're done here.",
                     "let's stop here", "I have to go."):
            assert self.STOP.search(text), text

    def test_a_sentence_that_carries_on_is_not(self):
        for text in ("all the tests that we need to run when we're actually working with these clients",
                     "let's wrap up the launch story first",
                     "we got enough funding to hire",
                     "my last thought on that is the river",
                     "we're done with the migration",
                     "they ended up rehiring them",
                     "once we're finished with phase one we move on"):
            assert not self.STOP.search(text), text


class TestTypedMessages:
    WRAP = _regex("TYPED_WRAP_UP_RE")
    PRESENCE = _regex("TYPED_PRESENCE_RE")

    def test_lets_wrap_it_is_a_wrap_up(self):
        for text in ("lets wrap it", "let's wrap it up", "we can wrap up now", "finish up"):
            assert self.WRAP.search(text), text
        for text in ("how we wrap up a product launch", "we can wrap up the launch story",
                     "wrap it in governance"):
            assert not self.WRAP.search(text), text

    def test_you_still_there_is_a_presence_check(self):
        for text in ("you still there", "are you still there?", "Mira, can you hear me?", "hello?"):
            assert self.PRESENCE.search(text), text
        for text in ("are you there yet with agents", "there is a question",
                     "talk about whether you are still there for customers"):
            assert not self.PRESENCE.search(text), text

    def test_presence_is_checked_before_a_topic(self):
        body = SCENARIO[SCENARIO.index("function onGuestFeedback("):]
        body = body[:body.index("\n}\n")]
        assert body.index("TYPED_PRESENCE_RE.test(text)") < body.index("topicSteer(text)")

    def test_the_steer_has_no_specimen(self):
        steer = SCENARIO[SCENARIO.index("const PRESENCE_STEER ="):]
        steer = steer[:steer.index(";\n")]
        assert "\\u201c" not in steer


@needs_node
class TestTheRoomLetsHimGo:
    def test_a_stop_means_no_round_on_the_clock(self):
        out = sim("blaine_stop_then_clock")
        assert out["askedToStop"] is True
        assert out["cancels"] == 0
        assert out["state"]["roundActive"] is False and out["state"]["roundClosed"] is True
        assert out["pendingStart"] is False and out["thanksSent"] is True
        assert any(x["e"] == "time" and x["d"].endswith("the guest asked to stop, so no round")
                   for x in out["trace"])
        assert not any(x["e"] == "round" and x["d"].startswith("asked ") for x in out["trace"])

    def test_without_a_stop_the_round_is_still_due(self):
        out = sim("blaine_no_stop_then_clock")
        assert out["askedToStop"] is False
        assert out["pendingStart"] is True and out["state"]["roundClosed"] is False

    def test_a_typed_wrap_up_still_gets_its_round(self):
        out = sim("typed_wrap_up_before_round")
        assert out["state"]["roundActive"] is True


@needs_node
class TestPresenceCheck:
    def test_it_is_a_message_not_a_topic(self):
        out = sim("typed_presence")
        assert "check that you are still there" in out["steer"]
        assert "something they wanted to get to" not in out["steer"]
        assert out["feedback"][-1]["presence"] is True
        assert out["acks"][-1] == {"nn": 1, "ack": "topic", "status": "queued"}

    def test_the_round_is_not_steered(self):
        out = sim("typed_presence_in_round")
        assert out["steer"] is None
        assert out["acks"][-1]["status"] == "closing"


class TestItIsRehearsed:
    def test_the_fixture_can_ask_to_wrap_early(self):
        import sys
        sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
        import rehearsal
        assert rehearsal.fixture_beats(early_wrap=True) == rehearsal.EARLY_WRAP_BEATS
        both = rehearsal.fixture_beats(with_hold=True, early_wrap=True)
        assert [b["at_min"] for b in both] == sorted(b["at_min"] for b in both)
        assert rehearsal.fixture_beats() is None
        fixture = (ROOT / "voximplant" / "scenarios" / "age_of_ai_fixture_guest.js").read_text(encoding="utf-8")
        assert 'case "ask_to_wrap":' in fixture
        workflow = (ROOT / ".github" / "workflows" / "nerra_voices_rehearsal.yml").read_text(encoding="utf-8")
        assert "inputs.early_wrap" in workflow and workflow.count("--early-wrap") == 2


class TestTheReadBackReadsBack:
    """Rehearsal 41953433703 (Nov 5): the first real candidate read-back
    failed on a copy uploaded one second earlier, so the early-wrap room was
    never rehearsed. The proof is now this upload's build marker."""

    @staticmethod
    def _vc():
        import importlib
        return importlib.import_module("voximplant.api_clients.voximplant_client")

    def _fake(self, monkeypatch, script):
        vc = self._vc()
        sent = {}

        def fake_call(method, **params):
            sent[method] = params
            return {"result": [{"scenario_name": params["scenario_name"], "scenario_id": 7,
                                "modified": "now", "scenario_script": script}]}
        monkeypatch.setattr(vc, "_call", fake_call)
        return vc, sent

    def test_it_asks_for_the_script_in_the_api_s_spelling(self, monkeypatch):
        vc, sent = self._fake(monkeypatch, "src")
        vc.read_back_scenario("x", "src")
        assert sent["GetScenarios"]["with_script"] == "true"

    def test_a_re_encoded_copy_with_this_upload_s_marker_passes(self, monkeypatch):
        body = "const DASH = \"\u2014\";\n"
        marker = f"{self._vc().BUILD_MARKER_PREFIX}{self._vc().source_digest(body)}"
        vc, _ = self._fake(monkeypatch, marker + "\nconst DASH = \"\\u2014\";\n")
        out = vc.read_back_scenario("x", marker + "\n" + body)
        assert out["matches"] is True and out["exact"] is False

    def test_another_upload_s_marker_fails_and_names_no_text(self, monkeypatch):
        vc, _ = self._fake(monkeypatch, "// nerra-build: 0000\nconst KEY = \"secret-a\";")
        with pytest.raises(vc.VoximplantError, match="does not hold") as err:
            vc.read_back_scenario("x", "// nerra-build: 1111\nconst KEY = \"secret-b\";")
        assert "secret" not in str(err.value)

    def test_the_verified_upload_carries_the_marker(self, monkeypatch):
        vc = self._vc()
        sent = {}

        def fake_call(method, **params):
            sent.setdefault(method, params)
            if method == "GetScenarios":
                return {"result": [{"scenario_name": params["scenario_name"],
                                    "scenario_script": sent["SetScenarioInfo"]["scenario_script"]}]}
            return {"result": 1}
        monkeypatch.setattr(vc, "_call", fake_call)
        for k in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "GROK_API_KEY", "XAI_API_KEY"):
            monkeypatch.setenv(k, "x")
        vc.upload_candidate_scenario()
        assert sent["SetScenarioInfo"]["scenario_script"].startswith(vc.BUILD_MARKER_PREFIX)
