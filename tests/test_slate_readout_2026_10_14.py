"""Oct 14 2026 — the first slate after PR #1430, scored and corrected.

Measured on the 21 episodes of 2026-10-14: the five desks went from 5.9-6.9
to 9.3-12.6 minutes, AI Chips / MAG 7 / Prediction Markets / Vancouver all
landed inside their promises, every break sat in the voice's own silence
(Vancouver's five gaps read 0.99-1.19 s against 0.56 s sentence gaps), and
the fixed segment openers were gone on 21 of 21 scripts. Four defects:

* the digest expansion compared PROSE against PROSE-PLUS-LEDGER, so Tesla's
  pass that added 80 prose words (1,154 -> 1,231 on a 1,600 floor) logged
  "improved (1154 -> 1785)";
* Fascinating Frontiers' deep-dive framework line still said 180-220 words
  under a 450-550 spec, its validator rejected both generations for a
  bold-item list with no number, and the break planner read six 50-word
  stories as one block;
* Top World's digest sat on its floor and Mira told it in 77% of target;
* market-research press releases ("… Market Forecast to 2035: 11% CAGR")
  had aired as digest headlines on eight shows — Planetterrian led with one
  on six recent days;
* the story-change cue played at the opening bed's exposed level (about
  2 dB under the voice on the shipped Europe and AI Chips mixes), not the
  ~12 dB under it was set for.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


def _cfg(slug):
    from engine.config import load_config
    return load_config(ROOT / "shows" / f"{slug}.yaml")


# ---------------------------------------------------------------------------
# The expansion is judged on prose
# ---------------------------------------------------------------------------

class TestExpansionJudgedOnProse:
    def test_section_word_counts_ignore_the_ledger(self):
        from engine.generator import digest_section_word_counts
        text = (
            "# Show\n> **Hook.**\n\n### Top News\n1. **A** — one two three four.\n"
            "Source: https://x.y/a\n\n### Essay\nfive six seven eight nine ten.\n\n"
            "```claims\n[{\"claim\": \"" + "ledger " * 300 + "\"}]\n```\n"
        )
        counts = dict(digest_section_word_counts(text))
        # The numbered prefix and the bold title count as words; the ledger never does.
        assert 5 <= counts["Top News"] <= 8 and counts["Essay"] == 6

    def test_retry_prompt_names_the_sections_and_counts_prose(self):
        from engine.generator import _build_digest_expansion_retry_prompt
        p = _build_digest_expansion_retry_prompt(
            712, 1400, "draft", sections=[("Tesla First Principles", 294)])
        assert "Tesla First Principles: 294 words" in p
        assert "words of prose" in p and "ledger does not count" in p
        assert "furthest below their own spec first" in p

    def test_the_result_is_measured_in_prose_with_a_bounded_second_pass(self):
        src = (ROOT / "engine/generator.py").read_text()
        block = src[src.index("digest_expansion_attempts"):src.index("# Combined generation: the script paired")]
        assert "expanded_wc = digest_prose_word_count(expanded)" in block
        assert "expanded_wc = len(expanded.split())" not in block
        assert "DIGEST_EXPANSION_SECOND_PASS_SHARE" in block
        assert "sections=digest_section_word_counts(text)" in block

    def test_attempts_knob(self):
        from engine.config import LLMConfig
        from engine.generator import DIGEST_EXPANSION_SECOND_PASS_SHARE
        assert LLMConfig().digest_expansion_attempts == 1
        assert DIGEST_EXPANSION_SECOND_PASS_SHARE == 0.9
        for slug in ("tesla", "fascinating_frontiers", "modern_investing", "omni_view"):
            assert _cfg(slug).llm.digest_expansion_attempts == 2, slug
        for slug in ("spacex", "omni_view_europe", "unintended_consequences"):
            assert _cfg(slug).llm.digest_expansion_attempts == 1, slug


# ---------------------------------------------------------------------------
# Fascinating Frontiers
# ---------------------------------------------------------------------------

class TestFascinatingFrontiers:
    def test_one_deep_dive_length(self):
        p = (ROOT / "shows/prompts/fascinating_frontiers_digest.txt").read_text()
        assert "450-550 words" in p
        assert "180–220" not in p and "180-220 words" not in p

    def test_validator_accepts_a_bold_list_without_numbers(self):
        from engine.validation import ff_validation_config, validate_digest
        items = "".join(
            f"**Story {i} shows a thing** — Outlet\nFirst fact here. Second fact there.\n"
            f"Source: https://example.org/{i}\n\n" for i in range(1, 10)
        )
        digest = ("# Fascinating Frontiers\n> **Hook sentence here.**\n---\n" + items +
                  "---\n### Cosmic Spotlight\nSomething deeper.\n---\n### Cosmic Deep Dive: X\nEssay.\n")
        issues = validate_digest(digest, ff_validation_config())
        assert not [i for i in issues if "Space Stories" in str(i)], issues

    def test_items_under_the_hook_are_stories(self):
        # Ep222's shape: six sourced items straight under the hook rule, no
        # ``##`` header before them.
        from engine.story_breaks import story_units, _is_short_item, SHORT_ITEM_MAX_WORDS
        from engine.story_breaks import StoryUnit
        digest = "# Fascinating Frontiers\n> **Hook here.**\n---\n" + "".join(
            f"**Story {i} about rocket {i}** — Outlet\n" +
            " ".join(f"fact{i}w{j}" for j in range(26)) + ". " +
            " ".join(f"more{i}w{j}" for j in range(26)) + f".\nSource: https://e.org/{i}\n\n"
            for i in range(6)
        ) + "---\n### Cosmic Spotlight\nSomething deeper about rocket zero and its tracks on the crater floor.\n"
        units = story_units(digest)
        assert len(units) == 7 and [u.label for u in units][:6] == ["item"] * 6
        assert all(u.words > SHORT_ITEM_MAX_WORDS for u in units[:6])
        assert not any(_is_short_item(u) for u in units[:6])
        assert _is_short_item(StoryUnit(label="item", tokens=frozenset(), sentences=1, words=20))
        # Front matter without a Source line or a number is still not a story.
        assert not story_units("# Show\n**Date:** today\n$TSLA 400.00 up 1%\n\n")


# ---------------------------------------------------------------------------
# Top World
# ---------------------------------------------------------------------------

class TestTopWorld:
    def test_floor_and_item_depth(self):
        assert _cfg("omni_view_world").llm.min_digest_words == 1900
        p = (ROOT / "shows/prompts/omni_view_world_digest.txt").read_text()
        assert "Items one to five: sentence count follows fact count, seven to ten" in p
        assert "Items four and five" not in p
        assert "Items six to ten: ONE sentence each" in p


# ---------------------------------------------------------------------------
# Market-research press releases never reach a prompt
# ---------------------------------------------------------------------------

AIRED = [  # real tracker headlines from the last 40 episodes
    "Transfection Reagents Market Forecast to 2035: Demand Accelerates on Cell and Gene Therapy Boom",
    "Protein Production Reagents Market Forecast to 2035: Growth Driven by Biologics",
    "Autonomous Mobile Robot Market Projected to Reach $7.07B by 2032",
    "Advanced Packaging Market Forecast to Reach $90B by 2031",
    "Latin America Carbon Credit Market Size to Reach USD 824.52 Billion by 2034 at 33.06% CAGR",
    "Peptide Antibiotics Market Projected to Expand at 5.4% CAGR Through 2034",
    "Europe DNA Plasmid Manufacturing Market Size, Share, Trends, and Forecast, 2021 - 2031",
    "The Artificial Intelligence (AI) Personal Computer (PC) Market is Expected to Grow Rapidly at a CAGR",
    "Longevity ingredient market projected to reach two point one billion dollars — openPR.com",
    "Copper Rigid Tubing Market Forecast to 2035: Growth Driven by Semiconductor and EV Demand",
]
NEWS = [
    "Market Outlook: Canadian dollar could weaken before rebounding",
    "Labor Market Report Doesn't Alter Fed's Base Case on Rate Hikes",
    "Tesla retakes #1 spot in Norway with 26.3% market share",
    "Samsung's HBM Market Share Jumps to 33%; Hybrid Bonding Tech",
    "Tesla Gains 6% China Market Share in September, Rises to 4th",
    "Stock market today: Nasdaq slides as chip stocks fall",
    "Polymarket adds a market on the 2028 nomination",
]


class TestMarketReportFilter:
    @pytest.mark.parametrize("title", AIRED)
    def test_press_release_dropped(self, title):
        from engine.utils import NETWORK_EXCLUDE_TITLE_PATTERNS, drop_excluded_titles
        kept, n = drop_excluded_titles([{"title": title}], list(NETWORK_EXCLUDE_TITLE_PATTERNS))
        assert n == 1 and not kept, title

    @pytest.mark.parametrize("title", NEWS)
    def test_news_kept(self, title):
        from engine.utils import NETWORK_EXCLUDE_TITLE_PATTERNS, drop_excluded_titles
        kept, n = drop_excluded_titles([{"title": title}], list(NETWORK_EXCLUDE_TITLE_PATTERNS))
        assert n == 0 and kept, title

    def test_every_fetch_site_adds_the_network_list(self):
        src = (ROOT / "run_show.py").read_text()
        assert src.count("exclude_title_patterns_for") >= 3
        # No site reads the per-show list on its own any more.
        assert 'getattr(config, "exclude_title_patterns", None) or []' not in src
        assert 'getattr(config, "exclude_title_patterns", []) or []' not in src

    def test_per_show_list_is_kept(self):
        from engine.utils import exclude_title_patterns_for
        pats = exclude_title_patterns_for(_cfg("planetterrian"))
        assert r"\bexoplanets?\b" in pats and any("CAGR" in p for p in pats)
        assert exclude_title_patterns_for(None)


# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------

class TestTheRecord:
    def test_readout_is_written(self):
        doc = (ROOT / "docs/reviews/transitions_and_length_2026_10_14.md").read_text()
        assert "## 5. The first slate" in doc
        reg = yaml.safe_load((ROOT / "docs/experiments.yaml").read_text())
        ids = {e.get("id") for e in reg.get("experiments", reg) if isinstance(e, dict)}
        assert "slate-readout-2026-10-14" in ids
