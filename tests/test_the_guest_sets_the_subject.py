"""Sept 29 2026, Chad Law. He came to discuss The Velvet Monopoly; Mira
followed his last sentence into biography and a tangent and never came
back, and his publicist asked for a re-record. The guest now sets the
subject and the points to reach; Mira keeps choosing the questions.
"""
from __future__ import annotations

import json
from pathlib import Path

from pipelines.voices import common
from pipelines.producer import guest_reply

ROOT = Path(__file__).resolve().parent.parent
PROMPT = (ROOT / "pipelines" / "voices" / "prompts" / "mira_system_prompt.txt").read_text()
SCENARIO = (ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js").read_text()
WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text()


class TestTheAgendaReachesMira:
    def test_points_are_destinations_not_a_script(self):
        block = common.guest_agenda_block({"guest_agenda": {
            "topic": "The Velvet Monopoly", "points": ["Why less competition?", "Monthly bills"]}})
        assert "THE SUBJECT THEY CAME FOR: The Velvet Monopoly" in block
        assert "Every one is reached before the closing round" in block
        assert "never\nread them out" in block or "never read them out" in block
        assert "- Why less competition?" in block

    def test_without_an_agenda_the_stated_topics_name_the_subject(self):
        block = common.guest_agenda_block({"topics": ["Consolidation", "Prices"]})
        assert "THE SUBJECT THEY CAME FOR: Consolidation; Prices" in block
        assert common.guest_agenda_block({}) == ""

    def test_the_prompt_and_the_fire_step_carry_it(self):
        assert "{{guest_agenda}}" in PROMPT
        fire = (ROOT / "pipelines" / "voices" / "fire_interviews.py").read_text()
        assert "guest_agenda=guest_agenda_block(app)" in fire


class TestHowMiraHoldsTheSubject:
    def test_the_rules(self):
        assert "THE SUBJECT THEY CAME FOR IS THE SPINE OF THE HOUR" in PROMPT
        assert "TANGENTS GET A TURN OR TWO, THEN YOU COME BACK OUT LOUD" in PROMPT
        assert "WHEN THE GUEST STEERS, GO WITH THEM" in PROMPT
        assert "A PERSONAL STORY IS NOT A CLAIM" in PROMPT
        assert "A complete answer comes before any follow-up" in PROMPT
        assert "within the first five minutes you are on the subject" in PROMPT

    def test_the_clock_brings_her_back(self):
        assert "If any point under THE SUBJECT THEY CAME FOR has not" in SCENARIO
        assert "make sure every point under THE" in SCENARIO


class TestTheGuestCanSendIt:
    def test_the_form(self):
        for page in ("age-of-ai-apply.html", "nerra-voices-apply.html"):
            html = (ROOT / page).read_text()
            assert 'id="must_cover"' in html and "must_cover:" in html
        assert "guest_agenda: Array.isArray(form.must_cover)" in WORKER

    def test_by_email(self):
        plan = guest_reply.validate({
            "intent": "interview_input", "confidence": 0.9,
            "reply_text": "Hi Chad,\n\nThank you, I'll cover each of these.",
            "interview_note": None,
            "agenda": {"topic": "The Velvet Monopoly", "points": ["Q1", " Q2 ", ""]},
            "summary": "sent five questions"})
        assert plan["agenda"] == {"topic": "The Velvet Monopoly", "points": ["Q1", "Q2"]}

    def test_the_brief_shows_them_back(self):
        t = (ROOT / "templates" / "email" / "voices_prep_brief.j2").read_text()
        assert "What you asked me to cover" in t

    def test_filing_replaces_points_and_keeps_topic(self, monkeypatch):
        writes = []
        monkeypatch.setattr(guest_reply, "sb_update", lambda t, q, p: writes.append(p))
        app = {"id": "a", "guest_agenda": {"topic": "Old topic", "points": ["old"]}}
        guest_reply.file_agenda(app, {"topic": None, "points": ["new 1", "new 2"]}, dry_run=False)
        agenda = writes[0]["guest_agenda"]
        assert agenda["topic"] == "Old topic" and agenda["points"] == ["new 1", "new 2"]
