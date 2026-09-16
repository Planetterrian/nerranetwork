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
        assert "free of advertising and" in block and "free of positions" in block
        assert "hand a microphone to people who would not otherwise" in block
        assert "why this show exists rather" in PROMPT

    def test_she_is_told_what_her_contribution_is(self):
        assert "remember every conversation this show has" in PROMPT


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


class TestTheCutterLearnedFromItsFirstRun:
    """Sept 15 2026, cutting Vincent Rylan's tape unsupervised. It found a
    fifty-second echo-troubleshooting loop at 9:49 that the human edit had
    missed entirely, and it started the episode at 3:08 — past the football
    and the writing-process questions, straight to the book."""

    def test_the_warm_up_is_protected(self):
        assert "the warm-up is not throat-clearing" in AUTO_PROMPT
        assert "born with disappointment in my\nheart" in AUTO_PROMPT
        assert "Cut\nINTO the warm-up, not past it" in AUTO_PROMPT
        assert "you have started too late" in AUTO_PROMPT

    def test_technical_loops_are_named_as_the_common_case(self):
        assert "a mute-and-unmute loop" in AUTO_PROMPT
        assert "easy to miss" in AUTO_PROMPT
        assert "whether anything is being SAID" in AUTO_PROMPT


class TestWhoMadeHerAndWhoSheIsFor:
    def test_patrick_made_the_network_and_made_her(self):
        assert "created the Nerra\nNetwork, and he created you" in PROMPT
        assert "give a voice to more people than a human\nschedule allows" in PROMPT
        assert "should\nnot need a producer, a following or a connection" in PROMPT

    def test_her_origin_is_a_fact_not_a_story(self):
        assert "as a fact about yourself rather\nthan an origin story" in PROMPT

    def test_she_invites_people_to_apply(self):
        assert "INVITE PEOPLE IN" in PROMPT
        assert "nerranetwork dot com" in PROMPT
        assert "apply to be a guest" in PROMPT
        assert "At the close, and only there" in PROMPT
        assert "It is not a plug" in PROMPT

    def test_the_produced_close_carries_it_too(self):
        assert "nerranetwork dot com" in AUTO_PROMPT
        assert "apply to be a guest" in AUTO_PROMPT.replace("\n  ", " ")
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
        assert self.ASSEMBLE.count('cut.get("gaps", True)') == 2


class TestNoLaughter:
    """Sept 15 2026. The tags do work through the voice agent — a test take
    proved it — and then Patrick listened to one and said the laugh sounds
    fake. He is right, and the reason matters: a laugh typed into a script is
    a performance of amusement by something that was not amused. A show
    hosted by an AI cannot afford to pretend."""

    NARRATE = (V / "narrate.py").read_text(encoding="utf-8")
    NARRATION_PROMPT = (V / "prompts" / "mira_narration.txt").read_text(encoding="utf-8")

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
            assert "shape\nhow real words are delivered rather than inventing a feeling" in text

    def test_she_does_not_laugh_in_the_room_either(self):
        assert "REACT, BUT DO NOT PERFORM" in PROMPT
        assert "Do NOT laugh" in PROMPT
        assert "sounds manufactured" in PROMPT
        assert "REACT LIKE A PERSON, OUT LOUD" not in PROMPT

    def test_warmth_still_has_somewhere_to_go(self):
        assert "say so in words" in PROMPT
        assert "what you\n  notice and what you ask next" in PROMPT

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
        assert "worse than the\ndead air it removed" in AUTO_PROMPT

    def test_corrections_are_protected_too(self):
        assert "the thing being corrected has to still be in the\nepisode" in AUTO_PROMPT

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

    PROMPT = (V / "prompts" / "mira_system_prompt.txt").read_text(encoding="utf-8")
    EDITOR = (V / "prompts" / "auto_edit.txt").read_text(encoding="utf-8")

    def test_nothing_may_sound_like_an_ending_until_it_is_one(self):
        assert "NEVER SIGNAL THE END BEFORE IT IS THE END" in self.PROMPT
        assert "Summing up is an ending move" in self.PROMPT

    def test_she_asks_what_they_came_to_say(self):
        assert "COVER THEIR GROUND, NOT JUST YOURS" in self.PROMPT
        assert "still in their pocket" in self.PROMPT

    def test_she_follows_the_interesting_thing_down(self):
        assert "DRILL IN." in self.PROMPT
        assert "Three\nquestions deep into one real thing" in self.PROMPT

    def test_the_personal_questions_are_not_optional_or_only_at_the_end(self):
        assert "ASK ABOUT THE PERSON, NOT ONLY THE SUBJECT" in self.PROMPT
        assert "spread through the hour" in self.PROMPT

    def test_the_personal_rule_still_defers_to_the_application(self):
        block = self.PROMPT[self.PROMPT.index("ASK ABOUT THE PERSON"):]
        block = block[:block.index("THE CLOSING ROUND")]
        assert "agreed to on their\napplication" in block

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
        assert "could not be placed in the room" in body
        assert "if i:\n                    continue" in body

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
        assert 'expected=expected_delay("host", i)' in body

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
