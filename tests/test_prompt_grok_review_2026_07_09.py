"""Drift guards for the July 9 2026 prompt + Grok API / Voice review.

See ``docs/reviews/prompt_grok_review_2026_07_09.md``.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SHOWS = ROOT / "shows"


# ---------------------------------------------------------------------------
# Prompt-cache sticky routing
# ---------------------------------------------------------------------------

class _FakeUsageDetails:
    def __init__(self, cached_tokens=0):
        self.cached_tokens = cached_tokens


class _FakeUsage:
    def __init__(self, cached=0):
        self.prompt_tokens = 100
        self.completion_tokens = 50
        self.total_tokens = 150
        self.prompt_tokens_details = _FakeUsageDetails(cached)


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content, finish_reason="stop"):
        self.message = _FakeMessage(content)
        self.finish_reason = finish_reason


class _FakeResponse:
    def __init__(self, content="ok", cached=0):
        self.choices = [_FakeChoice(content)]
        self.usage = _FakeUsage(cached)


class _FakeCompletions:
    def __init__(self, response, recorder):
        self._response = response
        self._recorder = recorder

    def create(self, **kwargs):
        self._recorder.update(kwargs)
        return self._response


class _FakeClient:
    def __init__(self, response, recorder):
        self.chat = SimpleNamespace(
            completions=_FakeCompletions(response, recorder)
        )


@pytest.fixture
def fake_openai_cache(monkeypatch):
    recorder: dict = {}
    response_holder = {"resp": _FakeResponse("  cached text  ", cached=40)}

    def _make_openai(*args, **kwargs):
        recorder["client_kwargs"] = kwargs
        return _FakeClient(response_holder["resp"], recorder)

    fake_mod = types.ModuleType("openai")
    fake_mod.OpenAI = _make_openai
    fake_mod.APITimeoutError = type("APITimeoutError", (Exception,), {})
    fake_mod.APIConnectionError = type("APIConnectionError", (Exception,), {})
    fake_mod.RateLimitError = type("RateLimitError", (Exception,), {})
    monkeypatch.setitem(sys.modules, "openai", fake_mod)
    monkeypatch.setenv("GROK_API_KEY", "test-key")
    return recorder, response_holder


class TestPromptCacheRouting:
    def test_show_cache_key_format(self):
        from engine.generator import _show_cache_key

        cfg = SimpleNamespace(slug="tesla")
        assert _show_cache_key(cfg) == "nerra-tesla"
        assert _show_cache_key(SimpleNamespace(slug="")) is None
        assert _show_cache_key(SimpleNamespace()) is None

    def test_call_grok_sends_x_grok_conv_id(self, fake_openai_cache):
        from engine.generator import _call_grok

        recorder, _ = fake_openai_cache
        text, meta = _call_grok(
            "hello", model="grok-4.3", cache_key="nerra-tesla",
        )
        assert text == "cached text"
        assert recorder.get("extra_headers", {}).get("x-grok-conv-id") == (
            "nerra-tesla"
        )
        assert meta["cache_key"] == "nerra-tesla"
        assert meta["usage"]["cached_tokens"] == 40

    def test_call_grok_omits_header_without_cache_key(self, fake_openai_cache):
        from engine.generator import _call_grok

        recorder, _ = fake_openai_cache
        _call_grok("hello", model="grok-4.3")
        assert "extra_headers" not in recorder

    def test_record_llm_usage_tracks_cached_tokens(self):
        from engine.tracking import create_tracker, record_llm_usage

        tracker = create_tracker("Tesla Shorts Time", 1)
        record_llm_usage(
            tracker, "x_thread_generation", 100, 50,
            model="grok-4.3", cached_tokens=40,
        )
        step = tracker["services"]["grok_api"]["x_thread_generation"]
        assert step["cached_tokens"] == 40
        assert tracker["services"]["grok_api"]["cached_tokens"] == 40


# ---------------------------------------------------------------------------
# Grok TTS speed passthrough (single-voice path)
# ---------------------------------------------------------------------------

class TestGrokTtsSpeedPassthrough:
    def test_speak_with_grok_signature_accepts_speed(self):
        import inspect
        from engine.tts import _speak_with_grok

        params = inspect.signature(_speak_with_grok).parameters
        assert "speed" in params
        assert params["speed"].default == 1.0

    def test_synthesize_forwards_speed_to_grok(self, monkeypatch, tmp_path):
        """``synthesize(provider='grok', speed=…)`` must reach ``_speak_with_grok``."""
        from engine import tts as tts_mod

        captured = {}

        def _fake_speak(*args, **kwargs):
            captured.update(kwargs)
            Path(args[2]).write_bytes(b"fake")

        monkeypatch.setattr(tts_mod, "_speak_with_grok", _fake_speak)
        out = tmp_path / "out.mp3"
        tts_mod.synthesize(
            "hello world",
            "kdif6sqjcyiq",
            out,
            api_key="k",
            provider="grok",
            speed=1.05,
        )
        assert captured.get("speed") == 1.05


# ---------------------------------------------------------------------------
# Russian max_chars alignment + weekly newsletter wording
# ---------------------------------------------------------------------------

class TestRussianMaxChars:
    def test_russian_shows_use_network_max_chars(self):
        for slug in ("finansy_prosto", "privet_russian"):
            data = yaml.safe_load(
                (SHOWS / f"{slug}.yaml").read_text(encoding="utf-8")
            ) or {}
            assert (data.get("tts") or {}).get("max_chars") == 14000, (
                f"{slug}.yaml: tts.max_chars must be 14000 so long scripts "
                "keep the single-call <fast> wrap (landmine #17)"
            )


class TestWeeklyNewsletterWording:
    def test_spacex_weekly_is_newsletter_not_recap_edition(self):
        text = (SHOWS / "prompts" / "spacex_weekly.txt").read_text(
            encoding="utf-8"
        )
        assert "weekly recap edition" not in text.lower()
        assert "newsletter" in text.lower()

    def test_weekly_template_is_newsletter_not_recap_edition(self):
        text = (SHOWS / "templates" / "weekly.txt.template").read_text(
            encoding="utf-8"
        )
        assert "weekly recap edition" not in text.lower()
        assert "newsletter" in text.lower()


class TestAntiRefusalGeneric:
    def test_anti_refusal_not_finance_only(self):
        src = (ROOT / "engine" / "generator.py").read_text(encoding="utf-8")
        assert "2-3 financial concepts" not in src
        assert "topic domain" in src


class TestReviewDocExists:
    def test_review_doc_present(self):
        path = ROOT / "docs" / "reviews" / "prompt_grok_review_2026_07_09.md"
        assert path.is_file()
        body = path.read_text(encoding="utf-8")
        assert "x-grok-conv-id" in body
        assert "landmine #17" in body
