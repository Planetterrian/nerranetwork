"""Oct 27 2026, Patrick's test room: what the studio page looked like.

1. The Join button read "Signing in…" for the whole setup: the background
   sign-in at page open wrote its steps onto the button and never put the
   label back. And "Signed in to the studio. Press Join when you're ready."
   showed before the guest had checked anything. Now the button keeps its
   label, the sign-in stays quiet for a guest unless it fails, and once the
   microphone check passes Join turns bright under a highlighted "you're
   all set".
2. The setup opened on a tall picture of Mira with the controls under it.
   The controls come first now (side by side on a computer), with Mira and
   what to expect at the foot of the card.
3. The call opened on a large picture of Mira with the steering panel at the
   bottom, and the guest never saw themselves. Steering is at the top now,
   with Mira and the guest's own camera side by side under it.
"""
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
STUDIO = (ROOT / "age-of-ai-studio.html").read_text(encoding="utf-8")


def _script():
    return STUDIO[STUDIO.index("<script>\n(function"):STUDIO.rindex("</script>")]


def _body(src, start, end):
    s = src[src.index(start):]
    return s[:s.index(end)]


def _block(state_id, next_marker):
    return _body(STUDIO, f'<div id="{state_id}"', next_marker)


class TestSignIn:
    def test_the_background_sign_in_leaves_the_button_alone(self):
        step = _body(_script(), "function step(name, label, promise) {", "function explainJoinError")
        assert "if (btn && joinInFlight) btn.textContent = label;" in step
        click = _body(_script(), 'document.getElementById("joinBtn").addEventListener("click"', "var joinStep")
        assert "joinInFlight = true;" in click
        rearm = _body(_script(), 'document.getElementById("rearmBtn").addEventListener("click"', "async function selectCallDevices")
        assert "joinInFlight = true;" in rearm
        assert "joinInFlight = false;" in _body(_script(), "function fail(msg) {", "function setPresence")

    def test_a_guest_hears_about_the_sign_in_only_if_it_fails(self):
        pre = _body(_script(), "function preLogin() {", "function wirePreview()")
        assert 'setStudioStatus("Signing in to the studio…", undefined, true);' in pre
        assert "\"Signed in to the studio. Press Join when you're ready.\", true, true);" in pre
        # The failure is not quiet.
        assert re.search(r'setStudioStatus\("Studio sign-in failed: "[^;]*, false\);', pre)
        status = _body(_script(), "function setStudioStatus(", "var preLoginPromise")
        assert "studioQuiet = !!quietForGuest && !isHost && !testMode;" in status

    def test_join_turns_bright_once_the_check_passes(self):
        gate = _body(_script(), "function updateJoinGate() {", 'document.getElementById("joinAnyway").addEventListener')
        assert 'btn.classList.toggle("ready", open);' in gate
        assert "renderReadyLine();" in gate
        ready = _body(_script(), "function renderReadyLine() {", "var preLoginPromise")
        assert "You're all set. Press Join your interview and Mira will start." in ready
        assert "#joinBtn.ready:not(:disabled)" in STUDIO
        assert 'id="studioStatus"' in _block("stateSetup", 'id="stateReady"')


class TestSetupOrder:
    def test_the_controls_come_before_mira(self):
        setup = _block("stateSetup", 'id="stateReady"')
        mira = setup.index('class="mira-intro guest-only"')
        for el in ('id="micSel"', 'id="micCheck"', 'id="echoRow"', 'id="camSel"', 'id="joinBtn"', 'id="consentNote"'):
            assert setup.index(el) < mira, el
        assert setup.index('id="micSel"') < setup.index('id="camSel"') < setup.index('id="joinBtn"')
        assert 'src="assets/mira/mira-studio.jpg"' in setup[mira:]
        assert "can't see you" in setup[mira:]

    def test_the_setup_test_still_hides_the_join_row(self):
        test = _body(_script(), "function startTest(s) {", "var lastReported")
        assert 'querySelectorAll("#joinRow, #joinGate, #consentNote, #notIn")' in test
        assert 'id="joinRow"' in STUDIO

    def test_the_page_uses_a_computer_s_width_and_a_phone_s(self):
        assert ".wrap.wide { max-width: 1080px;" in STUDIO
        assert "@media (max-width: 600px)" in STUDIO and "@media (min-width: 860px)" in STUDIO
        show = _body(_script(), "function show(id) {", "var shownState = null;")
        assert 'classList.toggle("wide", id === "stateSetup" || id === "stateCall")' in show
        assert "window.scrollTo(0, 0)" in show


class TestTheCall:
    def test_steering_on_top_then_mira_beside_the_guest_then_controls(self):
        call = _block("stateCall", 'id="stateDone"')
        steer, row, bar = call.index('id="feedbackPanel"'), call.index('id="stageRow"'), call.index('id="hangupBtn"')
        assert steer < row < bar
        stage = _body(call, 'id="stageRow"', '<p class="stage-note">')
        assert 'id="miraStage"' in stage and 'id="miraVideo"' in stage
        assert 'id="youTile"' in stage and 'id="selfview"' in stage and 'id="camOffNote"' in stage
        assert "illustration" in call and "can't see you" in call

    def test_the_guest_sees_the_camera_the_call_is_sending(self):
        js = _script()
        self_view = _body(js, "function showSelfView() {", "function hideSelfView()")
        assert "if (!callSentVideo)" in self_view
        assert "StreamManager.get().showLocalVideo(false)" in self_view
        assert "getUserMedia" not in self_view          # no second capture of the camera
        connected = _body(js, "function onCallConnected() {", "function onCallEnded()")
        assert "showSelfView();" in connected
        ended = _body(js, "function onCallEnded() {", "function finishDone()")
        assert ended.index("hideSelfView();") < ended.index("if (movedToPhone)")
        assert 'document.getElementById("stageRow").classList.toggle("solo", isHost);' in js

    def test_the_silence_warning_points_at_where_things_are_now(self):
        call = _block("stateCall", 'id="stateDone"')
        assert call.index('id="silenceBanner"') < call.index('id="feedbackPanel"')
        assert "the Mute button under the pictures" in call
        assert "Mute button above" not in call
        assert "Press Unmute under the pictures." in _script()


def test_the_page_script_parses(tmp_path):
    p = tmp_path / "studio.js"
    p.write_text(_script()[len("<script>"):], encoding="utf-8")
    subprocess.run(["node", "--check", str(p)], check=True)
