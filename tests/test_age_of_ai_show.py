"""Launch-shape + guest-pipeline drift guards for The Age of AI (July 2026).

The Age of AI is the network's AI-hosted interview show: Nerra (an AI
persona, Grok built-in voice ``eve``) interviews real people whose written
answers enter the pipeline verbatim. These tests pin:

* the launch config shape (narrative mode, dialogue TTS with NERRA/GUEST
  voices, distribution off);
* the consent gates in ``engine.interview`` (publish consent required;
  ai_voiced degrades to quoted without voice consent);
* verbatim answer ingestion + packet compilation;
* the hook's per-episode voicing behaviour (quoted packets flip dialogue
  mode off; consented per-guest voice overrides apply);
* the read-only-hooks contract (``NERRA_HOOKS_READONLY`` protects the CRM).
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

import yaml

ROOT = Path(__file__).resolve().parent.parent
# Hooks live in shows/hooks/ without a package __init__ at shows/ — import
# them the same way run_show and the other hook tests do.
sys.path.insert(0, str(ROOT / "shows" / "hooks"))
SHOW_YAML = ROOT / "shows" / "age_of_ai.yaml"
GUEST_QUEUE = ROOT / "shows" / "guest_queues" / "age_of_ai.yaml"
TOPIC_QUEUE = ROOT / "shows" / "topic_queues" / "age_of_ai.yaml"


def _guest(**overrides):
    base = {
        "id": "test-guest",
        "name": "Test Guest",
        "stage": "answers_received",
        "bio": "A test human.",
        "angle": "testing the age of AI",
        "consent_to_publish": True,
        "consent_ai_voice": False,
        "voice_mode": "quoted",
        "guest_voice_id": "",
        "answers": [{"q": "How are you?", "a": "Honestly, fine."}],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Launch config shape
# ---------------------------------------------------------------------------

class TestLaunchShape:
    def test_config_loads_and_is_narrative(self):
        from engine.config import load_config
        cfg = load_config(SHOW_YAML)
        assert cfg.slug == "age_of_ai"
        assert cfg.narrative_mode is True
        assert cfg.topic_queue_file == "shows/topic_queues/age_of_ai.yaml"
        assert cfg.min_articles_skip == 0, (
            "interview show never fetches news — a nonzero floor would block "
            "every episode"
        )

    def test_dialogue_tts_shape(self):
        """NERRA/GUEST dialogue voices are real Grok built-ins (not the
        network's Patrick clone — the host persona is a machine, not
        Patrick) and the speech wrap is pinned empty (landmine #17)."""
        from engine.config import load_config
        cfg = load_config(SHOW_YAML)
        assert cfg.tts.provider == "grok"
        assert cfg.tts.dialogue_mode is True
        voices = cfg.tts.dialogue_voices
        assert set(voices) == {"NERRA", "GUEST"}
        for label, vid in voices.items():
            assert vid and "REPLACE" not in str(vid).upper(), (
                f"dialogue voice {label} must be a real Grok voice ID"
            )
        assert voices["NERRA"] != "kdif6sqjcyiq", (
            "Nerra must NOT reuse the Patrick voice clone — the AI host is "
            "its own on-air identity"
        )
        assert cfg.tts.speech_wrap_open == "" and cfg.tts.speech_wrap_close == ""

    def test_distribution_off_at_launch(self):
        raw = yaml.safe_load(SHOW_YAML.read_text(encoding="utf-8"))
        assert raw["publishing"]["x_enabled"] is False
        assert raw["youtube"]["enabled"] is False
        assert raw["youtube"]["image_provider"] == "grok"
        assert raw["newsletter"]["enabled"] is False
        assert raw["multilingual"]["enabled"] is False
        assert raw.get("weekly_recap_on_sunday") is False

    def test_no_expand_retry(self):
        """The expand-below-target retry pads by paraphrase — on an
        interview show padding risks drifting from verbatim guest words, so
        it must stay off."""
        raw = yaml.safe_load(SHOW_YAML.read_text(encoding="utf-8"))
        assert not raw["llm"].get("podcast_expand_below_target", False)
        assert not raw["llm"].get("digest_expand_below_target", False)

    def test_chapter_ordering_rules(self):
        """Closing carries where:end and is listed before the body markers
        (EI June-11 ordering rule); Introduction anchors to start."""
        raw = yaml.safe_load(SHOW_YAML.read_text(encoding="utf-8"))
        markers = raw["chapters"]["section_markers"]
        titles = [m["title"] for m in markers]
        by_title = {m["title"]: m for m in markers}
        assert by_title["Introduction"]["where"] == "start"
        assert by_title["Closing"]["where"] == "end"
        body_positions = [
            titles.index(t) for t in titles
            if t not in ("Introduction", "Closing")
        ]
        assert body_positions, "expected at least one body marker"
        assert titles.index("Closing") < min(body_positions), (
            "Closing must be listed before body markers so a merged final "
            "line can't be stolen (EI June-11 ordering rule)"
        )

    def test_topic_queue_starts_empty_and_valid(self):
        data = yaml.safe_load(TOPIC_QUEUE.read_text(encoding="utf-8"))
        assert data == {"queue": []}

    def test_intro_personality_registered(self):
        from engine.intros import build_intro_line, build_closing_block
        import datetime as dt
        intro = build_intro_line(
            "age_of_ai", episode_num=2, today_str="July 4, 2026",
            date=dt.date(2026, 7, 4),
        )
        assert intro.startswith("NERRA: ")
        assert "Age of AI" in intro
        closing = build_closing_block(
            "age_of_ai", episode_num=2, today_str="July 4, 2026",
            date=dt.date(2026, 7, 4),
        )
        assert closing.rstrip().endswith("keep being human.")

    def test_prompts_carry_fidelity_and_disclosure_rules(self):
        podcast = (ROOT / "shows/prompts/age_of_ai_podcast.txt").read_text(encoding="utf-8")
        digest = (ROOT / "shows/prompts/age_of_ai_digest.txt").read_text(encoding="utf-8")
        for text in (podcast, digest):
            assert "VERBATIM" in text.upper()
        assert "{guest_dossier}" in podcast and "{guest_dossier}" in digest
        assert "DISCLOSURE" in podcast

    def test_run_show_defaults_guest_dossier(self):
        """A hook failure must degrade to an empty dossier, never a
        KeyError in prompt substitution (both stages)."""
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert src.count('setdefault("guest_dossier", "")') >= 2


# ---------------------------------------------------------------------------
# Guest queue + consent gates
# ---------------------------------------------------------------------------

class TestGuestPipeline:
    def test_seed_guest_queue_shape(self):
        data = yaml.safe_load(GUEST_QUEUE.read_text(encoding="utf-8"))
        guests = data["guests"]
        assert guests, "guest queue should seed at least the Ep1 prospect"
        from engine.interview import GUEST_STAGES
        for g in guests:
            assert g.get("stage") in GUEST_STAGES
            # Consent is a human agreement — the seed must never pre-set it.
            assert g.get("consent_to_publish") is False
            assert g.get("consent_ai_voice") is False

    def test_compile_refuses_without_publish_consent(self):
        import pytest
        from engine.interview import compile_packet
        with pytest.raises(ValueError, match="consent"):
            compile_packet(_guest(consent_to_publish=False))

    def test_compile_refuses_without_answers(self):
        import pytest
        from engine.interview import compile_packet
        with pytest.raises(ValueError, match="answers"):
            compile_packet(_guest(answers=[]))

    def test_ai_voiced_degrades_to_quoted_without_voice_consent(self):
        from engine.interview import compile_packet
        packet = compile_packet(_guest(voice_mode="ai_voiced",
                                       consent_ai_voice=False))
        assert packet["voice_mode"] == "quoted"
        assert "guest_voice_id" not in packet

    def test_ai_voiced_honoured_with_consent(self):
        from engine.interview import compile_packet
        packet = compile_packet(_guest(voice_mode="ai_voiced",
                                       consent_ai_voice=True,
                                       guest_voice_id="custom123"))
        assert packet["voice_mode"] == "ai_voiced"
        assert packet["guest_voice_id"] == "custom123"

    def test_compiled_packet_is_standard_queue_schema(self):
        from engine.interview import compile_packet
        packet = compile_packet(_guest())
        for key in ("id", "title", "brief", "produced",
                    "episode_number", "produced_date"):
            assert key in packet
        assert packet["produced"] is False
        assert packet["id"] == "interview-test-guest"
        assert "Honestly, fine." in packet["brief"], (
            "the guest's verbatim answer must reach the brief untouched"
        )
        assert "VERBATIM" in packet["brief"]

    def test_parse_answers_markdown_multiparagraph(self):
        from engine.interview import parse_answers_markdown
        pairs = parse_answers_markdown(textwrap.dedent("""\
            Q: First question?
            A: First paragraph.

            Second paragraph of the same answer.

            Q: Second question?
            A: Short answer.
        """))
        assert len(pairs) == 2
        assert "Second paragraph" in pairs[0]["a"]
        assert pairs[1]["a"] == "Short answer."

    def test_append_packet_refuses_duplicates(self, tmp_path):
        import pytest
        from engine.interview import append_packet_to_topic_queue, compile_packet
        queue = tmp_path / "queue.yaml"
        packet = compile_packet(_guest())
        append_packet_to_topic_queue(queue, packet)
        with pytest.raises(ValueError, match="already"):
            append_packet_to_topic_queue(queue, packet)
        data = yaml.safe_load(queue.read_text(encoding="utf-8"))
        assert len(data["queue"]) == 1

    def test_invite_and_questions_fallbacks_work_offline(self):
        """Outreach drafting must never require an API key."""
        from engine.interview import build_invite_email, build_question_set
        guest = _guest()
        invite = build_invite_email(guest, use_llm=False)
        assert "AI" in invite and "verbatim" in invite.lower()
        questions = build_question_set(guest, use_llm=False)
        assert len(questions) >= 5
        assert all(q.endswith("?") for q in questions)


# ---------------------------------------------------------------------------
# Hook behaviour
# ---------------------------------------------------------------------------

class TestHook:
    def _packet(self, **overrides):
        base = {
            "id": "interview-test-guest",
            "title": "Test Guest on testing",
            "brief": "GUEST: Test Guest\nQ1: ...\nA1: ...",
            "guest_id": "test-guest",
            "voice_mode": "ai_voiced",
            "consent_ai_voice": True,
            "produced": False,
        }
        base.update(overrides)
        return base

    def _run_hook(self, tmp_path, packet):
        import age_of_ai as hook  # noqa: PLC0415 (sys.path manipulation above)
        queue = tmp_path / "queue.yaml"
        queue.write_text(
            yaml.safe_dump({"queue": [packet]}, sort_keys=False),
            encoding="utf-8",
        )
        tts = SimpleNamespace(
            dialogue_mode=True,
            dialogue_voices={"NERRA": "eve", "GUEST": "ara"},
        )
        config = SimpleNamespace(topic_queue_file="", tts=tts)
        # The hook resolves topic_queue_file relative to the repo root, so
        # point it at the tmp queue via an absolute-path-tolerant monkeypatch.
        orig = hook._peek_next_packet
        hook._peek_next_packet = lambda cfg: packet if not packet.get("produced") else {}
        try:
            result = hook.pre_fetch(config, episode_num=1, today_str="July 4, 2026")
        finally:
            hook._peek_next_packet = orig
        return result, config

    def test_quoted_packet_flips_dialogue_off(self, tmp_path):
        packet = self._packet(voice_mode="quoted")
        result, config = self._run_hook(tmp_path, packet)
        assert config.tts.dialogue_mode is False
        assert "guest_dossier" in result
        assert "quoted" in result["guest_dossier"]

    def test_ai_voiced_packet_keeps_dialogue_and_overrides_voice(self, tmp_path):
        packet = self._packet(guest_voice_id="guestvoice1")
        result, config = self._run_hook(tmp_path, packet)
        assert config.tts.dialogue_mode is True
        assert config.tts.dialogue_voices["GUEST"] == "guestvoice1"
        assert config.tts.dialogue_voices["NERRA"] == "eve"
        assert "ai_voiced" in result["guest_dossier"]

    def test_empty_queue_returns_no_context(self, tmp_path):
        import age_of_ai as hook  # noqa: PLC0415 (sys.path manipulation above)
        orig = hook._peek_next_packet
        hook._peek_next_packet = lambda cfg: {}
        try:
            result = hook.pre_fetch(
                SimpleNamespace(topic_queue_file="x", tts=SimpleNamespace()),
                episode_num=1, today_str="today",
            )
        finally:
            hook._peek_next_packet = orig
        assert result == {}

    def test_post_generate_readonly_guard(self, tmp_path, monkeypatch):
        """--test/--rehearse runs (NERRA_HOOKS_READONLY=1) must never touch
        the guest queue."""
        import age_of_ai as hook  # noqa: PLC0415 (sys.path manipulation above)
        monkeypatch.setenv("NERRA_HOOKS_READONLY", "1")
        called = []
        monkeypatch.setattr(
            "engine.interview.mark_guest_published",
            lambda *a, **k: called.append(a),
        )
        hook.post_generate(
            SimpleNamespace(topic_queue_file="shows/topic_queues/age_of_ai.yaml"),
            digest_text="", episode_num=1,
        )
        assert called == []

    def test_post_generate_marks_guest_published(self, tmp_path, monkeypatch):
        import age_of_ai as hook  # noqa: PLC0415 (sys.path manipulation above)
        monkeypatch.delenv("NERRA_HOOKS_READONLY", raising=False)
        queue = tmp_path / "queue.yaml"
        queue.write_text(
            yaml.safe_dump({"queue": [self._packet(
                produced=True, episode_number=7, produced_date="2026-07-04",
            )]}, sort_keys=False),
            encoding="utf-8",
        )
        monkeypatch.setattr(hook, "_ROOT", tmp_path)
        calls = []
        monkeypatch.setattr(
            "engine.interview.mark_guest_published",
            lambda path, gid, ep, date: calls.append((gid, ep, date)) or True,
        )
        hook.post_generate(
            SimpleNamespace(topic_queue_file="queue.yaml"),
            digest_text="", episode_num=7,
        )
        assert calls == [("test-guest", 7, "2026-07-04")]
