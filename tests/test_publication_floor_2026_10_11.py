"""Oct 11 2026 — the publication floor has one owner.

Fascinating Frontiers lost its Oct 11 episode at 1,013 words against a
1,020-word floor (60 % of its 1,700-word target) one day after the Oct 10
pass capped it at 12 items. The floor existed as six copies of
``int(min_words * 0.6)``; ``engine.generator.publication_floor`` owns it now
and ``llm.min_podcast_publish_words`` lets a show set it apart from its
target.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

from engine.config import load_config
from engine.generator import (
    _podcast_expansion_retry_threshold,
    _publication_floor_for,
    publication_floor,
)

ROOT = Path(__file__).resolve().parent.parent


class TestOneOwner:
    def test_default_is_sixty_percent_of_target(self):
        assert publication_floor(1700) == 1020
        assert publication_floor(1600, 0) == 960

    def test_show_value_wins(self):
        assert publication_floor(1700, 850) == 850

    def test_no_copy_of_the_sixty_percent_rule_remains(self):
        text = (ROOT / "engine/generator.py").read_text(encoding="utf-8")
        body = text.split("def publication_floor", 1)[1].split("\ndef ", 1)[1]
        assert not re.search(r"int\(\s*min_words\s*\*\s*0\.6\s*\)", body)
        runner = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "_TARGET_WORDS * 0.6" not in runner
        assert "_publication_floor(" in runner

    def test_retry_band_follows_the_show_floor(self):
        # The expansion retry must stay above the floor it protects.
        assert _podcast_expansion_retry_threshold(1700, publish_floor=850) == int(850 * 1.1)
        assert _podcast_expansion_retry_threshold(1700) == int(1020 * 1.1)

    def test_config_helper_reads_the_field(self):
        cfg = SimpleNamespace(llm=SimpleNamespace(min_podcast_publish_words=850))
        assert _publication_floor_for(cfg, 1700) == 850
        assert _publication_floor_for(SimpleNamespace(llm=SimpleNamespace()), 1700) == 1020


class TestTheTwinsShipADenseDay:
    def test_ff_and_planetterrian_floor_below_the_skipped_script(self):
        for slug in ("fascinating_frontiers", "planetterrian"):
            cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
            floor = _publication_floor_for(cfg, cfg.llm.min_podcast_words)
            # FF's skipped Oct 11 script was 1,013 words.
            assert floor < 1013, slug
            hard = max(cfg.llm.min_podcast_word_floor, int(cfg.llm.min_podcast_words * 0.4))
            assert floor >= hard, slug

    def test_other_shows_keep_the_network_rule(self):
        cfg = load_config(ROOT / "shows" / "tesla.yaml")
        assert cfg.llm.min_podcast_publish_words == 0
