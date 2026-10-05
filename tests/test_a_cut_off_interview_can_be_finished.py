"""Oct 5 2026 (Piper Martz). The old time cap cut her off seconds into the
lightning round. A short closing session lets a guest come back, finish the
closing round and have the last word; it is spliced onto the first recording.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")
SCENARIO = (ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js").read_text(encoding="utf-8")
PROMPT = (ROOT / "pipelines" / "voices" / "prompts" / "mira_closing_session.txt").read_text(encoding="utf-8")


def test_the_prompt_is_the_closing_round_only():
    flat = " ".join(PROMPT.split())
    assert "THIS IS A SHORT CLOSING SESSION, NOT A NEW INTERVIEW" in PROMPT
    assert "Welcome them back warmly, by name" in flat
    assert "{{where_we_left_off}}" in PROMPT and "{{closing_question}}" in PROMPT
    assert "There is no time limit" in flat


def test_fire_uses_it_and_needs_no_brief(monkeypatch):
    import fire_interviews as fi
    monkeypatch.setattr(fi, "sb_select", lambda t, q: [{"transcript_cleaned": "[49:52] Mira: A book you would recommend?"}])
    iv = {"id": "x", "show": "age_of_ai", "session_kind": "closing", "continues_interview_id": "y"}
    app = {"name": "Piper Martz", "show": "age_of_ai"}
    text = fi.compile_closing_prompt(iv, app)
    assert "Piper Martz" in text and "A book you would recommend?" in text
    assert "{{" not in text
    assert fi.is_closing_session(iv) and not fi.is_closing_session({"id": "z"})
    src = (ROOT / "pipelines" / "voices" / "fire_interviews.py").read_text(encoding="utf-8")
    assert '"session_kind": interview.get("session_kind") or "interview",' in src


def test_scenario_opens_the_round_at_once():
    assert "if (isClosingSession()) return 0;" in SCENARIO
    assert 'config.session_kind === "closing"' in SCENARIO


def test_worker_books_it_as_its_own_row():
    assert "const closing = /closing/i.test(eventSlug) ||" in WORKER
    assert 'session_kind: "closing", continues_interview_id: continues' in WORKER
    assert "Thank you for coming back to finish our" in WORKER


def test_briefs_skip_it():
    src = (ROOT / "pipelines" / "voices" / "generate_briefs.py").read_text(encoding="utf-8")
    assert '(interview.get("session_kind") or "interview") == "closing"' in src
