"""Guards that the script-save pronunciation layer stays aligned with the Grok
voice and the garble-repair layer.

Background
----------
``assets.pronunciation.WORD_PRONUNCIATIONS`` runs at script-save time
(``run_show.py:_apply_pronunciation``) and its output is then passed through
``engine.utils.fix_phonetic_garbles`` *before* TTS / blog / RSS see the script
(``run_show.py:2284``). Any respelling whose VALUE is a key in the garble map is
a **dead round-trip**: it is produced and then immediately reverted, so it
changes neither the audio nor the published transcript. Those entries are pure
confusion (and they contradict the operator's "no phonetic respellings on the
Grok custom voice" policy — landmine #17). This guard blocks new dead
round-trips from creeping back in and documents the one tolerated exception.
"""

from assets.pronunciation import (
    COMMON_ACRONYMS,
    WORD_PRONUNCIATIONS,
    prepare_text_for_tts as assets_prepare,
)
from engine.tts import prepare_text_for_tts as tts_prepare
from engine.utils import _PHONETIC_GARBLES, fix_phonetic_garbles


# 2026-08-27: the last tolerated round-trip (``NVIDIA`` -> "En-vidia") was
# resolved the same way as every other one — moved to the audio-only YAML
# layer. The round trip was not protective after all: fix_phonetic_garbles
# matches case-insensitively, so the revert fired on "En-vidia" and TTS
# received plain "Nvidia", which shipped as "navidia" / "in video" on air.
_TOLERATED_ROUND_TRIPS: set = set()


def test_no_new_garble_redundant_respellings():
    garble_keys = {k.lower() for k in _PHONETIC_GARBLES}
    # Both script-save respelling maps run before fix_phonetic_garbles, so an
    # entry whose value is a garble key is a dead round-trip in either dict.
    overlaps = {
        k: v
        for k, v in {**COMMON_ACRONYMS, **WORD_PRONUNCIATIONS}.items()
        if v.lower() in garble_keys
    }
    assert set(overlaps) <= _TOLERATED_ROUND_TRIPS, (
        "These respelling entries are reverted by fix_phonetic_garbles "
        f"immediately after they run (dead round-trips) — drop them: {overlaps}"
    )


def test_removed_garble_redundant_entries_stay_removed():
    for word in (
        "Teslarati", "Anthropic", "Enceladus", "Qwen",
        "Llama", "Starmer", "Tianwen", "Hassabis", "NVIDIA",
    ):
        assert word not in WORD_PRONUNCIATIONS, (
            f"{word} respelling was removed as a dead round-trip — re-adding it "
            "here only leaks the respelling into the transcript before the "
            "garble layer reverts it."
        )


def test_garble_layer_still_protects_against_llm_garbles():
    # The respelling entries were redundant, but the garble map must stay —
    # it's what catches the LLM itself writing the phonetic form in the script.
    assert fix_phonetic_garbles("An-thropic and Lah-mah") == "Anthropic and Llama"
    assert "Teslarati" in fix_phonetic_garbles("per Tesla-rah-tee")
    assert "Enceladus" in fix_phonetic_garbles("the moon En-sell-uh-dus")


# --- Foreign / hard-name respellings MOVED to the audio-only YAML layer ---
# (2026-06-25) so they stop leaking the respelling into the published
# transcript while keeping the SAME audio. Each is verified two ways below:
#   1. the script-save layer (assets) now leaves the canonical spelling alone
#      -> transcript is clean,
#   2. the synthesis layer (engine.tts, shows/pronunciation_map.yaml) still
#      emits the respelling -> audio is unchanged.
_MOVED = {
    # 2026-08-27: Nvidia joined the moved set — the script-save NVIDIA entry
    # was reverted by the garble layer before TTS, so the voice never got the
    # guide ("navidia" shipped on MIT/M&A/OV). Audio-only layer now owns it.
    "Nvidia": "En-vidia",
    "Milei": "Mee-lay",
    "Mistral": "Mee-stral",
    "Cassini": "Kah-see-nee",
    "Karpathy": "Kar-pathy",
    "Amodei": "Ah-mo-day",
    "Zelensky": "Zeh-len-skee",
    "AstraZeneca": "Astra-Zeneca",
    "Afeela": "ah-FEE-lah",
    # Word-acronym guides moved from COMMON_ACRONYMS (2026-06-25).
    "EBITDA": "ee-bit-dah",
    "OPEC": "oh-peck",
    "CRISPR": "crisper",
    "JAXA": "jacksa",
    "GAAP": "gaap",
}


def test_moved_names_not_in_word_pronunciations():
    for word in _MOVED:
        assert word not in WORD_PRONUNCIATIONS, (
            f"{word} was moved to the audio-only pronunciation_map.yaml — it "
            "must not be back in the transcript-leaking WORD_PRONUNCIATIONS."
        )


def test_moved_names_clean_in_transcript_layer():
    # assets.prepare_text_for_tts feeds the saved _tts.txt / blog / RSS.
    for word, respelling in _MOVED.items():
        out = assets_prepare(f"Today {word} made news.")
        assert word in out, f"{word} should pass through the script-save layer"
        assert respelling not in out, f"{respelling} must not leak into the transcript"


def test_moved_names_still_respelled_for_audio():
    # engine.tts.prepare_text_for_tts applies shows/pronunciation_map.yaml at
    # synthesis — the Grok-bound audio must still get the pronunciation guide.
    for word, respelling in _MOVED.items():
        out = tts_prepare(f"Today {word} made news.")
        assert respelling in out, (
            f"{word} lost its audio respelling — the move to the YAML layer "
            "must preserve the exact pronunciation Grok hears."
        )
