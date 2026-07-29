"""Drift guards for the Whisper brand-name repair (July 28 2026, P0-1).

Whisper had never been given the show vocabulary, so it wrote the
network brand as "NARA" / "Naran Network" / "naranetwork.com" in 774
committed transcript files across 13 shows. Those files are published:
SRT/ASS captions are derived from them (so the misspelling was burned
into Shorts) and they are served as ``<podcast:transcript>`` on the
audio and video feeds.

Every string asserted below was taken verbatim from the committed
transcripts before the repair, so these tests pin the fix against the
real failure set rather than an imagined one.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.transcripts import (  # noqa: E402
    build_initial_prompt,
    correct_brand_text,
    correct_brand_words,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestObservedMisspellings:
    """Each case is a real line from a committed transcript."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            # Separated form — the dominant variant (~500 occurrences).
            (
                "this show is part of the NARA Network, a family of daily podcasts",
                "this show is part of the Nerra Network, a family of daily podcasts",
            ),
            (
                "this show is part of the NARA network, a family",
                "this show is part of the Nerra network, a family",
            ),
            (
                "part of the Naran Network, a family of daily",
                "part of the Nerra Network, a family of daily",
            ),
            # Joined domain form.
            (
                "explore the whole lineup at NARANetwork.com.",
                "explore the whole lineup at NerraNetwork.com.",
            ),
            (
                "explore the whole lineup at naranetwork.com.",
                "explore the whole lineup at nerranetwork.com.",
            ),
            (
                "All our shows are free at www.naranetwork.com.",
                "All our shows are free at www.nerranetwork.com.",
            ),
            # Hyphenated form.
            (
                "at nara-network.com slash gallery.",
                "at nerra-network.com slash gallery.",
            ),
            # Spoken-URL form.
            (
                "the dispatch wall at NARA network dot com slash the DPPOD.",
                "the dispatch wall at Nerra network dot com slash the DPPOD.",
            ),
            # The RU channel handle.
            ("Find us on YouTube at NARA-RU.", "Find us on YouTube at NerraRU."),
            ("Find us on YouTube at www.nara.ru.", "Find us on YouTube at NerraRU."),
            # "@NerraNetwork" read aloud, with the preposition glued on.
            (
                "find us on YouTube at Atnara Network, links",
                "find us on YouTube at Nerra Network, links",
            ),
            (
                "find us on YouTube at Anara Network, links",
                "find us on YouTube at Nerra Network, links",
            ),
        ],
    )
    def test_misspelling_is_repaired(self, raw, expected):
        assert correct_brand_text(raw) == expected


class TestNeverOverreaches:
    """The correction is anchored on brand context, never the bare token."""

    @pytest.mark.parametrize(
        "text",
        [
            # A real transcript token that contains the stem mid-word.
            "prototype a dinarag style pattern.",
            # The Japanese city — plausible on a world-news show.
            "We visited Nara, Japan last spring.",
            "The Nara period shaped Japanese art.",
            # Stem present but no brand anchor following.
            "Nara said the deal would close Friday.",
            # Mid-word match must not fire.
            "banarama Network tour dates",
        ],
    )
    def test_unrelated_text_is_untouched(self, text):
        assert correct_brand_text(text) == text

    def test_empty_input(self):
        assert correct_brand_text("") == ""

    def test_idempotent(self):
        once = correct_brand_text("part of the NARA Network at NARANetwork.com")
        assert correct_brand_text(once) == once


class TestWordLevelRepair:
    """The per-word array feeds burned-in Shorts captions — it must be repaired.

    ``engine/captions.py`` builds ASS per-word highlight lines straight
    from ``segments[].words[].word``, so a text-only fix would leave the
    misspelling on screen.
    """

    def test_bare_stem_uses_next_word_as_anchor(self):
        words = [
            {"word": "the", "start": 0.1, "end": 0.2, "probability": 0.9},
            {"word": "NARA", "start": 0.2, "end": 0.4, "probability": 0.5},
            {"word": "Network,", "start": 0.4, "end": 0.7, "probability": 0.9},
        ]
        out = correct_brand_words(words)
        assert [w["word"] for w in out] == ["the", "Nerra", "Network,"]

    def test_self_contained_token_repaired(self):
        words = [{"word": "NARANetwork.com.", "start": 1.0, "end": 1.4, "probability": 0.6}]
        assert correct_brand_words(words)[0]["word"] == "NerraNetwork.com."

    def test_bare_stem_without_anchor_is_left_alone(self):
        words = [
            {"word": "Nara,", "start": 0.1, "end": 0.3, "probability": 0.9},
            {"word": "Japan", "start": 0.3, "end": 0.6, "probability": 0.9},
        ]
        assert [w["word"] for w in correct_brand_words(words)] == ["Nara,", "Japan"]

    def test_timings_and_probabilities_are_never_modified(self):
        words = [
            {"word": "NARA", "start": 0.25, "end": 0.44, "probability": 0.51},
            {"word": "Network", "start": 0.44, "end": 0.71, "probability": 0.93},
        ]
        out = correct_brand_words(words)
        for before, after in zip(words, out):
            assert after["start"] == before["start"]
            assert after["end"] == before["end"]
            assert after["probability"] == before["probability"]

    def test_ru_prefixed_english_words_are_not_anchors(self):
        """"ruins"/"rules"/"Russia" start with "ru" but are not the
        NerraRU channel suffix — a legitimate "Nara" before them must
        survive (Nara's temple ruins are the live collocation)."""
        for follower in ("ruins", "rules,", "Russia"):
            words = [
                {"word": "Nara", "start": 0.1, "end": 0.3, "probability": 0.9},
                {"word": follower, "start": 0.3, "end": 0.6, "probability": 0.9},
            ]
            out = correct_brand_words(words)
            assert out[0]["word"] == "Nara", follower

    def test_standalone_ru_token_still_anchors(self):
        words = [
            {"word": "NARA", "start": 0.1, "end": 0.3, "probability": 0.5},
            {"word": "-RU.", "start": 0.3, "end": 0.6, "probability": 0.9},
        ]
        assert correct_brand_words(words)[0]["word"] == "Nerra"

    def test_ru_prefixed_segment_is_not_an_anchor(self):
        from engine.transcripts import correct_brand_segments
        segments = [
            {"text": "We visited Nara"},
            {"text": "Russia announced new sanctions"},
        ]
        out = correct_brand_segments(segments)
        assert out[0]["text"] == "We visited Nara"

    def test_input_list_is_not_mutated(self):
        words = [
            {"word": "NARA", "start": 0.2, "end": 0.4, "probability": 0.5},
            {"word": "Network", "start": 0.4, "end": 0.7, "probability": 0.9},
        ]
        correct_brand_words(words)
        assert words[0]["word"] == "NARA"


class TestInitialPrompt:
    """Prevention layer: the decoder is told the vocabulary up front."""

    def test_brand_terms_always_present(self):
        prompt = build_initial_prompt()
        assert "Nerra Network" in prompt
        assert "nerranetwork.com" in prompt

    def test_show_vocabulary_is_appended(self):
        prompt = build_initial_prompt(["Tesla Shorts Time", "Cybercab"])
        assert "Tesla Shorts Time" in prompt
        assert "Cybercab" in prompt

    def test_duplicates_and_blanks_are_dropped(self):
        prompt = build_initial_prompt(["Nerra Network", "  ", "", "Starship"])
        assert prompt.count("Nerra Network") == 1
        assert "Starship" in prompt

    def test_brand_survives_an_oversized_keyword_list(self):
        """Whisper keeps the TAIL of an over-window prompt, so the brand
        must sit at the end and the total must stay under the ~224-token
        window — otherwise keyword-heavy shows (planetterrian) lose the
        very terms the prompt exists to teach."""
        huge = [f"Some Long Keyword Phrase {i}" for i in range(100)]
        prompt = build_initial_prompt(huge)
        assert prompt.rstrip(".").endswith("nerranetwork.com")
        assert "Nerra Network" in prompt
        assert len(prompt) <= 620  # cap plus the closing punctuation

    def test_transcribe_is_called_with_initial_prompt(self):
        """The prompt must actually reach faster-whisper, not just exist."""
        source = (REPO_ROOT / "engine" / "transcripts.py").read_text(encoding="utf-8")
        call = source.split("model.transcribe(", 1)[1]
        # Walk to the matching close paren so nested calls don't truncate.
        depth, end = 1, 0
        for idx, ch in enumerate(call):
            depth += (ch == "(") - (ch == ")")
            if depth == 0:
                end = idx
                break
        assert "initial_prompt=" in call[:end]


class TestBackCatalogueIsClean:
    """The committed transcripts must stay repaired.

    A regression here means either the backfill was reverted or a new
    episode shipped with the misspelling — both are listener-visible,
    because these files are the published transcript and caption source.
    """

    def test_no_committed_transcript_contains_the_misspelling(self):
        pattern = re.compile(r"\bnaran?\b[\s\-]{1,3}network\b|\bnaran?network\b", re.I)
        offenders = []
        for path in sorted((REPO_ROOT / "digests").glob("*/*_transcript.txt")):
            if pattern.search(path.read_text(encoding="utf-8")):
                offenders.append(path.name)
        assert not offenders, f"brand misspelling present in: {offenders[:10]}"

    def test_json_word_arrays_are_clean(self):
        offenders = []
        for path in sorted((REPO_ROOT / "digests").glob("*/*_transcript.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            for segment in data.get("segments", []):
                for word in segment.get("words", []) or []:
                    token = (word.get("word") or "").lower()
                    if token.startswith("nara") or token.startswith("naran"):
                        offenders.append(f"{path.name}:{word.get('word')}")
                        break
        assert not offenders, f"brand misspelling in word arrays: {offenders[:10]}"


class TestBackfillScript:
    """The one-shot repair script stays runnable and defaults to a dry run."""

    def test_dry_run_by_default(self, tmp_path):
        show = tmp_path / "digests" / "demo"
        show.mkdir(parents=True)
        txt = show / "Demo_Ep001_20260728_transcript.txt"
        txt.write_text("part of the NARA Network today", encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "fix_transcript_brand.py"),
             "--digests-dir", str(tmp_path / "digests")],
            capture_output=True, text=True, check=True,
        )
        assert "Would rewrite" in result.stdout
        assert txt.read_text(encoding="utf-8") == "part of the NARA Network today"

    def test_apply_rewrites_text_and_preserves_json_timings(self, tmp_path):
        show = tmp_path / "digests" / "demo"
        show.mkdir(parents=True)
        txt = show / "Demo_Ep001_20260728_transcript.txt"
        txt.write_text("part of the NARA Network today", encoding="utf-8")
        js = show / "Demo_Ep001_20260728_transcript.json"
        js.write_text(json.dumps({
            "language": "en",
            "duration": 12.5,
            "segments": [{
                "start": 0.0, "end": 1.0,
                "text": "the NARA Network",
                "words": [
                    {"word": "the", "start": 0.0, "end": 0.2, "probability": 0.9},
                    {"word": "NARA", "start": 0.2, "end": 0.5, "probability": 0.4},
                    {"word": "Network", "start": 0.5, "end": 1.0, "probability": 0.9},
                ],
            }],
        }), encoding="utf-8")

        subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "fix_transcript_brand.py"),
             "--digests-dir", str(tmp_path / "digests"), "--apply"],
            capture_output=True, text=True, check=True,
        )

        assert txt.read_text(encoding="utf-8") == "part of the Nerra Network today"
        data = json.loads(js.read_text(encoding="utf-8"))
        seg = data["segments"][0]
        assert seg["text"] == "the Nerra Network"
        assert [w["word"] for w in seg["words"]] == ["the", "Nerra", "Network"]
        # Timing data is the thing we must never corrupt.
        assert [w["start"] for w in seg["words"]] == [0.0, 0.2, 0.5]
        assert [w["end"] for w in seg["words"]] == [0.2, 0.5, 1.0]
        assert data["duration"] == 12.5
