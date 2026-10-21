"""Oct 15 2026 — Grok Voice 3.0 (released Oct 14 2026).

What it is: xAI's speech-to-speech model behind the Voice Agent API, which
is Mira's live interview on The Age of AI and Nerra Voices. It is NOT the
text-to-speech endpoint the 31 shows synthesise through (`/v1/tts` has no
model id), so nothing in engine/tts.py moves. The `grok-voice-latest` alias
moved to 3.0 on release day and `grok-voice-2.0` is deprecated, so Mira has
been on 3.0 since Oct 14 without a change here.

What binds:

* the model is PINNED (`grok-voice-3.0`), never the floating alias — xAI's
  own production guidance, and the network's rule since the Aug 18
  translation incident (a vendor release must not change shipped audio
  unseen); the next version is adopted after a rehearsal;
* the scripted narration read runs `reasoning.effort: "none"` (a word-for-
  word read needs no thinking), the live interview pins `"high"`;
* the live transcription gets KEYTERMS (guest, organisation, show, network,
  hosts) from the run row, within xAI's 100 x 50-char limit, and a fire step
  on a database that lacks the column still fires the interview;
* Mira's prompt follows xAI's recommended section order (Role & Persona,
  Objective, Conversation Flow, Guardrails & Escalation, Voice &
  Communication Style, CRITICAL INSTRUCTIONS) with every earlier rule kept.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from unittest import mock

import pytest
import requests

ROOT = Path(__file__).resolve().parent.parent
SCENARIO = ROOT / "voximplant/scenarios/age_of_ai_interview.js"
PROMPT = ROOT / "pipelines/voices/prompts/mira_system_prompt.txt"


def _fire():
    sys.path.insert(0, str(ROOT / "pipelines/voices"))
    spec = importlib.util.spec_from_file_location(
        "fire_interviews_gv3", ROOT / "pipelines/voices/fire_interviews.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestPinnedModel:
    def test_default_is_the_versioned_model(self):
        spec = importlib.util.spec_from_file_location(
            "vc_gv3", ROOT / "voximplant/api_clients/voximplant_client.py")
        vc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(vc)
        assert vc.DEFAULT_GROK_VOICE_MODEL == "grok-voice-3.0"
        js = SCENARIO.read_text(encoding="utf-8")
        assert '? "grok-voice-3.0" : "__GROK_VOICE_MODEL__"' in js
        assert "grok-voice-latest" not in js.split("const GROK_MODEL")[1][:200]

    def test_key_check_probes_pin_alias_and_deprecated(self):
        wf = (ROOT / ".github/workflows/nerra_voices_xai_key_check.yml").read_text()
        assert '"grok-voice-3.0"' in wf and '"grok-voice-latest"' in wf and '"grok-voice-2.0"' in wf
        assert "grok-voice-fast-1.0" not in wf

    def test_tts_has_no_model_to_move(self):
        """`/v1/tts` takes text, voice_id, language, output_format,
        text_normalization, speed — no model id. The shows are untouched."""
        src = (ROOT / "engine/tts.py").read_text(encoding="utf-8")
        assert "grok-voice" not in src
        assert '"model"' not in src.split("def grok_speak_chunk")[1].split("def ")[0]


class TestSessionSettings:
    def test_narration_read_runs_without_reasoning(self):
        js = SCENARIO.read_text(encoding="utf-8")
        narr = js[js.index("const narrationSessionCfg = {"):js.index("agent.sessionUpdate({ session: narrationSessionCfg })")]
        assert 'reasoning: { effort: "none" }' in narr
        assert "turn_detection: null" in narr

    def test_live_interview_pins_high_and_sends_keyterms(self):
        js = SCENARIO.read_text(encoding="utf-8")
        live = js[js.index("const sessionCfg = {"):js.index("agent.sessionUpdate({ session: sessionCfg })")]
        assert 'reasoning: { effort: "high" }' in live
        assert "sessionAudioConfig()" in live
        fn = js[js.index("function sessionAudioConfig()"):js.index("function turnDetection()")]
        assert "config.keyterms" in fn and "transcription: { keyterms: clean }" in fn
        assert "clean.length < 100" in fn and ".slice(0, 50)" in fn
        # A run with neither a rate nor key terms sends no audio block at all.
        assert "return Object.keys(audio).length ? audio : null" in fn


class TestKeyterms:
    def test_builder_names_the_people_and_the_show(self):
        fi = _fire()
        show = type("S", (), {"name": "The Age of AI"})()
        terms = fi.keyterms_for(
            {"name": "Piper Martz", "organization": "Martz Robotics", "title": "Dr"},
            show, "Patrick Novak")
        assert terms[:3] == ["Piper Martz", "Piper", "Martz"]
        assert "Martz Robotics" in terms and "Dr" in terms
        assert "The Age of AI" in terms and "Nerra Network" in terms and "Mira" in terms
        assert "Patrick Novak" in terms and "Patrick" in terms and "Novak" in terms
        assert len(terms) == len({t.lower() for t in terms})  # deduplicated
        assert all(len(t) <= fi.KEYTERM_MAX_CHARS for t in terms)

    def test_builder_respects_the_api_limits(self):
        fi = _fire()
        long_name = " ".join(f"Name{i}" for i in range(150))
        terms = fi.keyterms_for({"name": long_name}, None, "")
        assert len(terms) <= fi.KEYTERMS_MAX
        assert all(len(t) <= 50 for t in terms)
        assert fi.keyterms_for({}, None, "") == ["Nerra Network", "Mira"]

    def test_insert_survives_a_missing_column(self):
        fi = _fire()
        calls = []
        resp = mock.Mock(status_code=400, text='{"message":"Could not find the \'keyterms\' column"}')

        def fake_insert(table, row):
            calls.append(dict(row))
            if "keyterms" in row:
                raise requests.HTTPError(response=resp)
            return {"id": "run-1", **row}

        with mock.patch.object(fi, "sb_insert", fake_insert):
            out = fi.insert_interview_run({"interview_id": "i", "keyterms": ["A"], "tools": []})
        assert out["id"] == "run-1" and "keyterms" not in out
        assert len(calls) == 2 and "keyterms" not in calls[1]

    def test_other_errors_still_raise(self):
        fi = _fire()
        resp = mock.Mock(status_code=500, text="boom")
        with mock.patch.object(fi, "sb_insert", side_effect=requests.HTTPError(response=resp)):
            with pytest.raises(requests.HTTPError):
                fi.insert_interview_run({"interview_id": "i", "keyterms": ["A"]})

    def test_run_row_carries_keyterms_and_the_migration_exists(self):
        src = (ROOT / "pipelines/voices/fire_interviews.py").read_text(encoding="utf-8")
        assert '"keyterms": keyterms_for(app, show, cohost_name()),' in src
        assert "run = insert_interview_run({" in src
        mig = (ROOT / "supabase/migrations/20261015_interview_runs_keyterms.sql").read_text()
        assert "add column if not exists keyterms jsonb" in mig


class TestPromptStructure:
    def test_sections_in_the_recommended_order(self):
        text = PROMPT.read_text(encoding="utf-8")
        heads = re.findall(r"^## (.+)$", text, re.M)
        assert heads == ["Role & Persona", "Objective", "Conversation Flow",
                         "Guardrails & Escalation", "Voice & Communication Style",
                         "CRITICAL INSTRUCTIONS"]
        assert text.startswith("## Role & Persona\n\nYou are Mira")

    def test_every_earlier_rule_survived(self):
        text = PROMPT.read_text(encoding="utf-8")
        # "HOW TO OPEN" carries its reason in brackets since Oct 19 2026.
        # Oct 21 2026: the same rules, stated once each as a host's brief.
        for needle in ("HOW TO OPEN", "HOW TO CLOSE.", "HOW IT ENDS.",
                       "RESEARCH IS QUIET.", "TIME.", "YOUR OWN VOICE.",
                       "{{cohost_craft}}", "{{lessons}}", "{{guest_shape}}"):
            assert needle in text, needle
        crit = text.split("## CRITICAL INSTRUCTIONS")[1]
        assert "One question per turn" in crit and "[TIME CHECK]" in crit
        # xAI: no soft language in CRITICAL INSTRUCTIONS.
        assert not re.search(r"\b(try to|ideally|if possible)\b", crit)

    def test_critical_section_is_last_and_short(self):
        text = PROMPT.read_text(encoding="utf-8")
        crit = text.split("## CRITICAL INSTRUCTIONS")[1]
        assert len(crit.split()) < 160
