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


def _flat(text: str) -> str:
    """Prompt wording, with the line-wrapping taken out of the comparison."""
    return " ".join(text.split())


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
        assert "I'm Mira. I'm the AI who hosts {{show_name}}." in PROMPT
        assert ("first podcast hosted and run end to end by an AI"
                in _flat(PROMPT))

    def test_the_claim_is_made_once_and_not_as_a_boast(self):
        flat = _flat(PROMPT)
        assert "Say it once, as a fact rather than a boast, and never again" in flat
        assert "a host who keeps mentioning it sounds like a press release" in flat

    def test_she_says_how_the_hour_will_go(self):
        flat = _flat(PROMPT)
        assert "roughly {{planned_minutes}} minutes" in flat
        assert "approve the episode before anyone else does" in flat
        assert "nothing is live" in flat

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

    def test_an_unreadable_file_is_not_evidence_against_the_take(self):
        # The coverage check exists to catch a short upload, not to gate on
        # ffprobe: if the duration cannot be measured, keep the local take.
        body = _pyfn("_covers", self.SRC)
        assert "except Exception as err:" in body
        assert "keeping the " in body
        assert "return True" in body.split("except Exception as err:")[1]

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


class TestTheCoHostAlsoRejoins:
    """Sept 14 2026 (Vincent Rylan): Patrick's connection dropped at 22:12:27
    and came back nine seconds later — two host legs, thirteen minutes and
    thirty. The run row names the first, so the co-host would have vanished
    from the last thirty minutes of his own interview. His browser take
    covered only the first leg too."""

    SRC = (ROOT / "pipelines" / "voices" / "post_interview.py").read_text(encoding="utf-8")

    def test_the_host_legs_are_measured_too(self):
        body = _pyfn("longest_leg_recording", self.SRC)
        assert 'log.get(f"extra_{role}_record_urls")' in body
        assert "if seconds > best_seconds" in body

    def test_the_pipeline_uses_it(self):
        # ae127b98d: every leg is fetched and placed on the room's clock;
        # the first leg is the host_raw the rest of the pipeline expects.
        assert 'host_legs = leg_recordings(run, "host", workdir)' in self.SRC
        assert "host_raw = host_legs[0] if host_legs else None" in self.SRC
        assert "host_legs=host_legs" in self.SRC

    def test_a_missing_leg_is_skipped_not_fatal(self):
        body = _pyfn("longest_leg_recording", self.SRC)
        assert "if leg is None:\n            continue" in body


class TestAnEagerGuestDoesNotCostTheCoHostHisIntroduction:
    """Vincent Rylan joined at 21:53 for a 22:00 interview. The hold was two
    minutes from HIS arrival, so it expired at 21:55 and Mira opened the show
    four minutes before Patrick got there."""

    def test_the_hold_runs_to_the_scheduled_start(self):
        body = _fn("cohostHoldMs")
        assert "config.scheduled_for" in body
        assert "untilDue + COHOST_WAIT_MS" in body

    def test_it_never_holds_forever(self):
        assert "COHOST_WAIT_MAX_MS = 12 * 60 * 1000" in SCENARIO
        assert "Math.min(COHOST_WAIT_MAX_MS" in _fn("cohostHoldMs")

    def test_a_missing_schedule_falls_back_to_the_flat_wait(self):
        body = _fn("cohostHoldMs")
        assert "isFinite(due)" in body
        assert "Math.max(COHOST_WAIT_MS" in body

    def test_the_timer_uses_it(self):
        assert "}, cohostHoldMs());" in SCENARIO


class TestAFinishedEpisodeIsNeverLost:
    """Sept 15 2026: John's episode built and uploaded, and then the job died
    on a KeyError because the EDL had no "interview_id" key — after the work
    was done, so the episode existed and nobody was told."""

    SRC = (ROOT / "pipelines" / "voices" / "assemble_edit.py").read_text(encoding="utf-8")

    def test_the_interview_is_found_without_the_edl_saying_so(self):
        body = _pyfn("_interview_id", self.SRC)
        assert 'if spec.get("interview_id")' in body
        assert 'run.get("interview_id")' in body
        assert 'sb_select("interview_runs"' in body

    def test_announcing_it_cannot_take_it_down(self):
        block = self.SRC[self.SRC.index("_tell_patrick(spec, show, slug, url, seconds, run)"):]
        block = block[:block.index("return {")]
        assert "except Exception" in block
        assert "The episode exists either way" in block
        assert "it is at %s" in block, "the log must still name the URL"

    def test_no_bare_spec_lookups_remain(self):
        assert "spec['interview_id']" not in self.SRC
        assert 'spec["interview_id"]' not in self.SRC or \
            'if spec.get("interview_id")' in self.SRC


class TestSomebodyIsActuallyTold:
    """Sept 15 2026: both finished episodes sat in R2 with nobody told. The
    assemble workflow passed OPERATOR_EMAIL from a repository secret that was
    never set, so the variable existed and was empty — os.environ.get returned
    "" and the default never applied. Resend got {"to": [""]} and said 422."""

    COMMON = (ROOT / "pipelines" / "voices" / "common.py").read_text(encoding="utf-8")

    def test_an_empty_env_var_is_not_an_address(self):
        assert 'os.environ.get("OPERATOR_EMAIL") or "patricknovak1@gmail.com"' in self.COMMON
        assert 'os.environ.get("VOICES_FROM_EMAIL") or "mira@nerranetwork.com"' in self.COMMON

    def test_the_default_survives_an_empty_secret(self):
        import os
        import importlib
        import sys
        sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
        before = os.environ.get("OPERATOR_EMAIL")
        os.environ["OPERATOR_EMAIL"] = ""
        try:
            import common
            importlib.reload(common)
            assert common.OPERATOR_EMAIL == "patricknovak1@gmail.com"
        finally:
            if before is None:
                os.environ.pop("OPERATOR_EMAIL", None)
            else:
                os.environ["OPERATOR_EMAIL"] = before
            importlib.reload(common)

    def test_the_error_names_the_cause(self):
        body = _pyfn("send_email", self.COMMON)
        assert 'if "@" not in to:' in body
        assert "OPERATOR_EMAIL" in body
        assert "reads as an empty" in body

    def test_the_workflow_does_not_pass_an_empty_secret(self):
        wf = (ROOT / ".github" / "workflows"
              / "nerra_voices_assemble_edit.yml").read_text(encoding="utf-8")
        assert "secrets.OPERATOR_EMAIL || 'patricknovak1@gmail.com'" in wf


class TestSheActuallyStops:
    """Sept 15 2026. Barge-in flushed her buffered audio, which stops her
    being HEARD, and left the server generating the rest of the turn. That
    audio then arrived after the guest had finished — which is why John's
    tape has the same question three times in twelve seconds and Vincent's
    has one question in three shapes. It was one turn, replayed, because
    nobody cancelled it."""

    def test_the_turn_is_cancelled_not_just_muted(self):
        body = SCENARIO[SCENARIO.index("VoiceAgentAPIEvents.InputAudioBufferSpeechStarted, function"):]
        body = body[:body.index("\n  });") + 6]
        assert "agent.clearMediaBuffer();" in body
        assert "responseCancel" in body
        assert 'type: "response.cancel"' in body, "fallback for an older connector"

    def test_it_only_cancels_a_turn_that_exists(self):
        body = SCENARIO[SCENARIO.index("VoiceAgentAPIEvents.InputAudioBufferSpeechStarted, function"):]
        body = body[:body.index("\n  });") + 6]
        assert "if (!miraSpeaking) return;" in body

    def test_the_flag_is_set_where_she_is_asked_to_speak(self):
        assert SCENARIO.count("miraSpeaking = true") >= 4
        assert "miraSpeaking = false;\n        trace(\"grok\", \"response done\");" in SCENARIO

    def test_a_connector_without_cancel_does_not_crash_the_room(self):
        body = SCENARIO[SCENARIO.index("VoiceAgentAPIEvents.InputAudioBufferSpeechStarted, function"):]
        body = body[:body.index("\n  });") + 6]
        assert "catch (err)" in body
        assert "could not cancel the turn" in body


class TestTheCraftRules:
    PROMPT = ((ROOT / "pipelines" / "voices" / "prompts"
               / "mira_system_prompt.txt").read_text(encoding="utf-8")
              + (ROOT / "pipelines" / "voices" / "prompts"
                 / "cohost_craft.txt").read_text(encoding="utf-8"))

    def test_yielding_is_separated_from_waiting(self):
        flat = _flat(self.PROMPT)
        # Waiting: the end of the thought, not the pause for breath ...
        assert "LET THEM FINISH. Wait for the end of the thought" in flat
        # ... and yielding: stop the moment the guest starts, mid-word.
        assert "yield the moment you hear them" in flat
        assert "stop mid-word, do not finish your thought" in flat

    def test_a_question_is_asked_once(self):
        flat = _flat(self.PROMPT)
        assert "ONE question per turn, asked once" in flat
        assert "never re-ask a question that has not been answered yet" in flat
        assert "The discomfort is yours to hold, not theirs to fill" in flat
        assert "Silence means they are thinking: count to five and wait again" in flat
        # The same rule again, where the cost of stacking is spelled out.
        assert "ONE QUESTION, THEN SILENCE" in flat

    def test_the_close_waits_for_the_answer(self):
        flat = _flat(self.PROMPT)
        assert "permission to close at the next natural break" in flat
        assert "not an instruction to talk over the answer in progress" in flat
        assert "let it land, then close" in flat
        # And the guest's own last word. Sept 22 2026, Viktor Popovic: she
        # asked for his parting thought and closed eleven seconds later,
        # which is worse than never asking.
        assert "THEIR LAST WORD IS THEIRS, NOT YOURS" in flat
        assert "AND WAITING IS THE WHOLE POINT OF ASKING" in flat
        assert "you close because they have finished" in flat

    def test_the_closing_round_is_a_tool_not_a_ritual(self):
        flat = _flat(self.PROMPT)
        assert "THE CLOSING ROUND is yours to shape" in flat
        assert "Skip it when the conversation is somewhere worth staying" in flat
        # three uses: a gear change, covering ground fast, or getting personal
        assert "cover ground fast when time got away from you" in flat
        assert "The personal set" in flat
        assert "What was it like being interviewed by an AI" in flat

    def test_the_co_host_is_a_model_to_learn_from(self):
        assert "LEARN FROM YOUR CO-HOST" in self.PROMPT
        # ... and only when he is in the room.
        assert "{{cohost_craft}}" in (ROOT / "pipelines" / "voices" / "prompts"
                                      / "mira_system_prompt.txt").read_text(encoding="utf-8")
        fire = (ROOT / "pipelines" / "voices"
                / "fire_interviews.py").read_text(encoding="utf-8")
        assert "def cohost_craft(enabled: bool = True, show=None)" in fire
        assert "if not enabled:\n        return \"\"" in fire
        for move in ("HE PUTS HIMSELF IN THE ANSWER",
                     "HE VALIDATES THE UNPOPULAR ANSWER",
                     "HE TESTS A CLAIM WITH A PRECEDENT",
                     "HE ASKS WHAT THEY WANTED TO SAY",
                     "HE OFFERS THE DOOR BACK",
                     "HE TELLS THEM WHY IT MATTERS TO HIM"):
            assert move in self.PROMPT, move
        assert "he gives something before he asks for\nsomething" in self.PROMPT

    def test_the_examples_are_from_real_tapes(self):
        assert "almost like your NetClaw" in self.PROMPT
        assert "part of the necessary dialogue" in self.PROMPT
        assert "a hundred times smarter" in self.PROMPT

    def test_the_question_pass_learned_the_same_shape(self):
        qgen = (ROOT / "pipelines" / "voices" / "prompts"
                / "question_generation.txt").read_text(encoding="utf-8")
        assert "offer something before it asks for something" in qgen
        assert "the bleak or unpopular reading is" in qgen

    def test_the_co_host_first_name_is_substituted(self):
        fire = (ROOT / "pipelines" / "voices"
                / "fire_interviews.py").read_text(encoding="utf-8")
        assert "cohost_first=cohost_name().split()[0]," in fire


class TestTheTranscriptStopsInventingSpeech:
    """Whisper fills silence with its most common short utterances, and each
    speaker's track is mostly silence — it is one microphone in a three-way
    conversation. John Capobianco's transcript carries 47 lines reading only
    "You"; Vincent Rylan's has "You" and "Thank you" every thirty seconds
    through passages where that person said nothing. Cosmetic in the audio,
    not cosmetic in the transcript a guest approves at gate 2."""

    SRC = (ROOT / "pipelines" / "voices" / "post_interview.py").read_text(encoding="utf-8")

    def _fn(self):
        ns: dict = {}
        start = self.SRC.index("_GHOSTS = {")
        exec(self.SRC[start:self.SRC.index("\ndef diarized_tracks")], ns)
        return ns["_is_hallucination"]

    def test_a_ghost_in_silence_is_dropped(self):
        f = self._fn()
        assert f({"avg_logprob": -0.9, "no_speech_prob": 0.8}, "You")
        assert f({"avg_logprob": -0.7}, "Thank you.")
        assert f({}, "You"), "no confidence at all is not a reason to keep it"

    def test_a_word_someone_really_said_survives(self):
        f = self._fn()
        assert not f({"avg_logprob": -0.2}, "Thank you."), \
            "a confident 'thank you' is a real one"
        assert not f({"avg_logprob": -0.9}, "Yeah, that works.")
        assert not f({"avg_logprob": -0.95}, "I live at the intersection")

    def test_only_short_reflexes_are_ever_candidates(self):
        f = self._fn()
        long_ghost = " ".join(["you"] * 8)
        assert not f({"avg_logprob": -0.99}, long_ghost)

    def test_the_filter_is_wired_into_the_merge(self):
        assert "if not text or _is_hallucination(seg, text):" in self.SRC
