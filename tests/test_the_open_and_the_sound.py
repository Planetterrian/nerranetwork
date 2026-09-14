"""The open, the interruptions, and how Mira sounds (Sept 14 2026).

After the John Capobianco interview. The scenario_trace of that room is the
whole indictment of the open: the guest's leg attached at 14:55:13.4, Mira
started the show at 14:55:14.5 — 1.1 seconds, before he had his headphones
settled — and the co-host arrived at 14:55:56, 43 seconds into a show that
had begun without him. Separately she talked over people all hour, and her
voice is 50 dB down by 5.5 kHz where the guest still has real energy at 8.3.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCENARIO = (ROOT / "voximplant" / "scenarios"
            / "age_of_ai_interview.js").read_text(encoding="utf-8")
PROMPT = (ROOT / "pipelines" / "voices" / "prompts"
          / "mira_system_prompt.txt").read_text(encoding="utf-8")
NARRATION = (ROOT / "pipelines" / "voices" / "prompts"
             / "mira_narration.txt").read_text(encoding="utf-8")
FIRE = (ROOT / "pipelines" / "voices" / "fire_interviews.py").read_text(encoding="utf-8")


def _fn(name: str, src: str = SCENARIO) -> str:
    start = src.index(f"function {name}(")
    return src[start:src.index("\n}\n", start) + 3]


def _pyfn(name: str, src: str) -> str:
    start = src.index(f"def {name}(")
    rest = src[start:]
    end = rest.index("\n\n\n") if "\n\n\n" in rest else len(rest)
    return rest[:end]


class TestSheWaitsForTheRoom:
    def test_the_guest_gets_a_beat_before_she_speaks(self):
        assert "GUEST_SETTLE_MS = 7 * 1000" in SCENARIO
        assert 'openWhenReady("guest settled")' in _fn("maybeOpen")

    def test_the_open_is_held_for_a_co_host_who_is_coming(self):
        body = _fn("maybeOpen")
        assert "waitingForCohost()" in body
        assert "greetGuestAndWait()" in body
        assert "COHOST_WAIT_MS" in body

    def test_holding_is_not_silence(self):
        """A guest left alone with nothing is as bad as being talked over."""
        body = _fn("greetGuestAndWait")
        assert "your name" in body and "AI host" in body
        assert "Do NOT start the show" in body
        assert "get\n          \"comfortable" in body or "comfortable" in body

    def test_the_hold_expires_rather_than_stranding_the_guest(self):
        assert "cohostWaitExpired = true" in SCENARIO
        assert 'openWhenReady("co-host no-show")' in SCENARIO
        assert "COHOST_WAIT_MS = 2 * 60 * 1000" in SCENARIO

    def test_only_one_open_ever_fires(self):
        opened = _fn("openWhenReady")
        assert "if (openingFired" in opened
        assert "openingFired = true;" in opened
        assert "clearTimeout(cohostWaitTimer)" in opened

    def test_the_co_host_arriving_releases_the_hold(self):
        assert "if (!openingFired) maybeOpen();" in SCENARIO


class TestSheStopsTalkingOverPeople:
    def test_end_of_turn_silence_is_set_not_defaulted(self):
        body = _fn("turnDetection")
        assert 'type: "server_vad"' in body
        assert "silence_duration_ms" in body
        assert "1100" in body, "a breath is shorter than this; a real pause is longer"

    def test_it_is_tunable_without_a_deploy(self):
        body = _fn("turnDetection")
        assert "config.turn_detection" in body
        for field in ("threshold", "prefix_padding_ms", "silence_duration_ms"):
            assert f"tuned.{field}" in body, field

    def test_the_session_actually_uses_it(self):
        assert "turn_detection: turnDetection()," in SCENARIO


class TestHowSheSounds:
    def test_an_output_rate_can_be_requested(self):
        body = _fn("audioOutputFormat")
        assert 'type: "audio/pcm"' in body
        assert "rate: rate" in body
        assert "if (!rate) return null" in body, "default must change nothing"

    def test_both_the_room_and_the_narration_can_use_it(self):
        assert "const outFormat = audioOutputFormat();" in SCENARIO
        assert "audioOutputFormat(custom.audio_rate)" in SCENARIO

    def test_no_object_spread_in_the_scenario(self):
        """VoxEngine's JS level is not worth guessing at mid-interview."""
        assert "...(" not in SCENARIO

    def test_the_narrate_path_carries_the_rate(self):
        client = (ROOT / "voximplant" / "api_clients"
                  / "voximplant_client.py").read_text(encoding="utf-8")
        assert "audio_rate: int | None = None" in client
        assert '"audio_rate": int(audio_rate) if audio_rate else None' in client
        narrate = (ROOT / "pipelines" / "voices" / "narrate.py").read_text(encoding="utf-8")
        assert 'AUDIO_RATE = int(os.environ.get("NARRATION_AUDIO_RATE", "0") or 0)' in narrate
        assert "audio_rate=AUDIO_RATE" in narrate


class TestWhatSheSaysAtTheTop:
    def test_she_introduces_herself_and_the_show(self):
        assert "HOW TO OPEN" in PROMPT
        assert "I'm the AI who hosts this show" in PROMPT
        assert "first podcast hosted and run end to end by an\n   AI" in PROMPT

    def test_the_claim_is_made_once_and_not_as_a_boast(self):
        assert "as a fact about the show rather than a" in PROMPT
        assert "do not repeat it later in the conversation" in PROMPT

    def test_she_says_how_the_hour_will_go(self):
        assert "roughly {{planned_minutes}} minutes" in PROMPT
        assert "approve it before anyone else does" in PROMPT
        assert "nothing\n   is live" in PROMPT

    def test_the_co_host_is_introduced_only_when_there_is_one(self):
        assert "{{cohost_intro_step}}" in PROMPT
        assert "def cohost_intro_step(enabled: bool = True)" in FIRE
        assert "if not enabled:\n        return \"\"" in FIRE
        assert "cohost_intro_step=cohost_intro_step(host_mode_enabled(interview))" in FIRE

    def test_the_co_host_block_asks_for_a_name_and_a_beat(self):
        assert "Introduce him BY NAME in your opening" in FIRE
        assert "been ambushed" in FIRE

    def test_the_produced_episode_says_it_too(self):
        assert "first podcast hosted and run end to end by an AI" in NARRATION
        assert "never as a boast" in NARRATION
        assert "never the same wording as the cold open" in NARRATION


class TestTheRunnerCanStillMakeAudio:
    def test_ffmpeg_is_ours_not_a_third_party_readme(self):
        action = (ROOT / ".github" / "actions" / "setup-ffmpeg"
                  / "action.yml").read_text(encoding="utf-8")
        assert "apt-get install -y -qq ffmpeg" in action
        assert "command -v ffmpeg" in action, "skip the install when it is there"
        for wf in ("assemble_edit", "narrate", "post_interview",
                   "produce_episode", "publish"):
            text = (ROOT / ".github" / "workflows"
                    / f"nerra_voices_{wf}.yml").read_text(encoding="utf-8")
            assert "FedericoCarboni" not in text, wf
            assert "./.github/actions/setup-ffmpeg" in text, wf

    def test_post_interview_can_be_re_driven_by_hand(self):
        wf = (ROOT / ".github" / "workflows"
              / "nerra_voices_post_interview.yml").read_text(encoding="utf-8")
        assert "workflow_dispatch:" in wf
        assert "github.event.client_payload.run_id || inputs.run_id" in wf


class TestTheRecordingWithTheInterviewOnIt:
    """Sept 14 2026: John Capobianco dropped 50 seconds in and rejoined six
    minutes later. Voximplant records each leg separately, so the 65-second
    false start was `voximplant_record_url` and the forty minutes that
    followed were in `extra_guest_record_urls` — and his browser had uploaded
    65 seconds too. The pipeline took the short one twice over and produced a
    transcript with almost none of his answers in it."""

    SRC = (ROOT / "pipelines" / "voices" / "post_interview.py").read_text(encoding="utf-8")

    def test_every_guest_leg_is_considered(self):
        body = _pyfn("fetch_recording", self.SRC)
        assert "extra_guest_record_urls" in body
        assert "if seconds > best_seconds" in body

    def test_a_dead_leg_url_is_not_fatal(self):
        body = _pyfn("fetch_recording", self.SRC)
        assert "except Exception as err:" in body
        assert "did not download" in body

    def test_a_short_local_take_loses_to_a_longer_leg(self):
        assert "COVERAGE_MIN = 0.80" in self.SRC
        body = _pyfn("_covers", self.SRC)
        assert "ratio >= COVERAGE_MIN" in body
        assert "using the Voximplant leg instead" in body

    def test_both_speakers_are_checked(self):
        assert '_covers(local_guest, guest_vox, "guest")' in self.SRC
        assert '_covers(local_host, host_vox or guest_r, "host")' in self.SRC

    def test_no_reference_means_trust_the_local_take(self):
        body = _pyfn("_covers", self.SRC)
        assert "if reference is None:\n        return True" in body


class TestEveryoneOnTheSameClock:
    """Sept 14 2026, the third thing John Capobianco's room exposed. He joined
    at 14:55:13, dropped at 14:56:05, and rejoined at 15:02:21. The recording
    we use is that second leg, but the transcript anchored it to his FIRST
    join, so every answer landed seven minutes before the question that
    prompted it — Mira asking "how would you describe what you do" at 8:51
    against his answer to it at 1:32."""

    SRC = (ROOT / "pipelines" / "voices" / "post_interview.py").read_text(encoding="utf-8")

    def _offsets(self):
        src = self.SRC
        start = src.index("def room_offsets(")
        ns: dict = {}
        exec("from __future__ import annotations\n"
             + src[start:src.index("\ndef ", start + 10)], ns)
        return ns["room_offsets"]

    TRACE = [
        {"e": "room", "d": "opened (webrtc)", "t": "2026-09-14T14:55:13.326Z"},
        {"e": "leg", "d": "guest #1 joined (1 in room)", "t": "2026-09-14T14:55:13.436Z"},
        {"e": "grok", "d": "session updated; agent<->room mix bridged",
         "t": "2026-09-14T14:55:14.536Z"},
        {"e": "leg", "d": "host #2 joined (2 in room)", "t": "2026-09-14T14:55:56.788Z"},
        {"e": "leg", "d": "guest #1 left: disconnected (1 in room)",
         "t": "2026-09-14T14:56:05.734Z"},
        {"e": "leg", "d": "guest #3 joined (2 in room)", "t": "2026-09-14T15:02:21.546Z"},
        {"e": "leg", "d": "guest #3 left: disconnected (1 in room)",
         "t": "2026-09-14T15:41:54.813Z"},
        {"e": "leg", "d": "host #2 left: disconnected (0 in room)",
         "t": "2026-09-14T15:42:01.835Z"},
    ]

    def test_the_rejoin_is_found_by_how_long_the_file_is(self):
        run = {"scenario_trace": self.TRACE}
        out = self._offsets()(run, {"guest": 2384.6, "host": 2765.9, "mira": 2713.0})
        assert 425 < out["guest"] < 431, out            # the 15:02 rejoin
        assert 43 < out["host"] < 44

    def test_the_first_leg_still_anchors_to_the_first_join(self):
        run = {"scenario_trace": self.TRACE}
        out = self._offsets()(run, {"guest": 64.9})
        assert out["guest"] < 1

    def test_without_durations_it_behaves_as_before(self):
        run = {"scenario_trace": self.TRACE}
        assert self._offsets()(run)["guest"] < 1

    def test_a_leg_still_open_at_the_end_is_measured_to_the_end(self):
        trace = [e for e in self.TRACE if "guest #3 left" not in e["d"]]
        out = self._offsets()({"scenario_trace": trace}, {"guest": 2370.0})
        assert out["guest"] > 400, "an unterminated leg must still be matchable"

    def test_the_durations_come_from_the_files_being_merged(self):
        assert "def _track_durations(tracks: dict) -> dict:" in self.SRC
        assert "room_offsets(run or {}, _track_durations(tracks))" in self.SRC
        assert "room_offsets(run, _track_durations(tracks))" in self.SRC
