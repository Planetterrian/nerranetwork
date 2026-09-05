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


class TestSep2026FlagshipPass:
    """Sep 4 2026 flagship pass (docs/reviews/flagship_review_2026_09_04.md).

    Three Grok-generated reviews (Aug 2/4/11) proposed the same M&A fixes
    with ``shipped: []`` each time. Verified against Ep153-162 before this
    pass: "Everyone talks/treats about…" opened the deep dive 10/10 (the
    podcast prompt SUPPLIED that sentence as an example opener, and the
    digest prompt supplied it too), three episodes had no Under the Hood
    chapter because the host elected that example over "pop the hood",
    and one of two closings aired 7/10.
    """

    _ROOT = Path(__file__).resolve().parent.parent

    def _podcast(self):
        return (self._ROOT / "shows/prompts/models_agents_podcast.txt").read_text(encoding="utf-8")

    def _digest(self):
        return (self._ROOT / "shows/prompts/models_agents_digest.txt").read_text(encoding="utf-8")

    def test_pop_the_hood_is_the_required_anchor(self):
        text = self._podcast()
        assert 'must contain the exact phrase "pop the hood"' in text
        # The quotable alternate that became the tic must never return.
        assert "everyone's been talking about" not in text.lower()

    def test_everyone_talks_shape_is_banned_in_both_prompts(self):
        for text in (self._podcast(), self._digest()):
            low = text.lower()
            assert "everyone talks about…" in low or "everyone talks about..." in low
            # De-seed by SHAPE: the ban names the pattern, and the prompt
            # no longer carries the literal example sentence.
            assert "as if it's a single switch you flip. in practice" not in low

    def test_digest_prompt_has_no_literal_title_placeholder(self):
        # The SpaceX Aug-15 fix: the literal ``**Title: Source Name**`` was
        # reproduced verbatim by the model. M&A's copy was never ported and
        # additionally invited ``Title: [@handle](url)`` headings.
        text = self._digest()
        assert "**Title: Source" not in text
        assert "never a link or @handle" in text or "NEVER a markdown link" in text

    def test_under_the_hood_marker_catches_the_transition_shape(self):
        cfg = yaml.safe_load((self._ROOT / "shows/models_agents.yaml").read_text(encoding="utf-8"))
        marker = next(m for m in cfg["chapters"]["section_markers"] if m["title"] == "Under the Hood")
        rx = re.compile(marker["pattern"], re.IGNORECASE)
        assert rx.search("Everyone talks about reranking as a simple quality knob.")
        assert rx.search("Everyone treats test-time scaling as simply spend more tokens.")
        assert rx.search("Okay, let's pop the hood on this one.")

    def test_closing_pool_is_pinned_to_one_signature(self):
        # Sep 4 grew the pool to four to break a tic; Sep 5's delivery
        # review reversed that on purpose — the operator asked for a
        # consistent voice and the closing is the signature (the sibling
        # plug and website surface still rotate after it). One closing,
        # and it must still hit the Closing chapter marker.
        from engine.intros import _SHOW_PERSONALITIES
        closings = _SHOW_PERSONALITIES["models_agents"]["closings"]
        assert len(closings) == 1
        cfg = yaml.safe_load((self._ROOT / "shows/models_agents.yaml").read_text(encoding="utf-8"))
        closing_rx = re.compile(
            next(m for m in cfg["chapters"]["section_markers"] if m["title"] == "Closing")["pattern"],
            re.IGNORECASE,
        )
        for c in closings:
            assert closing_rx.search(c), c

    def test_practical_marker_no_longer_fires_on_topic_words(self):
        cfg = yaml.safe_load((self._ROOT / "shows/models_agents.yaml").read_text(encoding="utf-8"))
        marker = next(m for m in cfg["chapters"]["section_markers"] if m["title"] == "Practical & Community")
        rx = re.compile(marker["pattern"], re.IGNORECASE)
        assert not rx.search("Liquid AI open-sourced the Pipette benchmarking suite.")
        assert not rx.search("an open source model dropped today")
        assert rx.search("Over in practical and community news")

    def test_ep153_shape_gets_headline_navigation(self):
        """Real Ep153 (2026-08-26): the only early marker hit was the topic
        word "open-sourced" at 8% of the script, which titled the whole
        news body "Practical & Community" and suppressed headline
        auto-segmentation. With the alternate gone the episode gets real
        per-story navigation plus its Under the Hood chapter."""
        import logging
        from engine.grok_imagine import extract_story_headlines
        logging.disable(logging.CRITICAL)
        md = self._ROOT / "digests/models_agents/Models_Agents_Ep153_20260826.md"
        tts = self._ROOT / "digests/models_agents/Models_Agents_Ep153_20260826_tts.txt"
        if not (md.exists() and tts.exists()):
            import pytest
            pytest.skip("Ep153 artifacts not on disk")
        cfg = yaml.safe_load((self._ROOT / "shows/models_agents.yaml").read_text(encoding="utf-8"))
        heads = extract_story_headlines(md.read_text(encoding="utf-8"), max_count=12)
        titles = [c.title for c in parse_chapters(
            tts.read_text(encoding="utf-8"), cfg["chapters"]["section_markers"],
            show_name="ma", story_headlines=heads)]
        assert "Practical & Community" not in titles, titles
        assert "Under the Hood" in titles, titles
        assert any(t.startswith("Qwen3.8") for t in titles), titles
        assert len(titles) >= 7, titles
