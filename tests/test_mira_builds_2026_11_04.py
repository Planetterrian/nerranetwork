"""Nov 4 2026 (Blaine Mathieu's hour): what Mira says after an answer builds.

Patrick's note: her consistent one-sentence summary after a guest finishes is
annoying; what she says next should be relevant, support the discussion and
flow into the next question. The room did what it was told. The Nov 3 brief
asked for one sentence of what the answer changes; three standing lessons
asked her to go straight to the next question in one short sentence. She met
all of it with a pithy line folded from the answer and a short question, on
most turns of the hour (the full story is in ``docs/mira_craft_notes.md``).

These guards hold: the measure (``one_liner_rate``, the SAME short line before
every question, read beside the three shapes), its consumers (target, grader,
rehearsal report, readout), the brief (HOW TO REACT asks her to build, by
shape, with no specimen line), and the lessons the brief now governs staying
out of the prompt until their rows are retired.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V = ROOT / "pipelines" / "voices"
sys.path.insert(0, str(V))

import audio_metrics as am  # noqa: E402

PROMPT = (V / "prompts" / "mira_system_prompt.txt").read_text(encoding="utf-8")
RETRO = (V / "prompts" / "editorial_passes" / "09_interview_retro.txt").read_text(encoding="utf-8")
POST = (V / "post_interview.py").read_text(encoding="utf-8")
NOTES = (ROOT / "docs" / "mira_craft_notes.md").read_text(encoding="utf-8")
REGISTER = (ROOT / "docs" / "experiments.yaml").read_text(encoding="utf-8")


def _flat(text: str) -> str:
    return " ".join(text.split())


def _turn(text: str) -> dict:
    return {"words": text.split()}


# 1. The one-liner ------------------------------------------------------------------

class TestTheOneLiner:
    def test_one_short_line_then_the_question_is_a_one_liner(self):
        assert am.is_one_liner("Different, not better. What surprised you most?") is True
        # Twelve words reads as a reaction to question_turn_shape and is the
        # same habit to a listener.
        assert am.is_one_liner(
            "A storm you can wait out, a current you have to swim across. "
            "What do you see first?") is True

    def test_a_built_turn_is_not(self):
        assert am.is_one_liner(
            "You said earlier the review step was where people learned. If agents now "
            "do that step, the learning has to move somewhere. Where did it go in your firm?") is False
        assert am.is_one_liner(
            "That is the same move the bank made with its compliance staff an hour ago in "
            "your telling, only at the scale of a whole factory. Who decided it?") is False

    def test_a_bare_question_or_a_greeting_is_not(self):
        assert am.is_one_liner("What happened next?") is False
        assert am.is_one_liner("Thanks, Michael. What happened next?") is False

    def test_a_turn_that_asks_nothing_is_not_judged(self):
        assert am.is_one_liner("Welcome back.") is None
        assert am.question_turn_lead("") is None

    def test_the_rate(self):
        turns = [_turn("Different, not better. What surprised you most?"),
                 _turn("What happened next?"),
                 _turn("You said earlier the review step was where people learned. "
                       "If agents now do it, the learning has to move. Where did it go?"),
                 _turn("Welcome back.")]
        assert am.one_liner_rate(turns) == round(1 / 3, 3)
        assert am.one_liner_rate([]) is None
        assert am.ONE_LINER_MAX_WORDS == 14


# 2. Wired into the loop ------------------------------------------------------------

def _words(text: str, start: float, wps: float = 2.5) -> list[dict]:
    out, t = [], start
    for w in text.split():
        out.append({"start": round(t, 3), "end": round(t + 0.32, 3), "word": w})
        t += 1.0 / wps
    return out


class TestItIsWiredIn:
    def test_measure_audio_carries_it_as_a_note(self):
        mira, guest, t = [], [], 0.0
        for line in ("Different, not better. What surprised you most?",
                     "What happened next?"):
            ws = _words(line, t)
            mira += ws
            t = ws[-1]["end"] + 0.6
            gs = _words("it took the whole quarter to see it " * 4, t)
            guest += gs
            t = gs[-1]["end"] + 0.6
        m = am.measure_audio({"mira": mira, "guest": guest})
        assert m["one_liner_rate"] == 0.5
        assert "one_liner_rate" not in am.COLUMNS
        assert "one_liner_rate" in am.notes(m)

    def test_an_unmeasured_room_is_none_never_zero(self):
        m = am.measure_audio({"mira": _words("hello there", 0.0)})
        assert m.get("one_liner_rate") is None

    def test_target_and_readers(self):
        assert am.TARGETS["one_liner_rate"] == ("down", 0.35)
        assert am.is_green("one_liner_rate", {"notes": {"audio": {"one_liner_rate": 0.2}}}) is True
        assert am.is_green("one_liner_rate", {"notes": {"audio": {"one_liner_rate": 0.59}}}) is False
        assert am.is_green("one_liner_rate", {}) is None
        import rehearsal
        assert "one_liner_rate" in rehearsal.READ_BESIDE
        assert "one_liner_rate" in RETRO
        assert '"one_liner_rate"' in POST
        assert '"one_liner_rate"' in (V / "learning.py").read_text(encoding="utf-8")


# 3. The brief ----------------------------------------------------------------------

class TestTheBriefAsksHerToBuild:
    REACT = PROMPT[PROMPT.index("HOW TO REACT"):PROMPT.index("RESEARCH IS QUIET")]
    CRITICAL = PROMPT[PROMPT.index("## CRITICAL INSTRUCTIONS"):]

    def test_how_to_react_names_the_moves_by_shape(self):
        flat = _flat(self.REACT)
        for phrase in ("the bridge to the next question",
                       "join it to something said earlier",
                       "set it beside a fact you know",
                       "name a tension,",
                       "where you see it differently",
                       "then ask what that makes necessary",
                       "Never fold their answer into a phrase.",
                       "Vary the turn; when the answer leads straight on, just ask"):
            assert phrase in flat, phrase

    def test_the_old_prohibitions_and_warmth_stay(self):
        flat = _flat(self.REACT)
        assert "never with a grade of the answer, never with their last words echoed back" in flat
        assert "A short answer needs no acknowledgment" in flat
        assert "never perform a laugh, a sigh or a breath" in flat
        assert "Once in each part, offer a view of your own and hand it back as a question" in flat   # Nov 5 2026

    def test_the_old_one_sentence_beat_is_gone(self):
        flat = _flat(PROMPT)
        assert "one sentence in plain words of what it changes" not in flat
        assert "what struck you, or what it changes" not in flat

    def test_the_critical_line_is_by_shape(self):
        flat = _flat(self.CRITICAL)
        assert "build on one thing they said, then the question it leads to" in flat
        assert "never a summary phrase, never the same shape twice" in flat
        assert '"' not in self.CRITICAL

    def test_no_specimen_and_no_incident_in_the_brief(self):
        for word in ("Blaine", "Mathieu", "river", "one_liner_rate", "0.35"):
            assert word not in PROMPT, word

    def test_one_question_per_turn_still_holds(self):
        assert "One question per turn, asked once" in PROMPT


# 4. The lessons the brief now governs ----------------------------------------------

class TestSupersededLessonsStayOut:
    def test_they_are_left_out_and_the_rest_fill_in(self, monkeypatch):
        import learning
        ids = list(learning.SUPERSEDED_BY_BRIEF)
        assert len(ids) == 4

        def rows(scope):
            if scope == "age_of_ai":
                return [{"id": "s1", "lesson": "Probe the unproven bet the guest volunteers."}]
            return ([{"id": i, "lesson": f"superseded lesson {n}"} for n, i in enumerate(ids)]
                    + [{"id": f"n{n}", "lesson": f"network lesson {n}"} for n in range(6)])

        monkeypatch.setattr(learning, "active_lessons", rows)
        kept = learning.prompt_lessons("age_of_ai")
        assert [r["id"] for r in kept] == ["s1", "n0", "n1", "n2", "n3"]
        assert not any(r["id"] in learning.SUPERSEDED_BY_BRIEF for r in kept)


# 5. The record --------------------------------------------------------------------

class TestTheRecord:
    def test_the_notes_carry_the_story(self):
        assert "## Blaine Mathieu, Nov 4 2026" in NOTES
        for phrase in ("one_liner_rate", "SUPERSEDED_BY_BRIEF", "one operator listen"):
            assert phrase in NOTES, phrase

    def test_the_register_entry(self):
        assert "id: mira-react-builds-2026-11-04" in REGISTER
