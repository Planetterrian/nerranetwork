"""Oct 21 2026 (review of every interview, §7.2 and §7.3): Mira's prompt is a
host's brief, not a rulebook.

The compiled prompt had reached 43,047 characters for one guest with 75
prohibitions, 17 dated incident narratives and 36 quoted specimen lines; the
network's own rule for prompts (de-seed by shape, never with a quotable
example) was violated throughout, and listing seventy instances of one
opener moved the tic to a one-word echo. These guards fail CI if the prompt
drifts back: size, no quoted specimens, no dated incidents, five positive
lessons at most, no relapse recap, retired shapes without instances, the
fact-check tool off by default, and one subject-matched callback offered
in the co-host's shape.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V = ROOT / "pipelines" / "voices"
sys.path.insert(0, str(V))
PROMPTS = V / "prompts"
PROMPT = (PROMPTS / "mira_system_prompt.txt").read_text(encoding="utf-8")
CLOSING = (PROMPTS / "mira_closing_session.txt").read_text(encoding="utf-8")
COHOST = (PROMPTS / "cohost_craft.txt").read_text(encoding="utf-8")
BRIEF = (PROMPTS / "research_brief.txt").read_text(encoding="utf-8")
QGEN = (PROMPTS / "question_generation.txt").read_text(encoding="utf-8")
FIRE = (V / "fire_interviews.py").read_text(encoding="utf-8")
NOTES = (ROOT / "docs" / "mira_craft_notes.md").read_text(encoding="utf-8")

PROMPT_WORDS_MAX = 1600
COMPILED_CHARS_MAX = 12000          # the ordinary room: Mira alone
COMPILED_CHARS_MAX_COHOST = 16000   # with the co-host block and craft

# The only things that may stand inside double quotes in a prompt: the words
# the room's sign-off catcher listens for (she must say them), and tokens.
QUOTE_ALLOWLIST = ("that's the end of the recording", "you can hang up now")
MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December",
          "Jan", "Feb", "Mar", "Apr", "Jun", "Jul", "Aug", "Sept", "Sep",
          "Oct", "Nov", "Dec")
DATE_RE = re.compile(r"\b(" + "|".join(MONTHS) + r")\.? \d{1,2}(,? \d{4})?\b")
YEAR_RE = re.compile(r"\b20\d\d\b")
# Guests whose incidents used to be narrated in the prompt. Any of these
# names in a prompt means a dated story has crept back.
PAST_GUESTS = ("Piper", "Cory", "Chad Law", "Jason Fishman", "Thor", "Roddy",
               "Scott Pulcini", "Sameer", "Viktor", "Jon Cheney", "Meridan",
               "Dan Perra", "Capobianco", "Vincent", "Wolfberg", "Zerner")


def _flat(text: str) -> str:
    return " ".join(text.split())


def _quoted_specimens(text: str) -> list:
    out = []
    for m in re.finditer(r'"([^"\n]{2,}?)"', text):
        inner = m.group(1).strip()
        if inner.lower() in QUOTE_ALLOWLIST or inner.startswith("{{"):
            continue
        if len(inner.split()) >= 4:
            out.append(inner)
    return out


class TestThePromptIsABrief:
    def test_under_the_word_budget(self):
        assert len(PROMPT.split()) < PROMPT_WORDS_MAX

    def test_no_quoted_specimen_line(self):
        for text, name in ((PROMPT, "system"), (CLOSING, "closing"), (COHOST, "cohost")):
            assert _quoted_specimens(text) == [], (name, _quoted_specimens(text))

    def test_no_dated_incident(self):
        for text, name in ((PROMPT, "system"), (CLOSING, "closing"), (COHOST, "cohost")):
            assert not DATE_RE.search(text), (name, DATE_RE.search(text).group(0))
            assert not YEAR_RE.search(text), name
            for guest in PAST_GUESTS:
                assert guest not in text, (name, guest)

    def test_the_incidents_are_kept_for_people(self):
        for guest in ("Piper Martz", "Cory O'Daniel", "Chad Law", "Viktor Popovic",
                      "Jon Cheney", "Sameer Ranjan"):
            assert guest in NOTES, guest
        assert "de-seed by shape" in NOTES

    def test_the_craft_is_stated_in_the_order_a_conversation_runs(self):
        order = ("HOW TO OPEN", "THEIR SUBJECT, FAST", "HOW TO LISTEN",
                 "IT IS THEIR HOUR", "HOW TO REACT", "RESEARCH IS QUIET",
                 "HOW TO CLOSE", "HOW IT ENDS", "## Guardrails")
        positions = [PROMPT.index(h) for h in order]
        assert positions == sorted(positions)

    def test_what_she_never_does_is_at_most_eight_lines_without_examples(self):
        block = PROMPT[PROMPT.index("## CRITICAL INSTRUCTIONS"):]
        bullets = [line for line in block.splitlines() if line.startswith("- ")]
        assert 1 <= len(bullets) <= 8
        assert '"' not in block

    def test_the_room_runs_the_closing_round(self):
        flat = _flat(PROMPT)
        assert "The closing round is the room's to run" in flat
        assert "hands you each closing question in turn" in flat
        assert "Ask each question you are handed in full as its own turn" in flat

    def test_every_placeholder_the_compile_step_fills_is_still_there(self):
        for token in ("{{show_name}}", "{{show_premise}}", "{{guest_name}}",
                      "{{guest_details}}", "{{guest_address_rule}}", "{{guest_address}}",
                      "{{cohost_name}}", "{{episode_thesis}}", "{{guest_brief}}",
                      "{{likely_questions}}", "{{guest_agenda}}", "{{guest_notes}}",
                      "{{guest_shape}}", "{{carry_the_show}}", "{{lessons}}",
                      "{{cohost_block}}", "{{cohost_intro_step}}", "{{cohost_craft}}",
                      "{{planned_minutes}}", "{{lightning_at}}", "{{closing_question}}",
                      "{{opening_line}}"):
            assert token in PROMPT, token

    def test_the_rules_the_room_cannot_enforce_are_still_stated(self):
        flat = _flat(PROMPT)
        for rule in ("stop mid-word", "A personal story is never checked",
                     "never say you cannot verify, confirm or find something",
                     "never perform a laugh, a sigh or a breath",
                     "The subject the guest came for gets the hour",
                     "never with a grade of the answer, never with their last words echoed back"):
            assert rule in flat, rule


class TestTheCompiledPromptIsShort:
    def _compile(self, monkeypatch, host_mode=False):
        import common
        import learning
        import fire_interviews as fi
        monkeypatch.setattr(common, "sb_select", lambda *a, **k: [])
        monkeypatch.setattr(learning, "sb_select", lambda *a, **k: [])
        return fi.compile_mira_prompt(
            {"episode_thesis": "THESIS-X", "host_mode": host_mode},
            {"name": "Jane Doe", "title": "Teacher", "organization": "PS 42",
             "email": "jane@example.com",
             "guest_agenda": {"topic": "Classroom robotics",
                              "points": ["Why the budget matters", "What broke"]},
             "guest_notes": [{"text": "Please ask about the grant."}]},
            {"bio_research": "BRIEF-X " * 60,
             "likely_questions": [{"question": f"Q-{i}?"} for i in range(8)]},
        )

    def test_under_twelve_thousand_characters_with_every_block_filled(self, monkeypatch):
        prompt = self._compile(monkeypatch)
        assert "{{" not in prompt
        assert "Classroom robotics" in prompt and "Please ask about the grant" in prompt
        assert len(prompt) < COMPILED_CHARS_MAX, len(prompt)

    def test_with_the_cohost_blocks_it_is_still_a_brief(self, monkeypatch):
        prompt = self._compile(monkeypatch, host_mode=True)
        assert "LEARN FROM YOUR CO-HOST" in prompt
        assert len(prompt) < COMPILED_CHARS_MAX_COHOST, len(prompt)

    def test_no_relapse_recap_is_appended(self):
        import learning
        assert learning.relapse_recap("age_of_ai") == ""
        assert "+ relapse_recap(" not in FIRE
        assert "PROMPT_MAX_CHARS = 16000" in FIRE

    def test_a_hello_session_compiles_its_own_prompt(self, monkeypatch):
        import fire_interviews as fi
        monkeypatch.setattr(fi, "compile_mira_prompt", lambda iv, app, brief: "INTERVIEW")
        monkeypatch.setattr(fi, "compile_closing_prompt", lambda iv, app: "CLOSING")
        assert fi.compile_prompt_for({"session_kind": "closing"}, {}, None) == "CLOSING"
        assert fi.compile_prompt_for({}, {}, {}) == "INTERVIEW"
        # With or without the hello module, a hello session never falls over.
        out = fi.compile_prompt_for({"session_kind": "hello"}, {"name": "J"}, None)
        assert isinstance(out, str) and out
        briefs = (V / "generate_briefs.py").read_text(encoding="utf-8")
        assert 'in ("closing", "hello")' in briefs
        wf = (ROOT / ".github" / "workflows" / "nerra_voices_fire_interview.yml").read_text(encoding="utf-8")
        assert "python pipelines/voices/hello_sessions.py invites" in wf
        assert wf.index("hello_sessions.py invites") < wf.index("python pipelines/voices/fire_interviews.py")


class TestLessonsAreFiveAndPositive:
    def _learning(self, monkeypatch, rows_by_query):
        import learning
        monkeypatch.setattr(learning, "sb_select",
                            lambda table, q="": [r for k, rs in rows_by_query.items()
                                                 if k in q for r in rs])
        return learning

    def test_at_most_five_lines_show_first(self, monkeypatch):
        L = self._learning(monkeypatch, {
            "show=eq.network": [{"id": f"n{i}", "show": "network", "lesson": f"Network note {i}."}
                                for i in range(6)],
            "show=eq.age_of_ai": [{"id": f"s{i}", "show": "age_of_ai", "lesson": f"Show note {i}."}
                                  for i in range(3)],
        })
        block = L.lessons_block("age_of_ai")
        lines = [line for line in block.splitlines() if line.startswith("- ")]
        assert len(lines) == L.PROMPT_LESSONS_MAX == 5
        assert lines[:3] == ["- Show note 0.", "- Show note 1.", "- Show note 2."]
        assert "WHAT THIS SHOW HAS TAUGHT YOU" in block
        assert "outrank" not in block and "corrections" not in block

    def test_a_lesson_that_quotes_a_line_never_reaches_the_prompt(self, monkeypatch):
        # Oct 21 2026: two hand-edited lessons quoted the lines they banned
        # ("Whatever.", "That's a [adjective] [noun]") on the eve of a room.
        # A quoted line is a specimen; the next unquoted lesson takes its slot.
        L = self._learning(monkeypatch, {
            "show=eq.network": [
                {"id": "n0", "lesson": "Never grade an answer: no 'Fair enough', no summary."},
                {"id": "n1", "lesson": "Do not open by repeating the guest's last words."},
                {"id": "n2", "lesson": "Never say \u201cgreat question\u201d."},
                {"id": "n3", "lesson": "Ask for one concrete example when an answer is vague."},
            ],
            "show=eq.age_of_ai": [
                {"id": "s0", "lesson": "Never insert a lone word such as 'Whatever.'"},
                {"id": "s1", "lesson": "Probe the unproven bet the guest volunteers."},
            ],
        })
        block = L.lessons_block("age_of_ai")
        lines = [line for line in block.splitlines() if line.startswith("- ")]
        assert lines == ["- Probe the unproven bet the guest volunteers.",
                         "- Do not open by repeating the guest's last words.",
                         "- Ask for one concrete example when an answer is vague."]
        assert not any(L.quotes_a_specimen(line) for line in lines)

    def test_an_apostrophe_is_not_a_quote(self):
        import learning
        for text in ("Move from a guest's point to the next question.",
                     "Don't re-ask a question they've answered.",
                     "A previous guest's words go to this guest's own subject."):
            assert not learning.quotes_a_specimen(text), text

    def test_listening_never_licenses_the_echo(self):
        # The HOW TO LISTEN beat once offered "their own word handed back",
        # the phrase that taught the echo the prompt's last rule forbids.
        assert "own word handed back" not in _flat(PROMPT)
        assert "what struck you, or what it changes" in _flat(PROMPT)

    def test_the_show_cap_is_six(self):
        import learning
        assert learning.MAX_SHOW_LESSONS == 6
        assert learning.lesson_cap("age_of_ai") == 6

    def test_retired_shapes_carry_no_instance(self, monkeypatch):
        import learning
        monkeypatch.setattr(learning, "sb_select", lambda *a, **k: [
            {"phrase": "That's a crisp answer"}, {"phrase": "That's a sharp distinction"},
            {"phrase": "Fair enough"}, {"phrase": "That's the end of the recording"}])
        block = learning.variety_block("age_of_ai")
        assert "REPLY SHAPES RETIRED" in block
        assert "grading the answer with an adjective" in block and "(2 times" in block
        for phrase in ("crisp answer", "sharp distinction", "Fair enough", "end of the recording"):
            assert phrase not in block, phrase
        assert '"' not in block

    def test_a_single_phrase_with_no_shape_renders_nothing(self, monkeypatch):
        import learning
        monkeypatch.setattr(learning, "sb_select", lambda *a, **k: [{"phrase": "Fair enough"}])
        assert learning.variety_block("age_of_ai") == ""


class TestResearchMakesHerCuriousNotSuspicious:
    def test_fact_check_is_off_by_default(self):
        import fire_interviews as fi
        names = [t["name"] for t in fi.MIRA_TOOLS]
        assert "fact_check_claim" not in names
        assert "fact_check_claim" not in [t["name"] for t in fi.mira_tools({}, {})]
        assert "fact_check_claim" in [t["name"] for t in fi.mira_tools({"fact_check": True}, {})]
        assert "verif" not in fi.FACT_CHECK_TOOL["description"].lower()
        assert '"tools": mira_tools(interview, app),' in FIRE

    def test_the_brief_asks_for_curiosity_and_is_capped(self):
        flat = _flat(BRIEF)
        assert "350 words" in flat
        assert "Three things you would be glad to be asked about" in flat
        assert "Two things only this person can tell us" in flat
        assert "mismatch" not in flat and "unverified" not in flat

    def test_the_questions_get_the_agenda_and_a_subject_tension(self):
        assert "{{guest_agenda}}" in QGEN and "{{guest_notes}}" in QGEN
        flat = _flat(QGEN)
        assert "IN THE SUBJECT" in flat
        assert "never from the guest's biography" in flat
        briefs = (V / "generate_briefs.py").read_text(encoding="utf-8")
        assert "guest_agenda=guest_agenda_block(app)" in briefs
        assert "guest_notes=guest_notes_block(app)" in briefs

    def test_the_prep_email_says_what_she_is_curious_about(self):
        import generate_briefs as gb
        lines = gb.curious_about([
            {"question": "Q1?", "why": "How the budget was actually decided"},
            {"question": "Q2?", "why": "what broke on the first deployment."},
            {"question": "Q3?", "why": "x", "curious": "how you know a team is ready"},
            "Q4?"])
        assert len(lines) == 3
        assert lines[0] == "I'm curious about how the budget was actually decided."
        assert lines[1] == "I'm curious about what broke on the first deployment."
        assert lines[2] == "I'm curious about how you know a team is ready."
        tpl = (ROOT / "templates" / "email" / "voices_prep_brief.j2").read_text(encoding="utf-8")
        assert "What I'm curious about" in tpl and "curious_about" in tpl
        assert "curious_about=curious_about(" in (V / "generate_briefs.py").read_text(encoding="utf-8")

    def test_a_note_about_the_guest_is_never_sent_to_the_guest(self):
        # Oct 27 2026, Glenn Broder's prep email.
        import generate_briefs as gb
        lines = gb.curious_about([
            {"question": "Q1?", "why": "Grounds the opening in his actual teaching sequence and gives a concrete entry point"},
            {"question": "Q2?", "why": "Directly surfaces the core distinction the guest wants explored"},
            {"question": "Q3?", "why": "how Glenn runs the false-guidance test"},
            {"question": "Q4?", "why": "x", "curious": "what the first application step looks like in your workshops"},
        ], "Glenn Broder")
        assert lines == ["I'm curious about what the first application step looks like in your workshops."]

    def test_reasoning_effort_is_a_run_setting(self, monkeypatch):
        import fire_interviews as fi
        monkeypatch.delenv("MIRA_REASONING_EFFORT", raising=False)
        assert fi.reasoning_effort() == "high"
        monkeypatch.setenv("MIRA_REASONING_EFFORT", "low")
        assert fi.reasoning_effort() == "low"
        monkeypatch.setenv("MIRA_REASONING_EFFORT", "turbo")
        assert fi.reasoning_effort() == "high"
        rows = []
        monkeypatch.setattr(fi, "sb_insert", lambda t, row: rows.append(row) or row)
        fi.insert_interview_run({"interview_id": "x"})
        assert rows[0]["reasoning_effort"] == "high"


class TestCarryTheShowIsOneOffer:
    ROWS = [
        {"guest": "Ada Example", "recorded_on": "2026-10-01",
         "summary": "A payments founder on processor fees and chargeback disputes.",
         "quote": "Processor fees are the tax nobody votes on.", "why": "", "predictions": []},
        {"guest": "Bea Sample", "recorded_on": "2026-09-20",
         "summary": "A nutritionist on being the architect of your own life.",
         "quote": "You are the architect of your own plate.", "why": "", "predictions": []},
    ]

    def _block(self, monkeypatch, app):
        import common
        monkeypatch.setattr(common, "show_insights", lambda *a, **k: list(self.ROWS))
        return common.carry_the_show_block("age_of_ai", exclude_email="", app=app)

    def test_only_the_guest_on_the_same_subject_is_offered(self, monkeypatch):
        block = self._block(monkeypatch, {
            "guest_agenda": {"topic": "Processor fees and chargeback disputes in payments"}})
        assert "Ada Example" in block and "Bea Sample" not in block
        assert block.count("In their words:") == 1

    def test_no_subject_match_means_no_callback(self, monkeypatch):
        assert self._block(monkeypatch, {"topics": ["offshore sailing"]}) == ""
        assert self._block(monkeypatch, None) == ""

    def test_a_guest_who_asked_to_keep_it_to_the_work_gets_none(self, monkeypatch):
        block = self._block(monkeypatch, {
            "personal_depth": "none",
            "guest_agenda": {"topic": "Processor fees and chargeback disputes"}})
        assert block == ""

    def test_it_is_an_offer_in_the_cohosts_shape(self, monkeypatch):
        block = self._block(monkeypatch, {
            "guest_agenda": {"topic": "Processor fees and chargeback disputes"}})
        flat = _flat(block)
        assert "says in a few words who they are" in flat
        assert "whether it holds from where this guest sits" in flat
        assert "Never ask whether the other person was right" in flat
        assert "Is he right" not in block
        assert "carry_the_show_block(show, exclude_email=app.get(\"email\", \"\"), app=app)" in FIRE
