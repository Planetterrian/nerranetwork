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


class TestClosingNotStolenByBodyMarkers:
    """June 23 2026 pass — the orphan-Closing bug the June-10 `where`
    anchors did NOT fully fix. The sign-off tagline "one example or one
    opportunity, every day" contains "opportunity", and the brand "First
    Principles Daily" contains "first principle". When the body markers
    "The Opportunity" / "The First Principle" had NOT matched earlier in the
    episode, they stole the sign-off line, dropping the Closing chapter:
    7 of the first 18 episodes (Ep001/004/007/009/011/015/017) shipped with
    NO Closing. Fix: list Closing BEFORE the body markers (EI June-11 /
    SpaceX June-18 ordering rule); `where: end` keeps it out of the body."""

    def test_closing_ordered_before_colliding_body_markers(self):
        titles = [m["title"] for m in _fp_markers()]
        assert titles.index("Closing") < titles.index("The Opportunity"), titles
        assert titles.index("Closing") < titles.index("The First Principle"), titles

    def _ep017_style_script(self):
        # Body deliberately AVOIDS "opportunity"/"could be"/"first principle"/
        # "magic wand"/"atoms" so those markers stay unmatched until the
        # sign-off line — the exact Ep017 condition that dropped Closing.
        intro = "Welcome to First Principles Daily, episode seventeen, for June twenty-second."
        body = ["Today we trace a cost that hides in the design, not the metal."]
        for i in range(36):
            body.append(
                f"Body sentence number {i} carries the reasoning forward with "
                f"concrete named processes and figures."
            )
        body.append("The idiot index here sits on the order of fifty.")
        body.append("The redesign attacked the assembly hours directly.")
        closing = _SHOW_PERSONALITIES["first_principles"]["closings"][0]
        return "\n".join([intro, "", *body, "", closing])

    def test_closing_present_when_body_lacks_opportunity(self):
        chapters = parse_chapters(
            self._ep017_style_script(), _fp_markers(),
            show_name="First Principles Daily",
        )
        titles = [c.title for c in chapters]
        assert "Closing" in titles, (
            f"Closing chapter dropped — a body marker stole the sign-off line: {titles}"
        )
        assert titles[-1] == "Closing", titles
        assert titles[0] == "Introduction", titles


class TestLessonTemplateDeSeed:
    """June 23 2026 pass — the lesson-echo tic the June-10 pass deferred on
    thin evidence (~3/5). It grew to 12 of ~16 episodes opening the lesson
    with the verbatim prompt-seeded formula "a [part] whose price greatly
    exceeds its [materials] is announcing a design problem". Same tic class
    as Omni View "strongest case" / Env Intel "You arrive at a…": a seeded
    example became a fill-in-the-blank template. De-seeded in both tracks."""

    def _episode_prompt(self):
        return (_ROOT / "shows/prompts/first_principles_episode.txt").read_text(
            encoding="utf-8"
        )

    def test_verbatim_seed_removed(self):
        text = self._episode_prompt()
        # The literal example lead-in must no longer be SEEDED as an example
        # the model copies. (It may still be quoted inside a ban instruction.)
        assert "is announcing a design problem, not a material shortage" not in text, (
            "the seeded lesson example is still present — the model will keep "
            "echoing it verbatim"
        )

    def test_fresh_phrasing_required(self):
        text = self._episode_prompt()
        assert "phrased FRESHLY" in text
        # The ban on the stock formula must be present.
        assert text.lower().count("stock formula") >= 1


class TestDigestExpansionRetry:
    def test_fp_opts_into_digest_expansion(self):
        cfg = yaml.safe_load(
            (_ROOT / "shows/first_principles.yaml").read_text(encoding="utf-8")
        )
        assert cfg["llm"]["digest_expand_below_target"] is True
        # Trigger set below the observed grok-4.3 ~1200-1500w plateau.
        assert 0 < cfg["llm"]["min_digest_words"] <= 1500

    def test_narrative_digest_retry_deepens_not_more_stories(self):
        from engine.generator import _build_digest_expansion_retry_prompt
        p = _build_digest_expansion_retry_prompt(900, 1400, "BRIEF", narrative=True)
        assert "DEEPENING" in p
        assert "ONE subject" in p
        assert "more stories" not in p.lower()

    def test_news_digest_retry_unchanged(self):
        from engine.generator import _build_digest_expansion_retry_prompt
        p = _build_digest_expansion_retry_prompt(900, 1400, "DIGEST")
        assert "under-covers" in p

    def test_config_defaults_are_noop(self):
        # The new fields must default to a byte-for-byte no-op for every
        # show that does not opt in.
        from engine.config import LLMConfig
        c = LLMConfig()
        assert c.min_digest_words == 0
        assert c.digest_expand_below_target is False
