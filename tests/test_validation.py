"""Tests for engine/validation.py — post-generation digest validation."""

import pytest

from engine.validation import (
    ValidationConfig,
    SectionRule,
    validate_digest,
    check_section_overlap,
    check_item_counts,
    check_forbidden_content,
    check_within_episode_duplicates,
    check_cross_episode_repeats,
    tst_validation_config,
    ff_validation_config,
    pt_validation_config,
    ov_validation_config,
    mab_validation_config,
    ma_validation_config,
    ei_validation_config,
    mi_validation_config,
)
import re as _re


def _structural(issues):
    """Mirror run_show._empty_mandatory_section_issues."""
    return [i for i in issues if _re.search(r":\s*0\s+(?:items|chars)", i)]


class TestProseSectionStructuralGuardNetworkWide:
    """Many shows lead with a PROSE feature (FF 'Cosmic Spotlight', PT
    'Planetterrian Spotlight', EI 'Lead Story', MI 'Strategy Spotlight')
    set to min_items>=1. Those have no **bold** items, so the item-counter
    returns 0 and run_show used to force a wasteful digest regenerate on
    every episode (FF Ep087 confirmed). The prose-aware guard suppresses the
    '0 items' signal when real prose is present; a genuinely empty section
    still triggers the regenerate.
    """

    _PROSE = ("This is a substantial prose lead with real content. " * 8)

    def _digest(self, header, body):
        return f"# Show\n\n{header}\n{body}\n"

    def test_ff_prose_cosmic_spotlight_not_structural(self):
        d = (
            "# FF\n\n### Top 15 Space Stories\n"
            + "".join(f"{i}. **Story {i} headline goes here**\n   Body text.\n"
                     for i in range(1, 9))
            + "\n━━━━\n### Cosmic Spotlight\n" + self._PROSE + "\n"
        )
        _, issues, _ = validate_digest(d, ff_validation_config())
        assert not [i for i in _structural(issues) if "Cosmic Spotlight" in i]

    def test_ff_empty_cosmic_spotlight_still_structural(self):
        d = ("# FF\n\n### Top 15 Space Stories\n1. **A headline here today**\n   B.\n"
             "\n━━━━\n### Cosmic Spotlight\n\n")
        _, issues, _ = validate_digest(d, ff_validation_config())
        assert [i for i in _structural(issues) if "Cosmic Spotlight" in i]

    def test_pt_ei_mi_prose_leads_not_structural(self):
        for cfg, header, name in [
            (pt_validation_config(), "### Planetterrian Spotlight", "Planetterrian Spotlight"),
            (ei_validation_config(), "### Lead Story", "Lead Story"),
            (mi_validation_config(), "### Strategy Spotlight", "Strategy Spotlight"),
        ]:
            _, issues, _ = validate_digest(self._digest(header, self._PROSE), cfg)
            assert not [i for i in _structural(issues) if name in i], name

    def test_list_section_thin_count_still_warns(self):
        # A list section below target (but non-zero) still gets the soft
        # item-count warning — the guard only suppresses the 0-items case.
        cfg = ValidationConfig(sections=[
            SectionRule(name="Stories", pattern=r"(?:### Stories)(.*?)(?=$)", min_items=5),
        ])
        d = "# X\n\n### Stories\n1. **First headline here**\n2. **Second headline here**\n"
        issues = check_item_counts(d, cfg.sections)
        assert any("Stories" in i and "2 items" in i for i in issues)


class TestMaTopStoryProse:
    """Models & Agents' 'Top Story' is a 4-6 sentence PROSE lead, not a list.
    The old min_items=1 forced a regenerate that shrank the digest (Ep066:
    12.9k -> 9.0k chars). Now validated by length."""

    _FULL = (
        "# M&A\n\n### Top Story\n"
        "OpenAI's model cracked an 80-year math problem by leaning on structured "
        "reasoning rather than brute force. It beat prior methods on the benchmark "
        "by a wide margin. Builders can try the approach through the API today. "
        "Watch for follow-up releases as other labs respond over the coming weeks.\n\n"
        "━━━━\n### Model Updates\n**A new model**\nDetails here.\n"
    )
    _EMPTY = "# M&A\n\n### Top Story\n\n### Model Updates\n**X**\nY.\n"

    def test_full_prose_top_story_not_flagged(self):
        _, issues, _ = validate_digest(self._FULL, ma_validation_config())
        assert not [i for i in issues if "Top Story" in i]

    def test_empty_top_story_flags_zero_chars(self):
        _, issues, _ = validate_digest(self._EMPTY, ma_validation_config())
        ts = [i for i in issues if "Top Story" in i]
        assert any(_re.search(r":\s*0\s+chars", i) for i in ts)


class TestMabBigStoryProse:
    """MAB's 'The Big Story' is an 8-12 sentence PROSE section, not a bullet
    list. The old ``min_items=1`` counted ``**bold**`` items, found 0 on a
    perfectly good prose section, and forced a wasteful (quality-degrading)
    digest regenerate on essentially every episode. It's now validated by
    ``min_chars`` instead.
    """

    _FULL = (
        "# MAB\n\n### The Big Story\n"
        "A new open AI model just launched with a million-token memory. Imagine "
        "reading an entire book and remembering every page at once. Until now, "
        "models forgot the start of long chats. This matters for students across "
        "a whole textbook. You can try a free version today on the model's site.\n\n"
        "━━━━\n### Cool Stuff & Try This\n"
        "**A fun image tool**\nIt turns sketches into art.\n"
    )
    _EMPTY = "# MAB\n\n### The Big Story\n\n### Cool Stuff & Try This\n**Tool**\nBody.\n"

    def _struct(self, issues):
        # Mirror run_show._empty_mandatory_section_issues.
        return [i for i in issues if _re.search(r":\s*0\s+(?:items|chars)", i)]

    def test_full_prose_big_story_not_flagged(self):
        _, issues, _ = validate_digest(self._FULL, mab_validation_config())
        assert not [i for i in issues if "The Big Story" in i]
        assert self._struct(issues) == []  # no structural regenerate

    def test_empty_big_story_flags_zero_chars_and_triggers_regenerate(self):
        _, issues, _ = validate_digest(self._EMPTY, mab_validation_config())
        bs = [i for i in issues if "The Big Story" in i]
        assert any(_re.search(r":\s*0\s+chars", i) for i in bs)
        assert self._struct(issues)  # structural regenerate fires

    def test_min_chars_field_on_section_rule(self):
        rule = SectionRule(name="x", pattern=r"### x(.*)$", min_chars=100)
        assert rule.min_chars == 100 and rule.min_items == 0


def test_mab_digest_prompt_has_no_source_name_placeholder():
    """The 'Cool Stuff' title template used to end ': Source Name', which the
    model echoed verbatim into digests/blog/newsletter. It must not return."""
    from pathlib import Path

    text = Path("shows/prompts/mab_digest.txt").read_text(encoding="utf-8")
    assert "Source Name" not in text
from engine.content_tracker import TST_SECTION_PATTERNS, FF_SECTION_PATTERNS


SAMPLE_DIGEST = """
━━━━━━━━━━━━━━━━━━━━
### Top News
1. **Tesla Cybertruck Production Ramps Up Significantly**
   Big milestone. More trucks coming.
   Source: https://example.com/1

2. **FSD v13 Achieves Cross-Country Zero Interventions**
   Autonomous driving breakthrough.
   Source: https://example.com/2

3. **Tesla Energy Storage Revenue Doubles Year Over Year**
   Megapacks are growing fast.
   Source: https://example.com/3

4. **Model Y Refresh Spotted at Gigafactory Berlin**
   New design details emerging.
   Source: https://example.com/4

5. **Tesla Supercharger Network Reaches 60,000 Globally**
   Charging infrastructure expands.
   Source: https://example.com/5

6. **Tesla Semi Deliveries Begin to PepsiCo Fleet**
   Commercial trucking starts.
   Source: https://example.com/6

━━━━━━━━━━━━━━━━━━━━
## Tesla X Takeover: What's Hot Right Now
🎙️ Tesla X Takeover

1. 🚨 **Optimus Robot Walks Unassisted in Demo**
   Robot division making progress.

2. 🔥 **Tesla Insurance Expands to All 50 States**
   Insurance business growing.

3. 💡 **Giga Mexico Construction Accelerates**
   New factory on schedule.

━━━━━━━━━━━━━━━━━━━━
## Short Spot
📉 **Short Spot**: Margin pressure from price cuts.

━━━━━━━━━━━━━━━━━━━━
### Tesla First Principles
🧠 Battery degradation analysis.

━━━━━━━━━━━━━━━━━━━━
### Daily Challenge
💪 Calculate your EV savings today.

━━━━━━━━━━━━━━━━━━━━
✨ **Inspiration Quote:** "Innovation distinguishes between a leader and a follower." – Steve Jobs
"""


OVERLAP_DIGEST = """
━━━━━━━━━━━━━━━━━━━━
### Top News
1. **Tesla Cybertruck Production Ramps Up Significantly**
   Source: https://example.com/1

2. **FSD v13 Achieves Zero Interventions Milestone**
   Source: https://example.com/2

━━━━━━━━━━━━━━━━━━━━
## Tesla X Takeover: What's Hot Right Now
🎙️ Tesla X Takeover

1. 🚨 **Tesla Cybertruck Production Ramps Up Significantly** - Same story repeated.
   Very similar to Top News #1.

2. 🔥 **FSD v13 Achieves Zero Interventions Milestone** - Same story repeated.
   Very similar to Top News #2.
"""


class TestSectionOverlap:
    def test_no_overlap(self):
        issues = check_section_overlap(
            SAMPLE_DIGEST,
            [("headlines", "takeover_headlines")],
            TST_SECTION_PATTERNS,
            threshold=0.50,
        )
        assert len(issues) == 0

    def test_detects_overlap(self):
        issues = check_section_overlap(
            OVERLAP_DIGEST,
            [("headlines", "takeover_headlines")],
            TST_SECTION_PATTERNS,
            threshold=0.50,
        )
        assert len(issues) >= 1
        assert "similarity" in issues[0].lower() or "similar" in issues[0].lower()


class TestItemCounts:
    def test_sufficient_items(self):
        sections = [
            SectionRule(
                name="Top News",
                pattern=(
                    r"(?:### Top News|### Top 10 News)"
                    r"(.*?)"
                    r"(?=━━|## Tesla X Takeover|## Short Spot|$)"
                ),
                min_items=5,
            ),
        ]
        issues = check_item_counts(SAMPLE_DIGEST, sections)
        assert len(issues) == 0

    def test_insufficient_items(self):
        sections = [
            SectionRule(
                name="Top News",
                pattern=(
                    r"(?:### Top News|### Top 10 News)"
                    r"(.*?)"
                    r"(?=━━|## Tesla X Takeover|## Short Spot|$)"
                ),
                min_items=10,
            ),
        ]
        issues = check_item_counts(SAMPLE_DIGEST, sections)
        assert len(issues) == 1
        assert "6 items" in issues[0]

    def test_missing_section(self):
        sections = [
            SectionRule(
                name="Nonexistent",
                pattern=r"### Nonexistent Section(.*?)(?=━━|$)",
                min_items=1,
            ),
        ]
        issues = check_item_counts(SAMPLE_DIGEST, sections)
        assert len(issues) == 1
        assert "missing" in issues[0].lower()

    def test_optional_section_not_flagged(self):
        sections = [
            SectionRule(
                name="Nonexistent",
                pattern=r"### Nonexistent Section(.*?)(?=━━|$)",
                min_items=1,
                optional=True,
            ),
        ]
        issues = check_item_counts(SAMPLE_DIGEST, sections)
        assert len(issues) == 0


class TestForbiddenContent:
    def test_no_forbidden(self):
        issues = check_forbidden_content(SAMPLE_DIGEST, [r"FORBIDDEN_WORD"])
        assert len(issues) == 0

    def test_detects_forbidden(self):
        issues = check_forbidden_content(
            SAMPLE_DIGEST, [r"Cybertruck"]
        )
        assert len(issues) == 1


class TestWithinEpisodeDuplicates:
    def test_no_duplicates(self):
        issues = check_within_episode_duplicates(
            SAMPLE_DIGEST, TST_SECTION_PATTERNS
        )
        assert len(issues) == 0


class TestCrossEpisodeRepeats:
    def test_detects_repeat(self):
        recent = ["Tesla Cybertruck Production Ramps Up Significantly"]
        issues, exact_dups = check_cross_episode_repeats(
            SAMPLE_DIGEST,
            recent,
            TST_SECTION_PATTERNS,
            threshold=0.65,
        )
        assert len(issues) >= 1

    def test_no_repeats_with_different_headlines(self):
        recent = ["SpaceX Launches New Satellite"]
        issues, exact_dups = check_cross_episode_repeats(
            SAMPLE_DIGEST,
            recent,
            TST_SECTION_PATTERNS,
            threshold=0.65,
        )
        assert len(issues) == 0
        assert len(exact_dups) == 0


class TestValidateDigest:
    def test_clean_digest_passes(self):
        config = ValidationConfig()
        passed, issues, exact_dups = validate_digest(SAMPLE_DIGEST, config)
        assert passed is True
        assert len(issues) == 0
        assert len(exact_dups) == 0

    def test_empty_digest_fails(self):
        config = ValidationConfig()
        passed, issues, exact_dups = validate_digest("", config)
        assert passed is False

    def test_with_section_pairs(self):
        config = ValidationConfig(
            section_pairs=[("headlines", "takeover_headlines")],
        )
        passed, issues, exact_dups = validate_digest(
            SAMPLE_DIGEST, config, section_patterns=TST_SECTION_PATTERNS
        )
        assert passed is True


class TestPrebuiltConfigs:
    def test_tst_config(self):
        config = tst_validation_config()
        assert len(config.section_pairs) > 0
        assert len(config.sections) > 0

    def test_ff_config(self):
        config = ff_validation_config()
        assert len(config.sections) > 0

    def test_pt_config(self):
        config = pt_validation_config()
        assert len(config.sections) > 0

    def test_ov_config(self):
        config = ov_validation_config()
        assert len(config.sections) > 0


def test_ov_top_stories_matches_real_header():
    """Omni View's digest header is '## Top stories (5)' (level-2, lowercase,
    count suffix). The old `### Top \\d+` pattern never matched it, so 'Top
    Stories missing' fired a full digest regenerate on EVERY episode (Ep068
    ~232s). Pin the corrected pattern against the real header shape."""
    digest = (
        "# Omni View\n\n**HOOK:** Something happened.\n\n"
        "## Top stories (5)\n"
        "### 1) A neutral headline about the lead story today\n"
        "**What happened (neutral):** Plain-language summary of the event.\n"
        "**Steel-man each side:** The strongest case for one side rests on X. "
        "The strongest case for the other rests on Y.\n\n"
        "### 2) A second neutral headline covering another major story\n"
        "**What happened (neutral):** Another summary here.\n"
        "**Steel-man each side:** Both sides framed fairly here.\n\n"
        "### 3) Third headline\n**What happened (neutral):** x.\n**Steel-man each side:** y.\n\n"
        "### 4) Fourth headline\n**What happened (neutral):** x.\n**Steel-man each side:** y.\n\n"
        "### 5) Fifth headline\n**What happened (neutral):** x.\n**Steel-man each side:** y.\n\n"
        "## Top world stories (2)\n### 6) World headline\n**What happened (neutral):** z.\n"
    )
    passed, issues, _ = validate_digest(digest, ov_validation_config())
    assert not any("Top Stories" in i for i in issues), issues
