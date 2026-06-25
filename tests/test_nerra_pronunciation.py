"""Drift guards for consistent "Nerra Network" brand pronunciation.

Listeners reported "Nerra" being pronounced several different ways within the
same closing segment. Root cause: the closing said the brand three ways —
the spaced "Nerra Network" (promo), the "nerranetwork.com" URL, and the
"NerraNetwork" YouTube handle — and only the spaced form was normalized, so
Grok guessed a drifting pronunciation for the other two.

Fix (2026-06-24, revised 2026-06-25):
  * the EN YouTube handle is split to the spaced brand in
    ``engine.intros._maybe_append_youtube_cta`` (RU "NerraRU" left intact);
  * every spoken form is normalized to the SAME two real words "Nerra
    Network" in ``shows/pronunciation_map.yaml`` (audio-only) — the URL /
    handle compound "nerranetwork" is split into "Nerra Network".

A phonetic respelling was tried twice ("NAIR-uh", then "NEH-ruh") and regressed
badly on the Grok voice: the all-caps stressed syllable was read as an
initialism and the hyphen voiced aloud ("N-E-H dash ruh"). Per landmine #17 we
do NOT respell the brand — we only normalize the spelling so Grok says the
natural word identically each time. These guards pin that no respelling (old or
new) survives and that every form reduces to the spaced "Nerra Network".
"""

import re

import engine.tts as tts
from engine.intros import _maybe_append_youtube_cta
from assets.pronunciation import WORD_PRONUNCIATIONS
from assets.pronunciation import prepare_text_for_tts as assets_prepare

# Both failed phonetic respellings (and the "spelling-out" / dash artifacts they
# produced) must never reappear in any spoken form.
_BANNED_RESPELLINGS = ("NEH-ruh", "NAIR-uh", "Neh-ruh", "Nair-uh")


class TestAudioFormsNormalizeIdentically:
    """Every spoken form of the brand must reduce to the SAME natural words
    in the TTS (audio-only) layer."""

    def test_all_three_forms_become_spaced_brand(self):
        # In production the assets layer runs strip_urls first, turning
        # "nerranetwork.com" into "nerranetwork dot com"; either way the
        # whole-word "nerranetwork" entry catches the compound and splits it.
        sample = (
            "part of the Nerra Network. Find every show at nerranetwork.com. "
            "Watch on YouTube at NerraNetwork."
        )
        out = tts.prepare_text_for_tts(sample)
        # One canonical spoken form, applied to every occurrence.
        assert out.count("Nerra Network") == 3
        # No un-normalized compound and no phonetic respelling survive.
        assert "NerraNetwork" not in out
        for bad in _BANNED_RESPELLINGS:
            assert bad not in out

    def test_bare_nerra_left_as_word(self):
        # The bare brand is already a real word — Grok says it natively, never
        # respelled (which is what produced the "N-E-H dash ruh" garble).
        out = tts.prepare_text_for_tts("The Nerra family of shows.")
        assert "Nerra" in out
        for bad in _BANNED_RESPELLINGS:
            assert bad not in out


class TestNoBrandRespellingAnywhere:
    """No phonetic respelling of the brand may live in EITHER pronunciation
    layer — the audio-only YAML map or the transcript-leaking assets dict."""

    def test_assets_layer_does_not_respell_brand(self):
        out = assets_prepare("This show is part of the Nerra Network.")
        assert "Nerra Network" in out
        for bad in _BANNED_RESPELLINGS:
            assert bad not in out

    def test_no_nerra_respelling_in_word_pronunciations(self):
        for key in WORD_PRONUNCIATIONS:
            assert "nerra" not in key.lower()

    def test_yaml_map_has_no_phonetic_brand_respelling(self):
        # The synthesis map may normalize spelling (split the compound) but must
        # never reintroduce an all-caps/hyphen phonetic guess for the brand.
        import yaml
        from pathlib import Path

        corrections = yaml.safe_load(
            Path("shows/pronunciation_map.yaml").read_text()
        )["corrections"]
        for key, val in corrections.items():
            if "nerra" in str(key).lower():
                # Allowed: a plain spelling normalization to the real words.
                assert val == "Nerra Network", (
                    f"{key!r} -> {val!r}: brand entries must normalize spelling "
                    "only, never a phonetic respelling (landmine #17)."
                )
                # Defensively reject the failure-mode shapes.
                assert not re.search(r"[A-Z]{2,}", val), "no all-caps initialism"
                assert "-" not in val, "no hyphen (Grok voices it as 'dash')"


class TestYouTubeHandleSplit:
    """EN handle splits to the spaced brand; RU handle stays one token."""

    def test_en_handle_split_to_spaced_brand(self):
        out = _maybe_append_youtube_cta("Patrick: Bye.", "@NerraNetwork")
        assert "Nerra Network" in out
        assert "NerraNetwork" not in out
        assert "@" not in out
        assert "at at" not in out.lower()

    def test_ru_handle_not_split(self):
        out = _maybe_append_youtube_cta("Ведущая: Пока.", "@NerraRU", is_ru=True)
        assert "NerraRU" in out  # a CamelCase split would mangle this on Olya
        assert "Nerra RU" not in out
        assert "@" not in out
