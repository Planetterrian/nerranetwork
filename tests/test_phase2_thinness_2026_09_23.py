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


class TestExpansionKeepsTheLedger:
    DRAFT = (
        "### Top Stories\n**A thing happened:** CBC. It happened today.\n"
        "Source: https://cbc.ca/a\n\n```claims\n"
        '[{"claim": "It happened today.", "source_url": "https://cbc.ca/a", '
        '"supporting_quote": "it happened today"}]\n```\n'
    )

    def test_empty_ledger_after_expansion_is_replaced_by_the_draft(self):
        from engine.claims import extract_claims_block
        from engine.generator import _carry_claims_ledger
        expanded = "### Top Stories\n**A thing happened:** CBC. It happened today, at noon.\n\n```claims\n[]\n```\n"
        out = _carry_claims_ledger(self.DRAFT, expanded, "t")
        prose, claims = extract_claims_block(out)
        assert len(claims) == 1 and claims[0]["source_url"] == "https://cbc.ca/a"
        assert "at noon" in prose and "[]" not in prose

    def test_missing_ledger_after_expansion_is_replaced(self):
        from engine.claims import extract_claims_block
        from engine.generator import _carry_claims_ledger
        out = _carry_claims_ledger(self.DRAFT, "### Top Stories\nLonger prose.\n", "t")
        assert len(extract_claims_block(out)[1]) == 1

    def test_expansion_with_its_own_ledger_keeps_it(self):
        from engine.generator import _carry_claims_ledger
        own = ('Prose.\n\n```claims\n[{"claim": "b", "source_url": "https://x/b", '
               '"supporting_quote": "b"}]\n```\n')
        assert _carry_claims_ledger(self.DRAFT, own, "t") == own

    def test_draft_without_entries_changes_nothing(self):
        from engine.generator import _carry_claims_ledger
        assert _carry_claims_ledger("Prose.\n```claims\n[]\n```\n", "More.\n", "t") == "More.\n"

    def test_wired_into_the_expansion_branch(self):
        src = Path("engine/generator.py").read_text()
        i = src.index('"x_thread_generation_expansion"')
        assert "_carry_claims_ledger(text, expanded" in src[i - 4000:i]


class TestHookArticlesSurviveEveryCap:
    """Vancouver Ep1: 152 articles, pre-dedup cap to 150 by plain slice,
    and the two it cut were the hook's DriveBC + Environment Canada
    articles — merged last. Every cap in run_show must keep them."""

    def test_pre_dedup_cap_keeps_hook_articles(self):
        src = Path("run_show.py").read_text()
        i = src.index("MAX_RAW_BEFORE_DEDUP = 150")
        block = src[i:i + 1500]
        assert "articles = articles[:MAX_RAW_BEFORE_DEDUP]" not in block
        assert 'a.get("source_kind") == "hook"' in block

    def test_prompt_cap_keeps_hook_articles(self):
        src = Path("run_show.py").read_text()
        i = src.index("MAX_ARTICLES_FOR_LLM = 40")
        assert '"source_kind") == "hook"' in src[i:i + 1800]


class TestBodyChapterMarkers:
    SCRIPT = (
        "A hook sentence about the day.\n\n"
        "Welcome to the very first episode of Vancouver Daily News.\n\n"
        "It covers what council decided and what that means for getting around.\n\n"
        + "\n\n".join(f"News sentence number {i} about the province and its politics today." for i in range(60))
        + "\n\nGetting around starts with a lane closure on Highway 17.\n\n"
        + "\n\n".join(f"Road sentence {i} with more detail about the commute." for i in range(10))
        + "\n\nThat's Vancouver Daily News, see you tomorrow.\n"
    )

    def _titles_at(self, markers):
        from engine.chapters import parse_chapters
        return {c.title: c.word_start for c in parse_chapters(self.SCRIPT, markers, known_sections_only=True)}

    def test_body_marker_skips_the_opening_window(self):
        m = [{"pattern": "first episode of", "title": "Introduction", "where": "start"},
             {"pattern": "getting around", "title": "Getting Around", "where": "body"}]
        at = self._titles_at(m)
        opening = len(self.SCRIPT.split("Getting around starts")[0].split())
        assert at["Getting Around"] == opening

    def test_unconstrained_marker_still_matches_first(self):
        m = [{"pattern": "first episode of", "title": "Introduction", "where": "start"},
             {"pattern": "getting around", "title": "Getting Around"}]
        assert self._titles_at(m)["Getting Around"] < 40

    @pytest.mark.parametrize("slug", ["vancouver", "collingwood"])
    def test_local_show_segment_anchors_are_body(self, slug):
        cfg = load_config(f"shows/{slug}.yaml")
        for mk in cfg.chapters.section_markers:
            if mk.title not in ("Introduction", "Closing"):
                assert mk.where == "body", (slug, mk.title)

    def test_vancouver_ep1_replay(self):
        import re
        from engine.chapters import parse_chapters
        stem = Path("digests/vancouver/Vancouver_Daily_Ep001_20260923")
        if not stem.with_name(stem.name + "_tts.txt").exists():
            pytest.skip("Ep1 not in this checkout")
        script = stem.with_name(stem.name + "_tts.txt").read_text()
        md = stem.with_suffix(".md").read_text()
        heads = [m.group(1) for m in re.finditer(r"^\*\*(.+?):\*\*", md, re.M)]
        cfg = load_config("shows/vancouver.yaml")
        chs = parse_chapters(script, cfg.chapters.section_markers, story_headlines=heads)
        by = {c.title: c.word_start for c in chs}
        assert by["Getting Around"] > len(script.split()) * 0.5
        assert any(t.startswith("Eby calls") for t in by)
