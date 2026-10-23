"""A refused camera never stops a guest joining (Oct 23 2026).

Patrick's test room: the preview used his camera and microphone, the echo
check ran, and pressing Join failed with "The call didn't go through (Media
access denied)" — the call asked for the camera again and a refusal failed
the whole call. The interview is the audio, so a refused camera joins
without it, once; a refused microphone gets the permission steps.
"""

import re
from pathlib import Path

STUDIO = Path(__file__).resolve().parents[1] / "age-of-ai-studio.html"


def _page() -> str:
    return STUDIO.read_text(encoding="utf-8")


def test_there_is_one_place_a_call_is_made():
    assert len(re.findall(r"sdk\.call\(", _page())) == 1
    assert "function placeCall(sendVideo)" in _page()


def test_a_failed_call_goes_through_the_media_check():
    page = _page()
    assert "call.on(VoxImplant.CallEvents.Failed, onCallFailed)" in page
    body = page.split("function onCallFailed(e)", 1)[1].split("\n  }\n", 1)[0]
    assert "callSentVideo && !audioOnlyRetried" in body
    assert "placeCall(false)" in body
    assert "audioOnlyRetried = true" in body  # once, never a loop


def test_a_refused_microphone_says_how_to_allow_it():
    body = _page().split("function onCallFailed(e)", 1)[1].split("\n  }\n", 1)[0]
    assert "allow the microphone" in body
    assert "Privacy & Security" in body


def test_the_media_check_names_the_browser_refusals():
    m = re.search(r"function isMediaRefusal\(e\) \{\s*return /([^/]+)/i", _page())
    assert m, "isMediaRefusal must test the failure reason"
    pattern = re.compile(m.group(1), re.I)
    for reason in ("Media access denied", "NotAllowedError", "NotReadableError",
                   "OverconstrainedError"):
        assert pattern.search(reason), reason
    assert not pattern.search("Busy here")


def test_the_call_waits_for_the_preview_to_release_its_devices():
    join = _page().split("async function join()", 1)[1].split("\n  }\n", 1)[0]
    assert "setTimeout(r, 400)" in join
    assert join.index("selectCallDevices") < join.index("placeCall(")
