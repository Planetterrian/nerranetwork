"""Tests for ``engine.shorts_hashtags`` — auto-extract YouTube
hashtags from a podcast hook line. Each scoring signal /
de-duplication invariant has its own targeted test so a regression
in one band (multi-word, single-noun, acronym, show-keywords)
lights up a focused failure."""

from __future__ import annotations

import pytest

from engine.shorts_hashtags import (
    extract_hashtags,
    format_hashtag_line,
    _extract_acronyms,
    _extract_multi_word_entities,
    _extract_single_proper_nouns,
    _normalise_show_keywords,
)


# ---------------------------------------------------------------------------
# Multi-word entities
# ---------------------------------------------------------------------------


def test_multi_word_entity_collapses_consecutive_capitals():
    out = _extract_multi_word_entities(
        "Tesla Cybercab just got a new wireless Battery Management System."
    )
    # "Tesla Cybercab" and "Battery Management System" both qualify.
    assert "TeslaCybercab" in out
    assert "BatteryManagementSystem" in out


def test_multi_word_entity_skips_single_capitals():
    out = _extract_multi_word_entities("Tesla beats Q1 delivery target.")
    # "Tesla" alone is a SINGLE proper noun, not multi-word.
    assert out == []


def test_multi_word_entity_drops_stopword_starts():
    """A sentence starting with "The Tesla Roadster" must NOT promote
    "The" into the entity — stopwords are filtered from the
    proper-noun band."""
    out = _extract_multi_word_entities("The Tesla Roadster ships in 2027.")
    # "Tesla Roadster" qualifies (2 proper nouns); "The" is a
    # stopword so it doesn't start a run with Tesla.
    assert "TeslaRoadster" in out
    assert "TheTesla" not in out


# ---------------------------------------------------------------------------
# Single proper nouns
# ---------------------------------------------------------------------------


def test_single_proper_noun_extracted():
    out = _extract_single_proper_nouns("Tesla announced new battery sizes.")
    assert "Tesla" in out


def test_single_proper_noun_ignores_stopwords():
    out = _extract_single_proper_nouns("Today Tesla shipped a new model.")
    assert "Tesla" in out
    assert "Today" not in out  # stopword


def test_single_proper_noun_dedupes():
    out = _extract_single_proper_nouns(
        "Tesla beat Tesla's own record. Tesla wins."
    )
    # Tesla appears 3 times in the hook; only one tag.
    assert out.count("Tesla") == 1


# ---------------------------------------------------------------------------
# Acronyms
# ---------------------------------------------------------------------------


def test_acronym_extracted():
    out = _extract_acronyms("AI took over Q1 — TSLA stock jumped 12%.")
    # AI and TSLA both qualify. Q1 contains a digit + capital but
    # is 2 chars and has letter+digit; rejected as a year-like
    # marker — actually our rule requires uppercase letters, and
    # Q1 satisfies that. So it would qualify too.
    assert "AI" in out
    assert "TSLA" in out


def test_acronym_rejects_pure_digits():
    out = _extract_acronyms("In 2026 Tesla shipped 500000 units.")
    assert "2026" not in out
    assert "500000" not in out


def test_acronym_rejects_too_long():
    out = _extract_acronyms("CALIFORNIA passed new rules.")
    # > 6 chars, drops.
    assert "CALIFORNIA" not in out


def test_acronym_rejects_lowercase_mixed():
    out = _extract_acronyms("iPhone shipped today.")
    # "iPhone" is not all-caps; rejected by the acronym branch
    # (it'd qualify as a proper noun elsewhere).
    assert "iPhone" not in out


# ---------------------------------------------------------------------------
# Show keyword normalisation
# ---------------------------------------------------------------------------


def test_show_keyword_collapses_spaces():
    out = _normalise_show_keywords(
        ["tesla cybertruck", "ai agents", "modern_investing"],
    )
    assert "TeslaCybertruck" in out
    assert "AiAgents" in out
    assert "ModernInvesting" in out


def test_show_keyword_skips_blanks():
    out = _normalise_show_keywords(["", "  ", "\t", "valid"])
    assert out == ["Valid"]


def test_show_keyword_dedupes():
    out = _normalise_show_keywords(["tesla", "Tesla", "TESLA"])
    assert len(out) == 1


# ---------------------------------------------------------------------------
# extract_hashtags — ranking + dedupe across bands
# ---------------------------------------------------------------------------


def test_multi_word_outranks_single_word():
    out = extract_hashtags(
        "Tesla Cybercab beats Cybertruck.", max_hashtags=5,
    )
    # Multi-word "TeslaCybercab" comes first.
    assert out[0] == "TeslaCybercab"
    # "Cybertruck" appears as a separate single proper noun.
    assert "Cybertruck" in out


def test_substring_dedupe_prefers_longer_form():
    """When a multi-word entity contains a single proper noun
    that ALSO appears alone, the substring should NOT take a
    second hashtag slot."""
    out = extract_hashtags(
        "Tesla Cybercab launched. Tesla also revealed Roadster.",
        max_hashtags=10,
    )
    # "TeslaCybercab" wins the multi-word band; "Tesla" alone
    # should be dropped (substring of the picked entity).
    assert "TeslaCybercab" in out
    assert "Tesla" not in out


def test_max_hashtags_respected():
    """Even on a hashtag-rich hook, the function caps at max_hashtags
    so callers know the output size up-front."""
    hook = "Tesla Cybercab and OpenAI ChatGPT and Apple iPhone Pro Max."
    out = extract_hashtags(hook, max_hashtags=3)
    assert len(out) <= 3


def test_show_keywords_blend_in_at_tail():
    """When the hook produces fewer hashtags than max_hashtags,
    show keywords fill the remaining slots."""
    out = extract_hashtags(
        "Tesla launched today.",  # only "Tesla" single proper noun
        show_keywords=["AI agents", "modern investing"],
        max_hashtags=5,
    )
    assert "Tesla" in out
    assert "AiAgents" in out
    assert "ModernInvesting" in out


def test_empty_hook_returns_keyword_only():
    out = extract_hashtags("", show_keywords=["tesla"], max_hashtags=5)
    assert out == ["Tesla"]


def test_empty_hook_and_no_keywords_returns_empty():
    assert extract_hashtags("") == []


def test_real_tesla_hook():
    """End-to-end on a realistic Tesla hook from the operator's
    feedback."""
    out = extract_hashtags(
        "Tesla is hiring engineers to build a wireless Battery "
        "Management System for Cybercab that removes heavy wiring.",
        show_keywords=["tesla", "cybertruck", "ev"],
        max_hashtags=5,
    )
    # "Battery Management System" is the multi-word entity — must
    # take the top slot.
    assert "BatteryManagementSystem" in out
    # "Tesla" + "Cybercab" individually picked.
    assert "Cybercab" in out
    # 'Tesla' shows up either as a single proper noun OR as the
    # blended show keyword — either way the entity is represented.
    assert any(t.lower() == "tesla" for t in out)


# ---------------------------------------------------------------------------
# format_hashtag_line
# ---------------------------------------------------------------------------


def test_format_hashtag_line_prepends_hash():
    line = format_hashtag_line(["Tesla", "Cybercab"], ("#Shorts", "#podcast"))
    assert line == "#Tesla #Cybercab #Shorts #podcast"


def test_format_hashtag_line_skips_empties():
    line = format_hashtag_line(["", "Tesla", ""], ("#Shorts",))
    assert line == "#Tesla #Shorts"


def test_format_hashtag_line_no_static_tags():
    assert format_hashtag_line(["Tesla"]) == "#Tesla"


def test_format_hashtag_line_empty_inputs():
    assert format_hashtag_line([], ()) == ""
