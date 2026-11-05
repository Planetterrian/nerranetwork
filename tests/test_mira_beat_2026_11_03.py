"""Nov 3 2026 (the six-month review, voices-1): the beat before the question.

The Oct 21 brief's last critical line banned the grade and the echo, and the
first room on it obeyed by reacting to nothing: on the published Ep15
transcript 15 of Mira's 28 question turns go straight to the question with
no sentence of her own before it (Ep12 5 of 37), her median turn is 18
words and 4.9 s against the 12-20 s band, and the guest's answers shortened
from 178 words to 58 across the hour. Nothing in the loop could see the
trade, because no measure rose when she reacted.

These guards hold the pieces together: the measure (``bare_question_rate``,
beside ``label_open_rate``; a question turn is a label, is bare, or carries
a reaction, and the three add to one), its consumers (the targets and the
weekly pass through ``is_green``, the retro grader's vocabulary and the
metrics it is handed, the readout email, the rehearsal report), the brief
(the beat is the critical list's last line, by shape, with the two opener
prohibitions still where they stood), the edit (a reaction in her own words
followed by a question is never read as bleed) and the notes (the incident
lives in ``docs/mira_craft_notes.md``, never in the prompt).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
V = ROOT / "pipelines" / "voices"
sys.path.insert(0, str(V))

import audio_metrics as am  # noqa: E402

PROMPT = (V / "prompts" / "mira_system_prompt.txt").read_text(encoding="utf-8")
RETRO = (V / "prompts" / "editorial_passes" / "09_interview_retro.txt").read_text(encoding="utf-8")
POST = (V / "post_interview.py").read_text(encoding="utf-8")
LEARNING = (V / "learning.py").read_text(encoding="utf-8")
NOTES = (ROOT / "docs" / "mira_craft_notes.md").read_text(encoding="utf-8")
DIGESTS = ROOT / "digests"

LINE_RE = re.compile(r"^\[(\d{1,2}):(\d{2})\]\s*([^:]+):\s*(.*)$")


def _turn(text: str) -> dict:
    return {"words": text.split()}


def _flat(text: str) -> str:
    return " ".join(text.split())


def transcript_turns(path: Path) -> list[dict]:
    """Mira's turns from a published transcript: consecutive ``Mira:`` lines
    are one turn (the published page writes a sentence a line); narration is
    labelled ``Mira (narration)`` and is not a turn in the room."""
    turns: list[dict] = []
    current: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = LINE_RE.match(line.strip())
        if not m:
            continue
        speaker, text = m.group(3).strip(), m.group(4).strip()
        if speaker == "Mira":
            current.append(text)
        elif current:
            turns.append(_turn(" ".join(current)))
            current = []
    if current:
        turns.append(_turn(" ".join(current)))
    return turns


# 1. The shape of a question turn ------------------------------------------------

class TestTheShapeOfAQuestionTurn:
    def test_a_question_with_nothing_of_her_own_before_it_is_bare(self):
        assert am.question_turn_shape("What drew you to that field in the first place?") == "bare"
        assert am.question_turn_shape("Did anyone on the team push back on handing that to candidates?") == "bare"

    def test_a_greeting_or_a_name_is_not_a_sentence_about_the_answer(self):
        assert am.question_turn_shape("Thanks, Michael. What happened next?") == "bare"
        assert am.question_turn_shape("Right. Where does that leave them?") == "bare"
        assert am.question_turn_shape("Okay. Who ran it?") == "bare"

    def test_a_few_words_before_the_question_are_a_label(self):
        assert am.question_turn_shape(
            "Agility instead of disloyalty. What's the mechanism you think makes that true?") == "label"
        assert am.question_turn_shape("Deadwood showing itself. Where does that leave them?") == "label"

    def test_a_sentence_of_four_words_or_more_before_the_question_is_a_reaction(self):
        assert am.question_turn_shape(
            "That decision cost the team its whole second quarter. What did you cut first?") == "reaction"
        assert am.question_turn_shape(
            "Right, and that changes what the parser is actually for. What breaks first?") == "reaction"

    def test_a_question_folded_into_one_sentence_is_bare(self):
        # The beat is a sentence of its own, then the question.
        assert am.question_turn_shape("I wonder, given what it cost, what you cut first?") == "bare"

    def test_a_turn_that_asks_nothing_is_not_judged(self):
        assert am.question_turn_shape("Welcome, Michael.") is None
        assert am.question_turn_shape("") is None

    def test_a_short_first_sentence_is_a_label_whatever_follows_it(self):
        # label_open_rate's own rule, so the two measures never double-count.
        assert am.question_turn_shape(
            "That is a real cost. And the team felt it before the numbers did. What did you cut?") == "label"
        assert am.REACTION_MIN_WORDS == 4 and am.LABEL_MAX_WORDS == 8


class TestTheThreeShapesAddToOne:
    TURNS = [
        _turn("What drew you to that field in the first place?"),                 # bare
        _turn("Thanks, Michael. What happened next?"),                            # bare
        _turn("Agility instead of disloyalty. What makes that true?"),            # label
        _turn("That decision cost the team its whole second quarter. What did you cut?"),  # reaction
        _turn("Right, and that changes what the parser is for. What breaks first?"),  # reaction
        _turn("Welcome, Michael."),                                               # not judged
    ]

    def test_counts(self):
        counts = am.question_turn_shapes(self.TURNS)
        assert counts == {"label": 1, "bare": 2, "reaction": 2, "judged": 5}
        assert counts["label"] + counts["bare"] + counts["reaction"] == counts["judged"]

    def test_the_rates_are_the_counts_over_the_judged_turns(self):
        assert am.bare_question_rate(self.TURNS) == 0.4
        assert am.label_open_rate(self.TURNS) == 0.2
        assert am.bare_question_rate([]) is None
        assert am.bare_question_rate([_turn("Welcome, Michael.")]) is None

    def test_label_open_rate_reads_as_it_did_on_glenn_broders_hour(self):
        turns = [{"words": ["Deadwood", "showing", "itself.", "Where", "does", "that", "leave", "them?"]},
                 {"words": ["Collective", "fattening.", "Who", "inspired", "you", "most?"]},
                 {"words": ["What", "pulled", "you", "in?"]},
                 {"words": ["Hello,", "Glenn.", "How", "are", "you?"]}]
        assert am.label_open_rate(turns) == 0.5
        assert am.bare_question_rate(turns) == 0.5


# 2. Calibrated on the published transcripts -------------------------------------

class TestTheCommittedTranscripts:
    """The six published transcripts the review recounted. Ep15 (the first
    room on the Oct 21 brief, hand re-cut on Oct 29) reads about one bare
    question in two; Ep12 about one in seven. Published pages do not change,
    so the bands are a calibration, not a trend."""

    CASES = (
        ("age_of_ai/Age_of_AI_Ep015_20261101.md", 0.45, 0.60),
        ("age_of_ai/Age_of_AI_Ep012_20261014.md", 0.10, 0.20),
        ("age_of_ai/Age_of_AI_Ep013_20261024.md", None, None),
        ("age_of_ai/Age_of_AI_Ep014_20261025.md", None, None),
        ("nerra_voices/Nerra_Voices_Ep003_20261015.md", None, None),
        ("nerra_voices/Nerra_Voices_Ep004_20261026.md", None, None),
    )

    @pytest.mark.parametrize("rel, low, high", CASES)
    def test_bare_question_rate_and_the_sum(self, rel, low, high):
        path = DIGESTS / rel
        if not path.exists():
            pytest.skip(f"{rel} is not in this checkout")
        turns = transcript_turns(path)
        counts = am.question_turn_shapes(turns)
        assert counts["judged"] >= 10, rel
        assert counts["label"] + counts["bare"] + counts["reaction"] == counts["judged"]
        shares = (am.label_open_rate(turns), am.bare_question_rate(turns),
                  counts["reaction"] / counts["judged"])
        assert abs(sum(shares) - 1.0) < 0.005, (rel, shares)
        if low is not None:
            assert low <= am.bare_question_rate(turns) <= high, (rel, am.bare_question_rate(turns))

    def test_ep15_reads_bare_where_ep12_reacted(self):
        ep15 = DIGESTS / "age_of_ai/Age_of_AI_Ep015_20261101.md"
        ep12 = DIGESTS / "age_of_ai/Age_of_AI_Ep012_20261014.md"
        if not (ep15.exists() and ep12.exists()):
            pytest.skip("the two transcripts are not in this checkout")
        assert am.bare_question_rate(transcript_turns(ep15)) > 2 * am.bare_question_rate(transcript_turns(ep12))


# 3. Wired into the loop ----------------------------------------------------------

def _words(text: str, start: float, wps: float = 2.5) -> list[dict]:
    out, t = [], start
    for w in text.split():
        out.append({"start": round(t, 3), "end": round(t + 1.0 / wps * 0.8, 3), "word": w})
        t += 1.0 / wps
    return out


def _room() -> dict:
    mira, guest = [], []
    t = 0.0
    lines = ("What drew you to that field in the first place?",
             "Thanks, Michael. What happened next?",
             "Agility instead of disloyalty. What makes that true?",
             "That decision cost the team its whole second quarter. What did you cut?")
    for line in lines:
        ws = _words(line, t)
        mira += ws
        t = ws[-1]["end"] + 0.6
        gs = _words("well the honest answer is that it took the whole quarter to see it " * 3, t)
        guest += gs
        t = gs[-1]["end"] + 0.6
    return {"mira": mira, "guest": guest}


class TestItIsWiredIn:
    def test_measure_audio_carries_the_three_shapes_as_notes(self):
        m = am.measure_audio(_room())
        assert m["metrics_basis"] == "audio"
        assert m["bare_question_rate"] == 0.5
        assert m["label_open_rate"] == 0.25
        assert m["reaction_open_rate"] == 0.25
        assert m["question_turn_shapes"] == {"label": 1, "bare": 2, "reaction": 1, "judged": 4}
        assert abs(m["label_open_rate"] + m["bare_question_rate"] + m["reaction_open_rate"] - 1.0) < 0.005
        # No migration: COLUMNS is unchanged and the measure rides in notes.
        for key in ("bare_question_rate", "reaction_open_rate", "question_turn_shapes", "label_open_rate"):
            assert key not in am.COLUMNS
            assert key in am.notes(m) and key not in am.columns(m)

    def test_an_unmeasured_room_is_none_never_zero(self):
        m = am.measure_audio({"mira": _words("hello there", 0.0)})
        assert "bare_question_rate" not in m or m["bare_question_rate"] is None

    def test_the_target_is_down_at_a_quarter(self):
        assert am.TARGETS["bare_question_rate"] == ("down", 0.25)
        assert am.TARGETS["label_open_rate"] == ("down", 0.35)

    def test_is_green_reads_the_note_the_weekly_pass_hands_it(self):
        # adopt_lessons_weekly hands is_green the episode_metrics ROW; the
        # measure is not a column, so it is read under notes.audio.
        assert am.is_green("bare_question_rate", {"notes": {"audio": {"bare_question_rate": 0.2}}}) is True
        assert am.is_green("bare_question_rate", {"notes": {"audio": {"bare_question_rate": 0.54}}}) is False
        assert am.is_green("bare_question_rate", {"notes": {"audio": {}}}) is None
        assert am.is_green("bare_question_rate", {}) is None
        # ... and the label beside it, which the same gap had made unretirable.
        assert am.is_green("label_open_rate", {"notes": {"audio": {"label_open_rate": 0.1}}}) is True
        assert am.metric_value({"seams": 0, "notes": {"audio": {"seams": 3}}}, "seams") == 0

    def test_a_lesson_may_name_it(self):
        import learning
        assert "bare_question_rate" in learning.LESSON_METRICS
        assert "|| bare_question_rate" not in RETRO
        vocabulary = next(line for line in RETRO.splitlines() if '"metric":' in line)
        assert "| bare_question_rate |" in vocabulary
        assert "| echo_open_rate |" in vocabulary

    def test_the_grader_is_told_what_it_means_and_handed_the_number(self):
        flat = _flat(RETRO)
        assert "bare_question_rate is the share of her question turns" in flat
        assert "read label_open_rate and bare_question_rate together" in flat
        assert "label_open_rate and bare_question_rate" in _flat(POST)   # the basis text
        assert '"bare_question_rate": ((metrics.get("notes") or {}).get("audio") or {}).get("bare_question_rate")' in POST

    def test_the_readout_email_prints_it(self):
        assert '("bare questions", "bare_question_rate", "%")' in LEARNING

    def test_the_rehearsal_report_reads_it_beside_the_verdict(self):
        import rehearsal
        assert "bare_question_rate" in rehearsal.READ_BESIDE and "label_open_rate" in rehearsal.READ_BESIDE
        assert "bare_question_rate" not in [k for k, _ in rehearsal.MUST_BEAT]

        def rec(arm, **metrics):
            return {"arm": arm, "fixture": "adrian", "run_id": f"{arm}-1",
                    "metrics": {"overlap_events": 1, "self_answered_turns": 0,
                                "guest_words_per_answer_median": 60, "mira_turn_sec_median": 14.0,
                                **metrics}}
        records = [rec("current", overlap_events=2, guest_words_per_answer_median=40,
                       bare_question_rate=0.5, label_open_rate=0.1),
                   rec("proposed", bare_question_rate=0.2, label_open_rate=0.3)]
        summary = rehearsal.summarise(records)
        result = rehearsal.verdict(summary)
        assert result["result"] == "PASS"
        assert summary["proposed"]["medians"]["bare_question_rate"] == 0.2
        text = rehearsal.report_markdown(summary, result)
        assert "Read beside the verdict (never gating it)" in text
        assert "| bare_question_rate | 0.2 | 0.5 |" in text
        assert "| label_open_rate | 0.3 | 0.1 |" in text
        # Without the measure on either arm the table is not printed.
        bare = [rec("current", overlap_events=2), rec("proposed", guest_words_per_answer_median=70)]
        assert "Read beside" not in rehearsal.report_markdown(rehearsal.summarise(bare),
                                                               rehearsal.verdict(rehearsal.summarise(bare)))

    def test_medium_is_a_reasoning_effort_the_rehearsal_can_name(self):
        import fire_interviews as fi
        assert "medium" in fi.REASONING_EFFORTS
        src = (V / "rehearsal.py").read_text(encoding="utf-8")
        assert "(none|low|medium|high)" in src


# 4. The brief carries the beat -----------------------------------------------------

class TestTheBriefCarriesTheBeat:
    BLOCK = PROMPT[PROMPT.index("## CRITICAL INSTRUCTIONS"):]

    def _bullets(self):
        lines = self.BLOCK.splitlines()
        bullets, current = [], None
        for line in lines:
            if line.startswith("- "):
                if current is not None:
                    bullets.append(current)
                current = line[2:].strip()
            elif current is not None and line.startswith("  "):
                current += " " + line.strip()
        if current is not None:
            bullets.append(current)
        return bullets

    def test_the_list_is_seven_lines_with_no_quote_and_the_beat_last(self):
        bullets = self._bullets()
        assert len(bullets) == 7
        assert '"' not in self.BLOCK
        # Nov 4 2026: the beat became a build (tests/test_mira_builds_2026_11_04.py);
        # it is still the list's last line, still by shape.
        assert bullets[-1].startswith("After a real answer, build on one thing they said")

    def test_the_prohibition_left_the_critical_list_and_stayed_in_how_to_react(self):
        assert "never a grade, never an echo" not in self.BLOCK
        react = PROMPT[PROMPT.index("HOW TO REACT"):PROMPT.index("RESEARCH IS QUIET")]
        flat = _flat(react)
        assert "never with a grade of the answer, never with their last words echoed back" in flat
        assert "A short answer needs no acknowledgment" in flat

    def test_the_beat_in_how_to_listen_is_still_there(self):
        # Nov 4 2026: HOW TO LISTEN hands the reaction to HOW TO REACT.
        listen = PROMPT[PROMPT.index("HOW TO LISTEN"):PROMPT.index("IT IS THEIR HOUR")]
        # Nov 5 2026: two or three steps down, then move on (test_interview_plan_2026_11_05).
        assert "build on it. Two or three steps down" in _flat(listen)

    def test_by_shape_only(self):
        # No specimen line, no number, no guest, no date in the brief.
        for word in ("Kamins", "Ep15", "bare_question_rate", "0.25", "178", "Michael"):
            assert word not in PROMPT, word
        assert "I'm the AI" not in self.BLOCK


# 5. The edit keeps the beat it asks for ---------------------------------------------

class TestTheEditKeepsTheBeat:
    def test_a_reaction_in_her_own_words_then_a_question_is_never_read_as_bleed(self):
        from post_interview import strip_echo_lines
        out, dropped = strip_echo_lines(
            "[12:01] Michael: It cost us the whole second quarter, honestly.\n"
            "[12:05] Mira: A quarter nobody had budgeted for, and the team paid it first. "
            "What did you cut to get it back?\n"
            "[12:12] Michael: The first thing to go was the manual review.\n", "Mira")
        assert dropped == 0
        assert "It cost us the whole second quarter" in out
        assert "A quarter nobody had budgeted for" in out
        assert "What did you cut to get it back?" in out

    def test_her_line_is_never_the_one_dropped(self):
        # The stripper takes HER voice out of HIS microphone; her own line
        # stands whatever it says. The line at risk is his, when his
        # microphone carries her words back within the window (the bleed
        # the stripper exists for): a beat in her own words followed by a
        # question is never the line that goes.
        from post_interview import strip_echo_lines
        bleed = ("[12:01] Mira: It cost us the whole second quarter. What did you cut?\n"
                 "[12:04] Michael: It cost us the whole second quarter.\n")
        out, dropped = strip_echo_lines(bleed, "Mira")
        assert dropped == 1
        assert "Mira: It cost us the whole second quarter. What did you cut?" in out
        assert "Michael:" not in out


# 6. The incident is kept for people --------------------------------------------------

class TestTheIncidentIsInTheNotes:
    def test_the_notes_carry_the_story_and_the_prompt_does_not(self):
        assert "## Michael Kamins, Oct 28 2026" in NOTES
        for phrase in ("bare_question_rate", "15 of her 28", "hand re-cut", "arms: both",
                       "reasoning_effort: medium", "adrian", "vincent", "one operator listen"):
            assert phrase in NOTES, phrase
        assert "Kamins" not in PROMPT
