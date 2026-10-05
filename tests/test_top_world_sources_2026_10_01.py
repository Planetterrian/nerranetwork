"""Oct 1 2026 — Top World Ep009 shipped 8 of 10 items with no Source line
while the published lint metric read 0 missing.

The model joined each item's reader-only ``Ranks:`` clause and its
``Source:`` line; the ranking clause reads as an absence sentence by design
("no figure given"), the absence filter dropped the one-sentence line, and
the URL went with it. The filter ran AFTER the lint, so the metric and the
file disagreed. Both halves are guarded here.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.absence_sentences import strip_absence_sentences  # noqa: E402
from engine.digest_lint import items_without_source  # noqa: E402

JOINED = (
    "**Explosions heard in Ethiopia's capital: BBC**\n"
    "In Ethiopia, blasts were heard in Addis Ababa after drone flights were banned.\n"
    "Ranks: Addis residents · no figure given · immediate Source: "
    "https://www.bbc.co.uk/news/articles/c3vgygpqky9zo\n"
)
SPLIT = (
    "**Prabowo replaces police chief: CNA**\n"
    "In Indonesia, the president swapped the police chief for the narcotics agency head.\n"
    "Ranks: Indonesia's police force · scale not given · now\n"
    "Source: https://www.channelnewsasia.com/asia/prabowo\n"
)


class TestRanksLinesKeepTheirSource:
    def test_a_joined_ranks_and_source_line_survives_whole(self):
        out, removed = strip_absence_sentences(JOINED)
        assert removed == 0 and out == JOINED

    def test_a_ranks_line_on_its_own_is_structure_not_prose(self):
        out, removed = strip_absence_sentences(SPLIT)
        assert removed == 0 and out == SPLIT

    def test_an_absence_clause_with_a_source_tail_keeps_the_citation(self):
        out, removed = strip_absence_sentences(
            "The company did not disclose the price. Source: https://a.example/c\n")
        assert removed == 1 and out == "Source: https://a.example/c\n"

    def test_a_url_inside_prose_is_never_an_absence_sentence(self):
        line = "Alphabet did not disclose terms; see https://a.example/c for the filing.\n"
        assert strip_absence_sentences(line) == (line, 0)

    def test_the_lint_and_the_filter_agree_on_the_ep009_shape(self):
        digest = "# Omni View Top World News\n\n### The Ten\n" + JOINED + "\n" + SPLIT + "\n" + JOINED
        filtered, _ = strip_absence_sentences(digest)
        assert items_without_source(filtered) == items_without_source(digest) == (3, 0)


class TestRunShowMeasuresTheShippedText:
    def test_the_lint_metric_is_re_read_after_the_absence_filter(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'metrics.record("items_without_source_shipped"' in src
