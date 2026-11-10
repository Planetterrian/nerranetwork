"""Sourcing narration is cut from every show's script (network review
2026-11-05, P0 #1).

The "<Outlet> is the source for …" cut lived only inside the opt-in absence
filter, and its pattern wanted a capitalised outlet followed by "for", so
Planetterrian spoke "Phys dot org is the source for the date, the journal…"
and "the science subreddit is the source for…" on air (Ep235-237).
"""

from __future__ import annotations

import glob
import re
from pathlib import Path

from engine.absence_sentences import cut_sourcing_clause, strip_sourcing_clauses

ROOT = Path(__file__).resolve().parent.parent


def test_lowercase_and_spoken_domain_outlets_are_cut():
    for s in (
        "Phys dot org is the source for the date, the journal, and the setting.",
        "the science subreddit is the source for the early-trial account.",
        "Fortune's transcript is the source for that raise.",
    ):
        assert strip_sourcing_clauses(s) == ("", 1)


def test_a_closing_source_clause_with_no_for_is_cut():
    text = ("Traditional Korean paper is the material, a wearable health patch "
            "is the form, and Phys dot org is the source.")
    assert strip_sourcing_clauses(text) == (
        "Traditional Korean paper is the material, a wearable health patch is the form.", 1)


def test_the_fact_after_the_clause_stays():
    s = ("Environment Canada is the source for those figures, and the current "
         "reading given is eleven point zero degrees.")
    assert cut_sourcing_clause(s) == "The current reading given is eleven point zero degrees."


def test_attribution_on_a_fact_stays():
    for s in (
        "Drier Texas rivers showed simpler food webs, according to Phys dot org.",
        "Space X has set Flight fifteen for Friday, Teslarati reported.",
        "Oil is a source of revenue for Alberta.",
    ):
        assert strip_sourcing_clauses(s) == (s, 0)


def test_structure_and_urls_are_untouched():
    text = "## Phys dot org is the source\nSource: https://phys.org/x is the source for it."
    assert strip_sourcing_clauses(text) == (text, 0)


def test_runs_on_every_show_not_only_the_absence_filter():
    src = (ROOT / "run_show.py").read_text(encoding="utf-8")
    i = src.index("strip_sourcing_clauses(podcast_script)")
    window = src[max(0, i - 600):i]
    assert "absence_sentence_filter" not in window


def test_every_committed_match_is_sourcing_narration():
    """The sweep the widening was checked against: no committed script,
    digest or reader text has a cut that removes a fact-only sentence. A cut
    sentence must name the source relation; anything else is a false hit."""
    for path in glob.glob(str(ROOT / "digests" / "*" / "*_tts.txt")):
        for s in re.split(r"(?<=[.!?])\s+", Path(path).read_text(encoding="utf-8")):
            s = s.strip()
            if cut_sourcing_clause(s) != s:
                assert re.search(r"\b(?:is|are|was|were) the sources?\b", s), (path, s)
