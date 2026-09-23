"""Three faults from one episode (Sept 22 2026, Viktor Popovic).

Patrick listened and said the introduction started off strange and asked
whether the ending still cut off early. Both were true, and pulling on them
found a third thing underneath that had caused most of the damage.

1. THE OPENING. The written introduction began "Thank you. Thank you for
   having me. I am based in South Florida." Those are Viktor's words, from
   [00:38] of the transcript the pass was reading, and they would have been
   performed in Mira's voice as the first thing anyone heard.

2. THE CLOSE. The new closing round half-worked. She did ask whether anything
   had gone unreached, at [42:40], and he used it — a referral programme and
   how to reach him. Then at [43:57] she asked for a parting thought and
   closed the recording at [44:08], eleven seconds later, before he had said
   a word of it. Asking without waiting is worse than not asking.

3. WHY THERE WERE NO CLEAN TRACKS. Viktor's browser recording never
   uploaded, and the two-track path was gated on the GUEST's track being local
   rather than on Mira having audio of her own. So a run holding a clean guest
   channel and a real Mira-only leg fell through to transcribing the raw
   Voximplant stereo, and neither the clean bed nor a transcript anyone could
   trust about who said what was ever produced.

4. AND A CORRECTION TO POINT 3, made the next day. Her turns in that first
   transcript kept opening with the guest's last few words ("Talking to staff.
   How big is the team?"), and the first account of this episode put that down
   to his voice leaking into her channel — and taught the grader to stop
   grading it. Re-transcribed from the clean tracks, every one of those lines
   was still on HER recording. She was echoing him, and resuming sentences she
   had been interrupted in. The grader had been right about the parroting. It
   is now TOLD whether the channels were separated, as a fact from the
   pipeline, instead of guessing from how the text reads — which is the
   mistake the reviewer made, not the grader.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V = ROOT / "pipelines" / "voices"
POST = (V / "post_interview.py").read_text(encoding="utf-8")
AUTO = (V / "auto_edit.py").read_text(encoding="utf-8")
SCENARIO = (ROOT / "voximplant" / "scenarios"
            / "age_of_ai_interview.js").read_text(encoding="utf-8")
PROMPT = (V / "prompts" / "mira_system_prompt.txt").read_text(encoding="utf-8")
RETRO = (V / "prompts" / "editorial_passes"
         / "09_interview_retro.txt").read_text(encoding="utf-8")

sys.path.insert(0, str(V))
sys.path.insert(0, str(ROOT))


def _jsfn(name: str) -> str:
    start = SCENARIO.index(f"function {name}(")
    return SCENARIO[start:SCENARIO.index("\n}\n", start) + 3]


class TestTheCleanPathIsChosenByMirasAudio:
    def test_the_branch_asks_about_mira_not_about_the_guest(self):
        assert 'elif tracks["sources"].get("mira") != "guest_r":' in POST
        # The old test — was the GUEST's track the local recording — is gone.
        assert 'elif tracks["sources"].get("guest") == "local":' not in POST

    def _two_track_branch(self) -> str:
        start = POST.index('elif tracks["sources"].get("mira")')
        return POST[start:POST.index("diarized_transcript(raw, workdir)", start)]

    def test_a_missing_browser_recording_no_longer_costs_the_clean_path(self):
        block = self._two_track_branch()
        assert "mix_two(" in block
        assert "processed[speaker] = r2_upload(" in block
        assert "diarized_tracks(" in block

    def test_it_reuses_the_alignment_build_tracks_already_measured(self):
        block = self._two_track_branch()
        assert 'if tracks.get("alignment") is None:' in block
        assert '_guest_label(app): 0.0, "Mira": 0.0' in block

    def test_the_raw_stereo_fallback_says_it_cannot_be_trusted(self):
        tail = POST[POST.index("        else:", POST.index('elif tracks["sources"]')):]
        tail = tail[:tail.index("diarized_transcript(raw, workdir)") + 40]
        assert "logger.warning" in tail
        assert "attribution is unreliable" in tail


class TestTheNarrationIsWrittenNotOverheard:
    def test_the_guard_runs_on_every_plan(self):
        assert 'out["intro"] = _drop_borrowed_open(str(out["intro"]), transcript)' in AUTO

    def test_it_takes_viktors_own_words_off_the_front(self):
        import auto_edit
        transcript = (
            "[00:36] MIRA: Welcome.\n"
            "[00:38] GUEST: Thank you. Thank you for having me. I am based in "
            "South Florida.\n"
            "[00:43] MIRA: Where are you calling from today?\n")
        bad = ("Thank you. Thank you for having me. I am based in South Florida. "
               "This is Nerra Voices from the Nerra Network. I'm Mira. Here is Viktor.")
        fixed = auto_edit._drop_borrowed_open(bad, transcript)
        assert fixed.startswith("This is Nerra Voices")
        assert "South Florida" not in fixed

    def test_it_catches_a_borrow_from_mid_turn_sentence(self):
        import auto_edit
        transcript = ("[00:38] GUEST: Thank you. Thank you for having me. I am "
                      "based in South Florida.\n")
        for bad in ("Thank you for having me. This is Nerra Voices. Here is Viktor.",
                    "I am based in South Florida. This is Nerra Voices. Here is Viktor."):
            assert auto_edit._drop_borrowed_open(bad, transcript).startswith(
                "This is Nerra Voices")

    def test_written_copy_is_left_alone(self):
        import auto_edit
        transcript = "[00:38] GUEST: Thank you for having me.\n"
        good = ("This is Nerra Voices from the Nerra Network. I'm Mira. Here is "
                "Viktor.")
        assert auto_edit._drop_borrowed_open(good, transcript) == good

    def test_a_quotation_later_in_the_narration_survives(self):
        # Only the OPENING is suspect. Quoting the guest is what an outro does.
        import auto_edit
        transcript = "[00:38] GUEST: Thank you for having me.\n"
        text = "This is Nerra Voices. He opened with thank you for having me. Here is Viktor."
        assert auto_edit._drop_borrowed_open(text, transcript) == text

    def test_it_never_empties_the_introduction(self):
        import auto_edit
        transcript = "[00:38] GUEST: Welcome.\n"
        assert auto_edit._drop_borrowed_open("Welcome.", transcript) == "Welcome."

    def test_it_survives_a_transcript_with_no_timestamps(self):
        import auto_edit
        good = "This is Nerra Voices. Here is Viktor."
        assert auto_edit._drop_borrowed_open(good, "nothing parseable") == good


class TestTheLastWordIsWaitedFor:
    def test_the_room_knows_when_she_hands_it_over(self):
        assert "const LAST_WORD_RE" in SCENARIO
        assert "function noteLastWordAsk(" in SCENARIO
        assert "lastWordAnswered = false" in SCENARIO

    def test_the_guest_speaking_is_what_answers_it(self):
        body = _jsfn("remember")
        assert "lastWordAnswered = true" in body
        # The ask has to be noted before the sign-off test, so that asking and
        # closing in one breath is still caught.
        assert body.index("noteLastWordAsk") < body.index("catchEarlySignOff")

    def test_closing_on_an_unanswered_question_is_caught_at_any_minute(self):
        body = _jsfn("catchEarlySignOff")
        assert "if (catchClosingWithoutTheAnswer(text)) return;" in body
        assert body.index("catchClosingWithoutTheAnswer") < body.index("closingPermitted")

    def test_silence_long_enough_counts_as_nothing_to_add(self):
        assert "LAST_WORD_WAIT_MS = 25 * 1000" in SCENARIO
        body = _jsfn("closingOnAnUnansweredQuestion")
        assert "Date.now() - lastWordAskedAt) < LAST_WORD_WAIT_MS" in body

    def test_it_tells_her_to_stop_talking_rather_than_ask_again(self):
        body = _jsfn("catchClosingWithoutTheAnswer")
        assert "STOP TALKING and wait" in body
        assert "Silence is the correct behaviour now" in body
        assert "ask a different question" in body

    def test_it_does_not_nag(self):
        body = _jsfn("catchClosingWithoutTheAnswer")
        assert "lastWordRescues >= 2" in body

    def test_the_regexes_know_the_two_questions(self):
        line = next(l for l in SCENARIO.splitlines()
                    if l.startswith("const LAST_WORD_RE"))
        pattern = re.compile(line[line.index("/") + 1:line.rindex("/i")], re.I)
        for asked in ("Do you have any parting thoughts?",
                      "is there anything you came wanting to say that we did not reach?",
                      "Is there a subject we never reached?",
                      "Anything else you would like to add?",
                      "Any last word?"):
            assert pattern.search(asked), asked
        for other in ("What keeps the processors competing?",
                      "Can you add some detail about the routing?"):
            assert not pattern.search(other), other

    def test_the_prompt_says_asking_without_waiting_is_worse(self):
        assert "AND WAITING IS THE WHOLE POINT OF ASKING" in PROMPT
        assert "eleven" in PROMPT and "seconds later" in PROMPT
        assert "you close because they have finished" in PROMPT


class TestTheGraderIsToldTheFactNotLeftToGuess:
    """Whether who-said-what can be trusted is a property of the recording,
    and the pipeline knows it. The grader is told; it does not infer it from
    how a line reads."""

    def test_the_heuristic_that_misled_the_reviewer_is_gone(self):
        # "A Mira turn that opens with the guest's words is bleed" was wrong
        # on the very tape it was written about.
        assert "IT HAPPENS THE OTHER WAY ROUND TOO" not in RETRO

    def test_the_pipeline_states_whether_the_channels_were_separated(self):
        assert "{{channels}}" in RETRO
        call = POST[POST.index('"editorial_passes/09_interview_retro.txt"'):]
        call = call[:call.index("temperature=0.3")]
        assert "channels=channels," in call
        # Decided by whether per-speaker tracks were produced, nothing else.
        assert 'if processed else' in POST[POST.index("channels = ("):
                                           POST.index("channels = (") + 700]

    def test_both_answers_say_what_they_mean(self):
        block = POST[POST.index("channels = ("):POST.index("channels = (") + 900]
        flat = " ".join(block.replace('" "', "").replace('"\n', "").split())
        assert "SEPARATED. Each speaker was recorded on a track of their own" in block
        assert "labelled Mira was said by Mira" in flat
        assert "NOT SEPARATED. Mira had no recording of her own" in block

    def test_only_an_unseparated_tape_stops_the_grading(self):
        block = RETRO[RETRO.index("HOW FAR TO TRUST WHO SAID WHAT"):
                      RETRO.index("AND A RELAPSE IS NOT A NEW LESSON")]
        assert "If it says NOT SEPARATED, do not grade listening" in block
        assert "propose no lesson that depends on who said what" in block

    def test_on_a_separated_tape_her_strange_lines_are_hers(self):
        block = RETRO[RETRO.index("HOW FAR TO TRUST WHO SAID WHAT"):
                      RETRO.index("AND A RELAPSE IS NOT A NEW LESSON")]
        assert "If it says SEPARATED, believe the labels" in block
        # The two habits Viktor's clean tracks proved were hers.
        flat = " ".join(block.split())
        assert "That is her echoing him back" in flat
        assert "picked up the sentence she had been cut off in" in flat

    def test_it_is_told_why_guessing_is_the_expensive_mistake(self):
        flat = " ".join(RETRO.split())
        assert "every one of those lines was still hers" in flat
        assert "Do not guess; read the line above." in flat

    def test_a_relapse_is_not_adopted_as_a_new_lesson(self):
        assert "AND A RELAPSE IS NOT A NEW LESSON" in RETRO
        block = RETRO[RETRO.index("AND A RELAPSE IS NOT A NEW LESSON"):]
        assert "adopt nothing" in block
        assert "relapse against that lesson's" in block


# ---------------------------------------------------------------------------
# 5. THE DEAD AIR THAT WASN'T (found Sept 23, on the re-run).
#
# Both grading passes marked Mira's pacing at 2 and 3 out of 10 for "18
# minutes of dead air", and the metric said 983 seconds. It measured from the
# START of one transcript line to the START of the next, so every second the
# guest spent talking counted as a second of silence. Measured from the audio,
# nobody was silent for more than 57 seconds in the whole hour — and the
# longest of those, 26 seconds, was Mira waiting while he thought.

import shutil  # noqa: E402
import subprocess  # noqa: E402
import wave  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402

LEARNING = (V / "learning.py").read_text(encoding="utf-8")


class TestTheTranscriptNoLongerCountsTalkingAsSilence:
    def test_a_long_answer_is_not_dead_air(self):
        import learning
        # He talks for the whole of a 40-word answer; she asks at 0:30.
        words = " ".join(["word"] * 40)
        t = (f"[00:00] Mira: What happened next?\n"
             f"[00:02] Viktor: {words}\n"
             f"[00:30] Mira: And after that?\n")
        m = learning.measure({"id": "r"}, t, host_label="Mira", guest_label="Viktor")
        # 40 words at 2 a second ends at 0:22; the gap to 0:30 is 8 seconds.
        # Measured start to start it would have been 28.
        assert m["dead_air_sec"] < 10

    def test_a_real_gap_is_still_counted(self):
        import learning
        t = ("[00:00] Mira: Take your time.\n"
             "[00:30] Viktor: Right, here is the example.\n")
        m = learning.measure({"id": "r"}, t, host_label="Mira", guest_label="Viktor")
        assert m["dead_air_sec"] > 20

    def test_the_estimate_says_it_cannot_be_graded_on(self):
        import learning
        m = learning.measure({"id": "r"}, "[00:00] Mira: Hello.\n[00:05] Viktor: Hi.\n",
                             host_label="Mira", guest_label="Viktor")
        assert "do not grade pacing on it" in m["notes"]["dead_air_basis"]

    def test_a_turn_is_a_run_of_her_lines_not_the_gap_between_them(self):
        import learning
        # Two Mira lines back to back are ONE turn; his answer between two of
        # her turns is not part of hers.
        t = ("[00:00] Mira: One two three four five six.\n"
             "[00:03] Mira: Seven eight nine ten.\n"
             "[00:05] Viktor: " + " ".join(["w"] * 60) + "\n"
             "[00:40] Mira: Short.\n")
        m = learning.measure({"id": "r"}, t, host_label="Mira", guest_label="Viktor")
        assert m["mira_turns"] == 3            # lines, as before
        assert m["mira_mean_turn_sec"] < 10    # was the whole answer, start to start

    def test_the_rate_is_the_one_people_actually_speak_at(self):
        assert "SPEAKING_WPS = 2.0" in LEARNING
        assert "5,313 words" in LEARNING


def _voice(path, spans, total=60.0, sr=16000):
    """A track with a tone during each (start, end) span and room tone elsewhere."""
    n = int(total * sr)
    rng = np.random.default_rng(1)
    x = rng.normal(0, 10 ** (-62 / 20), n)
    t = np.arange(n) / sr
    for a, b in spans:
        i, j = int(a * sr), int(b * sr)
        x[i:j] += 0.3 * np.sin(2 * np.pi * 220 * t[i:j])
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(np.clip(x * 32767, -32768, 32767).astype("<i2").tobytes())
    return path


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
class TestSilenceIsMeasuredFromTheAudio:
    def test_it_is_silent_only_when_everyone_is(self, tmp_path):
        import learning
        # She speaks 2-8; he speaks 9-40 (a long answer); she speaks 42-44;
        # then a 12-second silence nobody fills; he speaks 56-59.
        mira = _voice(tmp_path / "m.wav", [(2, 8), (42, 44)])
        guest = _voice(tmp_path / "g.wav", [(9, 40), (56, 59)])
        heard = learning.measure_silence([guest, mira])
        assert heard is not None
        # The lead-in (0-2) is left out; his 31-second answer is NOT silence;
        # the one real gap is 44-56.
        assert 10 < heard["longest_silence_sec"] < 13
        assert heard["dead_air_sec"] < 16
        assert any(43 < at < 46 for at, _d in heard["silences"])

    def test_the_lead_in_before_anyone_speaks_is_not_dead_air(self, tmp_path):
        import learning
        mira = _voice(tmp_path / "m.wav", [(20, 25)], total=30)
        guest = _voice(tmp_path / "g.wav", [(26, 29)], total=30)
        heard = learning.measure_silence([guest, mira])
        assert heard is not None
        assert all(at >= 1.0 for at, _d in heard["silences"])

    def test_nothing_to_measure_means_the_estimate_stands(self):
        import learning
        assert learning.measure_silence([]) is None
        assert learning.measure_silence([None]) is None


class TestPostInterviewUsesTheAudio:
    def test_it_measures_from_the_tracks_when_it_has_them(self):
        block = POST[POST.index("heard = measure_silence("):]
        block = block[:block.index("save_metrics(")]
        assert '[tracks.get(r) for r in ("guest", "host", "mira")] if processed' in block
        assert "else [raw]" in block

    def test_the_detail_goes_where_the_table_can_take_it(self):
        # An unknown key fails the whole metrics write, and the grade with it.
        block = POST[POST.index("heard = measure_silence("):]
        block = block[:block.index("save_metrics(")]
        assert 'metrics["dead_air_sec"] = heard["dead_air_sec"]' in block
        assert 'notes["silences"] = heard["silences"]' in block
        assert "metrics.update(heard)" not in block

    def test_the_grader_is_shown_how_it_was_measured_and_where(self):
        call = POST[POST.index('"editorial_passes/09_interview_retro.txt"'):]
        call = call[:call.index("temperature=0.3")]
        for key in ("dead_air_basis", "longest_silence_sec", "silences"):
            assert f'"{key}"' in call

    def test_the_grader_is_told_to_read_a_silence_before_punishing_it(self):
        flat = " ".join(RETRO.split())
        assert "READ A SILENCE BEFORE YOU PUNISH IT" in flat
        assert "Only a silence nobody asked for" in flat
        assert "do not grade pacing on it at all" in flat


# ---------------------------------------------------------------------------
# 6. THE FIRST THING A NERRA VOICES GUEST HEARD WAS THE WRONG SHOW.
#
# "Hi, this is Mira, the AI host for the Age of AI on the Nerra Network."
# Not in the scenario and not in any prompt: an MP3, set as the database
# default for every run on both shows. Deploying the scenario could never
# change it.

import json  # noqa: E402

FIRE = (V / "fire_interviews.py").read_text(encoding="utf-8")
NV_SYSTEM = json.loads((V / "narration" / "nerra_voices_room.json").read_text(encoding="utf-8"))


class TestEachShowHasItsOwnRoomClips:
    def test_nerra_voices_names_its_own(self):
        from pipelines.voices.shows import get_show
        nv = get_show("nerra_voices")
        assert nv.disclosure_clip.endswith("/nerra_voices/narration/nerra_voices_room/disclosure.mp3")
        assert nv.apology_clip.endswith("/nerra_voices/narration/nerra_voices_room/apology.mp3")

    def test_the_age_of_ai_keeps_the_clips_it_was_voiced_for(self):
        from pipelines.voices.shows import get_show
        aoa = get_show("age_of_ai")
        assert aoa.disclosure_clip == "" and aoa.apology_clip == ""

    def test_the_text_names_the_right_show_and_still_asks_consent(self):
        seg = {s["id"]: s["text"] for s in NV_SYSTEM["segments"]}
        assert NV_SYSTEM["show"] == "nerra_voices"
        assert "the AI host of Nerra Voices" in seg["disclosure"]
        assert "Age of AI" not in seg["disclosure"]
        assert "recorded" in seg["disclosure"] and "consent" in seg["disclosure"]
        assert "Age of AI" not in seg["apology"]

    def test_the_narration_upload_lands_where_the_config_points(self):
        # narrate.py uploads to show.r2_key("narration", slug, "<id>.mp3").
        from pipelines.voices.shows import get_show
        nv = get_show("nerra_voices")
        for seg_id, url in (("disclosure", nv.disclosure_clip), ("apology", nv.apology_clip)):
            assert url.endswith(nv.r2_key("narration", "nerra_voices_room", f"{seg_id}.mp3"))


class TestTheRoomNeverPlaysAMissingClip:
    def test_the_run_row_takes_the_shows_clips(self):
        insert = FIRE[FIRE.index('run = sb_insert("interview_runs", {'):]
        insert = insert[:insert.index("})")]
        assert "**room_clips(show)," in insert

    def test_a_clip_that_is_not_there_is_not_used(self, monkeypatch):
        import fire_interviews
        from pipelines.voices.shows import get_show
        monkeypatch.setattr(fire_interviews, "_clip_is_there", lambda url: False)
        assert fire_interviews.room_clips(get_show("nerra_voices")) == {}

    def test_a_clip_that_is_there_is(self, monkeypatch):
        import fire_interviews
        from pipelines.voices.shows import get_show
        monkeypatch.setattr(fire_interviews, "_clip_is_there", lambda url: True)
        clips = fire_interviews.room_clips(get_show("nerra_voices"))
        assert clips["recording_disclosure_url"].endswith("disclosure.mp3")
        assert clips["grok_drop_apology_url"].endswith("apology.mp3")

    def test_a_show_without_its_own_keeps_the_default(self, monkeypatch):
        import fire_interviews
        from pipelines.voices.shows import get_show
        monkeypatch.setattr(fire_interviews, "_clip_is_there", lambda url: True)
        assert fire_interviews.room_clips(get_show("age_of_ai")) == {}

    def test_unreachable_counts_as_absent(self):
        body = FIRE[FIRE.index("def _clip_is_there("):FIRE.index("def room_clips(")]
        assert "except Exception" in body and "return False" in body
        assert "resp.status_code == 200" in body


# ---------------------------------------------------------------------------
# 7. A RETAKE IS A SECOND CHANCE, NOT A SECOND REQUIREMENT.
#
# Voicing those two clips, the first take read all 34 words at 0.84 of the
# expected length, one hundredth under the retake line. The retake lost its
# socket to xAI and the exception threw the good take away with it. The same
# loop voices every episode's introduction and close.

class TestAFailedRetakeKeepsTheGoodTake:
    def _run(self, monkeypatch, tmp_path, outcomes):
        """outcomes: per attempt, either a ratio (take recorded) or an
        exception (take failed). Returns the uploaded path or raises."""
        import narrate
        seq = iter(outcomes)
        ratios = {}

        def record(slug, seg_id, n, para, voice):
            nxt = next(seq)
            if isinstance(nxt, Exception):
                raise nxt
            url = f"u{len(ratios)}"
            ratios[url] = nxt
            return url

        class _Resp:
            def __init__(self, url): self.content = url.encode()
        monkeypatch.setattr(narrate, "_record_take", record)
        monkeypatch.setattr(narrate.requests, "get", lambda url, timeout=0: _Resp(url))
        monkeypatch.setattr(narrate, "_trim", lambda part: part)
        monkeypatch.setattr(narrate, "_take_shortfall",
                            lambda part, text: ratios[part.read_bytes().decode()])
        monkeypatch.setattr(narrate, "_check_not_truncated", lambda part, text: None)
        monkeypatch.setattr(narrate, "_stitch", lambda parts, out, *level: parts[0])
        uploaded = []
        monkeypatch.setattr(narrate, "r2_upload",
                            lambda path, key: uploaded.append(path.read_bytes().decode()) or key)
        spec = tmp_path / "t.json"
        spec.write_text(json.dumps({"show": "nerra_voices", "segments": [
            {"id": "disclosure", "text": "One short paragraph."}]}))
        monkeypatch.setattr(narrate, "NARRATION_DIR", tmp_path)
        monkeypatch.setenv("NARRATION_ENGINE", "agent")
        narrate.narrate("t")
        return uploaded

    def test_what_happened_now_keeps_the_first_take(self, monkeypatch, tmp_path):
        up = self._run(monkeypatch, tmp_path,
                       [0.84, RuntimeError("take failed: socket closed: 1006")])
        assert up == ["u0"]

    def test_a_first_take_that_fails_gets_another_go(self, monkeypatch, tmp_path):
        up = self._run(monkeypatch, tmp_path, [RuntimeError("1006"), 0.95])
        assert up == ["u0"]   # the only take that came back

    def test_no_usable_take_at_all_still_fails(self, monkeypatch, tmp_path):
        with pytest.raises(RuntimeError):
            self._run(monkeypatch, tmp_path,
                      [RuntimeError("a"), RuntimeError("b"), RuntimeError("c")])

    def test_the_longest_take_still_wins_when_nothing_fails(self, monkeypatch, tmp_path):
        up = self._run(monkeypatch, tmp_path, [0.70, 0.80, 0.84])
        assert up == ["u2"]


# ---------------------------------------------------------------------------
# 8. THE ROOM'S CLIPS AT THE ROOM'S LEVEL.
#
# Narration is mastered for an episode at -16 LUFS. Mira live in the room
# measured -22.9 on Viktor's run, and the first Nerra Voices consent notice
# came out at -16.4: a loud notice, then Mira nearly 7 dB quieter, in the
# first ten seconds of every interview.

NARRATE = (V / "narrate.py").read_text(encoding="utf-8")


class TestTheRoomClipsMatchHerLiveVoice:
    def test_a_spec_names_its_own_level(self):
        assert 'loudness = float(spec.get("loudness") or EPISODE_LOUDNESS)' in NARRATE
        assert 'mp3 = _stitch(parts, work / f"{seg_id}.mp3", loudness)' in NARRATE
        assert "loudnorm=I={loudness}" in NARRATE

    def test_episodes_keep_the_episode_level(self):
        assert "EPISODE_LOUDNESS = -16.0" in NARRATE

    def test_the_room_clips_are_voiced_quieter(self):
        assert NV_SYSTEM["loudness"] == -23

    def test_the_existence_check_goes_past_the_cdn(self):
        body = FIRE[FIRE.index("def _clip_is_there("):FIRE.index("def room_clips(")]
        assert "exists={int(time.time())}" in body

    @pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
    def test_the_stitch_actually_lands_where_it_is_told(self, tmp_path):
        import narrate
        take = _voice(tmp_path / "take.wav", [(0.2, 5.8)], total=6.0)
        out = narrate._stitch([take], tmp_path / "out.mp3", -23.0)
        meas = subprocess.run(
            ["ffmpeg", "-v", "info", "-i", str(out), "-af",
             "loudnorm=print_format=json", "-f", "null", "-"],
            capture_output=True, text=True).stderr
        got = float(json.loads(meas[meas.rindex("{"):meas.rindex("}") + 1])["input_i"])
        assert -25.0 < got < -21.0


# ---------------------------------------------------------------------------
# 9. ONLY A GUEST WHO HAS SAID YES CAN BE QUOTED TO ANOTHER.
#
# Mira put Meridan Zerner's line to Viktor Popovic while Meridan's own episode
# was still waiting for her approval. The same pool held Rhett Mikols, whose
# interview was killed. episode_records are written when an interview is cut,
# before anyone approves anything.

COMMON_SRC = (V / "common.py").read_text(encoding="utf-8")


class TestOnlyPublishedGuestsAreCarried:
    ROWS = [
        {"interview_id": "viktor", "guest_name": "Viktor Popovic", "guest_email": "v@x",
         "recorded_on": "2026-09-22", "quotes": [{"text": "Two processors only."}]},
        {"interview_id": "meridan", "guest_name": "Meridan Zerner", "guest_email": "m@x",
         "recorded_on": "2026-09-20", "quotes": [{"text": "The architect of your own life."}]},
        {"interview_id": "rhett", "guest_name": "Rhett Mikols", "guest_email": "r@x",
         "recorded_on": "2026-09-17", "quotes": [{"text": "Killed."}]},
        {"interview_id": "vincent", "guest_name": "Vincent Rylan", "guest_email": "vr@x",
         "recorded_on": "2026-09-14", "quotes": [{"text": "Nobody can opt out."}]},
        {"guest_name": "No interview on record", "recorded_on": "2026-09-01",
         "quotes": [{"text": "Orphan."}]},
    ]

    def _insights(self, monkeypatch, published, fail=False):
        import common

        def fake_select(table, query):
            if table == "episode_records":
                return self.ROWS
            if table == "interviews":
                if fail:
                    raise RuntimeError("supabase down")
                return [{"id": i} for i in published if f"{i}" in query]
            raise AssertionError(table)
        monkeypatch.setattr(common, "sb_select", fake_select)
        return [r["guest"] for r in common.show_insights("nerra_voices")]

    def test_unapproved_and_killed_guests_are_not_quoted(self, monkeypatch):
        assert self._insights(monkeypatch, published={"vincent"}) == ["Vincent Rylan"]

    def test_nobody_published_means_nobody_quoted(self, monkeypatch):
        # Nerra Voices today: Viktor and Meridan in review, Rhett killed.
        assert self._insights(monkeypatch, published=set()) == []

    def test_a_record_with_no_interview_is_not_evidence_of_consent(self, monkeypatch):
        assert "No interview on record" not in self._insights(
            monkeypatch, published={"viktor", "meridan", "rhett", "vincent"})

    def test_if_publication_cannot_be_checked_nobody_is_quoted(self, monkeypatch):
        assert self._insights(monkeypatch, published={"vincent"}, fail=True) == []

    def test_the_forced_callback_is_described_by_the_one_that_happened(self):
        assert "architect of your own life to a payments founder" in COMMON_SRC
        assert "would this guest have" in COMMON_SRC


class TestSheIsToldWhenSheWasCutOff:
    def test_the_barge_in_leaves_her_a_note(self):
        start = SCENARIO.index("InputAudioBufferSpeechStarted, function")
        body = SCENARIO[start:SCENARIO.index("\n  });", start)]
        assert "You were cut off" in body
        assert "do NOT pick that sentence up where it stopped" in body
        assert "do not repeat" in body and "their last words back" in body

    def test_it_is_context_not_a_turn(self):
        start = SCENARIO.index("InputAudioBufferSpeechStarted, function")
        body = SCENARIO[start:SCENARIO.index("\n  });", start)]
        note = body[body.index("You were cut off"):]
        assert "responseCreate" not in note

    def test_it_comes_after_the_turn_is_cancelled(self):
        start = SCENARIO.index("InputAudioBufferSpeechStarted, function")
        body = SCENARIO[start:SCENARIO.index("\n  });", start)]
        assert body.index("responseCancel") < body.index("You were cut off")
