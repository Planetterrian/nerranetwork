"""Oct 23 2026 — the end of the closing round (rehearsal 39991520039), and the
seven questions Patrick set the same day.

The rehearsal asked the first six questions in their words and lost the last
two. Handed "How was the experience of being interviewed by an AI?", she
asked a question of her own; handed it again, she went into her goodbye (the
thanks, the network, "that's the end of the recording") three times, each cut
mid-sentence. The guest said "sounds like you trailed off there" and the room
counted that as the answer, to both questions. After her closing thanks the
room went on giving her turns: "Bye, Roddy.", "Silence.", "Nothing.", "Yeah.",
and, to an empty room, "I'm here. Take your time."

Patrick's round: the two questions about the interview are one, sixth; the
last asks for a follow-up interview in six months to a year.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js"
SCENARIO = SCENARIO_PATH.read_text(encoding="utf-8")
SIM = ROOT / "tests" / "fixtures" / "room_sim.js"
PROMPTS = ROOT / "pipelines" / "voices" / "prompts"
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))


def sim(which: str) -> dict:
    res = subprocess.run(["node", str(SIM), str(SCENARIO_PATH), which],
                         capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def round_lines(out: dict) -> list:
    return [x["d"] for x in out["trace"] if x.get("e") in ("round", "close", "turn")]


def entries() -> list:
    i = SCENARIO.index("const ROUND_QUESTIONS = [")
    block = SCENARIO[i:SCENARIO.index("];", i)]
    return re.findall(r'\["([^"]+)", /(.+?)/i(?:, "([^"]*)")?\]', block)


class TestPatricksSevenQuestions:
    def test_the_order(self):
        assert [label for label, _, _ in entries()] == [
            "the show's own question",
            "a book they would recommend",
            "who you should interview next",
            "the best advice they were ever given",
            "who has inspired them most",
            "how being interviewed by an AI was, and one improvement",
            "whether they would like a follow-up interview",
        ]

    def test_the_words(self):
        lines = {label: line for label, _, line in entries()}
        assert lines["how being interviewed by an AI was, and one improvement"] == (
            "How was the experience of being interviewed by an AI, and what's one specific"
            " thing we could improve?")
        follow_up = lines["whether they would like a follow-up interview"]
        assert "follow-up interview" in follow_up
        assert "six months to a year" in follow_up
        assert "projects" in follow_up and "how much I've improved" in follow_up

    def test_no_question_hears_another_ones_words(self):
        rows = entries()
        for label, pattern, _ in rows:
            for other, _, line in rows:
                if other != label and line:
                    assert not re.search(pattern, line, re.I), (label, other)

    def test_the_closing_session_list_matches_the_room(self):
        from fire_interviews import CLOSING_ROUND
        rows = entries()[1:]
        assert len(CLOSING_ROUND) == len(rows)
        for (_, rx), (label, _, line) in zip(CLOSING_ROUND, rows):
            assert rx.search(line), label

    def test_the_briefs_never_name_the_questions(self):
        flat = " ".join((PROMPTS / "mira_system_prompt.txt").read_text(encoding="utf-8").split())
        closing = " ".join((PROMPTS / "mira_closing_session.txt").read_text(encoding="utf-8").split())
        # Oct 23 2026 (rehearsal 39998790684): a brief that names what the
        # round holds is a template she fills with questions of her own, and
        # she spoke its label ("That's the show's own closing question").
        for text in (flat, closing):
            assert "four short closing questions" not in text
            assert "about the interview itself" not in text
            assert "the show's own question" not in text
            assert "No thanks or goodbye until the room says to close" in text or \
                "no thanks or goodbye until the room says to close" in text
        assert "with the words to ask it" in flat

    def test_the_feedback_reader_and_the_closing_cut_still_hear_it(self):
        import auto_edit
        import learning
        line = entries()[5][2]
        assert learning._FEEDBACK_CUE.search(line)
        assert auto_edit.CLOSING_ENDS.search(line)


class TestAQuestionNeverHeardIsNotAnswered:
    """Oct 24 2026: a question that never reached the guest goes again ONCE
    (Stuart Berkowitz's room); after that it is taken as asked and the round
    moves on, so a guest is never held in a loop."""

    def test_the_cut_sign_off_hands_it_again_once(self):
        out = sim("round_end_as_rehearsed")
        lines = round_lines(out)
        label = "how being interviewed by an AI was, and one improvement"
        assert ("the sign-off took the question's place; " + label +
                " goes again when they finish") in lines
        # "handed" starts after its first hand: exactly one more, never two.
        assert sum(1 for h in out["handed"] if h.split("\n\n")[-1].startswith("[ROUND 6 of 7")) == 1
        # The second cut finds it already handed again: taken as asked.
        assert any(x.startswith("taken as asked: " + label) for x in lines)
        assert "answered 6/7" in lines and "answered 7/7" in lines
        assert out["afterTrailedOff"]["roundIndex"] == 6

    def test_one_budget_for_every_reason(self):
        assert "const ROUND_REHANDS_MAX = 1;" in SCENARIO
        fn = SCENARIO[SCENARIO.index("function roundAnswered()"):]
        fn = fn[:fn.index("\nfunction ", 10)]
        assert "owedRehand(label, \"they spoke, but it never reached them\")" in fn
        assert "ROUND_UNHEARD_REHANDS_MAX" not in SCENARIO
        assert "roundIndex -= 1" not in SCENARIO

    def test_the_metric_says_the_round_was_not_complete(self):
        import audio_metrics
        out = sim("round_end_as_rehearsed")
        summary = audio_metrics.closing_round(out["trace"])
        assert summary["round_asked"] == 7
        assert summary["round_stacked"] == 0
        assert summary["round_unheard"] == 1
        assert summary["closing_round_complete"] is False


class TestSheKnowsTheRoundIsNotOver:
    def test_each_question_says_what_is_still_to_come(self):
        out = sim("round_end_as_rehearsed")
        round_turns = [h.split("\n\n")[-1] for h in out["handed"]]
        sixth = [h for h in round_turns if h.startswith("[ROUND 6 of 7")]
        seventh = [h for h in round_turns if h.startswith("[ROUND 7 of 7")]
        assert sixth and seventh
        # Oct 24 2026: said in words that never name the end (naming what not
        # to do yet was itself the cue, candidate rehearsal 40110915521).
        assert all("the room hands you 2 more questions." in h for h in sixth)
        assert "the room hands you one more question." in seventh[0]
        for h in sixth + seventh:
            low = h.lower()
            for word in ("goodbye", "thanks", "last word", "recording"):
                assert word not in low, (word, h)
            # Directions first, the question's words last.
            assert h.splitlines()[-1].endswith("?")


class TestNothingAfterTheGoodbye:
    def test_one_goodbye_then_silence(self):
        out = sim("round_end_as_rehearsed")
        assert out["createsAfterThanks"] == 1
        assert out["lastInstructions"].endswith("Say goodbye in a few words and end your turn there.")
        assert round_lines(out).count("the interview is over; no turn after her goodbye") == 1
        # Once they have gone, no turn at all (Oct 24 2026).
        assert "no guest in the room; no turn" in round_lines(out)

    def test_no_time_notes_after_the_round(self):
        tick = SCENARIO[SCENARIO.index("function startTimeChecks()"):]
        tick = tick[:tick.index("const elapsed")]
        assert "if (roundClosed) return;" in tick


# ---------------------------------------------------------------------------
# Rehearsal 39998790684 (the seven questions' first rehearsal), same day
# ---------------------------------------------------------------------------

class TestAQuestionOfHerOwnIsNotTheRoundQuestion:
    """Handed "Who's one person you think I should interview next?" she asked
    "What's one thing you learned about yourself through doing this
    interview?", and the topic check took the word "interview" as the
    question asked. Handed the advice question twice, she asked the follow-up
    interview question, and the second miss was taken as the advice question
    reworded."""

    def test_the_invented_question_is_handed_back(self):
        out = sim("another_round_question_in_its_place")
        lines = round_lines(out)
        assert ("her turn asked something else; who you should interview next goes again"
                " when they finish") in lines
        assert out["afterInvented"]["roundIndex"] == 2

    def test_another_round_question_never_counts_as_this_one(self):
        out = sim("another_round_question_in_its_place")
        lines = round_lines(out)
        # Handed the advice question she reacted only: handed again, once.
        assert ("her turn asked nothing; the best advice they were ever given goes again"
                " when they finish") in lines
        # Handed again, she asked the follow-up question instead: that is
        # never this one reworded, and with its one re-hand spent the advice
        # question is taken as asked (Oct 24 2026), never a third time.
        assert any(x.startswith("taken as asked: the best advice they were ever given") for x in lines)
        assert out["afterFollowUp"]["roundIndex"] == 4
        assert "answered 4/7" in lines

    def test_the_topic_check_does_not_take_any_interview_word(self):
        topics = SCENARIO[SCENARIO.index("const ROUND_TOPICS = {"):]
        line = [ln for ln in topics.splitlines() if ln.strip().startswith('"who you should interview next"')][0]
        rx = re.compile(line.split(": /", 1)[1].rsplit("/i", 1)[0], re.I)
        assert not rx.search("What's one thing you learned about yourself through doing this interview?")
        assert rx.search("Who should I talk to next?")


class TestNoStageWordsInHerTurns:
    """She says "Silence." and "Nothing." when an instruction for a spoken
    turn tells her to wait in silence or say nothing else (rehearsals
    39991520039 and 39998790684, and the Oct 22 hold check-in)."""

    def test_round_and_goodbye_turns_carry_no_speakable_stage_words(self):
        # Oct 24 2026 (Stuart's room): she said "Silence." and read a label
        # aloud. No round turn says "silence" or "stop talking"; each ends on
        # the words she is to say.
        for fn in ("askNextRoundQuestion", "askRoundLastWord", "closeRound", "roundReprompt"):
            body = SCENARIO[SCENARIO.index(f"function {fn}("):]
            body = body[:body.index("\nfunction ", 10)]
            body = "\n".join(ln for ln in body.splitlines() if not ln.strip().startswith("//"))
            assert "silence" not in body.lower(), fn
            assert "stop talking" not in body, fn
        assert "Say goodbye in a few words and end your turn there." in SCENARIO
        assert "Nothing else.\";" not in SCENARIO


class TestAPersonCanJoinTheDraftRoom:
    def test_the_studio_dials_the_candidate_only_with_room_candidate(self):
        studio = (ROOT / "age-of-ai-studio.html").read_text(encoding="utf-8")
        assert 'var candidateRoom = params.get("room") === "candidate";' in studio
        assert 'number: candidateRoom ? "mira-candidate" : "mira"' in studio

    def test_the_candidate_rule_takes_that_number_and_nothing_live(self):
        from voximplant.api_clients import voximplant_client as vc
        rx = re.compile(vc.CANDIDATE_ROOM_RULE_PATTERN)
        assert rx.match(vc.CANDIDATE_STUDIO_NUMBER) and rx.match("candroom-abc")
        for live in ("mira", "room-abc", "mira-candidatex"):
            assert not rx.match(live), live

    def test_the_candidate_scenario_answers_it_as_a_participant(self):
        # Any destination that is not the room prefix is a participant session.
        assert ('if (dest.indexOf(ROOM_PREFIX) === 0) return roomAlerting(e, dest);\n'
                '  return participantAlerting(e);') in SCENARIO

    def test_the_invite_link_and_email(self):
        import rehearsal
        link = rehearsal.invite_link({"id": "11111111-1111-1111-1111-111111111111",
                                      "show": "age_of_ai"})
        assert link.endswith("&role=guest&room=candidate")
        live = rehearsal.invite_link({"id": "11111111-1111-1111-1111-111111111111",
                                      "show": "age_of_ai"}, "deployed")
        assert "room=candidate" not in live
        subject, body = rehearsal.invite_email("Patrick Novak", link, 15, "candidate")
        assert "Hi Patrick," in body and "draft of the interview room" in body
        assert "Nothing from this room is published" in body

    def test_the_test_interview_is_a_rehearsal_and_never_a_guest(self, monkeypatch):
        import common
        import rehearsal
        inserted = []
        monkeypatch.setattr(common, "sb_select", lambda table, q: [])
        monkeypatch.setattr(common, "sb_insert",
                            lambda table, row: inserted.append((table, row)) or {"id": f"{table}-1", **row})
        pair = rehearsal.ensure_invite_interview(
            {"id": "a", "email": "someone@example.com", "name": "Some One", "show": "age_of_ai"}, 15)
        (t1, app), (t2, iv) = inserted
        assert t1 == "guest_applications" and app["status"] == "rehearsal"
        assert app["name"] == "Some One (test room)"
        assert t2 == "interviews" and iv["status"] == "rehearsal"
        assert iv["session_kind"] == "rehearsal" and iv["host_mode"] is False
        assert pair["interview"]["application_id"] == "guest_applications-1"

    def test_the_link_and_address_stay_out_of_the_log(self, monkeypatch, capsys, tmp_path):
        import rehearsal
        monkeypatch.setattr(rehearsal, "_source_application",
                            lambda email: {"id": "a", "email": email, "name": "Some One"})
        monkeypatch.setattr(rehearsal, "ensure_invite_interview",
                            lambda src, m: {"interview": {"id": "iv", "show": "age_of_ai"}})
        monkeypatch.setattr(rehearsal, "invite_prompt", lambda src, m: "PROMPT")
        monkeypatch.setattr(rehearsal, "build_run_row",
                            lambda **kw: {"grok_session_log": {"rehearsal": {}}})
        monkeypatch.setattr(rehearsal, "create_run", lambda row: {"id": "run-1", **row})
        monkeypatch.setattr(rehearsal, "wait_for_join", lambda run_id, m: {})
        sent = []
        out = rehearsal.invite_one(email="someone@example.com", minutes=15, scenario="candidate",
                                   out_dir=tmp_path, wait_minutes=0,
                                   send=lambda to, subject, body: sent.append((to, body)))
        assert out is None and sent and "room=candidate" in sent[0][1]
        printed = capsys.readouterr().out
        assert "run-1" in printed
        assert "someone@example.com" not in printed and "studio" not in printed

    def test_the_workflow_passes_the_address_through_the_environment(self):
        wf = (ROOT / ".github" / "workflows" / "nerra_voices_rehearsal.yml").read_text(encoding="utf-8")
        step = wf[wf.index("- name: Invite a person to a test room"):]
        step = step[:step.index("- name: Re-measure")]
        assert 'INVITE_EMAIL: ${{ inputs.invite_email }}' in step
        assert "${{ inputs.invite_email }}" not in step.split("env:")[0]
        assert "RESEND_API_KEY" in step
        for name in ("Upload this ref's fixture guest", "Rehearse the current configuration",
                     "Rehearse the proposed configuration"):
            block = wf[wf.index(f"- name: {name}"):]
            assert "inputs.invite_email == ''" in block[:block.index("run:")], name
