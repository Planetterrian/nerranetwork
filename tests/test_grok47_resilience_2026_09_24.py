"""Guards for the grok-4.7 resilience pass (PR H, 2026-09-24).

Nine of the launch cohort's first 24 episodes fell back from the pinned
grok-4.7 to grok-4.3 on ONE transient error — five connections dropped at
~260 s on a non-streaming request, three full 600 s timeouts, one pre-flight
ping run at default reasoning effort — and every fallback episode was the
thin one (0-3 claims against 8-25). Two of the drops hit the STRUCTURAL
RETRY of a good 4.7 digest and the sticky switch replaced it with a 4.3 one
(Top World Ep2: 1,548 words → 908). What binds now: pinned shows stream,
a pinned model gets one budget-gated same-model retry before the switch, a
retry of an existing digest never changes the model arm, the ping runs at
the show's own effort, and the fallback share is a dashboard metric.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import engine.generator as gen

ROOT = Path(__file__).resolve().parent.parent

COHORT = [
    "ai_chips", "mag7", "peptides", "longevity", "prediction_markets", "vancouver",
    "collingwood", "omni_view_europe", "omni_view_asia_pacific",
    "omni_view_africa_mideast", "omni_view_latam", "omni_view_north_america",
    "omni_view_world",
]
DESKS = ["omni_view_europe", "omni_view_asia_pacific", "omni_view_africa_mideast",
         "omni_view_latam", "omni_view_north_america", "omni_view_world"]


def _yaml(slug):
    return yaml.safe_load((ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# A minimal show config for generate_digest (the pinned-fallback test's shape)
# ---------------------------------------------------------------------------

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
    stream = False
    pinned_model_retries = 1

    def __init__(self, model: str):
        self.model = model


class _Cfg:
    name = "Resilience Test Show"
    slug = "omni_view_world"
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
VARS = {"today_str": "2026-09-24", "episode_num": 2}


def _connection_error():
    from openai import APIConnectionError
    return APIConnectionError(request=None)


def _timeout_error():
    import httpx
    from openai import APITimeoutError
    return APITimeoutError(request=httpx.Request("POST", "https://api.x.ai/v1/chat/completions"))


def _server_error():
    import httpx
    from openai import InternalServerError
    req = httpx.Request("POST", "https://api.x.ai/v1/chat/completions")
    return InternalServerError("degraded", response=httpx.Response(503, request=req), body=None)


def _scripted(failures):
    """A fake _call_grok that raises the queued errors first, then answers."""
    calls: list = []
    queue = list(failures)

    def fake(prompt, **kw):
        calls.append(kw["model"])
        if queue and kw["model"] == "grok-4.7":
            raise queue.pop(0)
        return DIGEST, {"finish_reason": "stop", "usage": {}}
    return fake, calls


@pytest.fixture
def quiet(monkeypatch):
    pytest.importorskip("openai")
    monkeypatch.setattr(gen, "_pinned_sleep", lambda *_: None)
    monkeypatch.setattr(gen, "_budget_remaining_fn", None)
    monkeypatch.setattr(gen.generate_digest.retry, "sleep", lambda *_: None)


# ---------------------------------------------------------------------------
# The bounded same-model retry
# ---------------------------------------------------------------------------

class TestPinnedRetry:
    def test_one_dropped_connection_is_retried_on_the_same_model(self, quiet, monkeypatch, tmp_path):
        fake, calls = _scripted([_connection_error()])
        monkeypatch.setattr(gen, "_call_grok", fake)
        cfg = _Cfg("grok-4.7", tmp_path)
        out = gen.generate_digest(VARS, cfg, tracker=None)
        assert "Council approved" in out
        assert calls == ["grok-4.7", "grok-4.7"]
        assert cfg.llm.model == "grok-4.7" and not getattr(cfg.llm, "_pinned_model", "")
        assert cfg.llm._pinned_retries == 1 and cfg.llm._pinned_recovered == 1

    def test_a_timeout_is_retried_the_same_way(self, quiet, monkeypatch, tmp_path):
        fake, calls = _scripted([_timeout_error()])
        monkeypatch.setattr(gen, "_call_grok", fake)
        cfg = _Cfg("grok-4.7", tmp_path)
        gen.generate_digest(VARS, cfg, tracker=None)
        assert calls == ["grok-4.7", "grok-4.7"] and cfg.llm.model == "grok-4.7"

    def test_two_failures_then_the_default_with_the_reason(self, quiet, monkeypatch, tmp_path):
        fake, calls = _scripted([_connection_error(), _connection_error()])
        monkeypatch.setattr(gen, "_call_grok", fake)
        cfg = _Cfg("grok-4.7", tmp_path)
        gen.generate_digest(VARS, cfg, tracker=None)
        assert calls == ["grok-4.7", "grok-4.7", "grok-4.3"]
        assert cfg.llm._pinned_model == "grok-4.7"
        assert "APIConnectionError" in cfg.llm._model_fallback_reason
        assert cfg.llm._pinned_retries == 1 and not getattr(cfg.llm, "_pinned_recovered", 0)

    def test_no_retry_when_the_pipeline_budget_cannot_carry_it(self, quiet, monkeypatch, tmp_path):
        fake, calls = _scripted([_connection_error()])
        monkeypatch.setattr(gen, "_call_grok", fake)
        monkeypatch.setattr(gen, "_budget_remaining_fn", lambda: 300.0)
        monkeypatch.setenv("NERRA_LLM_TIMEOUT_SECONDS", "600")
        cfg = _Cfg("grok-4.7", tmp_path)
        gen.generate_digest(VARS, cfg, tracker=None)
        assert calls == ["grok-4.7", "grok-4.3"]
        assert not getattr(cfg.llm, "_pinned_retries", 0)

    def test_a_5xx_switches_at_once(self, quiet, monkeypatch, tmp_path):
        fake, calls = _scripted([_server_error()])
        monkeypatch.setattr(gen, "_call_grok", fake)
        cfg = _Cfg("grok-4.7", tmp_path)
        gen.generate_digest(VARS, cfg, tracker=None)
        assert calls == ["grok-4.7", "grok-4.3"]

    def test_retries_zero_is_the_september_23_behaviour(self, quiet, monkeypatch, tmp_path):
        fake, calls = _scripted([_connection_error()])
        monkeypatch.setattr(gen, "_call_grok", fake)
        cfg = _Cfg("grok-4.7", tmp_path)
        cfg.llm.pinned_model_retries = 0
        gen.generate_digest(VARS, cfg, tracker=None)
        assert calls == ["grok-4.7", "grok-4.3"]

    def test_the_default_model_never_enters_the_pinned_path(self, quiet, monkeypatch, tmp_path):
        seen = []
        monkeypatch.setattr(gen, "_call_pinned", lambda *a, **k: seen.append(1) or (_ for _ in ()).throw(AssertionError))
        fake, calls = _scripted([])
        monkeypatch.setattr(gen, "_call_grok", fake)
        gen.generate_digest(VARS, _Cfg("grok-4.3", tmp_path), tracker=None)
        assert not seen and calls == ["grok-4.3"]

    def test_budget_unregistered_means_unlimited(self, monkeypatch):
        monkeypatch.setattr(gen, "_budget_remaining_fn", None)
        assert gen.pipeline_budget_remaining() == float("inf")
        monkeypatch.setattr(gen, "_budget_remaining_fn", lambda: 1 / 0)
        assert gen.pipeline_budget_remaining() == float("inf")

    def test_run_show_registers_its_budget_and_the_script_site_retries(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "register_pipeline_budget(_pipeline_budget_remaining)" in src
        gsrc = (ROOT / "engine" / "generator.py").read_text(encoding="utf-8")
        assert "_call_pinned(lambda: _script_call(script_model), config, \"script\")" in gsrc


# ---------------------------------------------------------------------------
# A retry never changes the model arm
# ---------------------------------------------------------------------------

class TestRetryNeverChangesArm:
    def test_a_disallowed_switch_raises_and_keeps_the_pin(self, quiet, monkeypatch, tmp_path):
        fake, calls = _scripted([_connection_error(), _connection_error()])
        monkeypatch.setattr(gen, "_call_grok", fake)
        cfg = _Cfg("grok-4.7", tmp_path)
        with pytest.raises(gen.PinnedModelUnavailable):
            gen.generate_digest(VARS, cfg, tracker=None, allow_model_switch=False)
        # the bounded retry, then the raise — and tenacity did NOT retry it
        assert calls == ["grok-4.7", "grok-4.7"]
        assert cfg.llm.model == "grok-4.7" and not getattr(cfg.llm, "_pinned_model", "")

    def test_the_exception_is_not_a_transient_class(self):
        assert not issubclass(gen.PinnedModelUnavailable, gen._TRANSIENT_ERRORS)
        assert not issubclass(gen.PinnedModelUnavailable, gen.LLMRefusalError)

    def test_run_show_structural_retry_passes_the_flag_and_keeps_the_original(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        block = src[src.index('metrics.stage("generate_digest_structural_retry")'):]
        block = block[:block.index("# Blocking lints")]
        assert "allow_model_switch=False" in block
        assert "keeping original" in block and "except Exception as exc:" in block


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------

def _chunk(text=None, finish=None, usage=None):
    choice = SimpleNamespace(delta=SimpleNamespace(content=text), finish_reason=finish)
    return SimpleNamespace(choices=[choice] if (text is not None or finish) else [], usage=usage)


_USAGE = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15,
                         prompt_tokens_details=None)


class _FakeStream:
    def __init__(self, chunks, raise_at=None, exc=None):
        self.chunks, self.raise_at, self.exc, self.closed = chunks, raise_at, exc, False

    def __iter__(self):
        for i, c in enumerate(self.chunks):
            if self.raise_at == i:
                raise self.exc
            yield c

    def close(self):
        self.closed = True


class _FakeClient:
    def __init__(self, stream):
        self.calls: list = []
        outer = self

        class _Completions:
            def create(self, **kw):
                outer.calls.append(kw)
                if kw.get("stream"):
                    return stream
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="plain"),
                                             finish_reason="stop")],
                    usage=_USAGE)
        self.chat = SimpleNamespace(completions=_Completions())


@pytest.fixture
def fake_openai(monkeypatch):
    openai = pytest.importorskip("openai")
    monkeypatch.setenv("GROK_API_KEY", "test-key")
    monkeypatch.setattr(gen, "_STREAM_DISABLED", False)
    holder = {}

    def factory(stream):
        client = _FakeClient(stream)
        holder["client"] = client
        monkeypatch.setattr(openai, "OpenAI", lambda **kw: client)
        return client
    return factory


class TestStreaming:
    def test_chunks_are_joined_and_the_call_shape_is_xais(self, fake_openai):
        import httpx
        stream = _FakeStream([_chunk("Hel"), _chunk("lo"), _chunk(" world", finish="stop"),
                              _chunk(usage=_USAGE)])
        client = fake_openai(stream)
        text, meta = gen._call_grok("p", model="grok-4.7", stream=True, timeout=600.0,
                                    reasoning_effort="low", cache_key="nerra-x")
        assert text == "Hello world"
        assert meta["finish_reason"] == "stop" and meta["usage"]["total_tokens"] == 15
        assert meta["stream"] is True and isinstance(meta["ttft_s"], float)
        kw = client.calls[0]
        assert kw["stream"] is True and kw["stream_options"] == {"include_usage": True}
        assert isinstance(kw["timeout"], httpx.Timeout)
        assert kw["extra_body"] == {"reasoning_effort": "low"}
        assert kw["extra_headers"] == {"x-grok-conv-id": "nerra-x"}
        assert stream.closed

    def test_a_non_streaming_call_is_the_old_request(self, fake_openai):
        client = fake_openai(_FakeStream([]))
        text, meta = gen._call_grok("p", model="grok-4.3", timeout=600.0)
        assert text == "plain" and "stream" not in meta
        kw = client.calls[0]
        assert "stream" not in kw and "stream_options" not in kw and "timeout" not in kw

    def test_silence_past_the_idle_timeout_is_a_timeout_error(self, fake_openai):
        import httpx
        from openai import APITimeoutError
        stream = _FakeStream([_chunk("a"), _chunk("b")], raise_at=1, exc=httpx.ReadTimeout("idle"))
        fake_openai(stream)
        with pytest.raises(APITimeoutError):
            gen._call_grok("p", model="grok-4.7", stream=True, timeout=600.0)
        assert stream.closed

    def test_a_broken_stream_is_a_connection_error(self, fake_openai):
        import httpx
        from openai import APIConnectionError
        stream = _FakeStream([_chunk("a"), _chunk("b")], raise_at=1,
                             exc=httpx.RemoteProtocolError("peer closed"))
        fake_openai(stream)
        with pytest.raises(APIConnectionError):
            gen._call_grok("p", model="grok-4.7", stream=True, timeout=600.0)

    def test_the_wall_timeout_holds_between_chunks(self, fake_openai, monkeypatch):
        from openai import APITimeoutError
        clock = {"t": 0.0}
        monkeypatch.setattr(gen.time, "monotonic", lambda: clock["t"])

        class _SlowStream(_FakeStream):
            def __iter__(self):
                yield _chunk("a")
                clock["t"] = 5000.0  # the next chunk arrives past the 600 s wall
                yield _chunk("b")
                yield _chunk("c", finish="stop")

        stream = _SlowStream([])
        fake_openai(stream)
        with pytest.raises(APITimeoutError):
            gen._call_grok("p", model="grok-4.7", stream=True, timeout=600.0)
        assert stream.closed

    def test_a_rejected_stream_request_falls_back_to_the_old_call_for_the_run(
            self, fake_openai, monkeypatch):
        import httpx
        from openai import BadRequestError
        monkeypatch.setattr(gen, "_STREAM_DISABLED", False)
        req = httpx.Request("POST", "https://api.x.ai/v1/chat/completions")
        resp = httpx.Response(400, request=req)
        client = fake_openai(_FakeStream([]))
        calls = client.calls

        class _Rejecting:
            def create(self, **kw):
                calls.append(kw)
                if kw.get("stream"):
                    raise BadRequestError("stream_options not supported", response=resp, body=None)
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="plain"),
                                             finish_reason="stop")], usage=_USAGE)
        client.chat = SimpleNamespace(completions=_Rejecting())
        text, meta = gen._call_grok("p", model="grok-4.7", stream=True, timeout=600.0)
        assert text == "plain" and "stream" not in meta
        assert [bool(c.get("stream")) for c in calls] == [True, False]
        # the flag stops the next call from trying to stream at all
        gen._call_grok("p", model="grok-4.7", stream=True, timeout=600.0)
        assert [bool(c.get("stream")) for c in calls] == [True, False, False]
        assert gen._STREAM_DISABLED is True

    def test_a_streamed_5xx_still_propagates(self, fake_openai, monkeypatch):
        import httpx
        from openai import InternalServerError
        monkeypatch.setattr(gen, "_STREAM_DISABLED", False)
        req = httpx.Request("POST", "https://api.x.ai/v1/chat/completions")
        client = fake_openai(_FakeStream([]))

        class _Failing:
            def create(self, **kw):
                raise InternalServerError("degraded", response=httpx.Response(503, request=req), body=None)
        client.chat = SimpleNamespace(completions=_Failing())
        with pytest.raises(InternalServerError):
            gen._call_grok("p", model="grok-4.7", stream=True, timeout=600.0)
        assert gen._STREAM_DISABLED is False

    def test_idle_timeout_is_env_tunable(self, monkeypatch):
        monkeypatch.delenv("NERRA_LLM_STREAM_IDLE_SECONDS", raising=False)
        assert gen._stream_idle_timeout_s() == 180.0
        monkeypatch.setenv("NERRA_LLM_STREAM_IDLE_SECONDS", "45")
        assert gen._stream_idle_timeout_s() == 45.0

    def test_the_digest_records_its_time_to_first_token(self, quiet, monkeypatch, tmp_path):
        def fake(prompt, **kw):
            assert kw.get("stream") is True
            return DIGEST, {"finish_reason": "stop", "usage": {}, "stream": True, "ttft_s": 4.2}
        monkeypatch.setattr(gen, "_call_grok", fake)
        cfg = _Cfg("grok-4.7", tmp_path)
        cfg.llm.stream = True
        gen.generate_digest(VARS, cfg, tracker=None)
        assert cfg.llm._last_digest_ttft_s == 4.2
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert '"llm_digest_ttft_s"' in src and '"llm_pinned_retries"' in src


# ---------------------------------------------------------------------------
# Config: the cohort streams, the established shows do not
# ---------------------------------------------------------------------------

class TestConfig:
    def test_dataclass_defaults(self):
        from engine.config import LLMConfig
        assert LLMConfig().stream is False and LLMConfig().pinned_model_retries == 1

    @pytest.mark.parametrize("slug", COHORT)
    def test_every_cohort_show_streams_and_loads(self, slug):
        from engine.config import load_config
        assert _yaml(slug)["llm"]["stream"] is True
        cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
        assert cfg.llm.stream is True and cfg.llm.model == "grok-4.7"
        assert cfg.llm.reasoning_effort == "low"

    def test_no_established_show_streams(self):
        from engine.config import load_config
        for p in sorted((ROOT / "shows").glob("*.yaml")):
            if p.name.startswith("_") or p.stem in COHORT:
                continue
            raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            assert "stream" not in (raw.get("llm") or {}), p.name
        assert load_config(ROOT / "shows" / "tesla.yaml").llm.stream is False

    @pytest.mark.parametrize("slug", DESKS)
    def test_progress_watch_is_exempt_from_the_overlap_dedup(self, slug):
        from engine.config import load_config
        assert _yaml(slug)["digest_overlap_exempt_sections"] == ["Progress Watch"]
        assert load_config(ROOT / "shows" / f"{slug}.yaml").digest_overlap_exempt_sections == ["Progress Watch"]

    def test_the_ping_runs_at_the_shows_effort_with_two_attempts_on_a_pin(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        block = src[src.index("# Pre-flight LLM ping"):src.index("# Validate newsletter API key")]
        assert "reasoning_effort=_llm_reasoning_effort(config)" in block
        assert "_ping_attempts = 2 if _is_pinned(config) else 1" in block
        assert "switch_to_network_default(config" in block


# ---------------------------------------------------------------------------
# The fallback share is a metric with a consumer
# ---------------------------------------------------------------------------

def _seed(root: Path, slug: str, episodes):
    d = root / "digests" / slug
    d.mkdir(parents=True)
    day = dt.date.today().strftime("%Y%m%d")
    for n, counters in episodes:
        (d / f"Show_Ep{n:03d}_{day}.md").write_text("# x\n", encoding="utf-8")
        (d / f"metrics_ep{n:03d}.json").write_text(json.dumps({"counters": counters}), encoding="utf-8")


class TestDashboardMetric:
    def test_share_and_recoveries_on_pinned_runs_only(self, tmp_path):
        import scripts.generate_dashboard as gd
        pinned = {"llm_digest_model": "grok-4.7"}
        fell = {"llm_digest_model": "grok-4.3", "llm_model_pinned": "grok-4.7",
                "llm_model_fallback": "digest call failed: APIConnectionError"}
        recovered = {"llm_digest_model": "grok-4.7", "llm_pinned_retries": 1, "llm_pinned_recovered": 1}
        _seed(tmp_path, "cohort", [(1, pinned), (2, fell), (3, recovered), (4, pinned), (5, fell)])
        _seed(tmp_path, "established", [(600, {"llm_digest_model": "grok-4.3"})] * 1)
        out = gd._pinned_model_metrics(tmp_path, dt.date.today())
        assert out == {"llm_pinned_fallback_share_7d": 0.4, "llm_pinned_recovered_7d": 1,
                       "llm_pinned_episodes_7d": 5}

    def test_null_under_five_pinned_episodes_never_zero(self, tmp_path):
        import scripts.generate_dashboard as gd
        _seed(tmp_path, "cohort", [(1, {"llm_digest_model": "grok-4.7"})] * 1)
        out = gd._pinned_model_metrics(tmp_path, dt.date.today())
        assert out["llm_pinned_fallback_share_7d"] is None

    def test_credit_files_are_found_padded_or_not(self, tmp_path):
        import scripts.generate_dashboard as gd
        (tmp_path / "credit_usage_2026-09-23_ep001.json").write_text("{}")
        (tmp_path / "credit_usage_2026-09-24_ep1.json").write_text("{}")
        (tmp_path / "credit_usage_2026-09-24_ep010.json").write_text("{}")
        assert [p.name for p in gd._credit_files_for_episode(tmp_path, 1)] == [
            "credit_usage_2026-09-23_ep001.json", "credit_usage_2026-09-24_ep1.json"]
        assert gd._credit_files_for_episode(tmp_path, 10)[0].name.endswith("ep010.json")
        src = (ROOT / "scripts" / "generate_dashboard.py").read_text(encoding="utf-8")
        assert 'glob(f"credit_usage_*_ep{' not in src

    def test_the_register_names_the_metric(self):
        import scripts.generate_dashboard as gd
        data = yaml.safe_load((ROOT / "docs" / "experiments.yaml").read_text(encoding="utf-8"))
        entry = next(e for e in data["experiments"] if e["id"] == "grok-47-resilience-2026-09-24")
        assert entry["metric"] == "llm_pinned_fallback_share_7d"
        assert "llm_pinned_fallback_share_7d" in gd._experiment_live_metrics(ROOT)

    def test_the_trial_report_carries_fallbacks_and_ttft(self):
        import scripts.model_trial_report as mtr
        src = (ROOT / "scripts" / "model_trial_report.py").read_text(encoding="utf-8")
        assert "pinned-model fallbacks" in src and "time-to-first-token" in src
        rows = mtr.collect(ROOT / "digests" / "omni_view_world")
        assert any(r["fallback"] for r in rows)


# ---------------------------------------------------------------------------
# The AI Chips lint judges site items only
# ---------------------------------------------------------------------------

class TestDcLintSitesOnly:
    def test_committed_ep1_to_ep3_no_longer_fire(self):
        from engine.digest_lint import lint_dc_items_unlabelled
        files = sorted(p for p in (ROOT / "digests" / "ai_chips").glob("AI_Chips_Ep00[123]_*.md")
                       if "_reader" not in p.name)
        if len(files) < 3:
            pytest.skip("committed digests not present")
        for f in files:
            finding = lint_dc_items_unlabelled(f.read_text(encoding="utf-8"))
            assert finding is not None and not finding.note, f.name

    def test_two_unlabelled_sites_fire_and_non_sites_never_count(self):
        from engine.digest_lint import dc_items_unlabelled, lint_dc_items_unlabelled
        digest = (
            "**HOOK:** x\n### Data Centres & Power\n"
            "1. **A 300 MW campus in Ohio: Outlet**\n   Acme will build 300 MW near Columbus. Source: [a.com](https://a.com/1)\n\n"
            "2. **Beta breaks ground in Texas: Outlet**\n   Beta broke ground on a 120-acre site. Source: [b.com](https://b.com/2)\n\n"
            "3. **A whitepaper on 800 VDC: Outlet**\n   A power-architecture discussion, not a named campus. Source: [c.com](https://c.com/3)\n\n"
            "### On the Horizon\n1. **x**\n   y\n")
        bad = dc_items_unlabelled(digest)
        assert len(bad) == 2 and not any("800 VDC" in b for b in bad)
        finding = lint_dc_items_unlabelled(digest)
        assert finding.note and finding.metrics == {"dc_items_unlabelled": 2, "dc_items_total": 3,
                                                    "dc_items_sites": 2}

    def test_one_ambiguous_site_item_is_not_a_finding(self):
        from engine.digest_lint import lint_dc_items_unlabelled
        digest = ("**HOOK:** x\n### Data Centres & Power\n"
                  "1. **Labs seek 20-30MW deployments: Outlet**\n   Two labs are seeking 20-30 MW sites. Source: [a.com](https://a.com/1)\n\n"
                  "2. **A product launch: Outlet**\n   An interconnect. Source: [b.com](https://b.com/2)\n")
        assert not lint_dc_items_unlabelled(digest).note

    def test_a_labelled_site_passes(self):
        from engine.digest_lint import dc_items_unlabelled
        digest = ("### Data Centres & Power\n1. **Site: Outlet**\n   The 200 MW site is under construction in Poland. Source: [a.com](https://a.com/1)\n")
        assert dc_items_unlabelled(digest) == []


class TestDocs:
    def test_playbook_and_claude_md_carry_the_rule(self):
        pb = (ROOT / "docs" / "model_upgrade_playbook.md").read_text(encoding="utf-8")
        assert "### 7." in pb and "allow_model_switch=False" in pb and "llm.stream" in pb
        cm = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        assert "_call_pinned" in cm and "PinnedModelUnavailable" in cm

    def test_ledgers_record_the_pass(self):
        for slug in ["omni_view_world", "omni_view_asia_pacific", "prediction_markets", "peptides", "ai_chips"]:
            text = (ROOT / "docs" / "reviews" / "ledger" / f"{slug}.yaml").read_text(encoding="utf-8")
            assert "grok-47-resilience-2026-09-24" in text, slug
            yaml.safe_load(text)

    def test_the_pass_is_dated_in_the_register(self):
        data = yaml.safe_load((ROOT / "docs" / "experiments.yaml").read_text(encoding="utf-8"))
        entry = next(e for e in data["experiments"] if e["id"] == "grok-47-resilience-2026-09-24")
        assert str(entry["readout"]) >= "2026-10-08" and re.search(r"stream", entry["notes"])
