"""Guards for the Oct 11 2026 script-stage model moves (operator-directed).

Unintended Consequences and First Principles write their SCRIPT on grok-4.7
at low effort; Planetterrian writes its script on grok-4.6. Every digest stays
on grok-4.3, every pinned arm streams (playbook rule 7), and a failed arm
falls back to the digest model for that episode at that model's own effort.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.config import load_config  # noqa: E402

TESLA_VARS = {
    "episode_num": 50, "digest": "body", "today_str": "x", "hook": "h",
    "intro_line": "i", "closing_block": "c", "tone_hint": "t",
    "cold_open_spec": "", "delivery_spec": "", "narrative_memory_section": "",
    "nerra_network_context": "", "tesla_narrative_status_block": "",
    "tesla_performance_signals_block": "", "tesla_theme_context_block": "",
}


class TestArms:
    @pytest.mark.parametrize("slug", ["unintended_consequences", "first_principles"])
    def test_narrative_scripts_on_47_low_effort(self, slug):
        cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
        assert cfg.llm.podcast_model == "grok-4.7"
        assert cfg.llm.podcast_reasoning_effort == "low"
        assert cfg.llm.stream is True
        assert cfg.llm.model == "grok-4.3", "the digest never follows the script arm"
        assert not cfg.llm.reasoning_effort, "the digest's effort is unchanged"

    def test_planetterrian_script_on_46(self):
        cfg = load_config(ROOT / "shows" / "planetterrian.yaml")
        assert cfg.llm.podcast_model == "grok-4.6"
        assert cfg.llm.stream is True
        assert cfg.llm.model == "grok-4.3"

    @pytest.mark.parametrize("slug", ["tesla", "fascinating_frontiers"])
    def test_flagship_scripts_on_46(self, slug):
        cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
        assert cfg.llm.podcast_model == "grok-4.6"
        assert cfg.llm.stream is True
        assert cfg.llm.model == "grok-4.3"

    def test_registered(self):
        reg = yaml.safe_load((ROOT / "docs" / "experiments.yaml").read_text(encoding="utf-8"))
        ids = {e["id"] for e in reg["experiments"]}
        assert {"narrative-script-grok47-2026-10-11",
                "planetterrian-script-grok46-2026-10-11",
                "flagship-script-grok46-2026-10-11"} <= ids


class TestScriptEffort:
    def _cfg(self):
        cfg = load_config(ROOT / "shows" / "tesla.yaml")
        cfg.llm.podcast_chain = False
        cfg.llm.podcast_model = "grok-4.7"
        cfg.llm.podcast_reasoning_effort = "low"
        cfg.llm.stream = True
        return cfg

    def test_effort_applies_to_the_override_only(self):
        from engine.generator import _script_reasoning_effort
        cfg = self._cfg()
        assert _script_reasoning_effort(cfg, "grok-4.7") == "low"
        assert _script_reasoning_effort(cfg, "grok-4.3") is None
        cfg.llm.podcast_reasoning_effort = ""
        assert _script_reasoning_effort(cfg, "grok-4.7") is None

    def test_script_call_sends_low_effort_and_streams(self, monkeypatch):
        from engine import generator
        cfg = self._cfg()
        seen = []

        def _fake(prompt, model=None, reasoning_effort=None, stream=False, **kw):
            seen.append((model, reasoning_effort, stream))
            return "word " * 500, {"finish_reason": "stop"}

        monkeypatch.setattr(generator, "_call_grok", _fake)
        monkeypatch.setattr(generator, "_validate_llm_output", lambda *a, **k: 0)
        generator.generate_podcast_script(dict(TESLA_VARS), cfg)
        assert seen and all(s == ("grok-4.7", "low", True) for s in seen), seen

    def test_fallback_runs_the_digest_model_at_its_own_effort(self, monkeypatch):
        from engine import generator
        cfg = self._cfg()
        seen = []

        def _fake(prompt, model=None, reasoning_effort=None, stream=False, **kw):
            seen.append((model, reasoning_effort))
            if model == "grok-4.7":
                raise TimeoutError("stall")
            return "word " * 500, {"finish_reason": "stop"}

        monkeypatch.setattr(generator, "_call_grok", _fake)
        monkeypatch.setattr(generator, "_validate_llm_output", lambda *a, **k: 0)
        generator.generate_podcast_script(dict(TESLA_VARS), cfg)
        assert seen[0] == ("grok-4.7", "low")
        assert seen[-1] == ("grok-4.3", None)
        assert cfg.llm._script_model_fallback.startswith("grok-4.7 -> grok-4.3")

    def test_truncation_retry_streams(self, monkeypatch):
        from engine import generator
        cfg = self._cfg()
        seen = []

        def _fake(prompt, model=None, reasoning_effort=None, stream=False, max_tokens=0, **kw):
            seen.append((model, reasoning_effort, stream))
            return "word " * 500, {"finish_reason": "length" if len(seen) == 1 else "stop"}

        monkeypatch.setattr(generator, "_call_grok", _fake)
        monkeypatch.setattr(generator, "_validate_llm_output", lambda *a, **k: 0)
        generator.generate_podcast_script(dict(TESLA_VARS), cfg)
        assert len(seen) >= 2 and seen[1] == ("grok-4.7", "low", True), seen
