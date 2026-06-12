"""Launch drift guards for SpaceX Daily (June 2026).

The show was scaffolded with every June 2026 lesson baked in at launch;
these pins keep them from regressing:

* chapter markers carry positional ``where`` anchors (Introduction=start,
  Closing=end) — the Tesla/FP chapter-bug class where the closing's brand
  mention re-opened an "Introduction" chapter on the sign-off.
* every closing-pool variant in engine/intros.py is matched by the YAML
  Closing chapter pattern, so no episode ships without a Closing chapter
  (the MAB orphan-closing class).
* ONE unified length target: min_podcast_words floor sits just under the
  prompt's stated 1,900-2,200w target, with the digest-carrying expansion
  retry opted in.
* show memory is registered + enabled so the narrative tracker runs from
  episode 1.
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
from engine.config import load_config  # noqa: E402
from engine.intros import _SHOW_PERSONALITIES, build_closing_block  # noqa: E402
from engine.show_memory import SHOW_MEMORY_CONFIGS  # noqa: E402


def _spacex_markers():
    cfg = yaml.safe_load((_ROOT / "shows/spacex.yaml").read_text(encoding="utf-8"))
    return cfg["chapters"]["section_markers"]


def _closing_pattern():
    return next(m["pattern"] for m in _spacex_markers() if m["title"] == "Closing")


class TestConfigLoads:
    def test_full_config_loads(self):
        cfg = load_config(_ROOT / "shows/spacex.yaml")
        assert cfg.name == "SpaceX Daily"
        assert cfg.slug == "spacex"

    def test_one_length_target_with_expand_retry(self):
        cfg = load_config(_ROOT / "shows/spacex.yaml")
        assert cfg.llm.min_podcast_words == 1700
        assert cfg.llm.podcast_expand_below_target is True

    def test_memory_enabled_and_registered(self):
        cfg = load_config(_ROOT / "shows/spacex.yaml")
        assert cfg.memory_enabled is True
        assert "spacex" in SHOW_MEMORY_CONFIGS
        mem = SHOW_MEMORY_CONFIGS["spacex"]
        assert "starship" in mem.default_programs
        assert "starlink" in mem.default_programs


class TestChapterPositionalAnchors:
    def test_introduction_anchored_to_start(self):
        by_title = {m["title"]: m for m in _spacex_markers()}
        assert by_title["Introduction"].get("where") == "start"

    def test_closing_anchored_to_end(self):
        by_title = {m["title"]: m for m in _spacex_markers()}
        assert by_title["Closing"].get("where") == "end"

    def test_teaser_anchored_to_end(self):
        by_title = {m["title"]: m for m in _spacex_markers()}
        assert by_title["Tomorrow Teaser"].get("where") == "end"


class TestClosingPoolMatchesChapterPattern:
    def test_every_closing_variant_matched(self):
        regex = re.compile(_closing_pattern(), re.IGNORECASE)
        for variant in _SHOW_PERSONALITIES["spacex"]["closings"]:
            assert regex.search(variant), (
                "SpaceX closing-pool variant not matched by the Closing chapter "
                f"pattern — episodes using it ship without a Closing chapter: "
                f"{variant[:80]!r}"
            )

    def test_resolved_closing_block_matched(self):
        regex = re.compile(_closing_pattern(), re.IGNORECASE)
        block = build_closing_block(
            "spacex", episode_num=1, today_str="June 12, 2026",
        )
        assert regex.search(block), block[:120]


class TestRealScriptParsesCleanly:
    """The closing variants mention 'SpaceX' heavily; without the positional
    anchors the Introduction pattern ('SpaceX Daily|welcome to SpaceX') could
    re-open an Introduction chapter on the sign-off."""

    def _build_script(self, closing_idx: int):
        intro = "Hey, welcome to SpaceX Daily, episode one. I'm Patrick in Vancouver."
        body_lines = [
            "Here's what's happening at SpaceX today.",
            "Starship's next flight test is stacking at Starbase this week.",
        ]
        for i in range(36):
            body_lines.append(
                f"This is body sentence number {i} carrying launch detail and "
                f"named hardware forward."
            )
        body_lines.append("From an engineering standpoint, the math favors reuse.")
        body_lines.append("Before we go, tomorrow we watch the static fire window.")
        closing = _SHOW_PERSONALITIES["spacex"]["closings"][closing_idx]
        return "\n".join([intro, "", *body_lines, "", closing])

    def test_single_introduction_first_and_closing_last(self):
        for idx in range(len(_SHOW_PERSONALITIES["spacex"]["closings"])):
            chapters = parse_chapters(
                self._build_script(idx), _spacex_markers(), show_name="SpaceX Daily",
            )
            titles = [c.title for c in chapters]
            assert titles, "no chapters parsed"
            assert titles[0] == "Introduction", titles
            assert titles.count("Introduction") == 1, (
                f"closing brand mention re-opened Introduction: {titles}"
            )
            assert titles[-1] == "Closing", (idx, titles)


class TestPromptContracts:
    def test_prompts_carry_memory_placeholder(self):
        for fname in ("spacex_digest.txt", "spacex_podcast.txt"):
            text = (_ROOT / "shows/prompts" / fname).read_text(encoding="utf-8")
            assert "{narrative_memory_section}" in text, fname

    def test_podcast_prompt_states_one_length_target(self):
        text = (_ROOT / "shows/prompts/spacex_podcast.txt").read_text(encoding="utf-8")
        assert text.count("1,900") == 1, (
            "ONE unified length target: the prompt must state the word target "
            "exactly once"
        )
