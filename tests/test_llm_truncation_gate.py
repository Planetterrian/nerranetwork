"""Drift guard for the May 7 2026 fix to the LLM truncation warning.

Operator caught the pre-flight LLM ping (10-token completion against
the configured model, used as a connectivity / API-key health check)
firing a WARNING-level log message every single run::

    LLM response truncated (finish_reason=length, max_tokens=10) —
    output may end mid-sentence

That's expected behaviour — the caller asked for 10 tokens and got 10.
The warning was fully informative on a 4000-token digest call but
pure noise on the 10-token ping. Suppressing tiny-budget calls keeps
the noise out of CI logs without losing the legitimate signal.

The fix in ``engine.generator._call_grok`` gates the WARN on
``max_tokens >= 200`` — well below any digest / podcast call (smallest
takes 4000+) but above every health-check / classifier path.
"""

from __future__ import annotations

import logging
import sys
import types
from types import SimpleNamespace
from unittest.mock import patch

import pytest


def _build_fake_response(*, content: str, finish_reason: str):
    """Build a stand-in for OpenAI's chat.completions response shape."""
    choice = SimpleNamespace(
        message=SimpleNamespace(content=content),
        finish_reason=finish_reason,
    )
    return SimpleNamespace(choices=[choice], usage=None)


def _call_with(max_tokens: int, finish_reason: str, caplog):
    """Drive ``_call_grok`` with a stubbed OpenAI client and capture logs."""
    from engine import generator as g

    fake_response = _build_fake_response(
        content="ok", finish_reason=finish_reason,
    )

    class _FakeCompletions:
        def create(self, **kwargs):
            return fake_response

    class _FakeChat:
        def __init__(self):
            self.completions = _FakeCompletions()

    class _FakeClient:
        def __init__(self, *_, **__):
            self.chat = _FakeChat()

    # ``openai`` is a runtime dependency the test env doesn't install
    # (``pip install -r requirements.txt`` is skipped during pytest).
    # Inject a fake module into sys.modules so the lazy
    # ``from openai import OpenAI`` inside _call_grok succeeds.
    fake_module = types.ModuleType("openai")
    fake_module.OpenAI = _FakeClient
    with patch.dict(sys.modules, {"openai": fake_module}), \
         patch.object(g, "_get_api_key", return_value="test-key"):
        caplog.set_level(logging.WARNING, logger="engine.generator")
        text, meta = g._call_grok(
            prompt="ping",
            model="grok-4.3",
            temperature=0.0,
            max_tokens=max_tokens,
        )
    # Snapshot the records list — caplog.records is a live reference
    # that gets shared across calls inside one test (caplog.clear()
    # mutates the same list object).
    return text, meta, list(caplog.records)


class TestTruncationWarningGate:

    def test_preflight_ping_does_not_warn(self, caplog):
        """max_tokens=10 (pre-flight ping) → no WARN even when the
        response trips finish_reason=length."""
        _, _, records = _call_with(
            max_tokens=10, finish_reason="length", caplog=caplog,
        )
        truncation_warns = [
            r for r in records
            if r.levelno == logging.WARNING
            and "LLM response truncated" in r.getMessage()
        ]
        assert truncation_warns == [], (
            f"Pre-flight ping should be silent on truncation, got: "
            f"{[r.getMessage() for r in truncation_warns]}"
        )

    def test_real_completion_still_warns(self, caplog):
        """A genuine digest-sized call (max_tokens=4000) MUST still
        WARN when finish_reason=length — that signals real content
        loss the operator needs to see."""
        _, _, records = _call_with(
            max_tokens=4000, finish_reason="length", caplog=caplog,
        )
        truncation_warns = [
            r for r in records
            if r.levelno == logging.WARNING
            and "LLM response truncated" in r.getMessage()
        ]
        assert len(truncation_warns) == 1, (
            f"Real completion should warn on truncation; got "
            f"{len(truncation_warns)} warning(s)."
        )

    def test_threshold_boundary_at_200(self, caplog):
        """The gate is ``max_tokens >= 200``. Confirm 200 warns and 199
        doesn't, so a future ``> 200`` typo doesn't break the loud
        path silently."""
        from engine import generator as g

        # 199 → silent
        _, _, records_199 = _call_with(
            max_tokens=199, finish_reason="length", caplog=caplog,
        )
        # Need to clear caplog between calls.
        caplog.clear()
        # 200 → warns
        _, _, records_200 = _call_with(
            max_tokens=200, finish_reason="length", caplog=caplog,
        )
        warns_199 = [
            r for r in records_199
            if r.levelno == logging.WARNING
            and "LLM response truncated" in r.getMessage()
        ]
        warns_200 = [
            r for r in records_200
            if r.levelno == logging.WARNING
            and "LLM response truncated" in r.getMessage()
        ]
        assert warns_199 == []
        assert len(warns_200) == 1

    def test_normal_finish_reason_never_warns(self, caplog):
        """``finish_reason='stop'`` is the happy path — no warning
        regardless of max_tokens. Pin the gate doesn't accidentally
        warn on completed responses."""
        _, _, records = _call_with(
            max_tokens=4000, finish_reason="stop", caplog=caplog,
        )
        truncation_warns = [
            r for r in records
            if r.levelno == logging.WARNING
            and "LLM response truncated" in r.getMessage()
        ]
        assert truncation_warns == []
