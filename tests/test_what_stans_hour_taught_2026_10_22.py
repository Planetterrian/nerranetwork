"""Oct 22 2026, Stan Lewis: what one interview showed, and the guards.

* His booking had a name and a personal address, nothing else. The research
  pass found a better-known man with the same first name and the brief, the
  questions emailed to him and Mira's first question were about that man.
  An application with nothing to tell the guest apart is not researched; the
  guest is asked who they are, and research that never names them is thrown
  away.
* He took a phone call mid-interview. The thank-you note quoted his side of
  it back to him, with Patrick and Dan copied. Moments are now whole, safe
  sentences from answers to Mira's questions.
* The studio page said "opening the studio" after the interview had ended,
  and the Worker emailed Patrick that the studio had not opened.
* Patrick got two emails per episode fifteen minutes apart. Now one.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
V = ROOT / "pipelines" / "voices"
sys.path.insert(0, str(V))
sys.path.insert(0, str(ROOT))

import generate_briefs as gb  # noqa: E402
import guest_thanks as gt  # noqa: E402

WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")
STUDIO = (ROOT / "age-of-ai-studio.html").read_text(encoding="utf-8")
POST = (V / "post_interview.py").read_text(encoding="utf-8")
ASSEMBLE = (V / "assemble_edit.py").read_text(encoding="utf-8")
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "nerra_voices_post_interview.yml"
PREP = (ROOT / "templates" / "email" / "voices_prep_brief.j2").read_text(encoding="utf-8")
SCENARIO = (ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js").read_text(encoding="utf-8")

# A guest who answers well, then takes a call. Invented details throughout.
CALL = """[00:10] Mira: Hello Sam, how are you today?
[00:14] Sam Rowe: Good, thank you, happy to be here.
[01:00] Mira: How did mediation in Houston change the way you lead?
[01:05] Sam Rowe: Mediation in Houston taught me that people defend positions but they negotiate interests. Once I learned to ask what someone actually needs, the room changed and the anger had somewhere to go.
[02:30] Mira: What do executives get wrong about conflict?
[02:35] Sam Rowe: They treat conflict as a fire to put out instead of information about the organisation. The best leaders I coached at Boeing learned to sit in it long enough to hear what it was telling them.
[03:40] Mira: Take your time.
[03:50] Sam Rowe: Hold on, I have to take this call.
[04:00] Mira: Of course, I'll wait. Is everything all right?
[04:05] Sam Rowe: Yes this is him, my date of birth is the eighteenth, and my number is 555 201 3344, I need the appointment moved to Thursday at the clinic.
[04:40] Sam Rowe: The doctor said my blood sugar was too high and I need the prescription refilled before Monday.
"""


class TestTheThankYouNeverQuotesAnotherConversation:
    def test_only_answers_and_only_safe_sentences(self):
        moments = gt.memorable_moments(CALL, "Sam Rowe")
        texts = [t for _at, t in moments]
        assert len(texts) == 2
        assert "Houston" in texts[0] and "Boeing" in texts[1]
        joined = " ".join(texts)
        for private in ("birth", "555", "appointment", "clinic", "doctor",
                        "blood sugar", "prescription", "Thursday", "Monday"):
            assert private not in joined, private
        assert all(t[0].isupper() for t in texts)              # whole sentences

    def test_the_sensitive_words_are_refused(self):
        for line in ("My social security number is on the form they sent me last week.",
                     "The doctor at the hospital said the diagnosis was early and treatable.",
                     "Call me back at 555 201 3344 when the paperwork arrives tomorrow.",
                     "I was born on April 3 and the claim has been open for two years now."):
            assert not gt.safe_to_quote(line), line
        assert gt.safe_to_quote("People defend positions but they negotiate interests.")

    def test_fewer_than_two_safe_moments_quotes_nothing(self):
        one = ("[00:20] Mira: What did the first year teach you?\n"
               "[00:25] Sam Rowe: The first year taught us that pricing is a story, and we "
               "told it badly for eleven months before Acme Corp walked.\n")
        assert gt.memorable_moments(one, "Sam Rowe") == []

    def test_a_line_nobody_asked_for_is_not_an_answer(self):
        unasked = ("[00:20] Mira: That is a lovely way to put it.\n"
                   "[00:25] Sam Rowe: The first year taught us that pricing is a story, and we "
                   "told it badly for eleven months before Acme Corp walked.\n")
        assert gt._answers(unasked) == []

    def test_no_em_dash_in_the_subject(self):
        class _S:
            name, short_label, base_url = "The Age of AI", "Age of AI", "https://nerranetwork.com"
            slug, page_url = "age_of_ai", "https://nerranetwork.com/age-of-ai.html"
        subject, body = gt.thank_you_email(_S(), {"name": "Sam Rowe"}, CALL)
        assert "—" not in subject
        assert "Two things you said" in body


class TestABareNameIsNotResearched:
    BARE = {"name": "Sam Rowe", "email": "samrowe1962@gmail.com", "phone": "+15552013344"}

    def test_a_bare_booking_has_no_anchor(self):
        assert gb.identity_anchors(self.BARE) == []
        assert gb.identity_anchors({**self.BARE, "email": "sam@rowemediation.com"}) == ["email_domain"]
        assert gb.identity_anchors({**self.BARE, "links": {"linkedin": "x"}}) == ["links"]
        assert gb.identity_anchors({**self.BARE, "topics": ["", " "]}) == []

    def test_the_same_name_under_another_address_lends_what_it_told_us(self, monkeypatch):
        # Oct 23 2026: Stan had pitched from his company address and booked
        # from Gmail; the pitch, topics and links were on the other row.
        other = {"id": "a0", "email": "slewis@nwardjourney.com", "topics": ["Team execution"],
                 "links": {"urls": ["https://go.nwardjourney.com/x"]},
                 "pitch_summary": "Leadership expert on team execution."}
        asked = []
        monkeypatch.setattr(gb, "sb_select", lambda t, q="": asked.append(q) or [other])
        app = {**self.BARE, "id": "a1"}
        merged = gb.borrow_identity(app)
        assert "name=ilike.Sam%20Rowe" in asked[0] and "id=neq.a1" in asked[0]
        assert merged["pitch_summary"] == other["pitch_summary"]
        assert merged["topics"] == other["topics"] and merged["email"] == self.BARE["email"]
        assert gb.identity_anchors(merged)
        # Two other rows with the same name: nobody is guessed at.
        monkeypatch.setattr(gb, "sb_select", lambda t, q="": [other, {**other, "id": "a2"}])
        assert gb.borrow_identity(app) is app

    def test_research_that_never_names_them_is_someone_else(self):
        assert not gb.research_names_guest("Stanislas Polu co-founded Dust after OpenAI.", "Stan Lewis")
        assert gb.research_names_guest("Stan Lewis mediates for executives in Texas.", "Stan Lewis")
        assert gb.research_names_guest("anything", "Cher")                  # nothing to check
        assert gb.surname("Robert Smith Jr.") == "smith"

    def test_no_anchor_means_no_web_search(self, monkeypatch):
        calls, made = [], []
        monkeypatch.setattr(gb, "llm", lambda *a, **k: calls.append(k) or "")
        monkeypatch.setattr(gb, "show_for", lambda i, a: type("S", (), {"short_label": "Age of AI"})())
        monkeypatch.setattr(gb, "send_email", lambda *a, **k: made.append(a[1]))
        monkeypatch.setattr(gb, "sb_insert", lambda t, row: {"id": "b1", **row})
        monkeypatch.setattr(gb, "sb_select", lambda t, q="": [])
        brief = gb.generate_brief({"id": "i1", "scheduled_at": ""}, self.BARE)
        assert calls == []                                                  # never researched
        assert brief["bio_research"].startswith("IDENTITY NOT CONFIRMED")
        assert made and "who is Sam Rowe" in made[0]

    def test_research_about_someone_else_is_discarded(self, monkeypatch):
        monkeypatch.setattr(gb, "llm", lambda *a, **k: "Stanislas Polu founded Dust.")
        monkeypatch.setattr(gb, "load_prompt", lambda *a, **k: "")
        monkeypatch.setattr(gb, "prior_record", lambda app: "")
        monkeypatch.setattr(gb, "show_for", lambda i, a: type("S", (), {"short_label": "Age of AI"})())
        monkeypatch.setattr(gb, "send_email", lambda *a, **k: None)
        monkeypatch.setattr(gb, "sb_insert", lambda t, row: {"id": "b1", **row})
        app = {**self.BARE, "name": "Stan Lewis", "organization": "Lewis Mediation"}
        brief = gb.generate_brief({"id": "i1", "scheduled_at": ""}, app)
        assert brief["bio_research"].startswith("IDENTITY NOT CONFIRMED")

    def test_the_guest_is_asked_instead_of_told(self):
        assert "{% if identity_unknown %}" in PREP
        assert "Before we talk, tell me about you" in PREP
        assert "{% if not identity_unknown %}" in PREP                      # no questions list
        assert "tell me about you" in (V / "generate_briefs.py").read_text(encoding="utf-8")


class TestAFinishedInterviewIsFinished:
    def test_the_worker_never_rescues_a_completed_room(self):
        assert 'const ended = !run && Boolean(latest) && String(latest.status) === "completed";' in WORKER
        assert "const waitingForRun = !run && !ended && openNow" in WORKER
        assert "ended," in WORKER

    def test_the_studio_page_says_thank_you(self):
        i = STUDIO.index("if (s.ended) {")
        assert i < STUDIO.index("var when =", i)
        assert "This interview has finished. Thank you!" in STUDIO


class TestOneEmailPerEpisode:
    def test_the_assembler_sends_it_and_the_package_step_does_not(self):
        assert 'os.environ.get("GATE1_AFTER_ASSEMBLY", "").strip() == "1"' in POST
        wf = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
        steps = wf["jobs"][next(iter(wf["jobs"]))]["steps"]
        post = next(s for s in steps if s.get("id") == "post")
        assert post["env"]["GATE1_AFTER_ASSEMBLY"] == "1"

    def test_the_review_link_still_arrives_when_the_cut_fails(self):
        wf = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
        steps = wf["jobs"][next(iter(wf["jobs"]))]["steps"]
        last = steps[-1]
        assert "--gate1-fallback" in last["run"]
        assert "!cancelled()" in last["if"] and "steps.post.outcome == 'success'" in last["if"]
        assert "CUT_FAILED" in last["env"]
        assert '"--gate1-fallback" in sys.argv' in POST
        body = POST[POST.index("def gate1_fallback()"):]
        assert 'pkgs[0].get("operator_preview_sent_at")' in body             # never twice

    def test_the_subjects_match_and_carry_no_dash(self):
        assert 'f"{show.short_label}: {app[\'name\']} is ready for your review"' in POST
        assert "is ready for your review" in ASSEMBLE
        assert "cut and ready for your ear" not in ASSEMBLE


class TestTheTraceKeepsWhatMatters:
    def test_bookkeeping_goes_first(self):
        i = SCENARIO.index("function traceForStorage()")
        body = SCENARIO[i:SCENARIO.index("\n}\n", i)]
        assert 'if (line.e === "grok" && line.d === "response done") continue;' in body
        assert "TRACE_KEEP_EARLY" in body
        assert "serverTurns % 10 === 0" in SCENARIO
