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
        monkeypatch.setattr(gen, "_pinned_sleep", lambda *_: None)
        # Any test that imports run_show registers its pipeline budget
        # (900 s default, counted from import), so a long suite would read
        # "no room for a retry" here — the budget gate has its own guards.
        monkeypatch.setattr(gen, "_budget_remaining_fn", None)
        cfg = _Cfg("grok-4.7", tmp_path)
        out = gen.generate_digest({"today_str": "2026-09-23", "episode_num": 1}, cfg, tracker=None)
        assert "Council approved" in out
        # Sep 24 2026: ONE bounded same-model retry on a dropped connection
        # (a ~260 s per-request accident, not a dead model), then the
        # default — never three stalls. tests/test_grok47_resilience_2026_09_24.py
        # covers the budget gate, the 5xx no-retry and retries=0.
        assert calls == ["grok-4.7", "grok-4.7", "grok-4.3"]
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


# ---------------------------------------------------------------------------
# Omni View Europe Ep1 (2026-09-23): the digest call on grok-4.7 answered
# "503 — the model's availability is currently degraded". A 5xx is an
# InternalServerError, not one of the transient classes the fallback caught,
# so the run died with grok-4.3 one exception class away. The script stage had
# no fallback at all for a whole-show pin.
# ---------------------------------------------------------------------------

def _server_error():
    import httpx
    from openai import InternalServerError

    req = httpx.Request("POST", "https://api.x.ai/v1/chat/completions")
    resp = httpx.Response(503, request=req)
    return InternalServerError("Service temporarily unavailable", response=resp, body=None)


class TestServerErrorFallback:
    def test_a_503_on_the_pinned_digest_model_falls_back(self, monkeypatch, tmp_path):
        pytest.importorskip("openai")
        calls = []

        def fake(prompt, **kw):
            calls.append(kw["model"])
            if kw["model"] == "grok-4.7":
                raise _server_error()
            return DIGEST, {"finish_reason": "stop", "usage": {}}

        monkeypatch.setattr(gen, "_call_grok", fake)
        cfg = _Cfg("grok-4.7", tmp_path)
        out = gen.generate_digest({"today_str": "2026-09-23", "episode_num": 1}, cfg, tracker=None)
        assert "Council approved" in out
        assert calls == ["grok-4.7", "grok-4.3"]
        assert "InternalServerError" in cfg.llm._model_fallback_reason

    def test_a_503_on_the_default_still_fails_loudly(self, monkeypatch, tmp_path):
        pytest.importorskip("openai")

        def fake(prompt, **kw):
            raise _server_error()

        monkeypatch.setattr(gen, "_call_grok", fake)
        cfg = _Cfg("grok-4.3", tmp_path)
        with pytest.raises(Exception):
            gen.generate_digest({"today_str": "2026-09-23", "episode_num": 1}, cfg, tracker=None)

    def test_a_5xx_is_not_added_to_the_retry_set(self):
        # Retrying a degraded model three times burns the run's budget; the
        # wider set is for the SWITCH only.
        pytest.importorskip("openai")
        from openai import InternalServerError
        assert InternalServerError not in gen._TRANSIENT_ERRORS
        assert InternalServerError in gen._MODEL_UNAVAILABLE_ERRORS


class TestScriptStageFallback:
    VARS = {"episode_num": 50, "digest": "body", "today_str": "x",
            "hook": "h", "intro_line": "i", "closing_block": "c",
            "tone_hint": "t", "cold_open_spec": "", "delivery_spec": "",
            "narrative_memory_section": "", "nerra_network_context": "",
            "tesla_narrative_status_block": "",
            "tesla_performance_signals_block": "",
            "tesla_theme_context_block": ""}

    def _cfg(self, model):
        from engine.config import load_config
        cfg = load_config(ROOT / "shows" / "tesla.yaml")
        cfg.llm.model = model
        cfg.llm.podcast_model = ""
        cfg.llm.podcast_chain = False
        return cfg

    def test_a_whole_show_pin_that_fails_at_the_script_falls_back(self, monkeypatch):
        pytest.importorskip("openai")
        seen = []

        def fake(prompt, model=None, **kw):
            seen.append(model)
            if model == "grok-4.7":
                raise _server_error()
            return "word " * 500, {"finish_reason": "stop"}

        monkeypatch.setattr(gen, "_call_grok", fake)
        monkeypatch.setattr(gen, "_validate_llm_output", lambda *a, **k: 0)
        cfg = self._cfg("grok-4.7")
        gen.generate_podcast_script(dict(self.VARS), cfg)
        assert seen[:2] == ["grok-4.7", "grok-4.3"]
        assert cfg.llm._pinned_model == "grok-4.7"

    def test_a_non_availability_error_on_the_pin_still_raises(self, monkeypatch):
        def fake(prompt, model=None, **kw):
            raise KeyError("prompt bug")

        monkeypatch.setattr(gen, "_call_grok", fake)
        cfg = self._cfg("grok-4.7")
        with pytest.raises(KeyError):
            gen.generate_podcast_script(dict(self.VARS), cfg)
        assert cfg.llm.model == "grok-4.7"


# ---------------------------------------------------------------------------
# Omni View Europe Ep1: the RSS fetch returned 21 s after run_show's 120 s wait
# expired. The ThreadPoolExecutor's exit joins the worker anyway, so the run
# waited for the whole fetch, then discarded 425 articles and went on with 8 X
# posts. A slow fetch now gets a grace period.
# ---------------------------------------------------------------------------

class TestFetchGracePeriod:
    def test_a_slow_fetch_is_waited_for_not_discarded(self):
        import time
        from concurrent.futures import ThreadPoolExecutor
        import run_show

        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(lambda: (time.sleep(0.3), ["article"])[1])
            got = run_show._await_fetch(fut, "RSS fetch", first_wait=0.05, grace=5)
        assert got == ["article"]

    def test_a_fetch_past_the_grace_still_fails(self):
        import time
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FTimeout
        import run_show

        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(time.sleep, 0.5)
            with pytest.raises(FTimeout):
                run_show._await_fetch(fut, "RSS fetch", first_wait=0.05, grace=0.05)

    def test_both_fetches_use_it_and_the_error_names_its_type(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert '_await_fetch(fetch_future, "RSS fetch")' in src
        assert '_await_fetch(x_fetch_future, "X account fetch")' in src
        assert "fetch_future.result(timeout=120)" not in src
        # A timeout's message is empty: the log line must carry the type.
        assert 'logger.error("RSS fetch failed: %s: %s", type(exc).__name__, exc)' in src
