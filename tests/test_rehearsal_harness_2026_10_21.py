"""The Age of AI rehearsal harness (Oct 21 2026, review §7.5).

A spoken change to Mira's room is measured against a fixture guest before
a real guest hears it. These guards pin: the persona renders from a real
published digest with no Mira line in it; the report's PASS rule; the
fixture scenario's contracts (same deploy placeholders, joins as a guest
leg, never speaks first by default); the workflow and deploy wiring.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import shutil
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
PIPELINES = ROOT / "pipelines" / "voices"
FIXTURE_JS = ROOT / "voximplant" / "scenarios" / "age_of_ai_fixture_guest.js"
INTERVIEW_JS = ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js"
CLIENT = ROOT / "voximplant" / "api_clients" / "voximplant_client.py"
WORKFLOW = ROOT / ".github" / "workflows" / "nerra_voices_rehearsal.yml"
DEPLOY = ROOT / ".github" / "workflows" / "nerra_voices_deploy_scenario.yml"

if str(PIPELINES) not in sys.path:
    sys.path.insert(0, str(PIPELINES))


@pytest.fixture(scope="module")
def rehearsal():
    spec = importlib.util.spec_from_file_location("rehearsal", PIPELINES / "rehearsal.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_client():
    spec = importlib.util.spec_from_file_location("voximplant_client", CLIENT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["voximplant_client"] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fixtures and the persona
# ---------------------------------------------------------------------------

class TestFixtures:
    def test_three_registers_on_real_digests(self, rehearsal):
        fixtures = rehearsal.load_fixtures()
        assert set(fixtures) == {"roddy", "vincent", "adrian"}
        for fid, fx in fixtures.items():
            assert (ROOT / fx["digest"]).exists(), fx["digest"]
            assert fx["voice"] != "ara", "a fixture never uses Mira's voice"
            assert fx["register"]

    def test_persona_carries_the_guest_and_no_mira_line(self, rehearsal):
        fixtures = rehearsal.load_fixtures()
        for fx in fixtures.values():
            digest = rehearsal.parse_digest(ROOT / fx["digest"])
            assert digest["name"] == fx["name"]
            assert digest["guest_lines"], "the register sample needs the guest's own lines"
            persona = rehearsal.fixture_persona(fx)
            assert fx["name"].split()[0] in persona
            assert "{about}" not in persona and "{register_sample}" not in persona
            md = (ROOT / fx["digest"]).read_text(encoding="utf-8")
            mira_lines = [re.sub(r"^\[\d+:\d+(?::\d+)?\]\s*Mira:\s*", "", ln).strip()
                          for ln in md.splitlines() if re.match(r"^\[\d+:\d+(?::\d+)?\]\s*Mira:", ln)]
            leaked = [ln for ln in mira_lines if len(ln.split()) >= 6 and ln in persona]
            assert not leaked, f"Mira's lines leaked into the persona: {leaked[:2]}"
            assert "[0" not in persona, "timestamps never reach the persona"
            assert len(persona) <= rehearsal.PERSONA_MAX_CHARS

    def test_the_persona_never_names_the_persona_as_a_model(self, rehearsal):
        text = (PIPELINES / "prompts" / "fixture_guest.txt").read_text(encoding="utf-8")
        assert "You are {guest_name}" in text
        assert "fixture" not in text.lower() and "rehearsal" not in text.lower()


# ---------------------------------------------------------------------------
# The §7.5 rule
# ---------------------------------------------------------------------------

def _rec(arm, **metrics):
    return {"arm": arm, "fixture": "roddy", "metrics": metrics, "listen_url": f"https://x/{arm}"}


class TestVerdict:
    def test_pass_when_proposed_beats_current_and_keeps_turn_length(self, rehearsal):
        records = [
            _rec("current", overlap_events=14, self_answered_turns=3,
                 guest_words_per_answer_median=40, mira_turn_sec_median=7.6),
            _rec("current", overlap_events=12, self_answered_turns=2,
                 guest_words_per_answer_median=44, mira_turn_sec_median=8.0),
            _rec("proposed", overlap_events=2, self_answered_turns=0,
                 guest_words_per_answer_median=70, mira_turn_sec_median=14.0),
            _rec("proposed", overlap_events=1, self_answered_turns=0,
                 guest_words_per_answer_median=66, mira_turn_sec_median=16.0),
        ]
        summary = rehearsal.summarise(records)
        assert summary["current"]["rooms"] == 2 and summary["proposed"]["rooms"] == 2
        result = rehearsal.verdict(summary)
        assert result["result"] == "PASS", result
        assert all(c["ok"] for c in result["checks"])

    def test_fail_when_any_required_metric_does_not_improve(self, rehearsal):
        records = [
            _rec("current", overlap_events=5, self_answered_turns=1,
                 guest_words_per_answer_median=50, mira_turn_sec_median=14),
            _rec("proposed", overlap_events=2, self_answered_turns=0,
                 guest_words_per_answer_median=45, mira_turn_sec_median=15),
        ]
        result = rehearsal.verdict(rehearsal.summarise(records))
        assert result["result"] == "FAIL"
        failed = [c["metric"] for c in result["checks"] if c["ok"] is False]
        assert failed == ["guest_words_per_answer_median"]

    def test_both_arms_at_zero_is_the_floor_not_a_loss(self, rehearsal):
        # The third rehearsal read FAIL on 0 self-answered turns against 0.
        records = [
            _rec("current", overlap_events=7, self_answered_turns=0,
                 guest_words_per_answer_median=34, mira_turn_sec_median=4.7),
            _rec("proposed", overlap_events=0, self_answered_turns=0,
                 guest_words_per_answer_median=44, mira_turn_sec_median=5.1),
        ]
        result = rehearsal.verdict(rehearsal.summarise(records))
        assert result["result"] == "PASS", result
        selfans = next(c for c in result["checks"] if c["metric"] == "self_answered_turns")
        assert selfans["ok"] and "both at zero" in selfans["rule"]
        # Zero is a floor only for a count both arms sit on: a tie above it,
        # or a proposal that adds one, still fails.
        for cur, prop in ((2, 2), (0, 1)):
            records = [
                _rec("current", overlap_events=7, self_answered_turns=cur,
                     guest_words_per_answer_median=34, mira_turn_sec_median=4.7),
                _rec("proposed", overlap_events=0, self_answered_turns=prop,
                     guest_words_per_answer_median=44, mira_turn_sec_median=5.1),
            ]
            assert rehearsal.verdict(rehearsal.summarise(records))["result"] == "FAIL"

    def test_fail_when_turn_length_moves_further_from_the_band(self, rehearsal):
        records = [
            _rec("current", overlap_events=5, self_answered_turns=1,
                 guest_words_per_answer_median=50, mira_turn_sec_median=11),
            _rec("proposed", overlap_events=2, self_answered_turns=0,
                 guest_words_per_answer_median=60, mira_turn_sec_median=6),
        ]
        result = rehearsal.verdict(rehearsal.summarise(records))
        assert result["result"] == "FAIL"
        turn = next(c for c in result["checks"] if c["metric"] == "mira_turn_sec_median")
        assert turn["ok"] is False

    def test_inconclusive_without_both_arms_or_with_a_missing_metric(self, rehearsal):
        only = [_rec("proposed", overlap_events=1, self_answered_turns=0,
                     guest_words_per_answer_median=60, mira_turn_sec_median=14)]
        assert rehearsal.verdict(rehearsal.summarise(only))["result"] == "INCONCLUSIVE"
        missing = only + [_rec("current", overlap_events=5, self_answered_turns=1,
                               mira_turn_sec_median=14)]
        assert rehearsal.verdict(rehearsal.summarise(missing))["result"] == "INCONCLUSIVE"

    def test_report_names_the_listen_rule(self, rehearsal, tmp_path):
        records = [
            _rec("current", overlap_events=5, self_answered_turns=1,
                 guest_words_per_answer_median=50, mira_turn_sec_median=14),
            _rec("proposed", overlap_events=2, self_answered_turns=0,
                 guest_words_per_answer_median=60, mira_turn_sec_median=15),
        ]
        for i, r in enumerate(records):
            (tmp_path / f"{r['arm']}_{i}.json").write_text(json.dumps(r), encoding="utf-8")
        loaded = rehearsal.load_records(tmp_path)
        assert len(loaded) == 2
        md = rehearsal.report_markdown(rehearsal.summarise(loaded),
                                       rehearsal.verdict(rehearsal.summarise(loaded)))
        assert "**PASS**" in md and "listened" in md and "https://x/proposed" in md
        assert rehearsal.main(["report", str(tmp_path)]) == 0


class TestRunRow:
    def test_run_row_is_marked_rehearsal_and_carries_the_configuration(self, rehearsal, monkeypatch):
        import fire_interviews
        monkeypatch.setattr(fire_interviews, "keyterms_for", lambda app, show, cohost="": ["Roddy"])
        monkeypatch.setattr(fire_interviews, "_clip_is_there", lambda url: True)
        row = rehearsal.build_run_row(
            interview={"id": "iv-1", "application_id": "app-1", "duration_min": 10},
            arm="proposed", fixture={"id": "roddy", "name": "Roddy de la Garza"},
            prompt="PROMPT", minutes=10, turn_silence_ms=1300,
            reasoning_effort="low", tools=[])
        assert row["session_kind"] == "rehearsal"
        assert row["status"] == "awaiting_guest" and row["host_mode"] is False
        assert row["turn_detection"] == {"silence_duration_ms": 1300}
        assert row["reasoning_effort"] == "low" and row["tools"] == []
        assert row["grok_session_log"]["rehearsal"]["arm"] == "proposed"
        assert row["planned_minutes"] == 10
        # Oct 28 2026: the test room plays the notice a guest of this show hears.
        assert row["recording_disclosure_url"].endswith("/disclosure.mp3")
        assert "_room_2026_10_28/" in row["recording_disclosure_url"]


# ---------------------------------------------------------------------------
# The fixture scenario
# ---------------------------------------------------------------------------

class TestFixtureScenario:
    @pytest.fixture(scope="class")
    def js(self):
        return FIXTURE_JS.read_text(encoding="utf-8")

    def test_same_deploy_placeholders_and_nothing_else(self, js):
        interview = INTERVIEW_JS.read_text(encoding="utf-8")
        allowed = set(re.findall(r"__[A-Z_]+__", interview))
        used = set(re.findall(r"__[A-Z_]+__", js))
        assert used, "the deploy substitutes the secrets into this file too"
        assert used <= allowed, used - allowed
        assert not re.search(r"(sk-|xai-)[A-Za-z0-9]{20,}", js)

    def test_joins_as_a_guest_leg_and_reports_it(self, js):
        assert 'VoxEngine.callConference(ROOM_PREFIX + runId, "guest", "guest", headers)' in js
        assert '"X-Role": "guest"' in js and '"X-Fixture": "1"' in js
        assert 'role: "guest"' in js and "fixture: true" in js
        assert 'LEG_EVENT_URL = API_BASE + "/leg-event"' in js

    def test_never_speaks_first_unless_told(self, js):
        # The only responseCreate is behind the speaks_first cue.
        creates = [m.start() for m in re.finditer(r"responseCreate\(", js)]
        assert len(creates) == 1
        assert js.rfind("custom.speaks_first", 0, creates[0]) > 0

    def test_behaves_like_a_person(self, js):
        for kind in ("pause_mid_thought", "cough", "let_me_think", "push_back", "ask_who"):
            assert kind in js, kind
        assert "two full seconds" in js and "sorry, you go" in js
        assert "answer only the last one" in js
        assert "Never say you are an AI, a fixture or a rehearsal" in js

    def test_its_own_voice_and_a_fixed_end_of_turn(self, js):
        assert 'String(custom.voice || "sal")' in js
        assert "DEFAULT_SILENCE_MS = 900" in js
        assert 'reasoning: { effort: "low" }' in js
        assert "tools: []" in js

    def test_leaves_on_the_clock(self, js):
        assert "MAX_MINUTES = 30" in js
        assert "finish(\"minutes_reached\")" in js
        assert 'finish("room_ended")' in js


# ---------------------------------------------------------------------------
# The Management client and the workflows
# ---------------------------------------------------------------------------

class TestClient:
    def test_start_fixture_guest_names_its_own_rule_and_carries_the_persona(self, monkeypatch):
        vc = _load_client()
        seen = {}

        def fake_call(method, **params):
            seen["method"] = method
            seen.update(params)
            return {"result": 1}

        monkeypatch.setattr(vc, "_call", fake_call)
        vc.start_fixture_guest("run-1", persona="You are Roddy.", voice="sal",
                               minutes=10, speaks_first=True, fixture_id="roddy",
                               guest_name="Roddy de la Garza", cough_clip="https://c/cough.mp3")
        assert seen["method"] == "StartScenarios"
        assert seen["rule_name"] == vc.FIXTURE_RULE_NAME != vc.RULE_NAME
        data = json.loads(seen["script_custom_data"])
        assert data["fixture"] is True and data["run_id"] == "run-1"
        assert data["persona"] == "You are Roddy." and data["speaks_first"] is True
        assert data["cough_clip"] == "https://c/cough.mp3" and data["minutes"] == 10

    def test_start_fixture_guest_refuses_an_empty_persona(self, monkeypatch):
        vc = _load_client()
        monkeypatch.setattr(vc, "_call", lambda *a, **k: {"result": 1})
        with pytest.raises(vc.VoximplantError):
            vc.start_fixture_guest("run-1", persona="  ")

    def test_fixture_rule_pattern_can_never_match_a_call(self):
        vc = _load_client()
        assert vc.FIXTURE_RULE_PATTERN == r"^fixture-guest-never-dialled$"
        assert not re.match(vc.FIXTURE_RULE_PATTERN, "room-abc")

    def test_ensure_fixture_rule_is_idempotent(self, monkeypatch):
        vc = _load_client()
        calls = []

        def fake_call(method, **params):
            calls.append(method)
            if method == "GetRules":
                return {"result": [{"rule_name": vc.FIXTURE_RULE_NAME, "rule_id": 9,
                                    "rule_pattern": vc.FIXTURE_RULE_PATTERN}]}
            return {"rule_id": 10}

        monkeypatch.setattr(vc, "_call", fake_call)
        out = vc.ensure_fixture_rule()
        assert out == {"rule_id": 9, "created": False}
        assert calls == ["GetRules"]

    def test_upload_fixture_scenario_uses_the_fixture_name(self, monkeypatch):
        vc = _load_client()
        seen = {}
        monkeypatch.setattr(vc, "upload_scenario",
                            lambda path, scenario_name=None, **kw: seen.update(
                                {"path": path, "name": scenario_name}) or {"result": 1})
        vc.upload_fixture_scenario()
        assert seen["name"] == vc.FIXTURE_SCENARIO_NAME
        assert Path(seen["path"]).name == "age_of_ai_fixture_guest.js"


class TestWorkflows:
    def test_rehearsal_workflow_inputs_and_rule(self):
        wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        inputs = wf[True]["workflow_dispatch"]["inputs"] if True in wf else wf["on"]["workflow_dispatch"]["inputs"]
        assert set(inputs) >= {"fixture", "minutes", "repeat", "arms",
                               "turn_silence_ms", "reasoning_effort", "tools"}
        assert inputs["fixture"]["options"] == ["roddy", "vincent", "adrian"]
        text = WORKFLOW.read_text(encoding="utf-8")
        assert "vars.VOICES_REHEARSAL_NIGHTLY == 'true'" in text
        assert "--arm current" in text and "--arm proposed" in text
        assert "rehearsal.py report" in text and "GITHUB_STEP_SUMMARY" in text
        # It measures; it never deploys the live room. Oct 22 2026: the
        # rehearsal-only fixture guest (and a candidate copy of the interview
        # scenario on its own prefix) may be uploaded, inside the one step
        # gated on candidate_scenario / with_hold; the live scenario and its
        # room rule are never written here.
        assert "upload_scenario(" not in text and "ensure_room_rule(" not in text
        assert "SetScenarioInfo" not in text
        assert text.count("upload_fixture_scenario()") == 1
        i = text.index("Upload this ref's fixture guest")
        step = text[i:text.index("- name:", i + 10)]
        assert "inputs.candidate_scenario || inputs.with_hold" in step
        assert "upload_fixture_scenario()" in step and "ensure_fixture_rule()" in step

    def test_deploy_uploads_the_fixture_after_the_interview_scenario(self):
        wf = DEPLOY.read_text(encoding="utf-8")
        assert "upload_fixture_scenario" in wf and "ensure_fixture_rule" in wf
        assert wf.index("upload_fixture_scenario") > wf.index("upload_scenario(path)")

    def test_results_are_never_committed(self):
        assert "outputs/rehearsals/" in (ROOT / ".gitignore").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Oct 22 2026: the guest channel is found, not assumed
# ---------------------------------------------------------------------------

def _write_wav(path, envelope_on, rate=8000, seconds=60):
    """A mono WAV with a 220 Hz tone wherever ``envelope_on(t)`` is true."""
    import wave
    import numpy as np
    t = np.arange(rate * seconds) / rate
    on = np.array([envelope_on(x) for x in t[::rate // 10]]).repeat(rate // 10)[: len(t)]
    samples = (np.sin(2 * np.pi * 220 * t) * 8000 * on).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples.tobytes())


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
class TestTheRehearsalFindsTheGuestChannel:
    """The Oct 22 rehearsal transcribed Mira's own words, a few seconds late,
    as the fixture guest's answers in both arms: on the fixture's leg the
    stereo sides are the other way round, and the report compared Mira with
    herself. The side that sounds least like her recording is the guest."""

    @staticmethod
    def _tracks(tmp_path):
        # Turns of irregular length, as speech is: Mira, then the guest, then
        # Mira again. The leg hears Mira three seconds late.
        import random
        rng = random.Random(22)
        turns, t = [], 0.0
        while t < 60:
            mira_len, guest_len = rng.uniform(1.5, 6), rng.uniform(2, 9)
            turns.append((t, t + mira_len, t + mira_len + 0.5, t + mira_len + 0.5 + guest_len))
            t += mira_len + guest_len + 1.0
        def mira_on(x):
            return any(a <= x < b for a, b, _, _ in turns)
        def guest_on(x):
            return any(c <= x < d for _, _, c, d in turns)
        mira = tmp_path / "mira.wav"
        heard = tmp_path / "heard.wav"
        guest = tmp_path / "guest.wav"
        _write_wav(mira, mira_on)
        _write_wav(heard, lambda x: mira_on(x - 3))
        _write_wav(guest, guest_on)
        return mira, heard, guest

    def test_the_guest_is_the_side_unlike_her_recording(self, rehearsal, tmp_path):
        mira, heard, guest = self._tracks(tmp_path)
        g, h, side = rehearsal.pick_guest_channel(heard, guest, mira)
        assert (g, h, side) == (guest, heard, "right")
        g, h, side = rehearsal.pick_guest_channel(guest, heard, mira)
        assert (g, h, side) == (guest, heard, "left")

    def test_without_her_recording_the_left_stays_the_guest(self, rehearsal, tmp_path):
        mira, heard, guest = self._tracks(tmp_path)
        assert rehearsal.pick_guest_channel(heard, guest, None)[2] == "left"

    def test_transcription_uses_the_picked_side(self):
        src = (PIPELINES / "rehearsal.py").read_text(encoding="utf-8")
        body = src[src.index("def transcribe_run("):src.index("def measure_room(")]
        assert "pick_guest_channel(left_wav, right_wav, mira_raw)" in body
        assert '"guest": guest_wav' in body
        assert '"guest_channel": guest_side' in body

    def test_mira_is_measured_from_what_the_guest_heard(self):
        # Her own record drops a long silence (a hold), so turns measured
        # from it slide minutes early and read as answering herself.
        src = (PIPELINES / "rehearsal.py").read_text(encoding="utf-8")
        body = src[src.index("def transcribe_run("):src.index("def measure_room(")]
        assert 'tracks = {"guest": guest_wav, "mira": heard_wav}' in body
        assert 'offsets["mira"] = offsets.get("guest", 0.0)' in body
        assert '"mira": mira_raw}' not in body.split("tracks = ", 1)[1].split("\n", 1)[0]

    def test_a_dropped_silence_would_make_her_answer_herself(self):
        # The measurement the fix avoids: the same room, with Mira's turns
        # shifted early by a vanished three-minute hold.
        from audio_metrics import self_answered
        guest = [{"start": 10, "end": 20}, {"start": 26, "end": 40},
                 {"start": 230, "end": 260},
                 {"start": 270, "end": 300}]
        mira = [{"start": 0, "end": 9}, {"start": 21, "end": 25},
                {"start": 225, "end": 229}, {"start": 261, "end": 268},
                {"start": 301, "end": 305}]
        assert self_answered(guest, mira) == 0
        early = [mira[0], mira[1]] + [{"start": m["start"] - 180, "end": m["end"] - 180}
                                       for m in mira[2:]]
        assert self_answered(guest, early) > 0


class TestRemeasure:
    def test_pairs_parse_and_reject_junk(self, rehearsal):
        a = "41187302-7fb8-453a-99cd-f1ca8dc4c94a"
        b = "1ca8839a-3e57-40dd-9db2-b9ac1bdb41a9"
        assert rehearsal.parse_remeasure(f"current:{a}, proposed:{b}") == [
            ("current", a), ("proposed", b)]
        for bad in ("nobody:" + a, "current:not-a-run", "current"):
            with pytest.raises(ValueError):
                rehearsal.parse_remeasure(bad)

    def test_the_workflow_remeasures_without_running_rooms(self):
        wf = WORKFLOW.read_text(encoding="utf-8")
        assert "remeasure:" in wf
        assert 'rehearsal.py remeasure --runs "$REMEASURE"' in wf
        for step in ("Rehearse the current configuration",
                     "Rehearse the proposed configuration",
                     "Upload this ref's interview scenario as the candidate",
                     "Upload this ref's fixture guest"):
            block = wf[wf.index(step):]
            block = block[:block.index("run:")]
            assert "inputs.remeasure == ''" in block, step
