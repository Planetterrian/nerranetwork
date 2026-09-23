"""Guards for the Sep 23 2026 Phase-2 thinness fixes.

Collingwood Weekly Ep1 skipped at 631 words against a 660 floor: the
entity dedup read the TOWN as every headline's entity and dropped 29 of
73 articles, an obituary reached the digest, and grok-4.7 at default
reasoning effort stalled past xAI's edge disconnect on the digest call.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from engine.config import LLMConfig, load_config
from engine.generator import _llm_reasoning_effort, switch_to_network_default
from engine.utils import deduplicate_by_entity, drop_excluded_titles

NEW_SHOWS = ["ai_chips", "mag7", "peptides", "longevity", "vancouver",
             "collingwood", "prediction_markets"]


def _art(title, url):
    return {"title": title, "description": "", "url": url, "link": url}


class TestEntityDedupIgnore:
    TITLES = [
        "Collingwood council approves new budget",
        "Collingwood library extends weekend hours",
        "Collingwood harbour cleanup begins Monday",
        "Collingwood arena roof repairs finish early",
    ]

    def _articles(self):
        return [_art(t, f"https://example.com/{i}") for i, t in enumerate(self.TITLES)]

    def test_default_behaviour_unchanged(self):
        kept = deduplicate_by_entity(self._articles(), max_per_entity=2)
        assert len(kept) == 2

    def test_ignored_place_name_is_not_an_entity(self):
        kept = deduplicate_by_entity(self._articles(), max_per_entity=2,
                                     ignore=["Collingwood", "Wasaga Beach"])
        assert len(kept) == 4

    def test_a_real_entity_still_dedups(self):
        arts = [_art(f"Georgian Triangle Humane Society {x}", f"https://e.com/{i}")
                for i, x in enumerate(["opens", "closes", "reopens"])]
        kept = deduplicate_by_entity(arts, max_per_entity=2, ignore=["Collingwood"])
        assert len(kept) == 2

    @pytest.mark.parametrize("slug", ["vancouver", "collingwood"])
    def test_local_shows_configure_it(self, slug):
        cfg = load_config(f"shows/{slug}.yaml")
        assert cfg.entity_dedup_ignore

    def test_other_shows_do_not(self):
        for path in sorted(Path("shows").glob("*.yaml")):
            if path.name.startswith("_") or path.stem in ("vancouver", "collingwood", "network_meta", "translation_overrides", "pronunciation_map"):
                continue
            assert "entity_dedup_ignore" not in path.read_text(), path.name

    def test_run_show_passes_it(self):
        src = Path("run_show.py").read_text()
        assert 'getattr(config, "entity_dedup_ignore"' in src


class TestObituaryShape:
    def test_nee_title_dropped(self):
        arts = [_art("KING, Jeanne Elizabeth (nee Langley)", "https://x/1"),
                _art("Town hall approves budget", "https://x/2")]
        cfg = load_config("shows/collingwood.yaml")
        kept, dropped = drop_excluded_titles(arts, cfg.exclude_title_patterns)
        assert dropped == 1 and kept[0]["url"] == "https://x/2"


class TestLowEffortOnNewShows:
    @pytest.mark.parametrize("slug", NEW_SHOWS)
    def test_pinned_47_runs_at_low_effort(self, slug):
        cfg = load_config(f"shows/{slug}.yaml")
        assert cfg.llm.model == "grok-4.7"
        assert _llm_reasoning_effort(cfg) == "low"

    def test_fallback_drops_the_effort_with_the_model(self):
        llm = LLMConfig()
        llm.model = "grok-4.7"
        llm.reasoning_effort = "low"
        cfg = SimpleNamespace(llm=llm)
        switch_to_network_default(cfg, "test")
        assert cfg.llm.model == LLMConfig().model
        assert _llm_reasoning_effort(cfg) is None
        assert cfg.llm._pinned_reasoning_effort == "low"

    def test_established_shows_send_no_effort(self):
        for slug in ("tesla", "spacex", "models_agents", "omni_view"):
            assert _llm_reasoning_effort(load_config(f"shows/{slug}.yaml")) is None


def test_collingwood_floor_matches_its_length_target():
    cfg = load_config("shows/collingwood.yaml")
    assert cfg.llm.min_podcast_words == 1000
