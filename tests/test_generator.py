"""Unit coverage for engine.generator's LLM-call path and prompt loading.

The existing tests/test_generator_postprocess.py covers the output-cleanup
helpers.  This module fills the gap the May 2026 codebase review flagged: the
prompt loader (including the new shared-snippet include mechanism), the refusal
/ validation gate, the refusal-fallback model resolution, and the Grok call
path itself (mocked, so a breaking change to how we shape the request/response
is caught without spending API credits).
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from engine.generator import (
    LLMRefusalError,
    _detect_story_duplication,
    _resolve_fallback_model,
    _resolve_includes,
    _validate_llm_output,
    load_prompt,
)


# ---------------------------------------------------------------------------
# load_prompt — substitution + error handling
# ---------------------------------------------------------------------------

class TestLoadPrompt:
    def test_basic_substitution(self, tmp_path: Path):
        p = tmp_path / "p.txt"
        p.write_text("Hello {name}, episode {episode_num}", encoding="utf-8")
        assert load_prompt(str(p), {"name": "Tesla", "episode_num": 5}) == "Hello Tesla, episode 5"

    def test_none_template_vars_returns_raw(self, tmp_path: Path):
        p = tmp_path / "p.txt"
        p.write_text("Raw {unfilled} text", encoding="utf-8")
        # None means "don't substitute" — placeholders survive untouched.
        assert load_prompt(str(p), None) == "Raw {unfilled} text"

    def test_missing_key_raises_keyerror(self, tmp_path: Path):
        p = tmp_path / "p.txt"
        p.write_text("Need {missing}", encoding="utf-8")
        with pytest.raises(KeyError):
            load_prompt(str(p), {"present": "x"})

    def test_missing_file_raises_filenotfound(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_prompt(str(tmp_path / "nope.txt"), {})

    def test_prompt_without_include_is_byte_identical(self, tmp_path: Path):
        body = "Line one\nLine two with {var}\n"
        p = tmp_path / "p.txt"
        p.write_text(body, encoding="utf-8")
        # No include directive -> raw passes through unchanged before format.
        assert load_prompt(str(p), None) == body


# ---------------------------------------------------------------------------
# Shared-snippet include mechanism
# ---------------------------------------------------------------------------

class TestPromptIncludes:
    def test_include_is_expanded_before_substitution(self, tmp_path: Path):
        shared = tmp_path / "_shared"
        shared.mkdir()
        (shared / "rules.txt").write_text("RULES for {name}", encoding="utf-8")
        main = tmp_path / "main.txt"
        main.write_text("Intro\n<<include: _shared/rules.txt>>\nOutro", encoding="utf-8")
        out = load_prompt(str(main), {"name": "Tesla"})
        assert out == "Intro\nRULES for Tesla\nOutro"

    def test_include_resolves_relative_to_including_file(self, tmp_path: Path):
        sub = tmp_path / "prompts"
        sub.mkdir()
        (sub / "snippet.txt").write_text("SNIPPET", encoding="utf-8")
        main = sub / "main.txt"
        main.write_text("<<include: snippet.txt>>", encoding="utf-8")
        assert load_prompt(str(main), None) == "SNIPPET"

    def test_nested_includes(self, tmp_path: Path):
        (tmp_path / "b.txt").write_text("B", encoding="utf-8")
        (tmp_path / "a.txt").write_text("A<<include: b.txt>>", encoding="utf-8")
        main = tmp_path / "main.txt"
        main.write_text("<<include: a.txt>>!", encoding="utf-8")
        assert load_prompt(str(main), None) == "AB!"

    def test_missing_snippet_raises(self, tmp_path: Path):
        main = tmp_path / "main.txt"
        main.write_text("<<include: _shared/nope.txt>>", encoding="utf-8")
        with pytest.raises(FileNotFoundError):
            load_prompt(str(main), None)

    def test_circular_include_raises(self, tmp_path: Path):
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_text("<<include: b.txt>>", encoding="utf-8")
        b.write_text("<<include: a.txt>>", encoding="utf-8")
        with pytest.raises((ValueError, FileNotFoundError)):
            load_prompt(str(a), None)

    def test_resolve_includes_noop_without_directive(self, tmp_path: Path):
        assert _resolve_includes("plain text {x}", tmp_path) == "plain text {x}"


# ---------------------------------------------------------------------------
# Refusal-fallback model resolution
# ---------------------------------------------------------------------------

class TestFallbackModel:
    def test_uses_configured_fallback(self):
        cfg = types.SimpleNamespace(llm=types.SimpleNamespace(fallback_model="grok-custom-fallback"))
        assert _resolve_fallback_model(cfg) == "grok-custom-fallback"

    def test_falls_back_to_module_default_when_unset(self):
        cfg = types.SimpleNamespace(llm=types.SimpleNamespace(fallback_model=""))
        assert _resolve_fallback_model(cfg) == "grok-4.20-reasoning"

    def test_handles_missing_llm_attr(self):
        assert _resolve_fallback_model(types.SimpleNamespace()) == "grok-4.20-reasoning"


# ---------------------------------------------------------------------------
# Output validation / refusal detection
# ---------------------------------------------------------------------------

class TestValidateLLMOutput:
    def test_clean_content_returns_int(self):
        text = "Today on the show, a long and perfectly normal digest. " * 20
        result = _validate_llm_output(text, stage="digest", show_name="test")
        assert isinstance(result, int)

    def test_empty_text_returns_zero(self):
        assert _validate_llm_output("", stage="digest", show_name="test") == 0

    def test_english_refusal_raises(self):
        with pytest.raises(LLMRefusalError):
            _validate_llm_output(
                "I'm sorry, but I cannot create this podcast episode.",
                stage="podcast_script",
                show_name="test",
            )

    def test_must_decline_refusal_raises(self):
        with pytest.raises(LLMRefusalError):
            _validate_llm_output("I must decline to produce this content.", show_name="mit")

    def test_russian_refusal_raises(self):
        with pytest.raises(LLMRefusalError):
            _validate_llm_output(
                "Я не могу создать этот выпуск.", show_name="finansy_prosto"
            )

    def test_refusal_phrase_inside_long_real_content_is_not_flagged(self):
        # A genuine refusal is short; a stray phrase deep in a 4000-char
        # script must NOT trip the gate (it scans only the head of long text).
        body = "The market moved today and here is the full story. " * 90
        text = body + " She said she must decline the offer."
        # Should not raise — returns a repetition count int.
        assert isinstance(_validate_llm_output(text, stage="podcast_script", show_name="t"), int)


# ---------------------------------------------------------------------------
# Story-level duplication detection
# ---------------------------------------------------------------------------

class TestStoryDuplication:
    def test_returns_int(self):
        assert isinstance(_detect_story_duplication("short text", "Tesla"), int)

    def test_too_few_blocks_returns_zero(self):
        assert _detect_story_duplication("one line\n\ntwo line", "Tesla") == 0


# ---------------------------------------------------------------------------
# _call_grok — request shaping + response parsing (mocked, no network)
# ---------------------------------------------------------------------------

class _FakeUsage:
    prompt_tokens = 100
    completion_tokens = 50
    total_tokens = 150


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content, finish_reason="stop"):
        self.message = _FakeMessage(content)
        self.finish_reason = finish_reason


class _FakeResponse:
    def __init__(self, content, finish_reason="stop"):
        self.choices = [_FakeChoice(content, finish_reason)]
        self.usage = _FakeUsage()


class _FakeCompletions:
    def __init__(self, response, recorder):
        self._response = response
        self._recorder = recorder

    def create(self, **kwargs):
        self._recorder.update(kwargs)
        return self._response


class _FakeClient:
    def __init__(self, response, recorder):
        self.chat = types.SimpleNamespace(completions=_FakeCompletions(response, recorder))


@pytest.fixture
def fake_openai(monkeypatch):
    """Inject a fake ``openai`` module so _call_grok runs without network."""
    recorder: dict = {}
    response_holder: dict = {"resp": _FakeResponse("  generated text  ")}

    def _make_openai(*args, **kwargs):
        recorder["client_kwargs"] = kwargs
        return _FakeClient(response_holder["resp"], recorder)

    fake_mod = types.ModuleType("openai")
    fake_mod.OpenAI = _make_openai
    # Exception types referenced at import time in generator.py
    fake_mod.APITimeoutError = type("APITimeoutError", (Exception,), {})
    fake_mod.APIConnectionError = type("APIConnectionError", (Exception,), {})
    fake_mod.RateLimitError = type("RateLimitError", (Exception,), {})
    monkeypatch.setitem(sys.modules, "openai", fake_mod)
    monkeypatch.setenv("GROK_API_KEY", "test-key")
    return recorder, response_holder


class TestCallGrok:
    def test_returns_text_and_meta(self, fake_openai):
        from engine.generator import _call_grok
        recorder, _ = fake_openai
        text, meta = _call_grok("hello", model="grok-4.3")
        assert text == "generated text"  # stripped
        assert meta["model"] == "grok-4.3"
        assert meta["usage"]["total_tokens"] == 150
        # The request carried our model + the user message.
        assert recorder["model"] == "grok-4.3"
        assert recorder["messages"][-1] == {"role": "user", "content": "hello"}

    def test_system_prompt_is_prepended(self, fake_openai):
        from engine.generator import _call_grok
        recorder, _ = fake_openai
        _call_grok("body", system_prompt="be terse")
        assert recorder["messages"][0] == {"role": "system", "content": "be terse"}

    def test_missing_api_key_raises(self, fake_openai, monkeypatch):
        from engine.generator import _call_grok
        monkeypatch.delenv("GROK_API_KEY", raising=False)
        monkeypatch.delenv("XAI_API_KEY", raising=False)
        with pytest.raises(RuntimeError):
            _call_grok("hello")


class TestSpeakerLabelRepetitionSkip:
    """Plain ``Host:`` speaker labels are a dialogue-format artifact, not a
    hallucination. They must NOT inflate the suspicious-repetition count (which
    would trigger wasteful retries that shorten the episode — Models & Agents
    Ep066 flagged 'host: the' x18 and lost ~200 words to anti-repetition regens).
    Genuine topic repetition must still be caught.
    """

    def _validate(self):
        from engine.generator import _validate_llm_output
        return _validate_llm_output

    def test_host_label_bigrams_not_flagged(self):
        validate = self._validate()
        # 18 host lines that all start "Host: The" (the artifact that tripped
        # the detector) but whose remaining content is genuinely distinct, so
        # ONLY the speaker-label bigram/trigram repeats.
        topics = [
            "quantum annealing surprised everyone", "robots folded laundry quickly",
            "compilers optimized themselves overnight", "satellites mapped deep oceans",
            "drones delivered medicine remotely", "sensors detected faint tremors",
            "batteries charged within seconds", "telescopes captured distant galaxies",
            "algorithms sorted petabytes instantly", "vaccines reached rural clinics",
            "turbines harvested gentle breezes", "microscopes revealed hidden proteins",
            "printers fabricated tiny gears", "rovers climbed steep craters",
            "antennas captured weak signals", "reactors fused light isotopes",
            "cameras tracked migrating whales", "engines burned cleaner fuels",
        ]
        lines = [f"Host: The {t}." for t in topics]
        script = " ".join(lines)
        n = validate(script, stage="podcast_script", show_name="Models & Agents")
        assert n == 0, f"speaker-label phrases should not be flagged (got {n})"

    def test_genuine_repetition_still_flagged(self):
        validate = self._validate()
        # Real topic loop: "mixture of experts" repeated far above threshold,
        # NOT behind a speaker label.
        script = ("We discuss the mixture of experts approach. " * 8) + \
                 " ".join(f"Word{i} filler text here." for i in range(60))
        n = validate(script, stage="podcast_script", show_name="Models & Agents")
        assert n >= 1, "genuine repetition must still be detected"
