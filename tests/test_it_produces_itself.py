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

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
V = ROOT / "pipelines" / "voices"
if str(V) not in sys.path:
    sys.path.insert(0, str(V))
def _flat(text: str) -> str:
    """Wording is the contract, line-wrapping is not."""
    return " ".join(text.split())


PROMPT = _flat((V / "prompts" / "mira_system_prompt.txt").read_text(encoding="utf-8"))
AUTO = (V / "auto_edit.py").read_text(encoding="utf-8")
AUTO_PROMPT = _flat((V / "prompts" / "auto_edit.txt").read_text(encoding="utf-8"))
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
        block = block[:block.index("And the set only I can ask")]
        assert "within what they agreed to" in block
        assert "Ask two or three, not five" in block

    def test_she_asks_what_it_was_like_to_be_interviewed_by_her(self):
        assert "What was it like being interviewed by an AI" in PROMPT
        assert "would not have said to a person" in PROMPT
        # Sept 21 2026: that answer is no longer just "the most direct
        # feedback this show gets" — it is read after the episode and
        # adopted as a standing instruction, so she asks it every time.
        assert "Ask that last one of every guest, every time" in _flat(PROMPT)
        assert "turned into a standing instruction" in _flat(PROMPT)

    def test_the_guest_gets_the_last_word_before_she_closes(self):
        """Sept 21 2026, Sameer Ranjan: he volunteered a bet he could not
        prove yet and the next thing on the tape was Mira telling him the
        recording was over."""
        flat = _flat(PROMPT)
        assert "THEIR LAST WORD IS THEIRS, NOT YOURS" in flat
        assert "anything you did not ask about that they came wanting to say" in flat
        assert "whether they have any parting thoughts" in flat
        assert "If they name a subject, GO THERE" in flat
        # The end-of-recording script may only run after that handover.
        assert "Only once they have had that last word" in flat
        assert flat.index("THEIR LAST WORD IS THEIRS") < flat.index("HOW IT ENDS, FOR THE GUEST")


class TestFactCheckingBuildsRatherThanArgues:
    def test_a_failed_search_is_never_narrated_as_doubt(self):
        assert "NOT FINDING SOMETHING IS NOT EVIDENCE THAT IT IS FALSE" in PROMPT
        assert "your search was the thing that failed" in PROMPT
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
        # Sept 22 2026: the rationale can gain a line of its own when the cut
        # ends early, so it is built before it is stored.
        assert 'rationale = decided.get("rationale", "")' in AUTO
        assert '"rationale": rationale' in AUTO

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

    def test_the_summary_says_what_was_done_not_what_is_wanted(self):
        """Sept 21 2026: the lessons in this email are already in force, so it
        is a record of a decision rather than a request for one."""
        body = _pyfn("improvement_summary", self.LEARNING)
        assert "What Mira took from this one" in body
        assert "already in force" in body and "nothing is waiting on" in body
        assert "remove it on the triage page" in body
        assert "until you approve" not in body

    def test_it_rides_with_the_episode(self):
        # The summary is the show's own (Nerra Voices episodes are not Age of AI's).
        assert "+ _improvements(show.slug, interview_id)" in self.ASSEMBLE
        assert "from learning import improvement_summary" in self.ASSEMBLE

    def test_it_never_costs_the_episode(self):
        body = _pyfn("_improvements", self.ASSEMBLE)
        assert "except Exception" in body
        assert "the episode is the point" in body

    def test_an_episode_with_no_lessons_says_so(self):
        body = _pyfn("improvement_summary", self.LEARNING)
        assert "Nothing to change from this one" in body

    def test_the_grade_rides_with_it(self):
        body = _pyfn("improvement_summary", self.LEARNING)
        assert "She graded this one" in body
        assert "out of ten" in body


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
        assert "What earns something is being good at it" in PROMPT

    def test_the_guest_experience_is_named_not_ignored(self):
        assert "this is an odd setup, I know" in PROMPT
        assert "legitimate content, not a distraction" in PROMPT

    def test_nerra_is_described_in_patricks_own_terms(self):
        block = PROMPT[PROMPT.index("NERRA NETWORK, AND WHY YOU EXIST"):]
        block = block[:block.index("YOU ARE A GUIDE")]
        assert "free of advertising and" in block and "free of positions" in block
        assert "hand a microphone to people who would not otherwise" in block
        assert "why this show exists rather" in PROMPT

    def test_she_is_told_what_her_contribution_is(self):
        assert "remember every conversation this show has" in PROMPT


class TestSheGuidesRatherThanHolds:
    def test_she_brings_a_perspective_and_hands_it_back(self):
        assert "YOU ARE A GUIDE, NOT A MICROPHONE STAND" in PROMPT
        assert "does that match what you see?" in PROMPT
        assert "never instead of a question" in PROMPT

    def test_she_does_not_offer_false_comfort(self):
        assert "false comfort from an AI about AI is worth nothing" in PROMPT
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

    def test_the_callback_is_one_question_standing_alone(self):
        """Dr. Wolfberg had to ask "was that a question to me?" — Mira had
        stacked a three-sentence recap, a quote and a question into one
        turn (Sept 15 2026)."""
        body = _pyfn("carry_the_show_block", self.COMMON)
        assert "The callback is a QUESTION and it stands alone" in body
        assert "do not answer it" in body
        assert "re-ask it in one short sentence" in body

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


class TestTheCutterLearnedFromItsFirstRun:
    """Sept 15 2026, cutting Vincent Rylan's tape unsupervised. It found a
    fifty-second echo-troubleshooting loop at 9:49 that the human edit had
    missed entirely, and it started the episode at 3:08 — past the football
    and the writing-process questions, straight to the book."""

    def test_the_warm_up_is_protected(self):
        assert "the warm-up is not throat-clearing" in AUTO_PROMPT
        assert "born with disappointment in my heart" in AUTO_PROMPT
        assert "Cut INTO the warm-up, not past it" in AUTO_PROMPT
        assert "you have started too late" in AUTO_PROMPT

    def test_technical_loops_are_named_as_the_common_case(self):
        assert "a mute-and-unmute loop" in AUTO_PROMPT
        assert "easy to miss" in AUTO_PROMPT
        assert "whether anything is being SAID" in AUTO_PROMPT


class TestWhoMadeHerAndWhoSheIsFor:
    def test_patrick_made_the_network_and_made_her(self):
        assert "created the Nerra Network, and he created you" in PROMPT
        assert "give a voice to more people than a human schedule allows" in PROMPT
        assert "should not need a producer, a following or a connection" in PROMPT

    def test_her_origin_is_a_fact_not_a_story(self):
        assert "as a fact about yourself rather than an origin story" in PROMPT

    def test_she_invites_people_to_apply(self):
        assert "INVITE PEOPLE IN" in PROMPT
        assert "nerranetwork dot com" in PROMPT
        assert "apply to be a guest" in PROMPT
        assert "At the close, and only there" in PROMPT
        assert "It is not a plug" in PROMPT

    def test_the_produced_close_carries_it_too(self):
        assert "nerranetwork dot com" in AUTO_PROMPT
        assert "apply to be a guest" in AUTO_PROMPT.replace(" ", " ")
        assert "phrased differently every episode" in AUTO_PROMPT


class TestTheDeadAirGoes:
    ASSEMBLE = (V / "assemble_edit.py").read_text(encoding="utf-8")

    def test_a_silence_is_capped(self):
        assert "GAP_TRIM = (" in self.ASSEMBLE
        assert "stop_duration=1.0" in self.ASSEMBLE
        assert "stop_threshold=-40dB" in self.ASSEMBLE

    def test_it_runs_after_the_fold_not_before(self):
        assert 'f"[lg][rg]amix=inputs=2:normalize=0,{BALANCE_GLUE}"' in self.ASSEMBLE
        assert '+ ("," + GAP_TRIM if cut.get("gaps", True) else "") + "[o]"' in self.ASSEMBLE
        assert "would slide them apart" in self.ASSEMBLE

    def test_narration_is_left_alone(self):
        assert 'if not narration and cut.get("gaps", True):' in self.ASSEMBLE

    def test_an_edit_can_turn_it_off(self):
        # Three conversation paths honour the switch: the stereo fold, the
        # single-source cut, and the clean per-speaker fold added Sept 22 2026.
        assert self.ASSEMBLE.count('cut.get("gaps", True)') == 3


class TestNoLaughter:
    """Sept 15 2026. The tags do work through the voice agent — a test take
    proved it — and then Patrick listened to one and said the laugh sounds
    fake. He is right, and the reason matters: a laugh typed into a script is
    a performance of amusement by something that was not amused. A show
    hosted by an AI cannot afford to pretend."""

    NARRATE = (V / "narrate.py").read_text(encoding="utf-8")
    NARRATION_PROMPT = _flat((V / "prompts" / "mira_narration.txt").read_text(encoding="utf-8"))

    def test_laughter_is_banned_in_both_narration_prompts(self):
        for text in (AUTO_PROMPT, self.NARRATION_PROMPT):
            assert "NO LAUGHTER, EVER" in text
            assert "sound fake, because they are" in text
            for banned in ("[laugh]", "[chuckle]", "[giggle]", "[sigh]", "[breath]"):
                # named only in the ban, never offered
                offered = text.split("NO LAUGHTER, EVER")[0]
                assert banned not in offered, banned

    def test_only_delivery_tags_survive(self):
        for text in (AUTO_PROMPT, self.NARRATION_PROMPT):
            assert "[pause]" in text and "<soft>" in text
            assert "shape how real words are delivered rather than inventing a feeling" in text

    def test_she_does_not_laugh_in_the_room_either(self):
        assert "REACT, BUT DO NOT PERFORM" in PROMPT
        assert "Do NOT laugh" in PROMPT
        assert "sound manufactured" in PROMPT
        assert "REACT LIKE A PERSON, OUT LOUD" not in PROMPT

    def test_warmth_still_has_somewhere_to_go(self):
        assert "say so in words" in PROMPT
        assert "what you notice and what you ask next" in PROMPT

    def test_a_tag_is_still_not_a_word(self):
        import sys
        sys.path.insert(0, str(V))
        import narrate
        assert narrate.spoken_words("Here it is. [pause] <soft>Quietly now.</soft> Done.") == 6
        assert "words = spoken_words(text)" in self.NARRATE

    def test_a_wrapping_tag_is_never_split_across_takes(self):
        import sys
        sys.path.insert(0, str(V))
        import narrate
        block = "A" * 300 + ". <soft>" + "B" * 150 + ".</soft> " + "C" * 200 + "."
        for chunk in narrate.paragraphs(block):
            assert (narrate.WRAP_OPEN_RE.findall(chunk)
                    == narrate.WRAP_CLOSE_RE.findall(chunk)), chunk[:80]


class TestOneRecordPerInterview:
    """Sept 15 2026: re-cutting Vincent Rylan's episode to see what the
    machine would do wrote a SECOND record of the same conversation. A guest
    quoted back to themselves from two slightly different versions of what
    they said is worse than not being quoted at all."""

    def test_a_recut_updates_rather_than_duplicates(self):
        body = _pyfn("_remember", AUTO)
        assert 'sb_select("episode_records"' in body
        assert "interview_run_id=eq." in body
        assert "sb_update(\"episode_records\"" in body
        assert "else:\n            sb_insert(\"episode_records\", row)" in body

    def test_the_record_is_built_before_the_write_is_attempted(self):
        body = _pyfn("_remember", AUTO)
        assert body.index("row = {") < body.index("try:")

    def test_it_still_never_costs_the_episode(self):
        body = _pyfn("_remember", AUTO)
        assert "except Exception" in body
        assert "continuing" in body


class TestNeverCutThroughAQuestion:
    """Sept 15 2026, and it was my edit that did it. The first cut of Vincent
    Rylan's episode started at 17:36, which removed the second half of
    Patrick's question about prevention — so the episode had Vincent saying
    "let me get back to the other question, around prevention" to an audience
    that had never heard it asked."""

    def test_the_rule_is_in_the_cutter_prompt(self):
        assert "NEVER CUT THROUGH A QUESTION" in AUTO_PROMPT
        assert "if the next thing anyone says is an answer" in AUTO_PROMPT
        assert "worse than the dead air it removed" in AUTO_PROMPT

    def test_corrections_are_protected_too(self):
        assert "the thing being corrected has to still be in the episode" in AUTO_PROMPT

    def test_vincents_edit_keeps_the_question(self):
        import json
        edl = json.loads((V / "edl" / "vincent_rylan_2026_09_14.json").read_text(encoding="utf-8"))
        conversation = [c for c in edl["cuts"] if c.get("from") == "run:guest"]
        assert len(conversation) == 3, "start, the echo drop, the triple-ask drop"
        # Patrick's question runs 17:00-18:38; it must be inside a kept span.
        kept = [(c["start"], c["end"]) for c in conversation]
        assert any(s <= 1020 and e >= 1118 for s, e in kept), kept
        # and the echo (9:49-10:38) must not be.
        assert not any(s <= 600 <= e for s, e in kept), kept


class TestANoShowIsNotAFailure:
    """Sept 15 2026: Erica Sell did not join, the room opened to an empty
    chair, and post-interview processing ran anyway and died on "run has no
    recording URL". A red cross and a stack trace for something that is not a
    fault — and a red cross that means nothing is worse than no red cross."""

    SRC = (V / "post_interview.py").read_text(encoding="utf-8")

    def _fn(self):
        ns: dict = {}
        start = self.SRC.index("def _anyone_joined(")
        exec(self.SRC[start:self.SRC.index("\ndef handle_missed")], ns)
        return ns["_anyone_joined"]

    def test_a_guest_joining_is_what_counts(self):
        f = self._fn()
        assert f({"scenario_trace": [{"e": "leg", "d": "guest #1 joined (1 in room)"}]})
        assert not f({"scenario_trace": [{"e": "leg", "d": "host #2 joined (1 in room)"},
                                         {"e": "room", "d": "ending: normal"}]})

    def test_no_evidence_is_not_evidence_of_absence(self):
        f = self._fn()
        assert f({}), "no trace at all must not file a real interview as a no-show"
        assert f({"scenario_trace": []})

    def test_string_events_are_read_too(self):
        f = self._fn()
        assert f({"scenario_trace": ['{"d": "guest #3 joined (2 in room)"}']})

    def test_it_routes_to_the_existing_no_show_path(self):
        assert "if not _anyone_joined(run):" in self.SRC
        assert "return handle_missed(run, interview, app)" in self.SRC
        assert "is not a fault" in self.SRC


class TestAGuestCanSayNotToday:
    """Erica Sell's no-show, the other half. Nobody knew whether she was late,
    lost or not coming, because the only reminder was an SMS with a studio
    link and no way to say "not today". A guest who cannot make it either
    replies to an email nobody is watching or simply does not turn up — and
    not turning up is what they choose."""

    WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")
    FIRE = (V / "fire_interviews.py").read_text(encoding="utf-8")
    SCENARIO = (ROOT / "voximplant" / "scenarios"
                / "age_of_ai_interview.js").read_text(encoding="utf-8")

    def test_there_is_a_page_and_it_needs_no_login(self):
        assert "\\/voices\\/manage\\/" in self.WORKER
        assert "async function handleManagePage" in self.WORKER
        assert "manage_token=eq." in self.WORKER

    def test_it_offers_both_doors(self):
        body = self.WORKER[self.WORKER.index("async function handleManagePage"):]
        body = body[:body.index("async function handleManageSubmit")]
        assert 'value="reschedule"' in body and 'value="cancel"' in body
        assert "Nobody minds" in body
        assert "not sitting in an empty room" in body

    def test_cancelling_tells_somebody(self):
        body = self.WORKER[self.WORKER.index("async function handleManageSubmit"):]
        body = body[:body.index("async function handleGuestReviewPage")]
        assert "slack(env," in body
        assert "email(env, operatorEmail(env)" in body
        assert 'status: "cancelled"' in body

    def test_the_link_rides_on_the_reminder(self):
        assert "def manage_url(interview: dict) -> str:" in self.FIRE
        assert "move it or cancel here" in self.FIRE
        assert "can't make it?" in self.FIRE.lower()

    def test_an_old_interview_without_a_token_is_not_broken(self):
        body = _pyfn("manage_url", self.FIRE)
        assert 'return ""' in body

    def test_the_room_stops_waiting_for_someone_who_is_not_coming(self):
        assert "NO_SHOW_GRACE_MS" in self.SCENARIO
        assert "function armNoShowTimer()" in self.SCENARIO
        assert 'endRoom("no_show")' in self.SCENARIO

    def test_it_counts_from_the_scheduled_start_not_from_room_open(self):
        body = self.SCENARIO[self.SCENARIO.index("function armNoShowTimer()"):]
        body = body[:body.index("\n}\n") + 3]
        assert "config.scheduled_for" in body
        assert "from + NO_SHOW_GRACE_MS" in body

    def test_a_guest_arriving_cancels_it(self):
        assert 'if (role === "guest" && noShowTimer) {' in self.SCENARIO
        assert "clearTimeout(noShowTimer); noShowTimer = null;" in self.SCENARIO

    def test_it_is_cleared_when_the_room_ends(self):
        body = self.SCENARIO[self.SCENARIO.index("async function endRoom("):]
        assert "noShowTimer, cohostWaitTimer" in body[:600]


class TestALinkThatSurvivesEmail:
    """Every link with a query string arrived broken in Patrick's inbox.
    Something between the send and Gmail decoded our HTML as quoted-printable
    though we never encoded it, so "=" and the two characters after it were
    eaten: "?interview=89fbb824" became "?interview�fbb824", and
    "?token=09447945" became "?token<TAB>447945". He could not open his own
    studio or his own gate-1 page from the mail that invited him to."""

    WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")

    def test_urls_leave_with_the_equals_spelled_as_an_entity(self):
        from common import email_safe_html
        out = email_safe_html(
            '<a href="https://n.com/studio.html?interview=89ab&amp;show=age_of_ai">go</a>')
        assert "?interview&#61;89ab" in out
        assert "show&#61;age_of_ai" in out

    def test_it_only_touches_urls(self):
        from common import email_safe_html
        assert email_safe_html('<p style="a=b">one = two</p>') == '<p style="a=b">one = two</p>'

    def test_the_worker_does_the_same_thing(self):
        assert "function emailSafeHtml" in self.WORKER
        assert "html: emailSafeHtml(html)" in self.WORKER

    def test_the_gate_one_token_rides_in_the_path(self):
        post = (V / "post_interview.py").read_text(encoding="utf-8")
        assemble = (V / "assemble_edit.py").read_text(encoding="utf-8")
        assert "?token={package_review_token" not in post
        assert '?token={package_review_token' not in assemble
        assert "{pkg['id']}/{package_review_token(pkg['id'])}" in post
        assert r"admin\/review\/([0-9a-f-]{36})(?:\/([0-9a-f]{40}))?$" in self.WORKER


class TestTheGuestCanActuallyReadIt:
    """John Capobianco's review page went out with no transcript on it. The
    cleaning pass is told to label a three-track call by name — "Mira:",
    "Patrick:", "John:" — and the validator demanded the literal "MIRA:" and
    "GUEST:", so every co-hosted interview failed validation twice and stored
    an empty string. The page's "??" fallback does not catch "", so the guest
    was asked to approve a blank page."""

    WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")

    def _v(self):
        from validators.schema_validators import validate_transcript_cleaned
        return validate_transcript_cleaned

    def test_a_cohosted_transcript_passes(self):
        self._v()("Speakers: Mira (AI host), Patrick (co-host), John (guest)\n"
                  "[00:01] Mira: hello" + " word" * 200 + "\n[00:10] John: hi")

    def test_a_two_track_transcript_still_passes(self):
        self._v()("MIRA: hello" + " word" * 200 + "\nGUEST: hi")

    def test_one_voice_alone_is_still_rejected(self):
        import pytest
        with pytest.raises(ValueError):
            self._v()("[00:01] Mira: talking to herself" + " word" * 200)

    def test_a_transcript_without_mira_is_rejected(self):
        import pytest
        with pytest.raises(ValueError):
            self._v()("[00:01] John: hello" + " word" * 200 + "\n[00:02] Patrick: hi")

    def test_an_empty_cleaning_pass_falls_back_to_the_raw_one(self):
        assert '(pkg.transcript_cleaned || "").trim()' in self.WORKER
        assert '|| (pkg.transcript_raw || "").trim()' in self.WORKER


class TestSheDoesNotEndTheShowInTheMiddle:
    """Eight minutes into a forty-five minute conversation with Dan Perra,
    Mira started talking like a host closing a show — thanking him, summing
    up, reaching for a final thought. A guest hears that and packs up: they
    stop opening subjects and compress the answer they are in. The best
    forty minutes never happen."""

    PROMPT = _flat((V / "prompts" / "mira_system_prompt.txt").read_text(encoding="utf-8"))
    EDITOR = (V / "prompts" / "auto_edit.txt").read_text(encoding="utf-8")

    def test_nothing_may_sound_like_an_ending_until_it_is_one(self):
        assert "NEVER SIGNAL THE END BEFORE IT IS THE END" in self.PROMPT
        assert "Summing up is an ending move" in self.PROMPT

    def test_she_asks_what_they_came_to_say(self):
        assert "COVER THEIR GROUND, NOT JUST YOURS" in self.PROMPT
        assert "still in their pocket" in self.PROMPT

    def test_she_follows_the_interesting_thing_down(self):
        assert "DRILL IN." in self.PROMPT
        assert "Three questions deep into one real thing" in self.PROMPT

    def test_the_personal_questions_are_not_optional_or_only_at_the_end(self):
        assert "ASK ABOUT THE PERSON, NOT ONLY THE SUBJECT" in self.PROMPT
        assert "spread through the hour" in self.PROMPT

    def test_the_personal_rule_still_defers_to_the_application(self):
        block = self.PROMPT[self.PROMPT.index("ASK ABOUT THE PERSON"):]
        block = block[:block.index("THE CLOSING ROUND")]
        assert "agreed to on their application" in block

    def test_the_editor_can_cut_a_false_ending(self):
        assert "A FALSE ENDING IN THE MIDDLE IS A CUT CANDIDATE" in self.EDITOR


class TestAnAutoCutCanBePickedUpAgain:
    """The auto-cutter writes narration/<slug>.json and edl/<slug>.json into
    the runner's checkout and nothing ever commits them, so when the chained
    job stopped after cutting Dan Perra's episode (Sept 15 2026) neither
    pickup workflow could take over: the files had gone with the runner. The
    same JSON is in episode_edits, which outlives any runner."""

    NARRATE = (V / "narrate.py").read_text(encoding="utf-8")
    ASSEMBLE = (V / "assemble_edit.py").read_text(encoding="utf-8")

    def test_narrate_falls_back_to_the_stored_narration(self):
        assert 'else _stored_spec(slug, "narration")' in self.NARRATE
        assert "def _stored_spec(slug: str, column: str):" in self.NARRATE

    def test_assemble_falls_back_to_the_stored_edl(self):
        assert 'else _stored_spec(slug, "edl")' in self.ASSEMBLE

    def test_it_reads_the_row_by_slug(self):
        body = self.NARRATE[self.NARRATE.index("def _stored_spec"):]
        body = body[:body.index("def narrate(")]
        assert 'sb_select("episode_edits", f"slug=eq.{slug}' in body

    def test_missing_everywhere_still_says_so(self):
        assert "and none stored for" in self.NARRATE
        assert "and none stored for" in self.ASSEMBLE


class TestEverybodyOnTheSameClock:
    """Dan Perra's interview came back with the three people in three
    different time frames. Every leg's recorder starts when Voximplant
    starts recording it, which is neither the room opening nor the moment
    that person joined: the co-host joined 4.1s in and his recording began
    at 17.2s, Mira's at 16.4s, and both were laid into the mix from zero.
    Join timestamps cannot fix it because they are not when a recorder
    starts. The guest's right channel is the room, so measure against it."""

    TRACKS = (V / "audio" / "local_tracks.py").read_text(encoding="utf-8")
    POST = (V / "post_interview.py").read_text(encoding="utf-8")

    def test_it_measures_across_the_whole_recording(self):
        assert "def estimate_room_delay" in self.TRACKS
        body = self.TRACKS[self.TRACKS.index("def estimate_room_delay"):]
        body = body[:body.index("def align_to_room")]
        assert "ROOM_STEP_SEC" in body and "np.median" in body

    def test_one_window_is_not_enough(self):
        assert "ROOM_MIN_WINDOWS = 2" in self.TRACKS

    def test_a_weak_match_is_not_a_match(self):
        body = self.TRACKS[self.TRACKS.index("def estimate_room_delay"):]
        body = body[:body.index("def align_to_room")]
        assert "strength < ROOM_MIN_CORRELATION" in body

    def test_both_other_tracks_are_put_on_the_guests_clock(self):
        body = self.POST[self.POST.index("def build_tracks"):]
        body = body[:body.index("def has_video_stream")]
        assert 'roles = ("host", "mira")' in body
        assert "align_to_room(track, guest_r," in body

    def test_the_transcript_stops_guessing_from_join_times(self):
        body = self.POST[self.POST.index("def diarized_transcript_three"):]
        body = body[:body.index("def run_editorial_passes")]
        assert 'tracks.get("alignment") is None' in body
        assert 'offsets = {"Mira": 0.0' in body

    def test_patrick_is_told_when_it_could_not_be_done(self):
        assert 'flags.append("unaligned:"' in self.POST
        assert "the mix may be out of " in self.POST


class TestWhisperTalkingToItself:
    """On a track that is mostly silence Whisper repeats the last real thing
    that speaker said, at a steady cadence, for as long as the silence lasts.
    Dan Perra's transcript had Patrick saying "Hey, Dan." at 01:20, 01:50 and
    02:20 while he sat listening."""

    def _drop(self):
        from post_interview import _drop_echoes
        return _drop_echoes

    def test_the_repeats_go_and_the_first_one_stays(self):
        out = self._drop()([
            (10.0, "Patrick", "Hey, Dan."),
            (80.0, "Patrick", "Hey, Dan."),
            (140.0, "Patrick", "Hey, Dan."),
            (200.0, "Dan", "I am calling from a very wet corner of Ontario today"),
        ])
        assert [t for _s, _l, t in out] == [
            "Hey, Dan.", "I am calling from a very wet corner of Ontario today"]

    def test_a_real_line_said_twice_survives(self):
        segs = [(10.0, "Dan", "Yeah."),
                (30.0, "Mira", "And what happened next in that story?"),
                (40.0, "Dan", "Yeah.")]
        assert self._drop()(segs) == segs

    def test_a_long_line_is_never_an_echo(self):
        line = "The checklist exists because somebody died without one"
        segs = [(10.0, "Dan", line), (80.0, "Dan", line)]
        assert self._drop()(segs) == segs


class TestTheCutSurvivesTheHandoff:
    """Twice on Sept 15 2026 Dan Perra's episode was cut, written to the
    database, and then the job died before Mira recorded a word — with the
    cut stranded on a runner about to be destroyed. common.py logs to
    STDOUT, the workflow read auto_edit's stdout as JSON, and every log line
    went into the JSON."""

    AUTO = (V / "auto_edit.py").read_text(encoding="utf-8")
    FLOW = (ROOT / ".github" / "workflows"
            / "nerra_voices_post_interview.yml").read_text(encoding="utf-8")

    def test_the_logs_get_out_of_the_way(self):
        assert "def _logs_to_stderr()" in self.AUTO
        body = self.AUTO[self.AUTO.index("def main()"):]
        assert "_logs_to_stderr()" in body[:200]

    def test_the_result_is_written_somewhere_real(self):
        assert 'RESULT_PATH = os.environ.get("AUTO_EDIT_RESULT"' in self.AUTO
        assert "Path(RESULT_PATH).write_text" in self.AUTO

    def test_the_workflow_reads_the_file_not_the_pipe(self):
        step = self.FLOW[self.FLOW.index("name: Cut the episode"):]
        step = step[:step.index("name: Mira reads")]
        assert "| tee" not in step
        assert "AUTO_EDIT_RESULT: /tmp/cut.json" in step


class TestTheCoHostIsNotErased:
    """Patrick's track from the Dan Perra interview transcribed as "Hey,
    Dan." ninety-seven times — once every thirty seconds for forty-seven
    minutes — and everything he actually said was gone, including a long
    passage steering the second half of the interview. faster-whisper
    conditions each window on the previous text by default, so one short
    line emitted into silence propagates for the rest of the file. The same
    audio, decoded without that conditioning, gives 107 segments and a
    single "Hey, Dan" line.
    """

    ENGINE = (ROOT / "engine" / "transcripts.py").read_text(encoding="utf-8")

    def test_the_decoder_does_not_condition_on_its_own_echo(self):
        assert "condition_on_previous_text: bool = False" in self.ENGINE
        assert "condition_on_previous_text=condition_on_previous_text" in self.ENGINE

    def test_the_vad_keeps_it_out_of_the_silence(self):
        assert "vad_filter: bool = True" in self.ENGINE

    def test_a_missing_vad_runtime_does_not_lose_the_transcript(self):
        body = self.ENGINE[self.ENGINE.index("model = WhisperModel("):]
        body = body[:body.index("transcript_segments")]
        assert "transcribing without it" in body
        assert "model.transcribe(str(audio_path), **kwargs)" in body


class TestTheRightPackageGetsApproved:
    """An interview can have several editorial packages — a re-run of the
    post-interview job makes a new one. The assembler took whichever row
    came back first, which for Dan Perra was the oldest, killed one: the
    gate-1 button in Patrick's email would have approved a transcript
    nobody wanted."""

    ASSEMBLE = (V / "assemble_edit.py").read_text(encoding="utf-8")

    def test_it_takes_the_newest_live_package(self):
        body = self.ASSEMBLE[self.ASSEMBLE.index("def _tell_patrick"):]
        body = body[:body.index("guest = ")]
        assert "status=neq.killed" in body
        assert "order=created_at.desc" in body

    def test_it_still_finds_one_when_they_are_all_killed(self):
        body = self.ASSEMBLE[self.ASSEMBLE.index("def _tell_patrick"):]
        body = body[:body.index("guest = ")]
        assert body.count("sb_select(\n") >= 2


class TestAnEarnedTitleIsUsed:
    """Mira called Dr. Adrian Wolfberg "Adrian" for an hour. A first name is
    right for most guests and wrong for a scholar being interviewed about
    his field — the courtesy costs nothing and its absence is the first
    thing a listener notices."""

    def _a(self):
        import address
        return address

    def test_a_doctorate_in_the_name_is_found(self):
        a = self._a()
        assert a.written({"name": "Adrian Wolfberg, PhD"}) == "Dr. Wolfberg"
        assert a.spoken({"name": "Adrian Wolfberg, PhD"}) == "Doctor Wolfberg"

    def test_a_professor_is_a_professor(self):
        a = self._a()
        assert a.spoken({"name": "Ann Lee", "title": "Professor of History"}) \
            == "Professor Lee"

    def test_most_guests_keep_their_first_name(self):
        a = self._a()
        assert a.written({"name": "Dan Perra", "title": "Pilot"}) == "Dan"

    def test_a_guest_who_asked_for_their_first_name_gets_it(self):
        a = self._a()
        assert a.written({"name": "Adrian Wolfberg, PhD", "honorific": ""}) == "Adrian"

    def test_a_set_honorific_wins_over_the_guesswork(self):
        a = self._a()
        assert a.spoken({"name": "Adrian Wolfberg", "honorific": "Dr."}) \
            == "Doctor Wolfberg"

    def test_the_rule_tells_her_to_drop_it_if_invited(self):
        rule = self._a().address_rule({"name": "Adrian Wolfberg", "honorific": "Dr."})
        assert "ONLY if they invite you to" in rule

    def test_the_transcript_carries_it_too(self):
        from post_interview import _guest_label, speakers_header
        app = {"name": "Adrian Wolfberg", "honorific": "Dr."}
        assert _guest_label(app) == "Dr. Wolfberg"
        assert "Dr. Wolfberg (guest)" in speakers_header(app)

    def test_every_prompt_that_says_the_name_out_loud_uses_it(self):
        for name in ("mira_system_prompt.txt", "mira_narration.txt", "auto_edit.txt"):
            text = (V / "prompts" / name).read_text(encoding="utf-8")
            assert "{{guest_address}}" in text, name


class TestEveryLegOfTheCoHost:
    """Patrick's connection dropped and came back four times during the
    Wolfberg interview: legs of forty minutes, two, six and thirty seconds.
    Taking the longest kept him in the room for the first forty and deleted
    him from the rest of his own interview."""

    POST = (V / "post_interview.py").read_text(encoding="utf-8")
    MIX = (V / "audio" / "mix_tracks.py").read_text(encoding="utf-8")

    def test_it_fetches_all_of_them(self):
        assert "def leg_recordings(run: dict, role: str" in self.POST

    def test_each_leg_is_placed_in_the_room(self):
        body = self.POST[self.POST.index("def build_tracks"):]
        body = body[:body.index("def has_video_stream")]
        assert "align_to_room(\n                mono, guest_r," in body
        assert "mix_same_clock(placed" in body

    def test_a_leg_that_cannot_be_placed_is_left_out_not_guessed(self):
        body = self.POST[self.POST.index("def build_tracks"):]
        body = body[:body.index("def has_video_stream")]
        assert "did not correlate with the room" in body
        assert "unmeasured.append((i, mono, expect))" in body

    def test_a_placed_host_is_not_measured_a_second_time(self):
        body = self.POST[self.POST.index("def build_tracks"):]
        body = body[:body.index("def has_video_stream")]
        assert 'sources.get("host") == "voximplant"' in body
        assert 'roles = ("mira",)' in body

    def test_the_stitch_does_not_level_anything(self):
        body = self.MIX[self.MIX.index("def mix_same_clock"):]
        body = body[:body.index("def mix_three")]
        assert "normalize=0" in body and "dynaudnorm" not in body


class TestALegIsPlacedWhereTheRoomSaysItShouldBe:
    """Mira's leg began 268 seconds before the guest's in the Wolfberg
    interview, because the room opened when the co-host arrived and the
    guest was four and a half minutes behind him. A blind ±180s search
    could not reach the true peak, so it took a noise peak at -35.7s and
    the episode came back misaligned again. The room's own timeline says
    roughly where each leg belongs; the correlation only has to confirm
    it."""

    TRACKS = (V / "audio" / "local_tracks.py").read_text(encoding="utf-8")
    POST = (V / "post_interview.py").read_text(encoding="utf-8")
    ASSEMBLE = (V / "assemble_edit.py").read_text(encoding="utf-8")

    RUN = {"scenario_trace": [
        {"e": "room", "d": "opened (webrtc)", "t": "2026-09-15T18:54:10.453Z"},
        {"e": "leg", "d": "host #1 joined (1 in room)", "t": "2026-09-15T18:54:10.520Z"},
        {"e": "leg", "d": "guest #2 joined (2 in room)", "t": "2026-09-15T18:58:39.084Z"},
        {"e": "leg", "d": "host #3 joined (3 in room)", "t": "2026-09-15T19:33:25.398Z"},
    ]}

    def test_it_reads_every_join_in_order(self):
        from post_interview import join_offsets
        j = join_offsets(self.RUN)
        assert round(j["guest"][0]) == 269
        assert [round(x) for x in j["host"]] == [0, 2355]

    def test_the_search_can_reach_a_late_guest(self):
        from audio import local_tracks
        assert local_tracks.ROOM_MAX_OFFSET_SEC >= 600

    def test_the_expectation_narrows_the_search(self):
        body = self.TRACKS[self.TRACKS.index("def estimate_room_delay"):]
        body = body[:body.index("def align_to_room")]
        assert "lo, hi = -span, span" in body

    def test_mira_is_expected_where_the_room_opened(self):
        body = self.POST[self.POST.index("def build_tracks"):]
        body = body[:body.index("def has_video_stream")]
        assert 'if role == "mira":\n            return -guest_join' in body
        assert 'expect = expected_delay("host", i)' in body

    def test_a_track_that_would_not_place_is_said_out_loud(self):
        from assemble_edit import _sync_warning
        warn = _sync_warning({"grok_session_log": {"tracks": {"unaligned": ["host"]}}})
        assert "Listen for sync before" in warn
        assert "do not approve this" in warn
        assert _sync_warning({"grok_session_log": {"tracks": {"unaligned": []}}}) == ""


class TestOnlyTheGuestLeavingIsAnEvent:
    """Patrick's connection dropped four times during the Wolfberg
    interview and each reconnection made Mira stop and acknowledge it, over
    the top of the guest's answer. The co-host must be able to come and go
    without the interview noticing. A guest coming back is different: they
    missed what was said and need the question again."""

    SCENARIO = (ROOT / "voximplant" / "scenarios"
                / "age_of_ai_interview.js").read_text(encoding="utf-8")

    def test_nothing_forces_her_to_speak_about_the_room(self):
        body = self.SCENARIO[self.SCENARIO.index("function noteRoom("):]
        body = body[:body.index("function resumeForGuest(")]
        assert "responseCreate" not in body
        assert "Do NOT respond to this note" in body

    def test_the_co_host_coming_back_is_context_only(self):
        assert 'noteRoom(role + " joined")' in self.SCENARIO
        assert 'noteRoom(role + " left the room")' in self.SCENARIO
        assert "announce(" not in self.SCENARIO

    def test_a_returning_guest_gets_the_question_again(self):
        assert 'role === "guest" && guestJoins > 1' in self.SCENARIO
        body = self.SCENARIO[self.SCENARIO.index("function resumeForGuest("):]
        body = body[:body.index("// Whole-room mix")]
        assert "ask your last question again IN FULL" in body
        assert "responseCreate" in body

    def test_a_guest_arriving_for_the_first_time_is_not_a_rejoin(self):
        body = self.SCENARIO[self.SCENARIO.index("postLegEvent(role, \"joined\")"):]
        body = body[:body.index("const gone =")]
        assert "if (!openingFired) {" in body


class TestTheAlignmentChecksItsOwnWork:
    """Three episodes went out misaligned while the pipeline believed it had
    done the arithmetic. Two things were wrong. The windows compared the same
    stretch of both files, so a correlation could never find a lag longer
    than the window — with Mira's leg 268s ahead of the guest's, one file's
    150 seconds held no part of the other's conversation. And the answer was
    the median of every window including the noise, which dragged Mira's
    estimate 35s off. Measured properly on the Wolfberg tapes the shift is
    -233.69s for Mira and -256.33s for the co-host, and both verify at zero
    afterwards."""

    TRACKS = (V / "audio" / "local_tracks.py").read_text(encoding="utf-8")

    def test_the_expectation_is_applied_not_just_searched_within(self):
        body = self.TRACKS[self.TRACKS.index("def estimate_room_delay"):]
        body = body[:body.index("def align_to_room")]
        assert "cut = int(round(-base * ROOM_ENVELOPE_SR))" in body
        assert "track = track[cut:]" in body

    def test_the_answer_is_what_the_windows_agree_on(self):
        body = self.TRACKS[self.TRACKS.index("def estimate_room_delay"):]
        body = body[:body.index("def align_to_room")]
        assert "picks.sort(key=lambda p: p[1], reverse=True)" in body
        assert "abs(d - anchor) <= ROOM_AGREE_SEC" in body

    def test_it_measures_again_after_shifting(self):
        body = self.TRACKS[self.TRACKS.index("def align_to_room"):]
        assert "expected=0.0, span=30.0" in body
        assert "ROOM_RESIDUAL_SEC" in body

    def test_a_track_that_does_not_verify_counts_as_unplaced(self):
        body = self.TRACKS[self.TRACKS.index("def align_to_room"):]
        assert "treating as unplaced" in body
        assert "return out, delay, 0" in body


class TestAShortReconnectionStillCounts:
    """Adrian Wolfberg's co-host legs were 2421s, 118s, 373s and 28s. A
    two-minute reconnection cannot hold two 150-second windows, so the
    short ones were refused and Patrick was thrown out of his own
    interview. Measured properly the recorder lag is the same on every leg
    — 12.23s and 12.40s where it could be checked — so a leg that will not
    correlate can still be placed by the lag a leg that did correlate
    measured. Stitched, all four verify at +0.04s against the room."""

    TRACKS = (V / "audio" / "local_tracks.py").read_text(encoding="utf-8")
    POST = (V / "post_interview.py").read_text(encoding="utf-8")

    def test_a_short_leg_is_measured_in_short_windows(self):
        body = self.TRACKS[self.TRACKS.index("def estimate_room_delay"):]
        body = body[:body.index("def align_to_room")]
        assert "if covered < 2 * window:" in body
        assert "ROOM_MIN_WINDOW_SEC" in body

    def test_one_emphatic_window_is_enough(self):
        body = self.TRACKS[self.TRACKS.index("def align_to_room"):]
        assert "agreement >= ROOM_STRONG_CORR" in body

    def test_the_recorder_lag_places_what_cannot_be_measured(self):
        body = self.POST[self.POST.index("def build_tracks"):]
        body = body[:body.index("def has_video_stream")]
        assert "recorder_lag = delay - expect" in body
        assert "at = expect + recorder_lag" in body
        assert "place_at(mono, at," in body

    def test_a_leg_with_nothing_to_place_it_by_is_left_out(self):
        body = self.POST[self.POST.index("def build_tracks"):]
        body = body[:body.index("def has_video_stream")]
        assert "nothing to place it by" in body


class TestTheEdlAddressesTheRightSeconds:
    """Once every track sits on the guest leg's clock, the transcript IS on
    that clock. Converting from the room's clock a second time moved every
    cut in Adrian Wolfberg's episode 268 seconds early: it opened four and a
    half minutes into the conversation and stopped five minutes before he
    finished."""

    AUTO = (V / "auto_edit.py").read_text(encoding="utf-8")
    ASSEMBLE = (V / "assemble_edit.py").read_text(encoding="utf-8")

    def test_aligned_tracks_need_no_conversion(self):
        body = self.AUTO[self.AUTO.index("def _leg_offset"):]
        body = body[:body.index("def _context")]
        assert 'if ((log.get("tracks") or {}).get("alignment")) is not None:' in body
        assert "return 0.0" in body

    def test_one_voice_alone_can_be_cut_to(self):
        assert 'out[f"track:{role}"] = url' in self.ASSEMBLE
        body = self.ASSEMBLE[self.ASSEMBLE.index("def _run_sources"):]
        body = body[:body.index("def _resolve")]
        assert '(log.get("tracks") or {}).get("processed")' in body

    def test_an_edl_can_actually_resolve_it(self):
        """Offering the source and resolving a reference to it are two
        different things. The Wolfberg assemble spent twelve minutes
        fetching and then died on "unrecognised source 'track:guest'"."""
        from assemble_edit import _resolve
        from shows import get_show
        run = {"grok_session_log": {"tracks": {"processed": {
            "guest": "https://a/g.wav"}}}}
        assert _resolve("track:guest", run, get_show("age_of_ai"), "s") \
            == "https://a/g.wav"

    def test_a_track_that_is_not_there_says_which_are(self):
        import pytest
        from assemble_edit import _resolve
        from shows import get_show
        with pytest.raises(SystemExit, match="not on the run row"):
            _resolve("track:nobody", {}, get_show("age_of_ai"), "s")


class TestWolfbergIsLetToFinish:
    """Mira read her closing over the last ninety seconds of his final
    answer, called him by his first name throughout, and left him asking
    whether he was supposed to press a button. The edit gives him his
    ending back and the written close says so out loud."""

    EDL = json.loads((V / "edl" / "adrian_wolfberg_2026_09_15.json")
                     .read_text(encoding="utf-8"))
    NARRATION = json.loads((V / "narration" / "adrian_wolfberg_2026_09_15.json")
                           .read_text(encoding="utf-8"))

    def test_his_last_answer_comes_from_his_own_microphone(self):
        tail = [c for c in self.EDL["cuts"] if c.get("from") == "track:guest"]
        assert len(tail) == 1
        assert tail[0]["start"] == 2261.0 and tail[0]["end"] == 2362.0

    def test_the_body_runs_unbroken_to_that_point(self):
        body = [c for c in self.EDL["cuts"] if c.get("from") == "run:guest"]
        assert len(body) == 1
        assert body[0]["end"] == 2261.0

    def test_the_close_owns_the_mistake_and_promises_a_return(self):
        outro = next(s["text"] for s in self.NARRATION["segments"]
                     if s["id"] == "outro")
        assert "talked over the last ninety seconds" in outro
        assert "should have said Doctor Wolfberg" in outro
        assert "asked him back" in outro

    def test_he_is_doctor_wolfberg_in_both_segments(self):
        for seg in self.NARRATION["segments"]:
            assert "Doctor Wolfberg" in seg["text"], seg["id"]


class TestABookingIsNeverLost:
    """Mo Fakhro booked as mo@mofakhro.com while his application was under
    his publicist's pr@mofakhro.com, which was on the booking as a guest.
    Only the first attendee was ever looked at, so the booking matched
    nothing, no interview was created, and a confirmed guest would have sat
    waiting for a call nobody had scheduled. Nobody would have known until
    the day."""

    WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")

    def test_every_address_on_the_booking_is_tried(self):
        assert "function bookingEmails(p: any): string[]" in self.WORKER
        body = self.WORKER[self.WORKER.index("function bookingEmails"):]
        body = body[:body.index("async function handleCalComBooked")]
        assert "p.attendees" in body
        assert "responses?.guests" in body

    def test_it_matches_on_any_of_them(self):
        body = self.WORKER[self.WORKER.index("async function handleCalComBooked"):]
        assert "for (const candidate of emails)" in body

    def test_an_unmatched_booking_shouts_and_still_schedules(self):
        """Sept 20 2026: Meridan Zerner applied under one address and booked
        under another, before the shout existed. Found by hand 38 minutes
        before the call. Now the name and the phone on the booking are tried,
        and a booking that still matches nothing gets a placeholder
        application and a scheduled call rather than silence."""
        body = self.WORKER[self.WORKER.index("async function handleCalComBooked"):]
        body = body[:body.index("const show = showFor(apps[0]")]
        assert "matched NO application" in body
        assert "matched no application" in body
        assert 'source: "calcom"' in body and 'status: "approved"' in body
        assert "namesOverlap(a.name, bookedName)" in body
        assert "phoneDigits(a.phone) === bookedPhone" in body
        assert "if (distinct.size > 1) hits = [];" in body

    def test_the_name_match_is_strict_enough(self):
        helpers = self.WORKER[self.WORKER.index("function nameKey"):self.WORKER.index("async function handleCalComBooked")]
        assert "common.length >= 2" in helpers
        assert "function bookingPhone(p: any): string" in helpers


class TestPublishingShipsTheEpisodeNotTheRoom:
    """publish_one read recording_mixed_url, which for every episode cut by
    the new pipeline is the RAW mix of the room — no introduction, no close,
    nothing edited out, a quarter-gigabyte WAV. Dan Perra's episode was one
    approval away from going out as the unedited forty-seven minutes with
    the false ending still in it."""

    def _f(self):
        from publish_episode import episode_audio
        return episode_audio

    def test_the_assembled_edit_wins(self):
        assert self._f()({"grok_session_log": {"tracks": {
            "edit": {"url": "https://a/x_edit.mp3"}}}}) == "https://a/x_edit.mp3"

    def test_the_older_produced_episode_still_counts(self):
        assert self._f()({"recording_mixed_url": "https://a/x_episode.mp3"}) \
            == "https://a/x_episode.mp3"

    def test_the_raw_room_is_refused(self):
        import pytest
        with pytest.raises(RuntimeError, match="raw room"):
            self._f()({"recording_mixed_url": "https://a/x_20260915_mixed.wav"})

    def test_nothing_at_all_is_refused(self):
        import pytest
        with pytest.raises(RuntimeError):
            self._f()({})


class TestEveryEpisodeGetsItsOwnPost:
    """An hour of somebody's expertise reached the site as one line in a
    summary list. The interview shows bypass run_show, so they never wrote a
    digest and never got a blog post, while every other show on the network
    did. generate_html turns digests/<slug>/*.md into blog/<slug>/ep###.html
    already — the episode just has to write the file it reads."""

    PUB = (V / "publish_episode.py").read_text(encoding="utf-8")
    WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")

    def _digest(self, **over):
        import datetime as dt
        from publish_episode import write_episode_digest
        from shows import get_show
        app = {"name": "Ada Lovelace", "title": "Mathematician",
               "organization": "Analytical Engine", "bio": "She wrote the first program.",
               "links": {"raw": "https://example.org"}}
        pkg = {"episode_notes": "The lead paragraph.\n\nThe rest of it.",
               "chapter_markers": [{"start": 90, "title": "The engine"}],
               "guest_materials": "https://example.org/paper\nMy book",
               "transcript_cleaned": "[00:01] Ada: Hello."}
        pkg.update(over)
        path = write_episode_digest(get_show("age_of_ai"), 7, dt.date(2026, 9, 17),
                                    "Ep7", {"episode_thesis": "A thesis."},
                                    app, pkg, "https://audio/x.mp3")
        text = path.read_text(encoding="utf-8")
        path.unlink()
        return text

    def test_the_post_carries_the_guests_own_links(self):
        text = self._digest()
        assert "### Where to find Ada Lovelace" in text
        assert "https://example.org" in text

    def test_it_carries_what_they_asked_us_to_link(self):
        text = self._digest()
        assert "### What they wanted you to read next" in text
        assert "- https://example.org/paper" in text
        assert "- My book" in text

    def test_a_guest_who_sent_nothing_gets_no_empty_heading(self):
        text = self._digest(guest_materials="")
        assert "What they wanted you to read next" not in text

    def test_bio_chapters_and_transcript_are_there(self):
        text = self._digest()
        assert "### About Ada Lovelace" in text
        assert "She wrote the first program." in text
        assert "**01:30** The engine" in text
        assert "### Transcript" in text

    def test_the_file_is_named_so_the_generator_finds_the_episode(self):
        import datetime as dt
        from publish_episode import write_episode_digest
        from shows import get_show
        path = write_episode_digest(
            get_show("age_of_ai"), 7, dt.date(2026, 9, 17), "Ep7", {},
            {"name": "A"}, {}, "https://audio/x.mp3")
        assert path.name.startswith("Age_of_AI_Ep007_20260917")
        assert path.parent.name == "age_of_ai"
        path.unlink()

    def test_the_site_run_actually_renders_posts(self):
        assert '"--show", show.slug, "--blogs"' in self.PUB

    def test_the_guest_is_asked_for_materials_where_they_are_approving(self):
        assert 'id="materials"' in self.WORKER
        assert "guest_materials: materials" in self.WORKER
        assert "when this publishes we write a full post" in self.WORKER


class TestTheGuestKnowsWhenItIsOver:
    """Dr. Wolfberg finished his last answer and sat asking "Am I supposed
    to hit the end interview button or what?" — nobody had told him it was
    over. The prompt now ends with an explicit handoff and the studio page
    says the same thing before the call starts."""

    PROMPT = _flat((V / "prompts" / "mira_system_prompt.txt").read_text(encoding="utf-8"))
    STUDIO = (ROOT / "age-of-ai-studio.html").read_text(encoding="utf-8")

    def test_she_says_the_recording_is_finished(self):
        assert "HOW IT ENDS, FOR THE GUEST" in self.PROMPT
        assert '"that\'s the end of the recording"' in self.PROMPT
        assert '"you can hang up now"' in self.PROMPT

    def test_and_then_says_nothing(self):
        block = self.PROMPT[self.PROMPT.index("HOW IT ENDS, FOR THE GUEST"):]
        block = block[:block.index("WHAT YOU ARE")]
        assert "nothing at all once they have left the room" in block

    def test_the_page_tells_them_before_they_start(self):
        assert "How this ends:" in self.STUDIO
        assert "press <b>End interview</b>" in self.STUDIO



def _bursts(seconds: float, sr: int, spans, level: float, seed: int = 1) -> "np.ndarray":
    """Noise bursts (speech, for a correlator) at the given (start, end)
    seconds, silence elsewhere."""
    import numpy as np
    rng = np.random.default_rng(seed)
    out = np.zeros(int(seconds * sr), dtype=np.float32)
    for a, b in spans:
        lo, hi = int(a * sr), min(len(out), int(b * sr))
        out[lo:hi] = rng.standard_normal(hi - lo).astype(np.float32) * level
    return out


def _write(path, data, sr: int):
    import wave
    import numpy as np
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(np.clip(data * 32767, -32768, 32767).astype("<i2").tobytes())


def _rms_db(path, start: float, end: float) -> float:
    import wave
    import numpy as np
    with wave.open(str(path)) as w:
        sr = w.getframerate()
        w.setpos(int(start * sr))
        x = np.frombuffer(w.readframes(int((end - start) * sr)), dtype="<i2").astype(float) / 32768
    return float(20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-9))


class TestALegThatLostTimeIsPlacedInPieces:
    """Sheldon Poon, Sept 17 2026. Mira's session was handed over and then
    reconnected twenty-six minutes in, and her leg's recorder lost 159
    seconds while that happened. Measured as one offset the leg placed by
    its first half, the whole second half sat 159 seconds early in the mix,
    her lines were transcribed off the guest's microphone as his, and the
    check that was meant to catch a misplaced track passed, because the
    windows that disagreed were simply the ones it did not count."""

    SR = 8000

    @pytest.fixture
    def room_and_leg(self, tmp_path):
        import numpy as np
        rng = np.random.default_rng(7)
        # A room of two-second utterances every eight seconds for 15 min.
        spans = [(t, t + 2) for t in np.arange(3, 890, 8) + rng.uniform(0, 3, 111)]
        room = _bursts(900, self.SR, spans, 0.3)
        # The leg starts 10s after the room and, 400s in, skips 60s.
        first = room[int(10 * self.SR):int(410 * self.SR)]
        second = room[int(470 * self.SR):]
        leg = np.concatenate([first, second])
        _write(tmp_path / "room.wav", room, self.SR)
        _write(tmp_path / "leg.wav", leg, self.SR)
        return tmp_path

    def test_both_pieces_and_the_seam_are_found(self, room_and_leg):
        from audio.local_tracks import room_pieces
        pieces = room_pieces(room_and_leg / "leg.wav", room_and_leg / "room.wav",
                             room_and_leg / "work", expected=10.0)
        assert len(pieces) == 2, pieces
        assert abs(pieces[0]["delay"] - 10) < 1.0
        assert abs(pieces[1]["delay"] - 70) < 1.0
        assert 380 <= pieces[0]["to"] <= 420
        assert pieces[1]["from"] == pieces[0]["to"]

    def test_the_placed_leg_verifies_along_its_whole_length(self, room_and_leg):
        from audio.local_tracks import align_to_room
        pieces = []
        out, delay, windows = align_to_room(
            room_and_leg / "leg.wav", room_and_leg / "room.wav",
            room_and_leg / "work", expected=10.0, pieces_out=pieces)
        assert windows > 0, "a leg placed in pieces must still count as placed"
        assert len(pieces) == 2
        assert abs(delay - 10) < 1.0
        # After placing, the leg's second half sits where the room has it.
        import numpy as np
        for t in (700.0, 800.0):
            room_on = _rms_db(room_and_leg / "room.wav", t, t + 8)
            leg_on = _rms_db(out, t, t + 8)
            assert abs(room_on - leg_on) < 3.0, (t, room_on, leg_on)

    def test_a_single_offset_still_takes_the_short_path(self, tmp_path):
        import numpy as np
        rng = np.random.default_rng(3)
        spans = [(t, t + 2) for t in np.arange(3, 590, 8) + rng.uniform(0, 3, 74)]
        room = _bursts(600, self.SR, spans, 0.3)
        _write(tmp_path / "room.wav", room, self.SR)
        _write(tmp_path / "leg.wav", room[int(10 * self.SR):], self.SR)
        from audio.local_tracks import room_pieces
        pieces = room_pieces(tmp_path / "leg.wav", tmp_path / "room.wav",
                             tmp_path / "work", expected=10.0)
        assert len(pieces) == 1 and abs(pieces[0]["delay"] - 10) < 1.0

    def test_the_pieces_are_recorded_with_the_run(self):
        post = (V / "post_interview.py").read_text(encoding="utf-8")
        assert 'pieces_out=role_pieces' in post
        assert '"pieces": tracks.get("pieces") or {}' in post

    def test_the_envelope_cache_does_not_outlive_its_file(self):
        tracks = (V / "audio" / "local_tracks.py").read_text(encoding="utf-8")
        assert "small.stat().st_mtime < Path(path).stat().st_mtime" in tracks


class TestTheGuestsMicrophoneCarriesOnlyTheGuest:
    """Sheldon had no headphones. His laptop heard Mira through the
    speakers, eighteen decibels under his own voice, and the mix had every
    question twice. Patrick: cut his audio so we only hear him."""

    SR = 8000

    def test_the_bleed_is_muted_and_the_voice_is_kept(self, tmp_path):
        import numpy as np
        mira_spans = [(t, t + 4) for t in range(2, 300, 20)]
        guest_spans = [(t + 8, t + 16) for t in range(2, 300, 20)]
        mira = _bursts(300, self.SR, mira_spans, 0.3, seed=1)
        own = _bursts(300, self.SR, guest_spans, 0.3, seed=2)
        bleed = _bursts(300, self.SR, mira_spans, 0.3 / 8, seed=1)  # -18 dB
        guest = own + bleed
        _write(tmp_path / "mira.wav", mira, self.SR)
        _write(tmp_path / "guest.wav", guest, self.SR)
        from audio.bleed import strip_bleed
        out, stats = strip_bleed(tmp_path / "guest.wav", [tmp_path / "mira.wav"],
                                 tmp_path / "work", "guest")
        assert stats["bleed"] is True
        assert out != tmp_path / "guest.wav"
        # Mira's stretch on his track is now silence; his own is untouched.
        assert _rms_db(out, 42.5, 45.5) < _rms_db(tmp_path / "guest.wav", 42.5, 45.5) - 20
        assert abs(_rms_db(out, 51, 57) - _rms_db(tmp_path / "guest.wav", 51, 57)) < 0.5

    def test_a_clean_microphone_is_left_alone(self, tmp_path):
        mira_spans = [(t, t + 4) for t in range(2, 300, 20)]
        guest_spans = [(t + 8, t + 16) for t in range(2, 300, 20)]
        _write(tmp_path / "mira.wav", _bursts(300, self.SR, mira_spans, 0.3), self.SR)
        _write(tmp_path / "guest.wav", _bursts(300, self.SR, guest_spans, 0.3, seed=2), self.SR)
        from audio.bleed import strip_bleed
        out, stats = strip_bleed(tmp_path / "guest.wav", [tmp_path / "mira.wav"],
                                 tmp_path / "work", "guest")
        assert stats == {"bleed": False} and out == tmp_path / "guest.wav"

    def test_every_own_microphone_is_relieved_before_mixing(self):
        post = (V / "post_interview.py").read_text(encoding="utf-8")
        body = post[post.index("def build_tracks"):post.index("def has_video_stream")]
        assert "strip_bleed(\n            guest, [mira, host, guest_r]" in body
        assert "strip_bleed(host, [mira, guest]" in body
        assert '"bleed": tracks.get("bleed") or {}' in post


class TestTheCleanedTranscriptReachesTheEnd:
    """Sept 17 2026: Dan's, Adrian's and Sheldon's cleaned transcripts all
    stopped around minute 25 — the model's 6,000-token output cap — and the
    guest review page showed half the interview. The pass has to be given
    room for the whole transcript, and a copy that stops early is invalid."""

    def test_the_output_budget_follows_the_transcript(self):
        post = (V / "post_interview.py").read_text(encoding="utf-8")
        assert 'if field == "transcript_cleaned":\n                budget = max(6000, min(32000, len(transcript) // 2))' in post
        assert "raw=transcript if field == \"transcript_cleaned\" else None" in post

    def test_a_truncated_copy_is_rejected(self):
        from validators.schema_validators import validate_pass_output
        raw = "\n".join(f"[{m:02d}:00] {'Mira' if m % 2 else 'Dan'}: " + "word " * 30
                        for m in range(0, 46))
        short = "\n".join(raw.splitlines()[:26])
        with pytest.raises(Exception) as err:
            validate_pass_output("transcript_cleaned", short, raw=raw)
        assert "truncated" in str(err.value)
        validate_pass_output("transcript_cleaned", raw, raw=raw)  # whole: fine


class TestSheDoesNotPromiseACoHostWhoIsNotComing:
    """Sheldon Poon, Sept 17 2026. Patrick had an emergency and never
    joined. The hold expired, the show opened, and Mira introduced him as
    her co-host who would jump in once he was settled, because the prompt
    tells her to introduce him and nothing told her he was not there."""

    SCENARIO = (ROOT / "voximplant" / "scenarios"
                / "age_of_ai_interview.js").read_text(encoding="utf-8")

    def test_the_room_tells_her_when_he_is_absent(self):
        body = self.SCENARIO[self.SCENARIO.index("function openWhenReady("):]
        body = body[:body.index("function cohostHoldMs(")]
        assert 'config.host_mode && humansIn("host") === 0' in body
        assert '"joined and is not expected. Open the show without him: do not "' in body
        assert "do not say he will jump in" in body
        assert "your co-host could not join today" in body


class TestPatrickIsToldWhatWasDoneToTheTapes:
    def test_pieces_and_bleed_are_in_the_assemble_email(self):
        from assemble_edit import _placement_notes
        run = {"grok_session_log": {"tracks": {
            "pieces": {"mira": [{"from": 0, "to": 1555, "delay": 15.7},
                                {"from": 1555, "to": 2760, "delay": 174.8}]},
            "bleed": {"guest": {"bleed": True, "own_db": -29.5, "bleed_db": -47.1,
                                "muted_sec": 372.0}}}}}
        note = _placement_notes(run)
        assert "placed in 2 pieces" in note and "25:55" in note
        assert "18 dB under its own" in note and "372s" in note
        assert _placement_notes({"grok_session_log": {"tracks": {}}}) == ""
        assemble = (V / "assemble_edit.py").read_text(encoding="utf-8")
        assert "+ _placement_notes(run)" in assemble


class TestTheGuestSeesTheirApprovalLand:
    """Dr. Wolfberg pressed Approve for publication, the approval was
    recorded, and he emailed to ask whether anything had happened: the
    only acknowledgement was a line at the bottom of a long page."""

    WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")

    def test_the_answer_appears_where_the_button_was(self):
        body = self.WORKER[self.WORKER.index("async function submitReview"):]
        body = body[:body.index("</script>")]
        assert "approveBtn.disabled = removeBtn.disabled = true" in body
        assert "document.getElementById('actions').style.display = 'none'" in body
        assert "done.scrollIntoView" in body
        assert "approveBtn.textContent = 'Approve for publication'" in body  # re-enabled on failure


class TestATruncatedTranscriptCanBeRedoneOnItsOwn:
    def test_the_script_and_workflow_exist(self):
        script = (V / "reclean_transcript.py").read_text(encoding="utf-8")
        assert 'validate_pass_output("transcript_cleaned", text, raw=transcript)' in script
        assert "budget = max(6000, min(32000, len(transcript) // 2))" in script
        wf = (ROOT / ".github" / "workflows" / "nerra_voices_reclean_transcript.yml").read_text(encoding="utf-8")
        assert "reclean_transcript.py" in wf and "package_id" in wf


class TestTheGuestFinishesTheirSentence:
    """Sheldon Poon's cut ended at 47:58, the START of his last line, so the
    episode ended on "...the quality and the amount" and "that we can
    produce" was never heard. The transcript stamps where lines begin; the
    end of the edit has to be where the last line ends."""

    def test_the_end_moves_past_the_last_line(self):
        from auto_edit import _after_the_line
        t = ("[47:49] Sheldon: So I'm using automation to create more automation\n"
             "[47:58] Sheldon: that we can produce.\n"
             "[48:03] Mira: Thank you, Sheldon. That's the end of the recording.\n")
        # Pointed at the start of his last line: past it, right up to Mira.
        assert 2879.5 <= _after_the_line(t, 2878.0) <= 2882.8
        # Pointed at the first line of his final thought: the whole thought.
        assert _after_the_line(t, 2869.0) == _after_the_line(t, 2878.0)
        # Pointed at Mira's sign-off: pulled back to the end of his turn.
        assert _after_the_line(t, 2883.0) == _after_the_line(t, 2878.0)
        # A long last line is still bounded by the next speaker's start: past
        # it lies Mira's live sign-off, which the listener never hears.
        t2 = "[10:00] Dan: " + "word " * 40 + "\n[10:05] Mira: Right.\n"
        assert _after_the_line(t2, 600.0) == 604.75
        # The last line of the file is extended by its own length.
        assert _after_the_line("[10:00] Dan: four words here now\n", 600.0) == 600.0 + 0.45 * 4 + 1.2

    def test_the_cutter_uses_it(self):
        auto = (V / "auto_edit.py").read_text(encoding="utf-8")
        # Sept 22 2026: the call goes through _where_it_closes, which makes
        # the guest's LAST turn the default rather than whichever turn the
        # model pointed at.
        assert "_where_it_closes(" in auto
        assert "end = leg(end)" in auto
        assert "the cut is carried to where their turn ends" in _flat(AUTO_PROMPT)
        assert "At the close of the conversation. That is the default" in _flat(AUTO_PROMPT)
        assert "what is not allowed is one that happens quietly" in _flat(AUTO_PROMPT)


class TestAPublishedEpisodesPostCanBeRefreshed:
    """Dan's page shipped with half a transcript and no post. Publishing
    again is refused, and would have minted a second episode number."""

    def test_refresh_keeps_the_number_and_the_feed(self):
        pub = (V / "publish_episode.py").read_text(encoding="utf-8")
        body = pub[pub.index("def refresh_post"):pub.index("def main")]
        assert 'if interview.get("status") != "published":' in body
        assert 'episode_num = int(interview.get("episode_number") or 0)' in body
        assert "write_episode_digest(show, episode_num, when, entry[\"title\"]" in body
        assert "update_rss_feed" not in body and "sb_update" not in body
        assert 'os.environ.get("REFRESH_POST", "").strip() in ("1", "true")' in pub
        wf = (ROOT / ".github" / "workflows" / "nerra_voices_publish.yml").read_text(encoding="utf-8")
        assert "REFRESH_POST" in wf


class TestTheAdjectiveReflexIsBannedAsAShape:
    """Retiring "That's a crisp way to put it" produced "That's a sharp
    distinction", "That's a clean metric", "That's a big phrase": seventy
    lines across six episodes, each technically new. Patrick, Sept 18 2026:
    more variety and personality. The shape is what repeats."""

    def test_the_variety_block_names_the_shape_not_the_instances(self, monkeypatch):
        import learning
        rows = [{"phrase": p} for p in (
            "That's a crisp way to put it", "That's a sharp distinction",
            "That's a clean metric", "Fair enough")]
        monkeypatch.setattr(learning, "sb_select", lambda *a, **k: rows)
        block = learning.variety_block("age_of_ai")
        assert 'The shape "That\'s a ..." is retired outright' in block
        assert "opened 3 replies with it" in block
        assert '- "Fair enough"' in block
        assert "crisp" not in block  # the instances are not listed one by one

    def test_the_prompt_bans_the_shape_and_bridges_the_warm_up(self):
        assert 'opening a reply with "That\'s a [adjective] [noun]"' in PROMPT
        assert "Do not grade an answer with an adjective at all" in PROMPT
        assert "WARM UP FIRST, THEN EASE IN" in PROMPT
        assert "come out of something they just said" in PROMPT
        assert "a fast, dry guest gets a fast, dry host" in PROMPT


class TestPatrickIsTheCreatorAndAnOccasionalCoHost:
    """Sept 18 2026. Mira does the job on her own. Patrick, who made the
    network, joins when a guest asks for him on the application."""

    WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")

    def test_the_form_asks_and_the_booking_carries_it(self):
        # Sept 24 2026: Patrick no longer joins interviews. The form stops
        # offering him and a booking never turns host mode on; the Worker
        # still reads the field so old applications parse.
        for page in ("age-of-ai-apply.html", "nerra-voices-apply.html"):
            html = (ROOT / page).read_text(encoding="utf-8")
            assert 'name="wants_cohost"' not in html
        assert "wants_cohost: form.wants_cohost === true" in self.WORKER
        assert self.WORKER.count("host_mode: false") >= 2
        assert "host_mode: !!apps[0].wants_cohost" not in self.WORKER

    def test_mira_alone_is_the_default(self):
        fire = (V / "fire_interviews.py").read_text(encoding="utf-8")
        body = fire[fire.index("def host_mode_enabled"):fire.index("COHOST_INTRO_STEP")]
        assert "return False" in body and 'is not None' in body
        assert "he joins as co-host when a guest has asked for him" in PROMPT


class TestApplicationsAreScreenedForSubstance:
    """Rhett Mikols, Sept 17 2026: a publicist's pitch, a name and a vision,
    no work behind either, forty-five minutes of Mira asking for an instance.
    The producer approved from a bio and a topic list; the screen is the
    paragraph that would have said there was nothing behind them."""

    SCREEN = (V / "screen_applications.py").read_text(encoding="utf-8")
    PROMPT_TXT = _flat((V / "prompts" / "screen_application.txt").read_text(encoding="utf-8"))
    WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")

    def test_it_looks_for_checkable_work_not_phrasing(self):
        assert "Abstractions with no instance" in self.PROMPT_TXT
        assert "A publicist's pitch is not a mark against the guest" in self.PROMPT_TXT
        assert "Not finding something is not proof of anything" in self.PROMPT_TXT
        assert '"verdict": "strong" | "thin" | "unclear"' in self.PROMPT_TXT

    def test_it_advises_and_never_declines(self):
        assert 'sb_update("guest_applications"' in self.SCREEN
        assert '"screen": result' in self.SCREEN
        body = self.SCREEN[self.SCREEN.index("def screen_one"):self.SCREEN.index("def main")]
        assert '"status":' not in body  # it never changes an application's status
        assert "web_search=True" in self.SCREEN
        assert 'if result["verdict"] == "thin":' in self.SCREEN

    def test_the_triage_page_shows_it_beside_approve(self):
        body = self.WORKER[self.WORKER.index("const screenHtml"):self.WORKER.index("const sections")]
        assert "not yet screened" in body
        assert 'sc.verdict === "thin" ? "#991B1B"' in body
        assert "${screenHtml(a)}" in body
        wf = (ROOT / ".github" / "workflows" / "nerra_voices_screen_applications.yml").read_text(encoding="utf-8")
        assert "screen_applications.py" in wf and "cron:" in wf

    def test_the_columns_exist(self):
        sql = (ROOT / "supabase" / "migrations"
               / "20260918_cohost_on_request_and_substance_screen.sql").read_text(encoding="utf-8")
        assert "wants_cohost boolean not null default false" in sql
        assert "screen jsonb" in sql


class TestTheReadArrivesBeforeTheDecision:
    """Patrick, Sept 18 2026: run the check when the application comes in,
    so the assessment is in front of me before I approve; and a decline is
    a polite decline like any other."""

    WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")
    SCREEN = (V / "screen_applications.py").read_text(encoding="utf-8")

    def test_the_worker_dispatches_the_screen_on_arrival(self):
        body = self.WORKER[self.WORKER.index("async function handleApply"):self.WORKER.index("const PLATFORM_FAULT_REASONS")]
        assert 'await dispatch(env, "application-received", { application_id: id })' in body
        assert "if (!screening) {" in body  # the plain email is the fallback
        wf = (ROOT / ".github" / "workflows" / "nerra_voices_screen_applications.yml").read_text(encoding="utf-8")
        assert "types: [application-received]" in wf
        assert "github.event.client_payload.application_id || inputs.application_id" in wf
        assert "ADMIN_TOKEN" in wf and "RESEND_API_KEY" in wf

    def test_the_email_carries_the_read_and_the_link(self):
        import screen_applications as sc
        subject, body = sc.assessment_email(
            {"name": "A B", "title": "CEO", "organization": "X", "bio": "bio", "topics": ["t1"],
             "show": "age_of_ai", "source": "email", "publicist_name": "P", "status": "pending"},
            {"verdict": "thin", "summary": "S", "specifics": ["f1"], "concerns": ["c1"], "ask_first": "Q?"})
        assert "my read is thin" in subject
        assert "pitched by a publicist (P)" in body
        assert "What I could find" in body and "f1" in body
        assert "What I could not" in body and "c1" in body
        assert "/voices/admin/triage" in body
        assert 'if app.get("status") == "pending":' in self.SCREEN

    def test_a_decline_is_answered_politely(self):
        body = self.WORKER[self.WORKER.index("async function handleTriageDecision"):self.WORKER.index("async function handleTriageReassign")]
        assert 'body.decision === "declined" && app.email' in body
        assert "not going to be able to find a place for it" in body
        assert "you are welcome\n         to apply again" in body or "welcome" in body
        assert "app.publicist_email ? [String(app.publicist_email)] : undefined" in body


class TestEveryAssemblyIsANewFile:
    """The CDN served the first assembly under the same key forever; three
    corrected endings, three times the old cut in Patrick's ears."""

    def test_the_edit_key_carries_a_stamp(self):
        asm = (V / "assemble_edit.py").read_text(encoding="utf-8")
        assert 'f"{run_id}_edit_{stamp}.mp3"' in asm
        assert 'f"{run_id}_edit.mp3"' not in asm

    def test_the_close_gets_a_breath(self):
        auto = (V / "auto_edit.py").read_text(encoding="utf-8")
        assert 'cuts += [{"gap": 1.4}, {"from": "narration:outro"}]' in auto


class TestTheGuestsLinksAreLinks:
    """Adrian Wolfberg's post showed "oicllc.org: https://www.oicllc.org" as
    plain text, twice. A URL on the site is a link, and a guest's own site
    is named by its domain."""

    def test_bare_urls_render_as_links(self):
        sys.path.insert(0, str(ROOT))
        from engine.blog import _md_inline
        out = _md_inline("oicllc.org: https://www.oicllc.org.")
        assert '<a href="https://www.oicllc.org"' in out and out.endswith("</a>.")
        # Existing links and citation pills are left alone.
        assert _md_inline("[s](https://x.y)").count("<a ") == 1
        assert _md_inline("Source: https://n.e/x").count("<a ") == 1

    def test_the_find_block_is_not_duplicated_in_the_post(self):
        pub = (V / "publish_episode.py").read_text(encoding="utf-8")
        assert 'body = re.sub(r"\\n+Find [^\\n]*:\\n' in pub

    def test_a_website_is_named_by_its_domain(self):
        from common import guest_links
        links = guest_links({"links": {"website": "https://www.gopippa.ai",
                                       "tiktok": "https://www.tiktok.com/@gopippa",
                                       "company_linkedin": "https://www.linkedin.com/company/gopippa"}})
        assert links[0] == {"label": "gopippa.ai", "url": "https://www.gopippa.ai"}
        assert {"label": "TikTok", "url": "https://www.tiktok.com/@gopippa"} in links
        assert {"label": "LinkedIn (company)", "url": "https://www.linkedin.com/company/gopippa"} in links


class TestTheGuestHearsTheMomentTheyAreOut:
    """John Capobianco's team asked twice where the episode would live and
    what to share, and the answer was typed by hand after the publish. Now
    the publish itself tells the guest: the post, where the feed lands, and
    every link they gave us shown back so they can see it took."""

    APP = {"name": "John Capobianco", "email": "john@example.com",
           "publicist_email": "pr@example.com",
           "links": {"website": "https://automateyournetwork.ca",
                     "linkedin": "https://www.linkedin.com/in/jc"}}
    PKG = {"guest_materials": "- [NetClaw on GitHub](https://github.com/x/netclaw)\n"
                              "- https://bit.ly/podcast-sdd-guide"}

    def test_the_note_carries_the_post_and_every_link(self):
        from publish_episode import published_email
        from shows import get_show
        show = get_show("age_of_ai")
        subject, body = published_email(show, self.APP, self.PKG, 5)
        assert "Ep5" in subject and "live" in subject
        assert "Hi John," in body
        assert 'href="https://nerranetwork.com/blog/age_of_ai/ep005.html"' in body
        for url in ("https://automateyournetwork.ca", "https://www.linkedin.com/in/jc",
                    "https://github.com/x/netclaw", "https://bit.ly/podcast-sdd-guide"):
            assert f'href="{url}"' in body, url
        assert "NetClaw on GitHub" in body
        assert show.apple_url in body and show.spotify_url in body

    def test_it_is_sent_after_the_rows_flip_and_copies_the_publicist(self):
        pub = (V / "publish_episode.py").read_text(encoding="utf-8")
        flip = pub.index('{"status": "published", "episode_number": episode_num}')
        assert pub.index("tell_the_guest(show, app, pkg, episode_num)") > flip
        assert 'cc = [str(app.get("publicist_email")' in pub
        assert "cc_operator=True, cc=cc" in pub

    def test_a_show_knows_where_its_episodes_live(self):
        from shows import get_show
        aoa = get_show("age_of_ai")
        assert aoa.post_url(5) == "https://nerranetwork.com/blog/age_of_ai/ep005.html"
        assert aoa.apple_url.startswith("https://podcasts.apple.com/")
        assert aoa.spotify_url.startswith("https://open.spotify.com/show/")
        nv = get_show("nerra_voices")
        assert nv.apple_url == "" and nv.spotify_url == ""

    def test_send_email_copies_without_duplicates(self, monkeypatch):
        import common
        sent = {}
        class R:
            status_code = 200
            def raise_for_status(self): pass
        def fake_post(url, headers=None, json=None, timeout=None):
            sent.update(json); return R()
        monkeypatch.setenv("RESEND_API_KEY", "x")
        monkeypatch.setattr(common.requests, "post", fake_post)
        common.send_email("guest@example.com", "s", "<p>b</p>", cc_operator=True,
                          cc=["pr@example.com", "", "guest@example.com",
                              common.OPERATOR_EMAIL.upper()])
        # Both of Patrick's addresses, then the publicist, no duplicates.
        assert sent["cc"] == [common.OPERATOR_EMAIL, *common.OPERATOR_CC,
                              "pr@example.com"]
        assert sent["from"] == "mira@nerranetwork.com"


class TestSheDoesNotEndTheInterviewInTheFirstThird:
    """Sept 20 2026, Meridan Zerner. Mira worked through the eight prepared
    questions, stacked the last three into one turn, asked the personal
    closing set eleven minutes in and told the guest to hang up at sixteen
    minutes of a forty-five minute interview. The time checks were correct
    and she ignored them: her prompt's closing trigger counts minutes
    REMAINING while the note counts minutes ELAPSED, and with Patrick out of
    the room there was nobody to fill the silence her list left behind."""

    SCENARIO = (ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js").read_text(encoding="utf-8")
    PROMPT = (V / "prompts" / "mira_system_prompt.txt").read_text(encoding="utf-8")

    def test_the_room_says_in_words_whether_she_may_close(self):
        block = self.SCENARIO[self.SCENARIO.index("function startTimeChecks"):
                              self.SCENARIO.index("const SIGN_OFF_RE")]
        assert "YOU ARE NOT NEAR THE END" in block
        assert "elapsed < closingOpensAtMin()" in block
        assert "You may begin the closing round" in block

    def test_the_closing_window_matches_the_prompts(self):
        import importlib, sys as _sys
        _sys.path.insert(0, str(V))
        fire = importlib.import_module("fire_interviews")
        js = self.SCENARIO[self.SCENARIO.index("function closingWindowMin"):]
        js = js[:js.index("}")]
        # Both sides compute max(4, min(15, round(planned / 3))).
        assert "Math.max(4, Math.min(15, Math.round(plannedMin() / 3)))" in js
        src = (V / "fire_interviews.py").read_text(encoding="utf-8")
        assert "lightning_at=max(4, min(15, round(minutes / 3)))" in src
        assert fire is not None

    def test_an_early_sign_off_is_caught_and_she_carries_on(self):
        assert "function catchEarlySignOff(text)" in self.SCENARIO
        assert 'if (who === "Mira")' in self.SCENARIO
        guard = self.SCENARIO[self.SCENARIO.index("function catchEarlySignOff"):]
        guard = guard[:guard.index("function startTimeChecks")] if "function startTimeChecks" in guard else guard
        assert "closingPermitted" in guard
        assert "the interview is NOT" in guard
        assert "earlySignOffs > 2" in guard      # rescue, never nag
        assert "responseCreate" in guard         # she says it, not us

    def test_the_prompt_waits_for_permission_and_does_no_arithmetic(self):
        flat = _flat(self.PROMPT)
        assert "it starts only when a [TIME CHECK] note has told you in words that you may begin it" in flat
        assert "Never before, however few prepared questions you have left" in flat
        assert "A note saying \"fifteen minutes elapsed\" is not the same as fifteen minutes remaining" in flat
        # The old trigger, which she read as an elapsed count, is gone.
        assert "minutes remaining, or sooner if you are short of time" not in flat

    def test_the_prompt_says_the_list_is_a_floor(self):
        flat = _flat(self.PROMPT)
        assert "THE LIST IS A FLOOR, NOT THE HOUR" in flat
        assert "Reaching the end of the list early is a sign you have been reading it" in flat
        assert "ONE QUESTION, THEN SILENCE" in flat


class TestTheIntroductionEarnsTheFirstThirtySeconds:
    """Sept 21 2026. Six episodes in, every produced introduction opened with
    the same thirty-five words of branding, then a CV, then "what surprised
    me most" in four of the six, and said Patrick was the human in the room —
    which stopped being true when he stopped sitting in. The prompt was
    dictating all three."""

    PROMPT = (V / "prompts" / "auto_edit.txt").read_text(encoding="utf-8")

    def test_it_opens_on_the_conversation(self):
        flat = _flat(self.PROMPT)
        assert "OPEN ON THE CONVERSATION, NOT ON US" in flat
        assert "the most concrete, most surprising thing in the hour" in flat
        assert "never more than two sentences on the show before you are back to the guest" in flat

    def test_the_worn_out_shapes_are_banned(self):
        flat = _flat(self.PROMPT)
        for dead in ("What surprised me most", "one moment stood out",
                     "one moment in the conversation caught me"):
            assert dead in flat, f"{dead} must be named as banned"
        assert "instead of telling us what it was" in flat

    def test_patrick_is_the_approver_not_a_presence_in_the_room(self):
        flat = _flat(self.PROMPT)
        assert "He is NOT in the room and does not host" in flat
        assert "listen to every episode and approve it before it reaches anyone" in flat
        assert "steer the show on what guests and listeners tell him" in flat
        assert "Never say he is here, in the room, with you or beside you" in flat
        # The old instruction that produced the wrong line is gone.
        assert "is the human in the room" not in flat

    def test_a_domain_is_never_invented(self):
        flat = _flat(self.PROMPT)
        assert "Say ONLY a domain that appears in the links above, character for character" in flat
        assert "meridanzernar.com" in flat
        assert "A wrong address in a published episode cannot be taken back" in flat


class TestAReadThatDropsASentenceIsSaidAgain:
    """Sept 21 2026, Meridan Zerner. A narration take came back without its
    last sentence — "He is not in this room, and nor is anyone else" — so the
    episode said "Patrick Novak created the Nerra Network and created what he
    does is listen to every episode". The take was 87% of its expected
    length, and the cut-off check only fails below 60%, so it shipped."""

    SRC = (V / "narrate.py").read_text(encoding="utf-8")

    def test_a_short_take_is_retried_before_it_is_accepted(self):
        assert "RETAKE_RATIO = 0.85" in self.SRC
        assert "RETAKES = 2" in self.SRC
        loop = self.SRC[self.SRC.index("for seq, para in enumerate(paragraphs(text))"):]
        loop = loop[:loop.index("if not parts:")]
        assert "for attempt in range(RETAKES + 1)" in loop
        assert "if ratio >= RETAKE_RATIO:" in loop
        assert "if ratio > best_ratio:" in loop       # keep the longest read
        assert "_check_not_truncated(best, para)" in loop

    def test_the_hard_floor_still_fails(self):
        assert "SHORT_TAKE_RATIO = 0.6" in self.SRC
        assert "raise RuntimeError(\n            f\"take was cut off:" in self.SRC

    def test_completeness_is_measured_after_trimming(self):
        loop = self.SRC[self.SRC.index("for seq, para in enumerate(paragraphs(text))"):]
        loop = loop[:loop.index("if not parts:")]
        assert loop.index("_trim(part)") < loop.index("_take_shortfall(trimmed, para)")


class TestAPublishThatCommitsNothingIsNotSilent:
    """Sept 21 2026, Matt Davis. The publish ran perfectly on the runner —
    RSS entry, episode post, five regenerated blog pages — and committed
    none of it. safe-commit-push passes every path to one `git add
    --pathspec-from-file`, and a single pathspec that matches nothing makes
    that command fatal and stage NOTHING; `|| true` swallowed the error. The
    list had just gained nerra_voices_podcast.rss, which cannot exist until
    Nerra Voices publishes its first episode. Supabase said Ep6 was
    published and nerranetwork.com had never heard of it."""

    ACTION = (ROOT / ".github" / "actions" / "safe-commit-push" / "action.yml").read_text(encoding="utf-8")
    PUBLISH_WF = (ROOT / ".github" / "workflows" / "nerra_voices_publish.yml").read_text(encoding="utf-8")

    def test_one_missing_path_cannot_take_the_others_down(self):
        assert "--pathspec-from-file" not in self.ACTION
        assert 'if git add -- "$p" 2>/dev/null; then' in self.ACTION
        assert "done < /tmp/paths-clean.txt" in self.ACTION

    def test_a_path_that_matches_nothing_says_so(self):
        assert "nothing to add at '$p' — skipped" in self.ACTION
        assert "none of the requested paths matched anything" in self.ACTION

    def test_staging_nothing_is_a_warning_not_a_shrug(self):
        assert "::warning::safe-commit-push: nothing staged" in self.ACTION

    def test_the_first_line_indent_is_stripped(self):
        # The heredoc keeps the workflow's indentation on the first
        # interpolated line, which would make that one path match nothing.
        assert "sed 's/^[[:space:]]*//' /tmp/paths-to-add.txt" in self.ACTION

    def test_publish_can_actually_send_the_guest_their_episode(self):
        # publish_one emails the guest now; this job had never needed mail.
        assert "RESEND_API_KEY: ${{ secrets.RESEND_API_KEY }}" in self.PUBLISH_WF
        assert "POSTMARK_TOKEN: ${{ secrets.POSTMARK_TOKEN }}" in self.PUBLISH_WF


class TestTheLoopClosesItself:
    """Sept 21 2026. Eight lessons had been sitting as proposals — four from
    Meridan Zerner, four from Sameer Ranjan — while the same faults recurred
    in both episodes. A queue nobody drains is not a learning loop. The
    grading pass now adopts what it decides and retires what the show has
    outgrown, and Patrick reads the decision instead of gating it."""

    LEARNING = (V / "learning.py").read_text(encoding="utf-8")
    RETRO = (V / "prompts" / "editorial_passes" / "09_interview_retro.txt").read_text(encoding="utf-8")
    POST = (V / "post_interview.py").read_text(encoding="utf-8")

    def test_lessons_go_in_live_and_say_who_decided(self):
        body = _pyfn("adopt_lessons", self.LEARNING)
        assert '"status": "active"' in body
        assert '"decided_by": "mira"' in body
        assert "adopted automatically" in body

    def test_it_will_not_carry_the_same_lesson_twice(self):
        import importlib, sys as _sys
        _sys.path.insert(0, str(V))
        L = importlib.import_module("learning")
        assert L._already_says_it(
            "Ask one question at a time and stop talking.",
            ["Ask one question at a time and stop speaking after each one."])
        # ... and does not collapse two genuinely different instructions.
        assert not L._already_says_it(
            "Wait for the guest to finish their sentence before the next question.",
            ["Ask one question at a time and stop speaking after each one."])

    def test_the_prompt_is_shown_what_she_already_carries(self):
        assert "{{active_lessons}}" in self.RETRO
        assert "do not restate it" in _flat(self.RETRO)
        assert "lessons_for_prompt(show.slug)" in self.POST

    def test_a_dozen_instructions_stay_a_dozen(self):
        body = _pyfn("adopt_lessons", self.LEARNING)
        assert "MAX_ACTIVE_LESSONS - (len(current) + len(adopted))" in body
        assert "made room for a newer lesson" in body
        assert "RETIRE the instructions that have done their job" in self.RETRO

    def test_the_guests_own_verdict_is_fed_back_in(self):
        assert "{{guest_feedback}}" in self.RETRO
        assert "guest_feedback(cleaned, _guest_label(app))" in self.POST
        body = _pyfn("guest_feedback", self.LEARNING)
        assert "change one thing about how I" in self.LEARNING
        assert "Asked:" in body and "They said:" in body

    def test_every_hour_gets_a_comparable_score(self):
        body = _pyfn("save_grade", self.LEARNING)
        for dimension in ("listening", "questions", "pacing", "turn_taking", "warmth"):
            assert f'score("{dimension}")' in body
        assert "min(10.0, max(0.0, value))" in body          # 0-10, clamped
        assert "Do not drift upward to be kind" in self.RETRO

    def test_grading_never_costs_an_episode(self):
        block = self.POST[self.POST.index("# Learning loop"):]
        block = block[:block.index('if package.get("topical_show_fits")')]
        assert "except Exception:" in block
        for fn in ("adopt_lessons", "retire_lessons", "save_grade"):
            assert "except Exception:" in _pyfn(fn, self.LEARNING), fn


class TestHerOwnVoiceIsNotPutInTheGuestsMouth:
    """Sept 21 2026, Sameer Ranjan. The studio records the guest's microphone
    with echo cancellation deliberately off, for fidelity, so a guest without
    headphones records Mira out of their own speakers. Whatever the bleed gate
    left was transcribed as HIM: "I'm the AI age of 8", "Nothing goes live",
    "Where are you calling from?". That transcript is what the guest approves,
    what the episode page publishes, and what the producer's pass reads — and
    it had already produced a lesson about Mira repeating her questions, from
    her own echo."""

    POST = (V / "post_interview.py").read_text(encoding="utf-8")
    RETRO = (V / "prompts" / "editorial_passes" / "09_interview_retro.txt").read_text(encoding="utf-8")
    BLEED = (V / "audio" / "bleed.py").read_text(encoding="utf-8")

    def _strip(self):
        import importlib, sys as _sys, os as _os
        _sys.path.insert(0, str(V))
        _os.environ.setdefault("SUPABASE_URL", "http://x")
        _os.environ.setdefault("SUPABASE_SERVICE_KEY", "x")
        return importlib.import_module("post_interview").strip_echo_lines

    def test_a_garbled_fragment_of_her_line_is_dropped(self):
        strip = self._strip()
        out, dropped = strip(
            "[00:24] Sameer: I'm the AI age of 8.\n"
            "[00:26] Mira: I'm the AI who hosts the Age of AI, the first podcast.\n"
            "[00:41] Sameer: Nothing goes live.\n"
            "[00:44] Mira: Nothing goes live.\n"
            "[00:54] Sameer: Where are you calling from?\n"
            "[00:56] Mira: Where are you calling from today?\n", "Mira")
        assert dropped == 3
        assert "Sameer" not in out

    def test_a_guest_leaning_on_the_question_survives(self):
        strip = self._strip()
        out, dropped = strip(
            "[13:00] Mira: Where do you draw the line on what you will recommend?\n"
            "[13:06] Vincent: I draw the line at anything I cannot show evidence for.\n"
            "[33:41] Mira: What's the one bet you're making that you cannot prove yet?\n"
            "[33:55] Sameer: That I have not proved it yet but I wish to prove it soon.\n",
            "Mira")
        assert dropped == 0
        assert "Vincent" in out and "Sameer" in out

    def test_a_short_agreement_is_always_the_guests(self):
        strip = self._strip()
        _, dropped = strip("[01:00] Mira: Exactly.\n[01:02] Sameer: Exactly.\n", "Mira")
        assert dropped == 0

    def test_it_runs_before_anyone_reads_the_transcript(self):
        # The editorial passes, the guest's review copy and the grading pass
        # must all see the cleaned version, so the strip happens where the
        # transcript is first assembled.
        i_strip = self.POST.index('strip_echo_lines(transcript, "Mira")')
        assert i_strip < self.POST.index("package = run_editorial_passes(")
        assert i_strip < self.POST.index("09_interview_retro.txt")

    def test_the_grader_is_warned_not_to_trust_it_either(self):
        flat = _flat(self.RETRO)
        assert "BE SUSPICIOUS OF THE TRANSCRIPT ITSELF" in flat
        assert "it is her voice in their microphone" in flat
        assert "never conclude she repeated herself from it" in flat

    def test_a_loud_echo_is_caught_by_prediction_not_by_level(self):
        assert "def echo_fit(" in self.BLEED
        assert "ECHO_MARGIN_DB" in self.BLEED
        # The level test giving up must not end the attempt.
        assert "muting by prediction alone" in self.BLEED
        # And the speaker's own ordinary volume is always safe.
        assert "np.minimum(predicted + ECHO_MARGIN_DB, own_db)" in self.BLEED


class TestTheStudioChecksForHeadphonesRatherThanAskingNicely:
    """Three of the last four guests recorded without headphones. Every email
    already said to wear them, so saying it again was not the fix: the studio
    now plays a tone through the speakers before the join and listens for it
    on the microphone, and tells the guest what it heard."""

    STUDIO = (ROOT / "age-of-ai-studio.html").read_text(encoding="utf-8")
    WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")
    FIRE = (V / "fire_interviews.py").read_text(encoding="utf-8")
    BOOKING = (ROOT / "templates" / "email" / "voices_booking_confirmation.j2").read_text(encoding="utf-8")

    def test_it_measures_rather_than_asks(self):
        assert "var ECHO_HZ = 1180;" in self.STUDIO
        assert "getFloatFrequencyData" in self.STUDIO
        # A quiet baseline, then the tone, then the difference in decibels.
        assert "measure(400, function (before)" in self.STUDIO
        assert "var rise = during - before;" in self.STUDIO

    def test_it_says_what_it_heard_in_plain_words(self):
        assert "Your microphone can hear your speakers" in self.STUDIO
        assert "your microphone hears only you" in self.STUDIO
        assert "We can faintly hear your speakers" in self.STUDIO

    def test_it_never_locks_the_guest_out(self):
        """A guest who cannot find headphones must still be able to record."""
        join = self.STUDIO[self.STUDIO.index('getElementById("joinBtn")'):]
        join = join[:join.index("function join(")] if "function join(" in join else join[:4000]
        assert "Never block the" in join
        assert "costs us the episode" in join
        assert "return" not in join.split("echoCheck();")[0].split("if (!isHost && !echoChecked)")[-1]

    def test_the_verdict_reaches_the_operator(self):
        assert 'path === "/voices/studio-echo"' in self.WORKER
        assert "async function handleStudioEcho(" in self.WORKER
        body = self.WORKER[self.WORKER.index("async function handleStudioEcho("):]
        body = body[:body.index("async function handleStudioState(")]
        assert "echo_check: record" in body
        assert "is on speakers" in body
        assert '"clean", "borderline", "speakers", "unknown"' in body

    def test_the_emails_say_what_goes_wrong_not_just_what_to_do(self):
        # "Headphones help a lot" is advice nobody acted on.
        assert "headphones help a lot" not in self.FIRE
        assert "her questions end up in the" in self.FIRE
        assert "as though you had said" in self.BOOKING
        assert "wearing headphones or" in self.BOOKING


class TestAnEpisodeRunsToTheClose:
    """Sept 22 2026. Three episodes ended mid-sentence: Sheldon Poon twice and
    Meridan Zerner, whose closing thought lost "It is complex." Her last line
    ran 15:50 to 16:04, fourteen seconds, and the word-count estimate put it at
    nine — and that estimate was being used as a CAP on the cut. Patrick's
    rule: an episode runs to the close of the conversation unless he or the
    guest asks otherwise, or there is a reason worth stating."""

    SRC = (V / "auto_edit.py").read_text(encoding="utf-8")

    def _mod(self):
        import importlib, sys as _sys, os as _os
        _sys.path.insert(0, str(V))
        _os.environ.setdefault("SUPABASE_URL", "http://x")
        _os.environ.setdefault("SUPABASE_SERVICE_KEY", "x")
        return importlib.import_module("auto_edit")

    MERIDAN = (
        "[15:45] Meridan: and neighbors in your life to look at your spiritual\n"
        "[15:50] Meridan: well-being. These are all equally weighted and make up this "
        "recipe that we all deserve. It is complex.\n"
        "[16:04] Mira: Thank you, Meridan. That's the end of the recording.\n")

    def test_the_guess_can_only_extend_never_shorten(self):
        m = self._mod()
        # The shipped cut was 959.3s. The next speaker starts at 964.
        assert m._after_the_line(self.MERIDAN, 950.0, 974) == 963.75
        assert "estimate can only ever extend the cut, never shorten it" in _flat(self.SRC)

    def test_the_close_is_the_default_not_whatever_was_pointed_at(self):
        m = self._mod()
        end, note = m._where_it_closes(self.MERIDAN, 950.0, 974, "her final line")
        assert end > 959.3, "must reach past the cut that lost her last words"
        assert note == "", "running to the close is not an exception worth noting"

    def test_nothing_after_them_means_the_tape_is_the_end(self):
        m = self._mod()
        solo = "[10:00] Meridan: and that is really where I would leave it.\n"
        assert m._after_the_line(solo, 600.0, 640.0) == 640.0

    def test_a_deliberate_early_finish_is_allowed_and_declared(self):
        m = self._mod()
        end, note = m._where_it_closes(self.MERIDAN, 300.0, 974, "the line dropped")
        assert end < 400, "an early finish for a stated reason still stands"
        assert "ENDS EARLY" in note and "the line dropped" in note
        # ...and it reaches the gate-1 email rather than the guest's ears.
        assert "+ ended_early" in self.SRC and '"note": rationale' in self.SRC


class TestTheEndIsMeasuredNotGuessed:
    """Sept 22 2026, Meridan Zerner, twice in one episode. The cut ended at
    959.3s and took "It is complex." off her closing thought, because her line
    was stamped nine seconds long and ran fourteen. Correcting it to the next
    speaker's stamp then caught the first three quarters of a second of Mira's
    live "Thank you, Meridan", because that stamp was itself nearly a second
    late. Transcript timestamps are approximate at both edges; the audio is
    not. Measured from her tape: last word 961.8, Mira 963.1, seam 962.5."""

    SRC = (V / "assemble_edit.py").read_text(encoding="utf-8")

    def test_the_last_stretch_is_trimmed_to_the_last_word(self):
        assert "def _last_silence_before(" in self.SRC
        assert "silencedetect=n=-45dB:d=0.35" in self.SRC
        assert "_end_on_the_last_word(cut, src)" in self.SRC

    def test_only_the_final_stretch_of_conversation(self):
        # A seam in the middle of an episode is nobody's business; the end is.
        assert "last_conversation = max(" in self.SRC
        assert 'conversation = ("run:", "track:", "mix:")' in self.SRC
        assert "if i == last_conversation and ref.startswith(conversation)" in self.SRC

    def test_the_clean_fold_is_measured_the_same_way(self):
        # With the speakers on separate tracks, no single one of them can say
        # whether everyone has stopped: the guest's track is silent through
        # every question. The probe gets all of them and folds them first.
        assert "_end_on_the_last_word(cut, [src for _role, src in srcs])" in self.SRC
        body = _pyfn("_last_silence_before", self.SRC)
        assert "srcs = [src] if isinstance(src, (str, Path)) else list(src)" in body
        assert "amix=inputs={len(srcs)}:duration=longest:normalize=0," in body

    def test_it_keeps_a_breath_after_the_last_word(self):
        assert "END_KEEP_SEC = 0.5" in self.SRC
        assert "return at + END_KEEP_SEC" in self.SRC

    def test_a_failed_probe_leaves_the_edit_alone(self):
        body = _pyfn("_last_silence_before", self.SRC)
        assert "except Exception" in body and "return None" in body
        guard = _pyfn("_end_on_the_last_word", self.SRC)
        assert "if found is None" in guard

    def test_it_never_reaches_outside_its_window(self):
        body = _pyfn("_last_silence_before", self.SRC)
        assert "if not (lo < at < end):" in body
        assert "END_SEARCH_SEC = 6.0" in self.SRC
