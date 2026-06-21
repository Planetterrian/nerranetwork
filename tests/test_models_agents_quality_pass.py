"""Drift guards for the June 14 2026 Models & Agents quality pass
(docs/reviews/models_agents_review_2026_06_14.md).

Same review process as the Tesla flagship pass
(docs/tesla_review_2026_06_10.md). Pins two metadata-only fixes:

* P0 — phonetic-garble repair extended to the core AI proper nouns the
  podcast-gen step spelled phonetically despite the prompt ban. "An-thropic"
  shipped to TTS in nearly every episode (6× in Ep080); "Lah-mah" (Llama) and
  "Hah-sah-biss" (Hassabis) also leaked. These reach BOTH the audio and the
  chapter titles (parse_chapters runs after the repair), so the fix is the
  blessed deterministic-restore layer, not a prompt change.

* P1 — the Under the Hood chapter marker now also matches "pop the hood", the
  phrase the deep-dive opens with in 9-10/10 episodes (the prompt seeds it).
  Without it only 1/5 recent episodes got an Under the Hood chapter, dropping
  several below min_chapters (4) and firing the auto-segmentation fallback
  that titled chapters from raw mid-sentence text (Ep080).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.utils import fix_phonetic_garbles  # noqa: E402
from engine.chapters import parse_chapters  # noqa: E402


class TestPhoneticGarbleRepair:
    def test_anthropic_restored_with_possessive_and_compound(self):
        assert fix_phonetic_garbles(
            "suspension of An-thropic's frontier models"
        ) == "suspension of Anthropic's frontier models"
        assert "Anthropic-style" in fix_phonetic_garbles("an An-thropic-style guard")

    def test_llama_and_hassabis_restored(self):
        assert "Llama-swap" in fix_phonetic_garbles("teams using Lah-mah-swap")
        assert "Hassabis" in fix_phonetic_garbles("Demis Hah-sah-biss said")

    def test_clean_text_unchanged(self):
        clean = "Anthropic and Llama and Hassabis are fine."
        assert fix_phonetic_garbles(clean) == clean

    def test_cuda_respelling_restored(self):
        # June 21 2026 review: the shared pronunciation map respells
        # CUDA -> "koo-dah" for TTS, and that respelling leaked verbatim
        # into 12 episodes' published blog transcripts. The restore layer
        # now reverses it (same mechanism as nassa -> NASA).
        assert fix_phonetic_garbles(
            "open-sourced a koo-dah kernel"
        ) == "open-sourced a CUDA kernel"
        # Capitalised / sentence-start variant.
        assert fix_phonetic_garbles("Koo-dah kernels run on-GPU") == (
            "CUDA kernels run on-GPU"
        )

    def test_cuda_restore_is_collision_safe(self):
        # "koo-dah" has no legitimate English use, so restoration never
        # mangles ordinary prose (unlike RAG->"rag"/LoRA->"Laura", which
        # are deliberately NOT in the restore dict).
        clean = "She wore a Laura dress and grabbed a rag."
        assert fix_phonetic_garbles(clean) == clean


class TestUnderTheHoodMarker:
    def _under_the_hood_pattern(self):
        cfg = yaml.safe_load(
            (_ROOT / "shows/models_agents.yaml").read_text(encoding="utf-8")
        )
        marker = next(
            m for m in cfg["chapters"]["section_markers"]
            if m["title"] == "Under the Hood"
        )
        return marker["pattern"]

    def test_pop_the_hood_matches_under_the_hood(self):
        regex = re.compile(self._under_the_hood_pattern(), re.IGNORECASE)
        assert regex.search("Okay, let's pop the hood on this hybrid attention approach.")
        # original phrasings still match
        assert regex.search("Now let's go under the hood here.")

    def test_pop_the_hood_yields_clean_chapters(self):
        """With the marker, an episode that says 'pop the hood' but not
        'under the hood' clears min_chapters and avoids the raw-sentence
        auto-segment titles."""
        cfg = yaml.safe_load(
            (_ROOT / "shows/models_agents.yaml").read_text(encoding="utf-8")
        )
        markers = cfg["chapters"]["section_markers"]
        script = (
            "Glad you're here — welcome to Models and Agents, episode ninety.\n\n"
            "The big news today is a new model release.\n\n"
            + ("Some model news paragraph that does not name a section. " * 6) + "\n\n"
            "Okay, let's pop the hood on this hybrid attention approach.\n\n"
            + ("Engineering teardown detail building from simple to complex. " * 6) + "\n\n"
            "That's Models and Agents for today — see you tomorrow.\n"
        )
        titles = [c.title for c in parse_chapters(script, markers, show_name="ma")]
        assert "Under the Hood" in titles
        # No chapter titled from a raw mid-sentence fragment.
        assert not any(t.endswith("…") for t in titles)
