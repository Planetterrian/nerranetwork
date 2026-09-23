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

3. WHY THE TRANSCRIPT WAS A MESS, which is the one that mattered. Viktor's
   browser recording never uploaded, and the two-track path was gated on the
   GUEST's track being local rather than on Mira having audio of her own. So a
   run holding a clean guest channel and a real Mira-only leg fell through to
   transcribing the raw Voximplant stereo — whose right channel carries the
   guest's own voice back — and his sentences were attributed to her. The
   grading pass read that as Mira parroting her guest, scored her listening at
   three, and adopted a standing instruction about a fault that was not hers.
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


class TestTheGraderIsToldAboutBothDirections:
    def test_it_knows_the_guest_can_land_in_her_channel(self):
        assert "IT HAPPENS THE OTHER WAY ROUND TOO" in RETRO
        assert "OPENS with the tail of" in RETRO

    def test_it_is_told_not_to_grade_those_dimensions_from_such_a_tape(self):
        block = RETRO[RETRO.index("IT HAPPENS THE OTHER WAY ROUND TOO"):]
        assert "do not grade listening, turn-taking or repetition" in block
        assert "propose no lesson that depends on who said what" in block

    def test_a_relapse_is_not_adopted_as_a_new_lesson(self):
        assert "AND A RELAPSE IS NOT A NEW LESSON" in RETRO
        block = RETRO[RETRO.index("AND A RELAPSE IS NOT A NEW LESSON"):]
        assert "adopt nothing" in block
        assert "relapse against that lesson's" in block
