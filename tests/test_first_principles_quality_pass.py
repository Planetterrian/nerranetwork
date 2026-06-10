"""Drift guards for the June 10 2026 First Principles Daily quality pass
(docs/reviews/first_principles_review_2026_06_10.md).

Same review process as the Tesla flagship pass — applied to the FP show.

Pins:
* FP chapter markers carry positional ``where`` anchors (Introduction=start,
  Closing=end) — FP was missed by the Tesla/four-show chapter hardening, so
  the closing's "First Principles Daily" mention re-opened a second
  "Introduction" chapter on the sign-off and Ep001-004 shipped with no
  Closing chapter.
* every FP closing-pool variant (and the Ep1 special closing) is matched by
  the Closing chapter pattern, so no episode ships without a Closing chapter.
* a realistic FP script — intro + body + the brand-heavy closing variant —
  parses to a single Introduction (first) and a real Closing (last).
* the podcast expansion retry is narrative-aware: narrative shows (FP, UC)
  expand by DEEPENING the single topic from the brief, not by the
  news-framed "cover more stories" instruction that did nothing for them.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.chapters import parse_chapters  # noqa: E402
from engine.generator import _build_expansion_retry_prompt  # noqa: E402
from engine.intros import _SHOW_PERSONALITIES, build_closing_block  # noqa: E402


def _fp_markers():
    cfg = yaml.safe_load((_ROOT / "shows/first_principles.yaml").read_text(encoding="utf-8"))
    return cfg["chapters"]["section_markers"]


def _closing_pattern():
    return next(m["pattern"] for m in _fp_markers() if m["title"] == "Closing")


class TestChapterPositionalAnchors:
    def test_introduction_anchored_to_start(self):
        by_title = {m["title"]: m for m in _fp_markers()}
        assert by_title["Introduction"].get("where") == "start"

    def test_closing_anchored_to_end(self):
        by_title = {m["title"]: m for m in _fp_markers()}
        assert by_title["Closing"].get("where") == "end"


class TestClosingPoolMatchesChapterPattern:
    def test_every_closing_variant_matched(self):
        regex = re.compile(_closing_pattern(), re.IGNORECASE)
        for variant in _SHOW_PERSONALITIES["first_principles"]["closings"]:
            assert regex.search(variant), (
                "FP closing-pool variant not matched by the Closing chapter "
                f"pattern — episodes using it ship without a Closing chapter: "
                f"{variant[:80]!r}"
            )

    def test_resolved_closing_block_matched(self):
        # The block actually appended to the script (build_closing_block adds
        # any network promo) must still trip the Closing pattern.
        regex = re.compile(_closing_pattern(), re.IGNORECASE)
        block = build_closing_block(
            "first_principles", episode_num=12, today_str="June 12, 2026",
        )
        assert regex.search(block), block[:120]


class TestRealScriptParsesCleanly:
    """The exact bug class: the brand-heavy closing variant 1 contains
    'First Principles Daily' (an Introduction trigger). Without the
    positional anchors it re-opened an 'Introduction' chapter at the
    sign-off (committed chapters_ep001-003 prove it)."""

    def _build_script(self):
        intro = "Welcome to First Principles Daily, episode twelve, for June twelfth."
        body_lines = []
        # ~40 lines of body to push the closing into the end window.
        body_lines.append("Today we run the magic wand number on a new subject.")
        body_lines.append("The raw material floor is small compared with the price.")
        for i in range(36):
            body_lines.append(
                f"This is body sentence number {i} carrying the reasoning forward "
                f"with concrete detail and named processes."
            )
        body_lines.append("The idiot index here sits on the order of fifty.")
        body_lines.append("That is the opportunity hiding in plain sight.")
        closing = _SHOW_PERSONALITIES["first_principles"]["closings"][0]
        return "\n".join([intro, "", *body_lines, "", closing])

    def test_single_introduction_first_and_closing_present(self):
        chapters = parse_chapters(
            self._build_script(), _fp_markers(), show_name="First Principles Daily",
        )
        titles = [c.title for c in chapters]
        assert titles, "no chapters parsed"
        assert titles[0] == "Introduction", titles
        assert titles.count("Introduction") == 1, (
            f"closing brand mention re-opened Introduction: {titles}"
        )
        assert "Closing" in titles, titles
        assert titles[-1] == "Closing", titles


class TestNarrativeExpansionRetry:
    def test_narrative_branch_deepens_not_news(self):
        p = _build_expansion_retry_prompt(935, 1500, "BRIEF", "SCRIPT", narrative=True)
        assert "DEEPENING" in p
        assert "ONE subject" in p
        # The dead news framing must be gone for narrative shows.
        assert "the day's news" not in p
        assert "MORE STORIES" not in p

    def test_news_branch_unchanged(self):
        p = _build_expansion_retry_prompt(935, 1500, "DIGEST", "SCRIPT")
        assert "the day's news" in p
        assert "MORE STORIES AT FULL DEPTH" in p

    def test_first_principles_is_narrative_mode(self):
        cfg = yaml.safe_load(
            (_ROOT / "shows/first_principles.yaml").read_text(encoding="utf-8")
        )
        assert cfg.get("narrative_mode") is True
