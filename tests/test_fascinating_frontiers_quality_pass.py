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
