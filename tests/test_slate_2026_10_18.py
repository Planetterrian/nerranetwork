"""Oct 18 2026 slate: what stopped the shows.

1. One UC sentence ("Lark et al.,") failed the book-release corpus guard,
   which ran in every show's smoke step, so every show after UC died.
2. Fascinating Frontiers died on xAI's "model is currently at capacity"
   arriving as an error event INSIDE the stream — the bare ``APIError``,
   which no retry set names.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

openai = pytest.importorskip("openai")

from engine import generator as G  # noqa: E402


class TestSmokeStep:
    def test_no_corpus_scan_of_other_shows_in_the_smoke_step(self):
        wf = (ROOT / ".github" / "workflows" / "run-show.yml").read_text(encoding="utf-8")
        step = wf[wf.index("- name: Run smoke tests"):]
        step = step[:step.index("- name:", 10)]
        command = step[step.index("python -m pytest"):]
        assert "test_book_release_pass.py" not in command

    def test_et_al_is_not_a_seam(self):
        sys.path.insert(0, str(ROOT / "tests"))
        import test_book_release_pass as T
        assert {"al", "e.g", "i.e", "inc"} <= T._ABBREVIATIONS


class _FakeStream:
    def __init__(self, exc):
        self._exc = exc

    def __iter__(self):
        raise self._exc

    def close(self):
        pass


class _FakeClient:
    def __init__(self, exc):
        self.chat = type("C", (), {})()
        self.chat.completions = type("X", (), {})()
        self.chat.completions.create = lambda **kw: _FakeStream(exc)


def _event_error(message):
    httpx = G.sdk_httpx()
    req = httpx.Request("POST", "https://api.x.ai/v1/chat/completions")
    return openai.APIError(message, req, body=None)


class TestStreamErrorEvents:
    def _read(self, exc):
        G._stream_completion(_FakeClient(exc), {"model": "m", "messages": []},
                             wall_timeout=60, model="m")

    def test_capacity_event_is_a_rate_limit(self):
        with pytest.raises(openai.RateLimitError):
            self._read(_event_error(
                "The model is currently at capacity due to high demand. "
                "Please try again in a few minutes"))

    def test_other_event_is_a_server_error(self):
        with pytest.raises(openai.InternalServerError):
            self._read(_event_error("internal error"))

    def test_capacity_is_retried_by_the_capacity_backoff(self):
        assert openai.RateLimitError in G._RATE_LIMIT_ERRORS
        assert openai.InternalServerError in G._MODEL_UNAVAILABLE_ERRORS

    def test_status_errors_pass_through_unchanged(self):
        httpx = G.sdk_httpx()
        req = httpx.Request("POST", "https://api.x.ai/v1/chat/completions")
        with pytest.raises(openai.APITimeoutError):
            self._read(openai.APITimeoutError(request=req))
