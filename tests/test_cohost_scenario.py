"""Phase 2 co-host contracts for the Voximplant scenario + Management client.

docs/cohost_phase2_contract.md: every Mira interview is a three-party local
conference (guest + Patrick as host + Mira), each participant recorded on
its own track, the host dialed with VoxEngine.callUser and re-dialed every
20 s while the guest is on the line, and Mira's opening delayed until the
host is in the room (or 20 s). These are string contracts on the scenario
source (VoxEngine JS is not importable here) plus a mocked check of the
``add_user`` bootstrap helper.
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


# ---------------------------------------------------------------------------
# Conference mixer
# ---------------------------------------------------------------------------

class TestConference:
    def test_conference_module_required(self, js):
        assert "require(Modules.Conference)" in js
        # The existing modules must survive the rewrite.
        assert "require(Modules.Grok)" in js
        assert "require(Modules.Recorder)" in js

    def test_local_conference_created_hd(self, js):
        assert "VoxEngine.createConference({ hd_audio: true })" in js

    def test_guest_added_with_documented_endpoint_shape_and_fallback(self, js):
        assert "function attachToConference(" in js
        assert re.search(
            r"conf\.add\(\{\s*call:\s*participant,\s*mode:\s*CONF_ENDPOINT_MODE,"
            r"\s*direction:\s*\"BOTH\"\s*\}\)", js), "conf.add({call, mode, direction})"
        assert 'CONF_ENDPOINT_MODE = "MIX"' in js
        # Fallback path when conf.add is not the live shape.
        assert "VoxEngine.sendMediaBetween(participant, conf)" in js
        assert 'attachToConference(call, "guest")' in js

    def test_mira_bridged_to_conference_not_directly_to_guest(self, js):
        assert "VoxEngine.sendMediaBetween(grokAgent, conf)" in js
        assert "VoxEngine.sendMediaBetween(call, grokAgent)" not in js, (
            "Phase 2: Mira talks to the conference, not the guest leg")

    def test_pstn_branch_also_gets_the_conference(self, js):
        # Both entries converge on beginInterview, which creates the conf
        # unconditionally (before any withVideo branch).
        body = js.split("async function beginInterview")[1].split("function silentMicNudge")[0]
        assert "createLocalConference();" in body
        assert body.index("createLocalConference();") > body.index("if (withVideo)")
        assert "dialHost();" in body


# ---------------------------------------------------------------------------
# Per-leg recording
# ---------------------------------------------------------------------------

class TestRecording:
    def test_guest_recording_unchanged(self, js):
        assert re.search(r'call\.record\(\{\s*name:\s*"aoa_"\s*\+\s*runId,\s*'
                         r'stereo:\s*true,\s*hd_audio:\s*true,\s*\}\)', js)

    def test_host_recording_stereo_hd(self, js):
        assert re.search(r'leg\.record\(\{\s*name:\s*"aoa_"\s*\+\s*runId\s*\+\s*"_host",\s*'
                         r'stereo:\s*true,\s*hd_audio:\s*true,\s*\}\)', js)
        assert "hostRecordUrl = e.url" in js, "host RecordStarted must be captured"

    def test_mira_recorder(self, js):
        assert re.search(r'miraRecorder = VoxEngine\.createRecorder\(\{\s*'
                         r'name:\s*"aoa_"\s*\+\s*runId\s*\+\s*"_mira",\s*hd_audio:\s*true,\s*\}\)', js)
        assert "grokAgent.sendMediaTo(miraRecorder)" in js
        assert "miraRecordUrl = e.url" in js
        assert "miraRecorder.stop()" in js

    def test_video_recorder_still_gets_mira(self, js):
        assert "grokAgent.sendMediaTo(videoRecorder)" in js
        assert "call.sendMediaTo(videoRecorder)" in js


# ---------------------------------------------------------------------------
# Host leg
# ---------------------------------------------------------------------------

class TestHostLeg:
    def test_call_user_shape(self, js):
        m = re.search(r"VoxEngine\.callUser\(\{(.*?)\}\);", js, re.S)
        assert m, "host leg must be dialed with VoxEngine.callUser"
        params = m.group(1)
        assert "username: hostUser" in params
        assert 'callerid: "mira"' in params
        assert 'displayName: "Mira"' in params
        assert "video: false" in params
        assert '"X-Run-Id": runId' in params
        assert '"X-Role": "host"' in params

    def test_host_user_from_run_row_with_default(self, js):
        assert 'DEFAULT_HOST_USER = "host"' in js
        assert "hostUser = config.host_user || DEFAULT_HOST_USER" in js

    def test_host_mode_false_disables_leg(self, js):
        assert "hostMode = config.host_mode !== false" in js
        assert "if (hostMode) {" in js and "dialHost();" in js

    def test_leg_events_posted(self, js):
        assert 'API_BASE + "/leg-event"' in js
        assert 'postLegEvent("guest", "joined")' in js
        assert 'postLegEvent("host", "joined")' in js
        assert 'postLegEvent("host", "left")' in js
        assert "JSON.stringify({ run_id: runId, role: role, event: event })" in js

    def test_redial_every_20s_capped_at_60(self, js):
        assert "HOST_REDIAL_MS = 20 * 1000" in js
        assert "HOST_MAX_ATTEMPTS = 60" in js
        assert "hostAttempts >= HOST_MAX_ATTEMPTS" in js
        assert "hostAttempts++" in js
        assert "}, HOST_REDIAL_MS);" in js
        # Both Failed (host not online) and Disconnected (host dropped) re-dial.
        block = js.split("function dialHost()")[1].split("function openWhenReady")[0]
        assert "CallEvents.Failed" in block and "CallEvents.Disconnected" in block
        assert "scheduleHostRedial()" in block

    def test_redial_only_while_guest_on_line(self, js):
        assert "function guestOnLine()" in js
        block = js.split("function scheduleHostRedial()")[1].split("function onHostConnected")[0]
        assert "!guestOnLine()" in block

    def test_host_hung_up_on_guest_disconnect_before_webhook(self, js):
        assert "function teardownCohost()" in js
        assert "hostCall.hangup()" in js
        handler = js.split("CallEvents.Disconnected, async function")[1].split("CallEvents.Failed")[0]
        assert handler.index("teardownCohost();") < handler.index("await fireWebhook(")
        assert 'status: "completed"' in handler


# ---------------------------------------------------------------------------
# Mira's opening waits for the host (or 20 s)
# ---------------------------------------------------------------------------

class TestOpening:
    def test_open_when_ready_guard(self, js):
        assert "function openWhenReady(" in js
        body = js.split("function openWhenReady(")[1].split("function postLegEvent")[0]
        assert "if (openingFired || !sessionReady || !grokAgent) return;" in body
        assert "openingFired = true;" in body
        assert "grokAgent.responseCreate({});" in body
        assert "startTimeChecks();" in body

    def test_opening_triggers(self, js):
        assert "OPENING_WAIT_MS = 20 * 1000" in js
        session = js.split("Grok.VoiceAgentAPIEvents.SessionUpdated")[1].split("InputAudioBufferSpeechStarted")[0]
        assert "sessionReady = true;" in session
        assert "openingTimer = setTimeout(" in session and "OPENING_WAIT_MS" in session
        host = js.split("function onHostConnected(")[1].split("function onHostGone(")[0]
        assert 'openWhenReady("host joined")' in host
        # The bare responseCreate that used to open on SessionUpdated is gone.
        assert session.count("grokAgent.responseCreate({})") == 0


# ---------------------------------------------------------------------------
# Webhook payload + unchanged guards
# ---------------------------------------------------------------------------

class TestWebhook:
    def test_payload_keys(self, js):
        handler = js.split("CallEvents.Disconnected, async function")[1].split("CallEvents.Failed")[0]
        for key in ("voximplant_host_record_url: hostRecordUrl",
                    "voximplant_mira_record_url: miraRecordUrl",
                    "host_joined_at: hostJoinedAt",
                    "host_left_at: hostLeftAt",
                    "host_attempts: hostAttempts",
                    "voximplant_record_url: recordUrl",
                    "voximplant_video_url: videoRecordUrl"):
            assert key in handler, key

    def test_join_timestamps_are_iso(self, js):
        assert "hostJoinedAt = new Date().toISOString()" in js
        assert "hostLeftAt = new Date().toISOString()" in js

    def test_hard_cap_and_time_checks_unchanged(self, js):
        assert "50 * 60 * 1000" in js
        assert "TIME_CHECK_EVERY_MS = 5 * 60 * 1000" in js
        assert "webhookFired" in js

    def test_barge_in_kept(self, js):
        assert "InputAudioBufferSpeechStarted" in js
        assert "grokAgent.clearMediaBuffer()" in js


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
