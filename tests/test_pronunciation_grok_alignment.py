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

from assets.pronunciation import WORD_PRONUNCIATIONS
from engine.utils import _PHONETIC_GARBLES, fix_phonetic_garbles


# ``NVIDIA`` -> "En-vidia" is reverted by the garble layer to "Nvidia" (a
# DIFFERENT token than the "NVIDIA" key), so removing it could let an all-caps
# "NVIDIA" reach Grok and letter-split. Kept until the A/B-listen batch settles
# it; every other garble-reverted respelling has been dropped.
_TOLERATED_ROUND_TRIPS = {"NVIDIA"}


def test_no_new_garble_redundant_respellings():
    garble_keys = {k.lower() for k in _PHONETIC_GARBLES}
    overlaps = {
        k: v for k, v in WORD_PRONUNCIATIONS.items() if v.lower() in garble_keys
    }
    assert set(overlaps) <= _TOLERATED_ROUND_TRIPS, (
        "These WORD_PRONUNCIATIONS entries are reverted by fix_phonetic_garbles "
        f"immediately after they run (dead round-trips) — drop them: {overlaps}"
    )


def test_removed_garble_redundant_entries_stay_removed():
    for word in (
        "Teslarati", "Anthropic", "Enceladus", "Qwen",
        "Llama", "Starmer", "Tianwen", "Hassabis",
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
