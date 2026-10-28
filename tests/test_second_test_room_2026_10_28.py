"""What Michael Kamins' room and Patrick's second test room taught (Oct 28 2026).

1. The camera worked (720p, 30 fps, one 0.25 s hiccup in 3.5 minutes,
   placed on the room's audio at +0.18 s), but the run listed no camera
   take: the page finishes its audio and video takes together, each
   upload-done read the run's log, added its take and wrote it all back, and
   the later write erased the earlier one. Takes are appended in the
   database now, and post-production finds an unlisted take in R2 anyway.
2. Asked "can you search about me?", Mira said she cannot browse. The room
   looks things up itself now; a request starts a lookup at once and her
   next turn says she will bring it in.
3. The test room played the old shared notice, so the new one (her pause,
   the camera) was never heard in a rehearsal.
4. Michael typed "we can wrap up now" in the closing round and the room ran
   five more minutes: typed words asking to finish are a stop.
5. Patrick put on AirPods after opening the room and the studio stayed on
   the laptop. The page follows a headset the guest puts on.
6. Background blur, on the guest's own computer, on what is recorded.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
V = ROOT / "pipelines" / "voices"
sys.path.insert(0, str(V))
sys.path.insert(0, str(ROOT))
SCENARIO_PATH = ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js"
SCENARIO = SCENARIO_PATH.read_text(encoding="utf-8")
SIM = ROOT / "tests" / "fixtures" / "room_sim.js"
DEVICES_SIM = ROOT / "tests" / "fixtures" / "studio_devices_sim.js"
STUDIO_PATH = ROOT / "age-of-ai-studio.html"
STUDIO = STUDIO_PATH.read_text(encoding="utf-8")
WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")
PROMPT = (V / "prompts" / "mira_system_prompt.txt").read_text(encoding="utf-8")
MIGRATION = (ROOT / "supabase" / "migrations" / "20261028_voices_append_take.sql").read_text(encoding="utf-8")

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


def sim(which: str) -> dict:
    out = subprocess.run([NODE, str(SIM), str(SCENARIO_PATH), which],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout)


def devices(which: str) -> dict:
    out = subprocess.run([NODE, str(DEVICES_SIM), str(STUDIO_PATH), which],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout)["after"]


# ---------------------------------------------------------------------------
# 1. The camera take is never lost
# ---------------------------------------------------------------------------

class TestTheTakeIsListed:
    def test_the_worker_appends_in_the_database(self):
        body = WORKER[WORKER.index("async function handleUploadDone("):]
        body = body[:body.index("\n}\n")]
        assert "await appendTake(env, runId, kind === \"video\" ? \"local_video_takes\" : \"local_takes\"" in body
        assert "grok_session_log: { ...existing" not in body, "no read-and-write of the whole log here"
        assert '"rpc/voices_append_take"' in WORKER

    def test_the_append_is_one_locked_update_and_never_doubles_a_take(self):
        assert "update interview_runs r" in MIGRATION
        assert "jsonb_array_elements" in MIGRATION and "p_take ->> 'manifest'" in MIGRATION
        assert "p_field not in ('local_takes', 'local_video_takes')" in MIGRATION
        assert "grant execute on function public.voices_append_take" in MIGRATION
        assert "to service_role" in MIGRATION

    def test_post_production_finds_an_unlisted_take(self):
        import video_take as vt
        keys = ["age_of_ai/local/r/guest-video/v1/00000.webm",
                "age_of_ai/local/r/guest-video/v1/00001.webm",
                "age_of_ai/local/r/guest-video/v1/manifest.json"]
        manifest = {"mime": "video/webm;codecs=vp9,opus", "started_at": "2026-10-28T18:41:46Z",
                    "duration_ms": 210877, "chunks": keys[:2], "missing": [], "bytes": 20}
        takes = vt.discover_takes(keys, lambda k: manifest)
        assert takes == [{"manifest": keys[2], "sid": "v1", "mime": manifest["mime"],
                          "started_at": manifest["started_at"], "duration_ms": 210877,
                          "chunks": 2, "missing": 0, "bytes": 20, "discovered": True}]

    def test_a_take_the_page_never_finished_is_adopted_up_to_its_first_gap(self):
        import video_take as vt
        keys = [f"age_of_ai/local/r/guest-video/v2/{i:05d}.webm" for i in (0, 1, 3)]
        written = {}
        takes = vt.discover_takes(keys, lambda k: None, put_json=lambda k, m: written.update({k: m}))
        assert len(takes) == 1 and takes[0]["adopted"] and takes[0]["missing"] == 1
        man = written["age_of_ai/local/r/guest-video/v2/manifest.json"]
        assert man["missing"] == ["age_of_ai/local/r/guest-video/v2/00002.webm"]
        assert vt.usable_chunks(man) == keys[:2]
        # Without leave to write a manifest, an orphan is not guessed at.
        assert vt.discover_takes(keys, lambda k: None) == []

    def test_build_uses_the_discovered_takes_when_the_row_lists_none(self, tmp_path):
        import video_take as vt
        seen = []
        out = vt.build_video_track({"grok_session_log": {}}, tmp_path / "ref.wav", tmp_path,
                                   upload=lambda p, k: "", key_for=lambda n: n,
                                   read_json=lambda k: None, download=lambda k, d: d,
                                   discover=lambda: seen.append(1) or [])
        assert out is None and seen == [1]
        post = (V / "post_interview.py").read_text(encoding="utf-8")
        assert 'r2_list(show.r2_key("local", run["id"], "guest-video") + "/")' in post


# ---------------------------------------------------------------------------
# 2. Asked to look something up, she does
# ---------------------------------------------------------------------------

@needs_node
class TestResearchOnRequest:
    def test_a_request_starts_a_lookup_and_her_next_turn_says_so(self):
        out = sim("research_request")
        assert out["lookupsAfterAsk"] == 2                 # the guest lookup, then the request
        assert "asked the host to look something up" in out["askPrompt"]
        assert 'when they say "me", they mean this person' in out["askPrompt"]
        assert out["createsAfterAsk"] == 1
        assert "They asked you to look something up" in out["turnInstructions"]
        assert "Never say you cannot search or browse" in out["turnInstructions"]
        note = out["notes"][-1]
        assert note.startswith("[RESEARCH NOTE") and "What the guest asked you to look up" in note
        assert "Bring it in on your next turn" in note
        assert out["lookupsAfterSecondAsk"] == 2           # not again within 45 s
        assert out["researchNotes"][-1]["kind"] == "request"

    def test_nothing_reliable_is_said_only_if_they_ask(self):
        out = sim("research_request_nothing")
        assert any("turned up nothing reliable" in n and "Do not bring it up yourself" in n
                   for n in out["notes"])

    def test_the_trace_names_a_request_by_its_length(self):
        out = sim("research_request")
        lines = [x["d"] for x in out["trace"] if x["e"] == "research"]
        assert "started (request): a request of 24 words" in lines
        assert not any("searching about me" in d for d in lines)


class TestSheKnowsTheRoomResearches:
    def test_the_brief_says_so_within_its_budget(self):
        assert "RESEARCH IS QUIET. The room looks things up as you talk." in " ".join(PROMPT.split())
        assert len(PROMPT.split()) < 1600


# ---------------------------------------------------------------------------
# 3. A test room plays the notice guests hear
# ---------------------------------------------------------------------------

class TestTheTestRoomNotice:
    def test_the_run_row_carries_the_shows_clips(self):
        src = (V / "rehearsal.py").read_text(encoding="utf-8")
        assert "**room_clips(show)," in src


# ---------------------------------------------------------------------------
# 4. A typed "we can wrap up now" is a stop
# ---------------------------------------------------------------------------

@needs_node
class TestTypedWrapUp:
    def test_in_the_closing_round_it_closes_with_her_thanks(self):
        out = sim("typed_wrap_up_in_round")
        assert out["state"]["roundClosed"] is True and out["askedToStop"] is True
        assert out["acks"][-1] == {"nn": 1, "ack": "topic", "status": "applied"}
        assert "The closing round is complete" in out["lastInstructions"]
        assert out["feedback"][-1]["wrap_up"] is True
        assert any(x["e"] == "close" and "typed to wrap up at 2/" in x["d"] for x in out["trace"])

    def test_before_it_the_closing_round_begins(self):
        out = sim("typed_wrap_up_before_round")
        assert out["state"]["roundActive"] is True
        assert any(x["d"].startswith("room-driven closing round begins (the guest asked to wrap up)")
                   for x in out["trace"])

    def test_a_topic_is_still_a_topic(self):
        import re
        rx = SCENARIO[SCENARIO.index("const TYPED_WRAP_UP_RE = /") + len("const TYPED_WRAP_UP_RE = /"):]
        rx = rx[:rx.index("/i;")]
        pattern = re.compile(rx, re.I)
        for text in ("we can wrap up now", "let's stop here", "can we end it", "time to finish",
                     "wrapping up", "Okay, let's wrap it up please.", "stop"):
            assert pattern.search(text), text
        for text in ("ask me about my jobs and how i got them", "how we wrap up a product launch",
                     "the end of moore's law", "stop motion animation", "we can wrap up the launch story"):
            assert not pattern.search(text), text


# ---------------------------------------------------------------------------
# 5. The studio follows the headset the guest puts on
# ---------------------------------------------------------------------------

@needs_node
class TestTheStudioFollowsTheHeadset:
    def test_airpods_in_setup_get_mira_and_offer_their_microphone(self):
        out = devices("airpods_in_setup")
        assert out["mic"] == "builtin", "the laptop microphone is pinned, not 'default'"
        assert "AirPods Pro</b> connected" in out["note"] and "useBtMic" in out["note"]
        assert "phone-call quality" in out["note"]
        assert {"default_audio": {"outputId": "airpods-out"}} in out["log"]

    def test_airpods_in_a_call_move_mira_to_them_at_once(self):
        out = devices("airpods_in_call")
        assert {"call_audio": {"outputId": "airpods-out"}} in out["log"]
        assert out["mic"] == "builtin" and "useBtMic" in out["noteCall"]

    def test_a_usb_headset_in_a_call_is_switched_to(self):
        out = devices("usb_in_call")
        assert out["mic"] == "usb-in" and {"switchCallMic": "usb-in"} in out["log"]
        assert "Switched to Jabra Evolve2 30 USB." in out["noteCall"]

    def test_a_wired_microphone_in_setup_is_switched_to_and_checked_again(self):
        out = devices("wired_in_setup")
        assert out["mic"] == "wired-in"
        assert "Press Check my microphone again." in out["micMsg"]

    def test_an_unplugged_microphone_falls_back(self):
        out = devices("unplugged")
        assert "Your microphone was disconnected" in out["note"]

    def test_airpods_already_on_keep_mira_and_the_computer_takes_the_microphone(self):
        # Oct 28 2026, later: "move to the best microphone possible". A
        # Bluetooth microphone is the lowest rank, so it is no longer offered
        # away: the better one is taken, and the headphones still play Mira.
        out = devices("airpods_already_on")
        assert out["mic"] == "builtin"
        assert "Using MacBook Pro Microphone (Built-in), the best microphone" in out["note"]
        assert "headphones still play Mira" in out["note"]

    def test_the_best_microphone_is_taken_when_the_page_opens(self):
        out = devices("best_at_open")
        assert out["mic"] == "yeti"
        assert "Using Yeti Stereo Microphone, the best microphone on this computer" in out["note"]

    def test_software_microphones_are_never_chosen_for_anyone(self):
        out = devices("software_never")
        assert out["mic"] == "builtin"

    def test_a_pick_by_hand_is_kept_when_the_page_lists_devices(self):
        out = devices("picked_by_hand")
        assert out["mic"] == "default" and out["note"] == ""

    def test_a_webcam_plugged_in_beside_a_better_microphone_is_offered_not_taken(self):
        out = devices("webcam_beside_yeti")
        assert out["mic"] == "yeti"
        assert "Logitech BRIO</b> connected" in out["note"] and "useNewMic" in out["note"]
        assert not any("switchDevices" in e for e in out["log"])

    def test_a_better_microphone_plugged_in_is_taken_even_after_a_pick(self):
        out = devices("yeti_plugged_in_after_a_pick")
        assert out["mic"] == "yeti" and "Switched to Yeti Stereo Microphone." in out["note"]

    def test_the_ranking_puts_a_microphone_over_a_headset_over_the_computer(self):
        a = STUDIO.index("function micScore(d)")
        body = STUDIO[a:STUDIO.index("\n  }", a)]
        order = [body.index(k) for k in ("return 0;", "return 10;", "return 50;", "return 40;",
                                         "return 20;", "return 35;", "return 30;")]
        assert order == sorted(order)

    def test_the_page_listens_for_device_changes(self):
        assert 'navigator.mediaDevices.addEventListener("devicechange"' in STUDIO
        assert 'id="deviceNote"' in STUDIO and 'id="deviceNoteCall"' in STUDIO


# ---------------------------------------------------------------------------
# 6. Background blur
# ---------------------------------------------------------------------------

class TestBackgroundBlur:
    def test_a_toggle_in_setup_and_in_the_room(self):
        assert 'id="blurBg"' in STUDIO and 'id="blurBgCall"' in STUDIO
        assert "Blur my background" in STUDIO

    def test_what_is_recorded_is_what_they_see(self):
        assert "vrec.view = b ? new MediaStream([b.track].concat(stream.getAudioTracks())) : stream;" in STUDIO
        assert "new MediaRecorder(vrec.view," in STUDIO
        assert "var vs = vrec.view || vrec.stream;" in STUDIO

    def test_pinned_library_and_model_loaded_only_when_used(self):
        assert '"https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14"' in STUDIO
        assert "selfie_segmenter.tflite" in STUDIO
        body = STUDIO[STUDIO.index("function loadBlur()"):]
        body = body[:body.index("\n  }\n")]
        assert "import(BLUR_LIB" in body
        # Not loaded at page start: only blurTrack calls it.
        assert STUDIO.count("loadBlur()") == 2

    def test_a_browser_without_it_keeps_the_camera_as_it_was(self):
        assert "Background blur isn't available in this browser. Your camera works as usual." in STUDIO
