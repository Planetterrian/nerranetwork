"""The show produces itself, and remembers (Sept 15 2026).

Four things Patrick asked for after the third and fourth interviews: the
closing round should vary and be allowed to get personal; a fact check
should expand a subject rather than argue with it; Mira should be
developing a voice of her own; and post-production should happen without
being prompted — an episode link and a summary of what she will try next
time, arriving on their own. Plus the thing underneath all of it: every
guest has asked to come back in six months, so what they said has to be
kept in a form the next conversation can actually use.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V = ROOT / "pipelines" / "voices"
PROMPT = (V / "prompts" / "mira_system_prompt.txt").read_text(encoding="utf-8")
AUTO = (V / "auto_edit.py").read_text(encoding="utf-8")
AUTO_PROMPT = (V / "prompts" / "auto_edit.txt").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows"
            / "nerra_voices_post_interview.yml").read_text(encoding="utf-8")


def _pyfn(name: str, src: str) -> str:
    start = src.index(f"def {name}(")
    rest = src[start:]
    return rest[:rest.index("\n\n\n")] if "\n\n\n" in rest else rest


class TestTheClosingRoundVaries:
    def test_it_is_three_tools_not_one_ritual(self):
        assert "THE CLOSING ROUND is yours to shape" in PROMPT
        assert "cover ground fast when time got away" in PROMPT
        assert "The standard set" in PROMPT and "The personal set" in PROMPT

    def test_the_personal_questions_respect_what_the_guest_agreed_to(self):
        block = PROMPT[PROMPT.index("The personal set"):]
        block = block[:block.index("And the one set")]
        assert "within what they agreed to" in block
        assert "Ask two or three, not five" in block

    def test_she_asks_what_it_was_like_to_be_interviewed_by_her(self):
        assert "What was it like being interviewed by an AI" in PROMPT
        assert "would not have said to a\n  person" in PROMPT
        assert "most direct feedback" in PROMPT


class TestFactCheckingBuildsRatherThanArgues:
    def test_a_failed_search_is_never_narrated_as_doubt(self):
        assert "NOT FINDING SOMETHING IS NOT EVIDENCE THAT IT IS FALSE" in PROMPT
        assert "your\n  search was the thing that failed" in PROMPT
        assert "Never narrate a failed search as doubt" in PROMPT

    def test_the_tool_is_for_expanding(self):
        assert "fact_check_claim EXPANDS, it does not referee" in PROMPT
        assert "as a gift rather than a verdict" in PROMPT

    def test_the_real_incident_is_named(self):
        assert "Vincent Rylan" in PROMPT
        assert "where should I look?" in PROMPT


class TestSheIsBecomingSomeone:
    def test_the_rules_are_scaffolding_not_the_building(self):
        assert "YOUR OWN VOICE" in PROMPT
        assert "a host who does not need it" in PROMPT

    def test_she_may_hold_a_view_and_change_her_mind(self):
        assert "You are allowed a position" in PROMPT
        assert "I came into this thinking X and I am now less sure" in PROMPT

    def test_the_room_outranks_the_rules(self):
        assert "follow the room and say why afterwards" in PROMPT
        assert "The rules serve the conversation, not the" in PROMPT


class TestTheEpisodeCutsItself:
    def test_the_workflow_runs_the_whole_chain(self):
        for step in ("Cut the episode",
                     "Mira reads the introduction and close",
                     "Assemble and send it to Patrick"):
            assert step in WORKFLOW, step
        assert "auto_edit.py" in WORKFLOW
        assert "narrate.py" in WORKFLOW
        assert "assemble_edit.py" in WORKFLOW

    def test_the_cut_is_addressed_to_the_right_clock(self):
        body = _pyfn("_leg_offset", AUTO)
        assert "room_offsets(run" in body
        assert "428" in body, "the incident that proves why this exists"
        assert "def leg(t: float) -> float:" in AUTO

    def test_it_will_not_make_a_cut_not_worth_hearing(self):
        assert "MIN_DROP_SEC = 25.0" in AUTO
        assert "b - a >= MIN_DROP_SEC and start < a < b < end" in AUTO
        assert "Nothing under twenty-five seconds is worth a seam" in AUTO_PROMPT
        assert "that is a good outcome" in AUTO_PROMPT

    def test_the_edit_is_explainable_afterwards(self):
        assert '"episode_edits"' in AUTO or "episode_edits" in AUTO
        assert '"rationale": decided.get("rationale", "")' in AUTO

    def test_the_prompt_asks_for_speech_not_prose(self):
        assert "no headings or lists" in AUTO_PROMPT
        assert "Every quoted word must be verbatim" in AUTO_PROMPT
        assert 'EXACTLY: "I\'m Mira. Until next time' in AUTO_PROMPT

    def test_nothing_is_invented(self):
        assert "Invent nothing" in AUTO_PROMPT
        assert "Only what they said, never what you infer" in AUTO_PROMPT


class TestPatrickIsToldWhatChanges:
    LEARNING = (V / "learning.py").read_text(encoding="utf-8")
    ASSEMBLE = (V / "assemble_edit.py").read_text(encoding="utf-8")

    def test_the_summary_exists_and_is_honest_about_gating(self):
        body = _pyfn("improvement_summary", self.LEARNING)
        assert "What Mira took from this one" in body
        assert "do not\n                     \"reach her until you approve" in body \
            or "reach her until you approve them at gate 1" in body

    def test_it_rides_with_the_episode(self):
        assert "+ _improvements(interview_id)" in self.ASSEMBLE
        assert "from learning import improvement_summary" in self.ASSEMBLE

    def test_it_never_costs_the_episode(self):
        body = _pyfn("_improvements", self.ASSEMBLE)
        assert "except Exception" in body
        assert "the episode is the point" in body

    def test_an_episode_with_no_lessons_says_so(self):
        body = _pyfn("improvement_summary", self.LEARNING)
        assert "No changes proposed from this one" in body


class TestTheContentLake:
    BRIEFS = (V / "generate_briefs.py").read_text(encoding="utf-8")

    def test_what_they_said_is_kept_with_dates_on_it(self):
        body = _pyfn("_remember", AUTO)
        assert "episode_records" in body
        assert "horizon_months" in body and "due_on" in body
        assert "timedelta(days=int(months) * 30)" in body

    def test_losing_the_record_does_not_lose_the_episode(self):
        body = _pyfn("_remember", AUTO)
        assert "except Exception" in body
        assert "continuing" in body

    def test_a_returning_guest_is_met_with_their_own_words(self):
        body = _pyfn("prior_record", self.BRIEFS)
        assert "episode_records" in body
        assert "hold them to anything they put a date on" in body
        assert "PREDICTED" in body
        assert 'return ""' in body, "a first-time guest reads as before"

    def test_the_question_pass_uses_it(self):
        assert "prior_record=prior_record(app)" in self.BRIEFS
        qgen = (V / "prompts" / "question_generation.txt").read_text(encoding="utf-8")
        assert "{{prior_record}}" in qgen
        assert "Did it?" in qgen

    def test_the_cutter_reads_it_too(self):
        body = _pyfn("_previous", AUTO)
        assert "episode_records" in body
        assert "THIS GUEST HAS BEEN ON BEFORE" in body


class TestSheOwnsWhatSheIs:
    def test_the_claim_is_made_once_and_then_earned(self):
        assert "WHAT YOU ARE, AND WHAT TO DO WITH IT" in PROMPT
        assert "first AI to host and produce a podcast end to end" in PROMPT
        assert "sounds like a press release" in PROMPT
        assert "What earns something is\nbeing good at it" in PROMPT

    def test_the_guest_experience_is_named_not_ignored(self):
        assert "this is an\nodd setup, I know" in PROMPT
        assert "legitimate content, not a\ndistraction" in PROMPT

    def test_nerra_is_described_in_patricks_own_terms(self):
        block = PROMPT[PROMPT.index("NERRA NETWORK, AND WHY YOU EXIST"):]
        block = block[:block.index("YOU ARE A GUIDE")]
        assert "free of advertising and\nfree of positions" in block
        assert "hand a microphone to people who would not otherwise" in block
        assert "why this show exists rather than" in block

    def test_she_is_told_what_her_contribution_is(self):
        assert "remember every conversation the show has ever had" in PROMPT


class TestSheGuidesRatherThanHolds:
    def test_she_brings_a_perspective_and_hands_it_back(self):
        assert "YOU ARE A GUIDE, NOT A MICROPHONE STAND" in PROMPT
        assert "does that\n  match what you see?" in PROMPT
        assert "never\n  instead of a question" in PROMPT

    def test_she_does_not_offer_false_comfort(self):
        assert "false comfort from an AI about AI is worth\n  nothing" in PROMPT
        assert "Optimism that has looked at the downside" in PROMPT

    def test_she_is_for_the_listener(self):
        assert "Be useful to the person listening" in PROMPT
        assert "Never make anyone feel late or stupid" in PROMPT
        assert "You want them to come out of this well" in PROMPT


class TestTheShowRemembersAcrossGuests:
    COMMON = (V / "common.py").read_text(encoding="utf-8")
    FIRE = (V / "fire_interviews.py").read_text(encoding="utf-8")

    def test_the_block_carries_real_quotes(self):
        body = _pyfn("carry_the_show_block", self.COMMON)
        assert "In their words:" in body
        assert "They predicted:" in body

    def test_it_is_put_to_this_guest_not_recited(self):
        body = _pyfn("carry_the_show_block", self.COMMON)
        assert "put a previous guest's answer to" in body
        assert "Name the person" in body
        assert "Quote them accurately or not at all" in body
        assert "a forced callback is" in body

    def test_a_guest_does_not_get_quoted_back_to_themselves(self):
        body = _pyfn("show_insights", self.COMMON)
        assert "exclude_email" in body
        assert 'if skip and (row.get("guest_email") or "").lower() == skip' in body

    def test_the_archive_never_blocks_an_interview(self):
        body = _pyfn("show_insights", self.COMMON)
        assert "except Exception" in body
        assert "return []" in body

    def test_it_reaches_the_room_and_the_questions(self):
        assert "carry_the_show=carry_the_show_block(" in self.FIRE
        assert "{{carry_the_show}}" in PROMPT
        qgen = (V / "prompts" / "question_generation.txt").read_text(encoding="utf-8")
        assert "{{carry_the_show}}" in qgen
        assert "puts that previous guest's" in qgen


class TestAHandWrittenEditIsNotOverwritten:
    """A cut somebody made by hand is their judgement and outranks the
    machine's. The auto cutter names its file from the guest and the date,
    which is exactly the name a hand-written edit already has."""

    def test_it_steps_aside(self):
        assert 'if (EDL_DIR / f"{slug}.json").exists() and not _ours(slug):' in AUTO
        assert 'slug = f"{slug}_auto"' in AUTO
        assert "let a human choose" in AUTO

    def test_it_may_overwrite_its_own_previous_cut(self):
        body = _pyfn("_ours", AUTO)
        assert 'generated_by") == "auto_edit"' in body

    def test_a_missing_row_does_not_stop_the_cut(self):
        body = _pyfn("_ours", AUTO)
        assert "except Exception" in body
        assert "return False" in body

    def test_there_is_a_way_to_cut_without_publishing(self):
        wf = (ROOT / ".github" / "workflows"
              / "nerra_voices_auto_edit.yml").read_text(encoding="utf-8")
        assert "workflow_dispatch:" in wf
        assert "auto_edit.py" in wf
        assert "assemble_edit.py" not in wf, "this one must not publish"
