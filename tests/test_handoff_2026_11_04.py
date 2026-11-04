"""Nov 4 2026 status handoff: the fixes made from it, each pinned.

See docs/outstanding.md (the one tracker) for what is still open."""
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "pipelines" / "voices", ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


class TestRehearsalRebindsTheGuest:
    def test_current_arm_names_the_fixture(self):
        reh = importlib.import_module("rehearsal")
        prompt = ("You are interviewing Elliot Marsh. Greet Elliot by name. "
                  "Elliott Smith is a different person.")
        out = reh.rebind_guest(prompt, "Elliot Marsh", "Roddy Grant")
        assert "Elliot Marsh" not in out and "Greet Roddy by name" in out
        assert "Elliott Smith" in out, "a longer name is never touched"

    def test_blank_names_change_nothing(self):
        reh = importlib.import_module("rehearsal")
        assert reh.rebind_guest("Hello, Elliot", "", "Roddy") == "Hello, Elliot"
        assert reh.rebind_guest("Hello, Elliot", "Elliot", "") == "Hello, Elliot"

    def test_cmd_run_passes_the_fixture(self):
        src = (ROOT / "pipelines" / "voices" / "rehearsal.py").read_text(encoding="utf-8")
        assert "prompt = current_prompt(fixture)" in src


class TestCandidateUploadIsReadBack:
    def test_candidate_upload_verifies(self, monkeypatch):
        vc = importlib.import_module("voximplant.api_clients.voximplant_client")
        calls = []

        def fake_call(method, **params):
            calls.append(method)
            if method == "GetScenarios":
                return {"result": [{"scenario_name": params["scenario_name"],
                                    "scenario_id": 7, "modified": "2026-11-01 14:31:00",
                                    "scenario_script": "stale"}]}
            return {"result": 1}

        monkeypatch.setattr(vc, "_call", fake_call)
        import pytest
        with pytest.raises(vc.VoximplantError, match="does not hold"):
            vc.read_back_scenario("age_of_ai_interview_candidate", "fresh source")
        assert calls == ["GetScenarios"]
        src = (ROOT / "voximplant" / "api_clients" / "voximplant_client.py").read_text()
        assert "room_prefix=CANDIDATE_ROOM_PREFIX, verify=True)" in src

    def test_matching_script_passes(self, monkeypatch):
        vc = importlib.import_module("voximplant.api_clients.voximplant_client")
        monkeypatch.setattr(vc, "_call", lambda m, **p: {"result": [
            {"scenario_name": p["scenario_name"], "scenario_id": 7,
             "modified": "now", "scenario_script": "src\r\n"}]})
        assert vc.read_back_scenario("x", "src\n")["matches"] is True


class TestChaseReadsThePerson:
    def test_a_recorded_twin_closes_the_row(self, monkeypatch):
        chase = importlib.import_module("pipelines.producer.chase")
        updates = []

        def fake_select(table, query=""):
            if table == "guest_applications":
                return [{"id": "4484f810"}, {"id": "33199c02"}]
            if table == "interviews":
                assert "status=in.(" in query and "published" in query
                return [{"application_id": "33199c02"}]
            return []

        monkeypatch.setattr(chase, "sb_select", fake_select)
        monkeypatch.setattr(chase, "sb_update", lambda *a: updates.append(a))
        monkeypatch.setattr(chase, "next_step", lambda app: "chase1")

        class NoGmail:
            def get_thread(self, *_):
                raise AssertionError("a closed row never reads or sends mail")

        summary = {"sent": 0, "drafted": 0, "lapsed": 0}
        line = chase.process({"id": "4484f810", "email": "stuart@example.com",
                              "email_thread_id": "t"}, gmail=NoGmail(), policy=None,
                             dry_run=False, summary=summary)
        assert line["action"] == "close"
        assert updates and updates[0][2]["producer_closed_reason"] == "already_interviewed"


class TestCorrectionReachesTheRecord:
    def test_record_fields_are_amended(self):
        ac = importlib.import_module("apply_corrections")
        record = {"id": "r1", "summary": "Michael built Pivot.",
                  "claims": [{"claim": "Pivot ships in May", "quote": "Pivot"}],
                  "predictions": [], "quotes": ["no change"]}
        patch, hits = ac.amend_record_fields(
            record, [{"replacements": [{"find": "Pivot", "replace": "Pyvot"}]}])
        assert hits == 3
        assert patch["summary"] == "Michael built Pyvot."
        assert patch["claims"][0] == {"claim": "Pyvot ships in May", "quote": "Pyvot"}
        assert "quotes" not in patch and "predictions" not in patch

    def test_only_interview_shows_touch_supabase(self):
        ac = importlib.import_module("apply_corrections")
        assert ac.amend_episode_record("tesla", 1, [], apply=True) == 0


class TestEchoLabelsAreNeverReactions:
    def test_the_three_rooms_reactions(self):
        am = importlib.import_module("audio_metrics")
        for text in ("Cold distance. What did the crew do next?",
                     "Carrying it. Who carried it after you?",
                     "Standing inside it. And then what?"):
            assert am.question_turn_shape(text) == "label", text
        assert am.question_turn_shape("Right, carrying it. What next?") == "bare"


class TestRoomOffsetsAnyPython:
    def test_one_digit_fractions_parse(self):
        post = importlib.import_module("post_interview")
        off = post.room_offsets({"scenario_trace": [
            {"t": "2026-09-12T00:26:57.7Z", "e": "room", "d": "opened (webrtc); mixer"},
            {"t": "2026-09-12T00:32:11.2Z", "e": "leg", "d": "guest #2 joined (2 in room)"},
        ]})
        assert abs(off["guest"] - 313.5) < 1.0
        src = (ROOT / "pipelines" / "voices" / "post_interview.py").read_text()
        assert 'ljust(6, "0")' in src
