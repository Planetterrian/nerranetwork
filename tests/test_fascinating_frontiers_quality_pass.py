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
import re
from pathlib import Path

import pytest
import yaml

from engine.chapters import parse_chapters
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


def _ff_markers():
    cfg = yaml.safe_load(
        (REPO / "shows/fascinating_frontiers.yaml").read_text(encoding="utf-8")
    )
    return cfg["chapters"]["section_markers"]


class TestChapterClosingOrdering:
    """June 24 2026: the spoken sign-off ("…I'll see you next time") matches the
    Tomorrow Teaser pattern (`Next time`). With Teaser listed before Closing the
    sign-off line was mis-titled Tomorrow Teaser and the episode shipped with NO
    Closing chapter (Ep110/Ep111 ended on Tomorrow Teaser). The fix: list Closing
    before Tomorrow Teaser, broaden the teaser to its real "Keep an eye on…" /
    "Watch for…" openers, and drop the bare `deep dive` pattern that the
    cross-promo ("daily deep dive into everything Tesla") tripped (Ep109 spurious
    out-of-order chapter). All metadata-only — no audio/prompt change.
    """

    def test_closing_listed_before_tomorrow_teaser(self):
        titles = [m["title"] for m in _ff_markers()]
        assert titles.index("Closing") < titles.index("Tomorrow Teaser"), (
            "Closing must precede Tomorrow Teaser so the 'see you next time' "
            "sign-off line is titled Closing, not Tomorrow Teaser"
        )

    def test_deep_dive_pattern_does_not_match_bare_deep_dive(self):
        dd = next(m for m in _ff_markers() if m["title"] == "Cosmic Deep Dive")
        rx = re.compile(dd["pattern"], re.IGNORECASE)
        # The network-family cross-promo must NOT open a Cosmic Deep Dive chapter.
        assert not rx.search(
            "give Tesla Shorts Time a listen: your daily deep dive into everything Tesla"
        )
        assert not rx.search("let's pop the hood and go under the hood")
        # The literal section label still matches when present.
        assert rx.search("Cosmic Deep Dive: how infrared light reveals hidden stars")

    def _parse(self, script):
        return [c.title for c in parse_chapters(
            script, _ff_markers(), show_name="Fascinating Frontiers")]

    # A realistic ~1600-word body so the teaser + sign-off land in the last
    # 15% (the `where: end` window), exactly as on a shipped episode. Each
    # "story" sentence carries a forward-looking phrase to prove mid-body
    # "watch for…" can't steal the Tomorrow Teaser title.
    _BODY = "\n\n".join(
        f"In story number {n}, astronomers used the telescope to measure the "
        f"distance and mass of a distant object, and they will watch for "
        f"follow-up data to confirm the result over the coming months."
        for n in range(1, 36)
    )

    def test_keep_an_eye_teaser_plus_signoff_gets_both_chapters(self):
        # Exact Ep110/Ep111 shape: "Keep an eye on…" teaser + "see you next
        # time" sign-off + network-family closing.
        script = (
            "Good to have you on Fascinating Frontiers, episode one hundred eleven.\n\n"
            + self._BODY + "\n\n"
            "Keep an eye on the next Starliner readiness review as testing continues through the summer.\n\n"
            "That's Fascinating Frontiers for today. I'm Patrick in Vancouver. "
            "Thanks for exploring with me, and I'll see you next time. And if you'd "
            "rather watch than listen, find us on YouTube.\n\n"
            "And before you go — this show is part of the Nerra Network, a family "
            "of daily podcasts. Give Planetterrian Daily a listen.\n\n"
            "This episode used AI voice synthesis of my voice."
        )
        titles = self._parse(script)
        assert "Closing" in titles, titles
        assert "Tomorrow Teaser" in titles, titles
        # Closing is the last semantic marker (the sign-off ends the episode).
        assert titles.index("Tomorrow Teaser") < titles.index("Closing"), titles

    def test_next_time_teaser_with_deep_dive_cross_promo_no_orphan_chapter(self):
        # Exact Ep109 shape: "Next time, we'll be watching…" teaser + a Tesla
        # cross-promo carrying "deep dive". The cross-promo must NOT create a
        # spurious Cosmic Deep Dive chapter after the close.
        script = (
            "Good to have you on Fascinating Frontiers, episode one hundred nine.\n\n"
            + self._BODY + "\n\n"
            "Next time, we'll be watching for the first integration milestones on the Roman Space Telescope.\n\n"
            "That's Fascinating Frontiers for today. I'm Patrick in Vancouver. "
            "Thanks for exploring with me, and I'll see you next time.\n\n"
            "And before you go — this show is part of the Nerra Network. Give "
            "Tesla Shorts Time a listen: your daily deep dive into everything Tesla.\n\n"
            "This episode used AI voice synthesis of my voice."
        )
        titles = self._parse(script)
        assert "Closing" in titles, titles
        assert "Tomorrow Teaser" in titles, titles
        assert "Cosmic Deep Dive" not in titles, (
            "the cross-promo 'deep dive into everything Tesla' must not open a "
            f"Cosmic Deep Dive chapter: {titles}")
        # Closing is the final chapter — nothing follows the sign-off.
        assert titles[-1] == "Closing", titles
