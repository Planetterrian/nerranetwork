"""A field label is not a headline (Nov 24 2026).

Omni View writes every story under bold field labels (``**What happened
(neutral):**`` and three more). ``engine.validation`` read each label as a
story headline: across the Nov 22-24 slate all 268 duplicate findings in
68 show runs were these four labels, on Omni View alone (~80 issues a
run). Each run then called the duplicate-story stripper for nothing and
handed the labels to run_show's exact-repeat stripper, which was only
harmless because the podcast copy of the digest carries no bold.

The item COUNT keeps reading the bold spans: Omni View's ``min_items`` is
met by them, and a zero there forces a digest regeneration every episode.
"""
from pathlib import Path

import pytest

from engine.content_tracker import SHOW_SECTION_PATTERNS
from engine.validation import (
    _extract_headline_items,
    _extract_items_from_section,
    _is_label_span,
    check_cross_episode_repeats,
    check_item_counts,
    check_within_episode_duplicates,
    ov_validation_config,
    validate_digest,
)

ROOT = Path(__file__).resolve().parent.parent
LABELS = (
    "What happened (neutral):",
    "Context & perspectives:",
    "Questions to consider:",
    "Read more (sources):",
)
# The Nov 24 2026 episode's own structure, cut to three stories.
DIGEST = """# Omni View — Omni-View Briefing

## Today's lead story (1)
### 1) Malaysia sets dates to send Rohingya back to Myanmar
**What happened (neutral):** Prime Minister Anwar Ibrahim told parliament that Malaysia will send more than 6,500 Rohingya refugees back to Myanmar.

**Context & perspectives:** CONTESTED. Rights groups called an earlier scheme opaque.

**Questions to consider:** Will the three navy vessels leave on December 6 and 7?

**Read more (sources):**
- https://example.com/a

## Major world stories (3)
### 1) South Korea scrambles jets after Russian planes near Ulleung
**What happened (neutral):** South Korea scrambled fighter jets after Russian military planes approached on Tuesday.

**Context & perspectives:** South Korea's Foreign Ministry conveyed regret to Russia.

**Read more (sources):**
- https://example.com/b

### 2) World Food Programme warns three sea chokepoints are pricing out aid
**What happened (neutral):** Luke Lindberg told the UN Security Council that disruption at three sea routes is raising food and aid costs.

**Context & perspectives:** About 30 percent of global fertiliser supplies pass through Hormuz.

**Read more (sources):**
- https://example.com/c

### Also Today
**Sheikh Hasina plans to return to Bangladesh from exile on December 16: Al Jazeera**
She said so in a statement.

**Pennsylvania reports ninth measles death in ongoing state outbreak: Al Jazeera**
The state health department confirmed it.

## Understanding the Issue: A return order is not a ban
Prose.
"""
PATTERNS = SHOW_SECTION_PATTERNS["omni_view"]


class TestALabelIsNotAHeadline:
    @pytest.mark.parametrize("label", LABELS)
    def test_the_four_omni_view_labels(self, label):
        assert _is_label_span(label)

    @pytest.mark.parametrize("headline", [
        "Sheikh Hasina plans to return to Bangladesh from exile on December 16: Al Jazeera",
        "Tesla recalls 12,000 Cybertrucks over a wiper motor",
        "Title: Source Name",
    ])
    def test_a_headline_with_a_colon_inside_is_still_a_headline(self, headline):
        assert not _is_label_span(headline)

    def test_the_fixture_matches_a_committed_digest(self):
        """The labels are what the show really writes, not a guess."""
        digests = sorted((ROOT / "digests" / "omni_view").glob("Omni_View_Ep*_2026*.md"))
        digests = [p for p in digests if not p.name.endswith("_reader.md")]
        if not digests:
            pytest.skip("no committed Omni View digest")
        text = digests[-1].read_text(encoding="utf-8")
        found = [label for label in LABELS if f"**{label}**" in text]
        assert len(found) >= 3, found

    def test_no_label_is_compared_as_a_story(self):
        items = _extract_headline_items(DIGEST, PATTERNS["headlines"])
        assert not [i for i in items if i in LABELS]
        assert any("Sheikh Hasina" in i for i in items)

    def test_the_repeated_labels_are_not_duplicates(self):
        assert check_within_episode_duplicates(DIGEST, PATTERNS) == []

    def test_yesterdays_labels_are_not_a_blocking_repeat(self):
        # What the tracker really holds for a recent Omni View episode.
        recent = list(LABELS) + ["Danish court backs law used to evict residents: Al Jazeera"]
        issues, exact = check_cross_episode_repeats(DIGEST, recent, PATTERNS)
        assert issues == []
        assert exact == []

    def test_validate_digest_reports_nothing_for_labels_alone(self):
        passed, issues, exact = validate_digest(
            DIGEST, ov_validation_config(),
            section_patterns=PATTERNS, recent_headlines=list(LABELS),
        )
        assert not [i for i in issues if "Duplicate" in i or "repeat" in i], issues
        assert exact == []


class TestRealDuplicatesAreStillCaught:
    def test_a_story_told_twice_in_one_episode(self):
        twice = DIGEST.replace(
            "**Pennsylvania reports ninth measles death in ongoing state outbreak: Al Jazeera**",
            "**Sheikh Hasina plans to return to Bangladesh from exile on December 16: Al Jazeera**",
        )
        issues = check_within_episode_duplicates(twice, PATTERNS)
        assert len(issues) == 1 and "Sheikh Hasina" in issues[0]

    def test_a_story_repeated_from_a_recent_episode(self):
        recent = ["Sheikh Hasina plans to return to Bangladesh from exile on December 16: Al Jazeera"]
        issues, exact = check_cross_episode_repeats(DIGEST, recent, PATTERNS)
        assert len(exact) == 1 and "Sheikh Hasina" in exact[0]
        assert any("BLOCKING" in i for i in issues)


class TestTheItemCountIsUntouched:
    def test_the_count_still_reads_the_bold_spans(self):
        """Omni View's min_items=4 is met by these spans; filtering them
        here would force a digest regeneration on every episode."""
        rule = ov_validation_config().sections[0]
        whole = _extract_items_from_section(DIGEST, rule.pattern)
        assert [i for i in whole if i in LABELS]
        assert len(whole) >= rule.min_items
        assert check_item_counts(DIGEST, [rule]) == []
