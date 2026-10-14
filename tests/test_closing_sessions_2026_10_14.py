"""Oct 14 2026: a closing session that the next guest will not have to hear
about. Three things went wrong in Piper Martz's, all fixed here.

1. The splice. Her closing session went onto the end of her episode from
   Mira's "We left off right in the middle of your book recommendation" to
   the end of the room, so the episode carried a break the listener never
   heard, her suggestion for what we could improve (which she had prefaced
   with "I wouldn't include this in the formal interview"), and the sign-off.
   It now starts on the Mira turn her first real answer follows, ends before
   the improvement question or the sign-off, and the transcript the guest
   approves keeps only those lines.

2. The brief. The first session had already reached the show's own question,
   and the closing session asked it again: the same bet and the same IKEA
   story, twice. Mira is now given the questions the first recording already
   finished, and told not to ask them.

3. The sign-off. The room only learns the guest has answered the last-word
   question from a transcription it never receives, so it decided Piper's
   "Nope, thank you so much" was silence, held the room open twice, and Mira
   said "You can hang up now" three times. The guest speaking now answers it.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
sys.path.insert(0, str(ROOT))

SCENARIO = (ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js").read_text(encoding="utf-8")
PROMPT = (ROOT / "pipelines" / "voices" / "prompts" / "mira_closing_session.txt").read_text(encoding="utf-8")

# Piper's closing session, as the pipeline transcribed it (Oct 13 2026),
# shortened. The guest's lines run a few seconds early against Mira's.
PIPER_CLOSING = "\n".join([
    "[00:14] Piper: Great. Hi Mira. I'm great. I'm happy to be back and finish running through the lightning round.",
    "[00:19] Mira: For it's so good to have you back, I'm sorry the room cut us off last time.",
    "[00:31] Mira: How are you?",
    "[00:41] Mira: I'm glad to hear it.",
    "[00:43] Mira: We left off right in the middle of your book recommendation, so let's pick that thread",
    "[00:47] Mira: back up and finish the lightning round, then a few closing questions, a few minutes",
    "[00:55] Piper: Sounds good.",
    "[01:00] Mira: You're back in the quick lightning round.",
    "[01:01] Mira: You were saying you love by Priya Parker.",
    "[01:05] Mira: Go ahead and finish that thought.",
    "[01:08] Piper: Yeah, one of my favorite books if you know me well or have ever chatted with me is The Art of Gathering by Priya Parker.",
    "[02:52] Mira: That's a beautiful thread to pick back up. What's one person you think I should interview next?",
    "[03:06] Piper: Paige Keeho is the founder of Audacious AI Friends, also known as Audacious AF.",
    "[09:08] Mira: What's the one bet you're making for the next 12 months that you cannot prove yet?",
    "[09:16] Piper: making is I really believe equipping leaders with better management skills",
    "[11:12] Mira: That's the bet that matters most.",
    "[11:14] Mira: How was the experience of being interviewed by an AI?",
    "[11:22] Piper: Definitely different than most of the other podcasts I've done before.",
    "[12:09] Piper: part of communication and it's yeah very strange to have an interview without that.",
    "[12:17] Mira: The absence of body language changes the whole rhythm.",
    "[12:20] Mira: What's one specific thing we could improve?",
    "[12:26] Piper: Candidly and I wouldn't include this in the formal interview but I guess",
    "[13:59] Mira: Do you have any parting thoughts?",
    "[14:07] Mira: Thank you, Piper. That's the end of the recording.",
    "[14:12] Mira: You can hang up now.",
    "[14:32] Piper: could hang up like three four times so also another little funny glitch",
])


def _rows(text: str) -> list:
    import auto_edit
    out = []
    for line in text.splitlines():
        m = auto_edit._LINE.match(line)
        h, mm, ss, who, said = m.groups()
        t = (int(h) * 3600 + int(mm) * 60 + int(ss)) if ss else (int(h) * 60 + int(mm))
        out.append((float(t), who, said))
    return out


class TestTheSpliceKeepsWhatAListenerShouldHear:
    def test_it_starts_on_the_question_her_answer_follows(self):
        import auto_edit
        begin, _end = auto_edit._closing_span(_rows(PIPER_CLOSING))
        assert begin == 60.0        # "You're back in the quick lightning round"

    def test_it_ends_before_the_improvement_question_and_mira_s_reply(self):
        import auto_edit
        _begin, end = auto_edit._closing_span(_rows(PIPER_CLOSING))
        assert end == 737.0         # the turn "The absence of body language..." opens

    def test_a_session_that_never_got_there_has_no_end_of_its_own(self):
        import auto_edit
        rows = _rows("\n".join(PIPER_CLOSING.splitlines()[:13]))
        assert auto_edit._closing_span(rows)[1] is None

    def test_the_sign_off_ends_it_when_nothing_else_does(self):
        import auto_edit
        rows = [r for r in _rows(PIPER_CLOSING) if "improve" not in r[2]]
        _b, end = auto_edit._closing_span(rows)
        assert end == 839.0         # "Do you have any parting thoughts?" opens the closing turn

    def test_an_answer_with_no_lead_in_still_starts_on_the_question(self):
        import auto_edit
        rows = _rows("\n".join([
            "[00:05] Mira: Welcome back, Piper. How are you?",
            "[00:09] Piper: Good, thanks.",
            "[00:40] Mira: We're back in the quick lightning round. You were telling me about a book.",
            "[00:48] Piper: The Art of Gathering.",
        ]))
        assert auto_edit._closing_span(rows)[0] == 40.0

    def test_the_guest_approves_only_the_lines_the_episode_keeps(self):
        import auto_edit
        kept = auto_edit._closing_text_between(PIPER_CLOSING, 60.0, 737.0)
        assert kept.startswith("[01:00] Mira: You're back in the quick lightning round.")
        assert "very strange to have an interview without that" in kept
        for gone in ("We left off", "Candidly", "hang up", "absence of body language"):
            assert gone not in kept, gone

    def test_splice_closing_writes_the_span_and_the_trimmed_transcript(self, monkeypatch, tmp_path):
        import auto_edit as ae
        monkeypatch.setattr(ae, "EDL_DIR", tmp_path / "edl")
        monkeypatch.setattr(ae, "NARRATION_DIR", tmp_path / "narr")
        parent = {"run_id": "r1", "interview_id": "iv1", "show": "age_of_ai", "note": "n",
                  "cuts": [{"from": "narration:intro"}, {"gap": 0.7},
                           {"from": "mix:clean", "start": 20.0, "end": 2987.2},
                           {"gap": 1.4}, {"from": "narration:outro"}]}
        writes = []
        monkeypatch.setattr(ae, "sb_select", lambda t, q="": (
            [{"id": "e1", "slug": "piper_y", "edl": parent, "narration": {}}]
            if t == "episode_edits" else
            [{"id": "p1", "transcript_cleaned": "[49:52] Mira: A book you would recommend?"}]
            if t == "editorial_packages" else []))
        monkeypatch.setattr(ae, "sb_update", lambda t, q, patch: writes.append((t, patch)))
        monkeypatch.setattr(ae, "_leg_offset", lambda run: 0.0)
        ctx = {"run": {"id": "r2", "duration_sec": 880, "created_at": "2026-10-13T16:01:00Z"},
               "interview": {"id": "iv2", "session_kind": "closing",
                             "continues_interview_id": "iv1"},
               "app": {}, "package": {"transcript_raw": PIPER_CLOSING}}
        ae.splice_closing(ctx)
        cuts = json.loads((tmp_path / "edl" / "piper_y.json").read_text())["cuts"]
        (piece,) = [c for c in cuts if c.get("run_id") == "r2"]
        assert piece["start"] == 59.6 and piece["end"] == 737.0
        (text,) = [p["transcript_cleaned"] for t, p in writes if t == "editorial_packages"]
        assert "[Closing session]" in text and "Candidly" not in text and "hang up" not in text


class TestMiraIsToldWhatTheFirstRecordingFinished:
    QUESTION = "What's the one bet you're making for the next twelve months that you cannot prove yet?"
    FIRST = "\n".join([
        "[45:10] Piper: and that is the whole point of change management.",
        "[46:28] Mira: What's the one bet you're making for the next 12 months that you cannot prove yet?",
        "[46:40] Piper: I really believe getting more leaders improving their AI literacy",
        "[49:45] Piper: operational cost savings. One of my favorite books, if you've met me before",
        "[49:48] Mira: That's the bet.",
        "[49:50] Mira: We're moving to a quick lightning round.",
        "[49:52] Mira: A book you would recommend and in a sentence why?",
        "[50:02] Piper: interviews, I love the art of gathering by Priya Parker.",
    ])

    def test_the_answered_show_question_is_listed_and_the_cut_off_one_is_not(self):
        import fire_interviews as fi
        covered = fi.covered_in_transcript(self.FIRST, self.QUESTION)
        assert covered == [f'The show\'s own question: "{self.QUESTION}"']

    def test_nothing_finished_says_so(self):
        import fire_interviews as fi
        assert fi.covered_in_transcript("[01:00] Mira: Welcome.\n[01:05] Piper: Hi.", self.QUESTION) == []

    def test_the_spliced_transcript_is_not_mistaken_for_the_first_recording(self):
        import fire_interviews as fi
        spliced = self.FIRST + "\n\n[Closing session]\n[02:55] Mira: What's one person you think I should interview next?\n[03:02] Piper: Three women.\n[05:19] Mira: Three strong recommendations."
        assert not any("interview next" in c for c in fi.covered_in_transcript(spliced, self.QUESTION))

    def test_it_reaches_her_prompt(self, monkeypatch):
        import fire_interviews as fi
        monkeypatch.setattr(fi, "sb_select", lambda t, q="": [{"transcript_raw": self.FIRST}])
        block = fi.already_answered({"continues_interview_id": "iv1"}, self.QUESTION)
        assert block.startswith("- The show's own question")
        assert "{{already_answered}}" in PROMPT
        assert "do NOT ask any of them again" in PROMPT
        src = (ROOT / "pipelines" / "voices" / "fire_interviews.py").read_text(encoding="utf-8")
        assert "already_answered=already_answered(interview, show.closing_question)" in src

    def test_the_prompt_resumes_on_a_line_a_listener_can_follow(self):
        assert "ask the question in full" in PROMPT
        assert "Do not say you were cut off" in PROMPT
        assert "Say the welcome and the apology ONCE" in PROMPT
        assert "do not announce the\n   end of the recording again" in PROMPT


class TestTheGuestSpeakingAnswersTheLastWord:
    def _fn(self, name: str) -> str:
        i = SCENARIO.index("function " + name + "(")
        j = SCENARIO.index("\n}\n", i)
        return SCENARIO[i:j]

    def test_speech_after_the_question_marks_it_answered(self):
        body = self._fn("noteGuestSpoke")
        assert "lastWordAnswered = true" in body
        assert "inboundSpokeAt <= lastWordAskedAt" in body
        assert "ms < LAST_WORD_MIN_SPEECH_MS" in body
        assert re.search(r"const LAST_WORD_MIN_SPEECH_MS = 500;", SCENARIO)

    def test_the_room_measures_it_when_the_guest_stops(self):
        i = SCENARIO.index("InputAudioBufferSpeechStopped, function () {")
        assert "noteGuestSpoke(Date.now() - inboundSpokeAt);" in SCENARIO[i:i + 200]

    def test_a_build_without_the_stopped_event_still_hears_them(self):
        i = SCENARIO.index("InputAudioBufferSpeechStarted, function () {")
        assert "noteGuestSpoke(LAST_WORD_MIN_SPEECH_MS)" in SCENARIO[i:i + 400]
