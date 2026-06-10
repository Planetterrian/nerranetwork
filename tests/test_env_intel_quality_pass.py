"""Drift guards for the June 10 2026 Environmental Intelligence quality
pass (docs/reviews/env_intel_review_2026_06_10.md) — the same review
process as the Tesla flagship pass and the four-show pass
(docs/four_show_review_2026_06_10.md), applied to a show that was
missed in those rounds.

Pins:
* chapter `where` positional anchors (Introduction=start, Tomorrow
  Teaser/Closing=end) so the Tesla chapter-bug class can't recur —
  Ep040 had shipped a "Closing" chapter at word-position 5 of 7 with
  real content after it;
* the Closing chapter pattern matches BOTH closing-pool variants (the
  "That covers today's environmental intelligence" variant previously
  matched no pattern, the MAB orphan-closing bug);
* the Industry & Practice pattern no longer matches the closing's
  "useful to your practice";
* cadence-accurate spoken copy — env_intel runs odd weekdays, so the
  intro/framing/closing must not claim "daily" or "back tomorrow";
* one unified prompt length target aligned with the tuned YAML floor
  (the prompt had demanded 1500-2200 words on a show whose episodes
  ship ~750 words, contradicting both the 900-word YAML target and the
  prompt's own "let the episode be shorter" instruction).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.intros import _SHOW_PERSONALITIES  # noqa: E402

_YAML = _ROOT / "shows/env_intel.yaml"
_PODCAST_PROMPT = _ROOT / "shows/prompts/env_intel_podcast.txt"


def _markers():
    cfg = yaml.safe_load(_YAML.read_text(encoding="utf-8"))
    return {m["title"]: m for m in cfg["chapters"]["section_markers"]}


class TestChapterPositionalAnchors:
    def test_introduction_anchored_to_start(self):
        assert _markers()["Introduction"].get("where") == "start"

    def test_closing_and_teaser_anchored_to_end(self):
        by = _markers()
        assert by["Closing"].get("where") == "end"
        assert by["Tomorrow Teaser"].get("where") == "end"

    def test_closing_pattern_matches_every_closing_variant(self):
        pattern = _markers()["Closing"]["pattern"]
        regex = re.compile(pattern, re.IGNORECASE)
        for variant in _SHOW_PERSONALITIES["env_intel"]["closings"]:
            assert regex.search(variant), (
                "env_intel closing variant ships without a Closing "
                f"chapter: {variant[:80]!r}"
            )

    def test_industry_pattern_excludes_closing_your_practice(self):
        """Bare 'practice' matched the closing's 'useful to your
        practice' and stole the final segment's title."""
        regex = re.compile(_markers()["Industry & Practice"]["pattern"], re.IGNORECASE)
        assert not regex.search("this briefing is useful to your practice")
        # but a real industry mention still matches
        assert regex.search("in practice this changes site closure criteria")


class TestCadenceAccurateCopy:
    """env_intel publishes odd weekdays — spoken copy must not claim a
    daily cadence or promise a 'tomorrow' episode."""

    def test_no_daily_or_tomorrow_in_intro_or_closing(self):
        p = _SHOW_PERSONALITIES["env_intel"]
        copy = " ".join(p["openers"] + p["framings"] + list(p["closings"])).lower()
        assert "daily" not in copy
        assert "tomorrow" not in copy


class TestUnifiedLengthTarget:
    def test_yaml_target_and_prompt_target_aligned(self):
        cfg = yaml.safe_load(_YAML.read_text(encoding="utf-8"))
        assert cfg["llm"]["min_podcast_words"] == 900
        prompt = _PODCAST_PROMPT.read_text(encoding="utf-8")
        assert "900–1300 words" in prompt

    def test_contradictory_length_targets_removed(self):
        prompt = _PODCAST_PROMPT.read_text(encoding="utf-8")
        assert "1500–2200 words" not in prompt
        assert "at least 1500 words" not in prompt
        assert "6–9 minute" not in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
