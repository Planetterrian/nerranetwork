"""Drift guards for the June 10 2026 four-show quality pass
(Modern Investing, Models & Agents, Models & Agents for Beginners,
Fascinating Frontiers) — the same review process as the Tesla flagship
pass (docs/tesla_review_2026_06_10.md), applied per
docs/four_show_review_2026_06_10.md.

Pins:
* every closing-pool variant for the four shows is matched by its
  show's `where: end` Closing chapter marker (the Tesla bug class —
  unmatched closings shipped 50% of MAB episodes with NO Closing
  chapter, and M&A/FF/MIT each had 1-2 orphan variants);
* positional `where` anchors on Introduction/Teaser/Closing markers;
* the unified single length target per show (floor under the prompt's
  stated low end);
* engine/show_memory.py carries the Tesla memory fixes: narrative-prose
  echo filter, per-episode idempotency, URL stripping, word-boundary
  program detection, and the OP3 performance-loop writer;
* the nightly workflow runs the generalized performance script and
  commits all four performance trackers.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine import show_memory  # noqa: E402
from engine.intros import _SHOW_PERSONALITIES  # noqa: E402

_SHOW_YAMLS = {
    "modern_investing": "shows/modern_investing.yaml",
    "models_agents": "shows/models_agents.yaml",
    "models_agents_beginners": "shows/models_agents_beginners.yaml",
    "fascinating_frontiers": "shows/fascinating_frontiers.yaml",
}


def _markers(slug):
    cfg = yaml.safe_load((_ROOT / _SHOW_YAMLS[slug]).read_text(encoding="utf-8"))
    return cfg["chapters"]["section_markers"]


class TestClosingPoolMatchesChapterPattern:
    @pytest.mark.parametrize("slug", sorted(_SHOW_YAMLS))
    def test_every_closing_variant_matched(self, slug):
        closing = next(m for m in _markers(slug) if m["title"] == "Closing")
        regex = re.compile(closing["pattern"], re.IGNORECASE)
        closings = _SHOW_PERSONALITIES[slug]["closings"]
        for variant in closings:
            assert regex.search(variant), (
                f"{slug}: closing variant not matched by the Closing "
                f"chapter pattern — episodes using it ship without a "
                f"Closing chapter: {variant[:80]!r}"
            )

    @pytest.mark.parametrize("slug", sorted(_SHOW_YAMLS))
    def test_positional_anchors(self, slug):
        by_title = {m["title"]: m for m in _markers(slug)}
        closing = by_title["Closing"]
        assert closing.get("where") == "end"
        intro_title = "Welcome" if slug == "models_agents_beginners" else "Introduction"
        assert by_title[intro_title].get("where") == "start"

    def test_ma_agent_pattern_not_bare_substring(self):
        """Bare 'agent' opened a spurious Agent & Tool Developments
        chapter ~30s into every M&A episode."""
        marker = next(m for m in _markers("models_agents")
                      if m["title"] == "Agent & Tool Developments")
        assert re.search(r"(?<![a-z])agent\|", marker["pattern"]) is None
        assert "agent and tool developments" in marker["pattern"]

    def test_mit_closing_not_bare_wraps_up(self):
        marker = next(m for m in _markers("modern_investing")
                      if m["title"] == "Closing")
        assert "|wraps up|" not in f"|{marker['pattern']}|".replace(
            "that wraps up", "")


class TestUnifiedLengthTargets:
    """One stated target per prompt; YAML floor sits under its low end."""

    EXPECTED = {
        "modern_investing": (1800, "2,000–2,200 words"),
        "models_agents": (1500, "1,600–2,200 words"),
        "models_agents_beginners": (1200, "1300–1700 words"),
        "fascinating_frontiers": (1700, "1,900–2,200 words"),
    }

    PROMPTS = {
        "modern_investing": "shows/prompts/modern_investing_podcast.txt",
        "models_agents": "shows/prompts/models_agents_podcast.txt",
        "models_agents_beginners": "shows/prompts/mab_podcast.txt",
        "fascinating_frontiers": "shows/prompts/fascinating_frontiers_podcast.txt",
    }

    @pytest.mark.parametrize("slug", sorted(EXPECTED))
    def test_floor_and_prompt_target(self, slug):
        floor, target_str = self.EXPECTED[slug]
        cfg = yaml.safe_load((_ROOT / _SHOW_YAMLS[slug]).read_text(encoding="utf-8"))
        assert cfg["llm"]["min_podcast_words"] == floor
        prompt = (_ROOT / self.PROMPTS[slug]).read_text(encoding="utf-8")
        assert target_str in prompt

    def test_contradictory_targets_removed(self):
        mit = (_ROOT / self.PROMPTS["modern_investing"]).read_text(encoding="utf-8")
        assert "2500–3500" not in mit
        ff = (_ROOT / self.PROMPTS["fascinating_frontiers"]).read_text(encoding="utf-8")
        assert "at least 2400 words" not in ff
        assert "12-15 minute" not in ff
        ma = (_ROOT / self.PROMPTS["models_agents"]).read_text(encoding="utf-8")
        assert "6–9 minute" not in ma

    def test_mab_opener_variation_required(self):
        mab = (_ROOT / self.PROMPTS["models_agents_beginners"]).read_text(encoding="utf-8")
        assert "VARY THE OPENER EVERY EPISODE" in mab


class TestShowMemoryHardening:
    """The Tesla June 10 memory fixes, ported to the generalized engine."""

    def _cfg(self):
        return show_memory.get_config("models_agents")

    DIGEST = (
        "DeepSeek shipped a new reasoning model today. The wireless "
        "benchmark suite surfaced alongside pricing data. "
        "Source: https://news.google.com/rss/articles/CBMi123"
    )

    def test_idempotent_per_episode(self, tmp_path):
        cfg = self._cfg()
        show_memory.update_theme_history_from_digest(tmp_path, cfg, self.DIGEST, 75)
        show_memory.update_theme_history_from_digest(tmp_path, cfg, self.DIGEST, 75)
        history = json.loads((tmp_path / cfg.theme_filename).read_text())
        episodes = [e["episode"] for e in history["theme_evolution"]]
        assert episodes.count(75) == 1

    def test_narrative_prose_echo_filtered(self, tmp_path):
        cfg = self._cfg()
        # Default tracker prose: "Autonomous agents, tool use, and the
        # MCP / interoperability layer maturing."
        digest = (
            "Agent update: autonomous agents, tool use, and the MCP "
            "interoperability layer maturing fast, plus new benchmark data."
        )
        show_memory.update_theme_history_from_digest(tmp_path, cfg, digest, 76)
        themes = json.loads(
            (tmp_path / cfg.theme_filename).read_text())["recurring_themes"]
        assert "autonomous agents" not in themes
        assert "interoperability layer" not in themes
        assert themes.get("benchmark") == 1  # curated keyword still counted

    def test_urls_not_mined(self, tmp_path):
        cfg = self._cfg()
        show_memory.update_theme_history_from_digest(tmp_path, cfg, self.DIGEST, 77)
        themes = json.loads(
            (tmp_path / cfg.theme_filename).read_text())["recurring_themes"]
        joined = " ".join(themes)
        assert "https" not in joined
        assert "google" not in joined

    def test_word_boundary_program_detection(self, tmp_path):
        cfg = show_memory.get_config("fascinating_frontiers")
        # "marsupial" must not advance the Starship & Mars program.
        mentioned = show_memory.auto_update_narrative_from_digest(
            tmp_path, cfg, "A study of marsupial biology in Australia.",
            90, "2026-06-10")
        assert "starship_mars" not in mentioned
        mentioned = show_memory.auto_update_narrative_from_digest(
            tmp_path, cfg, "Starship completed another test flight.",
            90, "2026-06-10")
        assert "starship_mars" in mentioned

    def test_op3_performance_loop(self, tmp_path):
        cfg = self._cfg()
        stats = {"episodes": [
            {"title": "Ep 75: Agents now deliver 26 minutes of autonomous "
                      "work per session", "downloads_30d": 9},
            {"title": "Ep 74: Open-weight models close the gap",
             "downloads_30d": 7},
        ]}
        count = show_memory.update_performance_from_op3(tmp_path, cfg, stats)
        assert count >= 1
        perf = show_memory.load_performance_tracker(tmp_path, cfg)
        topics = perf["recent_signals"]["strong_topics_last_30d"]
        assert "Agents & Tool Use" in topics
        block = show_memory.build_performance_signals_block(perf)
        assert "Agents & Tool Use" in block

    def test_nightly_workflow_wires_generalized_script(self):
        wf = (_ROOT / ".github" / "workflows" / "nightly-maintenance.yml"
              ).read_text(encoding="utf-8")
        assert "update_performance_trackers.py" in wf
        for tracker in (
            "models_agents_performance_tracker.json",
            "fascinating_frontiers_performance_tracker.json",
            "planetterrian_performance_tracker.json",
        ):
            assert tracker in wf
