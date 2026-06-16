"""Drift guards for the Fascinating Frontiers quality pass (June 12 2026).

See docs/reviews/fascinating_frontiers_review_2026_06_12.md. Two shipped
fixes:

1. Phonetic-garble repair extended to cover the space names the podcast-gen
   step spelled phonetically despite the prompt ban — "En-sell-uh-dus"
   (Enceladus) and "Tee-en-wen" (Tianwen) shipped to TTS verbatim.
2. Theme-mining self-reference filter — the show's own name
   ("fascinating frontiers") was mined as a top "recurring theme" every
   episode (FF Ep97/98/99 all led with it) because the digest template
   header repeats the show name. Component tokens of other shows
   ("models"/"agents") must NOT be filtered.
"""

import json
from pathlib import Path

import pytest

from engine.utils import fix_phonetic_garbles
from engine.show_memory import (
    _self_reference_bigrams,
    SHOW_MEMORY_CONFIGS,
)

REPO = Path(__file__).resolve().parent.parent


class TestPhoneticGarbleRepairSpaceNames:
    def test_enceladus_restored(self):
        out = fix_phonetic_garbles("subsurface oceans on En-sell-uh-dus and Europa")
        assert "Enceladus" in out
        assert "En-sell-uh-dus" not in out

    def test_enceladus_case_insensitive(self):
        assert "Enceladus" in fix_phonetic_garbles("the moon en-sell-uh-dus")

    def test_tianwen_restored_keeps_numeric_suffix(self):
        # The regex's trailing \b must leave the "-2" suffix intact.
        out = fix_phonetic_garbles("China's Tee-en-wen-2 mission returns samples")
        assert "Tianwen-2" in out
        assert "Tee-en-wen" not in out

    def test_no_false_positive_on_clean_text(self):
        clean = "NASA's Enceladus flyby and the Tianwen-2 sample return."
        assert fix_phonetic_garbles(clean) == clean


class TestThemeSelfReferenceFilter:
    def test_ff_show_name_is_a_self_reference_bigram(self):
        cfg = SHOW_MEMORY_CONFIGS["fascinating_frontiers"]
        assert "fascinating frontiers" in _self_reference_bigrams(cfg)

    def test_ma_component_tokens_not_filtered(self):
        # "models" / "agents" are legitimate themes for Models & Agents;
        # only the FULL multi-word name may be filtered, never single tokens.
        cfg = SHOW_MEMORY_CONFIGS["models_agents"]
        sr = _self_reference_bigrams(cfg)
        assert "models" not in sr
        assert "agents" not in sr

    def test_committed_ff_theme_history_has_no_show_name_echo(self):
        p = REPO / "digests/fascinating_frontiers/fascinating_frontiers_theme_history.json"
        if not p.exists():
            pytest.skip("FF theme history not present")
        rt = json.loads(p.read_text()).get("recurring_themes", {})
        assert "fascinating frontiers" not in rt, (
            "show-name echo re-accumulated in FF recurring_themes — "
            "the self-reference filter regressed"
        )


class TestStockMarketTitleFilter:
    """June 16 2026 review: since the SPCX IPO (June 12) the Google News
    "SpaceX" queries flood FF with pure stock-market items. FF Ep103 shipped
    FOUR of fifteen stories as market action. ``exclude_title_patterns`` now
    drops market-action titles at fetch time while keeping mission/science.
    """

    @staticmethod
    def _ff_patterns():
        import yaml
        cfg = yaml.safe_load(
            (REPO / "shows/fascinating_frontiers.yaml").read_text()
        )
        return cfg.get("exclude_title_patterns", []) or []

    # The exact titles FF Ep103 shipped (digest Top-15 #3/#13/#14/#15).
    STOCK_TITLES = [
        "SpaceX Raises Record $85.7 Billion in Funding Round",
        "Space Exploration Files for $60 Billion Merger",
        "SPCX Added to NASDAQ Telecom Index",
        "SPCX Shares Rise 20 Percent After Funding News",
    ]

    # Real FF mission/science titles that MUST survive the filter.
    KEEP_TITLES = [
        "Dragon Cargo Capsule Begins Return from ISS",
        "Tianwen-2 Executes Series of Approach Burns",
        "JWST Maps Extreme Weather on Ruby-Raining Exoplanet",
        "Astrobotic Readies Griffin-1 Lander for Testing",
        "NASA Releases Image of Nebraska Sandhills",
        # money in the title, but a mission contract — not market action
        "NASA Awards SpaceX $2.9 Billion Artemis Lander Contract",
        # "merger" in an astronomy sense must not be dropped
        "Galaxy Merger Captured by Hubble in Stunning Detail",
        # "shares" used as a verb (NASA shares imagery) must survive
        "NASA Shares Stunning New View of Jupiter's Aurora",
        # the legitimate "goes public" milestone (no market-action keyword)
        "SpaceX is Now a Public Company Valued for its AI Potential",
        # REGRESSION: a bare nasdaq/nyse pattern dropped this launch story
        # (live FF feed, June 16 2026). A Falcon 9 launch is core FF content.
        "SpaceX launches its first Falcon 9 rocket since Nasdaq debut",
    ]

    def test_drops_ep103_stock_titles(self):
        from engine.utils import drop_excluded_titles
        pats = self._ff_patterns()
        arts = [{"title": t} for t in self.STOCK_TITLES]
        kept, dropped = drop_excluded_titles(arts, pats)
        assert dropped == len(self.STOCK_TITLES), (
            f"expected all {len(self.STOCK_TITLES)} stock titles dropped, "
            f"got {dropped}; survivors: {[a['title'] for a in kept]}"
        )

    def test_keeps_mission_and_science_titles(self):
        from engine.utils import drop_excluded_titles
        pats = self._ff_patterns()
        arts = [{"title": t} for t in self.KEEP_TITLES]
        kept, dropped = drop_excluded_titles(arts, pats)
        survivors = [a["title"] for a in kept]
        assert dropped == 0, (
            "filter over-dropped legitimate mission/science titles: "
            f"{[t for t in self.KEEP_TITLES if t not in survivors]}"
        )

    def test_digest_prompt_excludes_stock_items(self):
        txt = (REPO / "shows/prompts/fascinating_frontiers_digest.txt").read_text()
        assert "NO STOCK / MARKET ITEMS" in txt
