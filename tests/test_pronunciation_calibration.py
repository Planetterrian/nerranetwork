"""Tests for the scripts/test_pronunciation.py pure-function pieces.

The tool itself makes real Grok TTS calls and runs faster-whisper locally,
so it can't run in CI. But the parts that DON'T touch the network — the
transcript-extractor, the similarity scorer, the table formatter — are
worth pinning so a future refactor doesn't silently break the scoring
math.

Operator caught (May 11 2026): two prior pronunciation respellings of
"Planetterrian" both shipped without testing — both turned out to be
wrong in production. The calibration tool exists so the operator can
listen-test respellings BEFORE shipping them. These tests pin the math
that powers the tool's verdict column.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import test_pronunciation as tp  # noqa: E402  (path manipulation needed)


# ---------------------------------------------------------------------------
# Carrier phrase extraction
# ---------------------------------------------------------------------------


class TestExtractWordUnderTest:

    def test_clean_carrier(self):
        out = tp._extract_word_under_test("The word is Planetterrian, that's correct.")
        assert out == "Planetterrian"

    def test_with_curly_apostrophe(self):
        out = tp._extract_word_under_test("The word is tissue, that’s correct.")
        assert out == "tissue"

    def test_grok_drops_carrier(self):
        """When Grok TTS doesn't render the carrier cleanly (e.g.
        runs words together) the extractor falls back to the full
        transcript — the scorer still computes against it, just at a
        lower confidence."""
        out = tp._extract_word_under_test("Some entirely different transcription")
        assert out == "Some entirely different transcription"

    def test_lowercase_t(self):
        out = tp._extract_word_under_test("the word is Cybertruck, that's correct.")
        assert out == "Cybertruck"


# ---------------------------------------------------------------------------
# Similarity scoring
# ---------------------------------------------------------------------------


class TestSimilarity:

    def test_identical_words_score_one(self):
        assert tp._similarity("Planetterrian", "Planetterrian") == 1.0

    def test_case_insensitive(self):
        assert tp._similarity("Tesla", "tesla") == 1.0

    def test_punctuation_ignored(self):
        assert tp._similarity("tissue", "tissue.") == 1.0
        assert tp._similarity("Tesla's", "teslas") == 1.0

    def test_completely_different_scores_low(self):
        # Real production case: "plan it TAIR ee uhn" transcribed as "Planet Terra EE and"
        score = tp._similarity("Planetterrian", "Planet Terra EE and")
        # Below 0.85 means the respelling is worse than baseline.
        assert score < 0.85

    def test_close_match_scores_high(self):
        # Grok might render "Planetterrian" as "Planetarian" — that's
        # close (one-letter difference among 13 chars). The scorer
        # treats this as ~0.83 — within the ≈-raw neutral band (5%
        # of baseline) when the baseline is 0.88 or higher.
        score = tp._similarity("Planetterrian", "Planetarian")
        assert 0.75 <= score < 0.95

    def test_empty_strings_score_zero(self):
        assert tp._similarity("", "anything") == 0.0
        assert tp._similarity("anything", "") == 0.0


# ---------------------------------------------------------------------------
# Verdict logic via _format_table
# ---------------------------------------------------------------------------


class TestVerdict:
    """The table's VERDICT column is what the operator scans to decide
    whether to keep/drop a respelling. Pin the boundary cases so a
    future tweak to the math doesn't quietly flip 'better' to '≈ raw'
    or vice versa."""

    def _result(self, sent: str, score: float, *, is_raw: bool) -> tp.Result:
        return tp.Result(
            target="Planetterrian",
            sent_text=sent,
            is_raw=is_raw,
            transcript_full=f"The word is {sent}, that's correct.",
            transcript_word=sent,
            score=score,
        )

    def test_respelling_clearly_better(self):
        results = [
            self._result("Planetterrian", 0.40, is_raw=True),
            self._result("plan-tair-ian", 0.92, is_raw=False),
        ]
        table = tp._format_table(results)
        assert "better" in table
        assert "WORSE" not in table

    def test_respelling_clearly_worse(self):
        results = [
            self._result("Planetterrian", 0.95, is_raw=True),
            self._result("plan it TAIR ee uhn", 0.30, is_raw=False),
        ]
        table = tp._format_table(results)
        assert "WORSE" in table
        assert "better" not in table

    def test_respelling_neutral_within_5_percent(self):
        results = [
            self._result("tissue", 0.96, is_raw=True),
            self._result("tish-oo", 0.93, is_raw=False),
        ]
        table = tp._format_table(results)
        # Within 5% delta → tied with baseline → respelling is redundant.
        assert "≈ raw" in table  # ≈ raw

    def test_raw_baseline_flagged_bad_when_low(self):
        results = [
            self._result("Planetterrian", 0.40, is_raw=True),
        ]
        table = tp._format_table(results)
        assert "BAD" in table


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------


class TestCliEntryPoints:
    """Smoke-check the CLI dispatch without hitting Grok TTS. We mock the
    network-touching helpers so the argument-parsing + reporting paths
    can be exercised."""

    def test_requires_word_or_all(self, capsys):
        rc = tp.main([])
        captured = capsys.readouterr()
        assert rc == 2
        assert "Pass --word" in captured.err

    def test_word_flag_resolves_baked_in_candidate(self, monkeypatch, tmp_path):
        """``--word Planetterrian`` should pull the baked-in candidate
        (with its two failed respellings) rather than just testing the
        raw form alone — the value of the tool is comparing options."""
        seen: list[tp.Candidate] = []

        def _fake_evaluate(c, work_dir):
            seen.append(c)
            return []

        monkeypatch.setattr(tp, "evaluate_candidate", _fake_evaluate)
        rc = tp.main(["--word", "Planetterrian"])
        assert rc == 0
        assert len(seen) == 1
        assert seen[0].target == "Planetterrian"
        # The baked-in candidate carries the two previously-tried respellings.
        assert len(seen[0].respellings) >= 2

    def test_extra_respelling_appended(self, monkeypatch):
        seen: list[tp.Candidate] = []

        def _fake_evaluate(c, work_dir):
            seen.append(c)
            return []

        monkeypatch.setattr(tp, "evaluate_candidate", _fake_evaluate)
        rc = tp.main([
            "--word", "Planetterrian",
            "--respelling", "Planehtarrian",
        ])
        assert rc == 0
        # Custom respelling appears alongside the existing ones.
        assert "Planehtarrian" in seen[0].respellings


# ---------------------------------------------------------------------------
# Pipeline-map loader (--from-pipeline)
# ---------------------------------------------------------------------------


class TestLoadPipelineCandidates:
    """The full-sweep flag is the operator's tool for deciding which
    pronunciation overrides still earn their keep. The loader must
    pull from both production maps and deduplicate sensibly — a
    silent miss here means a respelling stays in production unreviewed."""

    def test_returns_non_empty_list(self):
        candidates = tp._load_pipeline_candidates()
        assert len(candidates) > 0
        assert all(isinstance(c, tp.Candidate) for c in candidates)
        assert all(c.target and c.respellings for c in candidates)

    def test_includes_yaml_entries(self):
        """At least one entry that lives only in pronunciation_map.yaml
        (e.g. TSLA ticker, LLM acronym) must appear."""
        candidates = tp._load_pipeline_candidates()
        targets = {c.target.lower() for c in candidates}
        # Tickers/acronyms live only in the YAML map.
        assert "tsla" in targets or "llm" in targets

    def test_includes_word_pronunciations_entries(self):
        """At least one entry that lives only in WORD_PRONUNCIATIONS
        (e.g. Cybertruck, Gigafactory) must appear."""
        candidates = tp._load_pipeline_candidates()
        targets = {c.target.lower() for c in candidates}
        assert "cybertruck" in targets or "gigafactory" in targets

    def test_case_variants_dedup_by_lowercase(self):
        """``tissue`` + ``Tissue`` + ``tissues`` + ``Tissues`` collapse
        to (at most) one Candidate per lowercased key. Grok TTS is
        case-insensitive for pronunciation so testing one representative
        covers the family."""
        candidates = tp._load_pipeline_candidates()
        lowercased = [c.target.lower() for c in candidates]
        # Each lowercased target appears exactly once.
        assert len(lowercased) == len(set(lowercased))

    def test_from_pipeline_flag_dispatches_loader(self, monkeypatch):
        """``--from-pipeline`` should call the loader and use its
        result as the target list — not the baked-in DEFAULT_CANDIDATES."""
        seen: list[tp.Candidate] = []

        def _fake_evaluate(c, work_dir):
            seen.append(c)
            return []

        sentinel = [
            tp.Candidate(target="SentinelWord", respellings=["sen-tih-nul"]),
        ]
        monkeypatch.setattr(tp, "_load_pipeline_candidates", lambda: sentinel)
        monkeypatch.setattr(tp, "evaluate_candidate", _fake_evaluate)
        rc = tp.main(["--from-pipeline"])
        assert rc == 0
        assert len(seen) == 1
        assert seen[0].target == "SentinelWord"

    def test_no_args_error_message_mentions_from_pipeline(self, capsys):
        rc = tp.main([])
        captured = capsys.readouterr()
        assert rc == 2
        assert "--from-pipeline" in captured.err
