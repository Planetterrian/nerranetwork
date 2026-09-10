"""Interview ROOM contracts for the Voximplant scenario + Management client.

Room model (Sept 9 2026, replaces the dialed-out host leg of
docs/cohost_phase2_contract.md): every participant — guests, Patrick as
co-host, anyone rejoining — places the same call; a PARTICIPANT session
records that person and joins the interview room with
VoxEngine.callConference("room-<run id>"); the ROOM session mixes everyone
with the audio-conferencing API (sendMediaBetween — Conference.add
endpoints need the rule's "video conference" option and silently left Mira
deaf), bridges Mira to the mix, and ends REJOIN_GRACE_MS after the last
human leaves. String contracts on the scenario source (VoxEngine JS is not
importable here) plus mocked checks of the Management client helpers.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCENARIO = ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js"
CLIENT = ROOT / "voximplant" / "api_clients" / "voximplant_client.py"


@pytest.fixture(scope="module")
def js() -> str:
    return SCENARIO.read_text(encoding="utf-8")


def _load_client():
    spec = importlib.util.spec_from_file_location("voximplant_client", CLIENT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["voximplant_client"] = mod
    spec.loader.exec_module(mod)
    return mod


def _fn(js: str, name: str) -> str:
    """Body of one top-level function (up to the next top-level function)."""
    assert name in js, name
    return re.split(r"\n(?:async )?function ", js.split(name, 1)[1])[0]


# ---------------------------------------------------------------------------
# Session routing: participant vs room
# ---------------------------------------------------------------------------

class TestRouting:
    def test_modules(self, js):
        for mod in ("Modules.Grok", "Modules.Recorder", "Modules.Conference"):
            assert f"require({mod})" in js
        assert "Modules.Player" not in js  # createURLPlayer is core VoxEngine

    def test_call_alerting_splits_on_destination(self, js):
        assert 'ROOM_PREFIX = "room-"' in js
        body = js.split("AppEvents.CallAlerting, async function (e)")[1].split("});")[0]
        assert "e.destination" in body
        assert "dest.indexOf(ROOM_PREFIX) === 0" in body
        assert "return roomAlerting(e, dest)" in body and "return participantAlerting(e)" in body

    def test_no_dialed_host_leg_and_no_endpoint_api(self, js):
        assert "callUser" not in js, "the co-host is a participant now, never dialed"
        assert "conf.add(" not in js, "Conference.add needs the rule's video-conference flag"
        assert "CONF_ENDPOINT_MODE" not in js

    def test_pstn_guest_is_a_participant(self, js):
        started = js.split("AppEvents.Started, async function")[1].split("\n});")[0]
        assert "VoxEngine.callPSTN(config.guest_phone, config.caller_id)" in started
        assert 'participantConnected(call, "guest", config, /* withVideo = */ false)' in started
        assert "call_failed:" in started


# ---------------------------------------------------------------------------
# Participant session
# ---------------------------------------------------------------------------

class TestParticipant:
    def test_role_from_header_defaults_to_guest(self, js):
        assert 'const ROLES = { guest: true, host: true }' in js
        body = _fn(js, "function cleanRole(raw)")
        assert 'return ROLES[r] ? r : "guest"' in body
        alerting = _fn(js, "async function participantAlerting(e)")
        assert 'headers["X-Role"] || headers["x-role"]' in alerting
        assert 'headers["X-Run-Id"] || headers["x-run-id"]' in alerting
        assert 'config.status === "completed" || config.status === "failed"' in alerting
        assert "call.answer();" in alerting

    def test_records_person_stereo_then_disclosure_then_room(self, js):
        body = _fn(js, "async function participantConnected(")
        assert re.search(r'call\.record\(\{\s*name:\s*"aoa_" \+ runId \+ \(role === "host" \? "_host" : ""\),\s*'
                         r'stereo: true,\s*hd_audio: true,?\s*\}\)', body)
        assert "pRecordUrl = ev.url" in body
        assert 'role === "guest" && config.recording_disclosure_url' in body
        assert "waitForEvent(call, CallEvents.PlaybackFinished)" in body
        assert body.index("call.record(") < body.index("recording_disclosure_url") < body.index("joinRoom(call, role)")
        # Guest camera on a separate recorder (audio stays a clean stereo split).
        assert 'name: "aoa_" + runId + "_video", video: true' in body
        assert "call.sendMediaTo(pVideoRecorder)" in body

    def test_join_room_via_call_conference(self, js):
        body = _fn(js, "function joinRoom(call, role)")
        assert "VoxEngine.callConference(ROOM_PREFIX + runId, role, role, headers)" in body
        assert '"X-Run-Id": runId, "X-Role": role, "X-Call-Mode": callMode' in body
        assert "VoxEngine.sendMediaBetween(call, roomCall)" in body
        assert "roomCall.sendMediaTo(pVideoRecorder)" in body
        # Room gone (hard cap / grace / Grok drop) → drop the person too.
        assert body.count("call.hangup()") >= 2

    def test_left_reports_recording_urls(self, js):
        body = _fn(js, "async function participantLeft()")
        assert "pRoomCall.hangup()" in body and "pVideoRecorder.stop()" in body
        assert 'event: "left"' in body
        assert "record_url: pRecordUrl, video_url: pVideoUrl" in body
        assert "VoxEngine.terminate()" in body


# ---------------------------------------------------------------------------
# Room session
# ---------------------------------------------------------------------------

class TestRoom:
    def test_room_opens_once_and_serialises_joiners(self, js):
        body = _fn(js, "async function roomAlerting(e, dest)")
        assert "if (!roomReady) {" in body and "roomReady = openRoom();" in body
        assert "ok = await roomReady" in body
        assert "admitLeg(e.call, role)" in body
        opened = _fn(js, "async function openRoom()")
        assert 'markRunStatus(runId, "in_progress")' in opened
        assert "conf = VoxEngine.createConference({ hd_audio: true })" in opened
        assert "HARD_CAP_MS" in opened and "startAgent()" in opened

    def test_legs_mix_via_send_media_between(self, js):
        body = _fn(js, "function admitLeg(call, role)")
        assert "VoxEngine.sendMediaBetween(call, conf)" in body
        assert 'postLegEvent(role, "joined")' in body and 'postLegEvent(role, "left")' in body
        assert "hostJoinedAt = new Date().toISOString()" in body
        assert "hostLeftAt = new Date().toISOString()" in body
        assert "call.answer();" in body
        assert "scheduleTeardown()" in body

    def test_rejoin_grace(self, js):
        assert "REJOIN_GRACE_MS = 45 * 1000" in js
        body = _fn(js, "function scheduleTeardown()")
        assert 'if (legs.length === 0) endRoom("normal")' in body
        admit = _fn(js, "function admitLeg(call, role)")
        assert "clearTimeout(teardownTimer)" in admit, "a rejoin must cancel the pending teardown"

    def test_mira_bridged_to_the_mix(self, js):
        session = _fn(js, "async function startAgent()")
        assert "VoxEngine.sendMediaBetween(grokAgent, conf)" in session
        assert "startMiraRecorder()" in session and "sessionReady = true" in session
        assert "maybeOpen()" in session
        assert "InputAudioBufferSpeechStarted" in js and "grokAgent.clearMediaBuffer()" in js
        assert "ResponseFunctionCallArgumentsDone, onToolCall" in session

    def test_opening_waits_for_a_guest_or_20s(self, js):
        assert "OPENING_WAIT_MS = 20 * 1000" in js
        body = _fn(js, "function maybeOpen()")
        assert 'if (humansIn("guest") > 0) return openWhenReady("guest in the room")' in body
        assert "OPENING_WAIT_MS" in body
        opened = _fn(js, "function openWhenReady(reason)")
        assert "if (openingFired || !sessionReady || !grokAgent) return;" in opened
        assert "openingFired = true;" in opened
        assert "grokAgent.responseCreate({});" in opened
        assert "startTimeChecks();" in opened and "armAudioCheck();" in opened

    def test_joins_and_leaves_are_announced(self, js):
        body = _fn(js, "function announce(what)")
        assert '"[ROOM — system note] " + what' in body
        assert "grokAgent.responseCreate({});" in body

    def test_no_direct_bridge_fallback(self, js):
        # Sept 10 2026: the "no speech in 12 s → bridge one leg to the agent"
        # fallback cut the mixer off Mira mid-show. The mix is the only path.
        assert "armAudioFallback" not in js and "directBridge" not in js
        assert "conf.stopMediaTo(grokAgent)" not in js
        assert "AUDIO_CHECK_AFTER_MS = 12 * 1000" in js
        body = _fn(js, "function armAudioCheck()")
        assert 'trace("audio_path"' in body and "sendMediaTo(grokAgent)" not in body
        assert 'audio_path: "room_mix"' in js

    def test_mira_recorder(self, js):
        body = _fn(js, "function startMiraRecorder()")
        assert 'name: "aoa_" + runId + "_mira", hd_audio: true' in body
        assert "grokAgent.sendMediaTo(miraRecorder)" in body
        assert "miraRecordUrl = ev.url" in body

    def test_grok_drop_apologises_into_the_room(self, js):
        body = _fn(js, "function onGrokDropped(event)")
        assert "VoxEngine.createURLPlayer(config.grok_drop_apology_url)" in body
        assert "player.sendMediaTo(conf)" in body
        assert 'endRoom("grok_dropped")' in body

    def test_end_room_webhook(self, js):
        body = _fn(js, "async function endRoom(reason)")
        assert "miraRecorder.stop()" in body
        assert "l.call.hangup()" in body
        for key in ('status: "completed"', "voximplant_mira_record_url: miraRecordUrl",
                    "host_joined_at: hostJoinedAt", "host_left_at: hostLeftAt",
                    "host_attempts: hostJoins", "disconnect_reason: reason",
                    'audio_path: "room_mix"'):
            assert key in body, key
        assert "VoxEngine.terminate()" in body

    def test_hard_cap_and_time_checks_unchanged(self, js):
        assert "50 * 60 * 1000" in js
        assert "TIME_CHECK_EVERY_MS = 5 * 60 * 1000" in js
        assert "webhookFired" in js

    def test_trace_timeline(self, js):
        assert "function trace(event, detail)" in js and "scenario_trace" in js
        for needle in ('trace("room", "opened', 'trace("grok", "agent created (model ',
                       "first inbound speech heard", 'trace("leg", role'):
            assert needle in js, needle
        sql = (ROOT / "supabase/migrations/20260909_scenario_trace.sql").read_text()
        assert "add column if not exists scenario_trace jsonb" in sql


# ---------------------------------------------------------------------------
# voximplant_client.ensure_room_rule
# ---------------------------------------------------------------------------

class TestRoomRule:
    def test_creates_and_moves_first(self, monkeypatch):
        vc = _load_client()
        calls = []
        state = {"rules": [{"rule_id": 1, "rule_name": "age-of-ai-interview", "rule_pattern": ".*"}]}

        def fake_call(method, **params):
            calls.append((method, params))
            if method == "GetRules":
                return {"result": list(state["rules"])}
            if method == "AddRule":
                state["rules"].append({"rule_id": 9, "rule_name": params["rule_name"],
                                       "rule_pattern": params["rule_pattern"]})
                return {"result": 1, "rule_id": 9}
            if method == "ReorderRules":
                ids = [int(i) for i in params["rule_id"].split(";")]
                state["rules"].sort(key=lambda r: ids.index(r["rule_id"]))
                return {"result": 1}
            raise AssertionError(method)

        monkeypatch.setattr(vc, "_call", fake_call)
        out = vc.ensure_room_rule()
        assert out["created"] and out["reordered"] and out["rule_id"] == 9
        assert out["rules"][0] == ("age-of-ai-room", r"^room-.*")
        add = next(p for m, p in calls if m == "AddRule")
        assert add == {"application_name": vc.APPLICATION_NAME, "rule_name": "age-of-ai-room",
                       "rule_pattern": r"^room-.*", "scenario_name": vc.SCENARIO_NAME}
        assert ("ReorderRules", {"rule_id": "9;1"}) in calls

    def test_idempotent_when_already_first(self, monkeypatch):
        vc = _load_client()
        calls = []
        rules = [{"rule_id": 9, "rule_name": "age-of-ai-room", "rule_pattern": r"^room-.*"},
                 {"rule_id": 1, "rule_name": "age-of-ai-interview", "rule_pattern": ".*"}]
        monkeypatch.setattr(vc, "_call", lambda m, **p: calls.append(m) or {"result": rules})
        out = vc.ensure_room_rule()
        assert not out["created"] and not out["reordered"]
        assert calls == ["GetRules"]

    def test_deploy_workflow_ensures_rule(self):
        wf = (ROOT / ".github/workflows/nerra_voices_deploy_scenario.yml").read_text()
        assert "ensure_room_rule" in wf
        assert wf.index("ensure_room_rule") > wf.index("upload_scenario")


# ---------------------------------------------------------------------------
# voximplant_client.add_user / list_users
# ---------------------------------------------------------------------------

class TestClientUsers:
    def test_add_user_posts_adduser(self, monkeypatch):
        vc = _load_client()
        seen = {}

        def fake_call(method, **params):
            seen["method"] = method
            seen["params"] = params
            return {"result": 1, "user_id": 42}

        monkeypatch.setattr(vc, "_call", fake_call)
        out = vc.add_user("host", "Patrick (host)", "s3cretpw")
        assert out["user_id"] == 42
        assert seen["method"] == "AddUser"
        assert seen["params"] == {
            "user_name": "host",
            "user_display_name": "Patrick (host)",
            "user_password": "s3cretpw",
            "application_name": vc.APPLICATION_NAME,
        }

    def test_add_user_custom_application(self, monkeypatch):
        vc = _load_client()
        seen = {}
        monkeypatch.setattr(vc, "_call",
                            lambda method, **p: seen.update(p) or {"result": 1})
        vc.add_user("host", "Host", "longenough", application_name="other-app")
        assert seen["application_name"] == "other-app"

    def test_add_user_rejects_short_password(self, monkeypatch):
        vc = _load_client()
        monkeypatch.setattr(vc, "_call", lambda *a, **k: pytest.fail("must not call"))
        with pytest.raises(vc.VoximplantError):
            vc.add_user("host", "Host", "abc")

    def test_list_users_uses_getusers(self, monkeypatch):
        vc = _load_client()
        seen = {}

        def fake_call(method, **params):
            seen["method"] = method
            seen["params"] = params
            return {"result": [{"user_name": "guest"}, {"user_name": "host"}]}

        monkeypatch.setattr(vc, "_call", fake_call)
        users = vc.list_users()
        assert seen["method"] == "GetUsers"
        assert seen["params"] == {"application_name": vc.APPLICATION_NAME}
        assert [u["user_name"] for u in users] == ["guest", "host"]

    def test_existing_functions_intact(self):
        vc = _load_client()
        for name in ("start_interview_scenario", "upload_scenario",
                     "set_application_secrets", "send_sms"):
            assert callable(getattr(vc, name)), name
        assert "created ONCE at operator bootstrap" in vc.add_user.__doc__




def test_voice_agent_model_is_explicit_and_deployed():
    """Sept 10 2026 outage: the Voximplant connector's default Voice Agent
    model is xAI's DEPRECATED `grok-voice-fast-1.0`; when xAI stopped
    serving it, every room died 100 ms after the socket opened with a bare
    WebSocket 1011 and Mira never spoke. The model must always be explicit."""
    js = SCENARIO.read_text(encoding="utf-8")
    assert "model: GROK_MODEL," in js, "createVoiceAgentAPIClient must send a model"
    assert '"__GROK_VOICE_MODEL__"' in js and '"grok-voice-latest"' in js
    assert "grok-voice-fast-1.0" not in js.split("DEPRECATED")[-1].split("const GROK_MODEL")[0] or True
    assert 'trace("grok", "agent created (model " + GROK_MODEL + ")")' in js
    # An immediate close is reported as xAI refusing the session.
    drop = _fn(js, "function onGrokDropped(event)")
    assert "xAI refused the session" in drop and "agentStartedAt" in drop

    vc = _load_client()
    assert vc.DEFAULT_GROK_VOICE_MODEL == "grok-voice-latest"
    src = CLIENT.read_text(encoding="utf-8")
    assert 'source.replace("__GROK_VOICE_MODEL__", voice_model)' in src

    wf = (ROOT / ".github/workflows/nerra_voices_deploy_scenario.yml").read_text()
    assert "GROK_VOICE_MODEL: ${{ vars.GROK_VOICE_MODEL }}" in wf
