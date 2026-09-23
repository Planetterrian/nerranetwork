"""Guards for Phase 3 (Omni View regional desks) and the Mira Ep1 review
fixes of 2026-09-23. Plan: docs/new_shows_plan_2026_09_22.md §4.7-4.8."""

from pathlib import Path

import pytest

from engine.config import load_config
from engine.pipeline import build_podcast_template_vars


class TestMiraDebutKeepsIdentity:
    """Vancouver and Collingwood Ep1 never said Mira's name until the
    closing: the generic debut line replaced the identity line."""

    def _intro(self, slug, ep):
        cfg = load_config(f"shows/{slug}.yaml")
        from types import SimpleNamespace
        v = build_podcast_template_vars(cfg, episode_num=ep, today_str="September 23, 2026",
                                        effective_hook="A hook.", args=SimpleNamespace(show=slug))
        return v["intro_line"]

    @pytest.mark.parametrize("slug", ["vancouver", "collingwood"])
    def test_ai_host_debut_names_mira_and_the_ai(self, slug):
        line = self._intro(slug, 1)
        assert "very first episode" in line
        assert "I'm Mira, the Nerra Network's AI host." in line

    def test_human_host_debut_unchanged(self):
        line = self._intro("prediction_markets", 1)
        assert line == ("Welcome to the very first episode of Prediction Markets Daily! "
                        "Today is September 23, 2026.")

    def test_ai_host_later_episode_unchanged_shape(self):
        assert "I'm Mira" in self._intro("vancouver", 2)
