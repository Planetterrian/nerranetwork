"""Oct 27 2026: no phone-call interviews, and the bugs from Elliot Justin's.

Elliot (Oct 26) passed his microphone check, turned his camera off, and the
studio reset the check and locked Join again ("New microphone selected").
He tried his phone, then pressed "Have Mira call my phone"; the call reached
him with a scam call on top, he hung up after a minute, and those 73 seconds
became an editorial package waiting for Patrick's review. Mira then answered
"Let's skip this" by repeating his complaint back to him with a cancel link.

Patrick: remove phone calls as an option (the recording quality is too poor)
and fix the bugs. A review of the studio flow found more; each is held here.
The Worker's half is in workers/voices/test/studio_only.test.ts.
"""
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))

STUDIO = (ROOT / "age-of-ai-studio.html").read_text(encoding="utf-8")
SCENARIO = (ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js").read_text(encoding="utf-8")
WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")


def _body(src: str, start: str, end: str) -> str:
    s = src[src.index(start):]
    return s[:s.index(end)]


# ---------------------------------------------------------------------------
# No phone calls anywhere a guest or Mira could see one
# ---------------------------------------------------------------------------

GUEST_SURFACES = [
    "age-of-ai-studio.html", "nerra-voices-apply.html", "age-of-ai-apply.html",
    "templates/privacy_policy.html.j2", "privacy-policy.html",
    "pipelines/voices/prompts/mira_narration.txt",
    "shows/prompts/age_of_ai_system.txt", "shows/prompts/nerra_voices_system.txt",
    "pipelines/producer/prompts/followup_reply.txt", "pipelines/producer/prompts/guest_reply.txt",
    "templates/email/producer_guest_invite.j2",
]


@pytest.mark.parametrize("path", GUEST_SURFACES)
def test_no_surface_offers_a_phone_call(path):
    text = (ROOT / path).read_text(encoding="utf-8").lower()
    for offer in ("have mira call my phone", "call my phone", "take a phone call",
                  "by phone if they prefer", "i'll call your phone", "phone fallback",
                  "recorded phone interview", "take a call on your phone"):
        assert offer not in text, (path, offer)


def test_the_how_it_works_steps_say_studio_only():
    from engine import brand
    step = dict(brand.MIRA_INTERVIEW_STEPS)["You talk to Mira"]
    assert "phone's browser" in step and "take a call" not in step
    for page in ("mira.html", "press.html", "age-of-ai.html", "nerra-voices.html"):
        assert "take a call on your phone" not in (ROOT / page).read_text(encoding="utf-8")


def test_the_apply_pages_say_there_are_no_phone_interviews():
    for page in ("nerra-voices-apply.html", "age-of-ai-apply.html"):
        html = (ROOT / page).read_text(encoding="utf-8")
        assert "There are no phone-call interviews." in html
        assert "as a backup if the browser studio fails" not in html


def test_the_scenario_refuses_a_phone_start_and_says_nothing_about_calling():
    started = SCENARIO.split("AppEvents.Started, async function")[1].split("\n});")[0]
    assert "callPSTN" not in SCENARIO
    assert "phone interviews are no longer offered" in started
    line = _body(SCENARIO, "function silentMicHelpLine(", "\n}\n")
    assert "phone's browser" in line and "call my phone" not in line


def test_fire_interviews_never_dials():
    src = (ROOT / "pipelines" / "voices" / "fire_interviews.py").read_text(encoding="utf-8")
    assert "start_interview_scenario" not in src
    assert "phone_mode" not in src
    assert 'raise RuntimeError("no caller_id' not in src      # no longer needed to stage a studio
    assert "call_guest_link" not in src


def test_the_producer_never_offers_a_call():
    from pipelines.producer import guest_reply as g
    assert "Have Mira call" not in (ROOT / "pipelines/producer/guest_reply.py").read_text()
    reply = g.live_trouble_reply({"name": "Elliot Justin"}, {"id": "iv1", "call_mode": "pstn"},
                                 type("S", (), {"studio_url": lambda self, i: f"https://x/studio?interview={i}"})())
    assert "studio" in reply and "calling your phone" not in reply and "phone's browser" in reply


# ---------------------------------------------------------------------------
# The studio page
# ---------------------------------------------------------------------------

class TestTheStudio:
    def test_the_camera_never_resets_the_microphone_check(self):
        sw = _body(STUDIO, "function switchDevices(changed)", 'document.getElementById("micSel").addEventListener')
        assert sw.index('if (changed !== "mic") return;') < sw.index("micOk = false")
        assert 'document.getElementById("camToggle").addEventListener("click", function () {' in STUDIO
        toggle = _body(STUDIO, 'document.getElementById("camToggle").addEventListener("click"', "function meterMic()")
        assert 'switchDevices("camera")' in toggle

    def test_a_refused_device_falls_back_to_audio_only(self):
        sw = _body(STUDIO, "function switchDevices(changed)", 'document.getElementById("micSel").addEventListener')
        assert "return navigator.mediaDevices.getUserMedia({ audio: audio });" in sw
        assert "That microphone couldn't be opened" in sw

    def test_join_waits_for_a_real_headphones_check(self):
        click = _body(STUDIO, 'document.getElementById("joinBtn").addEventListener("click"', "var joinStep")
        assert click.index("if (!isHost && !micOk && !joinOverride) return;") < click.index("echoCheck(resolve)")
        assert "before.then(function () { return join(); })" in click
        assert "finished();" in _body(STUDIO, "function echoCheck(onDone)", "document.getElementById(\"echoBtn\").addEventListener")

    def test_a_dropped_guest_is_offered_rejoin_not_a_wrap(self):
        ended = _body(STUDIO, "function onCallEnded()", "function finishDone()")
        assert "if ((!guestEnded || endedEarly) && !closedForGood)" in ended
        assert "Rejoin the interview" in ended
        assert 'roomEndReason === "hard_cap"' in ended
        assert "else guestEnded = true;" in STUDIO
        assert 'm.room === "ended"' in STUDIO

    def test_the_room_says_when_it_closes(self):
        end = _body(SCENARIO, "async function endRoom(reason)", "await sleep(1000);")
        assert 'room: "ended", reason: reason' in end
        assert end.index("sendMessage") < end.index("l.call.hangup()")

    def test_a_rejoining_guest_does_not_hear_the_consent_again(self):
        assert "config.recording_disclosure_url && !config.guest_joined_at" in SCENARIO

    def test_the_room_grace_stays_under_the_session_limit(self):
        # Voximplant ends a session with no call after 60 s; a longer grace
        # never fired its webhook (Sept 10 2026). A reviewer caught a 90 s
        # version of this change before it shipped.
        m = re.search(r"const REJOIN_GRACE_MS = (\d+) \* 1000;", SCENARIO)
        assert m and int(m.group(1)) < 60

    def test_a_failed_call_is_not_an_active_one(self):
        failed = _body(STUDIO, "function onCallFailed(e)", "function wireCall(call)")
        assert failed.index("activeCall = null;") < failed.index("placeCall(false)")

    def test_a_late_arrival_is_not_stuck_on_arrival(self):
        tick = _body(STUDIO, "function notInTick()", "function startNotIn()")
        assert "Math.max(scheduledAt, pageOpenedAt)" in tick

    def test_the_stuck_report_says_what_happened_at_join(self):
        report = _body(STUDIO, "function reportCheck(forceMic, extra)", "// ---- 2d.")
        assert "join_attempted: joinAttempted, join_error: joinError, join_override: joinOverride" in report

    def test_the_sign_in_notices_a_dead_connection(self):
        login = _body(STUDIO, "async function studioLogin()", "async function join()")
        assert "VoxImplant.Events.ConnectionClosed" in login
        join = _body(STUDIO, "async function join()", "function placeCall(")
        assert "sdk.connected && !sdk.connected()" in join

    def test_a_dead_interview_is_not_getting_ready(self):
        assert 'DEAD_INTERVIEW.indexOf(String(s.interview_status || "")) >= 0' in STUDIO
        assert "This interview isn't on right now." in STUDIO

    def test_a_guest_who_never_got_in_has_not_had_a_wrap(self):
        done = _body(STUDIO, "function finishDone()", 'document.getElementById("muteBtn")')
        assert "if (!isHost && !everConnected)" in done
        assert "This interview session has closed" in done

    def test_the_page_script_parses(self, tmp_path):
        import subprocess
        script = STUDIO[STUDIO.index("<script>\n(function"):STUDIO.rindex("</script>")][len("<script>"):]
        f = tmp_path / "studio.js"
        f.write_text(script, encoding="utf-8")
        subprocess.run(["node", "--check", str(f)], check=True)


# ---------------------------------------------------------------------------
# Post-production: a minute is not an interview
# ---------------------------------------------------------------------------

class TestTooShort:
    def test_the_rule(self):
        import post_interview as pi
        iv = {"session_kind": "interview"}
        assert pi.too_short({"duration_sec": 73, "session_kind": "interview"}, iv)
        assert not pi.too_short({"duration_sec": 2400, "session_kind": "interview"}, iv)
        assert not pi.too_short({"duration_sec": None}, iv)              # unknown: process it
        assert not pi.too_short({"duration_sec": 200, "session_kind": "hello"}, {"session_kind": "hello"})
        assert not pi.too_short({"duration_sec": 200}, {"session_kind": "closing"})

    def test_no_package_no_guest_email(self, monkeypatch):
        import post_interview as pi
        updates, pings = [], []
        monkeypatch.setattr(pi, "sb_update", lambda t, q, patch: updates.append((t, q, patch)))
        monkeypatch.setattr(pi, "notify_operator", lambda text, critical=False: pings.append(text))
        monkeypatch.setattr(pi, "send_email", lambda *a, **k: pytest.fail("the guest must not be emailed"))
        pi.handle_too_short({"id": "r1", "duration_sec": 73}, {"id": "iv1", "show": "nerra_voices"},
                            {"name": "Elliot Justin", "email": "e@x.test", "show": "nerra_voices"})
        assert updates == [("interviews", "id=eq.iv1", {"status": "missed"})]
        assert pings and "73 seconds" in pings[0] and "nothing was sent to them" in pings[0]

    def test_it_runs_before_any_recording_is_fetched(self):
        src = (ROOT / "pipelines" / "voices" / "post_interview.py").read_text(encoding="utf-8")
        main = src[src.index("def main() -> int:"):]
        assert main.index("if too_short(run, interview):") < main.index("fetch_recording(run, workdir)")


# ---------------------------------------------------------------------------
# The no-show sweep never misses a guest who was in the room
# ---------------------------------------------------------------------------

def test_the_sweep_does_not_email_a_guest_who_was_in_the_room(monkeypatch):
    import fire_interviews as F
    now = dt.datetime(2026, 10, 26, 21, 0, tzinfo=dt.timezone.utc)
    iv = {"id": "iv1", "application_id": "a1", "show": "nerra_voices", "status": "briefed",
          "scheduled_at": "2026-10-26T20:00:00+00:00", "no_show_count": 0}
    run = {"id": "r1", "status": "awaiting_guest", "guest_joined_at": "2026-10-26T20:01:00+00:00"}
    updates, pings = [], []

    def select(table, query=""):
        return {"interviews": [iv], "interview_runs": [run],
                "guest_applications": [{"id": "a1", "name": "Elliot Justin", "email": "e@x.test"}]}[table]
    monkeypatch.setattr(F, "_now", lambda: now)
    monkeypatch.setattr(F, "sb_select", select)
    monkeypatch.setattr(F, "sb_update", lambda t, q, patch: updates.append((t, patch)))
    monkeypatch.setattr(F, "send_email", lambda *a, **k: pytest.fail("no email to the guest"))
    monkeypatch.setattr(F, "notify_operator", lambda text, critical=False: pings.append(text))
    assert F.sweep_browser_no_shows() == 1
    assert ("interview_runs", {"status": "failed", "disconnect_reason": "abandoned_after_join"}) in updates
    assert ("interviews", {"status": "missed"}) in updates
    assert not any(p.get("no_show_count") for _, p in updates)
    assert pings and "was in the room earlier" in pings[0]


# ---------------------------------------------------------------------------
# Mira does not answer "let's skip this" after our failure with a cancel link
# ---------------------------------------------------------------------------

class TestAfterOurTrouble:
    def test_what_counts(self):
        from pipelines.producer.guest_reply import our_trouble
        assert our_trouble("I don't have time for tech problems. Le'ts skip this.")
        assert our_trouble("The studio didn't work for me, let's cancel")
        assert our_trouble("The connection kept dropping, can we move it")
        assert not our_trouble("No problem, can we move it to Thursday?")
        assert not our_trouble("Something came up, I need to cancel. Sorry!")
        assert not our_trouble("Sorry, I have an issue with my calendar, can we reschedule")
        # Ordinary moves must still be answered at once (Oct 7 2026).
        for plain in ("That time doesn't work for me", "I can't join on Thursday",
                      "I have another call at that time", "I'm not working that day",
                      "Sounds good, let's move it to Friday"):
            assert not our_trouble(plain), plain

    def test_a_cancel_after_our_trouble_is_held_for_patrick(self):
        src = (ROOT / "pipelines" / "producer" / "guest_reply.py").read_text(encoding="utf-8")
        guard = _body(src, "if p[\"intent\"] in (\"cancel\", \"reschedule\") and our_trouble(", "reason = \"\"")
        assert '"intent": "needs_patrick"' in guard
        prompt = (ROOT / "pipelines" / "producer" / "prompts" / "guest_reply.txt").read_text(encoding="utf-8")
        assert 'BECAUSE something went wrong on our side' in prompt
        assert "never repeat a complaint, a problem or their frustration back to them" in prompt
