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
