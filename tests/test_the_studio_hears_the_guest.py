"""Sept 28 2026, Elliot. His microphone sent -40 to -55 dB for the first
hundred seconds; the meter moved a sliver, he joined, Mira heard nothing and
asked whether he was there, and he left sure his microphone worked. Nobody
on our side knew until the cancellation.

Five things change, and these tests hold them in place:
  1. Join waits for a spoken sentence measured loud enough.
  2. In the call, silence shows a yellow box and a microphone switcher, and
     Mira says exactly what to do instead of "are you there?".
  3. After 30 s of silence the guest can press "Have Mira call my phone".
  4. Patrick is emailed the moment nothing is heard.
  5. A day-before setup test, linked from the prep and reminder emails.
And one bug found on the way: the studio never applied the guest's chosen
microphone to the call at all.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDIO = (ROOT / "age-of-ai-studio.html").read_text(encoding="utf-8")
WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")
SCENARIO = (ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js").read_text(encoding="utf-8")
BRIEF_T = (ROOT / "templates" / "email" / "voices_prep_brief.j2").read_text(encoding="utf-8")
BRIEFS = (ROOT / "pipelines" / "voices" / "generate_briefs.py").read_text(encoding="utf-8")
FIRE = (ROOT / "pipelines" / "voices" / "fire_interviews.py").read_text(encoding="utf-8")


def _script() -> str:
    return STUDIO[STUDIO.index("<script>\n(function"):STUDIO.rindex("</script>")]


def _body(src: str, start: str, end: str) -> str:
    s = src[src.index(start):]
    return s[:s.index(end)]


class TestTheChosenMicrophoneReachesTheCall:
    def test_no_single_argument_call_settings(self):
        # setCallAudioSettings(call, params): with params alone it rejected
        # silently and every call used the system default microphone.
        assert not re.search(r"setCallAudioSettings\(\s*\{", STUDIO)
        assert "setDefaultAudioSettings(Object.assign(" in STUDIO
        assert "setCallAudioSettings(activeCall," in STUDIO
        assert not re.search(r"setCallVideoSettings\(\s*\{", STUDIO)


class TestJoinWaitsForARealMicrophoneCheck:
    def test_thresholds_and_measurement(self):
        assert "var MIC_OK_DB = -42;" in STUDIO
        assert "getFloatTimeDomainData" in STUDIO
        assert "frames.length * 0.85" in STUDIO

    def test_join_is_locked_until_it_passes(self):
        gate = _body(STUDIO, "function updateJoinGate()", "document.getElementById(\"joinAnyway\")")
        assert "btn.disabled = !open;" in gate
        assert "micOk || joinOverride" in gate
        assert "if (!isHost && !micOk && !joinOverride) return;" in STUDIO

    def test_help_is_plain_and_there_is_a_way_through(self):
        for words in ("Pick another microphone", "Input volume", "not your phone",
                      "Join from my phone instead", "Pick another time"):
            assert words in STUDIO
        assert "Have Mira call my phone" not in STUDIO   # Oct 27 2026: no phone calls
        assert "micFails < 2" in STUDIO          # "Join anyway" after two honest tries
        assert 'reportCheck("skipped")' in STUDIO

    def test_changing_microphone_needs_a_new_check(self):
        sw = _body(STUDIO, "function switchDevices(changed)", "document.getElementById(\"micSel\").addEventListener")
        assert "micOk = false" in sw
        # Oct 27 2026 (Elliot Justin): only a change of MICROPHONE resets the
        # check; the camera (its select or the toggle) never does.
        assert sw.index('if (changed !== "mic") return;') < sw.index("micOk = false")
        wiring = _body(STUDIO, 'document.getElementById("micSel").addEventListener', "function meterMic()")
        assert 'switchDevices("mic")' in wiring
        assert wiring.count('switchDevices("camera")') == 2


class TestSilenceInTheCall:
    def test_watchdog_timings(self):
        assert "BANNER_NEVER_MS = 15000, PHONE_NEVER_MS = 30000" in STUDIO
        assert 'id="silenceBanner"' in STUDIO and 'id="micSelCall"' in STUDIO
        assert "You're on mute." in STUDIO

    def test_the_studio_reports_silence(self):
        assert 'API + "/studio-silence"' in STUDIO

    def test_mira_says_what_to_do(self):
        nudge = _body(SCENARIO, "function silentMicNudge(", "\n}\n")
        assert 'Do NOT ask \\"are you there?\\"' in nudge
        line = _body(SCENARIO, "function silentMicHelpLine(", "\n}\n")
        assert "yellow box" in line and "phone's browser" in line
        for offer in ("call my phone", "call you", "ring you"):   # Oct 27 2026: no phone calls
            assert offer not in line.lower()
        assert "postSilenceAlert(" in nudge
        assert "const SILENT_MIC_AFTER_MS = 25 * 1000;" in SCENARIO

    def test_scenario_parses(self):
        subprocess.run(["node", "--check", str(ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js")],
                       check=True)


class TestTheWorker:
    def test_routes(self):
        for route in ("studio-check", "studio-silence", "studio-phone", "studio-reschedule"):
            assert f'path === "/voices/{route}"' in WORKER

    def test_silence_emails_patrick_once_per_run(self):
        body = _body(WORKER, "async function handleStudioSilence(", "function handleStudioPhoneRetired(")
        assert "if (alerts.length) return json({ ok: true, already_alerted: true });" in body
        assert "operatorEmail(env)" in body

    def test_the_phone_switch_is_retired(self):
        # Oct 27 2026: nothing in the Worker can make an interview a phone
        # interview any more.
        body = _body(WORKER, "function handleStudioPhoneRetired(", "async function handleStudioReschedule(")
        assert "410" in body
        assert 'call_mode: "pstn"' not in WORKER
        assert 'path === "/voices/studio-phone") return handleStudioPhoneRetired();' in WORKER

    def test_failed_setup_test_emails_patrick(self):
        body = _body(WORKER, "async function handleStudioCheck(", "async function handleStudioSilence(")
        assert "setup_check:" in body
        assert "problems.length && (test ||" in body


class TestTheDayBeforeTest:
    def test_studio_test_mode(self):
        assert 'params.get("test") === "1"' in STUDIO
        assert "function startTest(" in STUDIO
        assert "You're all set." in STUDIO

    def test_emails_link_it(self):
        assert "setup_test_link" in BRIEF_T
        assert "setup_test_link=setup_test_url(" in BRIEFS
        assert "&test=1" in BRIEFS
        assert "&test=1" in FIRE and '+ "&role=guest"' in FIRE
