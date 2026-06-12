"""Drift guards for the June 12 2026 Unintended Consequences quality pass
(docs/reviews/unintended_consequences_review_2026_06_12.md).

Same review process as the Tesla / First Principles passes — applied to UC.

Pins:
* UC chapter markers carry positional ``where`` anchors (Introduction=start,
  Closing=end) and DROP the unreliable middle semantic markers. UC was
  missed by the Tesla/four-show/FP chapter hardening: it had no anchors and
  seven keyword markers that depended on the spoken prose containing literal
  section words, while the podcast prompt forbids section labels. The show's
  own brand name ("Unintended Consequences") collided with the body
  "consequence" marker on both the intro and the sign-off — 0/10 recent
  episodes had a correct chapter shape.
* the Introduction pattern matches every intro the generator produces AND a
  generic opening-word fallback, so the first chapter is "Introduction" even
  when the LLM rewrites the supplied intro (observed ~30% of episodes).
* every UC closing-pool variant (+ the appended network promo) is matched by
  the Closing chapter pattern, so no episode ships without a Closing chapter.
* the closing pool has grown past two entries and no longer contains the
  "That wraps today's case" phrase the podcast prompt flags as recurring.
* a realistic UC script parses to a single Introduction (first) and a real
  Closing (last).
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
from engine.intros import _SHOW_PERSONALITIES, build_closing_block  # noqa: E402


def _uc_markers():
    cfg = yaml.safe_load(
        (_ROOT / "shows/unintended_consequences.yaml").read_text(encoding="utf-8")
    )
    return cfg["chapters"]["section_markers"]


def _pattern(title: str) -> str:
    return next(m["pattern"] for m in _uc_markers() if m["title"] == title)


class TestChapterPositionalAnchors:
    def test_introduction_anchored_to_start(self):
        by_title = {m["title"]: m for m in _uc_markers()}
        assert by_title["Introduction"].get("where") == "start"

    def test_closing_anchored_to_end(self):
        by_title = {m["title"]: m for m in _uc_markers()}
        assert by_title["Closing"].get("where") == "end"

    def test_unreliable_middle_markers_removed(self):
        # The label-free narrative prose never reliably contained these
        # keywords; they fired out of order and the brand collided. Only
        # Introduction + Closing should remain (auto-segmentation fills the
        # middle with in-order content titles).
        titles = [m["title"] for m in _uc_markers()]
        assert titles == ["Introduction", "Closing"], titles


class TestClosingPool:
    def test_pool_has_grown_past_two(self):
        # Two entries + a day-of-year seed shipped the same closing 3
        # episodes in a row (Ep026-028). More variety lives in the pool.
        closings = _SHOW_PERSONALITIES["unintended_consequences"]["closings"]
        assert len(closings) >= 4, len(closings)

    def test_banned_phrase_removed(self):
        # The podcast prompt's WHAT TO AVOID block flags "That wraps today's
        # case" as recurring — the closing block is supplied verbatim, so
        # the only way to honor that is to drop the phrase from the pool.
        for c in _SHOW_PERSONALITIES["unintended_consequences"]["closings"]:
            assert "wraps today's case" not in c.lower(), c[:80]

    def test_every_closing_variant_matched_by_chapter_pattern(self):
        regex = re.compile(_pattern("Closing"), re.IGNORECASE)
        for variant in _SHOW_PERSONALITIES["unintended_consequences"]["closings"]:
            assert regex.search(variant), (
                "UC closing-pool variant not matched by the Closing chapter "
                f"pattern — episodes using it ship without a Closing chapter: "
                f"{variant[:80]!r}"
            )

    def test_resolved_closing_block_matched(self):
        # build_closing_block appends the network promo — the Closing
        # pattern must still trip on the full appended block.
        regex = re.compile(_pattern("Closing"), re.IGNORECASE)
        block = build_closing_block(
            "unintended_consequences", episode_num=29, today_str="June 12, 2026",
        )
        assert regex.search(block), block[:160]


class TestRealScriptParsesCleanly:
    """The exact bug class: the brand name (intro + sign-off) and the
    closing brand mention each used to title body chapters, and the middle
    keyword markers fired out of order. A realistic script must now parse
    to Introduction-first / Closing-last with exactly one Introduction."""

    def _build_script(self, intro: str) -> str:
        # Real UC scripts are short (1-2 sentence) paragraphs separated by
        # blank lines — the structure the auto-segmentation fallback splits
        # on. Mirror that so the synthetic script segments like a real one.
        paras = ["The original idea, by most accounts, seemed entirely reasonable."]
        for i in range(40):
            paras.append(
                f"This is body paragraph number {i}, carrying the causal chain "
                f"forward with specific names, dates, and numbers that a listener "
                f"can follow without losing the thread of who did what and when."
            )
        closing = _SHOW_PERSONALITIES["unintended_consequences"]["closings"][0]
        return "\n\n".join([intro, *paras, closing])

    def test_pooled_intro_parses_clean(self):
        intro = (
            "Welcome to Unintended Consequences, episode twenty-nine, for "
            "June twelfth, twenty twenty-six. Today's case study: a story of "
            "good intentions and surprising results."
        )
        titles = [c.title for c in parse_chapters(
            self._build_script(intro), _uc_markers(), show_name="UC")]
        assert titles, "no chapters parsed"
        assert titles[0] == "Introduction", titles
        assert titles.count("Introduction") == 1, titles
        assert titles[-1] == "Closing", titles
        assert len(titles) >= 4, titles

    def test_llm_rewritten_intro_still_gets_introduction(self):
        # ep024 dropped brand + "episode N" + greeting entirely. The
        # generic opening-word fallback must still title chapter 1.
        intro = (
            "It's June fifth, two thousand twenty-six. Friday — let's wrap the "
            "week with a story that has a real lesson in it."
        )
        titles = [c.title for c in parse_chapters(
            self._build_script(intro), _uc_markers(), show_name="UC")]
        assert titles[0] == "Introduction", titles
        assert titles[-1] == "Closing", titles
