"""Guards for the pinned-model fallback (Sep 23 2026).

Vancouver's and Collingwood's Episode 1s, the first runs with ``llm.model:
grok-4.7`` on the digest stage, both died there: the pre-flight ping timed
out, then each digest attempt hung ~260 s until xAI dropped the connection,
three attempts, no episode. grok-4.7 had never completed a call on this
pipeline — Omni View's script-stage pin had quietly fallen back to grok-4.3
on its first run, because the script stage has a fallback and the digest
stage did not. A model experiment must not be able to cost a show its
episode, and one that fell back must be recorded as not having run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import engine.generator as gen

ROOT = Path(__file__).resolve().parent.parent


class _LLM:
    podcast_model = ""
    podcast_chain = False
    combined_generation = False
    max_tokens = 3000
    podcast_max_tokens = 5000
    digest_temperature = 0.5
    podcast_temperature = 0.7
    system_prompt_file = ""
    digest_prompt_file = ""
    podcast_prompt_file = ""
    min_digest_words = 0
    digest_expand_below_target = False

    def __init__(self, model: str):
        self.model = model


class _Cfg:
    name = "Fallback Test Show"
    slug = "vancouver"
    keywords = ()
    narrative_mode = False
    source_integrity = None
    chapters = None
    youtube = None

    def __init__(self, model: str, tmp_path: Path):
        self.llm = _LLM(model)
        p = tmp_path / "digest.txt"
        p.write_text("Write the digest for {today_str}.", encoding="utf-8")
        self.llm.digest_prompt_file = str(p)


DIGEST = ("**HOOK:** Council approved the plan.\n### Top Stories\n1. **Item one**\n"
          "   Vancouver council approved the transit plan on Tuesday.\n")


def test_the_network_default_is_the_dataclass_default():
    from engine.config import LLMConfig
    assert gen.network_default_model() == LLMConfig().model == "grok-4.3"


class TestSwitch:
    def test_a_run_on_the_default_is_left_alone(self, tmp_path, capsys):
        cfg = _Cfg("grok-4.3", tmp_path)
        assert gen.switch_to_network_default(cfg, "x") is False
        assert cfg.llm.model == "grok-4.3" and not hasattr(cfg.llm, "_pinned_model")
        assert "::warning::" not in capsys.readouterr().out

    def test_a_pinned_run_moves_to_the_default_and_says_so(self, tmp_path, capsys):
        cfg = _Cfg("grok-4.7", tmp_path)
        assert gen.switch_to_network_default(cfg, "pre-flight ping failed") is True
        assert cfg.llm.model == "grok-4.3"
        assert cfg.llm._pinned_model == "grok-4.7"
        assert "ping" in cfg.llm._model_fallback_reason
        out = capsys.readouterr().out
        assert "::warning::" in out and "did NOT run" in out

    def test_the_switch_is_sticky(self, tmp_path):
        cfg = _Cfg("grok-4.7", tmp_path)
        gen.switch_to_network_default(cfg, "first")
        # A second failure later in the run has nothing left to switch.
        assert gen.switch_to_network_default(cfg, "second") is False
        assert cfg.llm._pinned_model == "grok-4.7"


class TestDigestStageFallback:
    def _fake(self, fail_on: str):
        from openai import APIConnectionError

        calls = []

        def fake_call(prompt, **kw):
            calls.append(kw["model"])
            if kw["model"] == fail_on:
                raise APIConnectionError(request=None)
            return DIGEST, {"finish_reason": "stop", "usage": {}}
        return fake_call, calls

    def test_a_pinned_model_that_does_not_answer_costs_one_call_not_the_episode(
            self, monkeypatch, tmp_path):
        pytest.importorskip("openai")
        fake, calls = self._fake("grok-4.7")
        monkeypatch.setattr(gen, "_call_grok", fake)
        cfg = _Cfg("grok-4.7", tmp_path)
        out = gen.generate_digest({"today_str": "2026-09-23", "episode_num": 1}, cfg, tracker=None)
        assert "Council approved" in out
        # ONE attempt on the pinned model, then the default — never three stalls.
        assert calls == ["grok-4.7", "grok-4.3"]
        assert cfg.llm.model == "grok-4.3" and cfg.llm._pinned_model == "grok-4.7"

    def test_a_run_already_on_the_default_still_raises_into_the_retry(
            self, monkeypatch, tmp_path):
        pytest.importorskip("openai")
        fake, calls = self._fake("grok-4.3")
        monkeypatch.setattr(gen, "_call_grok", fake)
        monkeypatch.setattr(gen.generate_digest.retry, "sleep", lambda *_: None)
        cfg = _Cfg("grok-4.3", tmp_path)
        with pytest.raises(Exception):
            gen.generate_digest({"today_str": "2026-09-23", "episode_num": 1}, cfg, tracker=None)
        assert set(calls) == {"grok-4.3"} and len(calls) == 3


class TestRunShowWiring:
    SRC = (ROOT / "run_show.py").read_text(encoding="utf-8")

    def test_a_failed_ping_on_a_pinned_model_switches_before_the_fetch(self):
        block = self.SRC[self.SRC.index("Pre-flight LLM ping failed for model="):]
        block = block[:block.index("# Validate newsletter API key")]
        assert "switch_to_network_default(config" in block

    def test_the_fallback_is_a_metric(self):
        assert 'metrics.record("llm_model_pinned"' in self.SRC
        assert 'metrics.record("llm_model_fallback"' in self.SRC
