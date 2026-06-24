"""Drift guards for consistent "Nerra Network" brand pronunciation.

Listeners reported "Nerra" being pronounced several different ways within the
same closing segment. Root cause: the closing said the brand three ways —
the spaced "Nerra Network" (promo), the "nerranetwork.com" URL, and the
"NerraNetwork" YouTube handle — and only the spaced form was normalized, so
Grok guessed a drifting pronunciation for the other two.

Fix (2026-06-24):
  * the EN YouTube handle is split to the spaced brand in
    ``engine.intros._maybe_append_youtube_cta`` (RU "NerraRU" left intact);
  * the brand respelling moved OUT of ``assets.pronunciation`` (which leaks
    into the published transcript) and INTO ``shows/pronunciation_map.yaml``
    (audio-only), with compound coverage so all three spoken forms normalize
    to one pronunciation ("NEH-ruh Network").

These guards pin that behavior.
"""

import engine.tts as tts
from engine.intros import _maybe_append_youtube_cta
from assets.pronunciation import WORD_PRONUNCIATIONS
from assets.pronunciation import prepare_text_for_tts as assets_prepare


class TestAudioFormsNormalizeIdentically:
    """Every spoken form of the brand must reduce to the SAME pronunciation
    in the TTS (audio-only) layer."""

    def test_all_three_forms_become_neh_ruh_network(self):
        # In production the assets layer runs strip_urls first, turning
        # "nerranetwork.com" into "nerranetwork dot com"; either way the
        # whole-word "nerranetwork" entry catches the compound.
        sample = (
            "part of the Nerra Network. Find every show at nerranetwork.com. "
            "Watch on YouTube at NerraNetwork."
        )
        out = tts.prepare_text_for_tts(sample)
        # One canonical pronunciation, applied to every occurrence.
        assert out.count("NEH-ruh Network") == 3
        # No un-normalized compound and no stale respelling survive.
        assert "NerraNetwork" not in out
        assert "NAIR-uh" not in out

    def test_bare_nerra_normalized(self):
        out = tts.prepare_text_for_tts("The Nerra family of shows.")
        assert "NEH-ruh" in out
        assert "NAIR-uh" not in out


class TestTranscriptStaysClean:
    """The transcript-facing layer (assets.pronunciation, which leaks into the
    saved _tts.txt / blog / RSS) must keep the CLEAN brand — no respelling."""

    def test_assets_layer_does_not_respell_brand(self):
        out = assets_prepare("This show is part of the Nerra Network.")
        assert "Nerra Network" in out
        assert "NEH-ruh" not in out
        assert "NAIR-uh" not in out

    def test_no_nerra_respelling_in_word_pronunciations(self):
        # Moved to shows/pronunciation_map.yaml (audio-only) so it can't leak
        # into the published transcript again.
        for key in WORD_PRONUNCIATIONS:
            assert "nerra" not in key.lower()


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
