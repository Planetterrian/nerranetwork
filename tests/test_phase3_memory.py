"""Phase 3 (recursive narrative memory) drift guards.

Generalizes Tesla's narrative-memory system to other shows via
``engine.show_memory`` + per-show MemoryConfigs + thin hooks + flag-gated
prompt injection + public "story tracker" pages.

These tests pin: the generic engine, the flag gating (disabled == true no-op),
the per-show config registry, the prompt wiring, and the public page render.
``tests/test_show_memory.py`` continues to guard the untouched Tesla module.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine import show_memory as sm

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEMORY_SHOWS = ("models_agents", "fascinating_frontiers", "planetterrian")


# ---------------------------------------------------------------------------
# Generic engine
# ---------------------------------------------------------------------------

class TestEngine:
    def _cfg(self):
        return sm.MemoryConfig(
            slug="demo", label="DEMO", file_prefix="demo",
            default_programs={"p1": sm._prog("Program One", "Status one.", ["Q1?"])},
            theme_keywords=["alpha", "beta"],
        )

    def test_filenames(self):
        c = self._cfg()
        assert c.narrative_filename == "demo_narrative_tracker.json"
        assert c.performance_filename == "demo_performance_tracker.json"
        assert c.theme_filename == "demo_theme_history.json"

    def test_round_trip(self, tmp_path):
        c = self._cfg()
        t = sm.load_narrative_tracker(tmp_path, c)
        assert "p1" in t["programs"]
        sm.save_narrative_tracker(t, tmp_path, c)
        assert (tmp_path / c.narrative_filename).exists()

    def test_default_isolation(self, tmp_path):
        c = self._cfg()
        first = sm.load_narrative_tracker(tmp_path, c)
        first["programs"]["INJECTED"] = {}
        other = tmp_path / "x"; other.mkdir()
        assert "INJECTED" not in sm.load_narrative_tracker(other, c)["programs"]

    def test_section_empty_when_no_programs(self, tmp_path):
        c = sm.MemoryConfig(slug="empty", label="EMPTY", file_prefix="empty",
                            default_programs={}, theme_keywords=[])
        assert sm.build_memory_section(tmp_path, c) == ""

    def test_section_nonempty_with_programs(self, tmp_path):
        c = self._cfg()
        section = sm.build_memory_section(tmp_path, c)
        assert "DEMO" in section
        assert "Program One" in section
        assert "Status one." in section

    def test_get_memory_context_keys(self, tmp_path):
        ctx = sm.get_memory_context(tmp_path, self._cfg())
        assert set(ctx) == {"narrative_status_block", "performance_signals_block", "theme_context_block"}

    def test_theme_mining(self, tmp_path):
        c = self._cfg()
        sm.update_theme_history_from_digest(tmp_path, c, "Alpha and beta showed up today.", 1)
        themes = sm.load_theme_history(tmp_path, c)["recurring_themes"]
        assert themes.get("alpha", 0) >= 1
        assert themes.get("beta", 0) >= 1


# ---------------------------------------------------------------------------
# Flag gating via the shared hook helpers
# ---------------------------------------------------------------------------

class _FakeCfg:
    def __init__(self, output_dir, enabled):
        self.memory_enabled = enabled
        self.episode = type("E", (), {"output_dir": str(output_dir)})()


class TestHookGating:
    def test_disabled_is_true_noop(self, tmp_path):
        out = sm.memory_pre_fetch(_FakeCfg(tmp_path, False), "models_agents")
        assert out == {sm.SECTION_VAR: ""}

    def test_enabled_injects_section(self, tmp_path):
        out = sm.memory_pre_fetch(_FakeCfg(tmp_path, True), "models_agents")
        assert out[sm.SECTION_VAR]  # non-empty (seeded programs)
        assert "MODELS & AGENTS" in out[sm.SECTION_VAR]

    def test_unknown_slug_is_noop(self, tmp_path):
        out = sm.memory_pre_fetch(_FakeCfg(tmp_path, True), "no_such_show")
        assert out == {sm.SECTION_VAR: ""}

    def test_post_generate_disabled_writes_nothing(self, tmp_path):
        sm.memory_post_generate(_FakeCfg(tmp_path, False), "models_agents", "agent gpt", 1)
        assert not list(tmp_path.glob("*theme*"))

    def test_post_generate_enabled_mines(self, tmp_path):
        sm.memory_post_generate(_FakeCfg(tmp_path, True), "models_agents", "A new agent and gpt model.", 1)
        cfg = sm.get_config("models_agents")
        themes = sm.load_theme_history(tmp_path, cfg)["recurring_themes"]
        assert themes.get("agent", 0) >= 1


# ---------------------------------------------------------------------------
# Per-show config registry + YAML flags
# ---------------------------------------------------------------------------

class TestRegistryAndConfig:
    @pytest.mark.parametrize("slug", MEMORY_SHOWS)
    def test_registered_with_content(self, slug):
        cfg = sm.get_config(slug)
        assert cfg is not None
        assert cfg.default_programs, f"{slug} should have seeded programs"
        assert cfg.theme_keywords, f"{slug} should have theme keywords"
        assert cfg.label.isupper() or "&" in cfg.label

    @pytest.mark.parametrize("slug", MEMORY_SHOWS)
    def test_yaml_memory_enabled(self, slug):
        from engine.config import load_config
        cfg = load_config(PROJECT_ROOT / "shows" / f"{slug}.yaml")
        assert cfg.memory_enabled is True

    def test_non_memory_show_defaults_false(self):
        from engine.config import load_config
        cfg = load_config(PROJECT_ROOT / "shows" / "omni_view.yaml")
        assert cfg.memory_enabled is False


# ---------------------------------------------------------------------------
# Prompt wiring + hook files
# ---------------------------------------------------------------------------

class TestPromptWiring:
    @pytest.mark.parametrize("slug", MEMORY_SHOWS)
    def test_prompts_have_placeholder(self, slug):
        for kind in ("digest", "podcast"):
            txt = (PROJECT_ROOT / "shows" / "prompts" / f"{slug}_{kind}.txt").read_text(encoding="utf-8")
            assert "{narrative_memory_section}" in txt, f"{slug}_{kind} missing placeholder"

    @pytest.mark.parametrize("slug", MEMORY_SHOWS)
    def test_hook_file_exposes_prefetch(self, slug):
        import importlib.util
        path = PROJECT_ROOT / "shows" / "hooks" / f"{slug}.py"
        assert path.exists()
        spec = importlib.util.spec_from_file_location(f"hk_{slug}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "pre_fetch") and hasattr(mod, "post_generate")


# ---------------------------------------------------------------------------
# Public narrative page
# ---------------------------------------------------------------------------

class TestPublicPage:
    @pytest.mark.parametrize("slug", MEMORY_SHOWS)
    def test_page_renders(self, slug):
        import generate_html as gh
        path = gh.generate_narrative_page(slug, dry_run=False)
        assert path is not None and Path(path).exists()
        html = Path(path).read_text(encoding="utf-8")
        assert "Narrative Tracker" in html
        assert "program-card" in html
        assert "<title>" in html and "</title>" in html
        # title must be populated (not empty)
        import re
        m = re.search(r"<title>(.*?)</title>", html)
        assert m and m.group(1).strip(), "title should be populated"
